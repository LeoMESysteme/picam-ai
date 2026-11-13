# Spec-Entwurf: Prüfsumme mit Wiederholung für „UART über Brücke“

**Status:** Entwurf vom 2026-11-13 (Claude, autonomer Plan Punkt 5). Nicht umgesetzt,
Entscheidung durch Leonhard. Umsetzung wäre Backend (Pi und Windows-App) und damit ein
Codex-Handoff.

**Anlass:** Windows-Prüfung UX2 am 13.11. Der Empfangstest über UART brach zweimal ab
(3/600 und 124/600), die App meldete `uart_frame_invalid`. Läufe über denselben Weg blieben
lückenlos, verbanden aber bis zu fünfmal in 4,5 min neu. Der Kernelzähler von `ttyAMA0`
zeigt `fe:232` (Rahmenfehler), keinen Überlauf. Belege:
[UX2-Bericht](../../quellen/ux2-pruefung-2026-11-13/ux2-bericht.md),
[Ausgabewege-Vergleich](../../quellen/ausgabewege-vergleich-2026-11-13.md).

## 1. Befund im Code

Heute laufen über UART dieselben Brückennachrichten wie über TCP: kompakte JSON-Zeilen mit
`\n` (`encode_v2`, `V2LineReader` in `src/dispread/bridge/protocol.py`), 460 800 Baud
(`dispread.bridge.baud.UART_BAUD`). TCP schützt die Daten durch TLS, UART durch nichts.

1. **Erkannt wird nur kaputtes JSON.** Eine Zeile, die nach einem Bitfehler kein gültiges
   JSON oder kein gültiges v2-Objekt mehr ist, wirft `ValueError`.
   - Auf dem Pi setzt `UartListener._worker` daraufhin die ganze Sitzung zurück:
     Anmeldung, Lease, Bindung.
   - In der App wird daraus `uart_frame_invalid`, und die Verbindung baut neu auf.
   - Ein einzelnes gekipptes Bit kostet so eine komplette Neuverbindung. Das erklärt die
     Abbrüche im Empfangstest.
2. **Nicht erkannt wird ein Bitfehler, der gültiges JSON übrig lässt.** Beispiel: eine Ziffer
   im Wertfeld eines Takts (`"1.2345"` → `"1.2355"`), in der Taktnummer oder in einem Ergebnis
   der Quittung. Dann schreibt die App einen **falschen Wert als gültig** an GSVmulti. Das
   verletzt die Grundregel „Unlesbares ablehnen statt raten“ (`AGENTS.md`). Wie oft das
   vorkommt, ist nicht gemessen. Bei `fe:232` auf rund 3,8 Mio. empfangenen Zeichen ist es
   aber nicht auszuschließen.
3. **Ein Paket mit mehreren Zeilen geht ganz verloren.** Wirft `V2LineReader.feed` bei der
   ersten defekten Zeile, verwirft es auch die gültigen Zeilen danach.

Punkt 2 ist der eigentliche Grund für diese Spec, nicht die Neuverbindungen. **Bis zur
Umsetzung sollte „UART über Brücke“ nicht für Messungen verwendet werden**; Netzwerk oder
UART direkt (115 200 Baud, bisher fehlerfrei) sind die Alternativen. Das gehört als Hinweis
in Werkbank und App, sobald Leonhard zustimmt.

## 2. Ziel

- Jede über UART empfangene Zeile ist entweder unverändert oder wird verworfen. Ein gekipptes
  Bit wird praktisch immer erkannt (CRC-32: alle Ein- bis Dreibitfehler und alle Fehlerbündel
  bis 32 Bit).
- Eine verworfene Zeile kostet eine Wiederholung, nicht die Sitzung.
- Eine Quittung wird nie doppelt angewendet, und ein Wert wird nie doppelt geschrieben.
- Alte Gegenstellen funktionieren weiter: Pi und App mit und ohne Prüfsumme lassen sich in
  jeder Kombination koppeln. Wer keine Prüfsumme kann, bekommt keine.

Nicht Ziel: UART direkt. Dort liest GSVmulti das feste Telegramm `%wert;gültig;takt;zeit`;
eine Prüfsumme würde das Format ändern (kein Erfinden von Protokollen, OQ-07).

## 3. Rahmenformat

```text
<kompaktes JSON>\t<CRC-32 als 8 Hex-Ziffern, klein>\n
```

- CRC-32 wie `zlib.crc32` (IEEE 802.3) über die UTF-8-Bytes des JSON-Teils. Die Funktion
  steht auf beiden Seiten in der Standardbibliothek; es kommt keine Abhängigkeit hinzu.
- Als Trenner dient der Tabulator: `json.dumps` maskiert Steuerzeichen, im kompakten JSON
  kommt kein rohes `\t` vor. Eine Zeile mit genau einem `\t` und acht Hex-Ziffern davor
  `\n` ist gerahmt, jede andere ist eine alte, ungerahmte Zeile.
- Je Nachricht kommen 9 Bytes hinzu, bei einem Takt etwa 5 %.

Verworfen wurden folgende Alternativen:

- Binärrahmen mit COBS: robuster bei Bytes, die ausfallen, aber nicht mehr mit bloßem Auge
  lesbar und ein größerer Umbau.
- CRC-16: zu schwach für Zeilen bis 64 KiB.
- HMAC: Die Sitzung ist schon durch Kopplung und Signatur geschützt. Es geht um
  Leitungsfehler, nicht um Angreifer.

## 4. Aushandlung

- Der Pi kündigt die Fähigkeit im Kopplungsprofil an, als neues optionales Feld
  `uart_framing: "crc32"`. Das folgt demselben Muster wie `uart_baud`: Fehlt das Feld, gilt
  der alte Stand (`parse_profile` ergänzt den Standard).
- Die App rahmt ihre Anfragen nur, wenn das Profil `crc32` meldet.
- Der Pi erkennt jede Zeile einzeln, gerahmt oder ungerahmt, und antwortet im Format der
  Anfrage. Ein alter Pi bekommt nie eine gerahmte Zeile, eine alte App nie eine gerahmte
  Antwort.
- Der Wechsel innerhalb einer Sitzung ist verboten. Die erste Anfrage nach `uart_challenge`
  legt das Format fest, eine abweichende Zeile gilt als defekt.

## 5. Fehlerbehandlung und Wiederholung

Das Protokoll ist Anfrage/Antwort: Die App fragt, der Pi antwortet mit derselben
`request_id`.

**Auf dem Pi** (`UartListener`):

- **Defekte gerahmte Zeile** (falsche CRC, Format kaputt, kein gültiges JSON): Die Zeile wird
  still verworfen. Es gibt keine Antwort und **keinen** Sitzungsreset; der Zähler
  `uart_crc_errors` steigt.
- **Gültige Zeile, aber die Nachricht wird abgelehnt** (Anmeldung, Lease): Das bleibt wie
  heute, also Reset.
- **Wiederholungsspeicher:** Der Pi merkt sich die letzten 8 Antworten als
  (`request_id` → fertige Bytes). Kommt eine Anfrage mit bekannter `request_id` und
  gleichem Inhalt noch einmal, sendet er die gespeicherten Bytes erneut, ohne
  `hub.exchange` aufzurufen. So wird eine Quittung (`ack`, `tick_ack`) nie doppelt
  angewendet. Bei gleicher `request_id` mit anderem Inhalt wird die Anfrage abgelehnt
  (Reset), wie heute bei Identitätsfehlern.
- `V2LineReader.feed` verarbeitet die übrigen Zeilen eines Pakets weiter, wenn eine Zeile
  defekt ist. Das gilt auch ohne Rahmen.

**In der App** (`SerialTransport`, `connection._exchange`):

- **Defekte gerahmte Antwort:** Die Antwort wird verworfen, und die **unveränderte** Anfrage
  (gleiche `request_id`, gleiche Bytes) geht erneut hinaus. Dasselbe gilt, wenn bis zur
  Antwortfrist keine Antwort kommt.
- **Antwortfrist:** 150 ms je Versuch, höchstens 3 Versuche. Bei 10 Hz und kurzen Zeilen
  dauert ein Umlauf deutlich unter 10 ms; der Wert ist bei der Umsetzung aus den Logs zu
  begründen.
- **Danach** greift der heutige Weg: `uart_timeout` bzw. `uart_frame_invalid`, dann
  Neuverbindung.
- **Zähler:** `crc_errors`, `retransmits` und `retransmit_recovered` gehen ins
  Diagnoseprotokoll (`details.jsonl`, Freigabeliste) und in die Statuszeile des Wegs.

**Warum das für Werte sicher ist:**

- Ein Takt wird nur geschrieben, wenn seine Zeile die CRC besteht.
- Geht die Antwort mit einem Takt verloren, holt die Wiederholung genau dieselbe Antwort.
- Bleiben alle Versuche erfolglos, fehlt der Takt. Die App füllt ihn wie heute als ungültig
  auf (höchstens `TICK_WINDOW` = 50). Ein falscher oder doppelter Wert entsteht nicht.

## 6. Diagnose am Pi

`bridge status` und die Werkbank zeigen je UART-Sitzung:

- empfangene Zeilen
- verworfene Zeilen mit CRC-Fehler
- wiederholt beantwortete Anfragen

Damit lässt sich die Leitungsqualität ohne `sudo cat /proc/tty/driver/ttyAMA` beurteilen.
Den Kernelzähler `fe` zusätzlich zu lesen, wäre schön, braucht aber Root und bleibt optional.

## 7. Tests

- **Einheit:**
  - Rahmen bauen und prüfen
  - jede einzelne Bitposition einer Beispielzeile kippen: immer verworfen
  - ungerahmte Zeilen bleiben gültig
  - Mischbetrieb in einer Sitzung wird abgelehnt
- **Fehlerinjektion:** Transport-Attrappe, die mit fester Saat Bits kippt, Bytes verwirft und
  Zeilen verdoppelt. Ein Empfangstest mit 600 Werten und einer Bitfehlerrate von 1e-4 muss
  vollständig ankommen:
  - jeder Wert genau einmal
  - kein Sitzungsreset
  - Zähler stimmen
- **Kompatibilität:** alle vier Kombinationen alt/neu von Pi und App
  (`test_bridge_end_to_end`, `windows/bridge/tests`).
- **Am Aufbau:** Empfangstest 600/600 und ein Lauf von mindestens 30 min über UART bei
  460 800 Baud. CRC-Fehler und Wiederholungen werden gezählt und mit `fe` vorher und nachher
  verglichen.

## 8. Ergänzend zu prüfen (unabhängig von der Prüfsumme)

- **Gegentest mit 115 200 Baud über die Brücke:** Die Rate ist heute fest. Für den Test die
  Profilrate einmal herabsetzen. Verschwinden die Rahmenfehler, liegt es an Rate oder Pegel,
  nicht an der App.
- **Leitung:** Kabellänge, Masse und der Pegelwandler zwischen Pi-GPIO und RS-232 (OQ-09).
  `fe` deutet auf Signalqualität oder Taktabweichung hin, nicht auf Überlauf.
- **RTS/CTS-Flusssteuerung:** Sie hilft nicht gegen Rahmenfehler. Sie ist nur nötig, falls
  später Überläufe auftreten.

## 9. Offene Fragen an Leonhard

1. Soll „UART über Brücke“ bis zur Umsetzung in Werkbank und App als „nicht für Messungen“
   markiert werden (Punkt 1.2)?
2. Prüfsumme umsetzen, Rate senken oder beides? Empfehlung: zuerst der Gegentest mit
   115 200 Baud (eine Stunde Aufwand), dann die Prüfsumme in jedem Fall, weil sie den stillen
   Wertfehler ausschließt.
