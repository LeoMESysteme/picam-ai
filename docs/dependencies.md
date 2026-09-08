# Abhängigkeiten

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

## Bereits vorhanden (Systempakete, nichts zu tun)

| Paket | Version | Zweck |
| --- | --- | --- |
| `python3-picamera2` | 0.3.37 | Kamerazugriff, IMX500-Helfer |
| `python3-libcamera` | 0.7.2 | libcamera-Bindings |
| `python3-opencv` | 4.10.0 | Entzerrung, Bildaufbereitung |
| `python3-numpy` | 2.2.4 | Arrays |
| `python3-serial` | 3.5 | serielle Ausgabe |
| `rpicam-apps` | 1.13.0 | Inbetriebnahme, inkl. IMX500-Postprocessing |
| `imx500-all`, `-firmware`, `-models`, `-tools` | — | Sensorfirmware, 23 Fertigmodelle, Packager |
| `v4l-utils`, `ffmpeg`, `i2c-tools`, `git` | — | Diagnose, Videokonvertierung |

## Noch zu installieren

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-eng socat chrony
```

Blockiert, weil `sudo` seit dem Reboot ein Passwort verlangt
([OQ-15](open-questions.md)).

| Paket | Version | Warum |
| --- | --- | --- |
| `tesseract-ocr` | 5.5.0 | OCR-Vergleichsbasis. Konzept §5 nennt Tesseract als Kandidaten — ihn unbewertet stehen zu lassen wäre die schlechtere Option. Angebunden per **CLI über `subprocess`**, nicht über `pytesseract`: das spart eine Abhängigkeit, und `python3-pytesseract` existiert in Debian 13 ohnehin nicht |
| `tesseract-ocr-eng` | 4.1.0 | Ohne Traineddata startet Tesseract nicht |
| `socat` | 1.8.0.3 | pty-Paare mit stabilen Symlinks für interaktive Serial-Tests. **Für die Unit-Tests nicht nötig** — die nutzen `os.openpty()` aus der stdlib, damit `pytest` auch ohne socat läuft |
| `chrony` | — | Ersetzt `systemd-timesyncd`. Nur chrony liefert eine protokollierbare Offset- und Drift-Historie (`chronyc tracking`). Ohne dieses Log ist die Aussage „Pi-Zeit gegen Referenz" nicht belegbar — Messung M1 in [TIMING.md](TIMING.md) |

**Einschränkung, die dokumentiert bleiben muss:** `tesseract-ocr-eng` ist auf
Prosa trainiert. Auf 7-Segment-Anzeigen sind die Trefferquoten typischerweise
schlecht — verwechselt 1/7 und 0/8, verliert Dezimalpunkte. Das
Vergleichsbeispiel soll das **messen und belegen**, nicht kaschieren.
Spezialisierte Traineddata (`ssd`, `letsgodigital`) sind nicht in Debian, siehe
[OQ-10](open-questions.md).

## Bewusst nicht installiert

| Paket | Entscheidung | Begründung |
| --- | --- | --- |
| `torch`, `torchvision` | **nein, gar nicht auf dem Pi** | 2–3 GB von 34 GB frei. Zielort für Inferenz ist der IMX500, nicht die Pi-CPU — und die Konvertierungskette dorthin läuft ohnehin off-Pi ([OQ-11](open-questions.md)). Torch auf dem Pi würde Training ermöglichen, das dort nicht stattfinden soll |
| `onnxruntime` | zurückgestellt, aber **bevorzugte Option**, falls je CPU-Inferenz nötig wird | ~50 MB statt 2 GB, reine Inferenz. Erst installieren, wenn ein konkretes `.onnx` existiert |
| `tensorflow`, `tflite-runtime` | nein | wie torch, kein Bedarf ohne eigenes Modell |
| `paddleocr`, `paddlepaddle` | nein | arm64/Python-3.13-Wheels unzuverlässig, große Modell-Downloads. Konzept §5 nennt es als Kandidaten — hier als „geprüft, verworfen für jetzt" festgehalten, nicht stillschweigend weggelassen |
| `easyocr` | nein | zieht torch |
| `pytesseract` | nein | CLI genügt, und das Debian-Paket existiert nicht |
| `imx500-converter`, `model_compression_toolkit` | **off-Pi** | Auf dem Pi nicht verfügbar. Vorhanden sind nur die Packager-Endstufen `imx500-package`, `fpk2rpk` und `PostConverter.jar` unter `/usr/lib/imx500-tools/` |
| `nginx`, `flask` | nein | keine Weboberfläche im Umfang |

## Was das Projekt selbst zur Laufzeit braucht

Nichts über die Systempakete hinaus. Die Kette läuft mit `numpy`, `cv2` und
`pyserial`; `picamera2` wird ausschließlich in den beiden Kameramodulen
importiert, und zwar lazy in der Factory. Deshalb laufen Tests und Beispiele
auch ohne Kamera.

## Kamera-Workbench (2026-09-08)

Installation: `bash scripts/install-workbench.sh`. Weiterhin nur die Projekt-
venv mit Systempaketen und `pip install --no-deps -e .` verwenden. Der neue
Konsolenbefehl `dispread` ist in `pyproject.toml` registriert.

| Paket | Installierte Version bei Implementierung | Zweck |
| --- | --- | --- |
| Debian `python3-aiohttp` | 3.11.16 | HTTPS, MJPEG, WebSockets, Unix-Socket-API |
| Debian `python3-textual` | 2.1.2 | Tastaturbediente TUI und TUI-Tests |
| Debian `python3-pam` | 0.4.2 (Modul `PAM`) | Linux-Passwort- und Kontostatusprüfung |
| Debian `openssl` | Systempaket | Lokales TLS-Zertifikat und Fingerabdruck |
| `@xterm/xterm` | 5.5.0 | Browser-Terminalemulator |
| `@xterm/addon-fit` | 0.10.0 | Anpassung der Terminalgröße |

Die beiden xterm-Pakete wurden versioniert von jsDelivr bezogen und liegen
mit MIT-Lizenzen unter `src/dispread/workbench/static/vendor/`. Im Betrieb
werden keine CDN-Verbindungen benötigt. Browserassets werden mit dem Python-
Paket ausgeliefert; es ist keine Node.js-Laufzeit erforderlich.

Linux-Shell: Bash auf einem echten PTY. Ein frisch gestarteter Kindprozess
übernimmt das steuernde Terminal vor `exec`; kein Python-Code nach einem
Fork aus dem mehrthreadigen Kameraprozess. Kein tmux notwendig. PAM nutzt den
vorhandenen Dienst `login` für den eigenen Benutzer `me-systeme`; Serverstart
als root oder als anderer Benutzer wird abgelehnt.
