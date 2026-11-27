# CI-Fehlerkatalog und Stufenübersicht

Dieser Katalog gehört zu `scripts/ci.py`. Jede rote Stufe endet dort mit
Ursache, Fix und einem Verweis auf einen Anker dieser Seite
(`docs/ci-failures.md#<anker>`). Die Anker `#ruff`, `#gitleaks`, `#bandit`,
`#changelog`, `#pytest`, `#playwright`, `#release`, `#perf`, `#hardware` und
`#werkzeug-fehlt` werden von `ci.py` ausgegeben und dürfen nicht umbenannt werden
(`tests/test_ci_workflows.py` prüft das).

## Welche Stufe läuft wann {#stufen}

Die Zeiten sind Richtwerte vom Pi 5 (Plan-Annahmen, `-n 4`), keine Zusagen. Lokal und in
der CI gilt derselbe Aufruf; jede Stufe druckt am Ende "Zum lokalen Nachstellen: ...".

| Stufe | Wann | Inhalt | Zeit | Befehl |
| --- | --- | --- | --- | --- |
| T0 | jeder Commit (Hook `.githooks/pre-commit`) | ruff auf geänderte Dateien, gitleaks (staged), bandit (geänderte Dateien), CHANGELOG-Regel | unter 30 s | `scripts/ci.py t0 --staged` |
| T1 | Push auf Nicht-master-Branches, PR gegen andere Branches als master/main (`ci-fokussiert.yml`), `pre-push` | T0 plus betroffene Tests ohne `slow/timing/hardware/serial`; eskaliert bei Kernpfaden, über 25 Dateien oder Quelle ohne Zuordnung auf T2 | wenige Minuten | `scripts/ci.py t1` |
| T2 | PR gegen master/main, Label `full-ci`, manuell (`ci-voll.yml`) | ruff, gitleaks (gesamte Historie), bandit voll, komplette pytest-Suite (mock, `-n 4`), Coverage, Playwright (Doku und Werkbank) | etwa 15 Min | `scripts/ci.py t2` |
| T3 | Tag `v*`, manuell (`ci-release.yml`) | T2 plus `timing`-Tests seriell, Perf-Gate gegen `perf/baseline.json`, Versions-Konsistenz, `build-release.py`-Trockenlauf | 30 bis 60 Min | `scripts/ci.py t3` |
| Nightly | täglich 02:30 Europe/Berlin (`ci-nightly.yml`) | Security voll, volle Suite, Perf-Trend, Hardware-Tests im real-Modus nur wenn ein Gerät da ist | 20 bis 40 Min | `scripts/ci.py nightly` |

Hinweise zur Aufteilung in der CI:

* In `ci-voll.yml` und `ci-release.yml` laufen pytest und Playwright als getrennte Jobs
  (`--only lint,security,pytest` bzw. `--only playwright`), wegen der 20-Minuten-Grenze und
  des einzelnen Pi-Runners. Beim Release läuft Playwright erst nach dem ersten Job, damit der
  Perf-Gate keine fremde Last sieht.
* Für PRs gegen master/main führt `playwright.yml` die Playwright-Tests bereits aus. Der
  Playwright-Job in `ci-voll.yml` läuft deshalb nur manuell oder bei Label `full-ci` auf PRs
  gegen andere Branches (keine Doppelarbeit auf dem einen Runner).
* Jeder Job schreibt eine Zusammenfassung (`scripts/ci-summary.py`) in den Step-Summary und
  lädt `reports/` als Artefakt (JUnit, Coverage, `ci-*.log`, `perf-summary.md`).
* Lokal prüfen, was eine Stufe täte, ohne es auszuführen: `scripts/ci.py <stufe> --dry-run`.

## Fehlerklassen aus ci.py

### ruff {#ruff}

* Symptom: `FEHLER ruff ...`, Zeilen wie `E501` oder `F401` mit `datei:zeile`.
* Ursache: Stil- oder Importregel verletzt (Regel-ID steht vor der Meldung).
* Fix: `./.venv/bin/ruff check --fix <datei>` für behebbare Regeln, sonst Stelle anpassen.
  T2 und höher prüfen `src tests scripts packaging examples` komplett.

### gitleaks {#gitleaks}

* Symptom: `FEHLER gitleaks ...`; die Ausgabe nennt Regel und `datei:zeile`, der Inhalt
  ist absichtlich geschwärzt (`--redact`).
* Ursache: mögliches Geheimnis im Diff (T0 staged, T1 `<basis>..HEAD`) oder in der gesamten
  Historie (T2 und höher).
* Fix: Echtes Geheimnis entfernen **und rotieren**; ein Löschen im neuesten Commit genügt
  nicht, weil die Historie gescannt wird. Fehlalarm: begründet in `.gitleaks.toml` freigeben,
  nicht stillschweigend. Siehe `docs/security-scan.md` (Paket B), sofern vorhanden.
* Hinweis: Fehlt `.gitleaks.toml`, nutzt gitleaks Standardregeln.

### bandit {#bandit}

* Symptom: `FEHLER bandit ...` mit Test-ID wie `B602` und `datei:zeile`.
* Ursache: neuer Fund ab Schwelle medium (`-ll`), der nicht in `.bandit-baseline.json` steht.
* Fix: Code absichern (z. B. `subprocess` ohne `shell=True`, feste Argumentliste) oder
  begründet mit `# nosec B602` markieren. Bestandsfunde stehen in der Baseline; bandit lebt in
  `.venv-tools`, nicht in `.venv`.

### changelog {#changelog}

* Symptom: `FEHLER CHANGELOG-Regel: src/... (+N weitere) geändert, CHANGELOG.md nicht`.
* Ursache: Änderung unter `src/`, `examples/`, `scripts/`, `systemd/` oder `udev/` ohne
  CHANGELOG-Eintrag (Regel aus AGENTS.md). Ausgenommen ist `src/dispread/workbench/static/vendor/`.
* Fix: Eintrag unter "## Unveröffentlicht" in `CHANGELOG.md` ergänzen, im selben Commit.

### pytest {#pytest}

* Symptom: `FEHLER pytest ...`, darunter "rot: tests/test_x.py::test_y" je rotem Test;
  Kurztraceback im Step-Summary und in `reports/junit-*.xml`.
* Ursache: mindestens ein Test ist rot, oder die pytest-Konfiguration ist ungültig (Exit 2 oder 4).
* Fix: Test einzeln nachstellen: `./.venv/bin/python -m pytest tests/test_x.py::test_y -x`.
  Bei Exit 2 oder 4 die Konfiguration prüfen (siehe "Unbekannter Marker" unten).
  Alle Tests der Stufe: den Befehl aus "Zum lokalen Nachstellen" verwenden.

### playwright {#playwright}

* Symptom: `FEHLER Playwright ...` oder `Doku bauen`; Berichte unter `playwright-report*/`,
  `test-results*/` im Artefakt.
* Ursache: Browser-Test der Doku oder der Werkbank-Oberfläche rot, Browser fehlt oder der
  Doku-Build scheiterte (`.venv-docs` fehlt).
* Fix: `npm ci`, `npx playwright install --only-shell chromium`, `.venv-docs` anlegen
  (siehe `playwright.yml`), dann den Einzelschritt aus der Fehlerausgabe wiederholen. Die
  Werkbank-Tests brauchen `.venv` mit `--system-site-packages` (aiohttp, OpenCV, NumPy aus dem System).
  Auf dem Runner ist `PLAYWRIGHT_BROWSERS_PATH=/var/lib/forgejo-runner/playwright-browsers` gesetzt.

### release {#release}

* Symptom: `FEHLER Versions-Konsistenz` oder `build-release.py Trockenlauf`.
* Ursache: `VERSION`, oberste `## x.y.z`-Zeile in `CHANGELOG.md` und Tag `vX.Y.Z`
  widersprechen sich, oder `PICAM_RELEASE_TEMPLATES` zeigt auf eine fehlende Datei.
  `package.json` weicht nur mit Warnung ab.
* Die eingefrorene Lesevorlage ist nicht im Repo (`var/` ist ignoriert). `ci.py` sucht sie unter
  `var/dotmatrix/templates-stufe2c-2026-09-30.json` oder unter dem Pfad aus `PICAM_RELEASE_TEMPLATES`.
  Ohne beides wird der Build-Trockenlauf **übersprungen** und als "NICHT geprüft" gemeldet; gesetzt, aber
  fehlend ist ein Fehler. Auf dem Runner gibt es die Datei nicht (kein Zugriff auf `/home`), der Release-Build
  wird dort also nicht geprüft, bis eine Kopie unter `/var/lib/forgejo-runner/` liegt.
* Fix: Versionsstände angleichen, den Tag neu setzen, Vorlagendatei bereitstellen. Den Build lokal prüfen:
  `scripts/ci.py t3 --only release`.

### Grenzen des Forgejo-Runners {#runner-grenzen}

Der Dienst `forgejo-runner.service` ist bewusst abgeschottet (Pi ist ein Messgerät). Daraus folgt:

| Grenze | Folge | Umgang |
|---|---|---|
| `CPUQuota=200%`, `MemoryMax=2G` | `-n 4` überlastet 2 Kerne und kann am Speicher scheitern | Workflows setzen `PICAM_CI_WORKERS=2` |
| `Nice=19`, `CPUWeight=10`, IO idle | Latenzen nicht mit der Baseline vergleichbar | Workflows setzen `PICAM_PERF_GATE=skip`; Perf-Gate vor dem Tag am freien Gerät: `scripts/ci.py t3 --only perf` |
| `PrivateDevices=true` | keine Kamera, kein UART | Hardware-Tests werden übersprungen (nur am Gerät mit `--mode=real`) |
| `ProtectHome=true`, Schreibrecht nur `/var/lib/forgejo-runner` | kein Zugriff auf Lesevorlage und `/home`; Werkzeuge landen im Runner-Home | `install-security-tools.sh` installiert pro Lauf nutzerlokal; Vorlage per `PICAM_RELEASE_TEMPLATES` |
| `capacity: 1`, `timeout: 1h`, kein Cache | Jobs laufen nacheinander; jeder Job installiert neu | Job-Timeouts unter 1 h halten |

Übersprungene Prüfungen stehen im Lauf als "NICHT geprüft" und werden nicht als grün gezählt.

### perf {#perf}

* Symptom: `FEHLER Perf-Gate`; Tabelle in `reports/perf-summary.md`. `perf/baseline.json` fehlt
  oder `scripts/perf-report.py` fehlt (dann "uebersprungen - Perf-Gate NICHT geprueft").
* Ursache: p95-Latenz oder Durchsatz außerhalb der Toleranz, Lauf ungültig (Exit 3, siehe unten)
  oder Baseline stammt von einem anderen Runner (Exit 2).
* Fix: `./.venv/bin/python scripts/perf-report.py` einzeln wiederholen; die Ausgabe nennt die
  Stufe mit dem größten Zuwachs. Baseline nur auf dem Pi-5-Runner mit `--update-baseline`
  erneuern, und nur nach Ursachenklärung. Details: `perf/README.md`.

### hardware {#hardware}

* Symptom: `FEHLER Hardware-Tests (real)` im Nightly.
* Ursache: Kamera oder UART antwortet nicht. Ohne Gerät (`/dev/video0`, `/dev/ttyAMA0`,
  `/dev/ttyUSB0`) wird der Schritt übersprungen, nicht rot.
* Fix: `scripts/camera-commissioning.sh` ausführen (Exit 0 = einsatzbereit); USB3-Port, belegte
  Kamera (nur ein Prozess) und Port-Konfiguration prüfen.

### Werkzeug fehlt {#werkzeug-fehlt}

* Symptom: `FEHLER ...: gitleaks nicht gefunden`, `bandit nicht gefunden` oder
  `node_modules/.bin/playwright fehlt (npm ci)`. In T0 und T1 ist das nur ein Hinweis, ab T2 ein Fehler.
* Ursache: Pflichtwerkzeug nicht installiert (nutzerlokal, nicht Teil des Repos).
* Fix: `scripts/install-security-tools.sh` (gitleaks nach `~/.local/bin`, bandit nach
  `.venv-tools`), `npm ci` für Playwright; Dev-Plugins laut `docs/dependencies.md`
  (Abschnitt Dev-Werkzeuge). Auf dem Runner stehen diese Schritte in den Workflows.

## Weitere Symptome

### Timing-Test unter xdist übersprungen {#timing-xdist}

* Symptom: Skip-Grund "Laufzeitmessung nur ohne -n: pytest -m timing".
* Ursache: `tests/conftest.py` überspringt `timing`-Tests in xdist-Arbeitern, weil parallele
  Last Wanduhrmessungen verfälscht.
* Fix: kein Fehler. Getrennt und seriell ausführen: `./.venv/bin/python -m pytest -q -m timing`.
  T3 und Nightly tun das (Schritt "pytest timing (seriell)"); T2 nicht.

### Throttling oder ungültiger Perf-Lauf {#perf-ungueltig}

* Symptom: Perf-Exit 3, "Lauf ungültig", Drosselbits, SoC-Temperatur oder fremde CPU-Last.
* Ursache: Pi drosselt (Kühlung, Netzteil) oder ein anderer Prozess belastet den Runner,
  etwa ein paralleler Job. Das ist keine Regression.
* Fix: Last und Kühlung prüfen (`vcgencmd get_throttled`), Lauf wiederholen. Baseline nicht anpassen.

### Fehlendes Systempaket, ABI-Regel {#systempaket}

* Symptom: `ModuleNotFoundError: cv2`/`numpy`/`serial`/`aiohttp` oder ein ABI-/ImportError aus NumPy.
* Ursache: `.venv` ohne `--system-site-packages` angelegt, oder per pip ein eigenes `numpy`
  installiert, das neben dem gegen System-NumPy gebauten `cv2` einen ABI-Bruch erzeugt
  (`pyproject.toml`, `docs/dependencies.md`).
* Fix: `rm -rf .venv && python3 -m venv --system-site-packages .venv`, nur die Dev-Werkzeuge
  installieren (`pip install pytest pytest-xdist execnet pytest-timeout pytest-cov coverage ruff`),
  `numpy` und `opencv` nicht per pip. Fehlende Systempakete per apt am Host, nicht im Job.

### Mapping-Lücke und T2-Eskalation {#mapping-luecke}

* Symptom: "Stufe T1 -> eskaliert auf T2" mit "voll, weil ..." in der Testauswahl; bei einer
  neuen Quelldatei ohne passenden Test.
* Ursache: Kernpfad berührt (`pipeline.py`, `rectify*`, `ocr/`, `validate.py`, `records.py`,
  `live/`, `pyproject.toml`, `tests/conftest.py`, `packaging/`, `scripts/ci*`), mehr als 25 Dateien oder
  mehr als 3 Bereiche, oder die Datei hat keine Zuordnung (sicher statt still unvollständig).
* Fix: kein Fehler, nur länger. Bei Lücke Eintrag in `scripts/test-map.toml` ergänzen oder einen
  Test nach Namenskonvention anlegen; `tests/test_ci_tiers.py` prüft das Mapping.
  Entscheidung ansehen: `scripts/test-select.py`. Ausnahmsweise `--no-escalate` (nur lokal).

### Unbekannter Marker (`--strict-markers`) {#strict-markers}

* Symptom: `'xyz' not found in markers configuration option`, pytest Exit 2 oder 4, null Tests.
* Ursache: Marker nicht in `pyproject.toml` registriert, oder unbekannte Option (`--strict-config`),
  z. B. `timeout` in der Konfiguration ohne `pytest-timeout`.
* Fix: Marker unter `[tool.pytest.ini_options] markers` eintragen (registriert sind
  `hardware, serial, slow, timing, perf`) oder Tippfehler beheben. Plugin-Optionen gehören
  nicht in `addopts`; `ci.py` übergibt `--timeout` und `--cov` selbst.

### Timeout {#timeout}

* Symptom: `Failed: Timeout >300.0s` (T1/T2, 600 s in T3/Nightly) bei einem Test, oder
  "The job running on runner ... has exceeded the maximum execution time" beim Job.
* Ursache: hängender Test (Kamera, Port, Warteschleife) oder überlasteter Runner; Job-Limits
  stehen als `timeout-minutes` in den Workflows. Fehlt `pytest-timeout`, gibt es nur den Job-Timeout.
* Fix: Test einzeln mit `-x --timeout 60` nachstellen. Ein Dauerläufer gehört mit `slow` markiert.
  Laufende Parallelarbeit auf dem Runner prüfen. Limits nur mit Begründung erhöhen.
