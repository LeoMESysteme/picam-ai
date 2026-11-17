# Installer — Implementierung und Prüfung, 2026-11-17

Grundlage: Integrationsstand `911b8f3`, bestätigter
[Entwurf](../../superpowers/specs/2026-11-17-installer-vorbereitung-design.md),
[Plan](../../superpowers/plans/2026-11-17-installer.md).
Bedienung und Supportmatrix: [INSTALLER.md](../../INSTALLER.md).

## Ergebnis und Trennung

Implementiert sind ein ausführbarer Standardbibliothek-Installer, ein
eigenständiges `.pyz`, geprüfte Releasearchive, drei Installationsarten
und ausdrückliche TOML-Konfiguration. Planung ist der Standard;
`--apply` richtet nur neue Ziele ein. Paketinstallation braucht zusätzlich
`--install-packages`. Weder Dienststart noch Migration, Update,
Benutzer-/Bootänderungen oder Kalibrierimport erfolgen automatisch.

Gearbeitet wurde ausschließlich im eigenen Worktree
`installer-vorbereitung`, mit eigener venv und eigenen Testdateien.
Kein geteilter `var`-/venv-Symlink. Die bestehende Installation wurde nicht
umgestellt, kein Dienst neu gestartet, Kamera/UART nicht geöffnet.
Rein lesende Abschlusskontrolle: `dispread-werkbank-bruecke` aktiv,
PID 714468, Start weiterhin 2026-11-13 19:28:49 CET,
Betriebs-Worktree unverändert auf `95d0540`.

## Code und Fähigkeiten

- `packaging/picam_installer`: unabhängige Engine, Plattform-/Importprüfung,
  begrenzte Download-/Archivverarbeitung, Plan und transaktionale Erstinstallation.
- `install.sh`, `scripts/install.py`: Einstieg aus Checkout oder Release;
  `.pyz` enthält dieselbe Engine ohne benötigten Checkout.
- `packaging/release.py`, `scripts/build-release.py`: reproduzierbare Lieferung
  mit Commit-/Dirty-Bezug und allen Inhalts-Hashes; Vorlage nur aus
  ausdrücklicher, hashgeprüfter Quelle. Keine Daten oder Identitäten von diesem Pi.
- `workbench/config.py`: opt-in-TOML, CLI-Vorrang, relative Pfade zur Datei,
  strikte Schlüssel-/Typprüfung und ausdrückliche LiveConfig-Übergabe.
- `bridge/identity.py`, Workbench-CLI: optionaler DNS-/IP-SAN bei neuer
  Identität; exklusiver Export ausschließlich des öffentlichen Zertifikats.
  Bestehende Identitäten werden bei Hostabweichung nicht erneuert.

Systemmodus verwendet `/opt/picam`, `/var/lib/picam`, `/etc/picam`
und das vorhandene Bedienerkonto. Benutzer- und portabler Modus bieten
ausdrücklich gewählte Alternativen. Kein automatischer Moduswechsel.
Python >= 3.13 und tatsächliche native Importe sind entscheidend;
OS-Namen allein garantieren keine Kompatibilität. Ohne systemd hilft
portabler Betrieb. Ohne Pi-Serienkennung erlaubt `--without-bridge`
die Browser-Werkbank. Für fehlende ABI-passende Bibliotheken wird kein
pip-Ersatz installiert. Windows/macOS werden als Pi-Dienstziel abgelehnt.

Die installierten TOML-Pfade sind absolut; globale Legacy-Pfadkonstanten
wurden nicht umfassend umgebaut. Dies erhält ausdrücklich das bisherige
Verhalten bestehender CLI-Aufrufe. Der Aufwand bleibt auf der neuen
Konfigurationsgrenze, statt Pfade des laufenden Systems umzulenken.

## Testumgebung und Wiederholungen

Eigene venv mit `--system-site-packages`, ausschließlich dort Testwerkzeuge
installiert. Projekt separat mit `--no-index --no-deps --no-build-isolation -e .`
installiert. NumPy/OpenCV/Serial bleiben Systembibliotheken.

Der erste vollständige Lauf wurde vor vollständiger Einrichtung dieser
Testumgebung gestartet: **4024 bestanden, 11 fehlgeschlagen, 220 übersprungen**.
Zehn Fehlschläge waren Subprozessimporte ohne installierbares `dispread`:

- `test_dataset_benchmark.py`: `test_cli_laeuft_gegen_zwei_situationen_und_meldet_phase_a_und_b`,
  `test_cli_bricht_laut_ab_wenn_selected_fehlt`, `test_cli_meldet_luecke_bei_nur_einer_situation`.
- `test_gsv_bridge.py`: `test_actual_demo_cli_stdout_and_audit`,
  `test_publisher_demo_cli_help_and_bounded_unconnected_run`,
  `test_publisher_demo_subprocess_reaches_bridge_with_exact_finite_count`,
  `test_stdout_demo_receipt_does_not_claim_com_submission`.
- `test_live_reference_eval.py::test_cli_exit_codes`: alle drei Parameterfälle.

Diese zehn bestanden nach lokaler Projektinstallation. Der verbleibende
`test_r13_offline_setup.py::test_recording_setup_uses_real_checks_and_copied_reference`
benötigt die bestehenden, nicht versionierten Referenzdateien. Für diesen
Offline-Test wurden getrennte, unveränderliche Kopien der geprüften Vorlage
und der vorhandenen Kalibrierdatei ins **eigene** `var` gelegt. Dann bestand
auch dieser Test. Kalibrier-SHA256 der Testkopie:
`c98adfbb4045299c20ac45ab1b8172de41b0818002900991a27b0a22549dd955`.
Das ist kein Kalibrierimport durch den Installer und keine neue Messung.
Beide nativen Installationsproben besitzen weiterhin keine Kalibrierdatei.

Die neue Gesamtsuite wird nach dieser Umgebungskorrektur separat geprüft;
der erste Lauf wird nicht nachträglich als grün ausgegeben. Die zuletzt
nachgewiesenen Installer-/Konfigurations-/Release-/Identitäts-/Basisprüfungen
stehen im Abschlussabschnitt dieses Berichts.

Zusätzliche Windows-Importkompatibilität: **260 bestanden, 1 fehlgeschlagen**.
`windows/bridge/tests/test_windows_imports.py::test_exe_modules_import_without_unix_clocks`
scheitert am fehlenden `PySide6` in der isolierten Linux-Testumgebung.
Diese Windows-UI-Abhängigkeit wurde nicht auf dem Pi nachinstalliert;
kein Windows-EXE-/GUI-Abnahmenachweis daraus abgeleitet.

## Unabhängiges Review und Korrekturen

| Befund | Korrektur und Regression |
| --- | --- |
| Veränderliche Pfade könnten Code enthalten; rekursiver Besitzwechsel könnte Interpreterlinks folgen | Überlappung vor Schreibzugriff abgelehnt; `os.chown(..., follow_symlinks=False)`; Regressionen für Daten-/Konfigurationsüberlappung und Linkverhalten |
| Brücke und Browser teilen den Listener, das separat erzeugte Browserzertifikat würde nicht ausgeliefert | Neue Brückenidentität mit explizitem Host-SAN; Export genau dieses Zertifikats; TLS-Handshake mit Hostprüfung und Fingerabdruckvergleich |
| PAX-/GNU-Metadaten könnten die entpackte Größenbegrenzung umgehen | Gesamter dekomprimierter Tarstrom wird vor `tarfile` begrenzt; Regression mit kleinem gzip und zu großem Metadatenstrom |

Alle drei Befunde wurden zunächst durch fehlgeschlagene Regressionen
nachgewiesen und danach behoben. Es gibt keine zurückgestellten
Codebefunde dieses Reviews. Der Hinweis auf den ausdrücklich anzugebenden
Steuerungssocket wurde in die Anleitung aufgenommen.

## Native Installationsproben

Getrennte Probeziele unter `picam-installer-artifacts-20261117`:

1. Portable Erstinstallation mit Brücke, System-Python 3.13.5,
   Debian 13/aarch64: eigene venv, installierbares Produkt, absolute
   Konfiguration, geprüfte Vorlage, neue Identität und öffentlicher Zertifikatsexport.
2. Portable Browser-Werkbank mit `--without-bridge`: eigener Daten-/Configbaum,
   klassisches TLS-Zertifikat, keine Brückenprovisionierung.

Beide Installerläufe erfolgreich, kein Dienststart. Danach wurde aus der
installierten venv die echte TOML-Datei gelesen, der Vorlagenhash geprüft
und die weiterhin fehlende Kalibrierung bestätigt. Ein SSL-MemoryBIO-Handshake
mit `check_hostname` und Vertrauen in die exportierte Zertifikatsdatei
bestand; der Peerfingerabdruck entspricht der Brückenidentität. Dabei
wurde kein Netzwerksocket geöffnet. Keine Kamera-/UART-/Windows-Messung.

Die früher erzeugte erste Kandidatenprobe vor der TLS-Korrektur ist kein
Nachweis des finalen Browserzertifikats; maßgeblich sind `portable-verified`
und `portable-browser-only` samt Ergebnisdateien.

## Abschlussprüfung

**Gesamtsuite: 4075 bestanden, 220 übersprungen**, Exit 0:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src nice -n 10 \
  ./.venv/bin/python -m pytest -q -n 2 --tb=short
```

**Gezielt: 200 bestanden**, Exit 0: Installer, Produktkonfiguration,
Releasebau, neue und bestehende Identitätsverträge, TLS, Defaults,
Paket-/Pfadwächter und Tour-Fakten. Ruff für `src`, `tests`, `packaging`
sowie die beiden neuen Python-Einstiege sauber. Bash-Syntax der neuen
und bestehenden Installations-/Dienstskripte sauber; `git diff --check`
sauber. Die Bootstrap-Dateien bestehen zusätzlich die Python-3.9-
Grammatikprüfung; tatsächlich ausgeführt wurde Python 3.13.5.

Auslieferung unter `picam-installer-artifacts-20261117`:

- `picam-install-final.pyz`: eigenständiger Installer, ohne Checkout startbar.
- `picam-ai-installer-20261117.tar.gz`: finales Produkt-/Installerpaket.
- `INSTALLER.md`: kopierte Bedienungsanleitung für Offline-Übertragung.
- `SHA256SUMS`: Prüfsummen der drei Auslieferungsdateien.

Das endgültige Archiv wird aus dem gesicherten Git-Stand gebaut; seine
Inhalts-Hashes und Quellzuordnung stehen in `release.json`. Die öffentliche
Bereitstellung dieser Dateien ist nicht erfolgt. Keine Abnahme auf einem zweiten Pi
oder einem anderen realen Betriebssystem durchgeführt. Die OS-/Architektur-
Fälle sind simulierte Fähigkeitenprüfungen; echte native Installation ist
nur für den hier geprüften Debian-13/aarch64-Host belegt.
