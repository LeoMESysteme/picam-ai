# GSVmulti-Anbindung

## Stand: das Format ist unbekannt

Die Telegrammspezifikation der eingesetzten GSVmulti-Version liegt **nicht**
vor. Ein Mensch muss sie intern beschaffen ([OQ-07](open-questions.md)).

**Präzisierung 2026-09-22.** Die frühere Aussage „`me-systeme.de` blockt
automatische Abrufe mit HTTP 403" galt pauschal und ist so falsch: **PDFs unter
`/produkte/.../anleitungen/` sind abrufbar (HTTP 200)**, nur die
HTML-Produktseiten antworten mit 403. Beschafft und lokal abgelegt sind
seither:

* `var/datenblaetter/gsv2-bedienungsanleitung.pdf` — Bedienungsanleitung
  GSV-2 (GSV-2LS/-2AS/-2FSD) mit dem vollständigen **RS232-Protokoll des
  Messverstärkers**: 38400 Baud 8N1 ab Werk, permanentes Senden, Binär- und
  ASCII-Format, Befehlssatz. Ausgewertet in
  [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) und
  [OQ-38](open-questions.md).
* `var/datenblaetter/ba-gsvmulti.pdf` — GSVmulti-Bedienungsanleitung, Stand
  13.08.2011, 10 Seiten. **Enthält keine Telegrammspezifikation**, sondern die
  Bedienung der Oberfläche. Gesucht ist ausserdem v2.6.

**`var/` ist gitignored** — beide PDFs liegen nur lokal und überleben keinen
frischen Clone. Dauerhaft sind allein die Quell-URLs; wer sie erneut braucht,
lädt sie unter denselben Pfaden wieder herunter.

Damit ist geklärt, *warum* die Spezifikation fehlt: sie steht nicht in den
öffentlichen Anleitungen, nicht dass sie unerreichbar wäre. **An der
Kernaussage dieses Dokuments ändert das nichts** — das Format, das GSVmulti
akzeptiert, ist weiterhin unbekannt. Dass es mit dem ASCII-Format des GSV-2
zusammenfällt, ist plausibel und **nicht belegt**.

**Es wird nichts geraten.** `sink/protocol/gsv_ascii.py` wirft absichtlich
`NotImplementedError`. Ein geratenes Format wäre schädlicher als keines: es
würde in Tests grün erscheinen, in Messberichten als „Ausgabe funktioniert"
auftauchen und erst am Laborplatz auffallen.

## Was vorher geklärt sein muss (Konzept §8)

| Punkt | Stand |
| --- | --- |
| konkrete GSVmulti-Version und unterstützte Geräteanbindung | offen |
| Beispieltelegramm oder verbindliche Protokollspezifikation | offen |
| Baudrate, Zeichenformat, Trennzeichen, Zeilenende | offen |
| Dezimaltrennzeichen, Vorzeichen, Einheit, Kanalzahl | offen |
| Geräteidentifikation und Initialisierungskommandos | offen |
| Behandlung von Aufnahmezeit, ungültigen und veralteten Werten | offen ([OQ-06](open-questions.md)) |
| Streaming-, Abfrage- und Wiederverbindungsverhalten | offen |

Konzept §8 weist zusätzlich darauf hin, dass die Herstellerinformation zu
ASCII-Betriebsarten von GSV-2/GSV-3 noch **keine** Unterstützung beliebiger
CSV-Datenströme belegt. Drei Schnittstellenfälle sind zu unterscheiden:
CSV-Dateiimport, ASCII-Streaming und Emulation eines GSV-Geräts. Falls
erforderlich, muss der Adapter auch Gerätekommandos beantworten.

## Der beste Weg zur Antwort ist ein Mitschnitt

Belastbarer als die Dokumentation: ein vorhandenes GSV-2 oder GSV-3 im
ASCII-Modus an GSVmulti hängen und den realen Datenstrom aufzeichnen. Das
liefert das tatsächliche Telegramm statt einer Beschreibung davon — und
gleichzeitig das Verhalten bei Verbindungsabbruch und Wiederaufbau.

## Die wichtigste Einzelfrage: M8

**Verwendet GSVmulti einen übermittelten Aufnahmezeitstempel, oder ordnet es
nur Empfangszeiten zu?**

Versuch: Datenstrom mit absichtlich um z. B. 5 s vordatiertem
Aufnahmezeitstempel einspeisen und prüfen, welche Zeit GSVmulti anzeigt bzw.
speichert. Kostet nach Vorliegen der Spezifikation eine halbe Stunde.

Fällt er negativ aus, beseitigt ein interner Pi-Zeitstempel die zeitliche
Verschiebung in GSVmulti **nicht** (Konzept §6 sagt das ausdrücklich). Dann
braucht es einen anderen Weg:

1. nachträgliche Zuordnung über das JSONL-Audit-Log als führende Zeitquelle,
2. eine konstant gehaltene Sendeverzögerung mit dokumentiertem Korrekturwert,
3. Anpassung der Integration oder des Auswerteverfahrens.

Deshalb trägt jeder Formatter die Fähigkeit `carries_capture_timestamp`, und
die Pipeline vermerkt im Runartefakt, wenn sie `False` ist — statt es zu
verschweigen.

## Die Naht im Code

```
sink/protocol/__init__.py     TelegramFormatter (Protocol) + FormatterCapabilities
sink/protocol/ascii_csv.py    Platzhalter, provisional=True
sink/protocol/gsv_ascii.py    wirft NotImplementedError
sink/serial_out.py            Transport, unabhaengig vom Format
sink/jsonl.py                 Audit-Log, laeuft immer parallel
```

Das echte Format ist später ein **neuer Formatter**, keine Änderung an der
Pipeline. Mehrere Ausgaben gleichzeitig sind vorgesehen (JSONL immer plus
seriell).

## Der Platzhalter — ausdrücklich nicht das GSVmulti-Format

`AsciiCsvFormatter` dient dazu, die Kette Wert → Telegramm → Leitung →
Gegenstelle vollständig zu testen. Alle Achsen, die Konzept §8 als
klärungsbedürftig nennt, sind konfigurierbar, damit das echte Format später nur
eine andere Parametrierung ist:

```
1;1;-12.500;N;valid;492076801394;synthetic
│ │ │        │ │     │            └─ Zeitbasis des Zeitstempels
│ │ │        │ │     └─ capture_timestamp in ns
│ │ │        │ └─ Status: valid | transition | unreadable | stale
│ │ │        └─ Einheit
│ │ └─ Wert
│ └─ frame_sequence
└─ Kanal
```

Konfigurierbar: `field_separator`, `decimal_separator`, `line_ending`,
`decimals`, `include_unit`, `include_status`, `include_capture_timestamp`,
`channel`, `invalid_policy`, `encoding`.

**Die Zeitbasis geht bewusst mit.** Ein Zeitstempel ohne Zeitbasis ist nach
Konzept §6 keine verwertbare Angabe.

## Ungültige Werte

Konzept §7 ist eindeutig: alte Werte dürfen bei Erkennungsverlust nicht
unmarkiert als aktuelle gültige Werte weiterlaufen. Welcher Mechanismus dafür
passt, hängt am tatsächlich unterstützten Protokoll
([OQ-06](open-questions.md)). Alle drei Varianten sind implementiert und
getestet:

| Policy | Verhalten | Belegt durch |
| --- | --- | --- |
| `omit_record` | Datensatz entfällt vollständig | `TxReceipt.omitted = True`, damit die Lücke nicht als Übertragungsfehler gedeutet wird |
| `send_nan` | `NaN` als Wert | Telegramm enthält `NaN` |
| `status_flag` | Wertfeld leer, Statusfeld gesetzt | z. B. `1;7;;;unreadable;...` |

## Elektrische Ebene

Siehe [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) und
[OQ-09](open-questions.md). Kurz: Datenport ist `/dev/ttyAMA0`, nicht
`/dev/serial0`. Pi-GPIO-Pegel dürfen **nicht** direkt mit RS-232 verbunden
werden. Ein Transceiver fehlt noch, ebenso die Bewertung der galvanischen
Trennung.

`sink/serial_out.py` enthält `required_baudrate()` für die Durchsatzrechnung.
Konzept §6 warnt dabei: ein höherer Sendetakt liefert keine zusätzlichen
unabhängigen Messwerte, wenn die Anzeige langsamer aktualisiert.
