# 0 — Werkzeuge und Arbeitsrhythmus

**Ziel:** Du kannst Tests, Linter und Beispiele starten, weißt, warum die venv
so eigenartig aufgesetzt ist, und kennst den Rhythmus, in dem hier gearbeitet
wird.

**Vorbedingungen:** keine.

## Die vier Befehle

```bash
./.venv/bin/pytest -q                                    # alles ohne Hardware
./.venv/bin/ruff check src tests examples                # Stil und Importordnung
./.venv/bin/python examples/16_end_to_end_headless.py    # ganze Kette, kein Gerät
./scripts/camera-commissioning.sh                        # Kamera-Diagnose, Exit 0 = gut
```

Immer mit `./.venv/bin/…`. Nie `python3` ohne Pfad, nie `pip install` ohne die
Flags unten — sonst schießt du die ABI ab (nächster Abschnitt).

Erwartete Ausgabe heute: `36 passed`, `All checks passed!`, und beim Beispiel
`korrekt: 40`, `STILL FALSCH: 0`.

## Warum die venv so aussieht

```bash
python3 -m venv --system-site-packages .venv     # Systempakete sichtbar lassen
./.venv/bin/pip install --no-deps -e .           # nur dieses Paket, keine Deps
./.venv/bin/pip install pytest ruff              # Werkzeuge dürfen aus PyPI
```

`numpy`, `cv2`, `pyserial`, `picamera2` und `libcamera` kommen als
Debian-Systempakete. Ein `pip install numpy` legt eine zweite Kopie in
`.venv/lib/` — die überschattet die Systemkopie, und das gegen System-`numpy`
gebaute `cv2` bricht mit einem ABI-Fehler, der wie ein Absturz im C-Code
aussieht. Deshalb ist `dependencies = []` in `pyproject.toml` Absicht; die
Begründung steht dort im Kommentar und in [../dependencies.md](../dependencies.md).

Prüfen, dass alles aus dem System kommt:

```bash
./.venv/bin/python -c "import numpy, cv2, serial; print(numpy.__file__); print(cv2.__file__)"
# erwartet: Pfade unter /usr/lib/python3/dist-packages/, NICHT unter .venv/
```

### Falle: Repo verschieben oder umbenennen zerstört die venv

Eine venv speichert absolute Pfade — in den Shebangs von `.venv/bin/*`, in
`pyvenv.cfg` und in der `.pth`-Datei des editierbaren Installs. Nach einem
Umbenennen des Projektverzeichnisses sieht das so aus:

```
./.venv/bin/pytest: cannot execute: required file not found
ModuleNotFoundError: No module named 'dispread'
```

Das ist **kein** Fehler im Code. Zwei Wege zurück:

```bash
# a) Pfade ersetzen (schnell)
grep -rl ALTER_PFAD .venv/bin/* .venv/pyvenv.cfg .venv/lib/python3.13/site-packages/*.pth \
  | xargs sed -i "s#ALTER_PFAD#$PWD#g"

# b) neu aufsetzen (sauber, braucht Netz für pytest/ruff)
rm -rf .venv && python3 -m venv --system-site-packages .venv \
  && ./.venv/bin/pip install --no-deps -e . && ./.venv/bin/pip install pytest ruff
```

Genau das war am 2026-09-08 der Fall, nachdem das Repo von
`picam_number-ingestion` nach `picam-ai` umbenannt worden war. Dabei lagen auch
noch zwei Konsolenskripte (`dispread-doctor`, `dispread-replay`) in
`.venv/bin/` herum, deren Module es nie gab — entfernt. Wenn du in
[Kapitel 5](05-cli.md) Einsprungpunkte anlegst, entstehen sie neu, und zwar
erst nach einem erneuten `pip install --no-deps -e .`.

## Tests: mock und real

```bash
./.venv/bin/pytest -q                 # mock (Default): ohne Hardware
./.venv/bin/pytest -q --mode=real     # zusätzlich @hardware und @serial
```

`tests/conftest.py` überspringt im Mock-Modus alles, was mit
`@pytest.mark.hardware` oder `@pytest.mark.serial` markiert ist. **Jeder neue
Test gehört standardmäßig in den Mock-Pfad.** Nur wenn er ohne Kamera oder
UART physikalisch nicht laufen kann, wird er markiert:

```python
import pytest

@pytest.mark.hardware
def test_kamera_liefert_sensorzeitstempel() -> None:
    ...
```

Nützliche Schalter beim Entwickeln:

```bash
./.venv/bin/pytest -q -k folder            # nur passende Testnamen
./.venv/bin/pytest -x -q                   # beim ersten Fehler anhalten
./.venv/bin/pytest --lf -q                 # nur die letzten Fehlschläge
./.venv/bin/pytest -q -s                   # print() durchlassen
./.venv/bin/pytest tests/test_sevenseg.py::test_liest_negativen_wert -q
```

## Stil, den `ruff` erzwingt

Konfiguration in `pyproject.toml`: `line-length = 120`, Regeln `E,F,W,I,UP,B`.
`I` sortiert Importe, `UP` verlangt moderne Syntax (`int | None` statt
`Optional[int]`), `B` findet typische Fallen (etwa veränderliche Defaults).

Hauskonventionen, die kein Linter prüft, an die sich aber jede Datei hält —
schau dir `src/dispread/rectify.py` als kurzes Beispiel an:

* `from __future__ import annotations` als erster Import.
* Modul-Docstring erklärt **warum**, nicht was; mit Verweis auf `Konzept.md §n`
  oder ein `OQ-nn`, wenn eine Entscheidung dahintersteht.
* Datenklassen, die Ergebnisse tragen: `@dataclass(frozen=True, slots=True)`.
  Ergebnisse sind Beweismittel und werden nicht nachträglich verändert.
  Konfigurationen (`GateConfig`, `PipelineConfig`) sind veränderlich.
* Öffentliche Namen im Modul über `__all__` benennen.
* Kommentare auf Deutsch, ohne Umlaute im Code (`src/` schreibt „Aufnahmezeit"
  als `Aufnahmezeit`, aber Docstrings dort verwenden bewusst `ae/oe/ue` —
  bleib beim Stil der Datei, die du anfasst). In `docs/` sind Umlaute normal.
* Typannotationen überall, auch bei `-> None`.

## Der Rhythmus

Jede Aufgabe in dieser Anleitung läuft in derselben Schleife:

1. **Vertrag lesen.** Welches `Protocol` ist zu erfüllen?
   [Kapitel 2](02-vertraege.md) hat alle auf einer Seite.
2. **Test zuerst schreiben.** Er ist die Spezifikation. Er muss rot sein, bevor
   du anfängst — ein Test, der ohne Implementierung grün ist, prüft nichts.
3. **Gerüst anlegen**, Signaturen und Docstring, Rumpf `raise NotImplementedError`.
4. **Kleinsten Schritt implementieren**, bis ein Test grün wird. Nicht mehr.
5. `./.venv/bin/pytest -q` **und** `./.venv/bin/ruff check src tests examples`.
6. **Doku-Pflicht** erfüllen: `CHANGELOG.md`, ggf. `OQ-nn`, ROADMAP-Häkchen.
7. **Commit** in einem Schritt mit der Doku.

Warum so streng mit Schritt 2: die gefährlichen Fehler dieses Projekts sind
still. Ein falsch gelesener Wert, der als `VALID` durchgeht, sieht in keiner
Konsolenausgabe verdächtig aus. Der Test muss deshalb nicht „läuft durch"
prüfen, sondern **„lehnt das Unlesbare ab"**.

## Commit-Nachrichten

Deutsch, Imperativ oder Nominalstil, erste Zeile ≤ 72 Zeichen. Im Rumpf die
drei Fragen, die auch der CHANGELOG stellt:

```
folder://-Bildquelle implementiert

Problem:     Fuenf der sechs URI-Schemata scheiterten mit ImportError, damit
             war kein reales Bildmaterial durch die Kette zu schicken.
Aenderung:   FolderSource liest ein Verzeichnis in natuerlicher Sortierung,
             Zeitbasis FILE_MTIME (traegt keine Zeitaussage).
Konsequenz:  Aufgenommene PNG-Saetze sind ab jetzt regressionsfaehig.
```

## Wenn etwas nicht geht

* **Traceback von unten nach oben lesen.** Die letzte Zeile nennt den Typ, die
  Zeile darüber deine Datei.
* `ValueError: status=… ohne reject_reasons` ist **kein** Bug, sondern die
  Invariante aus `records.py`: ein nicht freigegebener Wert muss einen Grund
  nennen. Nenne einen.
* `ModuleNotFoundError: No module named 'dispread.frames.folder_source'` heißt:
  Registry-Eintrag existiert, Implementierung nicht. Genau das baust du in
  [Kapitel 3](03-erste-bildquelle-folder.md).
* Kamera weg? `Picamera2.global_camera_info() == []` und
  `RuntimeError: IMX500: Requested camera dev-node not found` sind erwartete
  Zustände ohne Kamera. `camera_auto_detect` greift **nur beim Booten** — nach
  dem Anstecken ist ein Reboot nötig.
* Sonst: [../CAMERA_COMMISSIONING.md](../CAMERA_COMMISSIONING.md) hat einen
  Fehlerbaum, und [../../CLAUDE.md](../../CLAUDE.md) einen Abschnitt
  „Erwartete Zustände, die keine Bugs sind".

**Fertig, wenn** die vier Befehle oben bei dir grün laufen und du weißt, warum
`pip install numpy` in diesem Projekt ein Fehler wäre.

Weiter mit [Kapitel 1 — Die Kette verstehen](01-kette-verstehen.md).
