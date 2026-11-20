"""Timing-Kalibrierung der StreamCam: Aufnahme, Auswertung, Kalibrierdatei.

Die Messkette (Telegramm -> Anzeigeversatz delta und Schutzabstand M) war bis
2026-11-20 nur als Skripte im Entwicklungs-Checkout vorhanden
(`scripts/sync-record.py`, `scripts/display-offset.py`,
`scripts/timing-calibration.py`). Fuer die Inbetriebnahme neuer Pis
(`picam kalibrieren`) liegt sie jetzt hier; die Skripte sind duenne Huellen.

- `record`: Kamerabilder und GSV-Telegramme gemeinsam aufzeichnen, optional
  mit Normierungsspruengen ueber RS232.
- `offset`: photometrische Auswertung (delta, sigma, d_misch, M).
- `build`: Kalibrierdatei aus den Berichten bauen (`dispread.timing_calibration`).
- `schedule`: Faktorplan fuer die Normierungsspruenge.

Die Untermodule werden bewusst nicht hier importiert (`record`/`offset`
ziehen cv2 und numpy nach).
"""
