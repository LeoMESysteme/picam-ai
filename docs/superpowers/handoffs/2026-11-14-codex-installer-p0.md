# Handoff an Codex: Installer Stufe P0a — Aufräumen ohne offene Entscheidungen (2026-11-14)

**Auftraggeber:** Leonhard. Er ist bis Mittwoch 18.11. weg und wünscht eine aufgeräumte
Codebase und ein Setup, das auf anderen Raspberries reibungslos läuft („so weit wie möglich
vorantreiben“). **Vorbereitet von:** Claude im autonomen Plan. Codex arbeitet selbstständig,
danach reviewt Claude.

**Grundlage:** [Spec-Entwurf Installer/TUI](../specs/2026-11-13-installer-tui-design.md),
Abschnitte 1 (Lücken L1–L11), 3 und 8. Diese Stufe enthält **nur** Punkte, die nicht von den
offenen Entscheidungen in Abschnitt 9 abhängen: Installationsort, Dienstart, Name,
Bezugsquelle und Kalibrierung bleiben unberührt.

## Rahmen

- **Worktree:** `/home/me-systeme/picam-ai/.worktrees/installer-p0`, Branch
  `feat/installer-p0` (von `feat/integration` 5610bb3). `.venv`, `.venv-docs` und `var` sind
  Symlinks.
- **Tests:**
  - Pi: `PYTHONPATH=src ./.venv/bin/pytest -q <gezielte Dateien>`; volle Suite optional
    (`DISPREAD_DEV_DATA=/mnt/ssd/picam-dev PYTHONPATH=src ./.venv/bin/pytest -q -n 4`), die
    volle Suite läuft Claude.
  - Lint: `PYTHONPATH=src ./.venv/bin/ruff check src tests`
  - Shell: `bash -n`; `shellcheck`, falls installiert
- **Nicht anfassen:**
  - den laufenden Werkbank-Dienst (`.worktrees/bruecke-run`), Kamera, `/dev/ttyAMA0`
  - `var/` schreibend
  - andere Worktrees
  - `apt`/`sudo` ausführen: Das Installationsskript wird nur gebaut und statisch geprüft,
    nicht auf diesem Pi ausgeführt
- **Nur Backend und Skripte.** Keine Oberfläche (JS/HTML/CSS). Wo das Frontend dieselben
  Werte dupliziert (`static/live/run/output.js`, `practice/scenario.js`), nur im Report
  vermerken.
- **Verhalten unverändert:** Standardwerte, Ports, Raten und Pfade behalten ihre heutigen
  Werte. Es geht um eine einzige Quelle, nicht um neue Werte.
- **Commits:** Die Sandbox kann nicht committen. Am Ende `REPORT-codex.md` im
  Worktree-Wurzelverzeichnis schreiben.
- **Verbindlich:** `AGENTS.md` (Doku-Pflicht, apt statt pip, venv-Flags).

## Aufgabe 1: Vollständige Paketliste und robustes `scripts/install-workbench.sh` (L1)

- **apt-Liste** aus dem tatsächlichen Bedarf ableiten. Heute fehlen `python3-numpy`,
  `python3-opencv`, `python3-serial` und `v4l-utils` (`v4l2-ctl` in `frames/uvc_source.py`).
  - `tesseract-ocr` nur aufnehmen, wenn der Live-Pfad es braucht. Sonst als optional
    kennzeichnen und begründen.
  - Die Liste steht an **einer** Stelle, z. B. `packaging/apt-packages.txt` mit Kommentar je
    Paket. Skript und Doku (`docs/dependencies.md`, README) verweisen darauf.
- **Idempotent:** Ein zweiter Lauf ändert nichts und meldet „bereits vorhanden“.
  `set -euo pipefail`, klare Zeilen `✓`/`✗` und Exit-Code ≠ 0 bei Fehler.
- **Prüfen, nicht ändern:** Gruppen `dialout`/`video`, `dtparam=uart0=on`, serielle Konsole.
  Bei Abweichung nennt das Skript den genauen Befehl, führt ihn aber nicht aus
  (Neustart- und Kernelfragen entscheidet der Mensch).
- **Folgeschritte am Ende** in richtiger Reihenfolge (L9): Identität anlegen
  (`dispread bridge identity --provision`), TLS mit der echten Adresse
  (`dispread init-tls --host <adresse>`), Dienst starten (Aufgabe 4), Profil exportieren.
- **Test:** statischer Test in `tests/`, der prüft:
  - die Paketliste ist gültig, und jedes von `src/` importierte Drittmodul ist abgedeckt
    (Abgleich der Importe mit der Liste über eine kleine Zuordnung Modul → Paket)
  - das Skript ist `bash -n`-sauber

## Aufgabe 2: Keine festen Pfade dieses Pi in Produktskripten (L10)

- `scripts/camera-commissioning.sh:174-183`: Python über das Repo-Wurzelverzeichnis des
  Skripts finden (`$(dirname "$0")/../.venv/bin/python`), nicht über `/home/me-systeme/...`.
- Alle weiteren Skripte, die zum Produkt gehören, prüfen: Installation, Kamera, Kalibrierung,
  GSV-Register, Brücke. CI-, Wiki- und Wartungsskripte (`forgejo-*`, `wiki-*`,
  `repo-maintenance*`, `picam-codex-*`) bleiben ausgenommen und kommen in eine Ausnahmeliste.
- **Wächtertest** analog `tests/test_no_dev_data_in_src.py`: Produktskripte und `src/`
  enthalten weder `/home/me-systeme` noch `me-systeme` als Benutzer.
  - Den Login-Text „me-systeme“ in `static/login.html:3` nur melden, nicht ändern, denn das
    ist UI und vielleicht Absicht (Firmenname).

## Aufgabe 3: Eine Quelle für feste Werte (L7)

Werte **unverändert** lassen, aber nur noch an einer Stelle definieren und überall
importieren:

- **UART-Datenport** `/dev/ttyAMA0`: `gsv_transport.py:58,67-68`, `bridge/uart.py:51` und
  weitere Fundstellen. Neues kleines Modul, z. B. `dispread/hardware_ports.py` mit
  `GSV_UART_PORT`, oder vorhandenes passendes Modul.
- **Baudrate „UART direkt“** 115 200: `live/output.py:96`, `sink/serial_out.py:85`,
  `gsv_bridge.py:555`. Nicht verwechseln mit der Brückenrate
  (`bridge/baud.py`: `UART_BAUD`, `LEGACY_UART_BAUD`). Die Namen müssen den Unterschied
  zeigen, z. B. `DIRECT_UART_BAUD`.
- **Datenverzeichnisse** in `workbench/cli.py:135-190` (`var/workbench` fünfmal, `var/live`
  doppelt zu `live/__init__.py:19`, TLS-Pfade dreimal): je eine Konstante. Die Herleitung aus
  dem Arbeitsverzeichnis bleibt **wie heute**. Das Pfadmodell (L6, `paths.py` gegen relative
  Pfade) ist eine offene Entscheidung; nur im Report bewerten, was zu tun wäre.
- **Standardport `serve`** 8080: einmal definieren. Nicht ändern.
- **Test** je Wert: Alle Verwender lesen die Konstante (z. B. Standardargument ist die
  Konstante).

## Aufgabe 4: Dienstbefehl ins Repository (L2)

Der Dienst läuft heute per `systemd-run --user`; der genaue Befehl steht nur im
Agenten-Gedächtnis.

- **`scripts/werkbank-dienst.sh start|stop|restart|status|logs`:**
  - Pflichtangaben: Host und Port. Datenverzeichnisse, Socket, Brückenverzeichnis und Endpunkt
    werden standardmäßig relativ zum Repo-Wurzelverzeichnis abgeleitet; Überschreiben per
    Option.
  - Keine IPs oder Home-Pfade fest im Skript.
  - Die Unit heißt wie heute `dispread-werkbank-bruecke` (überschreibbar).
- **Pflichten:**
  - Socket-Verzeichnis mit Rechten 0700 anlegen.
  - Nach einem Stop mit Zeitüberschreitung `systemctl --user reset-failed`.
  - `stop` und `restart` verweigern, solange ein Lauf aktiv ist. Prüfen über
    `dispread live status --socket …`; mit `--force` überstimmbar, mit deutlicher Warnung.
  - `restart` wartet, bis `https://<host>:<port>/live` antwortet.
  - `loginctl show-user` auf Linger prüfen und nur Hinweis ausgeben.
- **Doku:** Abschnitt in `docs/anleitung/10-kamera-livevorschau.md` bzw. dem passenden
  Betriebskapitel.
- **Test:** `bash -n`; ein Test, der `systemd-run` per Attrappe im `PATH` ersetzt und die
  erzeugte Befehlszeile prüft (`start` mit Host/Port, `stop` bei aktivem Lauf verweigert).
- **Nicht** auf diesem Pi ausführen. Der laufende Dienst bleibt unberührt.

## Aufgabe 5: TLS-Host (L8)

`dispread init-tls` hat als Standardhost `127.0.0.1`; die Doku sagt „interne IP“.

- Ohne `--host` bricht `init-tls` mit klarer Meldung ab („Adresse angeben, unter der Windows
  den Pi erreicht“), statt ein Zertifikat zu erzeugen, das nur lokal passt.
- `dispread init-tls --show` bzw. ein Feld in `status` zeigt die SAN-Adressen und das
  Ablaufdatum des vorhandenen Zertifikats. Grundlage für die spätere Warnung „läuft in
  < 30 Tagen ab“.
- Doku und Tests anpassen.

## Abschluss

- Gezielte Tests grün, ruff sauber, `bash -n` für alle geänderten Skripte.
- CHANGELOG-Eintrag je Aufgabe. Die Lücken L1/L2/L7/L8/L10 im Spec-Entwurf als „P0a
  umgesetzt“ markieren, mit Verweis.
- `docs/status.md` **nicht neu schreiben**: höchstens eine Zeile ergänzen.
- `REPORT-codex.md`:
  - je Aufgabe Dateien, Entscheidungen und Testzahlen
  - Liste der Frontend-Duplikate (für Claude)
  - Bewertung des Pfadmodells (L6) als Entscheidungsvorlage für Leonhard
