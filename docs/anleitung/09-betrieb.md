# 9 — Betrieb: Installation, Dienst, Dauerlauf

**Ziel:** Die Kette läuft als systemd-Dienst, überlebt Neustarts und
Störungen, und ein 72-Stunden-Dauerlauf belegt: **kein unmarkierter Altwert,
stabiler Speicher.** Dazu ein Doku-Konsistenztest, der die Projektdokumentation
prüft.

**Warum jetzt:** Das ist P6 („Robustheit und Dauerbetrieb"). Und es ist der
Punkt, an dem sich zeigt, ob die Invarianten wirklich Invarianten sind —
72 Stunden finden Zustände, die kein Unit-Test trifft.

**Vorbedingungen:** [Kapitel 5](05-cli.md) (`dispread run` läuft),
[Kapitel 6](06-kamera-aufnahme-replay.md).

## Teil A — `install.sh`

Eigenschaften, die nicht verhandelbar sind:

* **Idempotent.** Zweimal laufen lassen ändert nichts und bricht nichts.
* **Kein `pip install` für Systembibliotheken.** venv mit
  `--system-site-packages`, Paket mit `--no-deps` — die Regel aus
  [../dependencies.md](../dependencies.md) gilt auch im Installer.
* **Nur lesend prüfen, bevor geschrieben wird.** Erst Voraussetzungen
  (Python-Version, Systempakete, Kamera, Port), dann anlegen.
* **Verzeichnisse aus `paths.py`, nicht aus dem Skript.** `/etc/dispread`
  (Konfiguration), `/var/lib/dispread` (Sessions, Wertelogs),
  `/run/dispread` (Heartbeat) — und alles per Umgebungsvariable
  überschreibbar, damit Tests niemals in die echten Pfade schreiben.

**Und:** Die MEhub-Regel „nicht direkt nach `/opt` schreiben, erst nach `$HOME`
hochladen, dann `sudo install`" gilt hier **nicht**. Dieses Repo liegt im Home
und wird direkt bearbeitet ([../../AGENTS.md](../../AGENTS.md)).

## Teil B — systemd-Unit

`systemd/dispread.service` (im Repo versioniert, vom Installer verlinkt):

```ini
[Unit]
Description=Optische Displayauslesung (dispread)
After=multi-user.target

[Service]
Type=simple
ExecStart=/home/me-systeme/picam-ai/.venv/bin/python -m dispread.cli run \
          --source picamera2://?size=2028x1520 --profile %i
Restart=on-failure
RestartSec=5
StateDirectory=dispread
RuntimeDirectory=dispread
# Speicherdeckel: ein Leck soll den Pi nicht mitnehmen.
MemoryMax=1G
# Watchdog erst aktivieren, wenn der Dienst tatsaechlich sd_notify sendet.
# WatchdogSec=30

[Install]
WantedBy=multi-user.target
```

Fragen, die du beim Schreiben beantworten musst — und im Commit begründest:

* **Neustart nach Absturz: was passiert mit dem letzten Wert?** Nach einem
  Neustart gibt es keinen aktuellen Wert. Der erste Datensatz darf also nicht
  der letzte gespeicherte sein. `ReleaseGate` startet ohne Historie — halte das
  so, und teste es.
* **Wer schließt die Senken?** `SIGTERM` muss durch `Pipeline.run()`s
  `finally` laufen, sonst fehlt die letzte JSONL-Zeile.
* **Heartbeat.** Eine Datei unter `paths.RUN` mit Zeitstempel und
  `frames`-Zähler, die ein Monitor lesen kann. Ohne Heartbeat sieht ein
  hängender Dienst wie ein ruhiges Labor aus.
* **Logging.** `logging` nach stdout, systemd sammelt es. Keine eigene
  Logrotation für das Dienstprotokoll — aber die des JSONL-Logs ist eingebaut
  (`JsonlSink(max_bytes=…, keep=…)`).

## Teil C — udev-Regel für den seriellen Port

Datenport ist **`/dev/ttyAMA0`**. `/dev/serial0` zeigt auf `ttyAMA10` und ist
der 3-Pin-Debug-Header — nicht der Nutzdatenport. Wenn ein USB-Adapter
dazukommt, gib ihm einen stabilen Namen:

```
# udev/99-dispread-serial.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="dispread-out"
```

Elektrisch offen ([OQ-09](../open-questions.md)): Pi-GPIO-Pegel dürfen
**nicht** direkt an RS-232. Es braucht einen Transceiver, und die galvanische
Trennung ist zu bewerten. Bis dahin läuft die Strecke gegen ein pty
(`os.openpty()` oder `socat`), und der Nachweis M7 ist ausdrücklich nur
„gegen pty geprüft, nicht elektrisch".

## Teil D — 72-Stunden-Dauerlauf

Exit-Kriterium von P6. Vorher festlegen, was gemessen wird — hinterher ist es
kein Nachweis mehr:

| Größe | Wie | Zielwert |
| --- | --- | --- |
| `stale_unmarked` | jede JSONL-Zeile mit `status == "valid"` prüfen, deren `capture_timestamp` älter als `stale_after_ns` ist | **0** |
| Speicher | RSS des Dienstes minütlich protokollieren | kein Trend über 72 h |
| Plattenverbrauch | Größe von `/var/lib/dispread` | begrenzt, Rotation greift |
| Lücken | `frame_sequence` auf Sprünge prüfen; `dropped_frames` im Trace | erklärbar, nicht still |
| Sink-Fehler | `health().errors` über die Zeit | 0, oder erklärt |
| Neustarts | `systemctl show -p NRestarts` | 0, oder erklärt |

Provozierte Störungen, jede einzeln und protokolliert:

1. Kabel der Gegenstelle ziehen ⇒ Sink-Fehler gezählt, Messbetrieb läuft weiter.
2. Licht ausschalten ⇒ `low_contrast`, danach `STALE`. **Kein** letzter Wert.
3. Anzeige abdecken ⇒ `display_not_located` bzw. `display_lost`.
4. Gerät ins Menü schalten ⇒ `state:menu`, kein Zahlenwert.
5. Überlauf erzeugen ⇒ `state:overflow`.
6. Dienst mit `SIGKILL` beenden ⇒ Neustart ohne Wertehistorie.
7. Platte vollschreiben (in einer Kopie des Zielverzeichnisses!) ⇒ JSONL-Fehler
   gezählt, nicht stillschweigend verloren.

Auswertung mit `dispread inspect` ([Kapitel 5](05-cli.md)); Zahlen nach
[../VALIDATION.md](../VALIDATION.md), Aufbau und Deutung nach
[../lab_journal.md](../lab_journal.md).

## Teil E — Der Doku-Konsistenztest

Steht als offener P0-Punkt in der ROADMAP und ist eine gute kleine Übung:
`tests/test_docs.py`, reines Python, keine Hardware.

```python
"""Konsistenz der Projektdokumentation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dispread import paths

DOCS = paths.ROOT / "docs"


def _md_dateien() -> list[Path]:
    return sorted([*DOCS.rglob("*.md"), paths.ROOT / "CLAUDE.md",
                   paths.ROOT / "AGENTS.md", paths.ROOT / "CHANGELOG.md"])


def test_oq_nummern_sind_lueckenlos() -> None:
    text = (DOCS / "open-questions.md").read_text(encoding="utf-8")
    nummern = sorted(int(n) for n in re.findall(r"^## OQ-(\d+)", text, re.M))
    assert nummern == list(range(1, len(nummern) + 1))


def test_verwiesene_oq_existieren() -> None:
    vorhanden = set(re.findall(r"^## OQ-(\d+)", (DOCS / "open-questions.md").read_text("utf-8"), re.M))
    for datei in _md_dateien():
        for nummer in re.findall(r"OQ-(\d+)", datei.read_text("utf-8")):
            assert nummer in vorhanden, f"{datei.name} verweist auf OQ-{nummer}"


@pytest.mark.parametrize("datei", _md_dateien(), ids=lambda p: p.name)
def test_keine_toten_verweise(datei: Path) -> None:
    for ziel in re.findall(r"\]\(([^)#][^)]*)\)", datei.read_text("utf-8")):
        if ziel.startswith(("http", "mailto:")):
            continue
        pfad = (datei.parent / ziel.split("#")[0]).resolve()
        assert pfad.exists(), f"{datei.name} -> {ziel}"


def test_status_nennt_ein_datum() -> None:
    kopf = (DOCS / "status.md").read_text("utf-8").splitlines()[0]
    assert re.search(r"\d{4}-\d{2}-\d{2}", kopf)
```

Erweiterungen, wenn du Lust hast: geklärte OQ-Einträge müssen ein Datum und
einen Zielort nennen; `CHANGELOG.md` muss die aktuelle `VERSION` enthalten;
`docs/anleitung/README.md` muss jede Datei in `docs/anleitung/` verlinken.

## Fallen

* **`sudo` verlangt seit dem Reboot ein Passwort** ([OQ-15](../open-questions.md)).
  Alles, was `sudo` braucht, sammle in **einem** Block und lass es von einem
  Menschen ausführen, statt es über die Session zu verteilen.
* **Absolute Pfade in der Unit.** Zeigen sie auf ein umbenanntes Repo, startet
  der Dienst nicht — dieselbe Falle wie bei der venv
  ([Kapitel 0](00-werkzeuge.md)).
* **`MemoryMax` ohne Messung** ist geraten. Erst RSS beobachten, dann Deckel
  setzen — aber setze einen.
* **Watchdog ohne `sd_notify`** killt den Dienst im Takt. Erst senden, dann
  aktivieren.
* **34 GB frei.** Ein Dauerlauf mit Diagnosebildern füllt das schneller als
  erwartet. Ringpuffer mit harter Obergrenze, und den Verbrauch im Lauf
  beobachten.
* **Kein `Restart=always` mit stiller Wiederaufnahme des letzten Werts.**
  Neustart heißt: keine Historie.

## Fertig, wenn

* [ ] `install.sh` läuft zweimal hintereinander fehlerfrei
* [ ] Dienst startet, überlebt Reboot, schließt Senken bei `SIGTERM`
* [ ] Heartbeat vorhanden und von außen lesbar
* [ ] 72-h-Lauf protokolliert: `stale_unmarked = 0`, Speicher stabil,
      alle sieben Störungen provoziert und dokumentiert
* [ ] `tests/test_docs.py` grün und im Mock-Pfad
* [ ] `CHANGELOG.md`, `docs/ROADMAP.md` (P6), `docs/HARDWARE_PROFILE.md`
      (Konfigwirkung), `docs/status.md`

Danach ist P7 (Abnahme) organisatorisch, nicht mehr programmatisch: Kriterien
vorab festlegen, auf den **gesperrten** Geräten einmalig auswerten.
