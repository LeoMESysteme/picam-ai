# GSVmulti-Anbindung

Für die Trennung von erkanntem Wert, Zeitstempel und Transportbeleg siehe
[Messpfad und Freigabe](uebersicht/messpfad.md#ausgabe-und-fehlersuche)
und [Zeitstempel richtig lesen](uebersicht/zeitstempel.md#von-aufnahme-bis-gsvmulti).

## Stand: das Format ist unbekannt

Die Telegrammspezifikation der eingesetzten GSVmulti-Version liegt **nicht**
vor. Ein Mensch muss sie intern beschaffen ([OQ-07](open-questions.md)).

**Präzisierung 2026-09-22.** Die frühere Aussage „`me-systeme.de` blockt
automatische Abrufe mit HTTP 403" galt pauschal und ist so falsch: **PDFs unter
`/produkte/.../anleitungen/` waren bei der Prüfung am 2026-09-22 abrufbar
(HTTP 200)**; die geprüften HTML-Produktseiten antworteten mit 403. Beschafft und lokal abgelegt sind
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
frischen Clone. Die [GSV-2-Anleitung](https://www.me-systeme.de/produkte/elektronik/gsv-2/anleitungen/gsv2-bedienungsanleitung.pdf)
ist als Quell-URL dokumentiert. Weitere Recherche-Ausgangspunkte stehen in
[Konzept §12](../Konzept.md#12-quellen-aus-der-bisherigen-diskussion); der
lokale Dateiname allein ist keine dauerhaft verfügbare Quelle.

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
der jeweilige Lauf muss diese Fähigkeit zusammen mit `provisional` im
Runartefakt dokumentieren. Beispiel 16 schreibt beide Angaben in
`report.json`; `Pipeline` selbst erzeugt keinen allgemeinen Laufbericht.
Der aktuelle `/live`-Pfad schreibt JSONL und hat keinen seriellen Formatter.

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
Gegenstelle vollständig zu testen. Trennzeichen, Zahlendarstellung,
Zeitstempel und Fehlerbehandlung sind für gezielte Transporttests
konfigurierbar. Ob das echte Format mit anderer Parametrierung darstellbar
ist oder einen neuen Formatter braucht, bleibt bis zur Spezifikation offen:

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
| `status_flag` | Bei abgelehnten Datensätzen (`value=None`) Wertfeld leer, Statusfeld gesetzt | z. B. `1;7;;;unreadable;...` |

## Elektrische Ebene

Siehe [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) und
[OQ-09](open-questions.md). Für die **geplante Ausgabe nach GSVmulti** ist `/dev/ttyAMA0`
vorgesehen, nicht `/dev/serial0`. Pi-GPIO-Pegel dürfen **nicht** direkt mit
RS-232 verbunden werden. Der Transceiver für diesen Ausgang und die
Bewertung der galvanischen Trennung fehlen weiterhin.

Die **eingehende Referenz** des GSV-2AS wird dagegen bereits über einen
PL2303-USB-RS232-Adapter (`/dev/ttyUSB0`, 38400 8N1) aufgezeichnet. Dieser
Aufbau belegt weder den GPIO-Ausgang noch die GSVmulti-Kompatibilität.

`sink/serial_out.py` enthält `required_baudrate()` für die Durchsatzrechnung.
Konzept §6 warnt dabei: ein höherer Sendetakt liefert keine zusätzlichen
unabhängigen Messwerte, wenn die Anzeige langsamer aktualisiert.
