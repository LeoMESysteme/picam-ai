# Brückentest mit echten Werten (Testfreigabe, 2026-11-11)

**Aufbau:**
- Testbuild der Windows-App (`build-test.ps1`, Stand `feat/bruecke-ui` 2579cb8) auf Leonhards Windows-11-PC.
- Weg „Netzwerk über Brücke“ mit Testfreigabe („nicht abgenommen, keine Messfreigabe“).
- Portpaar com0com: COM7 auf der Brückenseite, COM8 auf der GSVmulti-Seite.
- GSVmulti: UserDef auf COM8, 10 Hz.
- Pi-Dienst `dispread-werkbank-bruecke`, Kamera StreamCam am GSV-2AS (Displaytech 161A), Raumlicht.

Die Dateien hier sind Originale von Leonhard:

| Datei | Inhalt |
| --- | --- |
| `zweiter-lauf_workbench-network.tdms` (+ `_index`) | GSVmulti-Aufnahme des zweiten Laufs, Kanal „Chan. 8_1“ in mV/V |
| `dispread-diagnose.zip` | Diagnoseexport der App nach dem zweiten Lauf; der ganze Tag, Secrets redigiert, die Suche nach Token-, Angebots- und Passwortfeldern war leer |
| `diagnose-summary.json` | die `summary.json` aus dem ZIP, ausgepackt |
| `tdms_werte.py` | Minimalleser für die TDMS-Rohwerte (float64, ein Kanal), mit dem der Vergleich unten gemacht wurde |

**Pi-Protokolle** (zu groß für das Repo, liegen auf dem Pi):
- Lauf 1: `var/live/live-20261111T095426Z/run-01`
- Lauf 2: `var/live/live-20261111T103604Z/run-01` (`output.jsonl`, `records.jsonl`, `session.json`, `diagnose/` mit 223 Bildern)

## Lauf 1 (89 s): Verbindungsabbruch bei jedem Übergang

**Befund:**
- 1 560 Werte wurden an COM übergeben.
- Etwa alle 2–15 s brach die Verbindung für rund 2 s ab, insgesamt 14-mal.
- Jedes Mal geschah das beim ersten Übergangswert nach gültigen Werten: `offered` und `unconfirmed` stehen in derselben Millisekunde.

**Ursache:** `protocol._record` verlangte `frames_confirmed >= 1`. Unlesbare Datensätze der echten Kette tragen dort aber 0. Behoben in 2579cb8; siehe CHANGELOG.

## Lauf 2 (555 s): Übertragung vollständig, Lücken aus Leser und GSVmulti

**Übertragung:**
- 14 661 Angebote, 0 Abbrüche, 0 `unconfirmed`.
- Quittung Pi→Windows→Pi: p50 15 ms, p95 28 ms, p99 49 ms, Maximum 0,8 s.

**Vollständigkeit:**
- Die TDMS enthält genau **7 389** Werte. Das sind exakt die 7 389 vom Pi als `written` quittierten VALID-Werte, in derselben Reihenfolge und ohne einen einzigen abweichenden Wert.
- Auf dem Weg Pi → App → COM → GSVmulti ging nichts verloren, und nichts kam doppelt an.

**Zeitachse in GSVmulti** (Beitrag zu OQ-51):
- Die TDMS trägt `wf_increment = 0,1 s`, also einen festen Abstand je empfangenem Wert.
- Ausgelassene, ungültige Abschnitte fehlen daher ohne Zeitlücke. Die längste echte Lücke dauerte 6,9 s; 21 Lücken waren länger als 2 s.
- Der Pi hat im Mittel 13,3 Werte/s geschickt statt 10. GSVmulti rechnet 7 389 × 0,1 s = 739 s, der Lauf dauerte aber 555 s.
- Die Zeitachse von GSVmulti ist auf diesem Weg damit nicht für die zeitliche Zuordnung von Prüfling und Referenz verwendbar. Belastbar sind nur die Zeitstempel im Pi-Audit.

**Leser auf dem Pi** (16 427 Datensätze, Kamera ~30 Bilder/s):

| Anteil | Status / Grund |
| --- | --- |
| 51 % | VALID |
| 24 % | UNREADABLE `tracking_lost:rahmen_unstimmig` (1 152 kurze Schübe, über den ganzen Lauf verteilt, nicht an Wertwechsel gekoppelt) |
| 19 % | TRANSITION (`anzeige_wechselt`, `awaiting_confirmation`; ~1,4 Wertwechsel/s) |
| 6 % | UNREADABLE einzelne Zellen (`low_segment_margin`, `no_value`) |

Das Diagnosebild `diagnose/0002.png` (Frame 1332, `rahmen_unstimmig`) zeigt eine ruhige, scharfe Anzeige `+0.63956 mV/V`. Die Nachführung meldet hier offenbar einen Fehlalarm (OQ-63).

**Weitere Beobachtungen:**
- Die Einrichtung stand auf „WARNUNG“ (bestätigt).
- Die Timing-Kalibrierung wurde nicht angewendet (`applied: false`).
- Der Demo-Empfangstest vor Lauf 1 zeigt erneut 599 von 600 `written`. Die App blieb sichtbar bei etwa 584 stehen.
