# Erneuter Fokusbefund und Kantenabbruch in neuer Aufstellung

[Originalarchiv](setup-focus-failure-2026-11-11-170836.zip),
[SHA-256](setup-focus-failure-2026-11-11-170836.sha256).
Sitzung `live-20261111T170836Z`, Betriebsstand `08ac9b9`.
Teil des [kritischen Workbench-Blockers](../WORKBENCH_BLOCKER.md),
[OQ-72](../open-questions.md#oq-72) und [OQ-74](../open-questions.md#oq-74).

## Beobachtung und tatsächlicher Abbruch

Nutzer beobachtet erneut, dass ein weniger scharfer Fokuspunkt verwendet
wird als zuvor sichtbar möglich. Einrichtung danach fehlgeschlagen.
Alle vier vorhandenen Setup-Originale gesichert: `still.png`,
`camera-settings.json`, `cell-text.json`, `failure.json`, außerdem kompletter
Status, Bedienermeldung, Herkunft/Hashes, eingefrorener Betriebsquellstand
mit Tests und Vorlagen. Keine neue Kameraaktion zur Sicherung.

Raster erster Versuch `ok`, Zellentext `+0.60994 ` aus serieller Quelle.
Abbruch: `Vorpruefung meldet FEHLER: kanten (Zellen 14, 15);
Stabilitaetsmessung nicht gestartet`. Anders als bei den beiden früheren
Kantenfällen betrifft dieser Befund die beiden letzten Leerzellen und
nicht Zahlzelle 7. Offline mit archiviertem Code reproduziert: Raster 155/155 Punkte.
Leerzelle 14 Stufe 11,0 (Fehlergrenze 8), Leerzelle 15 Stufe 7,0
(Warngrenze 6); das Gesamturteil ist FEHLER, die Meldung nennt beide.
Die Kantenprüfung nicht pauschal als Fokusfehler deuten.

Fokusziel und spätere Rückmeldung 56, Autofokus aus. Bestes protokolliertes
Schärfemaß 522,219448, Endprüfung 517,933823 gegenüber Schwelle 443,886531,
ROI `[640,360,640,360]`. Dies belegt die protokollierte Fokusprüfung,
nicht den optisch besten Fokus der LCD-Zeichen nach Kameraneustart.
Vorher-/Nachher-Fokusbilder und Rohstapel fehlen. Kein numerischer
Fokusrücksprung oder ursächlicher Zusammenhang bewiesen.

## Offline wiederholen

```bash
sha256sum -c docs/quellen/setup-focus-failure-2026-11-11-170836.sha256
./.venv/bin/python -m zipfile -e docs/quellen/setup-focus-failure-2026-11-11-170836.zip var/replay-focus
./.venv/bin/python var/replay-focus/setup-focus-failure-live-20261111T170836Z/replay.py
```

Rezept prüft Manifest, lädt den eingefrorenen Code und wiederholt Raster
und statische Vorprüfung am Original-PNG. Mit `--source /pfad/zum/checkout`
gegen späteren Fix vergleichen. Ein erfolgreicher Fit allein genügt nicht
als Abnahme. Prüfung ersetzt keine fehlende Fokus-Bildfolge oder zeitliche
Stabilitätsmessung. Sicherungszeit Host-Wanduhr UTC, Unsicherheit unbekannt;
keine Latenzaussage aus Datei-Mtime oder Sicherungszeit.

Weitere zufällige Aufstellungen sind für den Einstieg nicht erforderlich:
mehrere Fehlerbilder, drei bestätigte neue Setups und sechs ältere Kontrollen
liegen vor. Eine spätere zusätzliche Aufnahme gezielt für die noch fehlende
Fokus-Bildfolge instrumentieren; keine Vollständigkeitsgarantie daraus ableiten.
