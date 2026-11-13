# Spec-Entwurf: One-Line-Installer und Verwaltungs-TUI

**Status:** erster Entwurf vom 2026-11-13 (Claude, autonomer Plan Punkt 5). Grundlage ist
Leonhards Beschreibung vom 13.11.:

> One line installer. TUI/CLI, die den Nutzer visuell durch das Setup des picam-Projekts im
> Terminal führt und von der aus man auch Status, Logs usw. sehen kann, sowie die Werkbank
> starten, stoppen, konfigurieren, troubleshooten, updaten usw.

Dazu kommt sein Wunsch nach einer aufgeräumten Codebase und einem Setup, das auf anderen
Raspberries reibungslos läuft. Getestet wird später auf einem zweiten Pi. Gestaltung nach dem
Skill `terminal:tui-design`. Nichts davon ist umgesetzt; offene Entscheidungen stehen in
Abschnitt 9.

## 1. Bestandsaufnahme (Stand `feat/integration`, 13.11.)

**Was es gibt:**

- `scripts/install-workbench.sh`:
  - installiert per apt `python3-aiohttp python3-textual python3-pam python3-cryptography python3-zeroconf openssl`
  - legt `.venv` mit `--system-site-packages` an und führt `pip install --no-deps -e .` aus
  - gibt danach `dispread init-tls && dispread serve` als nächsten Schritt aus
- `pyproject.toml`: `dependencies = []` (absichtlich, alles kommt aus apt), Python ≥ 3.13,
  Einstieg `dispread = dispread.workbench.cli:main`.
- CLI `dispread`:
  - `serve`, `stop`, `status`
  - `live status|setup|stop|camera|mark|aufraeumen`
  - `init-tls`
  - `bridge identity|export-profile|revoke|status|prepare-uart|stop-uart`
  - `tui`: eine Textual-Bedienung für die alte Einrichtungsmaske, kein Installer
- Diagnose: `scripts/camera-commissioning.sh` (Exit 0 = Kamera einsatzbereit).
- Kalibrierung: `scripts/display-offset.py` → `scripts/timing-calibration.py` →
  `var/calibration/timing-streamcam.json`.

**Was fehlt oder stört auf einem frischen Pi:**

| # | Lücke | Beleg |
| --- | --- | --- |
| L1 | apt-Liste unvollständig: `python3-numpy`, `python3-opencv`, `python3-serial`, `v4l-utils` fehlen im Skript | `install-workbench.sh`; `uvc_source.py:114,132` ruft `v4l2-ctl` |
| L2 | Kein Werkbank-Dienst im Repo. Er läuft als `systemd-run --user`, der Befehl steht nur im Agenten-Gedächtnis; `loginctl enable-linger` ist nicht dokumentiert | `systemd/` enthält nur CI- und Wiki-Units |
| L3 | Pi-Konfiguration nur beschrieben: `dtparam=uart0=on`, serielle Konsole aus, Gruppen `dialout` und `video` | `HARDWARE_PROFILE.md` |
| L4 | `var/` ist nicht versioniert. Die Pflichtvorlage `var/dotmatrix/templates-stufe2c-2026-09-30.json` (SHA-geprüft, nicht auf dem Pi erzeugbar) fehlt auf einem frischen Pi | `live/__init__.py:12-13` |
| L5 | Timing-Kalibrierung ist Pflicht beim Laufstart und hängt vom Aufbau ab. Ob ein neuer Pi die Datei des alten übernehmen darf, ist offen | `live/__init__.py:15` |
| L6 | Pfade relativ zum Arbeitsverzeichnis (`var/...` in `cli.py`, `live/__init__.py`). Daneben gibt es eine zweite Pfadwelt in `paths.py` (`DISPREAD_ROOT`, `/etc/dispread`, `/var/lib/dispread`) | `cli.py:135-190`, `paths.py:20-43` |
| L7 | Mehrfach definierte Werte: Standardport `serve` 8080, im Betrieb 8081/8082; `var/workbench` fünfmal in `cli.py`; `/dev/ttyAMA0` in vier Python-Dateien und im JS; 115 200 Baud für UART direkt an vier Stellen | Single-Source-Regel |
| L8 | TLS: `init-tls` hat als Standardhost `127.0.0.1` (die Doku sagt „interne IP“); Zertifikat 365 Tage, keine Erneuerung, keine Anzeige der Laufzeit | `cli.py:30-65` |
| L9 | Reihenfolge für eine Neuinstallation (Identität → TLS → Dienst → Profil exportieren) ist nirgends als Ablauf beschrieben | — |
| L10 | Fest eingetragen in Skripten: `/home/me-systeme/picam-ai/.venv` (`camera-commissioning.sh:174`), Benutzer `me-systeme` (Wiki-Export), Login-Seite „me-systeme“ (`static/login.html:3`) | grep |
| L11 | Kein Update-Weg außer `git pull` von Hand; die Version steht in `VERSION` | — |

Die Produktdaten in `src/` sind frei von festen IPs, Home-Pfaden und SSD
(Wächtertest `test_no_dev_data_in_src.py`). Die Altlasten liegen in Skripten, Diensten und
der Pfadwahl.

## 2. Zielbild

```text
curl -fsSL https://<ort>/picam/install.sh | bash
```

1. **Bootstrap** (`install.sh`, Bash, ein Durchlauf, inline, ohne TUI):
   - prüft Pi und Betriebssystem
   - installiert die apt-Pakete
   - holt den Code in ein festes Installationsverzeichnis und legt die venv an
   - startet danach `picam setup`

   Das Skript ist idempotent: Ein zweiter Aufruf repariert bzw. aktualisiert. Ausgabe als
   lesbare Zeilen mit `✓`/`✗` und am Ende ein einzeiliger Beleg.
2. **`picam`** (Python, Textual) ist das Verwaltungswerkzeug mit zwei Gesichtern:
   - `picam` ohne Argument öffnet die **Konsole** (Vollbild-TUI): Status, Logs, Aktionen.
   - `picam setup` führt Schritt für Schritt durch die Einrichtung (Vollbild, Assistent).
   - Jede Aktion gibt es zusätzlich als **Einzelbefehl** für Skripte, SSH und
     Barrierefreiheit: `picam status [--json]`, `picam logs [-f]`, `picam start|stop|restart`,
     `picam doctor [--json]`, `picam update [--check]`, `picam pair`, `picam config get|set`.
     Diese Befehle haben stabiles stdout, Diagnosen auf stderr und Exit-Codes
     (0 OK, 1 Fehler, 2 Warnung bei `doctor`).

`dispread` bleibt der Produktbefehl (Dienst, Laufsteuerung). `picam` ist nur die
Verwaltungsschicht und ruft `dispread`, `systemctl` und `journalctl` auf. Es verändert nichts
am Messpfad. Den Namen `picam` muss Leonhard bestätigen (Abschnitt 9).

**Technik:**

- Textual ist schon im Projekt (`python3-textual` 2.1.2 aus Debian, `dispread tui`). Damit
  kommt keine neue Abhängigkeit hinzu, und die Lage passt zur apt-Regel aus `AGENTS.md`.
- Debian liefert Textual 2.x, nicht die aktuelle 8.x. Die Umsetzung muss gegen 2.1.2
  geprüft werden, etwa bei `Binding`, `@work` und `run_test`.
- Einzelbefehle mit `argparse` wie `dispread`; Rich für die Tabellen im Klartextmodus
  (Teil von Textual).

## 3. Eine Quelle für die Konfiguration

Vor jeder TUI-Arbeit kommt die Aufräumung (L6/L7). Sonst schreibt der Installer eine weitere
Kopie der Werte.

- **Eine Datei** `config.toml` im Datenverzeichnis, z. B. `<DATA>/config.toml`.
  - Inhalt: Adresse, Port, Datenverzeichnisse, Brückenname, Discovery, PAM-Benutzer,
    Standard-UART-Port und Baudrate für UART direkt.
  - Lesen: `tomllib`, Standardbibliothek.
  - Schreiben: nur `picam config set` mit Prüfung.
- **`dispread serve --config <datei>`** liest sie. Die Befehlszeilenoptionen bleiben als
  Überschreibung erhalten, die Standardwerte stehen danach nur noch im Code der
  Config-Klasse.
- **Ein Pfadmodell:** `paths.py` wird die einzige Quelle. `cli.py` und `live/__init__.py`
  leiten `var/...` daraus ab statt aus dem Arbeitsverzeichnis. Der Dienst setzt
  `DISPREAD_ROOT` (Code) und `DISPREAD_VAR` (Daten).
- **Werte im Frontend** (Port, Baud) sollen vom Server kommen, etwa als Standardwerte in
  `/live/status` (ob das schon teilweise so ist, bei P0 prüfen). Die Kopien in `output.js`
  und `scenario.js` entfallen bzw. werden zu Testdaten.

Ergebnis: Der Dienst braucht nur `dispread serve --config …`. Die Unit ist eine Vorlage
ohne Werte von diesem Pi.

## 4. Installationsort und Dienst

| Frage | Vorschlag | Alternative |
| --- | --- | --- |
| Code | `/opt/picam/<version>/` mit Symlink `/opt/picam/current` | `~/picam-ai` (heute); einfacher, aber Update und Rollback sind unsauber |
| Daten | `/var/lib/picam/` (= `DISPREAD_VAR`), auf der SD-Karte | `~/picam-ai/var` |
| Benutzer | eigener Systembenutzer `picam` in `dialout`, `video` | Installationsbenutzer (heute) |
| Dienst | System-Unit `picam-werkbank.service` mit `User=picam` | User-Unit mit `loginctl enable-linger` (heute ohne Linger) |
| Anmeldung Werkbank | PAM gegen einen festgelegten Bedienerbenutzer (`config.toml`) | PAM gegen den Dienstbenutzer (heute) |

Der Vorschlag trennt Code und Daten. Damit ist ein Update ein Umschalten des Symlinks und
der Rückweg ein Zurückschalten. Der Systemdienst startet ohne Anmeldung und nach dem Neustart.

**Migration dieses Pi:** `picam setup --adopt ~/picam-ai/var` übernimmt Identität, Kopplungen,
TLS und Läufe. Erst nach Leonhards OK und ohne aktiven Lauf.

## 5. Einrichtungsassistent `picam setup`

**Form:** Drill-down mit einem Schritt je Bildschirm. Links steht eine schmale Schrittliste
als Fortschritt, rechts der aktuelle Schritt. Jeder Schritt prüft zuerst, zeigt dann das
Ergebnis und fragt nur, was sich nicht ableiten lässt. Erledigte Schritte bleiben grün und
werden beim nächsten Aufruf nur geprüft, nicht wiederholt.

| Schritt | Prüft / tut | Fragt |
| --- | --- | --- |
| 1 System | Pi-Modell, OS, Python ≥ 3.13, freier Platz auf der SD, Uhrzeit synchron | — |
| 2 Pakete | apt-Liste (L1); fehlende installieren | Bestätigung (sudo) |
| 3 Kamera | USB-ID `046d:0893`, USB3-Port, YUYV 1920×1080 (Logik aus `camera-commissioning.sh` als Python-Modul) | — |
| 4 UART | `dtparam=uart0=on`, keine serielle Konsole, `/dev/ttyAMA0` vorhanden, Gruppe `dialout` | Änderung an `config.txt`/`cmdline.txt` nur nach ausdrücklicher Bestätigung; **Neustart nie automatisch**, sondern „Neustart nötig – jetzt / später“ |
| 5 Daten | Vorlage vorhanden und SHA stimmt (L4); Kalibrierung vorhanden (L5) | Kalibrierung: übernehmen (Datei wählen) / messen (Anleitung) / später (Laufstart bleibt gesperrt, sichtbar) |
| 6 Netzwerk | Adressen der Schnittstellen (LAN, WLAN, Tailscale) | Adresse und Port wählen |
| 7 TLS | Zertifikat mit genau dieser Adresse im SAN, Laufzeit (L8) | neu erzeugen, wenn die Adresse wechselt |
| 8 Brücke | Identität anlegen (`bridge identity --provision`) | Name des Pi |
| 9 Anmeldung | PAM-Benutzer existiert und hat ein Passwort | Benutzer wählen |
| 10 Dienst | Unit schreiben, aktivieren, starten, auf `https://<adresse>:<port>/live` warten | — |
| 11 Fertig | Zusammenfassung, URL, nächster Schritt „Windows koppeln: `picam pair`“ | — |

**Sicherheitsregeln:**

- Jeder Schritt, der etwas außerhalb des Installationsverzeichnisses ändert (apt,
  `config.txt`, systemd, Benutzer), zeigt vorher den genauen Befehl. Er läuft erst nach
  Bestätigung.
- `--yes` gilt nur für den Einzelbefehl-Modus.
- Kein Neustart, kein Kernel-Eingriff ohne Rückfrage.

**Skizze bei 80×24:**

```text
 picam setup                                                 Schritt 4 von 11
 ✓ System        UART für GSVmulti
 ✓ Pakete
 ✓ Kamera        /dev/ttyAMA0          fehlt
 › UART          dtparam=uart0=on      fehlt in /boot/firmware/config.txt
   Daten         serielle Konsole      aus
   Netzwerk      Gruppe dialout        ja
   TLS
   Brücke        Vorschlag: Zeile ergänzen
   Anmeldung       echo 'dtparam=uart0=on' | sudo tee -a /boot/firmware/config.txt
   Dienst        Danach ist ein Neustart nötig.
   Fertig
                 [Ändern]  [Überspringen]

 enter ausführen  tab weiter  esc zurück  ? hilfe  ctrl+q beenden
```

## 6. Konsole `picam`

**Form:** Dashboard mit festen Plätzen. Oben steht eine Statuszeile, darunter Status und Log.
Die Aktionen liegen auf Tasten und stehen in der Fußzeile.

**Statuszeile:** `Werkbank läuft · v0.1.0.dev0 (95d0540) · seit 19:35 · https://100.122.154.35:8082`

**Statusbereich** (je Zeile ein Wort plus Farbe, keine weiteren Marker):

| Zeile | Quelle |
| --- | --- |
| Dienst | `systemctl show` |
| Lauf | `dispread live status` (Sitzung, Lauf aktiv?, seit) |
| Kamera | `dispread live camera` / Commissioning-Kurzprüfung |
| Ausgabe | Weg, Zustand, letzter Takt (`unified_output_status`) |
| Brücke | `bridge status` (verbunden, Kopplungen je Weg, UART-Empfang) |
| TLS | Ablaufdatum, Warnung unter 30 Tagen |
| Speicher | SD frei, Größe `var/live`, Vorschlag `live aufraeumen` |
| Version | installiert, verfügbar (nach `update --check`) |

**Logbereich:** `journalctl -u <unit> -f` in einem Worker, nach Stufe filterbar
(`f`), Zeit nur als Uhrzeit, Volltext per `enter`.

**Tasten:**

| Taste | Aktion | Sperre |
| --- | --- | --- |
| `s` | starten / stoppen | Stoppen bei aktivem Lauf nur nach Rückfrage mit Laufname |
| `r` | neu starten | wie Stoppen; wartet auf die Diagnosekopie aus `/dev/shm` |
| `l` | Log vergrößern | — |
| `c` | Konfiguration (Formular aus `config.toml`, Prüfung, Neustart-Hinweis) | — |
| `d` | Diagnose (`doctor`): Prüfliste mit OK/WARNUNG/FEHLER und Abhilfe; Diagnosepaket als ZIP | — |
| `u` | Update (Abschnitt 7) | bei aktivem Lauf gesperrt |
| `p` | Windows koppeln: Kopplungscode bzw. Profil exportieren, Weg wählen | — |
| `?` | Hilfe | — |
| `ctrl+q` / `ctrl+c` | beenden | — |

**Breakpoints:**

- **ab 120 Spalten:** Status links (40 Spalten), Log rechts.
- **80–119:** Status oben (8 Zeilen), Log darunter.
- **60–79:** nur ein Bereich, mit `tab` zwischen Status und Log umschalten.
- **unter 60×16:** Meldung „Terminal zu klein: mindestens 60×16“.

**Skizze bei 80×24:**

```text
 Werkbank läuft · 95d0540 · seit 19:35 · https://100.122.154.35:8082
 Dienst    läuft           Kamera   bereit (USB3, 1920×1080)
 Lauf      keiner          Ausgabe  aus
 Brücke    1 Gerät, Netz   TLS      gültig bis 2027-11-06
 Speicher  21 GB frei      Version  aktuell
 ─ Log ─────────────────────────────────────────────────────────────────────
 19:35:02  Werkbank gestartet auf 100.122.154.35:8082
 19:35:03  Kamera geöffnet: 1920×1080 YUYV
 19:41:17  Brücke verbunden (Netzwerk, Windows-PC-1)


 s stop  r neustart  c konfig  d diagnose  u update  p koppeln  ? hilfe
```

**Clutter-Prüfung:**

- Rahmen: nur eine Trennlinie über dem Log, kein Außenrahmen.
- Status: einmal Farbe plus einmal Wort.
- Kein Marker auf jeder Zeile.
- Zeitstempel ohne Datum.

## 7. Update und Rückweg

- **Quelle:** Git-Tags bzw. Releases auf Forgejo. `picam update --check` zeigt die
  verfügbare Version und die CHANGELOG-Einträge seit der installierten.
- **Ablauf:**
  1. Neue Version nach `/opt/picam/<neu>` holen.
  2. venv anlegen.
  3. Selbsttest (neu zu bauen, z. B. `python -m dispread.selftest`: Importe, Vorlage, Konfiguration lesbar, ein
     synthetischer Durchlauf ohne Hardware).
  4. Nur bei Erfolg Symlink umschalten und Dienst neu starten.
  5. Auf `/live` warten.
- **Rückweg:** `picam update --rollback` schaltet auf die vorige Version zurück. Die Daten
  bleiben unberührt. Ändert eine neue Version das Datenformat, sagt sie das im Selbsttest
  und verlangt eine Bestätigung.
- **Sperren:** kein Update bei aktivem Lauf; nicht während einer Diagnosekopie.

## 8. Umsetzung in Stufen

| Stufe | Inhalt | Wer | Testbar auf diesem Pi |
| --- | --- | --- | --- |
| P0 Aufräumen | `config.toml` + `serve --config`, ein Pfadmodell, Duplikate L7, `init-tls --host` Pflicht, `camera-commissioning.sh` ohne festen Pfad, apt-Liste L1 | Codex (Backend) | ja |
| P1 Lieferung | Vorlage(n) als versionierte Paketdaten statt `var/` (L4), Unit-Vorlage, `install.sh` | Codex | teilweise (Container/zweite venv) |
| P2 Einzelbefehle | `picam status/logs/start/stop/doctor/config` mit `--json` und Exit-Codes | Codex | ja |
| P3 Konsole | Textual-Dashboard aus Abschnitt 6, Snapshot-Tests 120×40, 80×24, 60×20 | Claude (UI) | ja, gegen den laufenden Dienst |
| P4 Assistent | `picam setup` aus Abschnitt 5 | Claude (UI), Prüfschritte Codex | nur auf frischem Pi vollständig |
| P5 Update | Abschnitt 7 | Codex | ja, mit zwei Versionen |
| P6 Zweiter Pi | frisches Raspberry Pi OS, One-Liner, Assistent, erster Lauf | Leonhard + Claude | — |

Tests: State und Prüfschritte ohne Terminal (pytest). Textual mit `run_test` und
Snapshots in den drei Größen. Ein PTY-Durchlauf für Start und Beenden. `NO_COLOR` und
`--json` als eigene Tests.

## 9. Offene Entscheidungen (Leonhard)

1. **Bezugsquelle für den One-Liner:** Das Forgejo-Repo ist privat. Möglich sind ein
   öffentlicher Release-Download (nur Bootstrap und Paket), ein Token im Befehl oder die
   Installation per USB-Stick. Davon hängt die Form des One-Liners ab.
2. **Name:** `picam` als Verwaltungsbefehl neben `dispread`? Oder alles unter `dispread`
   (`dispread admin …`)?
3. **Ort und Dienst:** `/opt/picam` + `/var/lib/picam` + Systembenutzer (Vorschlag) oder
   weiter im Home-Verzeichnis mit User-Unit?
4. **Kalibrierung auf einem neuen Pi:** Darf eine Kalibrierdatei übernommen werden, wenn
   Kamera und Aufbau gleich sind, oder ist die Messung je Pi Pflicht? Davon hängt Schritt 5
   ab.
5. **Tailscale:** Gehört es zum Installer oder ist es Sache der IT?
6. **Bestehende `dispread tui`:** Behalten, in `picam` aufgehen lassen oder entfernen? Sie
   bedient die alte Einrichtungsmaske.
