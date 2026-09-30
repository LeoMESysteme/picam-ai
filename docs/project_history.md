# Projekt-Historie

Dieses Dokument beschreibt Entscheidungen, die **nicht** unmittelbar aus dem
Quellcode ersichtlich sind. Format je Eintrag: Problem / Entscheidung /
Begründung / Alternativen / Konsequenz.

Messergebnisse gehören nach [VALIDATION.md](VALIDATION.md) bzw.
[TIMING.md](TIMING.md), Tagesgeschäft nach [lab_journal.md](lab_journal.md).

---

# 2026-09-30 — Rasterversatz unabhängig vom Leser messen, als Pflichtprüfung vor jeder Ernte

## Problem

Abnahme 2 des Dot-Matrix-Lesers ergab 0 falsch, aber 85,8 % abgelehnt.
Ursache waren die Punktraster der Profile, nicht der Leser. Die von Hand
mit `latfit.py` angepassten Raster von `ab3`/`ab4` (auch `ernte1`, `auf2`,
`auf3`) lagen 0,4–0,9 Punktspalten neben den Punktmitten, geschert oder mit
falschem Punktabstand. Unauffällig blieben trotzdem:
* das Restmaß der Anpassung (0,17 / 0,26),
* die Leerzellenprüfung,
* der Zellen-Bias,
* die Import-Ausrichtung.

## Entscheidung

* **Eigenes Maß** (`dispread.lattice_offsets`): Bei bekanntem Text
  korreliert es die Abtastung im Quellbild je Zelle und Halbzelle mit dem
  ROM-Muster, über eine Blende von ±0,3 Punkt. Die Feinsuche nimmt die Mitte
  des Plateaus. Waagerecht zählt die Halbzelle (zeigt Scherung), senkrecht
  die ganze Zelle (beim `+` messen die Halbzellen entgegengesetzt).
* **Werkzeug** `scripts/profile-regrid.py`:
  * misst an Proben (`measure`) oder an Standbildern (`still`),
  * korrigiert das Quad (`refine`, `still --out-quad`), angepasst an der
    einen Hälfte der Bilder und geprüft an der anderen,
  * bestätigt nach Sichtprüfung (`confirm`).
* **Profilzuordnung:** Ein korrigiertes Profil ersetzt ein in Proben
  eingebettetes Profil nur über `replaces`, also mit ausdrücklich genannter
  Prüfsumme des alten.
* **Grenze vor jeder Ernte:** 0,15 Punktspalten. Im Einrichtungsassistenten
  ist das die Prüfung 2j: FEHLER über 0,25, WARNUNG über 0,15.

## Begründung und Alternativen

* **Punktschatten-Abzug** (`bg_closing_shadow_v1`): verworfen und
  zurückgenommen. Er behandelte das Symptom, verfehlte das vorab
  festgelegte Kriterium (`ab4` weiter 0/119) und verschlechterte `auf3`
  von 63 auf 1 richtige Probe.
* **Verschiebungssuche des Lesers vergrößern:** verworfen. Die Suche deckt
  ±0,24 Punktspalten ab. Eine größere Suche würde bei korrekten Rastern
  benachbarte Zeichen näher an die Vorlagen bringen und die Trennschärfe
  kosten.
* **Restmaß oder Zuordnungsquote der Anpassung als Kriterium:** verworfen.
  Falsches und richtiges Raster ergaben dasselbe Restmaß.
* **Profile direkt überschreiben:** verworfen. Die Proben tragen die
  Prüfsumme ihres Profils, eine stille Ersetzung wäre nicht
  nachvollziehbar.

## Konsequenz

* Abnahme 2 hat falsche Profile geprüft. Ihr Ergebnis bleibt stehen, sagt
  aber nichts über den Leser aus.
* Mit korrigierten Rastern sank die Schwelle `d_max` von 2,6 auf 1,9.
  Abnahme 3 über zwei neue, mit der Prüfung eingerichtete Aufstellungen ist
  bestanden: 215/215, 0 falsch.
* `latfit.py` lag auch bei `ab5`/`ab6` wieder 0,22 bzw. 0,36 daneben. Die
  Prüfung ist also nötig, nicht nur vorsichtig.

# 2026-09-30 — Bekannter DUT-Zellentext als unabhängige Rasterprüfung

## Problem

Das Restmaß der geometrischen Punktanpassung erkannte um bis zu 0,9
Punktspalten verschobene Raster nicht. Eine Nachführung nur anhand dieser
Punktkandidaten würde denselben Fehler wiederholen.

## Entscheidung

Prüfung 2j nutzt den bekannten Anzeigetext aus dem eingehenden GSV-2AS-
Telegramm oder einer ausdrücklichen Offline-Angabe. Sie misst den
ROM-Korrelationsversatz je Halbzelle waagerecht und je ganzer Zelle
senkrecht. Die automatische Quad-Nachführung wird erst übernommen, wenn
das zurückgehaltene zweite Standbild einen kleineren maximalen Versatz
zeigt und die geometrischen Prüfwerte für das neue Quad neu berechnet
werden. Randpixelmitten 399/159 gelten in Anpassung, Entzerrung und
Versatzmessung einheitlich.

## Begründung und Alternativen

Das Punktraster aus Helligkeitsminima allein wurde verworfen, weil scharfe
Punktränder falsche Minima erzeugen. Den Text aus dem Dot-Matrix-Leser
abzuleiten wäre zirkulär; der Eingangsstream liefert ihn unabhängig.
Ein Quad allein auszutauschen und die alten RMS-/Zuordnungswerte zu
behalten wurde verworfen, weil dann die Prüfung veraltete Zahlen zum
neuen Quad anzeigen würde. Für Offline-Arbeit ist der exakt neunstellige
Zellentext ein expliziter Parameter oder eine Datei; unerkannte Zeichen
werden abgelehnt. Die Schwellen 0,15/0,25 sind Vorabwerte.

## Konsequenz

Ein Rasterversatz-FEHLER oder verbleibender Gesamt-FEHLER erzeugt keinen
automatischen Vorschlag. Jedes Standbild braucht genügend belastbare
Zeichenpunkte; ein unlesbares zweites Bild wird nicht vom ersten verdeckt. Eine
frühere Raster-FEHLER-Vorprüfung darf die zweite Aufnahme noch zulassen,
damit die Nachführung diesen Fehler beheben kann. Andere harte
Vorprüfungen beenden den Lauf weiterhin vor der Wartezeit.

---

# 2026-09-30 — Startseite als vollständiger Doku-Wegweiser

## Problem

Die Zensical-Startseite zeigte noch die außer Betrieb genommene IMX500 als
aktive Kamera und verlinkte nur wenige Dokumente. Die tägliche Pflege prüfte
rotierende Anleitungsseiten, aber die Startseite nicht bei jedem Lauf.

## Entscheidung

Die Startseite enthält direkte Links auf alle Navigationsziele und Wege nach
Aufgabe. Drei thematische Vertiefungen erklären Messpfad, Zeitstempel sowie
Daten und Abnahme, jeweils mit Verweisen auf maßgebliche Anforderungen, Code
und Messprotokolle. Der Pflege-Audit prüft Startseite und Navigation bei jedem
Lauf. Der Codex-Aufruf behält Sessionzustand, damit lesende Subagents starten
können.

## Begründung und Alternativen

Nur zusätzliche Links in der Seitenleiste hätten die erste Seite nicht zu
einem verlässlichen Einstieg gemacht. Alle Spezialthemen in ein einziges
langes Handbuch zu setzen, hätte die bestehenden Zielseiten und stabilen
Abschnittsanker doppelt erklärt. Die drei kurzen Vertiefungen verbinden
stattdessen bestehende Quellen. Für Subagents wurde `--ephemeral` verworfen:
ein lokaler Probelauf zeigte beim Spawn „no thread with id“; ohne den Schalter
legte Codex einen Kind-Thread an.
Mit `--ignore-user-config` war die projektspezifische Rolle `docs_reader`
zunächst unbekannt; die explizite `agents.docs_reader.config_file`-Angabe
stellte sie in einem zweiten Probelauf bereit, ohne die übrige
Benutzerkonfiguration zu laden.

## Konsequenz

Neue Navigationsseiten brauchen einen direkten Startseiten-Link. Ein
Browsertest prüft das. Sessiondateien des automatischen Codex-Laufs liegen im
geschützten `CODEX_HOME` des Runner-Benutzers; das Publish-Gate bleibt
unverändert.

---

# 2026-09-24 — Keine automatische URL-Nachfuehrung in Zensical

## Problem

Mit `navigation.tracking` wurde beim mobilen Wechsel von der Anleitung zum
Glossar gelegentlich der Anker des Ausgangsabschnitts in die Ziel-URL
uebernommen. Der Link selbst zeigte korrekt auf `#value-record`.

## Entscheidung

`navigation.tracking` ist deaktiviert. `navigation.instant` und die
Kontextvorschauen bleiben aktiv.

## Begründung und Alternativen

Der bestehende Mobiltest scheiterte mit Tracking in 2 von 5 Wiederholungen
und bestand ohne Tracking 8 von 8 Mal. Eine Aenderung am Link oder ein
groesserer Eingriff in Zensicals Navigationsskript wuerde die Ursache nicht
gezielter behandeln. Die automatisch nachgefuehrte Abschnitts-URL ist fuer
die Doku weniger wichtig als verlaessliche Querverweise.

## Konsequenz

Beim Scrollen wird der Hash nicht mehr automatisch auf den sichtbaren
Abschnitt gesetzt. Explizite Links auf Abschnittsanker bleiben beim
Seitenwechsel stabil.

---

# 2026-09-24 — Systemdienst erlaubt Codex-Namespace

## Problem

Die Codex-CLI nutzt `bwrap` fuer ihre Dateisystem- und Netzwerk-Sandbox.
Ein vollstaendiger Namespace konnte unter den urspruenglichen systemd-
Regeln weder den `NETLINK_ROUTE`-Socket oeffnen noch `/proc` mounten. Zwei
Vorschaulaeufe konnten deshalb keine Quelldatei pruefen.

## Entscheidung

Der separate Runner erlaubt `AF_NETLINK` und verzichtet auf
`ProtectKernelTunables`, `ProtectKernelLogs` und `ProtectHostname`. Gezielt
ausgefuehrte Transienteinheiten reproduzierten jeden Fehler und bestaetigten
den `bwrap`-Start mit den verbleibenden Dienstregeln. Der Audit-Gate verlangt
zusaetzlich eine erfolgreiche Quellpruefung durch Codex.

## Begründung und Alternativen

Die Codex-Sandbox abzuschalten haette den Agenten unbeschraenkt auf dem Pi
arbeiten lassen und wurde verworfen. Die weiterhin aktiven Grenzen umfassen
einen eigenen Unix-Benutzer, `ProtectSystem=strict`, `ProtectHome`,
`PrivateDevices`, `NoNewPrivileges`, beschraenkte Schreibpfade und CPU-/RAM-
Limits. Die drei entfernten Optionen waren in den Tests mit dem Namespace-
Start unvereinbar.

## Konsequenz

Die vom Modell gestarteten Shell-Aufrufe bleiben in der Codex-Sandbox.
Ein Doku-Audit ohne erfolgreiche Shell-Pruefung kann nicht mehr als aktueller
Stand gespeichert werden.

---

# 2026-09-24 — Anmeldedatei fuer den getrennten Codex-Runner

## Problem

Die Codex-CLI auf dem Pi brauchte eine dauerhafte Anmeldung. Der vorgesehene
Device-Code-Login war fuer das vorhandene ChatGPT-Konto nicht freigegeben.

## Entscheidung

Die bestehende lokale `auth.json` wurde als separate Datei mit Besitzer
`picam-codex-runner` und Modus `0600` in dessen geschuetztes `CODEX_HOME`
kopiert. Der Runner nutzt damit dasselbe ChatGPT-Konto, haelt seine
Anmeldedatei aber unter einer anderen Unix-Identitaet. Bei Anmeldefehlern
wird die Kopie erneut geprueft beziehungsweise erneuert.

## Begründung und Alternativen

OpenAI dokumentiert die Dateikopie als Ausweichweg fuer Headless-Geraete.
Eine API-Key-Anmeldung haette eine getrennte Platform-Abrechnung und einen
neuen Schluessel erfordert; Device-Code-Login war nicht verfuegbar. Ein
gemeinsam beschreibbares `auth.json` wurde wegen der Benutzertrennung
verworfen.

## Konsequenz

Die Anmeldung funktioniert unter dem Dienstbenutzer; eine kleine Anfrage
an `gpt-6-luna` war erfolgreich. Die Datei enthaelt Zugangstoken und darf
weder ins Repo noch in Action-Artefakte oder Logs gelangen.

---

# 2026-09-24 — Unbeaufsichtigte Zensical-Pflege auf getrenntem Pi-Runner

## Problem

Der bisherige Claude-Job wurde per `@reboot` auf dem Pi gestartet, arbeitete
auf lokalen Branches und veröffentlichte seine Commits nicht. Die neue
Zensical-Anleitung und deren Kontextvorschauen brauchen eine Pflege, die
Quellcodeänderungen nachverfolgt und das veröffentlichte Ergebnis prüft.

## Entscheidung

Forgejo plant einen täglichen Workflow. Ein zweiter, repo-gebundener Runner
läuft auf demselben Pi unter eigenem Unix-Benutzer und hält eine eigene
Codex-CLI-Anmeldung. Der Job arbeitet auf `master`, prüft die Anleitung
anfangs in täglichen Dreierpaketen und ruft Codex danach nur bei Änderungen
oder für den wöchentlichen Anleitungsaudit auf. Er pusht nur nach
erfolgreichem Site-Build und Browsertests. Der Push verwendet einen
eingeschränkten Bot-Token, damit der vorhandene Cloudflare-Workflow startet.

## Begründung und Alternativen

Forgejo Actions benötigen einen ausführenden Runner; Cloudflare Pages bietet
keinen dauerhaften CLI-Arbeitsplatz mit persistentem Codex-Login. Ein Runner
auf dem Forgejo-NAS wurde erwogen; der Nutzer hat den Raspberry Pi als Ort
gewählt. Der vorhandene Doku-Runner bleibt getrennt, damit dessen Jobs keine
Codex-Anmeldedatei lesen können. Der automatische Forgejo-Workflow-Token
wurde für den Push verworfen, weil seine Commits keine weiteren Workflows
auslösen.

## Konsequenz

Die beiden Pi-Runner sind ressourcenbegrenzt und haben getrennte
Identitäten. Der Codex-Job setzt eine einmalige Runner-Registrierung,
Bot-Berechtigung und Geräteanmeldung voraus. Bei Ausfall bleibt `master`
unverändert; der Forgejo-Lauf zeigt den Fehler.

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
# 2026-09-25 — Logitech StreamCam statt Raspberry Pi AI Camera (IMX500)

## Problem

Die IMX500 war über Wochen der Engpass jeder Kamerasitzung. Die
RP2040-Brücke zwischen Pi und Sensor blieb beim Streamstart hängen (OQ-22):
zuerst nach 20–25 Starts je Boot, am 2026-09-24 schon beim 8. Start, und
nach einem Warmreboot war nicht einmal der erste Start sicher. Jede Sitzung
musste deshalb mit einem Streambudget und wenigen Starts geplant werden. Ein
Wedge kostete einen Reboot. Am 2026-09-25 fiel die Kamera zusätzlich
**mitten in einem laufenden Stream** aus (I2C-Fehler `-121`,
„Camera frontend has timed out"), nachdem sie mechanisch bewegt worden war.
Der Fokus ließ sich nur mechanisch am Objektiv einstellen, und die
AI-Funktionen des Sensors nutzte das Projekt nicht (die mitgelieferten
Modelle taugen nicht für Messverstärker-Displays, der Primärpfad ist die
bestätigte manuelle ROI).

## Entscheidung

Nutzerentscheidung 2026-09-25: offizieller Wechsel auf die **Logitech
StreamCam** (USB 3, UVC, USB-ID `046d:0893`), angebunden über V4L2
(`v4l2://`, `UvcSource`). Die IMX500-Pfade (`picamera2://`, `imx500://`,
Streamstart-Budget, ScalerCrop) sind außer Betrieb. Doku und Verweise auf
die IMX500 bleiben für eine mögliche Rückumstellung erhalten, sind aber als
historisch gekennzeichnet. Spec
`docs/superpowers/specs/2026-09-25-streamcam-switch-design.md`, Plan
`docs/superpowers/plans/2026-09-25-streamcam-switch.md`.

## Begründung

Ein Test am 2026-09-25 zeigte, dass die StreamCam alles liefert, was die
Ernte braucht: 1920×1080 YUYV mit 25–30 fps, Fokus per Software
(`focus_absolute` = 48 am besten bei abgeschaltetem Autofokus), etwa
3,6 px je Punktspalte des GSV-Sensor-Glases (Schwelle 2,6 px) und je Bild
einen V4L2-Pufferzeitstempel in CLOCK_MONOTONIC. Es gibt keinen
Streamstart-Wedge und kein Startbudget, und der Fokus lässt sich
reproduzierbar im Profil speichern.

## Alternativen

* **IMX500 behalten und OQ-22 weiter verfolgen** (Testplan mit dem
  Kernel-Maintainer: Standard-cmdline, dann Kernel-Zweig
  `naushir/linux#imx500_tests`). Verworfen: offener Ausgang, jeder Versuch
  kostet Reboots, und der Ausfall mitten im Stream wäre damit nicht
  erklärt.
* **Kameradienst**, der die IMX500 einmal beim Boot öffnet und Bilder
  verteilt (vorgemerkte Idee vom 2026-09-25). Verworfen: umgeht nur den
  Wedge beim Start, nicht den Ausfall im Stream, und hätte 3–4 Tage Arbeit
  gekostet.
* **Fokus der IMX500 mechanisch nachstellen**, sonst alles lassen.
  Verworfen: löst weder Wedge noch Ausfall.

## Konsequenz

* Kamerazeitstempel liegen jetzt in CLOCK_MONOTONIC statt BOOTTIME
  (`TimeBaseKind.V4L2_MONOTONIC`). Jede Aufnahme misst den Versatz
  BOOTTIME − MONOTONIC zu Beginn und Ende (`session.json`), und alle
  Auswerter rechnen über `records.to_boottime_ns` um. Fehlt der Versatz oder
  lag ein Suspend dazwischen, wird abgelehnt.
* Die Semantik des UVC-Zeitstempels (Belichtung oder Pufferempfang) ist
  offen (OQ-43). Deshalb ist vor der ersten StreamCam-Ernte eine
  **Timing-Kalibrierung Pflicht** (`timing-calibration.py`,
  `var/calibration/timing-streamcam.json`). Das Schutzfenster M = 695 ms der
  IMX500 gilt nicht mehr.
* Profile haben Schema 3 mit einem `camera`-Block (Fokus, Belichtung,
  Weißabgleich, Verstärkung). IMX500-Profile (Schema 2) bleiben für Import
  und Datensatz lesbar, `harvest.py` lehnt sie für neue Ernten ab.
* Die Kamera der Werkbank (`dispread serve`) ist außer Betrieb, bis die
  StreamCam dort angebunden ist; `--simulate` läuft weiter.
* Es gibt keine Treiber-Bildnummer mehr (`sensor_sequence` fehlt).
  Aussetzer erkennt `frame_gaps` in `session.json` über die Zeitstempel.

# 2026-09-29 — Aufnahme zuerst in den RAM, dann auf die SD-Karte

## Problem

Bei den StreamCam-Ernten stieg der Anteil verworfener Bilder von 0–1 % am
2026-09-28 auf 16–34 % am 2026-09-29. Ein Subagent hat das gemessen:
* Die SD-Karte, ein No-Name-Modell, schafft mit fsync 7,1 MB/s. Die
  Aufnahme braucht 5,9 MB/s.
* Zeitweise schreibt die Karte sekundenlang gar nicht. In `sc6` gab es 14
  Stillstände über 0,5 s, bis etwa 42 s am Stück.
* Die Kodierung (JPEG q95, 13 ms je Bild, GIL frei) und die CPU sind nicht
  der Engpass.
* Ein Nebeneffekt: Weil der serielle Thread `commands.jsonl` selbst schrieb,
  verlängerten die Hänger die GSV-Sendepausen. Daraus entstanden lange
  `telegrammluecke`-Ablehnungen.

## Entscheidung

`sync-record.py --staging-root /dev/shm` für Ernten. Die Aufnahme läuft
vollständig in tmpfs, erst danach wird mit fsync auf die Karte kopiert.
`commands.jsonl` bekommt einen eigenen Schreiber. Der Platz wird vorab
geprüft, ein Kopierfehler lässt die Zwischenablage stehen. Die Bildrate
bleibt bei 15 fps.

## Alternativen

* **Größere Warteschlange:** Um 42 s zu überbrücken, wären etwa 630 Bilder
  nötig, also 3,9 GB BGR. Zudem lag die mittlere Schreibrate von 3,8 MB/s
  unter dem Bedarf. Verworfen.
* **Mehrere Schreiber-Threads:** Die Kodierung ist nicht der Engpass.
  Verworfen.
* **Niedrigere JPEG-Qualität:** Das würde die Eingangsbilder des
  Dot-Matrix-Lesers unbemerkt verschlechtern. Nur mit eigener `loo`-Prüfung
  denkbar, vorerst verworfen.
* **Ernte mit 5 fps:** Der Import wählt ohnehin höchstens 3 Bilder je
  Plateau. Das bleibt eine Option, falls der RAM knapp wird. Zurückgestellt,
  bis eine echte Aufnahme mit Zwischenablage vorliegt.
* **Nur den Ausschnitt um das Quad speichern:** verlustfrei und klein, aber
  ein größerer Umbau (Koordinaten in Import, Profil und Referenzbild).
  Später.
* **Schnellere Karte oder USB3-SSD für `var/`:** empfohlen, aber
  Hardware. Die Softwaremaßnahme hilft unabhängig davon.

## Konsequenz

* Eine Ernte belegt während der Aufnahme bis zu etwa 2,3 GB RAM (geschätzt).
* Ist nicht genug frei, lehnt `sync-record.py` vor dem Start ab.
* Das Kopieren nach der Aufnahme dauert einige Minuten.
* Der Nachweis an der Kamera steht aus (TODO.md).


## 2026-09-29 — Einrichtungsassistent für Ernte-Aufstellungen

### Entscheidung

Das Quad einer neuen Dot-Matrix-Aufstellung wird aus dem sichtbaren
Punktraster geschätzt. Die feste Anzeigegeometrie (16 Zellen, 5×7 Punkte
plus Cursorzeile) verankert die Homographie; mehrere mögliche Startlagen
werden geprüft und eine unklare Lage abgelehnt. Qualitätsprüfungen und
Overlays gehen in einen Vorschlag, den weiterhin ein Mensch bestätigt.
Ein `FEHLER` kann nur mit dokumentierter Begründung übersteuert werden.

### Verworfene Alternativen

* Der bisherige Glasdetektor allein: Er traf bei den gespeicherten
  StreamCam-Aufstellungen teils die Blende oder Reflexe statt des Glases.
* Vier von Hand abgelesene Stützpunkte: Sie lieferten die Referenzquads,
  waren aber der zeitaufwendigste Einrichtungsschritt.
* Isotrope Glättung im entzerrten Bild: Die vertikale Streckung erzeugte
  doppelte Punktkandidaten zwischen den tatsächlichen Zeilen.

### Konsequenz

Der Assistent verwendet benannte Vorabschwellen und speichert Kennzahlen
neben der Ampel. Sechs vorhandene Standbilder prüfen die Geometrie
offline; Kamerazugriff und tatsächliche Einrichtungsdauer sind noch nicht
auf echter Hardware mit dem Nutzer geprüft.

## 2026-09-30 — Mehrdeutige Plusanker und breite Hinweisboxen

### Entscheidung

Die automatische Rasteranpassung prüft räumlich getrennte plausible
Plusanker. Konkurrierende gültige Raster mit ähnlich vielen Punkten
werden abgelehnt. Liefern die ersten acht Startlagen keinen Fit, wird
eine zweite begrenzte Runde geprüft. Bei einer breiten grünen Hinweisbox
wird ein kleinerer geschätzter Punktabstand als zusätzlicher Startversuch
genutzt. Die aus dem Format bekannten Leerzellen und der Zeilen- und
Zellen-Bias begrenzen weiterhin die Annahme eines Rasters.

### Verworfene Alternativen

* **Nur der stärkste Plusanker:** Ein zweites vollständiges Display mit
  einem einzigen schlechter erkannten Pluspunkt würde nicht geprüft.
* **Unbegrenzte Startlagensuche:** Sie hätte die ohnehin hohen Laufzeiten
  auf dem Raspberry Pi ohne begründeten Sicherheitsgewinn vergrößert.
* **Aus der grünen Box direkt ein Quad ableiten:** Die Glasfläche ist
  größer als die Zeichenzeile; ihre Grenzen sind keine Punktkoordinaten.

### Konsequenz

Auf sechs gespeicherten Aufstellungen trifft der Fit mit automatisch
erkannter grüner Hinweisbox die bestätigten Ecken auf höchstens 0,57 px.
Ein synthetischer Fall mit zwei fast gleich gut erkannten Anzeigen wird
als mehrdeutig abgelehnt. Echte Mehrfachanzeigen und andere Glasformen
bleiben für den ersten gemeinsamen Kameralauf offen.
