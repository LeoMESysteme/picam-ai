# Portable Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ausführbarer Installer mit geprüften Releasepaketen und System-, Benutzer- und portablem Betrieb, ohne Eingriff in die bestehende Installation.

**Architecture:** Ein eigenständig ausführbarer Standardbibliothek-Installer liest Systemfähigkeiten und prüft eine explizite Lieferung. Der Produktdienst erhält ausschließlich über eine opt-in-TOML-Konfiguration andere Pfade. Paketbau, Produktkonfiguration und Installationsengine sind getrennte Einheiten.

**Tech Stack:** Bash-Bootstrap, Python-Standardbibliothek, TOML im Produkt, Debian-Systempakete, optional systemd.

**Spec:** `docs/superpowers/specs/2026-11-17-installer-vorbereitung-design.md`; Erweiterung durch Nutzerauftrag: andere Installationsarten, OS-Versionen und Fallbacks.

## Global Constraints

- Bestehende Installation, Dienste, var und venv nicht verändern; ausschließlich eigener Worktree und temporäre Testziele.
- Produkt Python >= 3.13; Bootstrap meldet ältere Versionen verständlich. Keine automatische OS-/Python-Umstellung.
- venv mit --system-site-packages; pip --no-deps --no-build-isolation, kein PyPI-Ersatz für native Bibliotheken.
- Systemdienst unter vorhandenem Bedienerkonto; keine gelockerte PAM-Prüfung.
- Kein automatischer Dienststart, Neustart, Bootdatei-Edit, Kalibrierimport oder Bestandsmigration.
- Planungsmodus ist Vorgabe. Systemaktionen benötigen ausdrückliches --apply; Paketinstallation gesondertes Opt-in.
- Andere Linux-Systeme werden nach Fähigkeiten geprüft. Windows/macOS werden für den Pi-Dienst klar abgelehnt.

## Review Focus

- Bestehende oder symlinkte Zielpfade: keine Übernahme oder Überschreibung.
- Ältere Python-Version oder ABI-inkompatible Systemmodule: verständliche Ablehnung vor Installation.
- Archiv-Traversal, Links, doppelte Namen und manipulierte Inhalte: keine Extraktion außerhalb des neuen Releases.
- Fehlendes systemd/Benutzerbus: portabler Betrieb als explizite Alternative.
- Unterbrochene Installation, Wiederholung und zwei parallele Aufrufe: kein unvollständiges aktives Release.

### Task 1: Produktkonfiguration

**Files:** `src/dispread/workbench/config.py`, CLI und Server; `tests/test_install_config.py`.
**Interfaces:** `apply_config(args, argv)` liest `serve --config`; [workbench] für bestehende Serve-Argumente, [live] für templates/calibration. CLI überschreibt Konfiguration; relative Pfade relativ zur TOML. Ohne Konfiguration bisherige Defaults.

- [x] Tests für CLI-Vorrang, fremdes CWD, unzulässige Schlüssel/Typen/Pfade und alten Aufruf schreiben und rot sehen.
- [x] Strikt validierte opt-in-Konfiguration, Übergabe an LiveConfig und hilfreiche Fehler implementieren.
- [x] Konfigurations- und bestehende CLI-/TLS-Tests ausführen; Änderungen separat reviewen.

### Task 2: Releasebau

**Files:** `scripts/build-release.py`, `packaging/release.py`, `tests/test_release_bundle.py`, `pyproject.toml` package data.
**Interfaces:** `build_release(root, output, templates, release_id)` erzeugt tar.gz mit eindeutigem Paketwurzelverzeichnis `picam`, `release.json` (schema=1, release_id, commit, files: Pfad→SHA256), unveränderlicher Vorlage unter `src/dispread/data/templates-stufe2c-2026-09-30.json`. Keine var-/venv-/Geheimnisdateien. Erwarteter Vorlagenhash aus Produktkonstante.

- [x] Tests für vollständige/reproduzierbare Lieferung, fehlende/falsche Vorlage und Ausschluss von Laufzeitdaten schreiben und rot sehen.
- [x] Paketbau mit Standardbibliothek, strikt validierter Release-ID und getrenntem Ausgabeverzeichnis implementieren.
- [x] Pakettests ausführen; Änderungen separat reviewen.

### Task 3: Installer und Bootstrap

**Files:** `install.sh`, `scripts/install.py`, `packaging/picam_installer/{__init__,platform,archive,engine,__main__}.py`, `tests/test_installer.py`.
**Interfaces:** `install.sh`/`scripts/install.py --source ARCHIV|HTTPS --sha256 HASH --mode system|user|portable --user KONTO --host HOST --port PORT [--prefix PATH --data PATH --config PATH --runtime PATH --unit-dir PATH] [--python PATH] [--apply] [--install-packages] [--json]`. Default dry-run; kein Produktimport im Installer. Benutzer- und portable Defaults im eigenen Home. Optionales `--root` für vollständig getrennte Staging-Ziele ohne Systemaktionen. Kein stiller Wechsel des Modus.

- [x] Plattform-, Archiv-, Unit-/Pfad- und Transaktionsprüfungen zuerst schreiben und Fehler wegen fehlender Engine beobachten.
- [x] Fähigkeiten prüfen, Paketquelle validieren, sichere Extraktion/Hashes, atomare Erstinstallation, eigene venv, Selbsttest, Konfiguration, Konto/Rechte, Identität/TLS und optionale Unit implementieren.
- [x] Paketinstallation nur auf apt-Systemen explizit; andere Paketmanager manuell mit konkreten fehlenden Modulen. Keine automatische Python-/OS-Aktualisierung.
- [x] Kein Update auf bestehendes Ziel: explizite Ablehnung mit Hinweis auf fehlenden wartungsgesicherten Updateweg statt riskanter Umschaltung.
- [x] Echte Installationsengine mit Prozessattrappen in temporären Wurzeln testen; echte portable Installation ausschließlich mit Simulation und neuen Daten im eigenen Worktree prüfen.

### Task 4: Integration und Lieferung

**Files:** `docs/INSTALLER.md`, README, CHANGELOG, Abhängigkeiten, Status und Implementierungsbericht.

- [x] Gemeinsam gezielte Tests, Ruff, bash -n, Releasebau und portable Staging-Probe ausführen.
- [x] Volle hardwarefreie Suite im eigenen Worktree laufen lassen und jeden Fehlschlag berichten.
- [x] Frischen Reviewer für gesamten Diff einsetzen, wichtige Befunde mit Regressionen beheben.
- [x] Getestete Supportmatrix und Grenzen dokumentieren; Releasearchiv/Hashes zum Review ablegen. Kein Push/Merge/Deployment.

## Ergebnis

Umgesetzt und unabhängig reviewt. Drei wichtige Reviewbefunde wurden mit
RED→GREEN-Regressionen behoben (Besitzwechsel/überlappende Pfade, tatsächlich
ausgeliefertes Hostzertifikat, begrenzte Archivmetadaten). 200 gezielte und
4075 vollständige hardwarefreie Tests bestanden, 220 Fälle übersprungen.
Zwei native portable Installationswege bestanden, kein
Betriebsdienst gestartet oder verändert. Nachweise im Implementierungsbericht
`docs/quellen/installer-2026-11-17/REPORT.md`.
