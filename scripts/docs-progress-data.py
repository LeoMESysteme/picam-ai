#!/usr/bin/env python3
"""Erzeugt die Daten der Fortschrittsgrafik der Zensical-Doku.

Liest die Ernte- und Auswertungsdateien unter ``var/`` (nur lesend) und
schreibt ``docs-site/assets/data/fortschritt.json`` im Schema
``fortschritt_v1``. Die Datei wird versioniert, weil der Doku-Build kein
``var/`` hat.

Grundsatz: Was nicht in den Dateien steht, ist ``null``. Es wird nichts
geschätzt oder aus anderen Quellen aufgefüllt.

Die Ausgabe ist deterministisch (sortierte Schlüssel, ``indent=1``); der
einzige Zeitstempel ist ``generated_at``, festlegbar mit ``--generated-at``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "fortschritt_v1"

# Rolle je Aufstellung (setup = Verzeichnisname ohne "-run").
# * training:  Trainingsaufstellungen. sc6b ist die zweite Ernte der
#              Aufstellung sc6 und gehört zur Gruppe sc6.
# * abnahme:   ab1, ab2 = Abnahme 1, ab3, ab4 = Abnahme 2 (beide danach ins
#              Training übernommen), ab5, ab6 = Abnahme 3.
# * verworfen: sc1, sc2 — Kamera während der Ernte bewegt, Proben entfernt.
ROLES: dict[str, str] = {
    "ernte1": "training",
    "ernte2": "training",
    "auf2": "training",
    "auf3": "training",
    "sc3": "training",
    "sc4": "training",
    "sc5": "training",
    "sc6": "training",
    "sc6b": "training",
    "ab1": "abnahme",
    "ab2": "abnahme",
    "ab3": "abnahme",
    "ab4": "abnahme",
    "ab5": "abnahme",
    "ab6": "abnahme",
    "sc1": "verworfen",
    "sc2": "verworfen",
}

# Gruppe, falls weder harvest.json noch ein Profil sie nennt.
# ernte2 ist die zweite Ernte der Aufstellung ernte1 (gleiches Profil, Spec
# Abschnitt 3: "ernte1 (152, enthaelt Ernte 2, gleiche Aufstellung)").
GROUP_FALLBACK: dict[str, str] = {"sc6b": "sc6", "ernte2": "ernte1"}

# Leave-one-out-Berichte: Aeltere Berichte tragen die Normierung nicht,
# daher fest. Seit 2026-09-30 schreibt `dotmatrix-eval.py loo` sie selbst in
# den Bericht (`normalization`); fuer neue Dateien gilt dann dieser Wert.
# Reihenfolge = zeitliche Reihenfolge (Code-Commits 0d18d0a, 20d7403 (b, c),
# 021f8ab, 8908fe4, 48c31b3, dc8af22, 50d68d6, dann die Laeufe vom 2026-09-30).
# Abgeglichen mit docs/VALIDATION.md: loo (d) lief mit 021f8ab, dem ersten
# Commit von ink_per_cell_v1 ("der Lauf mit 021f8ab, …-29d.json,
# unterschied sich nur bei auf3"), ist also ink_per_cell_v1 und nicht
# ink_global_v0. "ink_global_v0" ist ein Doku-Name: vor 021f8ab trug die
# Normierung im Code keinen Namen (ein globaler Tintenpegel).
# Spalte 4 `raster`: welche Punktraster galten (VALIDATION.md 2026-09-30,
# Befund Rasterversatz). "alt" = handangepasste Profile, bei ab3/ab4/ernte1/
# auf2/auf3 0,4-0,9 Punktspalten daneben; "korrigiert" = *-profile-regrid1.
LOO_RUNS: list[tuple[str, str, str, str]] = [
    ("dotmatrix-loo-2026-09-29.json", "loo (a)", "ink_global_v0", "alt"),
    ("dotmatrix-loo-2026-09-29b.json", "loo (b)", "ink_global_v0", "alt"),
    ("dotmatrix-loo-2026-09-29c.json", "loo (c)", "ink_global_v0", "alt"),
    ("dotmatrix-loo-2026-09-29d.json", "loo (d)", "ink_per_cell_v1", "alt"),
    ("dotmatrix-loo-2026-09-29e.json", "loo (e)", "ink_per_cell_v1", "alt"),
    ("dotmatrix-loo-2026-09-29-mit-sc6.json", "9 Gruppen", "ink_per_cell_v1", "alt"),
    ("dotmatrix-loo-2026-09-29-basis-ink_per_cell_v1.json", "942 alt", "ink_per_cell_v1", "alt"),
    ("dotmatrix-loo-2026-09-29-bg_closing_v1.json", "942 neu", "bg_closing_v1", "alt"),
    ("dotmatrix-loo-2026-09-30-basis-bg_closing_v1.json", "1223 Basis", "bg_closing_v1", "alt"),
    ("dotmatrix-loo-2026-09-30-bg_closing_shadow_v1.json", "Schatten ✗", "bg_closing_shadow_v1", "alt"),
    ("dotmatrix-loo-2026-09-30-regrid1.json", "Raster 1", "bg_closing_v1", "korrigiert (ab3/ab4/auf2)"),
    ("dotmatrix-loo-2026-09-30-regrid1-ohne-ernte1-auf3.json", "ohne ernte1", "bg_closing_v1",
     "korrigiert (ab3/ab4/auf2), ohne ernte1/auf3"),
    ("dotmatrix-loo-2026-09-30-regrid2.json", "Raster 2", "bg_closing_v1", "korrigiert (+ ernte1)"),
]

# Abnahmeberichte unter var/dotmatrix/: Nummer der Abnahme je Datei. Unbekannte
# Dateien bekommen die naechste Nummer in Dateinamen-Reihenfolge.
ABNAHME_LABELS: dict[str, str] = {
    "abnahme-stufe2-2026-09-29.json": "Abnahme 1",
    "abnahme-stufe2b-2026-09-30.json": "Abnahme 2",
    "abnahme-stufe2c-2026-09-30.json": "Abnahme 3",
}


def load_json(path: Path) -> Any:
    """JSON lesen; fehlend oder unlesbar (z. B. halb geschrieben) -> None."""
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _profile_session_id(diag: Path, setup: str) -> str | None:
    base = diag / f"{setup}-profile"
    for candidate in (base / "profile.json", base):
        if candidate.is_file():
            sid = _str(_dict(load_json(candidate)).get("session_id"))
            if sid:
                return sid
    return None


def harvest_entry(diag: Path, run_dir: Path) -> dict:
    run = run_dir.name
    setup = run[: -len("-run")]
    harvest = _dict(load_json(run_dir / "harvest.json"))
    summary = _dict(harvest.get("summary"))
    session_raw = load_json(run_dir / "recording" / "session.json")
    session = _dict(session_raw)
    imp_raw = load_json(run_dir / "import.json")
    imp = _dict(imp_raw)

    group = (
        _str(harvest.get("session_id"))
        or _profile_session_id(diag, setup)
        or GROUP_FALLBACK.get(setup, setup)
    )

    recorded = _int(session.get("frames_recorded"))
    dropped = _int(session.get("frames_dropped_queue_full"))
    drop_fraction = None
    if recorded is not None and dropped is not None and recorded + dropped > 0:
        # Anteil an allen von der Kamera gelieferten Bildern (aufgenommen + verworfen).
        drop_fraction = round(dropped / (recorded + dropped), 4)

    staging_ram = None
    if isinstance(session_raw, dict):
        staging_ram = isinstance(session.get("staging"), dict)

    imported = _int(imp.get("imported"))
    import_rejected = None
    reasons = imp.get("rejected_by_reason")
    if isinstance(reasons, dict) and all(_int(v) is not None for v in reasons.values()):
        import_rejected = sum(reasons.values())

    return {
        "run": run,
        "setup": setup,
        "group": group,
        "role": ROLES.get(setup),
        "started_at_utc": _str(session.get("started_at_utc")),
        "frames_recorded": recorded,
        "frames_dropped": dropped,
        "drop_fraction": drop_fraction,
        "labeled": _int(summary.get("labeled")),
        "distinct_values": _int(summary.get("distinct_label_texts")),
        "staging_ram": staging_ram,
        "imported": imported,
        "import_rejected": import_rejected,
    }


def collect_harvests(diag: Path) -> list[dict]:
    if not diag.is_dir():
        return []
    runs = sorted(p for p in diag.iterdir() if p.is_dir() and p.name.endswith("-run"))
    entries = [harvest_entry(diag, p) for p in runs]
    return sorted(entries, key=lambda e: (e["started_at_utc"] is None, e["started_at_utc"] or "", e["run"]))


# Filter wie scripts/dotmatrix-dataset.py (_iter_resolved_records, DEVICE_NAME).
# Nachgebildet statt importiert, weil jenes Modul cv2 lädt und Bilder entzerrt;
# hier wird nur gezählt. Anders als dort wird das Profil nicht aufgelöst.
STORE_DEVICE_NAME = "gsv-sensor-161a"


def count_store_samples(dataset_root: Path) -> dict[str, int] | None:
    """Proben je Gruppe (label_origin_detail.session_id) im Datensatz-Store.

    None, wenn Store oder Gerät fehlen. Verzeichnisse mit Punkt am Anfang
    (halb geschriebene Proben eines laufenden Imports) und unlesbare
    sample.json werden übergangen.
    """
    devices = _dict(_dict(load_json(dataset_root / "devices.json")).get("devices"))
    device_id = next(
        (did for did, dev in sorted(devices.items())
         if _dict(dev).get("name") == STORE_DEVICE_NAME),
        None,
    )
    samples_dir = dataset_root / "samples"
    if device_id is None or not samples_dir.is_dir():
        return None
    counts: dict[str, int] = {}
    for sample_dir in sorted(samples_dir.iterdir()):
        if sample_dir.name.startswith(".") or not sample_dir.is_dir():
            continue
        sample = load_json(sample_dir / "sample.json")
        if not isinstance(sample, dict):
            continue
        if (sample.get("label_origin") != "serial_ascii"
                or sample.get("label_state") != "readable"
                or sample.get("device_id") != device_id):
            continue
        group = _str(_dict(sample.get("label_origin_detail")).get("session_id"))
        if group is not None:
            counts[group] = counts.get(group, 0) + 1
    return counts


def pending_import_groups(diag: Path, harvests: list[dict]) -> set[str]:
    """Gruppen mit einer Ernte, die harvest.json hat, aber kein auswertbares
    import.json: Der Import läuft noch oder ist abgebrochen, der Store-Stand
    dieser Gruppe ist daher offen."""
    return {
        h["group"] for h in harvests
        if (diag / h["run"] / "harvest.json").is_file() and h["imported"] is None
    }


def collect_dataset(harvests: list[dict], profile_map: dict,
                    store_counts: dict[str, int] | None,
                    pending: set[str] = frozenset()) -> dict:
    by_group: dict[str, list[dict]] = {}
    for h in harvests:
        by_group.setdefault(h["group"], []).append(h)
    names = sorted(set(by_group) | set(profile_map) | set(store_counts or {}))
    groups = []
    for name in names:
        role = ROLES.get(name)
        if role == "verworfen":
            samples: int | None = 0  # Proben entfernt
        elif store_counts is None or name in pending:
            samples = None
        else:
            samples = store_counts.get(name, 0)
        groups.append({
            "group": name,
            "role": role,
            "samples": samples,
            "in_profile_map": name in profile_map,
        })
    counts = [g["samples"] for g in groups if g["samples"] is not None]
    # Summe der bekannten Gruppen; null nur, wenn keine Gruppe bekannt ist.
    total = sum(counts) if counts or not groups else None
    return {"groups": groups, "total_samples": total}


def loo_groups(report: dict) -> dict:
    eligibility = _dict(_dict(report.get("training_eligibility")).get("groups"))
    out: dict[str, dict] = {}
    for run in report.get("durchgaenge") or []:
        run = _dict(run)
        group = _str(run.get("test_group"))
        if group is None:
            continue
        summary = run.get("summary")
        if isinstance(summary, dict):
            # Der Bericht führt nur vorkommende Ergebnisse; fehlend heißt 0.
            richtig = _int(summary.get("richtig", 0))
            falsch = _int(summary.get("falsch", 0))
            abgelehnt = sum(
                v for k, v in summary.items()
                if k.startswith("abgelehnt") and _int(v) is not None
            )
        else:
            richtig = falsch = abgelehnt = None
        plateaus = run.get("plateaus")
        plateaus = plateaus if isinstance(plateaus, dict) else None
        eligible = _dict(eligibility.get(group)).get("eligible")
        out[group] = {
            "richtig": richtig,
            "abgelehnt": abgelehnt,
            "falsch": falsch,
            "plateaus_richtig": _int(plateaus.get("richtig")) if plateaus else None,
            "plateaus_abgelehnt": _int(plateaus.get("abgelehnt")) if plateaus else None,
            "plateaus_falsch": _int(plateaus.get("falsch")) if plateaus else None,
            "d_max": _num(run.get("d_max")),
            "training_eligible": eligible if isinstance(eligible, bool) else None,
        }
    return out


def collect_loo(diag: Path) -> list[dict]:
    known = {row[0] for row in LOO_RUNS}
    extra = sorted(
        p.name for p in diag.glob("dotmatrix-loo-*.json") if p.name not in known
    ) if diag.is_dir() else []
    table = list(LOO_RUNS) + [
        (name, Path(name).stem.removeprefix("dotmatrix-loo-"), None, None) for name in extra
    ]
    out = []
    for order, (name, label, normalization, raster) in enumerate(table, start=1):
        report = load_json(diag / name)
        if not isinstance(report, dict):
            continue
        commit = _str(report.get("git_commit"))
        out.append({
            "file": name,
            "label": label,
            "normalization": _str(report.get("normalization")) or normalization,
            "raster": raster,
            "code_commit": commit[:7] if commit else None,
            "order": order,
            "groups": loo_groups(report),
        })
    return out


def collect_abnahmen(dotmatrix: Path) -> list[dict]:
    if not dotmatrix.is_dir():
        return []
    out = []
    next_number = len(ABNAHME_LABELS) + 1
    for path in sorted(dotmatrix.glob("abnahme-*.json")):
        report = load_json(path)
        if not isinstance(report, dict):
            continue
        normalization = _str(report.get("normalization"))
        base = ABNAHME_LABELS.get(path.name)
        if base is None:
            base = f"Abnahme {next_number}"
            next_number += 1
        label = f"{base} ({normalization})" if normalization else base
        groups = {}
        for name, entry in sorted(_dict(report.get("gruppen")).items()):
            proben = _dict(_dict(entry).get("proben"))
            groups[name] = {
                "richtig": _int(proben.get("richtig")),
                "abgelehnt": _int(proben.get("abgelehnt")),
                "falsch": _int(proben.get("falsch")),
            }
        bestanden = report.get("bestanden")
        out.append({
            "file": path.name,
            "label": label,
            "templates_sha256": _str(report.get("templates_sha256")),
            "groups": groups,
            "abgelehnt_anteil": _num(_dict(report.get("gesamt")).get("abgelehnt_anteil")),
            "bestanden": bestanden if isinstance(bestanden, bool) else None,
        })
    return out


def build(var_root: Path, generated_at: str) -> dict:
    diag = var_root / "diagnostics"
    harvests = collect_harvests(diag)
    profile_map = _dict(load_json(diag / "dotmatrix-profile-map.json"))
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "harvests": harvests,
        "dataset": collect_dataset(
            harvests, profile_map,
            count_store_samples(var_root / "workbench" / "datasets"),
            pending_import_groups(diag, harvests)),
        "loo_runs": collect_loo(diag),
        "abnahmen": collect_abnahmen(var_root / "dotmatrix"),
    }


def dumps(data: dict) -> str:
    return json.dumps(data, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--var-root", type=Path, default=Path("var"))
    parser.add_argument("--out", type=Path, default=Path("docs-site/assets/data/fortschritt.json"))
    parser.add_argument("--generated-at", default=None,
                        help="ISO-8601-Zeitstempel für generated_at (Vorgabe: jetzt, UTC)")
    args = parser.parse_args(argv)
    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    if args.out.resolve().is_relative_to(args.var_root.resolve()):
        parser.error("--out darf nicht unter --var-root liegen (var/ wird nur gelesen)")
    data = build(args.var_root, generated_at)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(dumps(data), encoding="utf-8")
    print(f"{args.out}: {len(data['harvests'])} Ernten, {len(data['loo_runs'])} loo-Läufe, "
          f"{len(data['abnahmen'])} Abnahmen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
