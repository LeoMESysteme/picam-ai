# Projekt-Historie

Dieses Dokument beschreibt Entscheidungen, die **nicht** unmittelbar aus dem
Quellcode ersichtlich sind. Format je Eintrag: Problem / Entscheidung /
Begründung / Alternativen / Konsequenz.

Messergebnisse gehören nach [VALIDATION.md](VALIDATION.md) bzw.
[TIMING.md](TIMING.md), Tagesgeschäft nach [lab_journal.md](lab_journal.md).

---

# 2026-09-24 — Kontextvorschauen in der Anleitung

## Problem

Fachbegriffe, Dokumentverweise und API-Symbole verlangen beim Lesen der
Anleitung häufig einen Seitenwechsel. Ein allgemeines Hover-Popup für alle
Links würde bei generierten API-Seiten ganze Klassen samt Quelltext anzeigen.

## Entscheidung

Zensicals Inhaltsvorschau gilt nur für Glossar und Timing: Seitenlinks zeigen
die kurze Einleitung, Abschnittslinks den jeweiligen kurzen Abschnitt.
Die Anleitung verlinkt diese Abschnitte mit festen Überschriften-IDs. Zwei
Codebeispiele erhalten native Zeilenanmerkungen. Ausgewählte API-Verweise
zeigen eine kurze Erklärung über den Markdown-Linktitel.

## Begründung

Die Vorschau übernimmt den gepflegten Text des Zielabschnitts; es entsteht
keine zweite Definition pro Begriff. Feste IDs halten Links bei Änderungen
der Überschrift stabil. Die bestehenden Zensical-Funktionen unterstützen
Maus, Tastatur und schmale Bildschirme ohne eigenen Popup-Code.

## Alternativen

Ein eigenes JavaScript-Popup könnte auch beliebige Textstellen erkennen,
würde aber eine zweite Auflösungs- und Darstellungsschicht benötigen.
Alle internen Links als Vorschau zu markieren wurde verworfen, weil die
Inhalte zu unterschiedlich lang sind. Die generierte API-Referenz wurde als
Vorschau-Ziel ausprobiert und wegen der überlangen Popups verworfen.

## Konsequenz

Neue Vorschau-Ziele brauchen einen kurzen Abschnitt mit stabiler ID und einen
Browsertest. Bei Änderungen an den referenzierten API-Signaturen sind die
kurzen Linktitel zu prüfen. Die Pflegeschritte stehen in `docs/HOSTING.md`.

---

# 2026-09-24 — OQ-Fokus aus TODO und nur noch Cloudflare-Doku

## Problem

Die OQ-Liste zeigte Nummern und Freitext, aber keine aktuelle Reihenfolge.
Eine zusätzliche Prioritätsliste hätte neben `TODO.md` gepflegt werden müssen.
Das Offline-ZIP erforderte außerdem eine zweite Navigationskonfiguration für
interaktive Seiten.

## Entscheidung

Der OQ-Index liest die aktive Aufgabenreihenfolge aus `TODO.md`, überspringt
erledigte Aufgaben und beantwortete OQ und bleibt als statische Tabelle
lesbar. Roadmap und OQ werden auf ihren bestehenden Seiten erweitert. Die
Doku wird nur noch auf Cloudflare Pages veröffentlicht; das Offline-ZIP
entfällt.

## Begründung

`TODO.md` ist bereits der priorisierte Wiedereinstieg. Ein Generator hält
die Übersicht daraus und aus `open-questions.md` synchron. Die bestehenden
Quelltabellen bewahren die Inhalte auch ohne JavaScript. Ein einziger
gehosteter Build kann Zensicals Sofortnavigation mit `site_url` verwenden.

## Alternativen

Eine manuell markierte OQ-Priorität wäre stabiler gegen Änderungen am
TODO-Format, würde aber eine zweite Reihenfolge schaffen. Nur nach Status
zu sortieren sagt nichts über die nächsten Aufgaben. Ein zusätzlicher
Offline-Build mit abgeschalteter Sofortnavigation wurde verworfen.

## Konsequenz

Wird das TODO-Format so verändert, dass die Aufgabenüberschrift nicht mehr
erkannt wird, stoppt der Doku-Build mit einer Meldung. Nach einem TODO- oder
OQ-Statuswechsel muss `scripts/oq-index.py` laufen. Die Cloudflare-Seite
bleibt durch die bestehende Forgejo-Anmeldung und Schutzprüfung abgesichert.

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

---

# 2026-09-08 — Ablesung in der Workbench: Anzeige statt Freigabe

**Entscheidung:** Der Controller liest bei bestätigter ROI jedes Kamerabild mit
`SevenSegmentReader` und führt `ReleaseGate` mit — aber ausschließlich als
**Anzeige** für den Bediener. Es entsteht kein `ValueRecord`, keine Freigabe und
keine serielle Ausgabe; `released` ist konstant `false`. Angezeigt werden der
Rohtext, die Evidenz je Stelle und vor allem die **Ablehnungsgründe** des Gates,
weil das die eigentliche Bedienhilfe ist: der Bediener sieht, woran eine
Ablesung scheitert, statt nur „unlesbar" zu lesen.

**Verworfene Alternativen:**

* *Freigabe direkt in der Workbench, inklusive Senden.* Die Freigabeschwellen
  sind Vorabdefaults und an echten Geräten nicht validiert (OQ-14), das
  GSVmulti-Telegramm ist unbekannt (OQ-07). Eine Freigabe hier hätte beides
  stillschweigend als geklärt behandelt.
* *Eigene Leseimplementierung in der Workbench.* Hätte die Kette aus Konzept §3
  gedoppelt. Stattdessen benutzt die Workbench `rectify`, `SevenSegmentReader`
  und `ReleaseGate` unverändert — dieselben Verträge, dieselbe Evidenz.
* *Zahlenformat aus dem Bild schätzen.* Konzept §4 verlangt die Bestätigung
  durch den Bediener; das Format steht deshalb im Profil (`layout`) und wird
  validiert, nicht geraten. `decimals: null` bleibt wählbar, führt aber
  ehrlich zur Ablehnung, weil der Dezimalpunkt nicht gemessen wird (OQ-17).
* *Zeitstempel der Vorschau als Messwertzeitbezug.* Die Veralterung im Gate
  bekommt CLOCK_MONOTONIC, klar als solches gekennzeichnet. Der
  Aufnahmezeitstempel liegt in SENSOR_BOOTTIME mit unbekannter Semantik; beides
  zu vermischen wäre genau der Fehler, den AGENTS.md verbietet.

**Umsetzungshinweis:** Die sieben Abtastpunkte je Ziffernstelle werden ins
Kamerabild zurückprojiziert und je nach gemessenem Zustand hell oder dunkel
gezeichnet. Weil die ROI achsparallel ist, genügt dafür eine lineare Abbildung
aus dem entzerrten Ausschnitt. Das macht Rasterfehler sofort sichtbar — ohne
diese Rückmeldung ist ein Zahlenformat kaum einzustellen.

**Grenzen:** Die Bedienzeilen für das Zahlenformat und die Tests des Lesepfads
fehlen noch (Stand in `docs/status.md`). Geprüft ist der Kern nur gegen eine
synthetisch gerenderte Anzeige — synthetische Daten ergänzen nach Konzept §9,
sie zählen nie zum Testset.

---

# 2026-09-09 — Perspektivisches ROI-Quad und kurze Controller-Sperren

**Entscheidung:** Das Profil behält die achsparallele `roi` als Hülle für
Qualitätsmetriken und Abwärtskompatibilität, ergänzt aber in Schema 2 ein
geordnetes `roi_quad` aus vier normierten Ecken. Der OCR-Ausschnitt wird aus
diesem Quad entzerrt; Profile aus Schema 1 werden beim Laden aus ihrem Rechteck
verlustfrei migriert. Bildsuche, Overlay und JPEG-Kompression laufen außerhalb
des Controller-Locks. Nach Bestätigung endet die Vollbildsuche, während die
OCR-Vorschau mit eigener 5-Hz-Rate weiterläuft.

**Verworfene Alternativen:**

* `roi` selbst je nach Version als Rechteck oder Polygon zu überladen: Jeder
  Verbraucher müsste den Typ erraten; eine getrennte kanonische Quad-Geometrie
  hält den Vertrag eindeutig.
* Nur Drehwinkel plus Rechteck zu speichern: korrigiert Rotation, aber keine
  perspektivische Trapezverzerrung.
* Die gesamte Verarbeitung unter dem Controller-Lock zu lassen und nur die
  Bildrate zu senken: Status und Shutdown blieben im ungünstigen Moment an
  OpenCV gebunden.
* Einen Web-Abschaltknopf anzubieten: unnötig großer externer
  Zustandsänderungspfad. `dispread stop` bleibt auf den privaten Unix-Socket
  begrenzt.

**Konsequenz:** Vier Ecken sind im eingefrorenen Original direkt editierbar;
Zellen und Segmentpunkte werden perspektivisch zurückgezeichnet. Alte Profile
bleiben ladbar. Die Änderung verbessert Ausrichtung und Bedienbarkeit, ist aber
kein Training und behebt die reale VFD-Glyphenabweichung aus OQ-23 nicht.

---

# 2026-09-09 — Separater, sichtbarer OCR-Innenrahmen

**Entscheidung:** Profilschema 3 ergänzt ein normiertes `ocr_box` innerhalb des
perspektivisch entzerrten `roi_quad`. Das äußere Quad beschreibt die physische
Displayebene und ihre Perspektive; der innere Rahmen beschreibt ausschließlich
den Bereich, über den Vorzeichen- und Ziffernzellen verteilt werden. Im
eingefrorenen Browserbild werden Rahmen, Zellen und dieselben sieben
Abtastpunkte gezeichnet, die `SevenSegmentReader` tatsächlich misst.

**Verworfene Alternativen:** Nur das äußere Quad enger um die Ziffern zu legen
vermischt Perspektivkante und Lesergrenze und wird bei Blenden/Leerraum
unpräzise. Frei editierbare Grenzen je einzelner Zelle würden viele kaum
prüfbare Profilparameter erzeugen und könnten eine Anzeige auf genau einen
Frame überanpassen. Eine automatisch als bestätigt gespeicherte Grenzerkennung
aus dem Einzelbild würde helle Segmente, Einheit und Reflexionen ohne reale
Validierung verwechseln; unbekannte Eingaben müssen abgelehnt statt geraten
werden.

**Konsequenz:** Die manuelle Framekalibrierung ist direkt wirksam und visuell
nachprüfbar. Schema-1/2-Profile bleiben durch Migration mit vollem `ocr_box`
ladbar. Automatische Vorschläge können später auf gelabelten Realbildern
ergänzt werden, dürfen aber die Bedienbestätigung nicht ersetzen.

**Korrektur nach Bedienprüfung:** Das zunächst beim Einfrieren kopierte Raster
blieb bei Änderungen an `layout` stehen, während die allgemeine Profilrevision
`Enter` mit „Modus/Profil geändert“ ablehnte. Reine Rasteränderungen übernehmen
nun die Revision des offenen Editierbilds und `snapshot()` liefert das aktuelle
Raster für den Browser. Bild- oder Kamerageometrieänderungen tun das bewusst
nicht. Die feste Dezimalposition wird als Kalibriermarker gezeichnet, aber
weiterhin nicht als optisch erkannt ausgegeben.

---

# 2026-09-11 — OCR-Selbstkalibrierung: verankerte Werkzeuge statt genereller OCR/Klassifikator

## Problem

Die Ausgangsmessung vom 2026-09-11 (`sevenseg/2` gegen alle gelabelten realen
Annotationen, siehe [VALIDATION.md](VALIDATION.md)) zeigte, dass Rastergeometrie,
Segmentschwellen und Anzeigepolarität weiterhin von Hand kalibriert werden
mussten und dabei fehleranfällig waren. Für
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md)
waren mehrere naheliegende Alternativen zu bewerten, bevor Autofit
(`fit_layout`) und Nachführung (`QuadTracker`) gebaut wurden.

## Entscheidung

Der Plan bleibt bei Werkzeugen, die **am bestätigten manuellen Ausschnitt
verankert** sind — Autofit aus einem einmal getippten Sollwert und begrenzte
Nachführung eines bereits bestätigten Quads — statt einer generellen,
unverankerten OCR- oder Klassifikatorlösung.

## Begründung / Alternativen

- **ssocr** (`https://www.unix-ag.uni-kl.de/~auerswal/ssocr/`, GPLv3, C, nur
  CLI) — vom Bediener vorgeschlagen. Verworfen als Primärpfad: liefert nur die
  Ziffernfolge, keine Per-Segment-Evidenz, und `ReleaseGate.evaluate` verlangt
  `contrast` und `min_margin` aus der Segmentanalyse ([OQ-19](open-questions.md)).
  Dazu Subprozessgrenze je Bild und eigene Ziffernsegmentierung, die den
  bereits bestätigten Rasterhinweis nicht nutzt. Als späteres, unabhängig
  implementiertes Vergleichsbackend neben Tesseract ([OQ-15](open-questions.md))
  weiterhin denkbar.
- **Gitterfreier Per-Ziffer-Decoder** (ssocr-Logik in-process, Raster je Bild
  neu herleiten). Verworfen, weil er [OQ-25](open-questions.md) in den
  **Lesepfad** erbt: `fit_ocr_box` wählt an dem realen Netzteil konsequent die
  falsche Zeile (untere `A`-Anzeige statt oberer `V`-Anzeige, IoU 0,0 an
  beiden Bildern). Als Vorschlag ist das folgenlos, im Lesepfad wäre es eine
  stille Ablesung der falschen Messgröße — die Haupt-/Nebenanzeige-
  Verwechslung aus `Konzept.md` §7. Die brauchbare Hälfte (Selbstskalierung je
  Ziffer) ist stattdessen **verankert** aufgenommen: `fit_layout` optimiert
  nur innerhalb einer Umgebung des bereits bestätigten Rasters.
- **Kleiner Ziffernklassifikator, rein synthetisch trainiert.** Umgeht das
  Annotationsproblem, nicht das Datenproblem — `Konzept.md` §9 und der
  Docstring von `layout.py` sagen beide, dass synthetische Daten ein reales
  Testset ergänzen und nie ersetzen. Dazu: Softmax ist keine
  Fehlerwahrscheinlichkeit (`AGENTS.md`), die Freigabe bräuchte einen neuen
  Evidenzvertrag ([OQ-19](open-questions.md)), und der IMX500-*Converter*
  fehlt auf dem Pi ([OQ-11](open-questions.md)). Gehört nach ROADMAP-P8, nicht
  in diesen Plan.
- **Rasterfeinschliff je Bild** (Projektionsprofil zieht die Zellgrenzen pro
  Frame nach). Aus diesem Plan gestrichen: Phase C (`QuadTracker`) fängt
  starre Bewegung des ganzen Quads bereits ab, und ein Feinschliff ohne
  Verankerung am bestätigten Raster bringt nur bei nicht-starren Änderungen
  im Ausschnitt etwas — und würde ohne Verankerung dieselbe
  Haupt-/Nebenanzeige-Verwechslung aus OQ-25 erben. Als eigener Punkt
  festgehalten in [OQ-27](open-questions.md), nicht gebaut.

## Konsequenz

`fit_layout` (`src/dispread/ocr/autofit.py`) und `QuadTracker`
(`src/dispread/track.py`) bleiben beide auf den einmal bestätigten manuellen
Ausschnitt bezogen — kein Ersatz für `manual_roi`, kein automatisch
übernommener Wert ohne diese Verankerung. Eine reale Messschwäche entdeckt:
`thickness_ratio`/`inset_ratio` sind für den aktuellen Punktabtast-Decoder
strukturell wirkungslos (nie gelesen in `sevenseg.py`) — offen als Teil von
[OQ-28](open-questions.md). Die Nachführungsschwellen (`max_shift`,
`max_rotation_deg`, `min_score`) bleiben unvalidierte Vorabdefaults —
[OQ-26](open-questions.md).

---

# 2026-09-18 — Datensatz-Sammelmodus: eigener Rohbild-Sammelpfad statt Lockerung der produktiven ROI-/Clip-Voraussetzungen

## Problem

Reale, unkalibrierte Prüfbilder sollten im Browser gesammelt werden können,
ohne Segmentraster oder bestätigtes Produktionsprofil vorauszusetzen. Die
bestehende Clipaufnahme (`Controller._clip_start`) verlangt genau das:
bestätigte Geometrie, Livebild und einen konstanten sichtbaren Wert je Clip.

## Entscheidung

Ein vollständig eigenständiger Speicher- und Bedienpfad
(`src/dispread/workbench/datasets.py`, `dataset_capture.py`, `dataset.js`)
statt einer Lockerung der bestehenden `roi`-/`clip.start`-Voraussetzungen.
Eigene Geräteregistrierung mit UUID und Split-Sperre, eigene Capture-Tokens
(getrennt vom kleinen ROI-Editor-Cache `Controller.frames`), eigenes
`DatasetStore`-Lock, eigene `dataset.*`-Kommandos über das bestehende
`/command`.

## Begründung / Alternativen

- **`clip.start`/`clip.stop` um einen unkalibrierten Modus erweitern.**
  Verworfen: hätte bedeutet, `confirmed`-Prüfungen dort probeweise zu
  umgehen — genau die Art Lockerung, die AGENTS.md für Freigaberegeln
  ausschließt, und die bestehenden Clip-Regressionstests (Manifest,
  Schreibfehlerbehandlung, `write_failures`) hätten für einen zweiten,
  unverwandten Anwendungsfall mitgepflegt werden müssen.
- **Zielbox/Label direkt in `ValueRecord` oder das Profilschema aufnehmen.**
  Verworfen: `ValueRecord` ist der stabile Vertrag aus Konzept.md §8 und
  darf laut Aufgabenstellung nicht angefasst werden; ein getipptes Label ist
  zudem strukturell etwas anderes als ein erkannter Wert und darf nach
  Konzept.md §7 niemals in `ValueReader`/`ReleaseGate` einfließen.
- **Bestehenden `Controller.frames`-Editor-Cache für Capture-Tokens
  wiederverwenden.** Verworfen: der ist an Profil-/Editorlogik gekoppelt
  (Revision, `roi`-Bestätigung) und auf vier Einträge mit stiller
  FIFO-Verdrängung ausgelegt — der Sammelmodus braucht dagegen eine
  explizite Ablehnung statt Verdrängung bei Erreichen des Limits
  (`MAX_OPEN_CAPTURES`).

## Konsequenz

Der Sammelmodus ergänzt den bestehenden Betriebspfad, ohne dessen
Freigaberegeln zu berühren: `ValueRecord`, `ReleaseGate` und
`TelegramFormatter` sind unverändert, Capture/Save fassen `self.config`,
`self.tracker` und `self.reading` nicht an (siehe Tests in
`tests/test_dataset_capture.py`). Kosten: zwei parallele Speicherpfade
(`clips/` und `datasets/samples/`) mit ähnlicher, aber bewusst nicht
gemeinsamer Schreiblogik — vertretbar, weil beide unterschiedliche
Garantien geben (ein Clip ist ein konstanter Wert über die Zeit, eine
Sample-Probe ein Einzelbild mit Zielbox).

---

# 2026-09-23 — Doku-Seite: Zensical statt KI-Wiki, Hosting auf Cloudflare Pages mit Forgejo-Anmeldung

## Problem

Die Doku ist umfangreich (> 20 000 Zeilen Markdown), hatte aber keine
Navigation, keine Suche und keine API-Referenz. Wer nur Zugriff auf das
Forgejo-Repo hat, soll sie als Web-Oberfläche lesen können.

## Entscheidung

* **Generator: Zensical** über die vorhandenen Markdown-Dateien, dazu eine
  API-Referenz aus den Docstrings (mkdocstrings). Kein KI-generiertes Wiki.
* **Build:** Forgejo-Runner auf dem Pi (Label `picam-docs`, Host-Modus,
  per systemd abgeschottet). Ergebnis ist immer ein Offline-ZIP am Lauf.
* **Hosting: Cloudflare Pages mit einer eigenen Pages Function** als
  Zugriffsschutz. Anmeldung über Forgejo, Zugang nur mit Leserecht am Repo.
  Live geht ein Stand nur nach bestandener Schutzprüfung auf einem
  Prüfstand. Details in [HOSTING.md](HOSTING.md).

## Begründung / Alternativen

- **KI-Wikis** (Repowise, FSoft CodeWiki, deepwiki-open, Google Code Wiki,
  DeepWiki). Verworfen: Sie erzeugen plausibel klingende Fehler, und im
  Kalibrierlabor ist eine falsche Beschreibung schlimmer als eine fehlende.
  Repowise schrieb über `src/dispread` nachweislich Unzutreffendes. Die
  gehosteten Varianten können nur öffentliche GitHub-Repos.
- **MkDocs + Material.** Verworfen: Material ist seit November 2025 im
  Wartungsmodus, MkDocs 2.0 streicht Plugins und damit mkdocstrings. Zensical
  ist der Nachfolger vom Material-Team und liest dieselbe Konfiguration.
  **Sphinx + MyST** wäre die konservative Rückfallebene, die Markdown-Dateien
  bleiben dafür unverändert.
- **Hosting in Forgejo selbst.** Nicht möglich: Forgejo 15 hat keine Pages,
  HTML aus dem Repo kommt als `text/plain` mit `nosniff`. Ein HTML-Renderer im
  iframe (`app.ini`) hat offene Fehler und trägt keine mehrseitige Seite.
  Das **Wiki** trüge nur schlichtes Markdown ohne Zensical-Oberfläche.
- **Eigener Dienst** (Forge-Pages, oauth2-proxy). Technisch am saubersten,
  die Daten blieben im Haus. Verworfen, weil es keinen zusätzlichen Server
  geben soll. Den Pi als Webserver wollten wir nicht, weil er das Messgerät ist.
- **Cloudflare Access (Zero Trust)** vor Pages. Zuerst gewählt, dann
  verworfen: Auch der kostenlose Plan verlangt eine hinterlegte
  Kreditkarte. Die Pages Function prüft zudem genauer, nämlich die
  Repo-Rechte statt einer E-Mail-Regel. Dafür ist ihr Anmelde-Code selbst
  geschrieben statt ein Fertigprodukt.
- **Gemeinsames Passwort** (Basic Auth in der Function). Verworfen: Es wäre
  nicht an Forgejo-Konten gebunden, und wer das Projekt verlässt, kennt es weiter.
- **GitHub Pages.** Verworfen: ohne Enterprise Cloud öffentlich.
- **Netlify, Vercel, Codeberg Pages.** Verworfen: Zugriffsschutz nur
  kostenpflichtig, Hobby-Tarif nicht für gewerbliche Nutzung, bzw. öffentlich
  und nur für Open Source gedacht.
- **GitLab.com Pages** mit Zugriffsschutz im Free-Tarif. Verworfen: Jeder
  Leser bräuchte ein GitLab-Konto, und private Gruppen sind seit August 2026
  auf 5 Nutzer begrenzt.

## Konsequenz

Die Doku liegt zusätzlich bei Cloudflare. Der Schutz hält Fremde fern, nicht
den Anbieter. Zugelassen ist genau, wer das Repo in Forgejo lesen darf.
Entzogene Rechte wirken spätestens nach 8 h (Sitzungsdauer). Lehre aus einem
ersten, von Hand angelegten und ungeschützten Pages-Projekt: Kein Deploy ohne
automatische Schutzprüfung davor.
Zensical ist jung (0.0.x) und deshalb in `requirements-docs.txt` gepinnt.
