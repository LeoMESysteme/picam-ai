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
- Die TDMS ist äquidistant (Handbuch S. 73): `dt mode = tf`, Start und Ende der Aufnahme von Hand. Das Inkrement ergibt sich aus der Aufnahmespanne geteilt durch die Wertezahl: 744,14 s / 7 388 = 0,10072 s (`wf_increment` am Dateiende).
- Ausgelassene, ungültige Abschnitte fehlen daher ohne Zeitlücke. Die längste echte Lücke dauerte 6,9 s; 21 Lücken waren länger als 2 s.
- Der Pi hat im Mittel 13,3 Werte/s geschickt statt 10. Die Aufnahme dauerte 744 s, der Pi-Lauf 555 s. Innerhalb der Aufnahme verteilt GSVmulti die Werte gleichmäßig; Pausen, Häufungen und Ratenabweichungen verschwinden.
- Die Zeitachse von GSVmulti ist auf diesem Weg damit nicht für die zeitliche Zuordnung von Prüfling und Referenz verwendbar. Belastbar sind nur die Zeitstempel im Pi-Audit.

**Leser auf dem Pi** (16 427 Datensätze, Kamera ~30 Bilder/s):

| Anteil | Status / Grund |
| --- | --- |
| 51 % | VALID |
| 24 % | UNREADABLE `tracking_lost:rahmen_unstimmig` (1 152 kurze Schübe, über den ganzen Lauf verteilt, nicht an Wertwechsel gekoppelt) |
| 19 % | TRANSITION (`anzeige_wechselt`, `awaiting_confirmation`; ~1,4 Wertwechsel/s) |
| 6 % | UNREADABLE einzelne Zellen (`low_segment_margin`, `no_value`) |

Das Diagnosebild `diagnose/0002.png` (Frame 1332, `rahmen_unstimmig`) zeigt eine ruhige, scharfe Anzeige `+0.63956 mV/V`. Die Nachführung meldet hier offenbar einen Fehlalarm (OQ-63).

**Ursache der `rahmen_unstimmig`-Schübe (Nachstellung aller 222 Diagnosebilder, bitgenau):**
- Ein einzelner automatisch gewählter Rahmenbereich liegt auf einer schmalen **Glanzlinie der unteren linken Fase**
  (Mitte 515, 774). Nach einer leichten Lichtänderung kurz nach Laufbeginn bewegt er sich nicht mehr starr mit dem
  Gerät, sondern weicht 0,7 bis 2,6 px ab. Ab 0,65 px kippt er die Residualgrenze, über 1,5 px wird er als
  Ausreißer verworfen und das Bild besteht wieder. Daher die kurzen Schübe.
- **Nummerierung:** Im Diagnosebericht heißt er R5 (0-basiert). In der Werkbank (Lauf-HUD, Nachführungstabelle,
  Bereichsbearbeitung) ist es **Rahmenbereich 6**.
- Keine echte Bewegung, kein Sicherheitsproblem: Die Ablehnungen sind richtig im Sinne der Prüfung, es gehen nur
  Werte verloren. Die Laufzeitgrenzen 0,35/0,65/1,5 px bleiben unverändert (eine Lockerung ließe im Sicherheitstest
  falsche Geometrie bis 3,5 px durch).
- Abhilfe ohne Code: unter Laufbeleuchtung neu einrichten und den Bereich an dieser Stelle entfernen. Seit
  2026-11-11 meldet die Werkbank so einen Bereich selbst („Rahmenbereich 6 ist dauerhaft unstimmig …“) und findet
  ihn nach der Neueinrichtung über die Lage wieder (CHANGELOG, OQ-63).
- Bericht: `.superpowers/sdd/2026-11-06-bruecke-ui/tracking-fehlalarm-diagnose.md`.

**Weitere Beobachtungen:**
- Die Einrichtung stand auf „WARNUNG“ (bestätigt).
- Die Timing-Kalibrierung wurde nicht angewendet (`applied: false`).
- Der Demo-Empfangstest vor Lauf 1 zeigt erneut 599 von 600 `written`. Die App blieb sichtbar bei etwa 584 stehen.
