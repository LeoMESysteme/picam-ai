# Übergabe an Claude: Windows-Brücke und Workbench

Stand 06.11.2026: Backend einschließlich G1-Wiederanlauf lokal integriert;
430 betroffene Tests bestanden, vier native Windows-Prüfungen übersprungen.
Branchreview und einmalige Nachprüfung sind abgeschlossen: fehlende
Pi-Sperrgrundweitergabe und Diagnosecodes korrigiert, keine offenen wichtigen
Befunde im Backend. Native Produktgates bleiben offen.
Noch keine Nachricht an einen anderen Claude-Chat versandt.

## Auftrag und Arbeitszweig

Leonhard hat Entwurf und Umsetzung freigegeben. Codex übernimmt Backend und
prüfbare Paketierung; **EXE-Oberfläche und sichtbare Workbench-Anpassungen
bleiben Claude vorbehalten**: Anleitung je Weg, Auswahl, Verbindung und Bereitschaft.

Worktree `/home/me-systeme/.codex/worktrees/windows-bridge-core/picam-ai`,
Branch `codex/windows-bridge-core`, Basis `ea29e44`. Der alte Redesign-Worktree
enthält andere Änderungen und den laufenden Labor-Dienst; er bleibt erhalten.
Keine Veröffentlichung, Installation, Hardwareänderung oder Merge ausgeführt.

[Spec](../specs/2026-11-06-windows-bruecke-design.md),
[Hauptplan](../plans/2026-11-06-windows-bruecke.md),
[Nachweise](../plans/2026-11-06-windows-bruecke-nachweise.md),
[Pi](../plans/2026-11-06-windows-bruecke-pi.md),
[Windows](../plans/2026-11-06-windows-bruecke-windows.md),
[V2-Vertrag](../../BRIDGE_PROTOCOL_V2.md).

## Technischer Lieferstand

| Baustein | Vorhanden | Grenze |
| --- | --- | --- |
| P1 | Strikte Profile/v2-Nachrichten und begrenzter OutputState | v1 nur ausdrücklich benannte Demos |
| P2/P3 | Geräteidentität, scoped Kopplung, Operator-/CSRF-Routen, TLS/WSS, begrenzte Discovery | Keine reale Zwei-Pi-/Netzabnahme |
| P4 | Ein Hub, exklusive Lease/Ports, UART-Proof, Run-ID und Live-Factory | DUT-Brücke weiterhin gesperrt |
| N1 | Eigene Runtime-/Qt-Probe, Build-/Hash-/Freigabeverträge | Kein qualifiziertes Windows-Paket/Lock |
| N2/W3 | PnP-/USB-Adapter, Portpaar-/Installer-/Updateverträge | Native Treiber-/Deploymentanbieter fehlen bzw. verweigern ungeprüfte Aktionen |
| N3 | Original-UCF/TXT mit Herkunftsprüfung | Export blockiert: Versionsbindung und echter Roundtrip fehlen |
| W1 | Verbindung, Pin vor HTTP-Headern, signierter UART, DPAPI, Bereitschaft | Native Windows-Prüfungen ausstehend |
| W2 | Dauerhafter COM-Intent, atomare Zulassung, Instanzschutz, Diagnose | Keine Exactly-once-/GSV-Empfangszusage |
| G1 | Tatsächlicher Manager/Worker/Hub/SQLite über lokales TLS integriert | Fake-COM; physische und native Windows-Abnahme fehlt |

**Dies ist keine fertige EXE.** Inno paketiert bislang ausschließlich die
interne N1-Probe. Signierte Produktverteilung und echte Systeminstallation
werden durch die offenen Gates nicht ersetzt.

## Einstieg für die App

Windows-Kern liegt unter `windows/bridge/src/dispread_bridge_app/`.
GUI importiert `ConnectionManager`, `CredentialStore`, `BridgeWorker`,
`DeliveryJournal`, `SingleInstance` und die N2-/W3-Adapter. Keine zweite
Transport-, Zahlenformatierungs- oder Bereitschaftslogik in Widgets bauen.

1. Profil mit dem strikten Parser einlesen. Namen/Suchtreffer als Text rendern.
2. CredentialStore im Benutzerbereich erstellen; Manager mit erwarteter Pi-ID,
   Zertifikat und Client-ID konstruieren. Client-ID lokal dauerhaft speichern;
   ein anderer PC koppelt als eigener Client.
3. Ausgabe-COM-Factory verwendet `pair.bridge_port`; GSVmulti verwendet
   `pair.gsv_port`. Physischer USB-UART-Eingang ist eine dritte Ressource.
4. Journal/Worker erstellen und `manager.set_worker(worker)` aufrufen.
   `snapshot()` liefert die sieben aggregierten Readiness-Felder.
5. `connect(network|uart)` und anschließend Worker starten. `start_demo()` ist
   eine ausdrückliche Aktion; Verbinden startet keine Demo oder Messung.
6. Gemeinsame BridgeEvent-Objekte in den GUI-Thread marshalen, Machinecodes
   deutsch erklären. Rohfehler/Profile/Tokens nicht protokollieren.

`data_link()` ist pro authentisierter Generation stabil.
`admit_write(link, claim)` synchronisiert Generation, Lease, Stop und Budget;
Callback bleibt ohne I/O. Diese Naht nicht umgehen. CredentialStore-Aufrufe
verwenden `expected_pin`; eigene Adapter müssen es durchsetzen. Ein
Zertifikatswechsel oder alter ungebundener Eintrag verlangt neue Kopplung;
alte Tokens gelangen nicht an das neue Zertifikat.

Die sieben `Readiness`-Felder bleiben unverändert. `output`/`next_action`
bilden jetzt auch den authentisierten Pi-Ausgabestand ab:

| `output` | `next_action` | Bedeutung |
| --- | --- | --- |
| `output_off` | `output_off` | Keine aktive Ausgabe bzw. kein Lauf |
| `demo_only` | `None` | Bekannter synthetischer Lauf; keine DUT-Freigabe |
| `blocked` | `dut_release_blocked` | Bekannte DUT-Abnahmesperre |
| `blocked` | `peer_release_blocked` | Anderer Sperrgrund; kein Peer-Freitext als Anweisung |
| `ended` | `run_ended` | Datenlauf beendet, Verbindung weiter vorhanden |
| `unavailable` | `peer_output_unknown` | Unbekannter Ausgabestand |

Disconnect/Generationswechsel löschen den alten Stand; lokale Workerfehler
haben Vorrang. COM und GSV bleiben eigenständige Felder. Nach Backendereignis
den Snapshot neu lesen; keine eigene Interpretation roher Hello-/Idle-Texte.

Bei gewöhnlichem Kanalverlust übernimmt der Manager den Backoff. Der Worker
bleibt `active=True`, wird `recovering`/`output_ready=False` und wartet auf eine
neue validierte Generation. Der COM-Port bleibt dabei derselbe. Die GUI darf
weder Worker noch Demo automatisch neu starten. Nach sauberem `ended` bleibt
die Verbindung für den nächsten ausdrücklichen Start bereit. Expliziter Stop,
Auditfehler, unklare COM-Übergabe und unbekannte Invalidierung bleiben terminal.

Aktuelle Routinggrenze: Die Standardfactory verwendet den ersten ausdrücklich
konfigurierten Profilendpunkt. Die App wählt LAN/Tailscale/gefundenen Endpunkt
vor Erzeugung des Managers; Pi-ID/Zertifikat bleiben aus dem vertrauenswürdigen
Profil. `dispread.bridge.discovery` liefert unbestätigte Kandidaten und
Fallback-Helfer. Unterstützt sind direkte HTTPS/WSS-Origins oder `/bridge/v2`,
keine CONNECT-Proxys/Präfixpfade. Kein stiller Pi-/Transportwechsel.

Im eingefrorenen Einstieg **`multiprocessing.freeze_support()` vor GUI-Aufbau**
aufrufen und die tatsächliche Discovery unter Windows prüfen. IPv6-Link-local
benötigt den lokalen Windows-Scope, keinen ungeprüft übernommenen Pi-Index.

## Pi-/Workbench-Backend

Explizites `serve --bridge-directory` lädt eine bereits provisionierte Identität
und verwendet deren TLS-Zertifikat. Alte `--cert`/`--key`-Dateien werden nicht
überschrieben. Bind-Standard ist 127.0.0.1; externe Dienstadresse und
`--bridge-endpoint` müssen tatsächlich konfiguriert sein. PAM-Konto muss zum
lokalen Dienstkonto passen. Aktivierung wurde hier nicht ausgeführt.

| Aktion | API |
| --- | --- |
| Öffentliches Profil | GET `/live/bridge/profile` |
| Einmalangebot | POST `/live/bridge/offers` |
| Widerruf | DELETE `/live/bridge/clients/{client_id}` |
| Status | GET `/live/bridge/status` |
| UART vorbereiten | POST `/live/bridge/prepare`, JSON `{"transport":"uart"}` |
| UART-Vorbereitung beenden | DELETE `/live/bridge/prepare` |

Operatoränderungen benötigen Login, Origin und CSRF. Netzwerkclient koppelt
über TLS-POST `/bridge/v2/pair`, danach WSS `/bridge/v2` mit scoped Bearer.
UART nutzt frische signierte Nonce vor Zugangsdaten; genaue Kontrollen und
Heartbeat stehen im V2-Anhang. Listener-Vorbereitung ist keine Peer-Verbindung.

Lokale Pi-Kommandos ohne Messstart:

```bash
PYTHONPATH=src ./.venv/bin/python -m dispread.workbench.cli bridge identity --provision
PYTHONPATH=src ./.venv/bin/python -m dispread.workbench.cli bridge export-profile --output pi.dispread --name Labor-Pi --pair --transport uart
PYTHONPATH=src ./.venv/bin/python -m dispread.workbench.cli bridge prepare-uart
PYTHONPATH=src ./.venv/bin/python -m dispread.workbench.cli bridge status
```

Nur unter dem autorisierten Pi-Konto ausführen. Kopplungsangebot ist einmalig
und höchstens fünf Minuten gültig. Die gemeinsame Worktree-venv nicht auf einen
anderen Checkout uminstallieren; deshalb hier `PYTHONPATH=src` verwenden.

## Sichtbare Aufgaben für Claude

- EXE-Onboarding/Tray, UART-/Netzwerkauswahl, Geräte-/Endpunktauswahl,
  Profilimport und verständliche nächste Aktion. Vor UI-Arbeit Impeccable lesen.
- Workbench-Ausgabewahl: Anleitung je Weg, generischer Download aus einem
  tatsächlich bereitgestellten Release-Kanal, Profil/Angebot und Vorbereitung.
  Laufende Konfiguration bleibt schreibgeschützt.
- Bereit für Demo, Pi verbunden, COM-Treiber bereit und GSVmulti-Empfang
  getrennt anzeigen. Workerfehler überstimmt eine weiterhin bestehende
  Pi-Verbindung. `gsv_receipt_confirmed=False` ist kein erfolgreiches Empfangen.
- Minimieren hält den Worker aktiv. Explizites Beenden/Abmelden/Standby an
  `stop()` anbinden; gestarteter COM-Aufruf kann unklar bleiben. Zweitstart
  signalisiert ein SID-Aktivierungsevent; GUI hebt das vorhandene Fenster hervor.
- Journal/Audits erhalten. Unbekannte Invalidierung hat keinen GUI-Bypass.
  Diagnosedetails separat begrenzt/redigiert; `prune()` bei Bedarf im Backend
  regelmäßig ausführen. Keine doppelte Retentionspolitik in Widgets.
- Sessionexport erst nach N3-Feld-/Import-/Empfangsbeleg aktivieren. Keine
  erfundene Datei als erfolgreiche GSVmulti-Session ausgeben.

## Vor Produktfreigabe weiter erforderlich

N1: Windows 11 x64 ohne Python sowie neben unverändertem Python 3.7, echte
hashgesperrte Wheels/Freeze/Qt-Probe. WSS-Client ist an aiohttp 3.14.3 gebunden;
der getestete API-Kandidat ist noch kein qualifizierter Windows-Lock.

N2/W3: Konkretes signiertes Treiberpaket, Weitergabe/HVCI/PnP/Portbeweis,
vertrauenswürdiger nativer UAC-/Deploymentanbieter und tatsächliche
Installations-/Reboot-/Reparatur-/Rollback-/Deinstallationsläufe. Release-Key,
Hosting und Schutz gegen alte signierte Versionen: [OQ-65](../../open-questions.md#oq-65).
Kein Windows-Runner vorhanden; keinen Pi-Runner dafür umdeuten.

N3: Exakte GSVmulti-/Dateiversion, Port/Einheit/Skalierung/Rate/Präfix/Filter
kontrolliert ändern, wieder öffnen und echten Demoempfang separat speichern.
Historische UCF-Originale sind Herkunftsbelege, kein Generatornachweis.

G1 physisch: Zwei Pi, UART/LAN/Tailscale, Abziehen/Prozessabbruch/Standby,
30-Minuten-Demos und Original-GSV-Dateien mit COM-/Quellaudit vergleichen.
DUT-Freigabe bleibt ein separates OQ-06/OQ-47-Verfahren.

## Prüfbelege für die Übernahme

Auf eingefrorenem Backend: 430 Tests bestanden, vier native Windows-Gates
übersprungen (DPAPI, geschützter Store/DACL, Instanzschutz, Freeze-Artefakt).
Die neuen Integrationsfälle verwenden tatsächliche TLS-Routen, Kopplung,
Manager, Worker und SQLite mit Fake-COM. Sie prüfen DUT-Sperre, Barriere vor
VALID, Wiederanlauf mit neuer Generation/Lauf-ID, Stop, Widerruf, Auditfehler
und Nichtwiederholung unklarer Übergaben. Ruff und Diff-Prüfung bestanden.

Doku: strenger Build und gesamter Playwright-Lauf mit 91 bestandenen Tests.
OQ-66 ist mit kontrollierter Testvorbedingung geklärt; keine Wiki-UI geändert.
Die frühere breite Pi-Prüfung ist historische Evidenz, kein neu behaupteter
Gesamtlauf aller Live-/CV-Tests auf diesem Abschlussstand.

Ein Zwischenlauf der neuen erweiterten Zustandsprüfung wartete vergeblich
auf einen zusätzlichen numerischen COM-Versuch; die genaue Laufzeitursache
ließ sich mit Diagnose und Wiederholungen nicht rekonstruieren
([OQ-67](../../open-questions.md#oq-67)). Die finale
Zustandsprüfung verwendet deshalb eine ausdrücklich leere Demo; die getrennten
numerischen Integrationstests bleiben bestehen. Keine Produktfrist erhöht
und kein Durchsatz-/Fehlerfreiheitsschluss aus den Wiederholungen gezogen.

## Entscheidungen zur Reviewgrenze

Das Abschlussreview hat alle Produktionsänderungen des Zweigs geprüft.
Seine folgenden Abgrenzungen sind übernommen; keine davon ist eine bestandene
Produktabnahme. Die konkrete Statusweitergabe wurde im Backend korrigiert und nachgeprüft.

| Grenze | Entscheidung und verbleibende Arbeit |
| --- | --- |
| Qt/Workbench-UI | Nach ausdrücklichem Nutzerwunsch Claude; Kern liefert die Statusdaten. |
| EXE/Windows-Laufzeit | N1 erst mit wirklichem Windows-Build und VM-Belegen; Probe genügt nicht. |
| DPAPI/DACL/Instanz | Linux/Fakes qualifizieren keine Windows-API; native Prüfungen offen. |
| VCOM/Treiber | Unverifizierter Provider verweigert; kein com0com-Paket still freigegeben. |
| UAC/Deployment | Native Anbieter und Systemläufe fehlen; portable Verträge ersetzen sie nicht. |
| Release-Vertrauen | OQ-65 bleibt Gate für Schlüssel, Kanal, Aktualität und Rückstufung. |
| Session/Empfang | N3 muss Version/Felder/Roundtrip belegen; Originale allein reichen nicht. |
| Physische Matrix | Zwei Pi, echte Wege und 30-Minuten-Läufe bleiben gesonderte Abnahme. |
| DUT/Zeitnachweis | Weiter gesperrt; keine Ableitung aus synthetischen Demos. |
| Routing/Proxy | Erster expliziter Endpunkt, direkte WSS-Verbindung; App wählt den Weg. |
| Frozen Discovery/IPv6 | `freeze_support()` und lokale Scope-Auswahl durch App, danach Windows-Test. |
| App-Lebenszyklus | Client-ID dauerhaft speichern, COM wählen, Quit/Logoff/Suspend an Kern anbinden. |
| Unklare Übergabe/COM | Konservativer Stop bleibt; sichere Netzerholung hält denselben COM-Port. |
| v1-Werkzeug | Nur benannte Demo/CLI; produktive Factory verwendet gekoppelten Hub. |
| Integration/Freigabe | Root finalisiert eigenen Branch; kein automatischer Merge/Release/Deploy. |

Die alte v1-Off-Publisher-Instanz wechselt bei `stop()` jetzt von `off` zu
`stopped`. Das Review bewertet diese terminale Statusunterscheidung ohne
aktuellen Live-/Byteeffekt als nicht blockierend; ausdrücklich zurückgestellt.
Der ausgeschaltete Live-Weg erzeugt keinen Publisher.

Aktuelle Test-/Reviewgrenzen stehen im [Status](../../status.md). Buildrezept im Repository:
`windows/bridge/README.md`. GUI-Integration benötigt anschließend ihre
Workbench-/Qt-Tests; diese Übergabe enthält keine sichtbaren UI-Änderungen.
