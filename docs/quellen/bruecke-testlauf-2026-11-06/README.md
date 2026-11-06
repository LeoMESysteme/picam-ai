# Erster Windows-Testlauf der GSVmulti-Brücke (2026-11-06)

**Was getestet wurde:** der interne Testbuild (`build-test.ps1`, unsigniert, nicht qualifiziert) auf Leonhards Windows-11-PC.
- **Brücke:** gekoppelt mit dem Pi `565e3468-…` (Werkbank-Dienst `dispread-werkbank-bruecke`), Weg Netzwerk (LAN), Endpunkt `https://100.122.154.35:8082`.
- **Portpaar:** com0com, manuell angegeben: Brückenseite COM7, GSVmulti-Seite COM8.
- **GSVmulti:** UserDef auf COM8.

Alle Dateien sind Originale von Leonhard; die Prüfsummen stehen in `SHA256SUMS`:

| Datei | Inhalt |
| --- | --- |
| `Session-COM8.ucf` | die GSVmulti-Session, mit der während des ganzen Tests gearbeitet wurde |
| `dispread-diagnose.zip` | der Diagnoseexport der App (`summary.json`, `details.jsonl`); Secrets sind redigiert, die Suche nach Token-, Angebots- und Passwortfeldern war leer |
| `diagnose-summary.json` | die `summary.json` aus dem ZIP, ausgepackt |

## Ergebnis laut Diagnose und Leonhards Meldung

**Was funktioniert hat:**
- Die EXE wird gebaut, besteht ihren Selbsttest und startet.
- Kopplung und Verbindung über das Netzwerk stehen; der Pi meldet `connected: true` und `transport: network`.
- Der Empfangstest mit Demo-Werten lief: Das Journal zeigt 599 Übergaben an COM7, alle mit Ergebnis `written`, keine davon ungeklärt. Laut Leonhard kamen die Werte in GSVmulti an.
  - Einen Vergleich gegen eine Originaldatei von GSVmulti gab es nicht. Damit gilt der Empfang nur als beobachtet, nicht als belegt.

**Was nicht funktioniert hat:**
- **Kein Messwert im echten Lauf:** Während eines echten Werkbank-Laufs kam in GSVmulti kein Messwert an. Das ist erwartet: Die DUT-Ausgabe über die Brücke ist gesperrt (OQ-06/OQ-47), die Brücke bekommt nur Leerlaufmeldungen.
- **Starke Verzögerung der App, solange die Brücke läuft:**
  - Die Diagnose enthält 26.268 Leerlauf-Abfragen gegenüber 599 Übergaben.
  - Ursache: Der Worker fragt den Pi nach einer Leerlaufantwort nach 10 ms erneut ab.
  - Jedes Ereignis schreibt synchron in die Diagnose und baut die Oberfläche neu auf.
  - Behebung: BQ4.
- **Bedienung blockiert:** Nach dem Verbinden war die Einrichtungsansicht komplett gesperrt. Behoben in 8bdad5d und fbbbf5d.
- **599 statt 600:** Die Demo fordert standardmäßig 600 Werte an, das Journal zeigt 599. Das ist offen; BQ4 untersucht es.

## Session-Vergleich (Beitrag zu OQ-53 und N3)

`Session-COM8.ucf` unterscheidet sich von der gepinnten Vorlage
`tests/fixtures/gsvmulti/session-templates/uart-demo-11.ucf` nur in folgenden Punkten:
- `[ch1] ComNr` 4 → 8
- `Name` „Chan. 4_1“ → „Chan. 8_1“
- `[UserDevice] ComNo` 4 → 8
- ein zusätzlicher Abschnitt `[CopyPaste]` mit Standardwerten, vermutlich von GSVmulti beim Speichern ergänzt

Alles andere ist gleich: `device = "UserDef"`, `BaudRate = 115200`, `OpenFlags = 1073741824`, `Unit = "mV/V"`, `Frequency = 10`, `NumChan = 1`, `Prefix = 37` (`%`), `Separator = 256`.

**Was das zeigt:** Ein Portwechsel betrifft genau diese drei Felder. Mit ihnen hat GSVmulti Demo-Werte über das Portpaar empfangen.

**Was das nicht zeigt:** einen Roundtrip, bei dem eine vom Generator geschriebene Datei in GSVmulti geöffnet wird, eine Bindung an die GSVmulti-Version und eine Klärung der Kodierung von `Separator` (OQ-53). Die automatische Sessionerzeugung bleibt deshalb gesperrt.
