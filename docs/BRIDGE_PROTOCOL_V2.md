# Pi-/Windows-Brückenprotokoll 2

Stand: 2026-11-06. Eigener Brückenvertrag, kein GSV-Telegramm.
DUT-Ausgabe bleibt fachlich gesperrt. Version 2 und eine erfolgreiche
Kopplung sind keine Ausgabeabnahme. V1 bleibt ausschließlich explizite Demo.

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
| `hello` | `protocol_version: 2`, `transport: network\|uart`, `run_id: ID\|null`, `state: Text`, `release_block: Text\|null`, `capabilities: Objekt`, `permissions: Textliste` | `lease_id: ID\|null`, `nonce: Text`, `signature: Text` |
| `demo_request` | `transport: network\|uart`, `run_id: ID\|null`, `count: Ganzzahl 1..100000`, `rate_hz: endliche Zahl >0..100` | — |
| `poll` | Run-/Leasebindung | — |
| `record` | Run-/Leasebindung, `demo: true`, `record: ValueRecord`, `frame_age_ns: null`, `barrier_id: positive Ganzzahl\|null` | — |
| `idle` | Run-/Leasebindung, `release_block: Text\|null` | — |
| `ended` | Run-/Leasebindung | — |
| `ack` | Run-/Leasebindung, `frame_sequence: Ganzzahl ≥0`, `barrier_id: positive Ganzzahl\|null`, `outcome: written\|expired\|failed\|unconfirmed` | — |
| `error` | `code: ID`, `detail: Text`, `run_id: ID\|null` | `lease_id: ID\|null` |

Texte sind höchstens 4096 Zeichen lang, `state` höchstens 128. Fähigkeiten
enthalten JSON-Daten, keine ausführbaren Inhalte. Berechtigungslisten enthalten
höchstens 32 Texte mit je 128 Zeichen. Hello kann Dienstbereitschaft, keinen
Lauf, Ausgabe aus, Demo und gesperrte DUT-Ausgabe getrennt melden. Ein
`demo_request` fordert ausdrücklich nur eine synthetische Demo an; der Adapter
entscheidet anhand der authentisierten Berechtigungen und exklusiven Lease.

`record` enthält das vollständige unveränderte `ValueRecord.to_dict()`-Schema 1,
mit Zeitbasis, Unsicherheit (unbekannt bleibt `null`), Status und Ablehnungsgründen.
In dieser Version ist ausschließlich synthetische Ausgabe erlaubt; deshalb
bleibt `frame_age_ns` `null`. Es gibt keine Subtraktion von Pi-/Windows-Uhren.
Die Formatter-Metadaten einschließlich `provisional` gehören ins Runartefakt.

## Profil

UTF-8-JSON, maximal 16384 Bytes, exakt diese Felder: `schema: 1`, `pi_id`, `name`,
`certificate_pem`, `certificate_sha256`, `endpoints`, `protocol_version: 2`,
optional `pairing_offer` (sonst `null`). `endpoints` enthält höchstens acht
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
