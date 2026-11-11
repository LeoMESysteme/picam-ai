# Erfolgreiche Workbench-Aufstellungen als positive Regression

[Referenzarchiv](workbench-positive-regression-2026-11-11.zip),
[SHA-256](workbench-positive-regression-2026-11-11.sha256).
Gegenstücke zu den [Fehlerfällen](setup-failures-2026-11-11.md) und verbindliche
Kontrollen für die [Blocker-Korrektur](../WORKBENCH_BLOCKER.md).

## Aktuelle positive Fälle

| Sitzung | Zustand bei Sicherung | Gesamturteil | Wesentliche Prüfungen |
| --- | --- | --- | --- |
| `live-20261111T164508Z` | bestätigt, später Lauf ordentlich beendet | WARNUNG wegen Raster-Bias, ausdrücklich bestätigt | Kanten, Rasterversatz, Gegenlesen, Nachführung OK; 20 automatische Bereiche |
| `live-20261111T165234Z` | bestätigt; kurzer Lauf war Bedien-Umweg | WARNUNG wegen Displayfehlerprüfung, ausdrücklich bestätigt | Raster, Kanten, Rasterversatz, Gegenlesen, Nachführung OK |
| `live-20261111T165754Z` | bestätigt, kein Lauf bei Sicherung | WARNUNG wegen Raster-Bias, ausdrücklich bestätigt | Kanten, Rasterversatz, Gegenlesen, Nachführung OK |

Jeweils vollständige vorhandene Setup-Dateien, Original-PNGs, Profile und
Bestätigungen gesichert. WARNUNG ist hier ein bestätigter Zustand und darf
nicht still als vollständig fehlerfreie Prüfung dargestellt werden.

## Erfolgreicher Lauf `164508Z/run-01`

Originale `records.jsonl`, `reference.jsonl`, `tx.jsonl` und `session.json`
vollständig erhalten. Aus den Auditzeilen erneut gezählt:

* 3.843 verarbeitete Datensätze: 2.920 VALID, 757 TRANSITION, 166 UNREADABLE,
  kein STALE. **VALID-Anteil 75,9823 %**, das vom Nutzer benannte Minimum
  von 75 % auf diesem Nenner erreicht. 26 zusätzliche übersprungene Bilder
  sind im Laufbericht ausgewiesen; Quote nicht als Anteil aller Sensorbilder
  ohne diesen Nennerzusatz ausgeben.
* Host-Wanduhrspanne 129,940458 s zwischen `started_at_utc` und
  `ended_at_utc` desselben Hosts, Unsicherheit unbekannt. Keine Latenzmessung.
* 0 Trackingverluste, 0 Auditfehler, kein gemeldeter Kamerafehler,
  Ende `bediener`, kein Testlauf, keine angepasste Lesetoleranz.
* Referenzvergleich laut Status: 0 Abweichungen unter 556 eindeutig
  vergleichbaren VALID-Datensätzen, 2.352 unentschieden und 12 ungedeckt.
  Nicht als 0 Fehler unter allen 2.920 gültigen Werten ausgeben.
* UART direkt: 2.920 gesendet, 923 ausgelassen, 0 Ausgabefehler,
  Format provisional, explizite Testbestätigung, Abnahme fehlt. Das ist
  kein Empfangsnachweis für Windows-EXE oder GSVmulti.

Timing-Kalibrierung war aufgezeichnet, `applied=false`. Aufnahmestempel
tragen `v4l2_monotonic`, Ergebnisstempel `host_monotonic`, Unsicherheiten
unbekannt. Daraus keine physische Framealter-/Sensorlatenzaussage ableiten.
Diagnosebilder während des Laufs waren deaktiviert; deshalb keine
nachträgliche Bild-für-Bild-Leserwiederholung des kompletten Laufs möglich.

## Kurzer Start-/Stopp-Lauf `165234Z/run-01`: Bedien-Umweg

Alle drei vorhandenen Laufdateien (`records.jsonl`, `reference.jsonl`,
`session.json`) bleiben gesichert: 28 UNREADABLE, 0 VALID, 28 Trackingverluste,
Grund `zu_wenig_rahmenmerkmale`; 5 weitere Bilder übersprungen.
Keine Auditfehler, kein Kameralesefehler, Ende durch Bediener.
Host-Wanduhr UTC: 16:57:49,654299 bis 16:57:51,425515, Unsicherheit unbekannt.

**Nutzerklärung 2026-11-11:** Der Lauf wurde nur gestartet und abgebrochen,
weil nach bestätigter Einrichtung ein Knopf für erneutes Einrichten fehlt.
So konnte der Nutzer für die neue Aufstellung erst wieder einrichten.
Diesen absichtlichen Umweg nicht als eigenständigen Trackingfehler am
ursprünglich eingerichteten Aufbau oder als negativen Regressionsfall
verwenden. [OQ-76 geklärt](../open-questions.md#oq-76),
[OQ-71 erweitert](../open-questions.md#oq-71): Neu einrichten muss auch
nach erfolgreicher Bestätigung direkt erreichbar sein.

## Sechs historische Kontrollaufstellungen

`sc3`, `sc4`, `sc5`, `ab1`, `ab2`, `sc6`: Original-PNG aus dem früheren
Entwicklungsdatenbestand plus bestätigtes Quad/Profil und verfügbare
Aufnahmemetadaten. 18 Originaldateien zusätzlich aus
`/mnt/ssd/picam-dev/diagnostics/` kopiert. Keine neuen unabhängigen
Abnahmedaten; als Regression gegen bereits funktionierende Geometrie nutzen.

Die tatsächlichen ursprünglichen Tests
`test_real_still_matches_confirmed_quad` bestehen auf diesen sechs Bildern.
Der relevante Quellstand `08ac9b9` sowie Vorlagen sind im Archiv enthalten.

## Offline prüfen

```bash
sha256sum -c docs/quellen/workbench-positive-regression-2026-11-11.sha256
./.venv/bin/python -m zipfile -e docs/quellen/workbench-positive-regression-2026-11-11.zip var/replay-positive
./.venv/bin/python var/replay-positive/workbench-positive-regression-20261111/replay.py --historical-controls
```

Rezept prüft Audit-Zählung, alle drei aktuellen Raster, die tatsächliche
nachfolgende Quad-Verfeinerung mit unabhängigem zweitem Standbild,
Gegenlesen und räumliche Bereichsverteilung/Reserve. Die Endquads stimmen
auf dem archivierten Quellstand mit den gespeicherten Vorschlägen überein.
Danach laufen sechs ursprüngliche Geometrie-Regressionstests. Eine
anfängliche Hilfsprüfung verglich fälschlich den groben Startfit mit dem
bereits verfeinerten Endquad; das Rezept wiederholt jetzt dieselbe echte
Verfeinerungsstufe wie die Einrichtung, statt die Toleranz zu lockern.

Mit `--source /pfad/zum/checkout` gegen einen späteren Fix prüfen. Originale
mit Manifest, Quellstand und tatsächlich ausgeführter Ausgabe gesichert.
Stabilitäts-Einzelbilder fehlen wie bei den Fehlerfällen; räumliche
Verteilungsprüfung ist keine neue zeitliche Stabilitätsprüfung. Erst nach
positiven und negativen Regressionen einen Fix als softwareseitig geprüft
ausweisen; echte Hardware-/Windows-Abnahme getrennt halten.
