# P4: Serielle Ausgabe an GSVmulti (UserDefined) — Prototyp

Stand 2026-10-29, Planung in der autonomen Phase (Leonhard bis Freitag weg).
Grundlage: [GSVMULTI_PROTOCOL.md](../../GSVMULTI_PROTOCOL.md) (UserDefined
belegt, ME v2.6 S. 118–121), [OQ-06](../../open-questions.md#oq-06),
[OQ-07](../../open-questions.md#oq-07), [OQ-47](../../open-questions.md#oq-47).
Zweig `feat/r13-display-haertung` (baut auf dem R13-Live-Pfad auf).

**Ziel:** Ein vorläufiger, ausdrücklich nicht freigegebener Transportpfad,
mit dem Leonhard am Windows-PC die Abnahmeschritte 1–3 aus
GSVMULTI_PROTOCOL.md („Abnahme und nächste Schritte“) durchführen kann.
**Keine Messfreigabe**: Ungültig-/STALE-Wirkung in GSVmulti (OQ-06) und die
Zeitachse (M8) sind ungeklärt.

## Entwurfsentscheidungen (vorläufig, von Leonhard zu bestätigen)

| Punkt | Vorläufige Wahl | Begründung / Alternative |
| --- | --- | --- |
| Frame | `%<zahl>\r\n`, ein Wert | Belegtes Profil, ein DUT-Wert = ein Kanal; keine Referenz im Frame |
| Zahlentext | **Anzeigetext unverändert**, nur innere Leerzellen entfernt (`+ 1.7643` → `+1.7643`) | Keine Rundung/Umformatierung; Auflösung = Anzeige. Nicht-Dezimaltext → kein Frame, Fehler im Beleg |
| Ungültige Werte | `omit_record` (kein Frame, `TxReceipt.omitted=True` im Audit) | Einzige Policy ohne erfundene Semantik; Wirkung in GSVmulti (Altwert?) ist OQ-06 und wird markiert. Alternative: zweiter Zahlenkanal Gültigkeit — Leonhard entscheidet |
| Baudrate | 115200 8N1, kein Handshake | Testvorschlag der Doku; konfigurierbar |
| Port | Konfiguration, **kein Default** | `/dev/ttyAMA0` braucht Pegel/Trennung (OQ-09); `/dev/ttyUSB0` ist der Referenzeingang und wird abgelehnt; `/dev/serial0` ist Debug |
| Live-Integration | **Opt-in** je Lauf, Standard aus | Kein Einfluss auf Leser/Gate; JSONL-Audit bleibt maßgeblich |
| Was gesendet wird | nur `ValueRecord` mit Status VALID **nach** allen Sperren (Testlauf R13-17, Umkonfiguration R13-21) | Konzept §7/§8; keine Altwertwiederholung, kein Aufholburst |

## Aufgaben

### P4-1 Formatter `userdefined` (Codex)
**Stand 2026-10-28: gebaut, ungeprüft am Windows-PC.** Lokale Formatter-
und SerialSink-Prüfungen mit pty/Fakes; weiterhin Prototyp, nicht freigegeben.

* `src/dispread/sink/protocol/userdefined.py`: `UserDefinedFormatter`
  (`TelegramFormatter`), `capabilities`: Formatkennung `gsvmulti_userdefined_v0`,
  `provisional=True`, 1 Kanal, keine Gerätekommandos,
  `carries_capture_timestamp=False`, `timestamp_resolution_ns=None`,
  Invalid-Policy nur `omit_record`. Präfix konfigurierbar (Standard `%`,
  nur druckbares ASCII ohne Ziffer/Vorzeichen/Punkt), CRLF fest.
* Zahl aus `ValueRecord.raw_text`: Leerzeichen entfernen, Regex
  `^[+-]?[0-9]+(\.[0-9]+)?$`, sonst `None` mit Grund; Konsistenz mit
  `record.value` prüfen (Abweichung → kein Frame).
* `gsv_ascii.py` bleibt der werfende Platzhalter (nicht anfassen).
* Tests: Bytes exakt, Vorzeichen/Null/Leerzelle, Nicht-VALID → `None`,
  inkonsistenter Text → `None`, Präfixprüfung; pty-Test über `SerialSink`.

### P4-2 Demo-Sender für den Windows-Test (Codex)
**Stand 2026-10-28: gebaut, ungeprüft am Windows-PC.** Profile, JSONL,
Portablehnung und Schreibstau lokal mit pty/Fakes geprüft;
[Windows-Anleitung](../../GSVMULTI_PROTOCOL.md#windows-test). P4-3 ist seit 2026-10-30 ebenfalls gebaut, ungeprüft am Windows-PC.

* `scripts/gsvmulti-demo-sender.py`: sendet Demo-Werte (Konstanten,
  Treppe, Vorzeichen/Null/Bereichsgrenzen) mit dem Formatter aus P4-1 an
  einen Port/pty, Rate (Standard 10 Hz) und Anzahl (Standard 600),
  schreibt jeden Frame (Bytes hex, Sendezeit BOOTTIME, Folgenummer) nach
  JSONL zum Vergleich mit dem GSVmulti-Export. Lehnt `/dev/ttyUSB0`
  (Referenz) und `/dev/serial0` (Debug) ab, außer mit ausdrücklichem
  Schalter. Keine Live-Kamera.
* Kurzanleitung für Leonhard (Wiki/Doku): GSVmulti DEFINE-Einstellungen,
  Verkabelung je Transportweg (3,3-V-USB-UART), Ablauf 600 Frames,
  Vergleich.

### P4-3 Opt-in-Ausgabe im Live-Lauf (Codex, nach Review von P4-1/2)
**Stand 2026-10-30: gebaut, ungeprüft am Windows-PC.** pty/Fakes prüfen
Freigabesicherungen, exakte Bytes, Portprüfung, Stau, Fehler und Legacy-Bytes.
Reviewkorrektur: ein offener Senderauftrag; angefangene Telegramme vollständig
bis CRLF mit 1 s Gesamtfrist schreiben. Kein Pufferverwerfen und kein Aufholen;
neue Frames bei Beschäftigung verwerfen. Schreib-/Timeout-/Threadfehler
sperren den Ausgang, lösen den Beschäftigt-Zustand und erscheinen mit Beleg
in Tx/Status/Session. Ausgabeport öffnet vor Referenzrecorder/Werteplan;
Öffnungsfehler startet weder Plan noch Rückstellung.
Live mindestens 9600 Baud: konservativ 16 Anzeigebytes + Präfix + CRLF =
19 Byte × 10 Bit / 9600 = 19,79 ms < 33 ms; 4800 braucht 39,58 ms und wird
wie 2400 abgelehnt. Längere Telegramme werden vor dem Write mit Fehler gesperrt.
Portschutz prüft Aliasse, den aktiven Referenzport und sysfs-USB-ID `067b:2303`
(PL2303). `allow_reference_adapter: true` ist eine ausdrückliche Ausnahme für
den Adapter, nie für den aktiven Referenz-/Werteplan- oder Debugport.
Die Demo nutzt dieselbe vollständige Schreibfunktion: Stau verwirft nur den
nächsten Frame, ein Schreibfehler beendet den Lauf. Tx-Auslassungsbelege
bleiben im Bildpfad; ihre Verlagerung brauchte eine weitere Audit-Warteschlange.
Keine Hardware-Abnahme oder Messfreigabe. [Code-Naht und API](../../GSVMULTI_PROTOCOL.md#opt-in-im-live-lauf-p4-3).

* `LiveService.start_run(..., output=None)` bzw. API-Parameter: Port,
  Baudrate, Präfix, `allow_reference_adapter` (Standard aus). `LiveSession` hängt nach Audit einen `SerialSink` mit
  `UserDefinedFormatter` an; nur freigegebene VALID-Records; TxReceipts nach
  `tx.jsonl`; `session.json` enthält Formatter-Fähigkeiten (`provisional`)
  und Portdaten; Ausgabefehler beenden den Lauf nicht, sind aber im Status
  sichtbar. Ohne `output` bytegleich.
* Keine UI-Änderung in diesem Schritt (Gestaltung später, Impeccable).

## Nicht in diesem Plan
Messfreigabe, Zeitachse/M8, Ungültigsemantik in GSVmulti, Windows-Bridge
aus dem ZIP (hat belegte Fehler), TCP/VCOM, UI.
