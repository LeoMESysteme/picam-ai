# Installer: getrennte Vorbereitung für einen neuen Pi

Stand: 2026-11-17. Grundlage: Integrationscommit `911b8f3` und der
[Installer-/TUI-Entwurf vom 13.11.](2026-11-13-installer-tui-design.md).
Dies ist die vorbereitete Ausgestaltung der nächsten Installer-Stufe;
Bootstrap, System-Unit und Pfadmigration sind noch nicht implementiert.

## Auftrag und bestätigte Entscheidungen

Leonhard möchte den Installer bereits vorbereiten. In dieser Session bestätigt:

- Code unter `/opt/picam`, persistente Daten unter `/var/lib/picam`, Systemdienst.
- Dienst unter einem vorhandenen Bedienerkonto. Dieses Konto wird bei der
  späteren Einrichtung ausdrücklich angegeben, nicht aus einem Entwicklerpfad
  oder unbesehen aus einem unter sudo laufenden Prozess abgeleitet.
- Die bestehende Werkbank/picam-ai-Installation muss weiter funktionieren.
  Jetzt keine Installation, Migration, Dienstumstellung oder Systemänderung;
  die Vorbereitung bleibt möglichst vollständig getrennt.

Die Vorbereitung liegt deshalb in einem eigenen Git-Worktree auf
`docs/installer-vorbereitung-20261117`, ohne Verknüpfungen auf `var` oder
eine bestehende `.venv`. Die heutige Lieferung ist dieses Dokument. Es gibt
keinen gestarteten Installer, neu eingerichteten Dienst oder One-Line-Download.

## Ansätze und Wahl

| Ansatz | Nutzen | Nachteil / Entscheidung |
| --- | --- | --- |
| Checkout im Home, Benutzerdienst | Passt zum bisherigen Betrieb | Von Leonhard zugunsten getrennter Systempfade verworfen |
| Versionen in `/opt/picam`, Daten in `/var/lib/picam`, Systemdienst unter Bedienerkonto | Trennung von Code und Daten, Boot-Autostart, Rückweg zur vorigen Version | Gewählt; Installer benötigt später gezielte Administratoraktionen |
| Gleiche Pfade, eigenes Dienstkonto `picam` | Separate Dienstidentität | Für diese Stufe verworfen: widerspricht der heutigen PAM-Kontogleichheit |

Codebeleg: `src/dispread/workbench/server.py::service_pam_user` lehnt root
und ein vom Dienstkonto abweichendes PAM-Konto ab. Ein Systemdienst mit
`User=<bedienerkonto>` kann diesen bestehenden Vertrag erhalten. Seine echte
PAM-Anmeldung muss auf dem zweiten Pi geprüft werden. Die Schutzprüfung
wird für den Installer nicht entfernt.

## Umfang der ersten Lieferung

Ein Releasepaket und ein Installer für einen **neuen, separaten Pi**.
Vorhandene Installationen erkennt der Installer und verweigert ihre
automatische Übernahme. Migration dieses Entwicklungs-Pi ist ein eigener,
später ausdrücklich beauftragter Vorgang.

Die erste Lieferung umfasst Paketprüfung, Betriebssystem-/Python-Prüfung,
getrennte Code-/Datenpfade, Erstkonfiguration, TLS/Brückenidentität und eine
persistent installierte System-Unit. Eine interaktive Textual-Konsole und
ein eigener Verwaltungsbefehl sind nachgelagerte Arbeiten. Bis zur
Namensentscheidung bleibt der bestehende Befehl `dispread` erhalten.

Der Installer nimmt ein ausdrücklich angegebenes lokales Releasearchiv
oder eine HTTPS-Downloadadresse entgegen. Damit lässt sich die Lieferung
zunächst per Datei auf dem zweiten Pi prüfen. Veröffentlichungsort und
Authentifizierung des privaten Forgejo-Repos bleiben offen; es wird kein
öffentlicher Download behauptet und kein Token in einen Beispiel-One-Liner
eingetragen. Der endgültige One-Liner folgt nach dieser Entscheidung.

## Paket und Zielverzeichnisse

Vorschlag des Bearbeiters für die konkrete Ausgestaltung:

| Bestandteil | Ziel / Vertrag |
| --- | --- |
| Versionierter Code samt eigener venv | `/opt/picam/releases/<release-id>/` |
| Aktive Version | `/opt/picam/current` als Symlink auf eine vollständig geprüfte Version |
| Persistente Daten | `/var/lib/picam/`; nie innerhalb eines Releaseverzeichnisses |
| Konfiguration | `/etc/picam/config.toml` |
| Flüchtiger Steuerungssocket | `/run/picam/control.sock`; eigenes Verzeichnis, Modus 0700 |
| System-Unit | `picam-werkbank.service`, `User=<bedienerkonto>` |
| Werkbank-/Live-Daten | `/var/lib/picam/workbench`, `/var/lib/picam/live` |
| Brückenidentität und Kopplungen | `/var/lib/picam/workbench/bridge` |
| Browser-TLS | `/var/lib/picam/workbench/tls` |
| Timing-Kalibrierung | `/var/lib/picam/calibration/`; individuelle Herkunft dokumentieren |
| Geprüfte Leservorlage | Im Release als unveränderliche Paketdatei, nicht aus dem Entwicklungs-`var` laden |

Die Release-ID muss für sichere Verzeichnisnamen validiert werden. Der
Code wird administrativ installiert und ist für das Dienstkonto nur lesbar.
Schreibrechte gibt es gezielt auf Daten- und Socketverzeichnis; kein
rekursives `chown` auf fremden oder verlinkten Bestandsverzeichnissen.
Die venv wird bereits im endgültigen Releaseverzeichnis angelegt, damit
ihre absoluten Interpreter-/Skriptpfade nach Freigabe unverändert bleiben.
Fehlgeschlagene Releases werden nicht aktiviert.

Das Paket enthält Code, Paketmanifest, Versions-/Commitbezug, Leservorlage
mit Sollhash und eine Inhaltsprüfliste. Keine Läufe, privaten Schlüssel,
Kopplungstokens, Kalibrierdatei dieses Pi oder komplette Kopie von `var`.
Ein SHA-256 aus demselben Download ist ein Integritätsabgleich, kein eigener
Herkunftsnachweis: Vertrauen entsteht durch den festgelegten Bezugsweg.
Archive werden vor dem Entpacken auf absolute Pfade, `..`, Links und
Ausbruch aus dem Zielverzeichnis geprüft; bestehende Versionen werden
nicht durch einen erneuten Download überschrieben.

## Konfiguration und Verträge zum bestehenden Code

- Ein Laufzeit-Pfadobjekt ersetzt die parallelen Ableitungen in `paths.py`,
  `defaults.py`, CLI und `live/__init__.py`; keine weitere Pfadwelt im Installer.
- Vorrang: ausdrückliche CLI-Angabe, dann ausdrücklich gewählte TOML-Datei,
  dann bisherige Defaults. Bestehende Aufrufe ohne Konfigurationsdatei
  behalten ihre CWD-relativen Pfade und Vorgaben.
- Relative Pfade in TOML beziehen sich auf das Verzeichnis dieser Datei;
  installierte Konfiguration schreibt absolute Pfade. Ungültige oder
  widersprüchliche Angaben verhindern den Start.
- Die neue System-Unit verweist ausdrücklich auf die Konfigurationsdatei
  und den Interpreter der aktiven Version. Ihr Name wird nicht mit dem
  bestehenden Benutzerdienst `dispread-werkbank-bruecke` gleichgesetzt.
- Python mindestens 3.13; venv mit `--system-site-packages`, Installation
  mit `--no-deps --no-build-isolation`. apt-Pakete ausschließlich aus
  `packaging/apt-packages.txt`; keine PyPI-Ersatzkopien von NumPy/OpenCV/Serial.
- Es gibt keine neuen Vorgaben für Telegramme, Baudraten, Freigabeschranken,
  Messwerte oder Zeitbasen. Auch die heutige Messfreigabe wird nicht geändert.

## Einrichtungsablauf auf dem zweiten Pi

1. **Nur prüfen:** neues Zielsystem, unterstützte Plattform, Python,
   vorhandenes Bedienerkonto, belegte Ports, vorhandene Dienste und Daten.
   Bei Konflikt endet der Ablauf mit Befund statt bestehende Prozesse zu stoppen.
2. **Lieferung prüfen:** explizite Quelle, Release-/Commitbezug,
   Archivstruktur, Datei-Hashes und Leservorlage. Bei einer unvollständigen
   Lieferung keine Aktivierung. Ein Planungsmodus beschreibt Aktionen und
   schreibt weder Zieldateien noch ruft er apt/systemctl auf.
3. **Gezielt installieren:** fehlende Debian-Pakete, neues Releaseverzeichnis,
   eigene venv, Paketinstallation und hardwarefreier Selbsttest. Kein pip
   im bestehenden Projekt und keine Nutzung seiner venv.
4. **Neue Konfiguration:** Konto, erreichbarer Host und Port ausdrücklich
   wählen. Kein Standardhost aus diesem Pi. Fehlende Gruppen/UART-Konfiguration
   melden; Änderungen an Gruppen und Bootdateien nur gesondert bestätigen.
   Kein automatischer Neustart und keine automatische Tailscale-Einrichtung.
5. **Daten bereitstellen:** geprüfte Leservorlage aus dem Release verwenden.
   Die Timing-Kalibrierung wird nicht vom alten Pi kopiert. Bei fehlender
   gültiger Kalibrierung bleibt der Messlauf gesperrt; die Einrichtung kann
   zur späteren Kalibrierung fortgesetzt werden. Ein Kalibrierimport bleibt
   bis zur fachlichen Entscheidung außerhalb dieser ersten Stufe.
6. **Neue Identität und TLS:** ausschließlich im neuen Datenverzeichnis;
   bestehende Dateien nicht ersetzen. Browser-TLS und gepinnte
   Brückenidentität bleiben getrennte Mechanismen. Host/SAN und Ablauf anzeigen.
7. **Systemdienst vorbereiten:** Verzeichnisse mit passenden Besitzern und
   Rechten, Laufzeitverzeichnis über systemd; zunächst nur auf dem neuen Pi.
   Erst nach expliziter Startaktion aktivieren, erreichbare `/live`-Seite und
   PAM-Anmeldung prüfen. HTTPS-Erreichbarkeit allein ist keine Messabnahme.
8. **Ergebnis ausgeben:** Version, Konfiguration, URL, Dienstzustand und
   offene Hardware-/Kalibrieraufgaben. Softwareinstallation, Dienstbereitschaft
   und Bereitschaft für einen Messlauf getrennt ausweisen.

## Wiederholung, Update und Rückweg

Ein identischer zweiter Installationslauf ersetzt weder Konfiguration noch
Identität oder Zertifikate. Ein erneuter Aufruf ist kein stillschweigendes
Update. Geänderte Konfiguration und eine andere Version brauchen eine
ausdrückliche Aktion.

Für spätere Updates gilt: neue Version separat installieren und prüfen,
danach erst `current` umschalten. Lauf, Einrichtung, Diagnosekopie oder
unbekannter Zustand sperren Umschaltung und Neustart. Eine Wartungssperre
muss neue Laufstarts während der Prüfung verhindern; die heutige reine
Statusabfrage im Dienstskript reicht als atomarer Schutz noch nicht aus.
Beim fehlgeschlagenen Start zur zuvor gesicherten Version zurückkehren;
persistente Daten nicht zurückkopieren oder löschen. Inkompatible Datenformate
müssen vor der Umschaltung erkannt werden. Automatische Datenmigration ist
kein Teil der ersten Lieferung.

## Prüffälle vor einer Installation

Tests benutzen temporäre Wurzeln und Attrappen für apt, sudo, systemd,
Benutzer-/Gruppenänderungen und Netzwerkdownload. Sie müssen Folgendes zeigen:

- Planungsmodus schreibt nichts; ungeeignetes System oder vorhandene
  Installation endet vor der ersten Systemänderung.
- Beschädigtes Archiv, falscher Vorlagenhash, unsichere Archivpfade,
  unvollständiges Release und unbrauchbare venv führen zu klarer Ablehnung.
- Paketbedarf, abgebrochene Installation, Wiederholung und bereits vorhandene
  Zielpfade werden korrekt behandelt; ein Fehler aktiviert kein Release.
- Pfadauflösung funktioniert unabhängig vom Arbeitsverzeichnis; alte
  CLI-Aufrufe behalten ihre Pfade. Fehlerhafte TOML überschreibt keine Defaults.
- Unit und Pfadrechte verwenden das ausgewählte Konto; kein root-Betrieb,
  keine gelockerte PAM-Prüfung, keine übernommenen Entwicklerpfade.
- Identität, Zertifikate, Konfiguration und Daten bleiben bei Wiederholung
  erhalten. Fremde Dienste und belegte Ports werden nicht angefasst.
- Fehlende Kalibrierung sperrt Messstart; Installation wird nicht als
  Hardware-/Messabnahme ausgegeben.
- Update-/Rollback-Tests einschließlich konkurrierendem Laufstart folgen
  vor Freigabe dieser nachgelagerten Funktion.

Die vollständige Neuinstallationsprüfung läuft später auf einem zweiten Pi
mit frischem Raspberry Pi OS; eine zusätzliche venv auf diesem Rechner
ersetzt sie nicht. Reale Kamera-, UART-, Boot-, PAM- und Windows-Abnahme
sind separate Schritte und werden hier nicht durchgeführt.

## Heutige Nachweise der vorhandenen Basis

Ausgeführt am Integrationsstand `911b8f3`, vor Produktänderungen:

```bash
PYTHONPATH=src ./.venv/bin/pytest -q \
  tests/test_werkbank_dienst.py tests/test_workbench_tls.py \
  tests/test_product_defaults.py tests/test_install_workbench.py \
  tests/test_product_script_paths.py tests/test_no_dev_data_in_src.py \
  tests/test_tour_facts.py --tb=short
```

Ergebnis: **51 bestanden**. Dazu die fünf im P0a-Bericht vom 14.11.
als socketbedingt blockiert dokumentierten Tests einzeln ausgewählt:

- `test_gsv_transport.py::test_tcp_actual_handshake_and_stop_release_port`
- `test_gsv_bridge.py::test_socket_framing_preserves_first_complete_reply`
- `test_gsv_bridge.py::test_actual_socket_publisher_preserves_invalid_barrier_before_valid`
- `test_gsv_bridge.py::test_actual_socket_lost_ack_does_not_replay_on_reconnect`
- `test_gsv_bridge.py::test_publisher_demo_subprocess_reaches_bridge_with_exact_finite_count`

Ergebnis: **5 bestanden**, insgesamt **56**. Die Sockettests verwenden lokale
Testserver, keine Verbindung zum Werkbankdienst. `bash -n` für vorhandenen
Installer, Dienstskript und Kameradiagnose erfolgreich. Ruff für die beiden
neuen P0a-Konstantenmodule und fünf zugehörige Testdateien sauber.
Kein vollständiger Python-/Browserlauf, kein ausgeführter Installer und
keine neue Hardwaremessung.

Die vorhandene Leservorlage wurde ausschließlich gelesen und geprüft:
25.939 Bytes, SHA-256
`6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a`.
Sie entspricht `DEFAULT_TEMPLATES_SHA256`. Sie ist derzeit nicht versioniert;
die Lieferung als Release-/Paketdatei muss erst umgesetzt werden. Die Vorlage
und die Kalibrierdatei dieses Pi wurden nicht kopiert.

## Verbleibende Entscheidungen und nächster Schritt

Unabhängiger Builder-Check am 17.11.: keine wichtigen Rückfragen vor der
Implementierungsplanung. Dies ist eine Prüfung des Entwurfs, keine
Installations- oder Produktabnahme.

Der Installationsort, Systemdienst und das vorhandene Bedienerkonto sind
bestätigt. Folgende Punkte blockieren die getrennte technische Vorbereitung
nicht und bleiben ausdrücklich außerhalb ihrer ersten Umsetzung:

- endgültiger öffentlicher/interner Bezugsweg und Authentifizierung für den One-Liner;
- Name einer zusätzlichen Verwaltungs-CLI und Zukunft der alten `dispread tui`;
- Zulässigkeit einer Kalibrierübernahme zwischen Geräten;
- Einbindung von Tailscale und Migration dieses bestehenden Pi.

Nach Prüfung dieses Dokuments lässt sich der Implementierungsplan für
Konfiguration/Pfade, Paketlieferung, isoliert testbaren Bootstrap und
System-Unit schreiben. Auch dessen Umsetzung bleibt ohne Ausführung gegen
die bestehende Installation. Ein vollständiger Installationslauf braucht
den gesonderten zweiten Pi.
