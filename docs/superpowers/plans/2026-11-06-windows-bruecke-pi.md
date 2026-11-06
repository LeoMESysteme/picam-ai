# Windows-Brücke: Pi und Protokoll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identität, überprüfte Kopplung und v2-Bereitschaft/Datenkanal auf dem Pi mit Fake-Clients unabhängig von der GUI bereitstellen.

**Architecture:** Reine Protokoll-/Identitätsmodule unter dispread.bridge, aiohttp-Routen am vorhandenen HTTPS-Dienst, UART und Laufoutput über einen gemeinsamen Hub mit exklusiven Ressourcen. Bestehende v1-Demotests und fachliche Sperren bleiben erhalten.

**Tech Stack:** Python >=3.13, aiohttp, Debian-Kryptografiebibliothek, mDNS/DNS-SD, pySerial aus dem System.

**Spec:** [Freigegebener Entwurf](../specs/2026-11-06-windows-bruecke-design.md); [Hauptplan](2026-11-06-windows-bruecke.md).

## Global Constraints

- Pi-venv `--system-site-packages`, Paket `--no-deps`; keine PyPI-Kamera-/CV-/Serialkopien.
- Keine Anmeldung/TLS umgehen; keine statische fremde Pi-IP oder festes `me-systeme` als allgemeiner Vertrag.
- Kopplung 256 Bit, einmalig, maximal fünf Minuten; Geräte-/Client-/Run-IDs nicht vermischen.
- DUT-Ausgabe gesperrt; Test-Override ohne externe Ausgabe; provisional/TimeBaseKind und Audit erhalten.
- UART ttyAMA0 exklusiv; Referenz ttyUSB0 nie als Brückenausgang öffnen.
- CHANGELOG und Abhängigkeiten im selben Commit; Hardwareänderung/Diagnose und neue OQs sofort dokumentieren.

## Review Focus

- Ungeprüfter Profilinhalt mit URL-/Pfadinjektion (P1).
- SD-Klon/gleichnamiger anderer Pi, abgelaufenes Kopplungsangebot (P2/P3).
- Windows mit falscher Systemzeit und veraltetem Zertifikat (P2/P3).
- Zwei Clients oder direkte UART-Ausgabe gegen Bereitschaftslistener (P4).
- ACK-Verlust bei ausstehender Ungültigkeitsbarriere (P1/P4).

### P1: V2-Vertrag und wiederverwendbarer begrenzter Ausgabekern

**Files:** Create `src/dispread/bridge/__init__.py`, `types.py`, `protocol.py`, `output_state.py`; modify `src/dispread/gsv_transport.py`; create `tests/test_bridge_protocol.py`, `tests/test_bridge_output_state.py`, `docs/BRIDGE_PROTOCOL_V2.md`; run existing `tests/test_gsv_transport.py`, `tests/test_gsv_bridge.py` unchanged first.

**Interfaces:**
- `BridgeProfile(schema: int, pi_id: str, name: str, certificate_pem: str, certificate_sha256: str, endpoints: tuple[str, ...], protocol_version: int, pairing_offer: str | None)`.
- `PeerHello(pi_id: str, client_id: str, protocol_version: int, transport: str, run_id: str | None, state: str, release_block: str | None)`.
- `BridgeEvent(kind: str, code: str | None, run_id: str | None, frame_sequence: int | None, detail: dict)`; secrets excluded by event producer.
- `parse_profile(raw: bytes) -> BridgeProfile`, `encode_v2(message: dict) -> bytes`, `decode_v2(raw: bytes) -> dict`.
- `OutputState(out_dir: Path, demo: bool=False)` with `start()`, `publish(record)`, `handle_v1(message)->dict|None`, `abandon_pending()`, `status()->dict`, `metadata()->dict`, `stop()`. v2 adapter translates only validated fields, never authorizes by version number alone.

- [x] P1.1 Protokollanhang zuerst schreiben: genaue JSON-Felder für Hello/Poll/Record/Idle/Ended/ACK/Error sowie explizites DemoRequest, Run-/Lease-/Requestbindung, maximale Nachricht 65536 Bytes, Profil maximal 16384 Bytes/8 Endpunkte, keine NaN/Infinity, keine unbekannten Profilfelder. V1 wird ausdrücklich nicht als v2 akzeptiert.
- [x] P1.2 RED: `test_profile_rejects_oversize_and_executable_urls` prüft 16385 Bytes sowie `file:`, `javascript:` und Pfadfelder; `test_v2_rejects_wrong_version_nonfinite_and_oversize` prüft v1, NaN und 65537 Bytes. `test_profile_preserves_ipv6_scope` prüft explizit geklammerte IPv6-Adresse samt Scope ohne Verlust.
- [x] P1.3 Codecs/Typen implementieren; erlaubte Profil-Endpunkte nur `https`/`wss`, keine Steuerbefehle. Signierte UART-Hello-Payload kanonisch serialisieren; Kryptografieadapter in P2 verifiziert tatsächliche Bytes.
- [x] P1.4 Begrenzt gehaltenen Zustand aus OutputPublisher in OutputState extrahieren, v1-Wrapper delegiert ohne veränderte Semantik. Auditöffnung und Netzwerk-/UART-Worker trennen. RED/GREEN für `test_invalid_barrier_survives_disconnect_and_new_valid`, `test_uncertain_write_never_reoffers_same_numeric_frame`, `test_wrong_run_request_barrier_ack_is_rejected`; vorhandene Teilwrite-/Demo-/Gate-Tests erhalten.
- [x] P1.5 `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_bridge_protocol.py tests/test_bridge_output_state.py tests/test_gsv_transport.py tests/test_gsv_bridge.py`; Erwartung alle bestanden, keine neue reale DUT-Ausgabe. Geänderte Dateien mit Projekt-Ruff prüfen.
- [x] P1.6 Anhang, Code, Tests, CHANGELOG committen. Vor sicherheitsrelevantem Anschluss gezieltes Review des neuen Vertrags; keine GUI erforderlich.

### P2: Pi-Identität und widerrufbare Kopplung

**Files:** Create `src/dispread/bridge/identity.py`, `pairing.py`; create `tests/test_bridge_identity.py`, `tests/test_bridge_pairing.py`; modify `src/dispread/workbench/auth.py`, `cli.py`, `scripts/install-workbench.sh`, `docs/dependencies.md`, `pyproject.toml` nur für neue CLI-Einstiege falls erforderlich.

**Interfaces:** `DeviceIdentity.load_or_create(directory: Path, hardware_id: str) -> DeviceIdentity`, properties `pi_id`, `certificate_pem`, `fingerprint`; `sign_hello(payload: bytes) -> bytes`, `verify_hello(certificate_pem: str, payload: bytes, signature: bytes) -> None`; `PairingStore(directory: Path, clock)` with `create_offer(transport: str, client_id: str | None=None) -> str`, `redeem_offer(offer: str, client_id: str, transport: str) -> str`, `authorize(token: str, transport: str) -> str`, `revoke(client_id: str) -> None`. Rückgabe authorize = client_id; getrennte Tokens je Client/Transport.

- [ ] P2.1 RED: `test_identity_survives_ip_hostname_and_process_change`, `test_hardware_change_requires_explicit_reprovision`, `test_no_identity_in_distributable_image`. Gleiche Hardware behält ID, geänderte Hardware mit kopierter Karte gibt definierten Konflikt statt stiller Nutzung/Datensatzlöschung.
- [ ] P2.2 Identität atomar mit restriktiven Rechten speichern. Neue Produktidentität mit RSA-3072-Schlüssel/TLS-Zertifikat erzeugen; UART-Hello signiert über Standard-RSA-PSS/SHA256 (MGF1 SHA256, Salt 32 Bytes), niemals eigene Kryptomath. Kryptografiebibliothek als Debian-Abhängigkeit am Pi und gesperrte Windows-Abhängigkeit dokumentieren; bestehendes Zertifikat nicht ohne Nutzeraktion ersetzen.
- [ ] P2.3 RED/GREEN: `test_pairing_offer_expires_at_300_seconds`, `test_offer_can_be_redeemed_once_even_concurrently`, `test_wrong_client_or_transport_is_rejected`, `test_revoked_token_fails`, `test_credentials_never_reach_logs`. Angebot = 32 Zufallsbytes; optional noch ungebundenes Exportangebot bindet beim ersten atomaren Einlösen den neuen Client. Vorgebundenes Angebot akzeptiert nur client_id. Pi speichert keine Klartext-Netzwerktokens; Laufzeit-/UTC-Uhrenzweck trennen. `test_identity_private_key_not_downloadable` prüft, dass Profildownload nur das öffentliche Zertifikat liefert und keine private Datei über Workbench-Routen erreichbar ist.
- [ ] P2.4 Konfigurierbaren PAM-Benutzernamen einführen, bestehende Installation behält ihren expliziten Nutzer. Neue CLI-Kommandos `bridge identity`, `bridge export-profile` und `bridge revoke` nur lokal/autorisiert; kein Messstart darüber. Lokale Erstkopplung und Profiltransfer ohne Netzwerk auf dem Windows-PC dokumentieren.
- [ ] P2.5 `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_bridge_identity.py tests/test_bridge_pairing.py tests/test_workbench.py`; Test für falsche Windows-Zeit/Zertifikatsgültigkeit als Clientvertrag in P3 mitführen. Setup ohne vorhandenen Hardwarezugriff mit injizierter Hardware-ID prüfen.
- [ ] P2.6 Identität/Kopplung, Installations-/Abhängigkeitsdoku, CHANGELOG committen; keine vorhandenen Geräteidentitäten auf dem echten Pi ohne Freigabe neu provisionieren.

### P3: Profil, Discovery und gekoppelter WSS-Endpunkt

**Files:** Create `src/dispread/bridge/discovery.py`, `routes.py`; modify `src/dispread/workbench/server.py`, `cli.py`; create `tests/test_bridge_discovery.py`, `tests/test_bridge_routes.py`; modify Installations-/Abhängigkeitsdateien für den ausgewählten mDNS-Adapter.

**Interfaces:** `DiscoveryCandidate(pi_id_hint: str | None, name: str, endpoints: tuple[str, ...])`; `discover_services(timeout_s: float) -> tuple[DiscoveryCandidate, ...]` liefert nur unbestätigte Kandidaten; `publish_service(identity, endpoints: tuple[str,...]) -> closeable`; `add_bridge_routes(app, identity, pairing_store, hub, authorize_operator)` registriert `/live/bridge/profile`, `/live/bridge/offers`, `/live/bridge/clients/{client_id}` und `/bridge/v2`. Operatoraktionen verwenden bestehende Anmeldung/CSRF, WSS prüft eigenen scoped Client-Token. P4 liefert hub; für P3 FakeHub mit identischer öffentlicher Schnittstelle verwenden.

- [ ] P3.1 RED: Profilangebot ohne Operatoranmeldung/CSRF abweisen; v2-Verbindung ohne Token, falscher Scope oder falsche Version abweisen. `/bridge/v2` muss ohne Messlauf authentisiert `idle` oder `output_off` liefern, nicht mit „Pi offline“ scheitern.
- [ ] P3.2 Routen und Profil-Download implementieren; Discovery-Daten enthalten keine Offers/Tokens. `test_revoked_client_loses_active_connection` ergänzt Widerruf auch für eine bestehende Verbindung: Hub-Lease lösen, keine weitere Ausgabe. Nicht auf Request-Host als alleinige vertrauenswürdige Identität verlassen. Dienstbindeadresse und LAN-/Tailscale-Endpunkte explizit konfigurierbar, keine fest codierte produktive IP.
- [ ] P3.3 RED/GREEN: `test_two_same_named_devices_stay_distinct`, `test_dhcp_change_preserves_pi_identity`, `test_mdns_failure_allows_explicit_endpoint`, `test_tls_pin_and_validity_reject_wrong_or_expired_certificate`. Keine globalen trust-Ausnahmen; selbstsigniertes Zertifikat nur gegen überprüften Pin und Gültigkeit. Offene Kopplung bei Uhrfehler erklärt ablehnen, kein stilles Ignorieren.
- [ ] P3.4 Tailscale-Prüfung als optionalen Adapter mit Fake-Status umsetzen: nicht installiert/abgemeldet/Freigabe/DNSfehler unterscheiden, sofern konkret nachweisbar; andernfalls „nicht erreichbar“. Keine Tailnet-Adminschlüssel in der App und keine automatische Tailscale-Installation auf dem Pi aus einem Netz-Timeout.
- [ ] P3.5 `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_bridge_discovery.py tests/test_bridge_routes.py`; zwei reale Pi bzw. bewusst getrennte Testidentitäten im LAN prüfen. DNS-/Profiltests allein gelten nicht als zwei echte Pi nachgewiesen. Vorübergehende Testdienste anschließend beenden.
- [ ] P3.6 Routen/Discovery/Doku/CHANGELOG committen. Ergebnis ist prüfbarer Dienst mit FakeHub, noch kein neuer produktiver Ausgabepfad.

### P4: Ressourcen, Lease und Live-Ausgabenaht

**Files:** Create `src/dispread/bridge/hub.py`, `publisher.py`, `resources.py`; modify `src/dispread/live/service.py`, `session.py`, `src/dispread/workbench/server.py`, `live_api.py`, `src/dispread/workbench/static/live/run/bridge-setup.js`, `run/output.js`, `run/start-popover.js`; create `tests/test_bridge_hub.py`, `tests/test_bridge_publisher.py`; extend `tests/test_live_output.py`, `tests/live_output.test.mjs`, `tests/live-ui.spec.ts` und Fake-Server.

**Interfaces:** `BridgeHub.prepare(transport: str, client_id: str) -> PeerHello`, `attach(client_id, transport) -> lease`, `detach(lease_id)`, `bind_run(run_id: str, state: OutputState)`, `unbind_run(run_id)`, `start_demo(client_id: str, transport: str, count: int=600, rate_hz: float=10.0)`; `SerialPortLease.acquire(path: str, owner_id: str, role: str)` / `release(owner_id)`. `PairedOutputPublisher(config: OutputConfig, out_dir: Path, *, hub, demo=False)` implementiert bestehende `start/publish/status/metadata/stop`-Naht. `LiveService` erhält optional injizierten hub und reicht eine gebundene Factory über bereits vorhandenes `LiveSession.output_factory` weiter.

- [ ] P4.1 RED: `test_two_clients_cannot_own_same_run`, `test_uart_prepare_conflicts_with_direct_serial`, `test_reference_port_is_never_opened`, `test_pairing_does_not_unlock_dut`, `test_test_override_never_creates_output`. Direkte `serial`-Ausgabe behält Prototyp-Hinweis und Pflichtbestätigung.
- [ ] P4.2 Hub und atomare Portbelegung implementieren. UART nur bei ausdrücklich vorbereiteter Brücke öffnen; dauernder Bereitschaftslistener darf direkte UART-Ausgabe nicht heimlich blockieren. Konflikt erklären, keine aktive Belegung wegnehmen. Lease mit 1-s-Heartbeat, 5-s-Ablauf und Run-ID; diese Protokollwerte im Anhang und mit injizierter Uhr an der Grenze prüfen, kein Socket-„connected“ ohne echten Hello.
- [ ] P4.3 PairedOutputPublisher an OutputState anschließen; `tcp` im bestehenden Konfigurationsobjekt ausdrücklich auf gekoppeltes WSS abbilden. Produktserver injiziert stets diese Factory; rohe v1-Sockets bleiben nur in benannten Demowerkzeugen. Nicht konfigurierter Hub liefert erklärten Fehler statt unsicherem Fallback. Audit-/Invalidierungsbarrieren unverändert.
- [ ] P4.4 RED/GREEN: Clientabbruch und Leasewechsel bei offener Invalidierung, Restart mit neuer Run-ID, falsche ACKs und blockierender Client. Test nachweisen: Kamera/Audit laufen weiter, kein Aufholpuffer, keine Wiederholung unklarer Zahlenübergabe.
- [ ] P4.4a Expliziten DemoRequest über beide gekoppelten Wege anbieten: nur wenn keine echte Messung läuft, eigene Demo-Run-ID/Auditablage, synthetische Quelle und demo/provisional=true/time_claim=false. Kein Kamera-/Referenzstart. `test_demo_request_is_refused_during_real_run` und `test_demo_request_uses_separate_audit_and_run_id` müssen bestehen; Anzahl 1–100000 und Rate >0 bis 100 Hz validieren. GUI-Vorgabe 600 Werte/10 Hz ist ein Testziel, kein Durchsatznachweis.
- [ ] P4.5 Workbench erhält Anleitung/Installationslink/Profildownload/Bereitschaftsstatus und autorisierte Prepare-Aktion. Vor UI-Code passende Impeccable-Anweisungen lesen; vorhandene Gestaltung erhalten. Laufende Konfiguration schreibgeschützt, Download/Pairing startet keinen Lauf und bestätigt keine Einrichtung.
- [ ] P4.6 `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_bridge_hub.py tests/test_bridge_publisher.py tests/test_live_output.py tests/test_live_service.py tests/test_live_api.py`; `node --test tests/live_*.test.mjs`; `npx playwright test -c playwright.live.config.ts`. Relevante User-Flows mit Fake prüfen, keine echte Kamera nötig.
- [ ] P4.7 Doku, Sicherheits-/Leaseschema und CHANGELOG mit eigener Änderung committen. Keine produktive DUT-Freigabe und kein Neustart der echten laufenden Werkbank im Rahmen dieser Unit-Prüfung.
