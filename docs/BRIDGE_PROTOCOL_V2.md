# Pi-/Windows-Brückenprotokoll 2

Stand: 2026-11-11 (Taktnachricht B2 additiv, Abschnitt am Ende). Eigener Brückenvertrag, kein GSV-Telegramm.
DUT-Ausgabe bleibt fachlich gesperrt; einzige Ausnahme ist die je Lauf vom
Pi-Bediener bestätigte **Testfreigabe** (Abschnitt unten, keine Abnahme).
Version 2 und eine erfolgreiche Kopplung sind keine Ausgabeabnahme. V1 bleibt
ausschließlich explizite Demo.

## Kodierung und Grenzen

UTF-8-JSON-Objekte, höchstens 65536 Bytes einschließlich optionalem abschließendem
LF. Ein JSON-Objekt je WSS-Nachricht bzw. LF-Zeile auf UART. Keine doppelten
Schlüssel, NaN/Infinity, unbekannten Nachrichtenfelder oder Version 1. `encode_v2`
fügt ein LF an; `decode_v2` prüft ein vollständiges Objekt. `V2LineReader` begrenzt
auch fragmentierte UART-Eingaben. Bezeichner sind 1–128 ASCII-Zeichen aus
Buchstaben, Ziffern, `_ . : -`, beginnend mit Buchstabe/Ziffer. Keine booleschen
Werte an Ganzzahlstellen. Höchstens 16 JSON-Verschachtelungsebenen.

Alle Nachrichten benötigen `version: 2`, `type`, `request_id`, `pi_id`, `client_id`.
Poll/Record/Idle/Ended/ACK benötigen zusätzlich `run_id` und
eine nichtleere `lease_id`. Poll/Idle erlauben `run_id: null` für Bereitschaft ohne
Messlauf; Record/Ended/ACK benötigen eine nichtleere Run-ID. Bereitschaftsleases
sind verbindungsgebunden; ein Laufwechsel verlangt explizite erneute Zuordnung. Der authentisierte Adapter prüft Pi-/Client-/Run-/Leasebindung gegen
die Verbindung **vor** Übergabe an den Ausgabekern. Der Codec prüft Struktur,
erteilt aber keine Berechtigung.

| type | zusätzliche Pflichtfelder | optionale Felder |
| --- | --- | --- |
| `hello` | `protocol_version: 2`, `transport: network\|uart`, `run_id: ID\|null`, `state: Text`, `release_block: Text\|null`, `capabilities: Objekt`, `permissions: Textliste` | `lease_id: ID\|null`, `nonce: Text`, `signature: Text`, `release: "test_unaccepted"` |
| `demo_request` | `transport: network\|uart`, `run_id: ID\|null`, `count: Ganzzahl 1..100000`, `rate_hz: endliche Zahl >0..100` | — |
| `poll` | Run-/Leasebindung | — |
| `record` | Run-/Leasebindung, `demo: true\|false`, `record: ValueRecord`, `frame_age_ns: null`, `barrier_id: positive Ganzzahl\|null` | `release: "test_unaccepted"` (Pflicht bei `demo: false`, verboten bei `demo: true`) |
| `idle` | Run-/Leasebindung, `release_block: Text\|null` | `release: "test_unaccepted"` |
| `ended` | Run-/Leasebindung | — |
| `ack` | Run-/Leasebindung, `frame_sequence: Ganzzahl ≥0`, `barrier_id: positive Ganzzahl\|null`, `outcome: written\|expired\|failed\|unconfirmed\|omitted` | — |
| `tick` (B2) | Run-/Leasebindung, `seq`, `valid`, `value_text`, `frame_sequence`, `time_unix_ns`, `origin_unix_ns`, `rate_hz`, `release: "test_unaccepted"` | — (siehe Abschnitt Taktnachricht) |
| `tick_ack` (B2) | Run-/Leasebindung, `seq: Ganzzahl ≥1`, `outcome: written\|expired\|failed\|unconfirmed`, `filled: Ganzzahl 0..50` | — |
| `error` | `code: ID`, `detail: Text`, `run_id: ID\|null` | `lease_id: ID\|null` |

Texte sind höchstens 4096 Zeichen lang, `state` höchstens 128. Fähigkeiten
enthalten JSON-Daten, keine ausführbaren Inhalte. Berechtigungslisten enthalten
höchstens 32 Texte mit je 128 Zeichen. Hello kann Dienstbereitschaft, keinen
Lauf, Ausgabe aus, Demo und gesperrte DUT-Ausgabe getrennt melden. Ein
`demo_request` fordert ausdrücklich nur eine synthetische Demo an; der Adapter
entscheidet anhand der authentisierten Berechtigungen und exklusiven Lease.

`record` enthält das vollständige unveränderte `ValueRecord.to_dict()`-Schema 1,
mit Zeitbasis, Unsicherheit (unbekannt bleibt `null`), Status und Ablehnungsgründen.
Ohne bestätigte Testfreigabe (siehe unten) ist ausschließlich synthetische
Ausgabe erlaubt; `frame_age_ns` bleibt in jedem Fall `null`. Es gibt keine Subtraktion von Pi-/Windows-Uhren.
Die Formatter-Metadaten einschließlich `provisional` gehören ins Runartefakt.

## Profil

UTF-8-JSON, maximal 16384 Bytes, exakt diese Felder: `schema: 1`, `pi_id`, `name`,
`certificate_pem`, `certificate_sha256`, `endpoints`, `protocol_version: 2`,
optional `pairing_offer` (sonst `null`) und `uart_baud`.
`uart_baud` ist eine Ganzzahl 1..4000000 (kein Boolean); ohne Feld gilt
`dispread.bridge.baud.UART_BAUD` (460800 Baud). Der Pi exportiert den Wert
im Profil, Windows verwendet ihn für Pi↔Brücke. GSVmulti und die direkte
Pi-Ausgabe sind davon getrennt und behalten ihre Session-Baudrate. `endpoints` enthält höchstens acht
verschiedene absolute `https`-/`wss`-URLs, ohne Zugangsdaten, Query oder Fragment.
IPv6 muss geklammert sein; eine Scope-ID bleibt unverändert erhalten. Kein
Dateipfad, Shellbefehl oder ausführbares URL-Schema wird akzeptiert.
Fingerprint: 64 kleine Hexzeichen. Der Codec prüft PEM-Hülle und Fingerprintform;
der Kryptografieadapter prüft Zertifikat, Fingerprintübereinstimmung, Gültigkeit
und Pi-ID. Das Profil ist vor dieser Prüfung kein Identitätsbeweis.
`pairing_offer` ist ein 256-Bit-Angebot (64 Hexzeichen oder 43 Base64url-Zeichen),
keine dauerhafte Zugangskennung. Der Kopplungsdienst erzwingt Ablauf ≤5 Minuten,
einmalige Einlösung sowie Client-/Transportbindung. Kein Angebot/Token im Audit.

## UART-Identitätsnachweis

`canonical_uart_hello(pi_id, client_id, nonce, *, transport="uart", protocol_version=2)` liefert die tatsächlich
zu signierenden Bytes, ohne LF: Domänentrenner
`b"dispread.bridge.uart-hello.v2\0"` gefolgt von JSON mit `sort_keys=True`,
`separators=(",", ":")`, `ensure_ascii=True`, exakt den Feldern
`{"client_id":...,"nonce":...,"pi_id":...,"protocol_version":2,"transport":"uart"}`.
Andere Transportwerte sind für diese Signatur ausgeschlossen. Die Nonce ist ein frischer
256-Bit-Clientwert (43 Base64url- oder 64 Hexzeichen). Signatur und Verifikation
verwenden diese Bytes und den zum importierten Zertifikat gehörenden Schlüssel
über die etablierte Kryptografiebibliothek: RSA mit 3072 Bit,
RSASSA-PSS, Hash SHA-256, MGF1(SHA-256), Saltlänge exakt 32 Bytes. Der
Kryptografieadapter prüft das importierte Zertifikat samt Fingerprint, Gültigkeit
und passendem RSA-Schlüssel und verifiziert die Signatur über die kanonischen
Bytes. Es gibt keinen Algorithmus-Fallback und kein selbst erfundenes
Signaturverfahren.

## Begrenzter Ausgabekern und Wiederanlauf

`OutputState(out_dir: Path, demo=False)` bietet `start()`, `publish(record)`,
`handle_v1(message)`, `abandon_pending()`, `status()`, `metadata()`, `stop()`.
Er öffnet nur das lokale Audit und startet keinen Netzwerk-/UART-Worker.
`OutputPublisher` nutzt denselben Kern und erhält seine v1-Schnittstelle.
Ein v2-Adapter darf nur nach Codec- und Berechtigungsprüfung die validierten
Poll-/ACK-Felder in v1-Kernfelder übersetzen; dies ist keine v1-Netzwerkfreigabe.

Im Speicher liegen der jüngste Datensatz, eine Invalidierungsbarriere und
höchstens ein ausstehendes Angebot. Die Barriere hat Vorrang und wird nur
bei passendem `written`-ACK beseitigt. ACK muss Request, Run, Frame und Barriere
exakt treffen; der v2-Adapter prüft zusätzlich Pi, Client und Lease. Neue
Ungültigkeit ersetzt eine ältere Barriere, deren späteres ACK die neue nicht
beseitigen kann. Verbindungs-/Leaseverlust ruft `abandon_pending()` auf:
Ein numerischer Versuch wird als unbestätigt auditiert und nie wieder angeboten;
eine Barriere bleibt bis zur bestätigten Invalidierung wirksam. Kein historisches
Nachsenden und keine Exactly-once-Zusage. COM-ACK bedeutet vollständige Annahme
durch den lokalen COM-Schreibpfad, niemals Empfang durch GSVmulti.

## P4: Lease und explizite UART-Vorauthentifizierung

`heartbeat` enthält exakt die Basisfelder plus `run_id` (nullable) und
`lease_id`. Antwort ist `heartbeat` mit denselben Bindungen. Intervall 1 s,
Ablauf bei **>= 5 s** ohne gültige Nachricht, monotone Pi-Uhr. Heartbeat liest
keinen Datensatz, reserviert keine Übergabe und bestätigt keinen COM-Write.
Neue Runs werden durch `hello` mit neuer Run-ID synchronisiert; ein ACK mit
fremder Run-/Lease-/Request-/Frame-/Barrier-ID wird abgelehnt.

UART wird nur durch eine autorisierte lokale/Operator-Prepare-Aktion geöffnet.
Vorab kennt der Client das geprüfte, gepinnte Profil. Die Kontrollnachrichten
haben die gemeinsamen Basisfelder (`version`, `type`, `request_id`, `pi_id`,
`client_id`) und ausschließlich folgende Zusatzfelder:

| Typ | Pflichtfelder | Grenzen |
| --- | --- | --- |
| `uart_challenge` | `nonce` | frische 256-Bit-Token-Darstellung |
| `uart_proof` | `nonce`, `signature` | gleiche Nonce; Base64-Signatur, max. 4096 Zeichen |
| `uart_auth` | `nonce`, `mode`, `credential` | mode `token` oder `offer`; 256-Bit-Credential |
| `uart_authenticated` | `token` | 256-Bit-UART-Token (auch nach Angebotseinlösung) |

Der Pi signiert P2 `canonical_uart_hello(pi_id, client_id, nonce)`; der Client
muss Nonce, Profilpin/Zertifikatsgültigkeit und RSA-Beweis prüfen, **bevor** er
`uart_auth` sendet. Ein Auth-Schritt gilt nur für die unmittelbar vorherige
Challenge derselben Client-/Request-/Pi-ID, maximal fünf Sekunden. Credentials
werden ausschließlich im UART-Scope autorisiert/eingelöst, nie in capabilities
oder Audit/Fehlertexte kopiert. Nach `uart_authenticated` ist ein reguläres
v2-UART-`hello` erforderlich; erst dann entsteht eine Lease. Alle Frames bleiben
auf 65536 Bytes beschränkt; Read/Write sind zeitlich begrenzt. Unauthentifizierte
Bereitschaft ist kein PeerHello und keine Lease. Rücksetzung/Abbruch verwirft
fragmentierte Eingaben und Sessionzustand.

### Pi-Bereitschafts-API und lokale Aktion

- `GET /live/bridge/status`: Operator-Sitzung; `pi_id`, nullable `run_id`,
  `real_run`, `connected`, nullable `transport`, `uart_prepared`, `uart_state`,
  nullable `uart_error`, `release_block`. `opening`/`listening` bedeuten nur
  vorbereiteten UART; `connected` verlangt eine gültige authentifizierte Lease.
- `POST /live/bridge/prepare` mit exakt `{"transport":"uart"}`: Operator,
  Origin und CSRF erforderlich. Antwort ist obiger Status, kein PeerHello.
  Konflikte liefern HTTP 409. Wiederholung übernimmt keine fremde Belegung.
- `DELETE /live/bridge/prepare`: gleiche Autorisierung, beendet eigenen Listener
  und dessen Lease; Antwort Status. Profilabruf und Dienststart öffnen UART nie.
- Ohne Netzwerk und ohne bekannte Windows-Client-ID:
  `dispread bridge prepare-uart --socket /PFAD/control.sock`.
  `bridge status` und `bridge stop-uart` verwenden denselben optionalen
  `--socket`-Parameter. Autorisierung erfolgt über den privaten (0700)
  lokalen Dienstsocket. Der bereits gestartete Dienst muss mit
  `serve --bridge-directory BESTEHENDE_IDENTITAET` konfiguriert sein.

`tcp` im bestehenden Live-Konfigurationsobjekt bedeutet nun gekoppeltes WSS
am konfigurierten HTTPS-Dienst. Alte `tcp_host`/`tcp_port`-Felder bleiben als
Konfigurationskompatibilität erhalten und öffnen keinen eigenen Listener.
Unkonfigurierte `LiveService`-/`LiveSession`-Brückenausgabe wird abgelehnt;
v1-Transport ist nur durch ausdrückliche Demo-/Test-Factory-Injektion nutzbar.

Jeder echte Lauf, auch `off` und direkte `serial`-Ausgabe, reserviert vor dem
Kamerastart eine frische globale Run-ID. `session.json` und der gekoppelte
Publisher tragen diese ID. Eine Demo benutzt `bridge/demo/<Run-ID>/` mit
`demo.json`, `records.jsonl` und `output.jsonl`, nur synthetischen Zeitstempeln
und `demo=true`, `provisional=true`, `time_claim=false`. Sie startet weder
Kamera noch Referenz und wird bei reserviertem echten Lauf abgelehnt. Client-
Abbruch oder Lease-Ablauf beendet die erzeugte Demo und gibt ihre Reservierung
frei; auch langsame Raten warten in abbrechbaren Abschnitten von höchstens
200 ms.

UART und direkte serielle Ausgabe teilen kanonische Gerätebelegung über
prozessübergreifendes `flock` in einem geschützten benutzerspezifischen
Lockverzeichnis; zusätzlich verlangt pySerial `exclusive=True`.
`/dev/ttyUSB0`, Symlinks und dieselbe Gerätedatei über Geräte-ID sind als
Ausgang verboten, unabhängig vom alten Referenzadapter-Override.
POSIX-Locks werden erst beim Pi-Portzugriff importiert.

Der Hub-Registry-Lock schützt ausschließlich Metadaten. Ausgabe-Audit und
ACK-/Invalidierungsserialisierung benutzen den bestehenden OutputState-Lock;
Lease/Run werden danach erneut geprüft. Socket-/UART-I/O findet außerhalb
beider Locks statt. Ein verlorenes ACK bleibt unbestätigt: Zahlen werden
nicht wiederholt, eine offene Ungültigkeitsbarriere bleibt erhalten.

## Testfreigabe echter Werte (seit 2026-11-09, additiv, v2 bleibt v2)

Nutzerentscheidung 2026-11-09 für den Test am 11.11.: echte Messwerte dürfen
über die Brücke (UART und Netzwerk) nach GSVmulti, **nur** wenn der
Pi-Bediener den Lauf mit `output = {transport: "uart"|"tcp", …,
acknowledge_unaccepted: true}` startet. Das ist **keine Abnahme** und keine
Messfreigabe (OQ-06/OQ-47 bleiben offen). Ohne `true` bleibt alles wie oben
gesperrt; die EXE hat keinen Schalter dafür.

- **Freigabestand:** `hello` und `idle` tragen `release: "test_unaccepted"`
  und `release_block: null` nur, wenn der gebundene echte Lauf bestätigt ist
  **und** die Lease denselben Ausgabeweg nutzt. Sonst fehlt `release`, und
  `release_block` nennt die Sperre. Der Codec akzeptiert ausschließlich diesen
  Wert und nie zusammen mit einer Sperre. Der Pi sendet das Feld nur im
  freigegebenen Fall: ein alter Client ohne R1-Codec lehnt es als unbekanntes
  Feld ab und verbindet nicht (fail-closed); ein neuer Client nimmt ohne Feld
  „gesperrt“ an. `capabilities.dut_output` bleibt `false`.
- **Ankündigung vor Wert:** Ändert sich der Freigabestand im selben Lauf (die
  Run-ID wird vor der Publisher-Bindung reserviert), antwortet der Pi auf
  `poll`/`heartbeat` zuerst mit `hello`. Ein `record` mit `demo: false` geht
  nur an eine Lease, der der aktuelle Stand angekündigt wurde.
- **Record:** `demo: false`, `release: "test_unaccepted"`, vollständiger
  `ValueRecord` mit seiner echten Zeitbasis, `frame_age_ns: null` (keine
  Altersbehauptung, keine Uhrensubtraktion). Der Pi bietet einen gültigen
  Wert höchstens `max_frame_age_ms` (Konfiguration, Standard 1000 ms) nach
  seiner Veröffentlichung an, gemessen nur auf der Pi-Uhr; danach verfällt er
  (`stale_skipped` im Audit), kein Nachsenden.
- **Altersschranke Ende zu Ende:** Sie besteht aus zwei getrennten Budgets: Pi
  `max_frame_age_ms` (Standard 1000 ms) ab Veröffentlichung, danach Windows bis
  `timeout_s` (Standard 1,0 s) für Anfrage, Verarbeitung und COM-Übergabe. Die
  OCR-Laufzeit vor der Veröffentlichung ist nicht enthalten. Ein bei GSVmulti
  ankommender Wert kann also bis ca. 2 s plus OCR-Laufzeit alt sein; das ist
  keine Aussage über das Messalter der Anzeige.
- **Barriere und Laufwechsel:** Eine offene Invalidierungsbarriere gehört zum
  Lauf und wird bei einem Laufwechsel nicht in den nächsten Lauf übernommen.
  Innerhalb eines Laufs (z. B. Lease-Wechsel) geht sie jedem späteren Wert vor.
- **Zeitbasis:** Unter Testfreigabe bietet der Pi nur Datensätze mit echter
  Kamerazeitbasis (`v4l2_monotonic`) an; andere (synthetisch/Replay) werden
  nie angeboten (Audit `release_time_base_rejected`).
- **Nur VALID an COM:** Der Windows-Kern formatiert freigegebene Werte mit
  dem P4-3-`UserDefinedFormatter(prefix="%")` – byte-gleich mit UART direkt.
  Ungültige Werte laufen weiter als Invalidierungsbarriere, werden aber mit
  `ack.outcome = "omitted"` quittiert, ohne ein COM-Byte. Der Pi lehnt
  `written` für eine Barriere im Testfreigabe-Lauf ab und hebt die Barriere
  nur mit passendem `omitted` auf. Ein Demo-Lauf akzeptiert `omitted` nie.
  GSVmulti zeigt bei ausgelassenen Werten den letzten Wert unmarkiert weiter;
  genau so steht es im Hinweis (`release_note`).
- **Windows-Seite:** `test_release` nur, wenn Hello/Idle der aktuellen
  Generation und Run-ID den Marker trugen (`_DataLink.test_release_for`). Ein
  `record` mit `demo: false` ohne vorherige Ankündigung widerruft die
  Verbindung (`peer_invalid`).

## Taktnachricht für den Vierkanal-Takt (seit 2026-11-11, B2, additiv)

Spec: `docs/superpowers/specs/2026-11-11-gsvmulti-takt-vierkanal-design.md`
(F1–F5). Gilt nur für einen echten Lauf mit `output.format: "4ch"` auf `uart`
oder `tcp` **und** bestätigter Testfreigabe. Keine Abnahme, keine Messfreigabe.

**Takt auf dem Pi.** Der Pi entscheidet jeden Takt selbst, mit demselben
`dispread.live.tick.Ticker` wie bei UART direkt (B1): festes Monotonraster,
1–10 Hz (Vorgabe 10), kein Aufholen; gültig nur ein noch nicht gesendetes,
VALID-Bild mit echter Kamerazeitbasis, jünger als `max_frame_age_ms`. Jeder
erzeugte Takt wird **vor** dem Angebot als `tick` in `output.jsonl` auditiert.
Ohne Testfreigabe entsteht kein Takt (auch keine Fehlwertzeile).

**Warteschlange statt latest-only.** Der Pi hält die erzeugten Takte in
Reihenfolge vor und bietet sie einzeln an (ein offenes Angebot je Lease wie
bisher). Ein Takt, der mehr als `TICK_WINDOW = 50` Takte hinter dem jüngsten
liegt, gilt als verloren (`tick_lost`, `reason: window`); am Laufende werden
erzeugte Takte begrenzt (1 s) noch abgeholt, danach `reason: run_end`. Ein
angebotener Takt wird nie erneut angeboten (Lease-Verlust: `unconfirmed`).

**Fähigkeit.** Der Windows-Client meldet im Hello `capabilities: {"tick": 1}`.
Ohne diese Fähigkeit bietet der Pi in einem Taktlauf nichts an: Hello/Idle
tragen keinen `release`, sondern die Sperre `TICK_CLIENT_BLOCK`; eine
`tick_ack` dieses Clients wird abgelehnt. Alte Clients sehen also nie einen
Takt (fail-closed). Das Pi-Hello bleibt sonst unverändert.

**Nachricht `tick`** (gemessen 410 Byte mit 32-stelligen Kennungen, statt
~1,2 kB je `record`; die Spec-Schätzung von 150 Byte enthielt die
Basisfelder nicht). Ein Takt kostet mit Poll, Quittung und Idle-Antwort etwa
1,2 kB auf der Leitung; auf UART reicht das bei 10 Hz erst mit 460 800 Baud
(`bridge/baud.py`, Branch `feat/bruecke-ux`) sicher, siehe Messung im
CHANGELOG-Eintrag B2.

| Feld | Inhalt |
| --- | --- |
| `seq` | Taktnummer ab 1, aufsteigend; Lücken = verpasste oder verlorene Takte |
| `valid` | `true`/`false` (JSON-Bool) |
| `value_text` | nur bei `valid`: dezimaler Anzeigetext ohne Leerzeichen, nie Exponent/NaN/Inf/`99999999.0`; sonst `null` |
| `frame_sequence` | nur bei `valid`: Bildnummer ≥ 0; sonst `null` |
| `time_unix_ns` | gültig: Erfassungszeit des Bilds; ungültig: Nominalzeit des Takts (Unix-ns aus Pi-Monotonuhr + eingefrorenem Startversatz, OQ-43 provisional) |
| `origin_unix_ns` | Rasterursprung in Unix-ns; Nominalzeit von Takt *s* = `origin + ceil(s · 10⁹ / rate_hz)` |
| `rate_hz` | 1–10 |
| `release` | Pflicht, genau `test_unaccepted` |

**Quittung `tick_ack`** bindet Request, Run und `seq` exakt. `written`: die
Taktzeile wurde vom lokalen COM-Treiber angenommen (kein GSVmulti-Empfang).
`expired`: Zeile nicht geschrieben (Windows-Budget 1 s abgelaufen); der Pi
zählt den Takt als verloren, Windows füllt ihn beim nächsten Takt auf.
`failed`/`unconfirmed`: unbekannt. `filled`: Zahl der Fehlwertzeilen, die
Windows unmittelbar vor diesem Takt geschrieben hat.

**Windows: Formatieren und Auffüllen.** Windows formatiert mit dem
`TickFormatter` (`gsvmulti_userdefined_4ch_v1`): `%wert;gültig;takt;zeit\r\n`.
Ist die höchste geschriebene Taktnummer dieses Laufs *n* und kommt Takt *n+k*,
schreibt Windows zuerst *k−1* Fehlwertzeilen `%99999999.0;0;s;Nominalzeit`,
dann den Takt. Ist *k−1 > 50*, wird nicht aufgefüllt; die Lücke steht im
Journal (`tick_gaps`) und der Lauf gilt als gestört (`tick_disturbed`). Ein
Takt mit *s ≤ n* wird nie geschrieben (bereits geschriebener Takt: nur erneute
Quittung). Jede Zeile, auch jede Auffüllung, wird **vor** dem COM-Schreiben im
`DeliveryJournal` (Tabelle `ticks`, Art `tick`/`fill`) beabsichtigt; eine
offene oder unbekannte Zeile sperrt die weitere Ausgabe für diesen Pi.

**Statusfelder.** Pi (`run.output.tick`, `session.json.output.tick` bzw.
`output.status.tick`): B1-Felder (`rate_hz`, `seq`, `total`, `valid`,
`invalid`, `missed`, Zeitbasis) plus `offered`, `acknowledged`,
`unconfirmed`, `lost`, `queued`, `window`. Es gilt `total = acknowledged +
unconfirmed + lost + queued` und `seq = total + missed`. Windows
(`WorkerStatus`): `ticks_written`, `ticks_invalid`, `ticks_filled`,
`tick_disturbed`, je laufendem bzw. letztem Lauf.

**Laufstart.** `output` für `uart`/`tcp` nimmt additiv `format: "1ch"|"4ch"`
und bei `4ch` `rate_hz` (1–10, Vorgabe 10); `max_frame_age_ms` gilt als
Altersgrenze des Takts. Ohne `format` bleibt die Einkanal-Ausgabe
unverändert (`record`, nur VALID an COM).
