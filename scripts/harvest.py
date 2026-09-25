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
import math
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dispread.session_profile import SessionProfile  # noqa: E402
from dispread.timing_calibration import DEFAULT_CALIBRATION_PATH, load_calibration  # noqa: E402

#: Geraetebereich des Normierungsfaktors am GSV-2AS (CLAUDE.md, gemessen
#: gegen scripts/sync-record.py::NORM_MIN/NORM_MAX). Nur zur Validierung,
#: keine eigene Messung und kein neu erfundener Wert.
_DEVICE_NORM_MIN, _DEVICE_NORM_MAX = 0.15, 1_580_000.0

#: Zwei aufeinanderfolgende Faktoren im Plan muessen mindestens diesen
#: Faktor auseinanderliegen, damit jeder Schritt ein grosser Wechsel ist
#: (Plan, Task 4, Interfaces).
_MIN_STEP_RATIO = 1.3

_DEFAULT_MIN_GAP_MS = 300.0
_DEFAULT_MAX_GAP_MS = 800.0
_DEFAULT_HOLD_S = 4.0

_SYNC_RECORD_SCRIPT = Path(__file__).parent / "sync-record.py"
_GATE_LABEL_SCRIPT = Path(__file__).parent / "gate-label.py"


class HarvestError(RuntimeError):
    """Ernte-Lauf abgebrochen - keine Kamera/Port-Zugriffe mehr danach."""


def _round_sig(value: float, digits: int) -> float:
    """Rundet `value` auf `digits` signifikante Stellen."""
    if value == 0:
        return 0.0
    shift = digits - int(math.floor(math.log10(abs(value)))) - 1
    return round(value, shift)


def plan_factors(
    n_steps: int, seed: int, lo: float = 0.5, hi: float = 9000.0
) -> list[float]:
    """Erzeugt `n_steps` log-uniform verteilte Normierungsfaktoren.

    Deterministisch je `seed`. Jeder Faktor ist auf 4 signifikante Stellen
    gerundet, liegt im Geraetebereich (0,15...1 580 000) und mindestens um
    den Faktor 1,3 vom vorherigen entfernt.
    """
    if n_steps < 1:
        raise ValueError(f"n_steps muss >= 1 sein, ist {n_steps}")
    if not (0 < lo < hi):
        raise ValueError(f"0 < lo < hi verletzt: lo={lo}, hi={hi}")

    rng = random.Random(seed)
    log_lo, log_hi = math.log(lo), math.log(hi)
    factors: list[float] = []
    max_attempts = 100_000
    attempts = 0
    while len(factors) < n_steps:
        attempts += 1
        if attempts > max_attempts:
            raise HarvestError(
                f"plan_factors: nach {max_attempts} Versuchen keine {n_steps} "
                "gueltigen Faktoren gefunden (Bereich/Mindestabstand zu eng?)"
            )
        candidate = _round_sig(math.exp(rng.uniform(log_lo, log_hi)), 4)
        if not (_DEVICE_NORM_MIN <= candidate <= _DEVICE_NORM_MAX):
            continue
        if factors:
            prev = factors[-1]
            ratio = max(candidate, prev) / min(candidate, prev)
            if ratio < _MIN_STEP_RATIO:
                continue
        factors.append(candidate)
    return factors


def _format_num(value: float) -> str:
    """Kompakte Zahlendarstellung ohne unnoetige Nachkommastellen/Exponenten,
    kompatibel mit `sync-record.py::_parse_norm_schedule` (nutzt `float()`)."""
    text = f"{value:.10g}"
    return text


def build_schedule(factors: list[float], hold_s: float) -> str:
    """Baut den `--norm-schedule`-String `'f1:hold,f2:hold,...'`."""
    hold_text = _format_num(hold_s)
    return ",".join(f"{_format_num(f)}:{hold_text}" for f in factors)


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
    ein v2-Profil (IMX500, `camera is None`) ist, das Aufloesungs-Gate nicht
    bestanden hat, die Timing-Kalibrierung nicht ladbar ist, sie zu einer
    anderen Kamera-USB-ID gehoert, oder `hold_s` zu kurz fuer ein labelbares
    Plateau ist. Bricht nach `sync-record.py` ab, wenn dessen Exitcode != 0
    ist - `gate-label.py` wird dann gar nicht erst gestartet.
    """
    profile_path = Path(profile_path)
    profile = SessionProfile.load(profile_path)
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
    try:
        calibration = load_calibration(calibration_path)
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
        "15",
        "--image-format",
        "jpg",
        "--norm-schedule",
        schedule,
        "--duration",
        str(duration),
        "--output",
        str(recording_dir),
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
        "calibration_sha256": hashlib.sha256(calibration_path.read_bytes()).hexdigest(),
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
    parser.add_argument("--profile", type=Path, required=True, help="Pfad zu profile.json")
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
