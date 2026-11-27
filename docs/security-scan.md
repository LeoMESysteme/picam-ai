# Security-Scan (gitleaks und bandit)

Stand: 2026-11-27. Werkzeuge: gitleaks 8.30.1 (Geheimnisse), bandit 1.8.6 (Python-Schwachstellen).
Einstieg ist `scripts/security-scan.sh`; die Werkzeuge installiert `scripts/install-security-tools.sh`.

## Einrichtung

```bash
scripts/install-security-tools.sh   # idempotent
```

* gitleaks landet in `~/.local/bin/gitleaks` (arm64- bzw. x64-Release von GitHub, SHA256 gegen
  `checksums.txt` geprueft; Version per `GITLEAKS_VERSION` aenderbar).
* bandit landet in einem **eigenen** venv `.venv-tools`, nicht in `.venv`: `.venv` nutzt
  `--system-site-packages` und die ABI-Regel aus `pyproject.toml`.
* Hinweis: `.venv-tools/` steht noch nicht in `.gitignore` (`git status` zeigt es als unversioniert).
  Zeile `/.venv-tools/` bitte dort ergaenzen (liegt ausserhalb dieses Arbeitspakets).

## Benutzung

```bash
scripts/security-scan.sh staged    # Pre-Commit: Staging-Bereich (gitleaks + bandit auf gestagte src/-Dateien)
scripts/security-scan.sh tree      # Arbeitsbaum komplett (T2/Nightly)
scripts/security-scan.sh history   # volle Git-Historie, nur gitleaks (T3 Release)
```

Exit 0 = sauber, 1 = Fund, 2 = Werkzeug fehlt oder Aufruffehler. Die Ausgabe nennt je Fund Regel-ID und
`datei:zeile` plus Fix-Hinweis. gitleaks laeuft immer mit `--redact`: Geheimnisse erscheinen nie im Log.

### Fund beheben oder begruendet freigeben

**gitleaks**

1. Echtes Geheimnis: entfernen (Umgebungsvariable), **sofort rotieren** (auch wenn nie gepusht).
   Ein Fund in der Historie wird durch Rotation entschaerft; Historie nicht umschreiben.
2. Fehlalarm, ganzer Pfad: Eintrag in `.gitleaks.toml` unter `[[allowlists]] paths`, **mit Kommentar
   und Begruendung** (Regex ist am Repo-Wurzelverzeichnis verankert, z. B. `^var/`).
3. Fehlalarm, einzelner Fund (v. a. Historie): Fingerprint aus der Ausgabe in `.gitleaksignore`, Kommentarzeile
   mit Begruendung davor.
4. Einzelne Codezeile: `# gitleaks:allow` in dieselbe Zeile, nur mit Begruendung im Review.

**bandit**

1. Code sicherer machen (`shell=True` vermeiden, `tempfile` statt festem `/tmp`-Pfad, `yaml.safe_load`).
2. Nachweislich unkritisch: `# nosec B<nummer> - <Begruendung>` in der betroffenen Zeile. Immer Test-ID und
   Begruendung, nie ein nacktes `# nosec`.
3. Bewusster Bestand: Baseline neu erzeugen (siehe unten) und die Bewertung in diesem Dokument ergaenzen.

Test-IDs: <https://bandit.readthedocs.io/en/latest/plugins/index.html>

### Baseline pflegen (bandit)

Gate: nur **neue** Funde ab Severity medium (`-ll`) gegenueber `.bandit-baseline.json` brechen.
Low-Funde stehen in der Baseline, brechen aber nie. Neu erzeugen (nur nach Review!):

```bash
.venv-tools/bin/bandit -r src -x '*/tests/*,*/.worktrees/*,*/.venv*,*/node_modules/*' \
    -f json -o .bandit-baseline.json -q
```

Die Baseline gleicht nach Dateiname, Test-ID und Code-Ausschnitt ab, nicht nach Zeilennummer.
Der Aufruf muss `-r src` verwenden (Einzeldateien liefern `./src/...` und passen nicht zu den Namen).
Das Skript beachtet das; im Staged-Modus scannt es `src/` und meldet nur gestagte Dateien.

### Gewuenschte Konfiguration fuer `pyproject.toml` (Paket A)

Das Skript uebergibt alle Optionen selbst und liest `[tool.bandit]` nicht. Damit ein direkter
`bandit`-Aufruf dasselbe tut, bitte ergaenzen:

```toml
[tool.bandit]
exclude_dirs = ["tests", ".worktrees", ".venv", ".venv-docs", ".venv-tools", "node_modules"]
```

Schwelle (`-ll`) und Baseline (`-b .bandit-baseline.json`) sind Kommandozeilenoptionen; bandit kennt
dafuer keinen pyproject-Schluessel. Empfohlener Aufruf in `scripts/ci.py`: `scripts/security-scan.sh staged|tree`.
Optionale ruff-Regeln `S` wuerden denselben Bestand zusaetzlich melden und brauchen eine eigene Bestandsbewertung.

## Erstscan gitleaks (2026-11-27)

Konfiguration: Standardregeln plus Allowlist in `.gitleaks.toml` (jeder Eintrag begruendet).

### Git-Historie (714 Commits, 22 MB)

**3 Funde, alle Fehlalarme**, per Fingerprint in `.gitleaksignore` freigegeben. Echte Funde: **keine**.

| Regel | Pfad:Zeile | Commit | Einschaetzung |
|---|---|---|---|
| generic-api-key | experiments/automatic_seven_segment/results/frozen.json:61 | 6a18bdf3 | False Positive: Hash zu einem Dateinamen (`auth.py`) in Experiment-Ergebnissen |
| generic-api-key | experiments/automatic_seven_segment/results/results.json:106 | 6a18bdf3 | wie oben |
| generic-api-key | src/dispread/workbench/static/vendor/xterm.js:1 | 2ecafab9 | False Positive: minifizierte Fremdbibliothek (Tabelle `FourKeyMap`) |

Ergebnis nach Freigabe: `scripts/security-scan.sh history` Exit 0.

### Arbeitsbaum

Ohne Allowlist: **1634 Funde** (gitleaks `dir` beachtet `.gitignore` nicht). Nach Triage und Allowlist: 0.

| Anzahl | Regel | Pfad | Einschaetzung | Behandlung |
|---|---|---|---|---|
| 1619 | generic-api-key | var/workbench/datasets/samples/*/sample.json:8 | False Positive: `capture_token` ist eine Zufalls-ID je Aufnahme, kein Zugangsdatum; `var/` ist gitignored | Allowlist `^var/` |
| 4 | generic-api-key | var/diagnostics/workbench-outage-20261111/network-journal.txt:31, :88 | False Positive: Journalauszug (Feld `discokey`, Netzwerkdienst-Kennung); gitignored | Allowlist `^var/` |
| 1 | private-key | var/workbench/tls/key.pem:1 | **echter Schluessel, lokal erwartet** (TLS der Werkbank), gitignored, nie im Repo | Allowlist `^var/` |
| 1 | private-key | var/workbench/bridge/identity.json:1 | **echter Schluessel, lokal erwartet** (Bruecken-Identitaet), gitignored | Allowlist `^var/` |
| 1 | private-key | remoteclaude:1 | **echter SSH-Schluessel**, per `.gitignore` Zeile 2 ausgeschlossen, nie in der Historie (Historienscan sauber) | Allowlist `^remoteclaude$` |
| 1 | generic-api-key | sites/picam-ai-cockpit/.env.local:1 | **echtes Geheimnis** (Forgejo-Zugriffstoken), nur lokal; Verzeichnis steht in `.git/info/exclude`, nicht in `.gitignore` | Allowlist, **Rotation empfehlen** falls die Datei je geteilt wurde (Sync, Backup, Screenshot) |
| 2 | generic-api-key | sites/picam-ai-cockpit/dist/server/vinext-server.json:1, .../ssr/vinext-server.json:1 | False Positive: zufaelliger `prerenderSecret` je Build, Build-Ausgabe | Allowlist `^sites/[^/]+/dist/` |
| 2 | generic-api-key | .impeccable/questions/seeds/*.json:1 | False Positive: JSON-Feld `key` mit Fragen-ID | Allowlist `^\.impeccable/` |
| 1 | generic-api-key | .superpowers/sdd/2026-10-23-wiki-geruest/task-9-codex.log:2934 | False Positive: Log mit Code (`FourKeyMap`) | Allowlist `^\.superpowers/` |
| 2 | generic-api-key | src/dispread/workbench/__pycache__/cli.cpython-313.pyc:16 und .worktrees/sensor-p0/.../cli.cpython-313.pyc:16 | False Positive: Bytecode-Konstante (`key.pem`-Dateiname); gitignored | Allowlist `.pyc`, `__pycache__`, `.worktrees` |

**Empfehlungen (nicht von diesem Paket umgesetzt):**

* `sites/picam-ai-cockpit/.env.local` enthaelt ein echtes Token und ist nur lokal per `.git/info/exclude`
  geschuetzt. In einem frischen Klon gaebe es diesen Schutz nicht. Empfehlung: `.env*` (ausser `.env.example`) in
  `.gitignore` aufnehmen und das Token rotieren, falls die Datei ausserhalb dieses Rechners lag.
* `var/` und `remoteclaude` sind per Pfad allowlistet. Ein erzwungenes `git add -f` faengt dann nur der
  Historien-Scan (`security-scan.sh history`, T3), nicht der Staged-Scan. Soll der Pre-Commit auch das fangen, die
  `var/`-Allowlist auf die konkreten Unterpfade einschraenken.
* Schluesselinhalte wurden nirgends ausgegeben; Fundstellen nur als Pfad:Zeile.

## Erstscan bandit (src/, 36 433 Zeilen)

74 Funde: 0 high, 6 medium, 68 low (Stand 2026-11-27, nach Bewertung von B602/B104/B301; vorher 77: 1 high, 9 medium, 67 low). Alle sind in `.bandit-baseline.json` eingefroren, damit das Gate nur
Neues bricht. `scripts/security-scan.sh tree` ist damit gruen. **Die Baseline ist keine Entwarnung**:
die Punkte unter "Separat zu bewerten" gehoeren in den Backlog.

### Separat zu bewerten (nicht stillschweigend akzeptiert)

| ID | Pfad:Zeile | Severity | Bewertung |
|---|---|---|---|
| B602 | src/dispread/admin/cli.py (`run_hint_command`) | HIGH → behoben | Startet Hinweisbefehle jetzt ohne Shell (`shlex.split`). Alle Befehle stammen aus `admin/probes.py` (feste Zeichenketten oder `shlex.join`), Verhalten unverändert; Test: `tests/test_admin_hint_command.py`. |
| B104 | src/dispread/gsv_transport.py:62 | MEDIUM → begründet (`# nosec B104`) | `tcp_host = "0.0.0.0"` ist ein Altfeld der v1-Brücke. Produktiv wird nur `PairedOutputPublisher` benutzt (WSS am HTTPS-Dienst, `docs/BRIDGE_PROTOCOL_V2.md`); der v1-Listener in `OutputPublisher` ist per Demo-/Test-Factory erreichbar, in `src/` gibt es keinen weiteren Aufrufer. Der Standardwert wurde nicht geändert, weil er Teil des serialisierten Konfigurationsformats ist (`tests/test_live_output.py`). **Offen:** Beim Entfernen des v1-Transports `OutputPublisher` samt Feld streichen. |
| B301 | src/dispread/live/region_probe.py:35, live/session.py:239 | MEDIUM → begründet (`# nosec B301`) | `pickle.loads` über stdin/stdout des selbst gestarteten Probenprozesses. Vertretbar, solange der Kanal nie Netz oder Datei wird. **Offen:** Bei Gelegenheit durch JSON/npz ersetzen. |

### Bestand, als vertretbar bewertet

| ID | Pfad:Zeile | Bewertung |
|---|---|---|
| B108 (2x) | bridge/resources.py:34, workbench/cli.py:22 | Festes `/tmp/dispread-<uid>/...` fuer Socket/Ressourcen; Verzeichnis wird mit `mode=0o700` pro UID angelegt. Rest-Risiko: Symlink-Vorab-Anlage durch anderen Nutzer. Gering, Pi ist Einzelnutzer-System. |
| B108 (4x) | calibration/schedule.py:34, live/diagnostics.py:65, live/service.py:226, live/session.py:304 | `/dev/shm` als bewusstes RAM-Staging (Schreibhaenger der SD-Karte, siehe Kommentar im Code), kein Geheimnis. Vertretbar. |

### Massen-Funde (alle low)

| ID | Anzahl | Bewertung |
|---|---|---|
| B404 | 17 | Import von `subprocess`. Reiner Hinweis, kein Befund. |
| B603 | 25 | `subprocess` ohne Shell mit Argumentliste. Unkritisch, solange keine Nutzereingabe in `argv[0]` landet; stichprobenartig mit B607 pruefen. |
| B607 | 6 | Teilpfad (`v4l2-ctl`, `tesseract` o. ae.): admin/cli.py:230, live/tick.py:80, ocr/tesseract_cli.py:51, :112, workbench/cli.py:56, :74. Abhaengig vom `PATH` des Dienstes; vertretbar. |
| B101 | 8 | `assert` in admin/calibrate.py:1079, :1260, :1339, admin/tui.py:978, calibration/record.py:485, :690, records.py:294, validate.py:206. Entfallen bei `python -O`. Bei `records.py`/`validate.py` (Messpfad) lieber explizite Pruefung mit Ausnahme, falls dort Eingaben gesichert werden. |
| B110 | 6 | `try/except/pass`: admin/views/uart_screen.py:482, update_screen.py:132, calibration/record.py:584, gsv_bridge.py:307, :474, live/reference.py:332. Stilles Verschlucken; im Messpfad widerspricht das "Unlesbares markieren", daher bei Gelegenheit mit Logging versehen. |
| B311 | 2 | `random.Random(seed)` in calibration/schedule.py:63 (reproduzierbarer Messplan) und admin/intro.py:111 (Animation). Kein Kryptobedarf, False Positive. |
| B403 | 2 | Import `pickle` (live/region_probe.py:14, live/session.py:214), siehe B301. |
| B606 | 1 | `os.execv` in admin/tui.py:1060: Neustart mit `app.relaunch`, interner Wert. Vertretbar. |

Nicht gefunden: `yaml.load`, `verify=False`, `eval/exec`, schwache Hashes, hartkodierte Passwoerter.

## Pruefnachweis

* Sauberer Baum: `scripts/security-scan.sh tree` und `history` jeweils Exit 0.
* Fake-Secret (GitHub-PAT- und AWS-Muster in einem Scratch-Verzeichnis ausserhalb des Repos): `tree` und `staged`
  schlagen mit Regel-ID, `datei:zeile` und Fix-Hinweis an (Exit 1).
* Neuer `pickle.loads` in einer gestagten Datei: bandit meldet B301 als neu (Exit 1); eine gestagte Bestandsdatei bleibt gruen.
