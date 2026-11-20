#!/usr/bin/env python3
"""Faktorplan und Ernte-Lauf (Ernte Phase 1, Task 4,
docs/superpowers/plans/2026-09-23-ernte-phase1.md).

Erzeugt einen deterministischen Ablaufplan grosser Normierungsspruenge,
fuehrt damit `sync-record.py --norm-schedule` und anschliessend
`gate-label.py` als Subprozesse aus und schreibt ein Ernte-Protokoll
(`harvest.json`). Setzt ein bestaetigtes `SessionProfile` (Task 1) voraus:
ohne `resolution_ok=True` wird gar nicht erst gestartet.

StreamCam-Umstieg 2026-09-25 (Task 5): M (`--guard-margin-ms` fuer
`gate-label.py`) kommt seither aus einer Timing-Kalibrierungsdatei
(`dispread.timing_calibration`), nicht mehr aus einer festen Konstante - die
695 ms aus `docs/VALIDATION.md` waren fuer die IMX500 gemessen und gelten
nicht fuer die StreamCam. Ein v2-Profil (IMX500, `camera is None`) wird
abgelehnt, ebenso eine Kalibrierung fuer eine andere Kamera-USB-ID als die im
Profil.

Weder Kamera noch serieller Port werden aus diesem Prozess direkt
angefasst - das geschieht ausschliesslich in den beiden Subprozessen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _devdata import input_path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dispread.calibration.schedule import (  # noqa: E402
    MIN_STEP_RATIO,
    RECORD_FRAME_RATE,
    RECORD_STAGING_ROOT,
    ScheduleError,
    build_schedule,
    format_num,
    round_sig,
)
from dispread.calibration.schedule import plan_factors as _plan_factors  # noqa: E402
from dispread.gsv2as_serial import NORM_MAX, NORM_MIN  # noqa: E402
from dispread.session_profile import SessionProfile, require_live_profile  # noqa: E402
from dispread.timing_calibration import (  # noqa: E402
    DEFAULT_CALIBRATION_PATH,
    load_calibration_from_bytes,
)

#: Geraetebereich und Mindestschritt kommen aus `dispread.calibration.schedule`
#: (seit 2026-11-20 dort, damit `picam kalibrieren` denselben Plan nutzt).
_DEVICE_NORM_MIN, _DEVICE_NORM_MAX = NORM_MIN, NORM_MAX
_MIN_STEP_RATIO = MIN_STEP_RATIO

_DEFAULT_MIN_GAP_MS = 300.0
_DEFAULT_MAX_GAP_MS = 800.0
_DEFAULT_HOLD_S = 4.0

#: sync-record.py --frame-rate und --staging-root, siehe
#: `dispread.calibration.schedule` (RECORD_FRAME_RATE, RECORD_STAGING_ROOT).
#: `run()` lehnt vorher ab, wenn profile.camera.fps kleiner als die
#: Ziel-fps ist (die Ausduennung waere sonst wirkungslos).
_SYNC_RECORD_FRAME_RATE = RECORD_FRAME_RATE
_SYNC_RECORD_STAGING_ROOT = RECORD_STAGING_ROOT

_SYNC_RECORD_SCRIPT = Path(__file__).parent / "sync-record.py"
_GATE_LABEL_SCRIPT = Path(__file__).parent / "gate-label.py"


class HarvestError(RuntimeError):
    """Ernte-Lauf abgebrochen - keine Kamera/Port-Zugriffe mehr danach."""


_round_sig = round_sig
_format_num = format_num


def plan_factors(n_steps: int, seed: int, lo: float = 0.5, hi: float = 9000.0) -> list[float]:
    """Siehe `dispread.calibration.schedule.plan_factors`; Fehlschlag als
    `HarvestError` wie bisher."""
    try:
        return _plan_factors(n_steps, seed, lo, hi)
    except ScheduleError as exc:
        raise HarvestError(str(exc)) from exc


def run(
    *,
    profile_path: Path,
    out_dir: Path,
    n_steps: int,
    hold_s: float,
    seed: int,
    port: str,
    calibration_path: Path,
    min_gap_ms: float = _DEFAULT_MIN_GAP_MS,
    max_gap_ms: float = _DEFAULT_MAX_GAP_MS,
) -> dict:
    """Erzeugt den Faktorplan, fuehrt `sync-record.py` und `gate-label.py`
    als Subprozesse aus und schreibt `out_dir/harvest.json`.

    Bricht vor jedem Subprozessaufruf ab (`HarvestError`), wenn das Profil
    offline ist, ein v2-Profil (IMX500, `camera is None`) ist, das Aufloesungs-Gate nicht
    bestanden hat, die Timing-Kalibrierung nicht ladbar ist, sie zu einer
    anderen Kamera-USB-ID gehoert, oder `hold_s` zu kurz fuer ein labelbares
    Plateau ist. Bricht nach `sync-record.py` ab, wenn dessen Exitcode != 0
    ist - `gate-label.py` wird dann gar nicht erst gestartet.
    """
    profile_path = input_path(profile_path)
    profile = SessionProfile.load(profile_path)
    try:
        require_live_profile(profile)
    except ValueError as exc:
        raise HarvestError(str(exc)) from exc
    if profile.camera is None:
        raise HarvestError(
            "IMX500-Profil (schema_version 2), Kamera ausser Betrieb - "
            "neues Profil mit harvest-setup anlegen"
        )
    if not profile.resolution_ok:
        raise HarvestError(
            f"Sitzungsprofil {profile_path} hat resolution_ok=False - "
            "Aufloesungs-Gate nicht bestanden, Ernte-Lauf nicht gestartet "
            "(Entscheidung 3, docs/superpowers/plans/2026-09-23-ernte-phase1.md)."
        )

    calibration_path = Path(calibration_path)
    # M-4 final-review.md: Bytes EINMAL lesen, daraus parsen UND hashen -
    # `calibration_sha256` weiter unten wird aus `calibration_bytes`
    # berechnet, nicht durch ein zweites `.read_bytes()` am Ende. Sonst
    # koennte sich die Datei waehrend der minutenlangen Ernte aendern und
    # Hash/verwendetes M passten nicht mehr zusammen.
    try:
        calibration_bytes = calibration_path.read_bytes()
    except OSError as exc:
        raise HarvestError(f"Timing-Kalibrierung {calibration_path} nicht lesbar: {exc}") from exc
    try:
        calibration = load_calibration_from_bytes(calibration_bytes, source=str(calibration_path))
    except ValueError as exc:
        raise HarvestError(
            f"Timing-Kalibrierung {calibration_path} konnte nicht geladen "
            f"werden: {exc}"
        ) from exc
    if calibration.camera_usb_id != profile.camera.usb_id:
        raise HarvestError(
            f"Timing-Kalibrierung {calibration_path} ist fuer Kamera "
            f"{calibration.camera_usb_id!r}, Sitzungsprofil {profile_path} "
            f"fuer {profile.camera.usb_id!r} - Kalibrierung passt nicht zur "
            "Kamera dieser Sitzung."
        )
    guard_margin_ms = calibration.guard_margin_ms

    # final-review.md I-1 (Ledger #9): sync-record.py duennt im Kamerazweig
    # jetzt nach Zeitstempel aus (kein Sleep mehr) und lehnt selbst ab, wenn
    # --frame-rate > camera_settings.fps ist - die Ausduennung waere sonst
    # wirkungslos. `_SYNC_RECORD_FRAME_RATE` bleibt hier trotzdem fest
    # (nicht an profile.camera.fps gekoppelt): 15 Hz ist die Zielrate fuers
    # Labeln/gate-label, unabhaengig davon, wie schnell die jeweilige Kamera
    # tatsaechlich liefert - eine schnellere Kamera duennt einfach mehr aus.
    # Nur der Sonderfall "Kamera liefert langsamer als die Zielrate" muss VOR
    # dem Subprozessaufruf abgefangen werden, sonst bricht sync-record.py erst
    # nach dem Start (Exit 2) ab.
    if _SYNC_RECORD_FRAME_RATE > profile.camera.fps:
        raise HarvestError(
            f"Sitzungsprofil {profile_path} hat camera.fps={profile.camera.fps}, "
            f"kleiner als die feste sync-record.py-Ziel-fps {_SYNC_RECORD_FRAME_RATE} "
            "- die Ausduennung dort waere wirkungslos (final-review.md I-1)."
        )

    min_hold_s = 2 * guard_margin_ms / 1000.0 + 1.0
    if hold_s < min_hold_s:
        raise HarvestError(
            f"--hold-s {hold_s} ist kuerzer als 2*M/1000+1.0={min_hold_s} "
            f"(M={guard_margin_ms} ms) - das Plateau liesse kein labelbares "
            "Bild uebrig."
        )

    factors = plan_factors(n_steps, seed)
    schedule = build_schedule(factors, hold_s)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    recording_dir = out_dir / "recording"
    proposal_path = out_dir / "proposal.json"
    duration = n_steps * (hold_s + 2.0) + 10

    sync_cmd = [
        sys.executable,
        str(_SYNC_RECORD_SCRIPT),
        "--source",
        "camera",
        "--frame-rate",
        _format_num(_SYNC_RECORD_FRAME_RATE),
        "--image-format",
        "jpg",
        "--norm-schedule",
        schedule,
        "--duration",
        str(duration),
        "--output",
        str(recording_dir),
        "--staging-root",
        str(_SYNC_RECORD_STAGING_ROOT),
        "--port",
        port,
        "--camera-settings",
        str(profile_path),
    ]

    sync_result = subprocess.run(sync_cmd, capture_output=True, text=True)
    if sync_result.returncode != 0:
        raise HarvestError(
            f"sync-record.py brach mit Exitcode {sync_result.returncode} ab:\n"
            f"{sync_result.stderr}"
        )

    gate_cmd = [
        sys.executable,
        str(_GATE_LABEL_SCRIPT),
        "--recording",
        str(recording_dir),
        "--guard-margin-ms",
        _format_num(guard_margin_ms),
        "--min-gap-ms",
        _format_num(min_gap_ms),
        "--max-gap-ms",
        _format_num(max_gap_ms),
        "--output",
        str(proposal_path),
    ]
    gate_result = subprocess.run(gate_cmd, capture_output=True, text=True)
    if gate_result.returncode != 0:
        raise HarvestError(
            f"gate-label.py brach mit Exitcode {gate_result.returncode} ab:\n"
            f"{gate_result.stderr}"
        )

    # gate-label.py schreibt proposal.json["summary"] bereits mit denselben
    # Zahlen wie sein stdout-Bericht (frames_total, labeled, rejected_total,
    # rejected_by_reason je Grund inkl. 0-Zaehlwerten, distinct_label_texts)
    # - hier unveraendert uebernommen, nicht neu berechnet.
    summary = {}
    if proposal_path.is_file():
        proposal = json.loads(proposal_path.read_text())
        summary = proposal.get("summary", {})

    harvest_record = {
        "profile_path": str(profile_path),
        "session_id": profile.session_id,
        "device_id": profile.device_id,
        "out_dir": str(out_dir),
        "recording_dir": str(recording_dir),
        "proposal_path": str(proposal_path),
        "n_steps": n_steps,
        "hold_s": hold_s,
        "seed": seed,
        "factors": factors,
        "guard_margin_ms": guard_margin_ms,
        "min_gap_ms": min_gap_ms,
        "max_gap_ms": max_gap_ms,
        "gap_thresholds_provisional": True,
        "camera": profile.camera.to_dict(),
        "calibration_path": str(calibration_path),
        "calibration_sha256": hashlib.sha256(calibration_bytes).hexdigest(),
        "sync_record_exit_code": sync_result.returncode,
        "gate_label_exit_code": gate_result.returncode,
        "summary": summary,
    }
    harvest_path = out_dir / "harvest.json"
    harvest_path.write_text(json.dumps(harvest_record, indent=2, ensure_ascii=False), encoding="utf-8")
    return harvest_record


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Faktorplan erzeugen und einen Ernte-Lauf fahren: sync-record.py "
            "mit --norm-schedule aufzeichnen, dann gate-label.py labeln. "
            "Setzt ein bestaetigtes SessionProfile voraus (harvest-setup.py)."
        )
    )
    parser.add_argument("--profile", type=input_path, required=True, help="Pfad zu profile.json")
    parser.add_argument("--out-dir", type=Path, required=True, help="Zielverzeichnis des Ernte-Laufs")
    parser.add_argument("--n-steps", type=int, required=True, help="Zahl der Normierungsschritte")
    parser.add_argument(
        "--hold-s",
        type=float,
        default=_DEFAULT_HOLD_S,
        help=f"Haltezeit je Schritt in Sekunden, Vorgabe {_DEFAULT_HOLD_S}",
    )
    parser.add_argument("--seed", type=int, required=True, help="Seed fuer den deterministischen Faktorplan")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serieller Port fuer sync-record.py")
    parser.add_argument(
        "--calibration",
        type=Path,
        default=DEFAULT_CALIBRATION_PATH,
        help=(
            "Pfad zur Timing-Kalibrierung (dispread.timing_calibration), "
            f"Vorgabe {DEFAULT_CALIBRATION_PATH}. Ersetzt M aus der IMX500-Messung "
            "(695 ms) durch einen je Kamera-USB-ID gemessenen Wert."
        ),
    )
    parser.add_argument("--min-gap-ms", type=float, default=_DEFAULT_MIN_GAP_MS)
    parser.add_argument("--max-gap-ms", type=float, default=_DEFAULT_MAX_GAP_MS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run(
            profile_path=args.profile,
            out_dir=args.out_dir,
            n_steps=args.n_steps,
            hold_s=args.hold_s,
            seed=args.seed,
            port=args.port,
            calibration_path=args.calibration,
            min_gap_ms=args.min_gap_ms,
            max_gap_ms=args.max_gap_ms,
        )
    except HarvestError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
