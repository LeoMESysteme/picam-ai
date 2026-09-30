# 3 — Erste eigene Bildquelle: `folder://`

Dieses Kapitel ist eine Bauaufgabe: Die URI-Registry kennt `folder://`, aber
`dispread.frames.folder_source` ist im aktuellen Stand nicht vorhanden.
`open_source("folder:///tmp")` schlägt deshalb derzeit mit
`ModuleNotFoundError` fehl. Zum Vergleich: [Kapitel 6](06-kamera-aufnahme-replay.md)
beschreibt `replay://` für aufgezeichnete Sessions; die aktive Kameraquelle ist
`v4l2://` für UVC-Geräte wie die StreamCam.

## Vertrag und Grenzen

Eine Implementierung muss das [FrameSource-Protokoll](02-vertraege.md)
erfüllen. Lies dort zuerst, was `open()`, `frames()`, `close()` und
`describe()` bedeuten. Die Registry in `src/dispread/frames/__init__.py`
übergibt Verzeichnis, `glob` (Standard `*.png`) und `rate` (Standard 10 Hz).

Für die neue Quelle gelten diese Grenzen:

* Dateizeit ist `FILE_MTIME`, keine Aufnahmezeit. Daraus darf keine Latenz
  abgeleitet werden; die Unsicherheit bleibt `None`.
* `rate` steuert höchstens die Wiedergabegeschwindigkeit, nicht die
  ursprüngliche Aufnahmerate.
* Ein leeres Verzeichnis und unlesbare Bilder müssen in `describe()` sichtbar
  sein. Ein fehlendes Verzeichnis muss klar fehlschlagen.
* Dateien sollten natürlich sortiert werden (`frame2` vor `frame10`), damit
  eine Bildserie in ihrer erwartbaren Reihenfolge läuft.

## Vorgehen

Lege zuerst `tests/test_folder_source.py` an. Decke mindestens das Protokoll,
natürliche Sortierung, lückenlose Sequenznummern, leere und fehlende Ordner,
unlesbare Dateien sowie die Zeitbasis ab. Implementiere danach
`src/dispread/frames/folder_source.py` in kleinen Schritten. Das Registry-
Gerüst existiert bereits; passe es nur an, falls ein Test einen echten Fehler
darin belegt.

Ein minimaler manueller Einstieg nach der Implementierung:

```python
from dispread.frames import open_source

source = open_source("folder:///absoluter/pfad/zu/bildern?rate=0&glob=*.png")
source.open()
try:
    for frame in source.frames():
        print(frame.frame_sequence, frame.image.shape)
finally:
    source.close()
```

`rate=0` ist hier der gewünschte schnelle Durchlauf. Das Beispiel ist erst
ausführbar, wenn die fehlende `FolderSource`-Implementierung gebaut wurde.
Arbeite mit [Kapitel 0](00-werkzeuge.md) (venv, Tests und Doku-Pflichten) und
prüfe anschließend die gesamte Kette aus [Kapitel 1](01-kette-verstehen.md).

## Fertig

Die Quelle erfüllt das Protokoll, die genannten Grenzfälle sind getestet und
`describe()` kennzeichnet `FILE_MTIME` als nicht zeittragend. Ergänze bei einer
Codeänderung den obersten Abschnitt in `CHANGELOG.md` und aktualisiere den
belegten Roadmap-Stand.
