# Abhängigkeiten

Die aktive Kamera ist seit 2026-09-25 die Logitech StreamCam über UVC
([Hardwareprofil](HARDWARE_PROFILE.md)). `picamera2`, `libcamera` und die
IMX500-Pakete in den Bestandslisten unten stammen vom früheren Aufbau; die
aktuelle Bildquelle `v4l2://` nutzt OpenCV und V4L2. Die Regel für die
Projekt-venv mit Debian-Systempaketen gilt weiterhin.

## Windows-Brücke {#windows-bruecke}

Die neue GSVmulti-Brücke benötigt auf Windows Python **3.13 oder neuer**
und **pySerial 3.5**. Dies ist dieselbe Bibliothek, die auf dem Pi bereits
als Debian-Systempaket vorliegt; es kommt keine neue Python-Bibliothek für
die Linux-Messpipeline hinzu. Die Brücke importiert nur die leichtgewichtigen
Datensatz-/Format-/Transportmodule, keine Kamera-, NumPy- oder OpenCV-Module.

Auf Windows im bereitgestellten Projektverzeichnis eine eigene Umgebung
anlegen und nur Brückenabhängigkeiten installieren:

```powershell
py -3.13 -m venv --system-site-packages .venv
.\.venv\Scripts\python.exe -m pip install --no-deps pyserial==3.5
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe scripts/gsv-bridge.py --help
```

Ein virtueller COM-Treiber ist zusätzlich erforderlich. Das Originalpaket
[com0com3.0.0.0](https://com0com.sourceforge.net/) blieb auf dem Zielrechner
mit Code52 blockiert. Nach angeleitetem Wechsel zur
[Vovsoft-verlinkten com0com-Ausgabe](https://vovsoft.com/blog/how-to-sniff-serial-port-communication/)
meldet der Nutzer am2026-11-04 alle sechs PnP-Geräte ohne Fehler; COM5/COM6
sind vorhanden. Installer-SHA256:
`ae0dd19472f92bab3165d370c3713616a3ffb708fad785684759b04653705a71`.
Bidirektionale Portprobe erfolgreich, aktiver Dateihash passt und SecureBoot/
HVCI bleiben aktiv. Gültige synthetische TCP-Werte und Brückenprozess-
Wiederanlauf in GSVmulti-Dateien belegt; vollständige Abnahme bleibt offen;
keine allgemeine Win11-/HVCI-Kompatibilität behaupten. Der physische FTDI-USB-TTL-Adapter ist
separat als COM4/StatusOK belegt.
[Einrichtung und Abnahmegrenzen](GSVMULTI_PROTOCOL.md#windows-bruecke).

Auf dem Pi gelten unverändert die untenstehenden Regeln: Projekt-`.venv`
mit `--system-site-packages`, Projektinstallation mit `--no-deps` und keine
PyPI-Kopien der Debian-Kamera-/CV-/Serialpakete.

## Windows-EXE: getrennte Buildvorbereitung

Die technische Umsetzung unter `windows/bridge/` verwendet einen eigenen
Windows-Build und bündelt die Laufzeit. Die vorhandene Pi-venv bleibt
unverändert; Qt/PyInstaller werden dort nicht installiert. Kandidaten für
Windows-Laufzeit/Build stehen in den `.in`-Dateien des Windows-Pakets.
Verifizierte, hashgesperrte Locks und tatsächlicher Freeze-Nachweis fehlen,
solange kein entsprechend geprüfter Windows-Build vorliegt. Der Build darf
fehlende oder ungeprüfte Lock-Evidenz nicht als erfolgreich ersetzen.

Device-/VCOM-Adapter werden lokal mit injizierten Betriebssystemantworten
geprüft. Die tatsächliche Windows-PnP-/Treiberinstallation und Freigabe der
Weitergabe sind getrennte Nachweise. Kein neuer Treiber oder Qt-Paket wurde
bei dieser Vorbereitung auf dem Pi installiert. [Spec](superpowers/specs/2026-11-06-windows-bruecke-design.md),
[Nachweisplan](superpowers/plans/2026-11-06-windows-bruecke-nachweise.md).

## Windows-Worker und geschützte Prozessinstanz

Das Übergabejournal nutzt SQLite aus der Standardbibliothek mit bestätigtem
Intent vor COM und Ergebnis danach. Es ist Lauf-Audit und wird nicht durch
Diagnoserotation gelöscht. Detaildiagnosen sind getrennt auf 64 MiB/sieben
Tage begrenzt; Zugriffe und Export wenden die Aufbewahrung an. Wer genaue
physische Löschung auch während Leerlauf braucht, plant `prune()` regelmäßig
im Backend ein. Globale Laufbereinigung bleibt OQ-60.

Die Prozessinstanz verwendet native Win32-SID/DACL-/Mutex-/Event-APIs über
`ctypes`, ohne zusätzliche Bibliothek und ohne GUI-Fenstercode. Linux-Fakes
sind vom echten Windows-Prozesstest getrennt; dessen Ergebnis steht aus.
GSVmulti wird nicht beendet. Die GUI muss Aktivierungswunsch, explizites
Beenden, Abmelden und Standby an die vorhandenen Kernoperationen anbinden.

## Windows-Installer und Updateverträge

W3 verwendet Standardbibliothek plus die bereits getrennt deklarierte
cryptography-Bibliothek für Ed25519-Manifestprüfung. Vertrauensschlüssel und
erlaubter HTTPS-Release-Ursprung müssen ausdrücklich provisioniert werden;
Testschlüssel sind keine Produktvorgabe. OQ-65 führt Kanal-/Schlüsselwechsel
und Schutz gegen alte signierte Releases. Native Deployment-/UAC-Anbieter
fehlen weiterhin und bleiben ohne Qualifikation gesperrt.

Optionales Inno-Setup-Rezept paketiert ausschließlich die interne N1-Probe
nach bestandenen N1-Buildgates. Es ist kein signierter Produktinstaller und
enthält keinen Treiber-/GUI-Start. Kein Windows-Runner ist bereitgestellt;
deshalb wurde keine zusätzliche CI-Jobdatei angelegt. Konkrete Inno-Version,
Signierung und VM-Nachweise sind externe Voraussetzungen, keine Installation
in der Pi-venv.

## Brücke v2: optionale Discovery und HTTPS-Zugang

Debian `python3-zeroconf` wird im Workbench-Installationsskript deklariert.
Es wird erst für ausdrücklich aktivierte DNS-SD-Veröffentlichung benötigt;
SDK-Fehler lassen konfigurierte HTTPS/WSS-Endpunkte verwendbar. Hier wurde
das Paket nicht installiert. Windows führt `zeroconf` als eigenen, noch zu
qualifizierenden Buildkandidaten. Die Adapter-API wurde gegen die
[primäre SDK-Dokumentation](https://python-zeroconf.readthedocs.io/en/latest/api.html)
und freigegebenen Quelltext geprüft, nicht am installierten Netzwerk.

Die Suche läuft per `multiprocessing` mit `spawn` in einem begrenzten
Kindprozess, einschließlich SDK-Start und Aufräumen. Der spätere eingefrorene
Windows-Einstieg braucht `multiprocessing.freeze_support()` und eine echte
Windows-Suchprüfung. Dies betrifft keine Kameraprozesse. Veröffentlichung
ist separat optional; explizite Endpunkte bleiben unabhängig davon erhalten.

`--bridge-directory` lädt ausschließlich eine vorhandene provisionierte
Identität und verwendet deren Zertifikat am HTTPS-Dienst. Vorhandene
`--cert`/`--key`-Dateien werden nicht überschrieben. Ohne Opt-in bleibt der
bisherige TLS-Weg. Der portable Bind-Standard ist 127.0.0.1; externe
Erreichbarkeit braucht eine ausdrückliche Dienstadresse und konfigurierte
Endpunkte. PAM-Konto muss zum lokalen Dienstkonto passen und ist
konfigurierbar; kein festes me-systeme-Konto als allgemeiner Vertrag.

## Brücke v2: Identität und Kopplung

Der Pi benötigt zusätzlich Debian `python3-cryptography`;
`scripts/install-workbench.sh` deklariert es, ohne Qt/PyPI-Kopien einzuführen.
Die vorhandene Testumgebung stellt cryptography 50.0.1 bereit; in dieser
Umsetzung wurde nichts installiert. Windows führt cryptography 50.0.1
als Buildkandidaten in seiner getrennten `.in`-Datei, nicht als bereits
qualifizierten Windows-Lock.

Die öffentliche Zertifikats-/Signaturprüfung ist auch ohne POSIX-Module
importierbar. Persistente Identität und lokale Erstkonfiguration sind
Pi-Aufgaben: Eigentümerverzeichnis 0700, private Identitätsdatei 0600,
hardwaregebundene ID und RSA-3072-Zertifikat. Bereitstellung ausschließlich
über ausdrückliches `dispread bridge identity --provision`; bestehende
Zertifikate und laufende Dienste werden dabei nicht ersetzt. Offline-UART
kann ein lokal exportiertes Profil mit höchstens fünf Minuten gültigem
Einmalangebot verwenden. Netzwerk-/HTTP-Anbindung und gemeinsamer Hub sind als Backend integriert;
Aktivierung und reale Abnahme bleiben ausdrücklich getrennt.

## Zensical-Pflege auf dem Forgejo-Runner

Der getrennte Wartungs-Runner installiert `@openai/codex@0.156.1` mit Node
unter `/opt/picam-codex` (siehe
`scripts/forgejo-codex-runner-install.sh`). Das Paket gehört nur zum
Dokumentations-Workflow und nicht zur Messpipeline. Der Job nutzt die
ChatGPT-Anmeldung der Codex CLI im privaten, persistenten `CODEX_HOME` des
Runner-Benutzers; es wird kein API-Schlüssel im Repo abgelegt.
Die Zensical-Build-Abhängigkeiten stehen weiter in `requirements-docs.txt`
und werden in einem eigenen `.venv-docs` installiert. Das Projekt-`.venv`
bleibt mit `--system-site-packages` angelegt; das Projektpaket wird, falls
benötigt, ausschließlich mit `--no-deps` installiert.

## Die wichtigste Regel

```bash
python3 -m venv --system-site-packages .venv
./.venv/bin/pip install --no-deps -e .
./.venv/bin/pip install pytest ruff
```

Beide Flags sind **nicht optional**:

* **`--system-site-packages`** — ohne das sind `picamera2` und `libcamera` im
  venv unsichtbar. `libcamera` ist ein C++-Binding und per pip überhaupt nicht
  installierbar.
* **`--no-deps` plus `dependencies = []` in `pyproject.toml`** — stünden
  `numpy`, `opencv-python` oder `pyserial` als Projektabhängigkeiten drin,
  legte pip PyPI-Kopien nach `.venv/lib/`, die die Systempakete
  **überschatten**. Ein pip-`numpy` neben dem gegen System-`numpy 2.2.4`
  gebauten `cv2 4.10.0` ist ein ABI-Bruch, der sich als schwer deutbarer
  Absturz zeigt.

Gegenprobe — alle Module müssen nach `/usr/lib/python3/dist-packages` auflösen:

```bash
./.venv/bin/python -c "
import cv2, numpy, serial, picamera2, libcamera
for m in (cv2, numpy, serial, picamera2, libcamera): print(m.__name__, m.__file__)"
```

`pytest` und `ruff` liegen bewusst **im** venv: sie gehören versioniert zum
Projekt, und PEP 668 (`externally-managed-environment`) betrifft nur das
System-pip, nicht das venv.

## Dokumentierter Systempaketbestand

| Paket | Version | Zweck |
| --- | --- | --- |
| `python3-picamera2` | 0.3.37 | historischer IMX500-Kamerazugriff; zur Laufzeit nicht mehr benötigt |
| `python3-libcamera` | 0.7.2 | historische IMX500-Bindings; zur Laufzeit nicht mehr benötigt |
| `python3-opencv` | 4.10.0 | Entzerrung, Bildaufbereitung |
| `python3-numpy` | 2.2.4 | Arrays |
| `python3-serial` | 3.5 | serielle Ausgabe |
| `rpicam-apps` | 1.13.0 | historische IMX500-Inbetriebnahme und Postprocessing |
| `imx500-all`, `-firmware`, `-models`, `-tools` | — | historische Sensorfirmware, Modelle und Packager |
| `v4l-utils`, `ffmpeg`, `i2c-tools`, `git` | — | Diagnose, Videokonvertierung |
| `tesseract-ocr` | 5.5.0 | OCR-Vergleichsbasis. Konzept §5 nennt Tesseract als Kandidaten — ihn unbewertet stehen zu lassen wäre die schlechtere Option. Angebunden per **CLI über `subprocess`**, nicht über `pytesseract`: das spart eine Abhängigkeit, und `python3-pytesseract` existiert in Debian 13 ohnehin nicht |
| `tesseract-ocr-eng` | — | Ohne Traineddata startet Tesseract nicht |
| `socat` | — | pty-Paare mit stabilen Symlinks für interaktive Serial-Tests. **Für die Unit-Tests nicht nötig** — die nutzen `os.openpty()` aus der stdlib, damit `pytest` auch ohne socat läuft |
| `chrony` | 4.6.1-3 | Ersetzt `systemd-timesyncd`. `chronyc tracking` kann für eine protokollierbare Offset- und Drift-Historie aufgezeichnet werden. Damit ist noch keine Synchronität zur Kalibrierreferenz belegt — Messungen M1 und M6 in [TIMING.md](TIMING.md) |

Die Tesseract-Pakete sowie `socat` und `chrony` waren zwischenzeitlich
installiert, ohne dass dieser Eintrag nachgezogen wurde — bestätigt am 2026-09-21 per `which`/`dpkg -l`
([OQ-15](open-questions.md), geklärt).

**Einschränkung, die dokumentiert bleiben muss:** `tesseract-ocr-eng` ist auf
Prosa trainiert. Auf 7-Segment-Anzeigen sind die Trefferquoten typischerweise
schlecht — verwechselt 1/7 und 0/8, verliert Dezimalpunkte. Das
Vergleichsbeispiel soll das **messen und belegen**, nicht kaschieren.
Spezialisierte Traineddata (`ssd`, `letsgodigital`) sind nicht in Debian, siehe
[OQ-10](open-questions.md).

## Bewusst nicht installiert

| Paket | Entscheidung | Begründung |
| --- | --- | --- |
| `torch`, `torchvision` | **nein, gar nicht auf dem Pi** | Großer Speicherbedarf; Training ist off-Pi vorgesehen. Die frühere Angabe zum freien Speicher war ein historischer Snapshot, kein aktueller Ressourcenstand. Die frühere Begründung mit Inferenz auf der IMX500 ist seit dem Kamerawechsel historisch ([OQ-11](open-questions.md)). |
| `onnxruntime` | zurückgestellt, aber **bevorzugte Option**, falls je CPU-Inferenz nötig wird | ~50 MB statt 2 GB, reine Inferenz. Erst installieren, wenn ein konkretes `.onnx` existiert |
| `tensorflow`, `tflite-runtime` | nein | wie torch, kein Bedarf ohne eigenes Modell |
| `paddleocr`, `paddlepaddle` | nein | arm64/Python-3.13-Wheels unzuverlässig, große Modell-Downloads. Konzept §5 nennt es als Kandidaten — hier als „geprüft, verworfen für jetzt" festgehalten, nicht stillschweigend weggelassen |
| `easyocr` | nein | zieht torch |
| `pytesseract` | nein | CLI genügt, und das Debian-Paket existiert nicht |
| `imx500-converter`, `model_compression_toolkit` | **off-Pi** | Auf dem Pi nicht verfügbar. Vorhanden sind nur die Packager-Endstufen `imx500-package`, `fpk2rpk` und `PostConverter.jar` unter `/usr/lib/imx500-tools/` |
| `nginx`, `flask` | nein | Die Weboberfläche nutzt `aiohttp`; ein zusätzlicher Webserver oder Flask ist für den vorhandenen Betrieb nicht nötig |

## Was das Projekt selbst zur Laufzeit braucht

Nichts über die dokumentierten Systempakete hinaus. Der Messkern nutzt
`numpy`, `cv2` und `pyserial`. Für die Workbench kommen `aiohttp` und PAM
hinzu; Brücke v2 benötigt cryptography und für optionale Discovery zeroconf; die optionale TUI nutzt `textual` (Pakete siehe unten). Die aktive
UVC-Bildquelle öffnet OpenCV erst beim Öffnen der Kamera. `picamera2` wird von ihr nicht importiert; Tests und Beispiele ohne
Kamera bleiben ausführbar ([Bildquellen-API](../api/frames.md)).

## Kamera-Workbench (2026-09-08)

Installation: `bash scripts/install-workbench.sh`. Weiterhin nur die Projekt-
venv mit Systempaketen und `pip install --no-deps -e .` verwenden. Der
Konsolenbefehl `dispread` ist in `pyproject.toml` registriert.

| Paket | Installierte Version bei Implementierung | Zweck |
| --- | --- | --- |
| Debian `python3-aiohttp` | 3.11.16 | HTTPS, MJPEG, WebSockets, Unix-Socket-API |
| Debian `python3-textual` | 2.1.2 | Tastaturbediente TUI und TUI-Tests |
| Debian `python3-pam` | 0.4.2 (Modul `PAM`) | Linux-Passwort- und Kontostatusprüfung |
| Debian `openssl` | Systempaket | Lokales TLS-Zertifikat und Fingerabdruck |
| `@xterm/xterm` | 5.5.0 | Browser-Terminalemulator |
| `@xterm/addon-fit` | 0.10.0 | Anpassung der Terminalgröße |
| Schrift Noto Sans (Regular, Medium, SemiBold, Bold) | 2.015 | Grundschrift der Live-Seite `/live` |
| Schrift Noto Sans Mono (Regular, Bold) | 2.014 | Werte, Koordinaten und Kennungen auf `/live` |

Die beiden xterm-Pakete wurden versioniert von jsDelivr bezogen und liegen
mit MIT-Lizenzen unter `src/dispread/workbench/static/vendor/`. Im Betrieb
werden keine CDN-Verbindungen benötigt. Die Noto-Schriften (SIL OFL 1.1)
stammen aus den offiziellen Builds unter
`github.com/notofonts/notofonts.github.io` (`fonts/NotoSans*/hinted/ttf`) und
liegen als woff2-Teilmenge (Latein, Griechisch, Satz- und Pfeilzeichen) mit
`LICENSE.noto` unter `static/vendor/fonts/`; Quell-Prüfsummen und
Teilmengenbereich stehen in der Lizenzdatei. Die Teilmenge entstand mit
fontTools in einer temporären Umgebung, nicht in der Projekt-venv. Browserassets werden mit dem Python-
Paket ausgeliefert; es ist keine Node.js-Laufzeit erforderlich.

Linux-Shell: Bash auf einem echten PTY. Ein frisch gestarteter Kindprozess
übernimmt das steuernde Terminal vor `exec`; kein Python-Code nach einem
Fork aus dem mehrthreadigen Kameraprozess. Kein tmux notwendig. PAM nutzt den
vorhandenen Dienst `login` für das konfigurierte lokale Dienstkonto
(standardmäßig effektiver OS-Benutzer). Serverstart als root oder mit einem
PAM-Konto, dessen UID nicht zum Dienst passt, wird abgelehnt.

## Doku-Seite und CI (2026-09-23)

Nur für die Doku, nicht für den Messpfad. Deshalb eine **eigene** venv
`.venv-docs` (ohne `--system-site-packages`), die Projekt-`.venv` bleibt
unberührt. Einrichtung und Bauen: Kopf von `scripts/docs-site.sh`.

| Paket | Version (gepinnt in `requirements-docs.txt`) | Zweck |
| --- | --- | --- |
| `zensical` | 0.0.64 | Statische Doku-Seite aus `docs/` und den Wurzel-Markdowns |
| `mkdocstrings`, `mkdocstrings-python` | 1.0.6, 2.0.9 | API-Referenz aus den Docstrings |
| `griffelib` | 2.3.0 | Liest den Quelltext statisch, importiert nichts |
| `pymdown-extensions` | 12.1 | Transitiv (Zensical/mkdocstrings), seit 2026-10-12 gepinnt: 12.2 verlangt in `Highlight.__init__` das Argument `md`, das mkdocstrings 1.0.6 nicht übergibt, und bricht den Build |
| `forgejo-runner` | 13.2.0 (arm64, SHA-256 gepinnt) | Führt `.github/workflows/docs.yml` auf dem Pi aus |

Der Runner läuft als eigener Systemnutzer ohne Zugriff auf Kamera, serielle
Ports, GPIO und `/home` (`systemd/forgejo-runner.service`). Einrichtung:
`sudo ./scripts/forgejo-runner-install.sh`. Mermaid lädt die Seite zur
Laufzeit von `unpkg.com`. Ohne Internet fehlen deshalb die Diagramme, der
Rest der Seite funktioniert.

**anime.js 4.5.0** (MIT, 2026-10-12) treibt die Animation der
[Projekt-Tour](uebersicht/projekt-tour.md) und seit 2026-10-23 den
räumlichen Ebenenwechsel der [Roadmap](ROADMAP.md). Es liegt als lokale Kopie unter
`docs-site/assets/vendor/anime-4.5.0.umd.min.js` (SHA-256
`8d5b3a58a1f64023a04a4cedeef135a2263b18da04b35177ac13438a0bad033b`, aus
`npm pack animejs@4.5.0`, Lizenz daneben in `anime-LICENSE.txt`). Es gibt
also keinen CDN-Abruf und keinen npm-Build-Schritt. `tour.js` lädt die Datei
auf der Tour-Seite und auf Seiten mit eingebetteten Tour-Abbildungen nach;
`roadmap.js` nutzt dieselbe Datei auf der Roadmap. Ohne die Laufzeit bleibt
die Karte ohne Animation bedienbar.
Für ein Update die Datei samt Versionsnummer im Namen tauschen, `ANIME_FILE`
in `tour.js` und `ANIME_URL` in `roadmap.js` anpassen und die Docs-Tests laufen
lassen.


## Einmalige TDMS-Auswertung, 2026-11-04

Für den Nutzerexport aus UART-Demo 05 wurde npTDMS 1.13.0 mit
`./.venv/bin/python -m pip download --no-deps --only-binary=:all:` nach
`var/diagnostics/gsvmulti/analysis-tools/` geladen und direkt als Wheel über
sys.path im lokalen Analyserezept importiert. Es wurde weder in die
Projekt-venv installiert noch als Laufzeitabhängigkeit hinzugefügt;
pyproject.toml/install.sh benötigen es nicht. Keine zusätzlichen Pakete
heruntergeladen, Debian-NumPy weiter verwendet. Wheelhash und Importpfad
stehen in `recording-comparison.json` von Lauf 05.
[Reader-Dokumentation](https://nptdms.readthedocs.io/en/stable/reading.html),
[Auswertung](VALIDATION.md#uart-demo-20261104-05).
