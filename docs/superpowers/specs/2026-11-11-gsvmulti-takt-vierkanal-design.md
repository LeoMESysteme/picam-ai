# GSVmulti: fester Takt mit Vierkanal-Telegramm (Design)

**Stand:** 2026-11-11 · F1–F5 von Leonhard entschieden (2026-11-11), freigegeben · Branch `feat/bruecke-ui`

**Grundlage:**
- Brückentest mit echten Werten: [Beleg](../../quellen/bruecke-testlauf-2026-11-11/README.md)
- GSVmulti-Versuche 1–3 und 2b: [Anleitung und Ergebnisse](../../../windows/bridge/GSVMULTI-VERSUCHE.md), Originale unter `docs/quellen/gsvmulti-versuche-2026-11-11/`
- Handbuch-Recherche: `.superpowers/sdd/2026-11-06-bruecke-ui/gsvmulti-fehlwerte-recherche.md`

**Bezug:** [OQ-06](../../open-questions.md#oq-06), [OQ-51](../../open-questions.md#oq-51), [Windows-Brücke §9/§11](2026-11-06-windows-bruecke-design.md).

## 1. Problem

GSVmulti speichert UserDefined-Werte äquidistant: Es zählt Zeilen und misst keine Zeit (Handbuch S. 73, belegt am 11.11.). Heute sendet der Pi nur gültige Werte, und zwar so oft sie entstehen (im Lauf 13,3/s). Daraus folgen drei Fehler:
1. Ungültige Abschnitte verschwinden ohne Lücke; die längste war 6,9 s.
2. Weicht die Rate ab, wird die Zeitachse gedehnt oder gestaucht.
3. Die Zuordnung zur Referenz über die GSVmulti-Zeitachse ist unbrauchbar.

GSVmulti selbst zu ändern ist ausgeschlossen, weil es ein zentrales Kundenprodukt ist.

## 2. Gemessene Bausteine (GSVmulti 2.01 Pro, 2026-11-11)

| Baustein | Beleg |
| --- | --- |
| UserDefined mit 4 Werten je Telegramm, `;`-getrennt, Filter an | Versuch 1c: 600/600, alle Kanäle identisch |
| Fester 10-Hz-Takt erhält einen ungültigen Abschnitt als markierte Zeilen | Versuch 2: 50 Zeilen genau an Zeile 100–149 |
| Zeitkanal mit Unix-Sekunden und 6 Nachkommastellen bleibt erhalten | Versuch 1c/2/2b: Abweichung ≤ 0,24 µs (float64) |
| Fehlwert `99999999.0` bleibt erhalten | Versuch 3 |
| `1E+300` wird still zu `1.0`; `NaN`/`Inf` verwerfen das Telegramm | Versuch 3, **verboten** |
| Ausgeblendete Kanäle werden nur mit „Record Hidden Channels“ aufgezeichnet, und diese Einstellung steht **nicht** in der `.ucf` | Versuch 2b |
| `.ucf`: `NumChan = 4`, `Separator = 315` (256 × Filter + ASCII `;`), `IsHidden` je Kanal | drei Sessions verglichen |

## 3. Entscheidung (vorgeschlagen)

### 3.1 Telegramm

```
%<wert>;<gültig>;<takt>;<zeit>\r\n
```

| Kanal | Feld | Inhalt |
| --- | --- | --- |
| 8_1 | `wert` | **Gültig:** der unveränderte Anzeigetext ohne Leerzellen, wie heute vom `UserDefinedFormatter` geprüft. Dezimal, **nie** Exponent. **Ungültig:** der letzte gültige Wert dieses Laufs, gehalten (Entscheidung Leonhard 2026-11-13, siehe 3.5); vor dem ersten gültigen Wert `99999999.0` |
| 8_2 | `gültig` | `1` bei gültigem Wert, `0` sonst |
| 8_3 | `takt` | Taktnummer ab Laufstart, beginnend bei 1, lückenlos auf Pi-Seite |
| 8_4 | `zeit` | Erfassungszeit des Bildes, aus dem der Wert stammt, in Unix-Sekunden mit 6 Nachkommastellen (siehe 3.4). Bei ungültigem Takt die Taktzeit |

Nur die Kanäle 8_2–8_4 werden in GSVmulti ausgeblendet; sichtbar bleibt der Messwert.

### 3.2 Takt auf dem Pi

- Der Takt entspricht der in GSVmulti eingestellten Frequenz, nicht fest 10 Hz. Er wird beim Laufstart angegeben, Vorgabe 10 Hz, erlaubt 1–10 Hz.
- Die Taktquelle ist der Pi selbst (Monotonuhr, fester Raster, **kein Aufholen**). Nur der Pi kann die Frische eines Werts gegen seine Kamerazeit prüfen.
- **Pro Takt genau ein Datensatz:**
  - Ein gültiger Wert, wenn der jüngste Datensatz VALID ist, aus einem noch nicht gesendeten Bild stammt und jünger als `max_frame_age_ms` ist. Ein Zwang, dass das Bild im eigenen Taktfenster aufgenommen wurde, entfällt: Die Auswertung dauert 50–90 ms, und in der Simulation des Laufs vom 11.11. kostete das Fenster 40 % statt 51 % gültige Takte. Der Zeitkanal trägt ohnehin die echte Erfassungszeit.
  - Sonst ein Fehlwert mit `gültig = 0`.
- **Kein gültiger Wert wird zweimal gesendet.** Liegt kein neuer gültiger Wert vor, folgt `gültig = 0`; den alten Wert erneut zu senden ist verboten.
  - Offene Frage F1: Die Anzeige wechselt nur etwa 1,4-mal pro Sekunde. Ein unveränderter, aber im neuen Takt neu gelesener Wert ist ein **neuer** gültiger Datensatz und keine Wiederholung. Entscheidend ist der Erfassungszeitpunkt, nicht der Zahlenwert.
- Die Invalidierungsbarriere ist im Takt bereits enthalten, weil jede ungültige Zeile explizit gesendet wird. Die bestehende Regel bleibt: Nach einem ungültigen Abschnitt gilt ein Wert erst als gültig, wenn er wieder bestätigt ist.

### 3.3 Weg zu GSVmulti

- **Neue Ausgabeart** `InvalidValuePolicy.MARK_RECORD` mit dem Format `gsvmulti_userdefined_4ch_v1`. Sie gilt für alle drei Wege: UART direkt (P4-3), UART über Brücke und Netzwerk über Brücke. Damit passt dieselbe Session-Vorlage überall.
  - Die bisherige Ausgabe (nur VALID, `OMIT_RECORD`, einkanalig) bleibt bis zur Abnahme wählbar, mit Warnung (F3). Vorgabe wird der Vierkanal-Takt, sobald er umgesetzt ist.
- **Formatierung** nur über den TelegramFormatter. Wie heute formatiert die Windows-Seite. Die Brücke überträgt dafür eine neue, kompakte Taktnachricht statt des vollen ValueRecord:
  - Felder: `run_id`, `takt`, `gültig`, `wert_text` (nur bei gültig), `zeit_ns`, `frame_sequence`.
  - Das sind etwa 150 Byte JSON statt etwa 1,2 kB. Der volle Datensatz bleibt im Pi-Audit.
  - Das ist eine additive Erweiterung von Protokoll v2, mit Review.
- **UART-Kapazität:** Die Baudrate kommt aus `src/dispread/bridge/baud.py` (`UART_BAUD = 460800`, Branch `feat/bruecke-ux`, Session picam-ai-65). Keine zweite Konstante.
  - Mit der Taktnachricht sind bei 460 800 Baud einschließlich Poll und Quittung etwa 3 kB/s für 10 Hz nötig. Das liegt weit unter der Kapazität von rund 46 kB/s.
  - Die GSVmulti-Seite bleibt bei 115 200 Baud: 4 Kanäle sind etwa 40 Byte, bei 10 Hz also etwa 400 B/s.
- **Verlorene Takte:**
  - Kommt auf Windows Takt *n+k* nach *n* an, schreibt die App für *n+1 … n+k−1* Fehlwertzeilen (`gültig = 0`, `zeit` = nominale Taktzeit, als solche markiert). Danach schreibt sie den empfangenen Takt.
  - Damit bleibt die Zeilenzahl richtig, und es wird nie ein alter Wert nachgereicht.
  - Obergrenze 50 Takte (5 s). Darüber wird die Ausgabe als gestört gemeldet, die Lücke nicht aufgefüllt, und das Journal hält es fest.
  - Offene Frage F2: Ist das Auffüllen gewünscht, oder soll eine Sequenzlücke stehen bleiben?
- **COM-Quittung:** wie heute. Sie belegt nur die Annahme durch den Treiber und ist kein Nachweis, dass GSVmulti den Wert empfangen hat.

### 3.4 Zeitkanal

- Der Pi rechnet die Erfassungszeit (`V4L2_MONOTONIC`, über `records.to_boottime_ns`) mit einem Versatz REALTIME−MONOTONIC in Unix-Zeit um. Den Versatz misst er beim Laufstart und hält ihn in `session.json` fest.
- **Aussage:** Der Kanal zeigt die Erfassungszeit auf der Pi-Uhr. Er belegt keine Synchronität mit der Windows-Uhr.
  - Ob der Pi per NTP synchron ist, wird beim Start geprüft und protokolliert (`timedatectl`); die gemessene Unsicherheit steht in `session.json`.
  - Die Semantik des V4L2-Zeitstempels bleibt offen (OQ-43); der Kanal ist entsprechend `provisional` dokumentiert.
- Die Zuordnung zur Referenz in GSVmulti läuft über diesen Kanal. Die GSVmulti-Zeitachse lag in Versuch 2 bis 0,8 s daneben.

### 3.5 GSVmulti-Einrichtung (App, Werkbank, Wiki)

- **Session-Vorlage:** Die EXE (Session picam-ai-65, Vorlagenkatalog) liefert die Vierkanal-Vorlage mit 8_2–8_4 ausgeblendet. Umgeschaltet wird, sobald Pi und Brücke dieses Format senden.
- **Pflichtschritt in App und Wiki:** Configure Recording → Advanced → **„Record Hidden Channels“**. Diese Einstellung steht nicht in der Session.
- **Empfehlung:** Für 8_1 Autoscale Y aus und Min/Max fest einstellen, damit der Fehlwert vor dem ersten gültigen Wert die Skala nicht sprengt.

### 3.5 Gehaltener Wert in 8_1 (Nachtrag 2026-11-13)

- **Anlass:** Zwei echte Läufe am 13.11. (GSVmulti 2.01 und 2.03 Pro) hatten 20 bzw. 24 % ungültige Takte, meist einzeln. Mit `99999999.0` in 8_1 sprang die Zahlenanzeige von GSVmulti bei jedem Lesefehler an den Bereichsrand und war nicht ablesbar.
- **Entscheidung (Leonhard, 2026-11-13):** Bei ungültigem Takt trägt 8_1 den letzten gültigen Wert desselben Laufs. Die Markierung trägt allein 8_2 (`gültig = 0`). Vor dem ersten gültigen Wert gibt es nichts zu halten, dann steht `99999999.0`. Ein neuer Lauf beginnt ohne gehaltenen Wert. Auch die Windows-Füllzeilen (F2) halten den Wert vor der Lücke.
- **Auswertung:** Nur Zeilen mit `gültig = 1` sind Messwerte. Ein gehaltener Wert ist nie eine Messung. Wer 8_1 ohne 8_2 auswertet, verwendet veraltete Werte; deshalb bleibt „Record Hidden Channels“ Pflicht.
- **Ausnahme zu** [GSVMULTI_PROTOCOL.md](../../GSVMULTI_PROTOCOL.md) (gehaltener Wert kein zulässiger Ersatz): Sie gilt nur für dieses Vierkanal-Format, weil die Markierung in derselben Zeile in 8_2 steht.
- **Zeitkanal:** 8_4 trägt bei gültigem Takt die Erfassungszeit des Bildes, bei ungültigem die Taktzeit (3.1). An Wechseln gültig/ungültig kann die Zeit deshalb um bis zu `max_frame_age_ms` rückwärts springen (13.11.: −5 ms bei Takt 223). Für eine Zeitachse die Taktnummer 8_3 verwenden, 8_4 nur für die Zuordnung gültiger Werte.
- **Werkbank, Laufstart:** Takt (Hz) angeben. Hinweis „In GSVmulti dieselbe Frequenz einstellen“.

## 4. Was nicht geändert wird

- ValueRecord, Pi-Audit (`records.jsonl`), Freigaberegeln und Testfreigabe (Bestätigung pro Lauf, „nicht abgenommen“) bleiben unverändert.
- Weiterhin gilt: keine Glättung, keine Referenzkorrektur, kein historisches Nachsenden von Werten.
- Ein Testlauf (`test_run`) erzeugt weiterhin keine externe Ausgabe.

## 5. Nachweise vor der Abnahme

1. **Linux-E2E** (pty und TLS, wie R1): 10 Hz über 10 min mit synthetischer Quelle und eingestreuten ungültigen Phasen.
   - Zeilenzahl = Taktzahl.
   - Sequenz lückenlos bzw. korrekt aufgefüllt.
   - Gültige Werte nur aus frischen Bildern.
   - Kein Wert doppelt.
2. **UART über Brücke mit 460 800 Baud** auf echter Hardware (USB-TTL): 10 Hz über 10 min, keine Lücke.
3. **Echter Lauf** in GSVmulti mit Vorlage und „Record Hidden Channels“.
   - Die TDMS-Zeilen entsprechen den Pi-Takten 1:1.
   - Die Zeitkanäle stimmen mit dem Pi-Audit überein.
4. **Versuch mit `1/f0`** statt `tf` (optional): Ist die GSVmulti-Achse dann genau?

## 6. Entscheidungen (Leonhard, 2026-11-11)

- **F1, ja:** Ein gleicher Zahlenwert aus einem neuen Bild zählt als neuer gültiger Takt. Entscheidend ist der Erfassungszeitpunkt.
- **F2, ja:** Verlorene Takte füllt die Windows-App mit Fehlwertzeilen auf, höchstens 50 Takte (5 s).
- **F3, ja, mit Warnung:** Die alte Einkanal-Ausgabe bleibt bis zur Abnahme wählbar. Werkbank (Laufstart und Lauf) und App zeigen dann deutlich: „Einkanal-Ausgabe: Bei Übergang (TRANSITION) und unlesbarer Anzeige (UNREADABLE) werden keine Zeilen gesendet. GSVmulti zeichnet die Lücken nicht auf; Laufzeit und Zeitachse der Aufnahme sind deshalb nicht genau.“
- **F4: 10 Hz ist Obergrenze und Vorgabe.** Mehr Takt brächte kaum Information, aber mehr Fehlwertzeilen (bei 20 Hz nur 1–2 Bilder je Takt) und Zeitnot in der Brücke (Quittung p99 49 ms). Höher erst, wenn die Bildwiederholrate der Anzeige gemessen ist und der Leser deutlich mehr gültige Bilder liefert.
- **F5, eigene Belege reichen:** Das Fehlwert-Format `99999999.0` wird nicht mit der GSVmulti-Entwicklung abgestimmt.
