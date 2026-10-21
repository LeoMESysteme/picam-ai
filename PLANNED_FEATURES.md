# Geplante Funktionen und Bedienablauf

Stand: 2026-10-21. Die aktive Arbeitsreihenfolge steht in [TODO.md](TODO.md),
der aktuelle Bau- und Prüfstand in [docs/status.md](docs/status.md).
Diese Liste beschreibt Produktziele; sie ist keine Freigabezusage.

## Bedienablauf und heutiger Stand

| Schritt | Stand |
| --- | --- |
| Oberfläche öffnen und Kamera auf die Anzeige richten | `dispread serve --port 8081`, geschützte Oberfläche `/live` mit Vorschau; Port 8080 ist auf diesem Pi durch MEhub belegt |
| Anzeige, Punktraster und Kameraregler einrichten | Einrichtungsassistent für GSV-2AS / Displaytech 161A gebaut; Prüfungen und Gegenlesen vor dem Lauf |
| Einrichtung prüfen und namentlich bestätigen | In `/live` gebaut; Bestätigung gilt für diese Einrichtung |
| Erkennung starten und Zustände sehen | Dot-Matrix-Leser, VALID / TRANSITION / UNREADABLE / STALE und JSONL-Audit pro Lauf gebaut; reale Grenzen siehe Status |
| Werte an GSVmulti übertragen | Offen: Telegrammspezifikation, Zeit- und Fehlerbehandlung fehlen ([OQ-07](docs/open-questions.md#oq-07)) |

Ein echter Messwertsprung bleibt erhalten. Unlesbare Eingaben werden abgelehnt;
es gibt keine automatische Korrektur, Mittelung oder Glättung von Messwerten
([Konzept §7](Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung)).
Modell-Konfidenz ist ohne Kalibriermessung keine Fehlerwahrscheinlichkeit.

## Weitere Produktziele

* **Einfachere Werkbank:** ROI- und OCR-Auswahl, sichtbare Bestätigung und
  verständliche Fehlermeldungen überarbeiten. Frühere Beobachtungen an der
  7-Segment-Seite sind Prüfaufträge, keine nachgewiesenen aktuellen Fehler
  von `/live`. Die Vorschau wird derzeit nur alle 0,5 s abgefragt.
* **Ansichten:** ein vergrößerter entzerrter Ausschnitt, bedienbare
  Bildrotation und ein Verlauf mit klar markierten ungültigen Abschnitten.
  Qualitätskennzahlen sollen ihre Bedeutung erklären; ein Farbwert darf
  keine ungemessene Genauigkeit suggerieren.
* **GSVmulti-Ausgabe:** Transport und Format erst nach verbindlicher
  Spezifikation festlegen. Das bestehende `AsciiCsvFormatter`-Format bleibt
  `provisional=True` und belegt keine GSVmulti-Kompatibilität.
* **Datensätze erweitern:** Auto-Labeling aus dem seriellen GSV-2AS-Strom,
  Timing-Kalibrierung, Ernte und Import sind gebaut. Der Displaybus-Abgriff
  ist eine nicht gebaute Rückfallebene
  ([Skizze](docs/DISPLAYBUS_TAP.md), [OQ-38](docs/open-questions.md#oq-38)).
  Mehr Bilder derselben Anzeige ersetzen keine Abdeckung von Geräten,
  Lichtbedingungen, Vorzeichen und Einheiten
  ([OQ-39](docs/open-questions.md#oq-39)).
* **Betrieb:** Dauerlauf, Audit-Aufbewahrung und Kamerawiederverbindung
  absichern; Leistung am Aufbau messen. Installationspaket und automatischer
  Dienst bleiben Ausbauziele. Der vorhandene Python-Einsprungpunkt heißt
  `dispread`; Node.js ist für die Workbench-Laufzeit nicht erforderlich.
