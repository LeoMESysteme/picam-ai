# Projekt-Historie

Dieses Dokument beschreibt Entscheidungen, die **nicht** unmittelbar aus dem
Quellcode ersichtlich sind. Format je Eintrag: Problem / Entscheidung /
Begründung / Alternativen / Konsequenz.

Messergebnisse gehören nach [VALIDATION.md](VALIDATION.md) bzw.
[TIMING.md](TIMING.md), Tagesgeschäft nach [lab_journal.md](lab_journal.md).

---

# 2026-09-07 — Kamera wurde nicht erkannt: Reboot statt Fehlersuche

## Problem

`rpicam-hello --list-cameras` meldete `No cameras available!`, obwohl die AI
Camera an CAM/DISP0 angeschlossen war. `dtoverlay -l` zeigte
`No overlays loaded`, es gab keinen Sensorknoten im Device-Tree, keine
`rp1-cfe`-V4L2-Nodes und keine CAM-I2C-Busse.

## Entscheidung

Kein Debugging der Softwarekonfiguration, sondern Reboot als erste Maßnahme.

## Begründung

`camera_auto_detect=1` war korrekt gesetzt und die Bootloader-Firmware aktuell.
`camera_auto_detect` prüft die Anschlüsse aber **ausschließlich beim Booten**.
Das Journal zeigte genau einen Boot um 12:03 und die Installation von
`imx500-all` erst um 13:34 — die Kamera war also nach dem letzten Boot
angesteckt worden. Damit war die Ursache nicht ein Konfigurationsfehler,
sondern ein fehlender Neustart.

## Alternativen

Explizites `dtoverlay=imx500,cam0` eintragen (hätte ebenfalls einen Reboot
gebraucht), Kabel und Anschluss prüfen (unnötiger Eingriff in funktionierende
Hardware).

## Konsequenz

Nach dem Reboot wurde die Kamera erkannt. Die Eskalationsleiter ist in
[CAMERA_COMMISSIONING.md](CAMERA_COMMISSIONING.md) dokumentiert, damit der Fall
beim nächsten Gerätewechsel in Minuten statt in Stunden erledigt ist.

---

# 2026-09-07 — `dtoverlay -l` ist kein Kriterium für „Kamera erkannt"

## Problem

Das Diagnoseskript meldete nach erfolgreicher Inbetriebnahme weiter zwei
Fehler, obwohl die Kamera aufnahmefähig war.

## Entscheidung

`dtoverlay -l` und die CAM-I2C-Busnummern gelten nur noch als informativ. Als
Nachweis dient der **Sensorknoten im Device-Tree** plus die Enumeration durch
libcamera.

## Begründung

`camera_auto_detect` wird von der Firmware beim Booten angewandt und erscheint
deshalb **nicht** in `dtoverlay -l` — das listet nur zur Laufzeit nachgeladene
Overlays. Die CAM-Busnummern sind zudem nicht stabil (hier 6 und 10, nicht die
oft genannten 4 und 6).

## Konsequenz

Zwei Falschmeldungen im Diagnoseskript beseitigt. Die Unterscheidung
„Anschluss vorhanden" (`cam0_reg` im Device-Tree, auf dem Pi 5 immer da) gegen
„Sensor erkannt" (Knoten `imx500@1a`) ist jetzt maschinell möglich.

---

# 2026-09-07 — Bestätigte manuelle ROI ist der Primärpfad, nicht die IMX500-Detektion

## Problem

Das Konzept nennt einen kleinen Objektdetektor zum Finden der Anzeige, und der
IMX500 kann Netze im Sensor ausführen. Naheliegend wäre, damit anzufangen.

## Entscheidung

Der Primärpfad zum Lokalisieren der Anzeige ist die vom Bediener bestätigte
ROI (`detect/manual_roi.py`). Die IMX500-Detektion ist ein Experiment.

## Begründung

Die 23 mitgelieferten `.rpk` sind COCO-/ImageNet-Modelle — gemessen liefert
`network_intrinsics` Labels wie `person`, `bicycle`, `tv`. Dass ein solches
Modell auf einem GSV-2ASD-Display eine brauchbare Box liefert, ist
unwahrscheinlich. Eigene Modelle sind auf diesem Pi nicht konvertierbar (nur
der Packager ist da, siehe [OQ-11](open-questions.md)). Konzept §10 Ph. 2 nennt
den manuellen Ausschnitt selbst als Rückfalloption.

## Alternativen

Zuerst einen eigenen Detektor trainieren — hätte einen Datensatz und eine
Konvertierungs-Workstation vorausgesetzt, beides nicht vorhanden, und die
gesamte übrige Kette blockiert.

## Konsequenz

Die Werterkennung, die Freigabelogik und die Ausgabekette konnten sofort gebaut
und gemessen werden. Die Detektion bleibt hinter derselben Schnittstelle
austauschbar.

---

# 2026-09-07 — Kein `torch`/`onnx`/`paddle` auf dem Pi

## Entscheidung

Auf dem Pi werden keine ML-Frameworks installiert.

## Begründung

`torch` belegt 2–3 GB von 34 GB freiem Speicher. Der Zielort für Inferenz ist
der IMX500, nicht die Pi-CPU — und die Konvertierungskette dorthin läuft
ohnehin off-Pi. `paddleocr` hat auf arm64/Python 3.13 unzuverlässige Wheels.
Ein Framework auf dem Pi würde also Training ermöglichen, das dort gar nicht
stattfinden soll.

## Konsequenz

`onnxruntime` (~50 MB, reine Inferenz) bleibt die bevorzugte Option, falls je
CPU-Inferenz nötig wird — installiert wird es erst, wenn ein konkretes `.onnx`
existiert. Dokumentiert in [dependencies.md](dependencies.md).

---

# 2026-09-07 — Keine Laufzeitabhängigkeiten in `pyproject.toml`

## Problem

`numpy`, `opencv`, `pyserial`, `picamera2` und `libcamera` liegen als
Debian-Systempakete vor. Stünden sie als Projektabhängigkeiten in
`pyproject.toml`, würde `pip` PyPI-Kopien ins venv legen.

## Entscheidung

`dependencies = []`, Installation mit `pip install --no-deps -e .`, venv mit
`--system-site-packages`.

## Begründung

Ein pip-`numpy` unter `.venv/lib/` überschattet das System-`numpy 2.2.4`, gegen
das `cv2 4.10.0` und `python3-libcamera` gebaut sind — das ist ein ABI-Bruch,
der sich als schwer deutbarer Absturz zeigt. `libcamera` ist als C++-Binding
per pip ohnehin nicht installierbar.

## Konsequenz

Laufzeitabhängigkeiten kommen ausschließlich per `apt`. Ein Doctor-Check
verifiziert aktiv, dass die Module nach `/usr/lib/python3/dist-packages`
auflösen. `pytest` und `ruff` liegen im venv, weil sie versioniert zum Projekt
gehören und PEP 668 nur das System-pip betrifft.

---

# 2026-09-07 — Zeitbasis ist ein Pflichtfeld und wird nie geschönt

## Problem

Konzept §6 verlangt, Bedeutung und Genauigkeit von Zeitstempeln getrennt zu
führen. Beim Entwickeln ohne Kamera entstehen zwangsläufig Zeitstempel, die
keine Zeitaussage tragen.

## Entscheidung

`TimeBaseKind` ist Pflichtfeld in `Frame` und `ValueRecord`, mit der
Eigenschaft `carries_time_information`. Eine synthetische Quelle darf keine
Sensorqualität behaupten.

## Begründung

Ohne dieses Feld wäre der naheliegende Fehler, später Replay- oder
Synthetik-Latenzen als reale Latenzen zu berichten. Das Feld macht die
Unterscheidung im Datenstrom sichtbar und im Bericht maschinenlesbar
(`timing_is_meaningful` in `report.json`).

## Konsequenz

Beispiel 16 weist explizit aus, dass seine Latenzzahlen keine Zeitaussage über
den Realbetrieb sind.

---

# 2026-09-07 — Adapterzustand getrennt vom Datensatz (`TxReceipt`)

## Entscheidung

Kanalnummer, Sendezeit, Telegrammtext, Retries und die angewandte
`InvalidValuePolicy` stehen in einem `TxReceipt`, nicht im `ValueRecord`.

## Begründung

Der `ValueRecord` ist das Beweismittel für „was hat das System erkannt", der
Receipt für „was ging über die Leitung". Wer beides vermischt, kann später
nicht mehr belegen, welche Zeit welche war — und genau das braucht die
zeitliche Zuordnung nach Konzept §6. Zusätzlich darf der Adapter den
`capture_timestamp` niemals verändern.

---

# 2026-09-07 — Segmentschwelle aus den Segmentmessungen, nicht aus dem Bild

## Problem

Erster Ansatz: Schwelle pro Ziffernzelle aus deren Min/Max. Das verwarf jede
`8` — bei sieben aktiven Segmenten ist der zellinterne Kontrast null. Zweiter
Ansatz: Otsu über alle Bildpunkte des Ausschnitts. Das erkannte den Überlauf
nicht.

## Entscheidung

Die Schwelle kommt aus den **gepoolten Segmentmessungen aller Stellen**
(`segment_threshold`).

## Begründung

Eine 7-Segment-Anzeige hat drei Helligkeitsstufen, und die inaktiven Segmente
sind die häufigste. Gemessen an einem synthetischen Panel: Panel 19, inaktives
Segment 34, aktives Segment 115 von 255. Otsu über alle Bildpunkte legte die
Schwelle bei 34 und trennte damit Panel von Segmenten statt inaktiv von aktiv.
Die gepoolten Segmentmessungen sind dagegen bimodal genau in der gesuchten
Achse.

## Konsequenz

`8` wird gelesen, Überlauf erkannt, und starke Unschärfe führt nicht mehr zu
Ablehnung aller Frames. Bekannte Grenze: zeigt die Anzeige ausschließlich `8`,
fehlt die inaktive Klasse und der Ausschnitt wird abgelehnt — siehe
[OQ-13](open-questions.md). Eine Falschablehnung ist nach Konzept §7 die
zulässige Richtung.

---

# 2026-09-07 — Kein Erfinden des GSVmulti-Telegramms

## Entscheidung

`sink/protocol/gsv_ascii.py` wirft `NotImplementedError` und verweist auf die
Klärungsliste. Der Platzhalter `AsciiCsvFormatter` ist als
`provisional=True` gekennzeichnet, und dieses Flag wandert in jedes
Runartefakt.

## Begründung

Ein geratenes Format wäre schädlicher als keines: es würde in Tests grün
erscheinen, in Messberichten als „Ausgabe funktioniert" auftauchen und erst am
Laborplatz auffallen. Die Spezifikation ist nicht verfügbar
([OQ-07](open-questions.md)).

## Konsequenz

Die Kette ist vollständig testbar, ohne eine Behauptung über GSVmulti
aufzustellen. Das echte Format ist später ein neuer Formatter, keine Änderung
an der Pipeline.

---

# 2026-09-07 — MEhub-Konventionen übernommen, Deployment-Apparat nicht

## Entscheidung

Übernommen: src-Layout, `paths.py`-Muster, `hardware.conf`-Regel „fehlender
Schlüssel ⇒ Default", `tests/conftest.py` mit `--mode=mock|real`, ruff+pytest,
Service-plus-Watchdog-Muster, Projekt-`.venv`, die Doku-Dateinamen
`project_history.md` und `open-questions.md`.

Nicht übernommen: `web/`, `nginx/`, `telegraf/`, OTA-/Releases-Layout unter
`/opt`.

## Begründung

Hier läuft ein Laborgerät, kein Flottenbetrieb. Ein leerer OTA-Apparat wäre
reine Last. Wichtig ist die ausdrückliche Feststellung, dass MEhubs
Hotfix-Regel „nicht direkt nach `/opt/mehub/current` schreiben" hier **nicht**
gilt — das Repo liegt im Home. Ohne diese Notiz in `AGENTS.md` würde eine
künftige Session sie kopieren.

## Konsequenz

Konfiguration in JSON statt YAML, weil Konzept §5 „JSON-Profile" festschreibt
und `json` in der stdlib ist — das vermeidet zwei weitere Abhängigkeiten, die
Systempakete überschatten könnten.

---

# 2026-09-08 — Eigenständige Kameravorschau mit MJPEG und Konturheuristik

## Entscheidung

Ein einzelnes Beispielskript kombiniert Kamera, geometrische Display-Vorschläge
und HTTP-Vorschau auf Loopback. Windows verwendet einen SSH-Tunnel und den
Browser. Das Skript bleibt unabhängig von Messwertpipeline und Quellenregistry;
der nächste Versuch braucht weder OCR noch eine vollständige `picamera2://`-
Implementierung. Keine Änderung des manuellen ROI-Primärpfads.

## Verworfene Alternativen

* X11/VNC: zusätzliche Einrichtung auf Windows für eine reine Bildvorschau.
* WebRTC/H.264: mehr Protokoll-/Clientaufwand als für den ersten Versuch nötig;
  MJPEG benötigt mehr Bandbreite, ist hier aber direkt im Browser nutzbar.
* Flask oder separates Frontend-Projekt: Standardbibliothek plus eingebettete
  HTML-Seite genügen, zusätzliche Abhängigkeiten entfallen.
* Stock-IMX500-Modelle: laut bisherigen Versuchen kein geeigneter
  Messgeräte-Displaydetektor. Training eines eigenen Modells benötigt Daten.
* Nur manuelle ROI: vom Nutzer für diesen Prototyp zugunsten automatischer
  Vorschläge verworfen; die Heuristik bleibt ausdrücklich unbestätigt.

## Konsequenz

Schneller, nachvollziehbarer Versuch mit geometrischen Filtern. Keine
Behauptung semantischer Display-Erkennung und keine Konfidenzwahrscheinlichkeit.
Reale Kameraübertragung ist lokal geprüft; die visuelle Abnahme am Gerät und
unter Windows steht aus. Anleitung: [Livevorschau](anleitung/10-kamera-livevorschau.md).

---

# 2026-09-08 — Workbench statt weiter wachsendem Beispielskript

**Entscheidung:** Kamerabesitzer, Profile, HTTPS-Server, Shellverwaltung,
CLI/TUI und Browserassets unter `dispread.workbench` getrennt. Das Beispiel
bleibt Einstieg. HTTP/WebSockets mit aiohttp, TUI mit Textual, echte Shells
über PTYs und xterm.js. Systempakete erhalten die Projekt-ABI-Regel.

**Bedienentscheidung des Nutzers:** Möglichst keine Buttons/Slider. TUI in der
Shell statt separater Regleroberfläche oder reiner Befehlsliste. Kamera oben,
Shell darunter, Log rechts. Shell-Tabs überleben Browsertrennung. Gesamte
Oberfläche mit dem normalen SSH-/Linux-Passwort von `me-systeme` schützen;
nicht mit einem separaten root-Passwort. Interne Bindadresse bleibt erhalten,
TLS mit lokalem oder Firmenzertifikat schützt die Passwortübertragung.

**Verworfene Alternativen:** Webserver als root (unnötige Privilegien),
Passwortkopie im Profil (PAM prüft das Linux-Konto), unabhängige Kameraprozesse
je Bedienweg (Gerätekonflikte), Live-Nachtraining bei Boxkorrektur (fehlende
getrennte Validierung). Die aktuelle Konturheuristik ist kein trainierbares
Modell. Annotationen werden auf eingefrorenen Originalbildern gespeichert.

**Umsetzungshinweis:** Ein frischer Shell-Hilfsprozess übernimmt das PTY und
führt Bash aus. Das ersetzt `forkpty` im mehrthreadigen Server, das im Test
berechtigt vor möglichen Deadlocks warnte. Ausgabe ist pro Tab auf 2 MiB
begrenzt; gekürzte Historie wird beim Wiederverbinden sichtbar gemeldet.

**Grenzen:** `run` ist in dieser Workbench fester Vorschau-/Erkennungsbetrieb,
keine Messwertfreigabe. Auto-Setup bleibt bestätigungspflichtige Einstellhilfe
(OQ-20). Hardware-Worker und TLS/WSS-Backend sind geprüft; Browser-Gesamtabnahme
unter Windows und mit echter PAM-Anmeldung bleibt offen (OQ-21).
