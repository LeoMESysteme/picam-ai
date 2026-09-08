# 5 — Die CLI

**Ziel:** `dispread run --source "folder:///…" --profile gsv-2asd-labor1
--jsonl var/lauf/values.jsonl` ersetzt das Kopieren von Beispielskripten, und
jeder Lauf hinterlässt ein Runartefakt, das sich später deuten lässt.

**Warum jetzt:** Alles ist gebaut, aber nur über Python-Aufrufe erreichbar.
Ohne CLI gibt es keinen Dienst ([Kapitel 9](09-betrieb.md)) und keine
reproduzierbare Messreihe. Hakt die ROADMAP-Zeile „CLI (`dispread.cli.*`)" ab.

**Vorbedingungen:** [Kapitel 3](03-erste-bildquelle-folder.md),
[Kapitel 4](04-geraeteprofile.md).

## Ausgangslage

`pyproject.toml` deklariert **absichtlich keine** Konsolenskripte:

> Ein deklarierter Einsprungpunkt auf ein nicht vorhandenes Modul ist
> schlechter als keiner — er scheitert erst zur Laufzeit.

Genau das war schon einmal passiert: in `.venv/bin/` lagen `dispread-doctor`
und `dispread-replay` und zeigten auf `dispread.cli.doctor`, das es nie gab.
Also: **erst Modul, dann Einsprungpunkt.**

## Unterkommandos

Fange mit den ersten drei an. Die anderen kommen in Kapitel 6 und 9 dazu.

| Kommando | Was es tut | Kapitel |
| --- | --- | --- |
| `dispread run` | Quelle + Profil + Senken verdrahten, Kette laufen lassen | hier |
| `dispread profiles` | Profile auflisten, eines anzeigen, eines prüfen | hier |
| `dispread inspect` | `values.jsonl` auswerten: Statusverteilung, Ablehnungsgründe, Latenzen | hier |
| `dispread doctor` | `scripts/camera-commissioning.sh` aufrufen und die Umgebung prüfen | 6 |
| `dispread roi` | ROI-Vorschau erzeugen, Profil schreiben | 4/6 |
| `dispread record` | Aufnahmesession mit Manifest schreiben | 6 |

## Struktur

```
src/dispread/cli/
    __init__.py      main(argv) -> int, Subparser-Registrierung
    __main__.py      python -m dispread.cli
    run.py           add_parser(sub) + execute(args) -> int
    profiles.py
    inspect.py
```

Zwei Regeln, die den Unterschied zwischen einer CLI und einem Skripthaufen
machen:

1. **Keine Fachlogik in der CLI.** Sie liest Argumente, baut Objekte, ruft die
   Pipeline und schreibt den Bericht. Wenn du in `run.py` eine Schwelle
   vergleichst, gehört das ins Gate.
2. **Keine Importe von `picamera2` beim Start.** `dispread --help` muss auf
   einem Rechner ohne Kamera funktionieren. Die Registry macht das per Lazy
   Import vor — halte dich daran und importiere Kameramodule nicht auf
   Modulebene.

### Gerüst

`src/dispread/cli/__init__.py`:

```python
"""Kommandozeile. Duenne Schale um die Verarbeitungskette."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from dispread import __version__
from dispread.cli import inspect as inspect_cmd
from dispread.cli import profiles as profiles_cmd
from dispread.cli import run as run_cmd

_KOMMANDOS = (run_cmd, profiles_cmd, inspect_cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dispread", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="kommando", required=True)
    for modul in _KOMMANDOS:
        modul.add_parser(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.execute(args))
```

Jedes Kommandomodul registriert sich selbst und hängt seine Funktion an:

```python
def add_parser(sub) -> None:
    p = sub.add_parser("run", help="Kette laufen lassen")
    p.add_argument("--source", required=True, help="URI, z. B. folder:///pfad?rate=5")
    p.add_argument("--profile", required=True, help="Profil-ID aus config/profiles/")
    p.add_argument("--jsonl", type=Path, help="Audit-Log (Default: aus paths.VAR_LIB)")
    p.add_argument("--serial", help="Port, z. B. /dev/ttyAMA0")
    p.add_argument("--baudrate", type=int, default=115200)
    p.add_argument("--limit", type=int, help="nach n Frames beenden")
    p.add_argument("--confirm-frames", type=int, default=1)
    p.add_argument("--report", type=Path, help="Runartefakt als JSON")
    p.add_argument("--dry-run", action="store_true", help="nur zeigen, was passieren wuerde")
    p.set_defaults(execute=execute)
```

## Exit-Codes

Sie sind Teil der Schnittstelle — der systemd-Dienst und deine Testläufe
hängen daran:

| Code | Bedeutung |
| --- | --- |
| `0` | Lauf beendet, keine stille Fehlablesung, keine Sink-Fehler |
| `1` | Laufzeitproblem: Sink-Fehler, Quelle abgebrochen, stille Fehlablesung erkannt |
| `2` | Nutzungsfehler: unbekanntes Schema, Profil fehlt, ROI passt nicht zur Bildgröße |

`examples/16` macht es vor: der Lauf schlägt **nur** bei stillen
Fehlablesungen fehl, Ablehnungen sind kein Fehler. Übernimm diese Haltung.

## Das Runartefakt

Am Ende jedes Laufs eine JSON-Datei mit mindestens:

```python
{
  "dispread_version": __version__,
  "argv": sys.argv[1:],
  "started_at": ...,            # UTC, ISO-8601
  "source": source.describe(),
  "profile": profil.to_dict(),
  "timing_is_meaningful": bool,          # aus TimeBaseKind.carries_time_information
  "formatter": {"format_id": ..., "provisional": True},
  "counts": {"frames": ..., "by_status": {...}},
  "sinks": [{"type": ..., "sent": ..., "omitted": ..., "errors": ..., "last_error": ...}],
  "processing_latency": {...},           # aus PipelineTrace.stage_durations_us()
  "component_versions": pipeline.component_versions(),
}
```

Vier Felder darin sind nicht verhandelbar: `timing_is_meaningful`,
`formatter.provisional`, die Sink-Gesundheit und `by_status`. Ohne sie kann ein
Messbericht später zu einer Falschaussage werden — „Ausgabe funktioniert" ohne
den Hinweis, dass das Format provisorisch ist, oder Latenzen aus einer
synthetischen Quelle. `examples/16_end_to_end_headless.py` schreibt genau das
schon; nimm die Struktur von dort.

## Tests

Eine CLI ist gut testbar, wenn `main(argv)` einen Int zurückgibt statt
`sys.exit` zu rufen. `tests/test_cli.py`:

```python
from dispread.cli import main


def test_hilfe_geht_ohne_kamera(capsys) -> None:
    import pytest
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "run" in capsys.readouterr().out


def test_unbekanntes_schema_ist_nutzungsfehler(tmp_path) -> None:
    code = main(["run", "--source", "quatsch://x", "--profile", "testgeraet"])
    assert code == 2


def test_lauf_gegen_synthetische_quelle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DISPREAD_PROFILES", str(tmp_path / "profiles"))
    # Profil anlegen wie in tests/test_profiles.py, dann:
    code = main([
        "run", "--source", "synthetic://seven-seg?digits=5&decimals=2&unit=N&count=10",
        "--profile", "testgeraet", "--limit", "10",
        "--jsonl", str(tmp_path / "values.jsonl"), "--report", str(tmp_path / "report.json"),
    ])
    assert code == 0
    assert (tmp_path / "values.jsonl").read_text().count("\n") == 10
```

`paths.py` liest alle Verzeichnisse aus Umgebungsvariablen (`DISPREAD_PROFILES`,
`DISPREAD_VAR_LIB`, …) — genau dafür ist das da. **Kein Test schreibt in
`/var/lib/dispread`.**

## Einsprungpunkte erst am Ende

Wenn `python -m dispread.cli run …` funktioniert, in `pyproject.toml`:

```toml
[project.scripts]
dispread = "dispread.cli:main"
```

und danach **einmal neu installieren**, sonst existiert das Skript nicht:

```bash
./.venv/bin/pip install --no-deps -e .
./.venv/bin/dispread --version
```

Den Kommentar in `pyproject.toml`, der die Abwesenheit der Skripte begründet,
ersetzt du dabei durch die Angabe, welche Module es jetzt gibt.

## Fallen

* **`argparse` und Umlaute in Hilfetexten** sind unproblematisch, aber halte
  die Hilfetexte kurz; sie sind das erste, was ein Laborant liest.
* **Kein `sys.exit()` tief im Code.** Nur `main()` gibt einen Code zurück.
* **Kein `print` als Protokoll.** Für den Dienstbetrieb brauchst du `logging`
  (Kapitel 9). Menschliche Ausgabe auf stdout, Diagnose auf stderr.
* **`--dry-run` ehrlich halten.** Er soll Quelle, Profil, Senken und Zielpfade
  ausgeben und nichts schreiben — auch nicht das Runartefakt.
* **Kein `--force` für Profilprüfungen.** Ein Schalter, der die ROI-Prüfung
  übergeht, ist der kürzeste Weg zu einer stillen Fehlablesung.
* **Signale.** `SIGINT`/`SIGTERM` müssen die Senken schließen. `Pipeline.run()`
  hat dafür ein `finally` — lauf durch die Pipeline, nicht daran vorbei.

## Fertig, wenn

* [ ] `python -m dispread.cli run --source "synthetic://…" --profile …` läuft
      und schreibt `values.jsonl` plus Runartefakt
* [ ] `dispread profiles` listet, `dispread inspect values.jsonl` fasst zusammen
* [ ] `--help` funktioniert ohne Kamera und ohne UART
* [ ] Exit-Codes wie oben, mit Tests belegt
* [ ] Tests grün, `ruff` grün, `CHANGELOG.md` und ROADMAP aktualisiert
* [ ] `pyproject.toml`-Kommentar zu den Konsolenskripten korrigiert

Weiter mit [Kapitel 6 — Kamera, Aufnahme, `replay://`](06-kamera-aufnahme-replay.md).
