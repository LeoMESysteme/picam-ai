# Changelog

Neueste Änderung oben. Je Abschnitt: was war das Problem, was wurde geändert,
was ist die Konsequenz.

## 0.1.0.dev0 — 2026-09-24 (Dot-Matrix-Leser, Phase 2)

**Problem:** Für die Punktraster-Anzeige des GSV-2AS gab es keinen Leser,
der Zeichen erklärbar liest und im Zweifel ablehnt (`tesseract_cli` las
0/11 Proben). Spec: `docs/superpowers/specs/2026-09-24-dotmatrix-reader-design.md`,
Plan: `docs/superpowers/plans/2026-09-24-dotmatrix-reader.md`.

**Änderung:**
* `src/dispread/ocr/dotmatrix_font.py` (Task 1): HD44780-Zeichensatz (ROM
  A00) als 5×8-Bitmuster für Ziffern, `.`, `+`, Leerzelle (dazu `-`/`°` für
  Ablehnungstests) und `rom_vector()`; Gegenprobe für gelernte Vorlagen.
  Tests: `tests/test_dotmatrix_font.py`.
<!-- dotmatrix-bullets -->

**Konsequenz:** siehe Plan, Task 8 (Stufe 1) und Stufe 2 (Abnahme).

## 0.1.0.dev0 — 2026-09-24 (Führende Nullen: zwei statt einer)

**Problem:** Das GSV-2AS-Telegramm trägt immer sechs Ziffern; bei
`dpoint = 1` und Werten unter 1000 kommen zwei führende Nullen vor
(`+00988.5`). Die Anzeige zeigt dafür zwei Leerzellen. `gate-label.py` und
`import-harvest.py` entfernten nur eine Null — das Label wäre `+0988.5 mV/V`
gewesen (OQ-41-Nachtrag). Gefunden in der Stichprobe vor dem Import.

**Änderung:** `telegram_to_display_text()` und `_cell_text_for_telegram()`
unterdrücken alle führenden Nullen des Ganzzahlteils bis auf die Stelle vor
dem Punkt; mehr als zwei (unbelegt) werden abgelehnt und als
`fuehrende_nullen_ungeprueft` gezählt. `label_normalization` jetzt
`gsv2as_leading_zero_v2`. Tests in `tests/test_gate_label.py` und
`tests/test_import_harvest.py`.

**Konsequenz:** Aufstellung 3 wurde offline neu gelabelt (nur die 32 Bilder
mit `+00988.5` ändern sich). Bisher importierte Proben sind nicht betroffen.

## 0.1.0.dev0 — 2026-09-24 (Ernte 1: erste echte Ernte mit Import)

**Problem:** Die Ernte-Kette (`harvest-setup.py`, `harvest.py`,
`import-harvest.py`) war nur gegen Attrappen geprüft; der Datensatz enthielt
keine seriell gelabelten Proben. Um 11:11 blockierte zudem die Kamerabrücke
beim 8. Start des Boots (OQ-22-Nachtrag).

**Änderung:** Kein Code geändert. Nach Neustart eine Ernte mit 30 Schritten
à 4 s gefahren: 2835 Bilder, 837 gelabelt, 81 importiert (Datensatz 88 →
169). Doku: `docs/VALIDATION.md` und `docs/lab_journal.md` („Ernte 1"),
OQ-39-Nachtrag, Status der Tasks E/F/G im Auto-Labeling-Plan, Task 7 im
Plan Ernte Phase 1 abgehakt, `docs/status.md`, `TODO.md`.

**Konsequenz:** Die Kette läuft Ende zu Ende gegen echte Hardware. Weitere
Ernten brauchen je nur einen Streamstart, solange die Kamera steht. Offen:
Vorzeichenstelle, endgültige Gap-Schwellen (OQ-40), Ziffernlücken je Zelle
(OQ-39).

## 0.1.0.dev0 — 2026-09-24 (Task 6: ScalerCrop, Winkel, Auflösungsschwelle)

**Problem:** Für die erste Ernte fehlten Fokus, ein Sensorausschnitt um die
Anzeige und die Auflösungsschwelle `resolution_threshold_px`; die Kamera
war seit gestern blockiert (OQ-22). Beim Prüfen der Overlays kam zudem der
Verdacht auf, `harvest-setup.py propose` entzerre gespiegelt.

**Änderung:**
* Kamera nach nächtlicher Abschaltung wieder funktionsfähig; sechs
  Streamstarts, Fokus nachgestellt, ScalerCrop 1920×1440 (1:1 nativ im
  2028×1520-Modus), drei Stellungen gemessen. Schwelle 2,6 px vom Nutzer
  festgelegt (Plan Ernte Phase 1, Entscheidung 7). Zahlen in
  `docs/VALIDATION.md`, Verlauf in `docs/lab_journal.md`, Nachträge zu
  OQ-22 und OQ-40, `docs/status.md` und `TODO.md` nachgezogen.
* Spiegelverdacht geprüft, nicht bestätigt: die Eckenreihenfolge
  (`dispread.rectify._order_quad`) ist in allen Aufrufern gleich. Neu
  `tests/test_harvest_setup.py::test_propose_rectified_image_is_not_mirrored`
  mit asymmetrischem Muster; der bisherige Test hätte eine Spiegelung nicht
  bemerkt.

**Konsequenz:** Task 7 (erste echte Ernte) ist frei. Die Lichtspiegelung
auf dem Glas schneidet die automatische Glaserkennung ab und muss vorher
beseitigt oder per Hand-Quad umgangen werden.

## 0.1.0.dev0 — 2026-09-23 (OQ-Übersicht und Fokus-Übergabe)

**Problem:** Der Einstieg in neue Agenten-Sitzungen las die ganze
`docs/open-questions.md` (> 100 KB) und mehrere alte Changelog-Einträge.
Beim Fokusversuch scheiterte zudem nach einem erfolgreichen Commissioning-Bild
der nächste Streamstart; nach Warmreboot scheiterte sogar der erste Start des
Boots (OQ-22). Es gab kein Fokusbild und keine Schärfemessung.

**Änderung:**
* `scripts/oq-index.py` erzeugt eine Übersicht (Nummer, Status, Titel) am
  Anfang von `docs/open-questions.md`; `--check` und
  `tests/test_oq_index.py` melden eine veraltete Tabelle.
* `CLAUDE.md` und `AGENTS.md` verweisen auf gezielte Lektüre und die
  Aktualisierung der OQ-Übersicht. Nicht mehr genutzte Claude-Plugins wurden
  in `.claude/settings.json` deaktiviert.
* Die zwei Fokus-Fehlversuche, Boot-IDs, Kernelbefunde und der Wiedereinstieg
  nach einem möglichen Stromzyklus stehen in `docs/status.md`,
  `docs/VALIDATION.md`, `docs/lab_journal.md` und OQ-22. Die Rohdiagnosen
  liegen lokal unter `var/diagnostics/focus-handoff-2026-09-23/`.

**Konsequenz:** Die nächste Sitzung kann gezielt beginnen. Ein Warmreboot ist
keine belegte Abhilfe; bis zur Nutzerentscheidung über den Stromzyklus gibt
es keinen weiteren Kamerastart. Die OQ-Tabelle muss bei neuen oder geänderten
Status-Einträgen neu erzeugt werden.

## 0.1.0.dev0 — 2026-09-23 (Lauf ohne Bilder, Auflösungs-Gate nativ, Streamstart-Budget)

**Problem:** Beim Winkelversuch blockierte die Kamera wieder (OQ-22). Das war
der 21. Streamstart des Boots, nach 20 erfolgreichen. `sync-record.py` meldete
den Lauf mit 0 Bildern trotzdem als „vollständig" (Exit 0). Ausserdem mass
das Auflösungs-Gate im hochgerechneten Ausgabebild. Mit engem `ScalerCrop`
auf dem 2×2-gebinnten Sensormodus überschätzte es die echte Auflösung.

**Änderung:**
* `scripts/sync-record.py`:
  * Kommt 5 s lang kein erstes Bild (`STARTUP_TIMEOUT_S`) oder bleibt es bei
    0 Bildern, wird `acquisition_error` mit Verweis auf OQ-22 gesetzt und der
    Lauf endet mit **Exit 4**. Der hängende Thread wird nicht abgewürgt, die
    Rückstellung nach `--norm-schedule` läuft trotzdem.
  * Neu ist ein **Streamstart-Budget** je Boot, `--stream-budget`, Vorgabe
    15. Gezählt wird aus `journalctl -k -b` bzw. `dmesg` (`Using a link
    rate`, Zeilen innerhalb von 2 s gelten als ein Start). Rückfall ist eine
    Zählerdatei je `boot_id`.
  * Vor dem Öffnen der Kamera gilt **Exit 5**, wenn das Budget erschöpft ist
    oder dieser Boot schon ein `stream on failed` zeigt. Drei Starts vorher
    gibt es eine Warnung, `--override-stream-budget` hebt die Sperre auf.
  * `session.json` trägt `sensor_mode_size` und `sensor_array_size`.
* `scripts/harvest-setup.py`: `propose --session-json` rechnet `native_scale`
  = min(1, (Crop-Breite / Binning) / Ausgabebreite) und
  `min_native_dot_column_px`. `confirm` prüft den nativen Wert und verlangt
  ohne Sitzungsdaten ausdrücklich `--assume-native-scale`.
* `src/dispread/session_profile.py`: Schema 2 mit `native_scale` und
  `min_native_dot_column_px`. Schema 1 wird mit einer klaren Meldung
  abgelehnt.

**Konsequenz:** Ein blockierter Sensor fällt jetzt laut auf, und die Kamera
wird vor dem Grenzbereich von 20–25 Starts nicht mehr geöffnet. Frontal mit
Crop 1195 ergibt das ≈ 0,62 × 7,3 ≈ 4,5 native px je Punktspalte.

## 0.1.0.dev0 — 2026-09-23 (Ernte Phase 1: Zellenraster, Sitzungsprofil, ScalerCrop)

**Problem:** Für den Zellen-Klassifikator (Plan `2026-09-23-ernte-phase1.md`)
fehlten ein bestätigbares Zeichenzellenraster, ein Sitzungsprofil mit
Auflösungsbefund und mehr Pixel je Anzeigepunkt. Bisher lagen im Vollbild nur
≈ 2 px auf einer Punktspalte.

**Änderung:**
* `src/dispread/charcells.py` (neu) enthält `CharGrid` und
  `source_dot_column_px`.
  * `CharGrid` beschreibt das Zellenraster im entzerrten Bild, liefert die
    Zellenboxen und prüft das Raster.
  * `source_dot_column_px` misst die Punktspaltenbreite im **Quellbild** über
    die inverse Homographie, als Minimum über alle Zellen. Es nimmt die
    geometrische Eckabbildung ohne `-1`, weil es einen Massstab misst und
    keine Pixel verzerrt.
* `src/dispread/session_profile.py` (neu): `SessionProfile` (Schema 1) mit
  Quad, Raster, ScalerCrop und Auflösungsbefund. Wird atomar gespeichert,
  unbekanntes Schema führt zum Abbruch.
* `scripts/sync-record.py`: neu ist `--scaler-crop X,Y,W,H`.
  * Der Wert geht über `controls` in `create_video_configuration`
    (picamera2.py:1292/1338) und gilt damit ab dem ersten Bild.
  * `session.json` trägt `scaler_crop_requested` und `scaler_crop_actual`.

* `src/dispread/glassquad.py` (neu): `glass_quad_in_region` findet das
  beleuchtete LCD-Glas.
  * Die Farbmaske richtet sich nach dem Farbton, der in der Mitte der
    Hint-Box gemessen wird. Das Viereck wird mit vier freien Ecken angepasst
    (eine Gerade je Kante), damit auch schräge Ansichten als Trapez
    abgebildet werden.
  * Ist der Fit schlecht, liefert die Funktion `None`.
  * Anlass: Das Gehäuse des GSV-2AS ist selbst gesättigt. `lcd_quad_in_region`
    hat deshalb Rahmen und Gehäuse mit eingeschlossen, und `minAreaRect` kann
    kein Trapez darstellen.
* `scripts/harvest-setup.py` (neu) mit den Befehlen `propose` und `confirm`.
  * `propose` schlägt Quad und Raster vor und schreibt die Overlays für
    Quell- und entzerrtes Bild.
  * `confirm` prüft die Auflösung gegen `--resolution-threshold-px` (Pflicht,
    ohne Vorgabe). Die unbestätigte Standardteilung lehnt es ab, ausser mit
    `--accept-default-grid`.
  * `lcd_quad_in_region` bleibt als Rückfall über `--detector saturation-only`.
* `scripts/import-harvest.py` (neu): Die Ernte wird vollautomatisch in den
  `DatasetStore` importiert (Plan-Entscheidung 5).
  * Je Plateau werden höchstens k Bilder ausgewählt.
  * Ablehnungsgründe: `bildguete` (Ausreisser nach MAD), `zellen_inkonsistent`
    (Abstand zum Medoid, Schwelle je Zeichen), `nicht_pruefbar`,
    `laenge_passt_nicht`, `store_abgelehnt`. Alle Gründe werden gezählt.
  * Die Zeichen stehen linksbündig ab Zelle 0, die unterdrückte Null ist eine
    leere Zelle.
  * `expected_text` folgt der bestehenden Konvention, nur der Zahlenwert ohne
    `+` und Einheit.
  * `label_origin_detail` trägt `display_text`, `cell_text` (16 Zellen),
    `telegram_text`, `label_normalization` und `unit_text`.
  * Dazu kommt eine Stichprobenliste `audit.json`. `datasets.py` ist
    unverändert.
* `scripts/harvest.py` (neu): Ernte-Lauf.
  * Der Faktorplan ist deterministisch, log-uniform verteilt, mit
    Mindestabstand 1,3 zwischen zwei Schritten und im Gerätebereich
    0,15…1 580 000.
  * Ablauf: `sync-record.py --norm-schedule [--scaler-crop]`, danach
    `gate-label.py`.
  * Vor jedem Subprozess wird abgebrochen, wenn `resolution_ok=False` ist
    oder die Haltezeit unter 2·M + 1 s liegt.
  * `harvest.json` mit `gap_thresholds_provisional: true`.
* `scripts/gate-label.py`: `proposal.json` trägt jetzt `summary` mit
  denselben Zählern wie stdout (alle Ablehnungsgründe, auch Nullen).

**Konsequenz:** Auf der Hardware geprüft, Sensorausschnitt
`1858,592,1520,1140`: 133 Bilder ohne Sequenzlücke, kein `stream on failed`.
Das Glas ist im 960×720-Bild jetzt ≈ 560 px breit statt ≈ 210 px.

## 0.1.0.dev0 — 2026-09-23 (Stillstand beim Aufzeichnen behoben, OQ-40)

**Problem:** In `sync-record.py` standen Kamera und serieller Strom zeitweise
bis 2,5 s still. Danach kamen Telegramme mit fast gleichem `t_boot`, ihre
Werte waren vollständig, ihre Zeitstempel falsch. Gemessen wurde die
Ursache: Beim Rückschreiben gepufferter Seiten auf die SD-Karte blockieren
Dateischreibvorgänge. Das betraf sowohl das JPEG-Schreiben in der
Hauptschleife als auch das Schreiben von `serial.jsonl` im Lesethread. Ein
unabhängiger Prozess ohne Dateizugriffe lief lückenlos weiter. Verlorene
Bilder blieben unsichtbar, weil `frame_sequence` ein Zähler des Skripts ist.

**Änderung:**
* `scripts/sync-record.py`: Erfassung und Schreiben sind getrennt.
  * Der serielle Lesethread liest nur noch und vergibt den Zeitstempel. Die
    Kameraschleife holt nur noch Bilder. Geschrieben wird in eigenen Threads
    über Warteschlangen.
  * Die Bild-Warteschlange ist begrenzt (`--frame-queue-size`, Vorgabe 60).
    Bei Überlauf wird verworfen, gezählt (`frames_dropped_queue_full`) und
    als `dropped`-Datensatz protokolliert, nie blockiert und nie still.
  * Neu je Bild: `sensor_sequence` (libcamera `Request.sequence`) und
    `sensor_timestamp_interval_ns`.
  * `session.json` trägt die maximalen Warteschlangentiefen,
    `max_loop_iteration_s` und `stall_iterations`.
* `scripts/gate-label.py`: neues Pflichtargument `--min-gap-ms`, bewusst
  ohne Vorgabewert. Ein Telegrammstoss wird zusammen mit der Lücke davor als
  `telegrammburst` abgelehnt.

**Konsequenz:** In der Belastungsprobe mit 152 MB Rückschreiben blieb der
serielle Strom exakt (532–534 ms). 17 Bilder gingen verloren, sichtbar und
gezählt. Zahlen: VALIDATION.md, 2026-09-23.

## 0.1.0.dev0 — 2026-09-23 (Normierungsplan in sync-record, Versatzmessung, Export mit Herkunft)

**Problem:** Task B (Versatz Telegramm ↔ Anzeige) brauchte grosse
Anzeigesprünge während einer Aufzeichnung. `norm_sweep.py` kann den Port aber
nicht neben `sync-record.py` öffnen. Ausserdem hinterliess ein `SIGTERM`
keine `session.json`. Das Inbetriebnahme-Skript meldete „einsatzbereit" bei
blockiertem Sensor. Und der Export trug `label_origin` nicht weiter.

**Änderung:**
* `scripts/sync-record.py`:
  * `--norm-schedule "Faktor:Sekunden,..."` schreibt `set norm`/`set dpoint`
    aus der bereits offenen Portsitzung. Die Byte-Kodierung ist aus
    `norm_sweep.py` und `gsv-registers.py` übernommen.
  * Jeder Schreibzyklus hält den Strom an (STOP/CLEAR → schreiben → START,
    ≈ 1,8 s). Pause, Wiederanlauf, Befehle und Antworten landen als eigene
    Ereignisse in `commands.jsonl`, mit `non_telegram` markiert.
  * Vorher wird der Registerstand gegen den Rückstellpunkt geprüft und bei
    Abweichung abgebrochen (`--ignore-restore-point-mismatch`). Danach wird
    immer zurückgestellt und per Rücklesen bestätigt
    (`session.json["restore_verification"]`).
  * Ohne Plan geht kein Byte an den Port.
  * `SIGTERM` nimmt jetzt denselben Abbruchpfad wie `SIGINT`
    (`abort_reason: "SIGTERM"`).
* `scripts/display-offset.py` (neu): Photometrische Versatzmessung ohne OCR.
  * Jedes Bild wird auf die Differenz zweier Plateau-Vorlagen projiziert. Das
    liefert Beginn, Mitte und Ende jedes Glaswechsels.
  * Die Populationen `large`, `small` und Normierungsbefehl werden getrennt
    ausgewertet. Rampen und Verdeckungen werden ausgeschlossen, eine
    Null-Basislinie dient als Gegenprobe.
  * M wird nur über die feste Formel aus Festlegung 3 berechnet.
  * Eine erste Fassung mit Bild-zu-Bild-Differenz meldete fälschlich „kein
    Signal". Das war ein Fehler der Methode, weil das träge LCD den Wechsel
    über mehrere Bilder verschmiert, und kein Befund.
* `scripts/camera-commissioning.sh`: echte Aufnahme-Gegenprobe (OQ-22 d).
  * Das Kernel-Log wird auf `stream on failed` geprüft.
  * Es folgt eine gebundene Testaufnahme mit 640×480, ohne SIGKILL.
  * Ein belegtes Gerät wird als „nicht geprüft" gemeldet statt als Fehler.
* `src/dispread/workbench/datasets.py`: `EXPORT_SCHEMA_VERSION` 1 → 2.
  * `manifest.json` trägt `label_origin`/`label_origin_detail` je Probe.
  * `coverage.json` zählt `label_origin_counts`.
  * `scripts/check-dataset-export.py` akzeptiert die Versionen 1 und 2.
* `scripts/gate-label.py`: Normalisierung der führenden Null (OQ-41).
  * `telegram_to_display_text()` entfernt die `0` direkt nach dem Vorzeichen,
    wenn ihr eine Ziffer folgt, weil das Glas sie nicht zeigt.
  * Jeder Vorschlag trägt das Rohtelegramm (`telegram_text`), die
    normalisierte Kette (`label_text`) und `label_normalization`.
  * Die Laufbildung bleibt auf dem Rohtext. Das ist gleichwertig, weil die
    Abbildung injektiv ist.
  * Negative Werte sind ausdrücklich ungeprüft.
* Plan, Vorab-Festlegungen: **M = 695 ms** festgeschrieben (grösster Wert
  über die Populationen) und die Normalisierung der führenden Null ergänzt.

**Konsequenz:** Der Kamerazweig ist gegen die Hardware gelaufen, und für
Task B liegen Zahlen vor (VALIDATION.md, 2026-09-23). Der externe Loader in
`picam-ai-auto-seven-segment` (`evaluation.py:50`) lehnt Schema 2 noch ab.
`test_real_export_is_accepted_by_the_actual_experiment_loader` ist deshalb
als `xfail(strict=True)` markiert.

## 0.1.0.dev0 — 2026-09-22 (sync-record: Betriebsgroesse 960x720, grosse Sensormodi gesperrt)

**Problem:** Der Kamerazweig von `scripts/sync-record.py` lief zum ersten Mal
gegen echte Hardware - mit der Vorgabe **2028x1520**. Das ist einer der
grossen Sensormodi, von denen OQ-22 seit dem 2026-09-08 sagt: jede
protokollierte Sitzung damit war die letzte des Boots. Genau das trat ein:
kein einziges Bild, Prozess haengt in `capture_request`, danach setzt der
Sensor keinen Stream mehr auf (33 x `stream on failed in subdev` in 0,11 s,
`cfe_stop_streaming` im Aufrufpfad). Reboot noetig.

Zweites Problem im selben Zweig: `create_still_configuration` statt
`create_video_configuration`. Der Standbildpfad ist nicht fuer Dauerlauf
gedacht; der erprobte Weg im Repo (und der, mit dem die 88 Bestandsproben
entstanden sind) ist die Videokonfiguration mit `format="RGB888"`, gesetzter
`FrameRate` und `queue=False`.

**Änderung:**
* Vorgabe `--camera-size` von `2028x1520` auf **`960x720`** - die in OQ-22
  festgehaltene Betriebsgroesse.
* Neue **harte Sperre**: eine Aufloesung ueber 1 MPixel bricht mit einer
  Meldung ab, die auf OQ-22 verweist. Aufhebbar nur ueber das ausdrueckliche
  `--allow-large-sensor-mode`. Bewusst ein Abbruch und keine Warnung - die
  Folge eines grossen Modus ist ein Reboot des Labor-Pi, das haengt man nicht
  an eine uebersehene Zeile auf stderr.
* Kamerakonfiguration auf `create_video_configuration` umgestellt, mit
  Begruendung im Docstring, warum jeder Teil davon gebraucht wird.

**Konsequenz:** Der Kamerazweig ist damit an die dokumentierte Betriebsgrenze
gebunden, statt sie zu umgehen. **Weiterhin ungetestet gegen echte
Hardware** - der Sensor ist blockiert, bis der Pi neu startet. Nebenbefund
fuer Nachahmer: `capture_request(wait=2.0)` ist ein **Timeout in Sekunden**,
kein Flag; bei blockiertem Sensor sieht der `TimeoutError` aus wie ein
Konfigurationsfehler, ist aber der Sensorzustand.

## 0.1.0.dev0 — 2026-09-22 (Registerstand des GSV-2 als Rueckstellpunkt)

**Problem:** Die Anzeige des GSV-2AS laesst sich ueber `set norm` (16) und
`set dpoint` (17) gezielt veraendern - das ist der Weg zu Ziffernvielfalt bei
festem Stimulus. Es sind aber Schreibbefehle an ein Laborgeraet. Ohne
festgehaltenen Ausgangszustand gibt es keinen Rueckweg, und die vorige
Sitzung hat gezeigt, wie leicht man sich beim Lesen der Register vertut: der
`0x3B`-Praefix wurde einmal fuer den Registerwert gehalten.

**Änderung:** Neues Skript `scripts/gsv-registers.py`. Liest norm, unit,
dpoint, mode, digits, range, firmware, options, bridge_type, device_type und
last_error, rechnet den Normierungsfaktor zurueck und schreibt alles als
JSON-Rueckstellpunkt. Sendet **ausschliesslich Lesebefehle** plus stop/start
transmission - keinen einzigen Schreibbefehl auf ein Konfigurationsregister.

Zwei Fallstricke sind eingebaut statt dokumentiert: das Semikolon-Praefix
wird gelesen **und geprueft** (`1 + n` Bytes statt `n`), und
`start transmission` laeuft im `finally`-Block in derselben offenen Sitzung,
mit anschliessender Verifikation, dass wirklich wieder Daten kommen.

**Konsequenz:** Der Ausgangszustand ist gesichert
(`var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json`). Beim ersten
Lauf hat sich nebenbei die Umrechnungsvorschrift der Anleitung gegen das
Geraet bestaetigt: der Rohwert ist exakt 5250020, die Konstante aus der
Rechenvorschrift, passend zu Faktor 1,0. Messungen dazu in
`docs/VALIDATION.md`.

## 0.1.0.dev0 — 2026-09-22 (Offline-Gate für das Auto-Labeling, Task F)

**Problem:** Eine `sync-record.py`-Aufzeichnung hat Kamerabilder und den
seriellen GSV-Strom nebeneinander, aber noch keine Entscheidung, welches
Bild welchen Sollwert bekommen darf. Diese Entscheidung folgt dem im Plan
(`docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md`, „Der Kern:
das Schutzintervall") hergeleiteten Schutzintervall `[t_i + M, t_{j+1} − M)`
um einen Lauf gleicher Telegrammzeichenketten, und muss vier stille
Fehlerquellen ausdrücklich ablehnen statt sie zu übersehen.

**Änderung:** Neues Skript `scripts/gate-label.py`. Wertet eine
Aufzeichnung rein offline aus (liest keine Bilddateien, nur Zeitstempel),
schreibt keine Datensatzproben, sondern eine Vorschlagsdatei (JSON, je
gelabeltem Bild Bildpfad, exakte Telegrammzeichenkette, führender
Zahlenteil und ein `label_origin_detail`-Block mit genau den Feldnamen, die
`DatasetStore` bei `label_origin="serial_ascii"` verlangt) plus einen
Bericht auf stdout, der die Zahl **verschiedener Zeichenketten** unter den
gelabelten Bildern deutlich herausstellt (wichtiger als die Bilderzahl,
siehe Plan). `--guard-margin-ms` (M) und `--max-gap-ms` haben absichtlich
keinen Vorgabewert — beides sind offene Mess-/Festlegungsgrößen.

Vier Ablehnungsgründe werden getrennt gezählt: Wertwechsel im
Schutzfenster, außerhalb des Telegrammbereichs (vor dem ersten/nach dem
letzten Telegramm), der letzte Lauf ohne Folgetelegramm (konservativ mit
dem letzten passenden Telegramm statt mit einer unterstellten Dauer
geschlossen) und Telegrammlücken. Lückenfall-Entscheidung: der betroffene
Lauf wird an der Lücke **geteilt**, nicht komplett verworfen — verwirft nur
die tatsächlich unsichere Stelle statt des ganzen Laufs. Das gilt sowohl
für Lücken *innerhalb* eines Laufs gleicher Werte als auch — das ist der
gefährlichste, in der ersten Fassung übersehene Fall — für eine Lücke
**genau an einem Wertwechsel**: dort sah der Strom sonst wie ein normaler
A→B-Übergang aus, obwohl dazwischen unbemerkt ein dritter Wert gestanden
haben kann. Fenstergrenze halboffen, wie die Klammerschreibweise des Plans
sie vorgibt: `t_i + M` eingeschlossen, `t_{j+1} − M` ausgeschlossen.

Test-first in `tests/test_gate_label.py` (9 Tests, u. a. der geforderte
Falsifikationstest: ein Bild exakt im Wechselfenster wird abgelehnt, nicht
irgendwie gelabelt), alle scheiterten vor der Implementierung (Skript fehlte).
382 Bestandstests weiterhin grün, `ruff check src tests scripts` sauber.

**Konsequenz:** Der Gate-Schritt ist gebaut und geprüft, aber **nicht
scharf geschaltet** — er erzeugt nur einen Vorschlag, legt keine Proben an.
Das Anlegen von Proben aus dem Vorschlag ist eine spätere, getrennte
Aufgabe mit Menschenbeteiligung. `M` und `--max-gap-ms` bleiben offene
Messgrößen; ohne eine gemessene Zahl für M (Task B) lässt sich dieses
Skript nicht sinnvoll gegen eine echte Aufzeichnung fahren. Für
`--max-gap-ms` gibt es bislang keinen dokumentierten OQ-Eintrag — das
gehört nachgezogen, ist aber in dieser Änderung nicht passiert, weil
`docs/open-questions.md` außerhalb des Auftrags dieser Aufgabe lag.

## 0.1.0.dev0 — 2026-09-22 (Migration der Bestandsproben auf schema_version 2)

**Problem:** Mit dem Pflichtfeld `label_origin` (schema_version 2) lehnt
`DatasetStore` jede Probe mit `schema_version == 1` hart ab. Das ist richtig
so - eine Herkunft zu unterstellen waere genau das Raten, das dieses Projekt
nicht haben will. Praktisch bedeutet es aber, dass die 88 Bestandsproben ab
sofort unlesbar sind und der Sammelmodus steht, bis sie gehoben werden.

**Änderung:** Neues Wartungsskript
`scripts/migrate-samples-v1-to-v2.py`. Es traegt `label_origin="manual"`,
`label_origin_detail=None` und `schema_version=2` ein. Das ist keine
Annahme, sondern Tatsache: alle Bestandsproben entstanden, bevor es
ueberhaupt einen automatischen Labelpfad gab.

Schutzvorkehrungen, weil das Skript echte Messdaten unter `var/` aendert:
Trockenlauf ist die Vorgabe, geschrieben wird nur mit `--apply`; vorher wird
jede betroffene Datei in ein Zeitstempelverzeichnis gesichert und die
Vollstaendigkeit der Sicherung geprueft, bevor die erste Datei angefasst
wird; geschrieben wird atomar; bereits gehobene Proben werden uebersprungen,
der Lauf ist also wiederholbar; und bei auch nur EINER unklaren Datei bricht
es ab, ohne irgendetwas zu schreiben.

**Konsequenz:** Der Weg zurueck in den Sammelmodus ist ein Befehl, und er ist
umkehrbar (Sicherung zurueckkopieren). **Nicht ausgefuehrt** - das Schreiben
in `var/` gehoert dem Nutzer. Trockenlauf gegen den Bestand geprueft:
88 Proben, davon 88 zu migrieren, 0 unklar.

## 0.1.0.dev0 — 2026-09-22 (Synchronaufzeichner: Kamera + serieller Strom, Task E)

**Problem:** Um den Ende-zu-Ende-Versatz zwischen dem seriellen Telegramm des
GSV-2AS und dem, was die Kamera auf dem LC-Display sieht, zu messen (Task B
aus `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md`), braucht es
eine gemeinsame, zeitgestempelte Aufzeichnung beider Ströme in derselben
Zeitdomäne (CLOCK_BOOTTIME). Bisher gab es keinen Weg, Kamera und seriellen
Mitschnitt gemeinsam wegzuschreiben, ohne sich gegenseitig zu blockieren.

**Änderung:** `scripts/sync-record.py` (Diagnosecode, kein Produktionspfad)
zeichnet für eine angegebene Dauer parallel auf: den seriellen Strom in einem
eigenen Thread, rein lesend (kein Byte, kein Handshakesignal geht an den
Port), jede Zeile mit `t_boot` (`CLOCK_BOOTTIME`); und Bilder je Sequenz mit
`SensorTimestamp` unverändert als `value_ns`, `timebase`,
`timestamp_semantics: "unknown"`, `uncertainty_ns: None` — dieselben
Feldnamen und dieselbe Behandlung wie `Controller._capture`
(`src/dispread/workbench/controller.py`), nicht neu erfunden. Zwei
Bildquellen: `--source synthetic` (Vorgabe, über
`dispread.frames.open_source`, vollständig ohne Hardware testbar) und
`--source camera` (echte Kamera, `picamera2` lazy importiert, absichtlich
NICHT von hier aus ausgeführt — Kamera kann nur ein Prozess halten, siehe
OQ-22). Ctrl-C hinterlässt vollständige, gültige Dateien (zeilenweise
geflusht, `session.json` auch im Abbruchfall mit `"aborted": true`); kommt
über die ganze Dauer kein einziges Telegramm an, wird das am Ende laut auf
stderr gemeldet statt stillschweigend eine leere `serial.jsonl` zu
hinterlassen.

**Konsequenz:** Aufzeichnen und Labeln sind bewusst getrennt (Task E vs. Task
F) — dieselbe Aufzeichnung lässt sich später mit einem anderen
Schutzintervall M erneut auswerten, ohne neu zu messen. `tests/test_sync_record.py`
prüft den `synthetic`-Pfad als Subprozess (Muster aus
`test_dataset_benchmark.py`) mit einem `os.openpty()`-Pseudo-Terminal statt
eines echten Ports (Muster aus `test_gate_und_referenz.py`): vollständiger
Lauf, leerer Telegrammstrom, Ctrl-C-Abbruch, nicht öffenbarer Port. Der
`camera`-Zweig ist ungetestet und wartet auf eine Ausführung durch den
Supervisor auf dem Pi; welche `picamera2`-Metadatenfelder real JSON-fähig
sind, bleibt bis dahin unverifiziert (Annahme aus `Controller._capture`
übernommen).

## 0.1.0.dev0 — 2026-09-22 (Herkunftsmerkmal `label_origin` im Sammelmodus, OQ-38 Punkt 6)

**Problem:** Der Sammelmodus soll perspektivisch auch automatisch aus dem
seriellen GSV-2AS-ASCII-Strom gelabelt werden (OQ-38, `DISPLAYBUS_TAP.md`
„Anbindung an den Sammelmodus"). `DatasetStore` kannte bislang keine Herkunft
fuer ein Label - von Hand und automatisch gelabelte Proben waeren nicht mehr
unterscheidbar gewesen, und ein systematischer Fehler des seriellen Abgriffs
haette sich unsichtbar in jede Benchmarkzahl eingeschlichen, ohne dass sich
der Datensatz je wieder entmischen liesse.

**Änderung:** `src/dispread/workbench/datasets.py` bekommt zwei neue
Probenfelder: `label_origin` (Pflicht, `"manual"` oder `"serial_ascii"` -
ein fehlender Wert ist jetzt ein `DatasetError`, kein stiller
`"manual"`-Default) und `label_origin_detail` (bei `"manual"` zwingend
`None`, bei `"serial_ascii"` ein Pflicht-Dict mit `source_port`,
`guard_margin_ms`, `plateau_start_ns`, `plateau_end_ns`, `telegram_count`,
typgeprueft, groessenbegrenzt, unbekannte Zusatzschluessel erlaubt aber nur
als JSON-faehige Skalare). Beide Felder gehen in die
Unveraenderlichkeitspruefung von `_save_sample_locked` ein - ein Retry mit
demselben `capture_token`, aber anderer Herkunft, ist jetzt ein
`RevisionConflict`, kein stilles Ueberschreiben. `relabel_sample` setzt beim
manuellen Korrigieren `label_origin` immer auf `"manual"` und
`label_origin_detail` auf `None`; die vorherige Herkunft samt Detail landet
unter `previous_label_origin`/`previous_label_origin_detail` im
`label_history`-Eintrag (Entscheidung, keine verworfene Alternative: ein
Mensch, der korrigiert, ist die neue Quelle, die Spur bleibt erhalten - siehe
Docstring von `_relabel_sample_locked`). `SAMPLE_SCHEMA_VERSION` ist von 1 auf
2 gestiegen; eine Probe mit `schema_version == 1` (kein `label_origin`) wird
beim Laden jetzt hart abgelehnt (`_load_sample_json`), analog zum bestehenden
Muster in `_load_devices` - kein stilles "wird schon manuell gewesen sein".
`Controller._dataset_save` reicht `label_origin`/`label_origin_detail` aus
den Op-Argumenten durch, im selben Stil wie die Nachbarfelder. Kein
automatisches Labeln implementiert - nur das Herkunftsmerkmal selbst.

**Konsequenz:** Die 88 echten Proben unter `var/workbench/datasets/` (nicht
Teil dieser Änderung, `var/` bleibt unangetastet) liegen weiterhin mit
`schema_version=1` vor. **Bevor der Sammelmodus wieder auf sie zugreift -
speichern, auswaehlen, umlabeln, zusammenfassen, exportieren -, braucht es
einen Migrationsschritt, der ihnen nachtraeglich `label_origin="manual"`
zuweist.** Diese Migration ist bewusst nicht Teil dieser Änderung. Bis dahin
wirft jede dieser Operationen einen `DatasetError` mit Verweis auf OQ-38
Punkt 6; reine Kamera-/Statusabfragen (`Controller.snapshot`) sind davon
unberuehrt, da sie `DatasetStore` nicht beruehren. Ebenfalls offen und in
OQ-38 Punkt 6 nachgetragen: `_export_locked`/`manifest.json` geben
`label_origin` noch nicht in den Export weiter - eine spaetere Änderung an
`EXPORT_SCHEMA_VERSION` mit eigenem Test ist noetig, sonst endet die
Herkunftsspur an der Probe und erreicht den Benchmark nicht.

## 0.1.0.dev0 — 2026-09-22 (Diagnose-Skript: Dotmatrix-Rasterfit-Probe)

**Problem:** Der vorgeschlagene dotmatrix-Leser fuer die Displaytech-161A
(GSV-Sensor) haengt komplett daran, ob sich das feste 16-Zellen-Raster pro
Bild zuverlaessig verankern laesst. Ein Spike zeigte gute Passung auf einer
einzelnen sauberen Probe, aber auch, dass das entzerrte Quad zwischen Bildern
stark schwankt - ohne eine Messung ueber alle 11 echten GSV-Proben ist nicht
feststellbar, ob der Rasterfit traegt.

**Änderung (2. Fassung):** Die erste Fassung fittete `left` UND `pitch`
gemeinsam ueber denselben "Mitte dunkel/Rand hell"-Score - das ist entartet
und konvergiert auf einen Pitch nahe der HALBEN wahren Zellbreite (alle 16
Zellen passen dann in die dichte Textregion; gemessen: ~18px statt der
wahren ~35px bei 640px Warpbreite). Globaler Otsu machte zudem wegen des
Helligkeitsgradienten der Anzeige das rechte Drittel zu einem soliden
dunklen Blob, und die 5x7-Zell-Downsampling+Binarisierung liess Zeichen mit
wenig Tinte (v.a. den Dezimalpunkt) zu einem Nullvektor kollabieren.

`scripts/dotmatrix-grid-probe.py` bestimmt den Pitch jetzt unabhaengig per
Autokorrelation des Spalten-Tintenprofils (staerkster lokaler Peak im
Bereich 25-55px - die Harmonik-Sorge bei 2x/3x ist bereits durch diesen
Bereichsschnitt abgedeckt, keine gesonderte Harmonik-Erkennung noetig),
sucht danach nur noch die Phase (1 freier Parameter statt 2), binarisiert
adaptiv (`ADAPTIVE_THRESH_GAUSSIAN_C`, 51/15) statt global per Otsu, und
extrahiert Zellen als Float-Tintendichte (INTER_AREA), die erst NACH dem
Downsampling binarisiert wird. Das komplette Parametergrid (Zellaufloesung
5x7/8x10 x Binarisierungsschwelle 0.15/0.25/0.35, sechs Kombinationen) wird
gemessen, nicht nur eine Wahl. Druckt: Rasterfit je Probe (Pitch, Phase,
Raster-Breitenanteil), den Nearest-Class-Treffertest je Kombination, den
Median darueber, sowie fuer die Median-Kombination die Aufschluesselung je
Zeichenlabel plus within-/between-class Hamming-Distanz samt Verhaeltnis.
Schreibt weiterhin nur einen Kontaktabzug (PNG) in ein Scratch-Verzeichnis
ausserhalb des Repos, keine Produktionscode-Aenderung.

**Korrektur (Autokorrelations-Peakwahl):** Die erste Fassung der obigen
Regel waehlte den KLEINSTEN Lag im Bereich, der ein lokales Maximum ueber
Schwelle ist - das zieht die Wahl systematisch an den Bereichsboden.
Gemessen an der Referenzprobe: lokales Maximum bei Lag 25 (Wert 0.328) und
ein staerkeres bei Lag 36 (Wert 0.396) - die alte Regel lieferte 25, korrekt
ist 36. Korrigiert auf den staerksten lokalen Peak im Bereich; die
Harmonik-Sorge (2x/3x-Peaks) ist bereits durch den Bereichsschnitt
PITCH_LAG_MIN/PITCH_LAG_MAX abgedeckt.

**Konsequenz:** Inzwischen sind vier Verankerungsverfahren gemessen (Zahlen
in `docs/VALIDATION.md`): Score-Suche 19,3 %, Tintenausdehnung 67,9 %,
Autokorrelation (nach obiger Korrektur) 38,9 %, Block-Anker 45,2 % -
jeweils Median der Nearest-Class-Trefferquote ueber sechs
Parameterkombinationen. Das vorab festgelegte 70-%-Gate ist in keinem der
vier Verfahren erreicht. Das Skript selbst faellt kein Urteil, ob der
dotmatrix-Ansatz weiterverfolgt wird. Ergebnis bislang nicht in `var/`
uebernommen.

## 0.1.0.dev0 — 2026-09-22 (LCD-Quad-Vorschlag ueber HSV-Saettigung)

**Problem:** `fit_quad_in_region` (Canny-Kantenzug) liefert auf den beiden
LED-/VFD-Laborgeraeten kein einziges Quad (0/36 und 0/41, gemessen
2026-09-22 - der als 0/73 in docs/VALIDATION.md 2026-09-21 dokumentierte
Befund, hier reproduziert) und auf dem GSV-Geraet nur 7 von 11. Ein Blocker,
weil nichts nachgelagert zuverlaessig gegen echte Daten getestet werden kann.
Ein Spike (2026-09-22) zeigte, dass bei hinterleuchteten Farb-LCDs
(GSV-Sensor) eine HSV-Saettigungsmaske das leuchtende Glas sauber vom grauen
Metallrahmen trennt, wo Kantenerkennung scheitert.

**Änderung:** Neue Funktion `lcd_quad_in_region`
(`src/dispread/workbench/vision.py`), gleicher Vertrag wie
`fit_quad_in_region` (normierter `hint_box`, normiertes geordnetes
Vierpunktquad oder `None`). Saettigungsmaske > Schwelle, MORPH_CLOSE,
groesste Aussenkontur, Mindestflaechenanteil, `minAreaRect` -> `_order_quad`
(`dispread.rectify`). Kein Ersatz fuer `fit_quad_in_region`, sondern
Sonderpfad fuer genau diese Geraeteklasse; Fehlschlag ist inert, `manual_roi`
bleibt Primaerpfad. Schwellen sind unvalidierte Vorabdefaults, gemessen an
einem Geraet (n=11) - siehe neues OQ-36 (`docs/open-questions.md`).

**Konsequenz:** Fuer hinterleuchtete LCDs existiert jetzt ein Vorschlagspfad,
der auf echten Daten tatsaechlich einen Quad liefert, statt wie bisher 0/73.
Generalisiert nachweislich nicht auf die zwei LED-/VFD-Laborersatzgeraete im
Datensatz - laut Nutzer nicht relevant, weil die Produktionshardware LCD ist.
Ob die Schwelle auf weiteren echten LCD-Geraeten haelt, bleibt offen (OQ-36).

## 0.1.0.dev0 — 2026-09-22 (DatasetStore: begruendete Label-Korrektur)

**Problem:** `save_sample` lehnt ein anderes Label fuer denselben
`capture_token` bewusst als `RevisionConflict` ab (Labels sind unveraenderlich)
- aber damit gab es keinen unterstuetzten Weg, ein von Menschenhand
vertipptes `expected_text` zu korrigieren. `var/` liegt nicht unter
Versionskontrolle, also haette ein direktes Editieren der `sample.json` keine
Spur des vorherigen Werts hinterlassen.

**Änderung:** `DatasetStore.relabel_sample`/`_relabel_sample_locked`
(`src/dispread/workbench/datasets.py`), nach demselben Revisions-Check-Muster
wie `select_sample`/`_select_sample_locked`. Nur fuer `label_state=readable`,
verlangt eine Begruendung, lehnt No-Op-Aenderungen ab, haengt den vorherigen
Wert plus Zeitstempel und Begruendung an ein neues `label_history`-Feld an,
erhoeht `metadata_revision`. Neuer Controller-Befehl `dataset.relabel`
(`src/dispread/workbench/controller.py`), analog zu `dataset.select`.

**Konsequenz:** Fehlgetippte Ground Truth kann jetzt nachvollziehbar
korrigiert werden, ohne die Unveraenderlichkeitsregel fuer echte
Label-Konflikte aufzuweichen. `label_history` ist ein zusaetzliches Feld -
`benchmark.load_dataset_samples` und der Exportpfad pruefen nur bekannte
Pflichtfelder, ignorieren unbekannte, also bricht nichts Bestehendes.

Erstmals angewandt am selben Tag auf zwei vertippte GSV-Beschriftungen
(`663591e6…`, `e96bd68c…`, beide `0.94801`); Befund und Begruendung im
[Laborjournal](docs/lab_journal.md) 2026-09-22. Danach weichen 0 von 11
GSV-Beschriftungen vom Festformat ab.

## 0.1.0.dev0 — 2026-09-21 (Workbench-UI: Leser-Backend waehlbar)

**Problem:** `backend.set` (voriger Commit) war nur ueber einen direkten
Befehl erreichbar, keine Bedienoberflaeche dafuer.

**Änderung:** Neue Zeile "leser-backend" in `fields.rows()`, direkt vor den
Layout-Feldern - Auswahl zwischen `sevenseg` (7-Segment) und `tesseract_cli`
(Zeichen-/dot-matrix-LCDs wie GSV-Sensor), demselben deklarativen
`_row`/`_option`-Muster wie die bestehende `polaritaet`-Zeile. Die
bestehende `reading.evidence`-Zeile zeigt das aktive Backend bereits generisch
(`reading.get('backend')`) - keine Aenderung dort noetig.

**Konsequenz:** Ein Bediener kann jetzt ueber die Werkbank-Oberflaeche
zwischen den beiden Lesern wechseln. Kein echter Browser-Klick-Durchlauf
verifiziert (dieselbe Einschraenkung wie OQ-21/OQ-34 fuer den ganzen
Prototyp) - `fields.rows()` ist unit-getestet, nicht die DOM-Interaktion.

## 0.1.0.dev0 — 2026-09-21 (Controller: backend-Feld waehlt den Leser)

**Problem:** `backend` existierte im Profilschema (voriger Commit), aber
`Controller` benutzte immer die fest instanzierte `SevenSegmentReader` -
das Feld hatte keine Wirkung.

**Änderung:** `Controller._reader_for(backend)` waehlt zwischen der
bestehenden `SevenSegmentReader`-Instanz und einer bei Bedarf erzeugten,
wiederverwendeten `TesseractReader`-Instanz. `_read`/`_autofit` nutzen das
statt des fest verdrahteten `self.reader`. Neuer Befehl `backend.set`
(analog `profile.role`). `layout.autofit` (die sevenseg-Glyphenverhaeltnis-
Suche) lehnt bei `backend=tesseract_cli` sofort mit einer erklaerenden
Meldung ab, statt eine fuer dieses Backend bedeutungslose Suche laufen zu
lassen. 3 neue Tests: Backend-Wechsel aendert tatsaechlich, welcher Leser
antwortet; unbekannter Wert abgelehnt; `layout.autofit` lehnt sofort ab.

**Konsequenz:** Ein Profil kann jetzt tatsaechlich `tesseract_cli` als
Leser nutzen. Noch offen: eine UI-Auswahl dafuer (naechster Commit) - bisher
nur ueber den `backend.set`-Befehl direkt erreichbar.

## 0.1.0.dev0 — 2026-09-21 (Profilschema: backend-Feld fuer tesseract_cli)

**Problem:** `src/dispread/ocr/tesseract_cli.py` (voriger Commit) existiert,
aber kein Profil kann es auswaehlen - `DisplayLayout`/das Profilschema
kannten nur `sevenseg`.

**Änderung:** `DEFAULT["backend"] = "sevenseg"`, Schema 3 -> 4. Migration:
ein Profil mit Schema 3 ohne `backend`-Feld bekommt `"sevenseg"` - exakt das
bisherige Verhalten, keine Vermutung; die Umstellung erfolgt unbedingt bei
`schema_version == 3` (nicht zusaetzlich an der Feldabwesenheit geprueft),
sonst haetten die bestehenden v1/v2-Migrationstests (die DEFAULT komplett
kopieren) das neue Feld bereits mitgebracht und waeren faelschlich bei
Schema 3 haengen geblieben. `validate()` lehnt unbekannte `backend`-Werte
ab. 3 neue Tests (Migration, unbekannter Wert abgelehnt, `tesseract_cli`
akzeptiert); zwei bestehende Migrationstests
(`test_profile_v1_rectangle_is_migrated_to_quad`,
`test_profile_v2_is_migrated_with_full_ocr_box`) erwarten jetzt
`schema_version == 4` statt `3`; ein bestehender Parametrisierungsfall in
`test_profile_validation` von `schema_version: 4` auf `5` verschoben (4 ist
jetzt die gueltige aktuelle Version).

**Konsequenz:** Das Feld existiert und wird validiert, aber `Controller`
liest es noch nicht (naechster Commit) - ein gesetztes `backend` hat bisher
keine Wirkung.

## 0.1.0.dev0 — 2026-09-21 (Neues OCR-Backend tesseract_cli fuer dot-matrix-/Zeichen-LCDs)

**Problem:** Der neu angelegte GSV-Sensor ist eine dot-matrix-Zeichen-LCD
(HD44780-artig, z. B. `+1.05000 mV/V`), keine 7-Segment-Anzeige. Der
bestehende `sevenseg`-Leser kann sie strukturell nicht lesen - `DIGIT_SEGMENTS`
kennt Balkenmuster, keine Punktraster-Glyphen, und keine Buchstaben/Symbole.

**Änderung:** Neues `src/dispread/ocr/tesseract_cli.py`, `TesseractReader`,
implementiert dieselbe `ValueReader`-Schnittstelle wie `sevenseg` - keine
Schnittstellenänderung. Nutzt die bereits installierte `tesseract`-CLI
(5.5.0) als Subprozess (TSV-Ausgabemodus, liefert Text und Wortkonfidenz in
einem Aufruf), keine neue Python-Abhängigkeit. Zeichen-Whitelist und
erwartete Ziffern-/Nachkomma-/Vorzeichenform kommen ausschließlich aus dem
bestätigten `DisplayLayout` - nie geraten. Zwei unabhängige
Ablehnungskriterien (Konzept.md §7): Formatprüfung (erkannte Ziffernzahl
muss exakt zum Profil passen) und eine Konfidenzschwelle - beide müssen
bestehen, sonst `value=None`. 11 neue Tests, davon 8 deterministisch gegen
einen gefakten Tesseract-Output (Parser-/Ablehnungslogik, unabhängig von der
tatsächlichen Bilderkennungsgüte) und ein Sicherheitstest gegen die echten
GSV-Sensor-Fotos im Datensatz (`nie ein falscher Wert, höchstens eine
Ablehnung`).
OQ-15 geklärt: `tesseract-ocr`/`socat`/`chrony` sind bereits installiert.

**Konsequenz:** Zweites lauffähiges OCR-Backend, noch nicht mit dem
`Controller`/Profilschema verdrahtet (folgt in einem separaten Commit).
Die Erkennungsgüte des Standard-Tesseract-Modells auf dieser dot-matrix-
Schrift ist noch nicht zuverlässig (manuelle Stichproben lasen z. B.
`1.05000` als `1.75000`) - die Ablehnungslogik hat in den bisherigen 11
Stichproben jede Fehllesung gestoppt (3 kein Text erkannt, 6 Ziffernzahl
stimmt nicht, 1 Vorzeichen nicht erkannt, 1 Konfidenz zu niedrig) - kein
einziger falscher Wert, aber die Trefferquote selbst braucht weitere Arbeit
(mehr/bessere Vorverarbeitung oder ein segmentschrift-trainiertes
Tesseract-Modell wie `letsgodigital`) - bewusst nicht Teil dieses Commits.

## 0.1.0.dev0 — 2026-09-21 (Dataset-Benchmark: Leser-Polarität kam nie vom Gerät - jede LCD-Probe wäre garantiert gescheitert)

**Problem:** Der Nutzer hat ein neues Gerät ("GSV", `technology=LCD`)
angelegt - das erste Gerät im Sammelmodus, das die tatsächliche Zielhardware
repräsentiert (Nutzerbestätigung: alle Produktivanzeigen sind LCD, siehe
OQ-04-Update). `fit_dataset_sample`/`target_layout` bauten ihr Testraster
bisher aber immer mit dem `DisplayLayout`-Default `polarity=bright_on_dark`
(LED: helle Segmente auf dunklem Grund) - unabhängig von der tatsächlichen
Geräte-Technologie. `dispread.ocr.autofit.fit_layout` sucht Polarität nicht
mit (kein Eintrag in `_CANDIDATES`), eine falsche Polarität lässt daher JEDE
Probe scheitern, unabhängig von der Geometrie - das hätte die eigentliche
Geometriefrage für LCD-Geräte dauerhaft unsichtbar gemacht.

**Änderung:** `fit_dataset_sample`/`target_layout` bekommen einen expliziten
`polarity`-Parameter (Default `bright_on_dark`, rückwärtskompatibel zu allen
bisherigen Tests/`render_display`). `scripts/dataset-benchmark.py` liest die
Geräte-`technology` direkt aus `devices.json` (`_device_polarities`, kein
`DatasetStore` nötig) und leitet daraus `dark_on_bright` für LCD ab, sonst
den Default. Neuer Regressionstest
`test_fit_dataset_sample_falsche_polaritaet_scheitert_richtige_matcht`:
ein invertiertes `render_display`-Bild (simuliert LCD) scheitert mit
Standard-Polarität garantiert und matcht garantiert mit der richtigen -
beweist den Fehler und die Behebung in einem Test statt nur zu behaupten.

**Konsequenz:** Ein erneuter Lauf gegen das neue GSV-Gerät zeigt jetzt
korrekt `Polaritaet (aus Geraete-technology, LCD=dark_on_bright):
dark_on_bright`. Weiterhin 0 von 3 Proben gefittet - aber diesmal ist das
eine Aussage über die Geometrie, nicht über eine falsche Polaritätsannahme.
Der Bestand ist mit 3 Proben, alle mit identischem Sollwert, in einer
einzigen Situation, noch zu klein für eine belastbare Aussage zur
LCD-Geometrie. `324 passed`, `ruff check` sauber.


## 0.1.0.dev0 — 2026-09-21 (Dataset-Benchmark: fehlendes `selected` bricht nur die eine Faltung ab, nicht den ganzen Lauf)

**Problem:** Der erste echte Volllauf gegen `var/workbench/datasets` (77
Proben, gewachsen gegenüber den 52 aus dem Plan) brach sofort ab: die
BK-Precision-Situation „schräg links" (`57227b16...`) hat noch keine als
`selected` markierte Probe - eine echte, nicht erfundene Datenlücke. Die
ursprüngliche CLI-Implementierung beendete beim ersten fehlenden `selected`
den GESAMTEN Lauf (`return 1`), was auch die bereits berechneten,
brauchbaren Befunde des anderen Geräts (RND-Lab) und der anderen zwei
BK-Situationen verschluckt hätte.

**Änderung:** `scripts/dataset-benchmark.py`: ein fehlendes `selected` bricht
jetzt nur die betroffene Faltung ab (`FEHLER:` auf stderr, Faltung
übersprungen, `exit_code=1` gesetzt), der Lauf läuft für alle anderen
Situationen/Geräte weiter. Kein Ersatzvertreter wird erraten - das bleibt
wie im Plan gefordert. Exit-Code des gesamten Laufs bleibt `1`, wenn
irgendeine Faltung deswegen übersprungen wurde - der Fehler ist also
weiterhin sichtbar, nur nicht mehr blockierend für den Rest des Berichts.

**Konsequenz:** Ein Volllauf liefert jetzt den vollständigen Befund für alle
auswertbaren Situationen/Geräte in einem Durchgang, meldet die BK-Situation
ohne Vertreter aber weiterhin laut als offenen Punkt (nicht als „0 %
korrekt", nicht stillschweigend übersprungen). Diese Lücke gehört als
Bedienaufgabe behoben (Vertreter für „schräg links" markieren), nicht durch
Software geraten.

## 0.1.0.dev0 — 2026-09-21 (Dataset-Benchmark Task 4: CLI und Faltungslogik)

**Problem:** Task 2/3 lieferten die Fitting-/Auswertungsbausteine
(`search_ocr_box`, `fit_dataset_sample`, `target_layout`,
`evaluate_dataset_sample`, `segment_report`, `aggregate`), aber noch kein
lauffähiges Werkzeug - die Leave-one-group-out-Faltung (Phase B) und die
Zusammenfassung je Gerät (Phase A) fehlten.

**Änderung:** `scripts/dataset-benchmark.py` (neu), dünne CLI wie
`ocr-benchmark.py`. `--samples`/`--split`/`--deskew`/`--device`/`--diagnose`.
Phase A und Phase B je Gerät und Geometrie getrennt gedruckt, nie gepoolt.
Ehrliches Ausfallverhalten wie im Plan gefordert: fehlt eine
`selected`-markierte Probe in einer Situation, bricht der ganze Lauf mit
`FEHLER:` auf stderr ab (Exit 1) statt eine Situation stillschweigend
auszulassen; ein Gerät mit nur einer Situation meldet die
Übertragungslücke explizit (`LUECKE:`); ein fehlendes Quad/`ocr_box` in
Phase B landet als eigener Ablehnungsgrund im festgenagelten Nenner, nie als
stiller Rückfall. `has_sign` kommt NICHT von einem Gerätefeld - das gibt es
im aktuellen `DatasetStore`-Schema nicht (Abweichung vom Plan, dort
dokumentiert) - sondern aus dem Vorzeichen aller lesbaren Proben eines
Geräts, aggregiert über den ganzen Bestand, nie aus der einzelnen
Zielprobe einer laufenden Auswertung. `DatasetSample` um `selected` und
`similarity_warning` erweitert (optional, Default aus, rückwärtskompatibel),
damit die CLI beides ohne eigenen `DatasetStore`-Import lesen kann.
5 neue Tests, darunter 3 CLI-Subprozesstests (Muster aus
`tests/test_dataset_export.py`).

**Konsequenz:** `scripts/dataset-benchmark.py` ist jetzt lauffähig.
`322 passed`, `ruff check src tests examples scripts` sauber. Bekannte,
bewusste Lücken dieses Laufs (im Skript selbst dokumentiert): keine
Aufschlüsselung nach Bedingung (reflection/angled/...), keine gesonderte
Ähnlichkeitsmessung je Faltung (nur das je Probe gespeicherte
`similarity_warning` wird durchgereicht). Der erste echte volle Lauf gegen
`var/workbench/datasets` steht noch aus (Laufzeit im Minutenbereich je
Gerät/Geometrie) - Protokollierung in `docs/VALIDATION.md`/
`docs/lab_journal.md` sowie das Update an OQ-23/OQ-17 folgen danach.

## 0.1.0.dev0 — 2026-09-21 (Dataset-Benchmark Task 2/3: Phase-A-Fitting + Phase-B-Uebertragung)

**Problem:** Die im Sammelmodus gesammelten realen Proben (52+, siehe
`docs/PLAN_2026-09-21-dataset-benchmark.md`) waren zwar ladbar und geometrisch
zuschneidbar (Task 1: `load_dataset_samples`, `sample_quad`), aber noch nicht
gegen den 7-Segment-Leser messbar - es fehlte die eigentliche Fitting- und
Auswertungslogik.

**Änderung:** `src/dispread/benchmark.py` um Phase A (Passbarkeit/Diagnose,
ausdrücklich kein Erkennungswert) und Phase B (Übertragung) erweitert:
`search_ocr_box` (grobe, wertfreie Rahmenvorsuche gegen `ocr.autofit.fit_layout`,
~36 Kandidaten statt eines vollen Kreuzprodukts), `fit_dataset_sample` (Zielbox
→ `sample_quad` → `search_ocr_box`, liefert `SampleFit`), `target_layout`
(Zielraster NUR aus Zielformat + eingefrorenen Glyphenverhältnissen +
geräteseitigem `has_sign` - **niemals** aus dem Zieltext der Probe selbst),
`evaluate_dataset_sample` (liest eine Probe mit einem Phase-B-Raster),
`segment_report` (Segmentdiagnose je Ziffernstelle: gemessene Helligkeiten vs.
Sollmuster aus `DIGIT_SEGMENTS`) und `aggregate` (aus `evaluate_set`
herausgezogen, damit Clip-/Annotationspfad und Datensatz-Pfad dieselbe
Summierung benutzen). 20 neue Tests in `tests/test_dataset_benchmark.py`,
darunter ein Leck-Test für `target_layout` (has_sign kommt beweisbar nie aus
dem Sollwert) und die Pflichtprüfung gegen eine `render_display`-Probe für
`fit_dataset_sample`/`evaluate_dataset_sample`.

**Konsequenz:** Gegen eine echte Probe bestätigt `fit_dataset_sample` empirisch
den Spike-Befund aus dem Plan (OQ-23): `search_ocr_box` findet unter 35
Kandidaten keinen, der den Sollwert exakt dekodiert (`matched=False`,
2485 Leseversuche, ~4s). Laufzeit pro Probe/Geometrie liegt damit im
Minutenbereich für den gesamten realen Bestand, nicht Stunden. `317 passed`,
`ruff check` sauber. Die CLI (`scripts/dataset-benchmark.py`, Task 4) und die
Phase-B-Faltungslogik (Leave-one-group-out) fehlen noch.

## 0.1.0.dev0 — 2026-09-21 ("als Vertreter markieren" war unsichtbar - Nachschliff zur eigenen Sitzung)

**Problem:** Nutzerbefund direkt nach dem vorigen Fix: "ich kann in dispread
keinen 'Vertreter' für eine Situation festlegen". Ursache: `#dataset-representative`
(der neue Knopf aus dem vorherigen Eintrag dieser Sitzung) war im Markup als
**Kind** von `#dataset-editor` verschachtelt. `afterSave()` setzt
`#dataset-editor.hidden = true`, bevor es `#dataset-representative.hidden =
false` setzt - ein verstecktes Vorfahrenelement (`display:none` via
`[hidden]`) blendet aber jedes Kind aus, unabhängig von dessen eigenem
`hidden`-Attribut. Der Knopf existierte im DOM, die Logik lief korrekt
(Backend-Aufruf `dataset.select` funktionierte), er war aber schlicht nie
sichtbar.

**Änderung:** `#dataset-representative` in `static/index.html` als Geschwister
von `#dataset-editor` verschoben (beide Kinder von `#dataset-step-capture`).
Neue Struktur-Prüfung in `tests/dataset_client.test.mjs`: liest das echte
Markup und stellt sicher, dass `#dataset-representative` nicht innerhalb von
`#dataset-editor` verschachtelt ist - verifiziert am alten (fehlerhaften)
Markup, dass sie tatsächlich anschlägt, bevor sie gegen den Fix bestätigt
wurde. Kein DOM/jsdom nötig, passt zum bestehenden Teststil dieser Datei
(siehe OQ-21 zu den Grenzen echter Browsertests in dieser Umgebung).

**Konsequenz:** Der Knopf ist jetzt tatsächlich sichtbar. `297 passed`,
`ruff check` weiterhin sauber. Lehre für diese Sitzung: eine rein
strukturelle Markup-Änderung wie diese hätte durch die vorhandenen
JS-Unit- und Python-HTTP-Tests nicht auffallen können, weil keiner von ihnen
tatsächliche DOM-Sichtbarkeit prüft - das war eine Lücke im eigenen
Verifikationsschritt, nicht in der Testabdeckung an sich.

## 0.1.0.dev0 — 2026-09-21 (`dispread serve` liess sich nicht mit Strg+C beenden)

**Problem:** `dispread serve` reagierte auf kein Strg+C mehr, auch nicht nach
vielen Versuchen. Live-Diagnose am haengenden Prozess (Thread-Zustaende via
`/proc`, `gdb`, `py-spy`): Das SIGINT wurde korrekt verarbeitet, `serve()`
lief bis zum Ende der eigenen `finally`-Kette vollstaendig durch (HTTPS-Port
bereits geschlossen) - der Prozess blieb trotzdem fuer immer haengen. Ursache
war eine Nebenlaeufigkeitsluecke, keine Kamera-/Treiberfrage (OQ-22): die
alte Reihenfolge schloss `terminals.close()` **vor** `runner.cleanup()`/
`unix.cleanup()` ab. Solange der HTTPS-Server (bzw. der lokale
Steuersocket) noch Verbindungen annahm, konnte in der Luecke zwischen dem
Setzen von `stop` und diesem Zeitpunkt ein neues `POST /terminals` eine
Shell anlegen, die `terminals.close()` nie zu Gesicht bekam. Deren
Reap-Task (`asyncio.to_thread(subprocess.wait)`) blockierte dann fuer immer
einen Worker-Thread des asyncio-Default-Executors - und genau den joint
`asyncio.run()` bei seinem eigenen, nicht unterbrechbaren Abbau, lange
nachdem `serve()` selbst schon zurueckgekehrt und der Signal-Handler damit
weg war. Ein zweites, drittes, ... Strg+C danach traf ins Leere.

**Änderung:** `serve()` in `src/dispread/workbench/server.py`: die
`finally`-Kette ruft jetzt zuerst `runner.cleanup()` und `unix.cleanup()`
(stoppt beide Verbindungsannahmen, oeffentliches HTTPS **und** lokalen
Steuersocket) und erst danach `terminals.close()` auf. Neuer Test
`test_serve_stops_accepting_connections_before_closing_terminals`
(`tests/test_workbench.py`) prueft genau diese Reihenfolge end-to-end gegen
den echten `serve()`-Ablauf (via `server.stop` am lokalen Steuersocket,
nicht ueber ein zeitlich unzuverlaessiges HTTP-Rennen).

**Konsequenz:** Eine waehrend des Herunterfahrens angelegte Shell kann
`terminals.close()` nicht mehr entgehen. Der zuvor haengende Prozess auf dem
Lab-Pi wurde nach Bestaetigung, dass alle eigenen Aufräumschritte
(`runner.cleanup`/`terminals.close`/`controller.close`/Socket-/Lock-Datei)
bereits vollstaendig durchgelaufen waren (Port 7777 nicht mehr belegt, kein
Kamerathread mehr aktiv, alle Threads im Zustand `S`, kein `D`-Zustand -
somit kein OQ-22-Kamera-Wedge), risikofrei mit `SIGKILL` beendet. `297
passed`, `ruff check` weiterhin sauber.

## 0.1.0.dev0 — 2026-09-21 (Datensatz-Sammelmodus: "als Vertreter markieren" fehlte in der Oberfläche)

**Problem:** Beim ersten echten Sammeldurchlauf mit mehreren Situationen à
mehrere Aufnahmen lieferte "Prüfsatz exportieren" durchgängig **0 Bilder**.
Ursache: `DatasetStore._export_locked()` schließt eine Situation mit mehr
als einer Probe komplett aus, solange keine davon ausdrücklich als Vertreter
markiert ist (`group_without_selection` — verhindert, dass zufällig eine von
zehn Wiederholungen automatisch "die" Probe wird). Das dafür nötige Backend
(`DatasetStore.select_sample`/`dataset.select`-Kommando) existiert bereits
seit Aufgabe 5, wurde aber **nie mit einem Knopf in der Oberfläche
verdrahtet** — unabhängig von der heutigen Schrittumstellung, dieser Knopf
hat schlicht noch nie existiert.

**Änderung:** Neue Zeile "als Vertreter dieser Situation markieren" in
Schritt 3, erscheint direkt nach "Speichern und weiter" für die soeben
gespeicherte Probe; ruft den bestehenden `dataset.select`-Befehl auf. Bei
genau einer Aufnahme je Situation ist der Knopf nicht nötig (die einzige
Probe wird beim Export automatisch Vertreter). Bewusst minimal: markiert nur
die zuletzt gespeicherte Probe, keine nachträgliche Auswahl älterer Proben —
eine Übersicht/Galerie je Situation (auch zum Verschieben zwischen
Entwicklungs- und Abschlusstestbestand) ist als nächster Schritt vorgesehen,
siehe `docs/status.md`.

**Konsequenz:** Eine Situation mit mehreren Aufnahmen lässt sich jetzt
tatsächlich exportieren. Neuer Test
`test_marking_a_sample_as_representative_makes_the_group_exportable`
(`tests/test_dataset_api.py`) belegt über den echten HTTP-Pfad: ohne Auswahl
0 exportierte Bilder, nach `dataset.select` 1. `296 passed`, `ruff check`
weiterhin sauber, `node --check`/`dataset_client.test.mjs` unverändert grün.

## 0.1.0.dev0 — 2026-09-21 (Datensatz-Sammelmodus: Schrittoberfläche statt flacher Formularliste)

**Problem:** Nutzerrückmeldung nach erstem Kontakt: "die oberfläche zum
datensatz aufnehmen ist zu unverständlich und umständlich". Ursache: es gab
keine Möglichkeit, ein bereits angelegtes Gerät auszuwählen — die Oberfläche
zeigte nur ein "neues Gerät anlegen"-Formular, was nach jedem Neuladen
faktisch zwang, Geräte erneut anzulegen. Geräteformular, Situationsformular,
Aufnahmeknopf, Label-Editor und Export standen zudem undifferenziert flach
untereinander, ohne Hinweis, welcher Schritt gerade dran ist.

**Änderung:** Neuer Lesebefehl `DatasetStore.list_devices()` /
`dataset.device.list` (sortiert nach Anzeigename, inkl. Situationsgruppen je
Gerät). `static/index.html`/`static/dataset.js` bauen den Sammelmodus jetzt
als drei Schritte: **Gerät** (`<select>` aus vorhandenen Geräten, letzte
Option öffnet das bestehende "neues Gerät"-Formular), **Situation**
(vorhandene Situationen des Geräts zum Fortsetzen, plus "neue Situation";
bei genau einer vorhandenen Situation automatisch übersprungen) und
**Aufnahme** (unveränderte Capture-/Box-/Label-/Save-Mechanik, jetzt einzig
sichtbarer Teil sobald Gerät+Situation stehen, mit Kopfzeile "Gerät: X ·
Situation: Y"). Jeder abgeschlossene Schritt klappt zu einer
Einzeiler-Zusammenfassung mit "ändern"-Knopf zusammen. Echte `<label>`s
statt reiner Platzhaltertexte; Modell/Familie/Technologie wandern im
Geräteformular hinter ein `<details>` "Weitere Angaben", damit der
Normalfall (vorhandenes Gerät wählen) ohne Zusatzfelder auskommt. Ein
Schrittwechsel über "ändern" verwirft eine noch offene, nicht gespeicherte
Aufnahme automatisch. Export bleibt unverändert als feste Zeile am Ende.
Ändert keinen bestehenden Kommando-/Endpunktvertrag außer der einen neuen
Leseoperation.

**Konsequenz:** Ein vorhandenes Gerät lässt sich jetzt direkt wählen statt es
neu anzulegen; der jeweils nächste Schritt ist eindeutig erkennbar. Neue
Tests: `test_list_devices_is_sorted_by_name_and_includes_groups`,
`test_device_list_command_returns_a_json_list_over_http` (belegt, dass der
`/command`-Pfad eine Liste unverändert durchreicht, nicht nur ein Dict), und
drei Faelle fuer die aus `dataset.js` extrahierte reine Entscheidungsfunktion
`chooseInitialGroup` (0/1/mehrere Situationen) in
`tests/dataset_client.test.mjs`. Bestehende ROI-/Clip-/OCR-/Tracking-/
Serial-/Dataset-Regressionstests laufen unverändert mit (`295 passed`).
Reale Browserabnahme bleibt wegen OQ-21/OQ-34 aus dieser Umgebung nicht
möglich — manuelle Prüfung im laufenden `dispread serve` steht noch aus.

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Nachschliff nach Advisor-Review)

**Problem:** Eine unabhängige Zweitprüfung nach Abschluss der Aufgaben 1-7
fand vier Lücken gegen den eigenen Exportvertrag/die eigene Spezifikation:
(1) `synthetic: true`-Proben liefen ungefiltert in den Export, obwohl der
Exportvertrag sie explizit in derselben Aufzählung wie `uncertain`/`draft`
ausschließt — genau die Zählerinflation, die Aufgabe 5 für `summary()` schon
behoben hatte, blieb im Exportpfad bestehen. (2) Ein Absturz zwischen dem
Schreiben von `sample.json` und dem abschließenden `rename()` in
`_save_sample_locked` hinterlässt ein `.sample-*`-Verzeichnis, das alle vier
Scan-Methoden (`_load_all_samples`, `_device_has_samples`,
`_find_existing_sample_for_token`, `_find_duplicate_hash`) als fertige Probe
mitgezählt hätten — sortiert sogar vor echten UUID-Verzeichnissen und hätte
so versehentlich Gruppenvertreter im Export werden können. (3)
`identity_evidence` (Belegart der Identitätsbestätigung) war spezifiziert,
aber nirgends implementiert. (4) Das 64-MiB-Aufnahmebudget zählte auch
bereits gespeicherte (nicht mehr offene) Aufnahmen mit — bei üblichem
Sammeltempo hätte das neue Aufnahmen ohne echten Grund abgelehnt.

**Änderung:** `_export_locked()` filtert synthetische Proben zuerst heraus
(Grund `synthetic` in `selection.json`). Neue `_iter_sample_dirs()` lässt nur
Verzeichnisse mit gültigem UUID-Namen gelten; alle vier Scan-Methoden nutzen
sie jetzt einheitlich; `summary()["incomplete_temp_dirs"]` zählt liegen
gebliebene Temp-Verzeichnisse diagnostisch, statt sie stillschweigend zu
ignorieren. `_validate_device_fields()` verlangt jetzt `identity_evidence`
(Pflichtfeld, wie `identity_confirmed`); der Export gibt es je Probe mit;
`dataset.js`/`index.html` haben dafür ein neues Eingabefeld. Das
Aufnahmebudget in `dataset_capture.CaptureRegistry.begin()` summiert nur noch
über *offene* (nicht gespeicherte) Einträge.

**Konsequenz:** Sechs neue Tests
(`test_synthetic_sample_is_excluded_from_export_like_uncertain`,
`test_incomplete_temp_sample_directory_does_not_count_after_restart`,
`test_device_creation_requires_identity_evidence`,
`test_identity_evidence_is_carried_through_to_the_export_manifest`,
`test_saved_captures_do_not_count_against_the_byte_budget`, plus eine
Korrektur eines Testfixtures, das versehentlich einen synthetischen
Testframe durch den vollen Exportpfad schickte). `291 passed, 2 skipped`
gesamt, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Aufgabe 7: Doku-Abschluss und Übergabe)
## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Aufgabe 6: unveränderlicher, direkt auswertbarer Export)

**Problem:** Der Export aus Aufgabe 1 war gegen den *beschriebenen*
Manifestvertrag getestet, aber nie gegen den echten Experiment-Loader aus
`codex/automatic-seven-segment` (`src/dispread/experimental/evaluation.py::load_manifest`,
Commit `6a18bdf`). Dessen `load_manifest` prüft zusätzlich projektübergreifend:
kein doppeltes Bildhash über den *gesamten* Export hinweg (nicht nur je
Gruppe) und höchstens ein Manifest-Eintrag je `heldout`-Unabhängigkeitsgruppe.

**Änderung:** `DatasetStore._export_locked()` entfernt jetzt zusätzlich
Proben mit einem bereits im Export vorhandenen Bildhash (Grund
`duplicate_image_hash_of=<id>` in `selection.json`) - unabhängig davon, aus
welcher Situation/Gruppe sie stammen. Neues
`scripts/check-dataset-export.py`: lokale Schema-/Pfad-/Hashprüfung ohne
Argument, oder mit `--experiment-root <worktree>` zusätzlich ein echter Aufruf
von `load_manifest` in einem **separaten Prozess** mit dem venv jenes
Worktrees (`subprocess.run` mit getrennten Argumenten, kein Shell-String,
importiert nur `load_manifest`, keine Modelle/den Runner). Ohne
`--experiment-root` meldet das Skript die externe Kompatibilität ausdrücklich
als **nicht geprüft** statt als Erfolg.

**Konsequenz:** `tests/test_dataset_export.py` verwendet ein bereits
lizenziertes Realbild aus dem Experiment (`data/scale.jpg`, Public Domain,
Original-Herkunft/-Label/-Split unverändert übernommen) und prüft: ein
kompatibler Export wird vom echten Loader akzeptiert, eine nachträglich
veränderte Bilddatei wird abgelehnt, der Export überlebt Verschieben in ein
anderes Verzeichnis und einen anderen Arbeitsordner, und eine spätere
Labelkorrektur (als neue, unabhängige Probe) verändert einen bereits
veröffentlichten Export nicht. Die Tests überspringen sich selbst, falls der
Experiment-Worktree lokal fehlt - ein fehlender Experimentstand ist kein
Bestehen. `286 passed, 2 skipped` gesamt, `ruff check` sauber. Diese
Integration erzeugt keine neue OCR-Messung.

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Aufgabe 5: Gruppen, Ähnlichkeitswarnung, Fortschritt)

**Problem:** Wiederholungsaufnahmen und beinahe-identische Bilder in
derselben Situation konnten unbemerkt als mehrere unabhängige Proben zählen;
synthetische Fixtures hätten die Zähler für lesbare/unlesbare *reale*
Testwerte künstlich aufblähen können; es gab keine Übersicht, welche
Bedingungen (negatives Vorzeichen, mehrere Zeilen, …) für ein Gerät noch
fehlen.

**Änderung:** `DatasetStore._find_similar_in_group()` vergleicht ein neues,
nicht-identisches Bild gegen die anderen Proben *derselben*
Unabhängigkeitsgruppe (kleines Graustufenbild, mittlere normierte Differenz,
`SIMILARITY_THRESHOLD = 0.02` ausdrücklich als Heuristik gekennzeichnet, keine
validierte Grenze). Eine Ähnlichkeitswarnung blockiert das Speichern, bis
`similarity_confirmed=true` **und** eine Begründung mitgeschickt werden -
beide werden dauerhaft in `sample.json` mitgeführt
(`similarity_warning`/`similarity_confirmation_reason`), keine stille
Löschung. `summary()` zählt `readable`/`unreadable`/`uncertain_or_draft` sowie
Familien/Technologien nur noch aus nicht-synthetischen Proben und liefert
zusätzlich `missing_conditions` (gesamt und je Gerät) aus dem festen
Aufgabenkatalog - eine Lücke wird als Lücke gemeldet, nicht als erledigt
umgedeutet. `dataset.js` zeigt die Warnung inline mit Begründungsfeld
(`#dataset-similarity`) und die fehlenden Bedingungen in der Übersichtszeile.

**Konsequenz:** Zehn Wiederholungen einer Situation zählen weiterhin als eine
Unabhängigkeitsgruppe, ein Auswahlwechsel ändert nur den Vertreter. Acht neue
`DatasetStore`-Tests plus ein Controller-Test für den vollen
Bestätigungs-Roundtrip. `280 passed, 2 skipped` gesamt, `ruff check` sauber,
beide JS-Dateien syntaktisch geprüft.

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Aufgabe 4: geführter Browserablauf)

**Problem:** Aufgaben 1-3 lieferten Speicherung, Kamerabindung und HTTP-Endpunkte,
aber keine Bedienoberfläche - der Sammelmodus war nur über rohe `/command`-Aufrufe
erreichbar.

**Änderung:** Neues, eigenständiges `static/dataset.js` (eigener Namespace
`DatasetCollection`, eigene `csrf`-Beschaffung, kein Zugriff auf
`workbench.js`-internen Zustand) plus ein neuer Bereich in `index.html`
("Datensatz sammeln"-Knopf im Header schaltet `#dataset` frei, `main.dataset-mode`
blendet Kamera/Shell/Log dafür aus - beide Ansichten teilen sich nichts
Zustandsbehaftetes). Ablauf: Gerät anlegen, Situation eröffnen, Rohbild
einfrieren (`dataset.capture`), Zielbox per Ziehen auf einem Canvas über der
Vorschau (`/dataset/captures/{token}.jpg`) markieren, Lesbarkeit/Wert/Bedingungen
eintragen, `dataset.save`, danach Übersicht und Export. Die Zielbox-Umrechnung
von sichtbaren CSS-Pixeln (object-fit:contain, inklusive Letterboxing) in
Originalbildpixel ist eine reine, exportierte Funktion (`toOriginalBox`) -
bewusst die einzige aus dem Modul sichtbare Funktion, weil eine falsche
Umrechnung sonst eine falsche Zielbox in einer gespeicherten Probe erzeugen
würde. Sie ist nachweislich unabhängig von `window.devicePixelRatio`, weil
ausschließlich mit `getBoundingClientRect()`-Größen (CSS-Pixel) gerechnet wird.

**Konsequenz:** Neue Tests `tests/dataset_client.test.mjs` (node, reine
Geometrie: gleiches Seitenverhältnis, horizontales und vertikales
Letterboxing, DPR-Unabhängigkeit, Klemmung an den sichtbaren Bildrand) und
`tests/test_dataset_client.py` als pytest-Anbindung plus `node --check`.
`271 passed, 2 skipped` gesamt, `ruff check` sauber, beide JS-Dateien
syntaktisch geprüft. **Offen:** ein echter interaktiver Browserdurchlauf
(Geräteanlage → Aufnahme → Speichern → Neustart → Export) ist in dieser
Umgebung nicht möglich - der headless Chromium dieser Umgebung lädt laut
[OQ-21](docs/open-questions.md) auch einfache lokale HTTP-Seiten nicht
zuverlässig; dieser Nachweis bleibt eine reale Browserabnahme (Aufgabe 7).

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Aufgabe 3: geschützte Vorschau- und Export-Endpunkte)

**Problem:** Der Sammelmodus konnte Aufnahmen und Exporte nur über den
generischen, JSON-basierten `/command`-Endpunkt bedienen. Weder eine
Bildvorschau der eingefrorenen Aufnahme noch ein Export-Download waren über
HTTP erreichbar.

**Änderung:** Zwei neue authentifizierte GET-Routen in `server.py`:
`/dataset/captures/{token}.jpg` (JPEG-Vorschau der offenen Aufnahme, wie die
bestehende `/frozen/{id}.jpg`) und `/dataset/exports/{id}.zip` (ZIP eines
bereits veröffentlichten Exports, on-demand über `datasets.zip_export()` und
`asyncio.to_thread` gebaut, damit die Ereignisschleife nicht blockiert). Beide
lösen ihre ID serverseitig auf (`DatasetStore.get_export_dir()` validiert das
Hex-Format und die Existenz) - kein vom Browser frei bestimmbarer Dateipfad.
Beide laufen durch die bestehende Middleware (Session-Pflicht, CSRF nur für
nicht-GET); unbekannte/abgelaufene IDs liefern 400 ohne weitere Details.

**Konsequenz:** Aufnahme-Vorschau und Exportdownload sind jetzt Teil derselben
authentifizierten Oberfläche wie der restliche Kamerapfad. `4 neue Tests`
(`tests/test_dataset_api.py`, echter aiohttp-Testclient wie
`test_camera_preview.py`), `269 passed, 2 skipped` gesamt, `ruff check`
sauber. Noch offen: Browserbedienung (Aufgabe 4).

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Nachschliff: Save/Export blockieren den Kamerapfad nicht mehr)

**Problem:** `dataset.save` und `dataset.export` liefen wie alle anderen
`command()`-Operationen unter `Controller.lock` - Bildkodierung, Plattenschreiben,
Hashbildung und ZIP-Erzeugung sind aber genau die teure I/O, die Abschnitt 5
der Spezifikation ausdrücklich ausserhalb dieses Locks verlangt. Ein
laufender Save hätte damit `status`, `stream.mjpg` und `publish()` (den
Kamera-Empfangspfad) blockiert.

**Änderung:** `dataset.save` und `dataset.export` werden jetzt wie
`ocr.suggest`/`layout.autofit` VOR dem `with self.lock:`-Block behandelt.
`_dataset_save()` haelt das Controller-Lock nur noch fuer die kurze Entnahme/
Markierung des Capture-Tokens, nicht fuer `DatasetStore.save_sample()` selbst.
`DatasetStore` bekommt dafuer ein eigenes `threading.Lock()`
(`create_device`/`update_device`/`begin_group`/`save_sample`/`select_sample`/
`export` serialisieren sich selbst, unabhaengig vom Controller).

**Konsequenz:** Ein neuer Test (`test_blocked_save_does_not_block_status_or_publish`)
haelt einen simulierten langsamen Save in einem Thread offen und misst, dass
`status` und `publish()` im Hauptthread währenddessen nicht blockieren.
`265 passed, 2 skipped` gesamt, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Aufgabe 2: Rohbildaufnahme ohne Profilkalibrierung)

**Problem:** Die bestehende Clipaufnahme (`clip.start`/`clip.stop`) verlangt
bestätigte Geometrie und Livebild - unbrauchbar für unkalibrierte reale
Prüfbilder. Der neue `DatasetStore` (Aufgabe 1) hatte noch keine Anbindung an
den Kamerabesitzer.

**Änderung:** Neues Modul `src/dispread/workbench/dataset_capture.py`
(`CaptureRegistry`): eigene Capture-Tokens, unabhängig vom kleinen
ROI-Editor-Cache (`Controller.frames`) - höchstens zwei gleichzeitig offene
Aufnahmen, insgesamt höchstens 64 MiB Rohbildspeicher, Ablauf nach zehn
Minuten. `Controller` bekommt `dataset_store`/`dataset_captures` sowie die
neuen `command()`-Operationen `dataset.device.create/update`,
`dataset.group.begin`, `dataset.capture`, `dataset.save`, `dataset.discard`,
`dataset.select`, `dataset.summary`, `dataset.export`. `_dataset_capture()`
kopiert `self.raw` sofort beim Aufruf - ein späteres `publish()` mit einem
neuen Bild ändert die offene Aufnahme nicht mehr. Capture/Save fassen
`self.config`, `self.tracker`, `self.reading` und den Gate-Zustand nicht an;
Capture lehnt `run`-Modus, fehlendes Livebild und unbekanntes Gerät/Gruppe ab.
Ein erfolgreich gespeicherter Token bleibt im Speicher (als `saved` markiert,
zählt nicht mehr gegen das Zwei-Aufnahmen-Limit) - ein Retry nach einer
verlorenen HTTP-Antwort trifft so wieder auf dieselbe gespeicherte Probe statt
auf "Aufnahme unbekannt"; ein Retry mit anderem Label bleibt über
`DatasetStore` ein Revisionskonflikt.

**Konsequenz:** Ein Rohbild lässt sich jetzt ohne bestätigtes Produktionsprofil
aufnehmen und mit Zielbox/Label sichern, ohne den bestehenden ROI-/Clip-/
OCR-Pfad zu berühren. `10 neue Tests`, `264 passed, 2 skipped` gesamt, `ruff
check` sauber. Noch offen: HTTP-Endpunkte und Browserbedienung (Aufgabe 3/4).

## 0.1.0.dev0 — 2026-09-18 (Datensatz-Sammelmodus, Aufgabe 1: Geräte, Samples, sichere Persistenz)

**Problem:** Die bestehende Clipaufnahme verlangt bestätigte Geometrie,
Gerätekennung und einen konstanten sichtbaren Wert je Clip - sie taugt nicht
als Sammelassistent für unkalibrierte reale Prüfbilder. Es fehlte ein eigener,
von Produktionsprofil/OCR unabhängiger Speicherpfad für Geräte, Rohbilder und
getippte Labels.

**Änderung:** Neues Modul `src/dispread/workbench/datasets.py` mit
`DatasetStore` (eigene Instanz, eigener Speicherbereich
`Controller.root / "datasets"`, keine Kamera-/Profilabhängigkeit):
Gerätestammdaten mit UUID, Revisionszähler und Split-Sperre nach der ersten
Aufnahme (`create_device`, `update_device`); Unabhängigkeitsgruppen
(`begin_group`); atomare, idempotente Sample-Speicherung über ein temporäres
Verzeichnis plus `rename` (`save_sample`) - ein Schreibfehler bei Bild oder
Metadaten hinterlässt keine fertige Probe, ein Retry mit demselben
`capture_token` erzeugt genau eine; ein zweiter Token mit anderem Label auf
denselben, bereits gespeicherten Token ist ein Revisionskonflikt statt eines
stillen Überschreibens. `normalize_label()` erhält Vorzeichen, führende
Nullen und Dezimalzeichen exakt, wandelt nur Komma zu Punkt und lehnt alles
andere ab. `validate_bbox()` lehnt eine Box außerhalb des Bildes ab, statt sie
an den Rand zu klemmen. Export erzeugt ein unveränderliches, formatkompatibles
Manifest (`schema_version: 1`) samt Abdeckungs- und Ausschlussliste; unsichere/
Entwurfs-Proben und unausgewählte Wiederholungen einer Gruppe bleiben draußen.

**Konsequenz:** Reale, unkalibrierte Prüfbilder lassen sich jetzt sicher
sammeln, ohne Produktionsfreigaberegeln zu berühren oder zu lockern.
`ValueRecord`, `ReleaseGate` und `TelegramFormatter` sind unverändert. Noch
offen: Anbindung an die Kamera/Workbench-Bedienung (Aufgabe 2 ff.) und die
Prüfung gegen den echten Experiment-Loader (Aufgabe 6). `44 neue Tests`,
`254 passed, 2 skipped` gesamt, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Abschlussreview, Nachschliff R6: Verlustarten im Clipmanifest trennen)

**Problem:** Mit dem R6-Fix zählen zwei verschiedene Verluste auf dasselbe
Feld: eine volle Schreib-Queue („Kamera schneller als die Platte", unter Last
erwartbar) und ein fehlgeschlagenes `cv2.imwrite` („Schreiben ging schief").
Die Logzeile unterscheidet sie, `clip.json` nicht — wer den Clip später
auswertet, kann die harmlose von der ernsten Ursache nicht trennen.

**Änderung:** Das Manifest trägt zusätzlich `write_failures`. `dropped_frames`
bleibt die Gesamtzahl der verlorenen Bilder (Invariante „Bilder im Manifest
plus verworfene = aufgenommene" unverändert), `write_failures` ist die
Teilmenge daraus, die am Schreiben scheiterte. Additiv und ohne
Schemawechsel: `ReplaySource` prüft nur `schema_version` und liest `frames`.
Zwei Tests prüfen jetzt zusätzlich die Diagnosewege: `write_failures` in
beiden Fehlerfällen bzw. `0` im Queue-voll-Fall, und ein fehlendes Manifest
nach `drain_clip_writer()` schlägt mit einer aussagekräftigen Meldung fehl
statt mit einem `FileNotFoundError`.

**Konsequenz:** Ein lückenhafter Clip sagt jetzt auch, *warum* er lückenhaft
ist. `210 passed`, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Abschlussreview R1/R8a/R8b: Vorschau, Vorschlagsgültigkeit, Nachführungsfrische)

**Problem:** (R1) `runAutofit()` legte den Vorschlag in `editing.autofit` ab,
die Leinwand zeichnete aber weiter `editing.ocr_grid` — das serverseitig
*übernommene* Raster, das die Statusabfrage alle 500 ms auffrischt. Der
Bediener sah damit ein anderes Raster als das, was sein ✓-Klick übernahm; die
visuelle Bestätigung, um die es bei diesem Schritt geht, lief ins Leere.
(R8a, zugleich OQ-31) Eine Handänderung an einem Layoutfeld der Einstelltabelle
nach einem erfolgreichen Autofit machte den Vorschlag nicht ungültig — der
✓-Klick schickte über `layout.set_many` das ganze alte Vorschlagsraster und
überschrieb die Eingabe (inkl. Polarität) stillschweigend; eine noch laufende
Autofit-Anfrage konnte dasselbe tun, wenn ihre Antwort spät eintraf. (R8b) Der
Tracker läuft auf jedem Bild, `reading["track"]` und die Statusflags wurden
aber nur bei einer frischen, gedrosselten Ablesung erneuert: die
Einstelltabelle meldete bis zu ein Drosselintervall lang „Nachführung folgt",
obwohl das gezeigte Bild die Anzeige verloren hatte.

**Änderung:** (R1) `Controller._autofit()` liefert zusätzlich
`ocr_grid = grid_geometry(layout)` des Vorschlags — dieselbe Rechnung wie für
das eingefrorene Bild, damit gezeichnetes und bestätigtes Raster nicht
auseinanderlaufen können; `draw()` zeichnet
`editing.autofit ? editing.autofit.ocr_grid : editing.ocr_grid`, das Polling
frischt weiterhin nur das übernommene Raster auf. (R8a) Neuer gemeinsamer
Pfad `invalidateAutofit(grund)` — benutzt von den bisherigen Canvas-Fällen und
neu von `send()` bei jedem `layout.set`/`layout.set_many`; er erhöht
zusätzlich `editing.requestId`, wenn gerade eine Autofit-Anfrage läuft, sodass
deren späte Antwort verworfen wird. (R8b) `reading_with_current_track()` zieht
auf einem gedrosselten Bild den Nachführungsbefund *dieses* Bilds in die
zwischengespeicherte Ablesung und setzt `tracking_lost`; Rohtext, Wert und
Freigabeentscheidung bleiben unangetastet die der letzten Ablesung, ein
einmal gesetztes `tracking_lost` wird nicht wieder entfernt.

**Konsequenz:** Was der Bediener vor dem ✓ sieht, ist das, was übernommen wird
— auch über beliebig viele Statusabfragen hinweg. Eine Handänderung sticht den
Vorschlag statt umgekehrt (OQ-31 damit geklärt). Der angezeigte
Nachführungszustand gehört zum aktuellen Bild, ohne die OCR-Drosselung
(OQ-24) aufzuheben. Neu: `tests/workbench_client.test.mjs` fährt
`workbench.js` im Auslieferungsstand unter `node` mit minimalem DOM-Ersatz
(kein neues Paket; angestoßen von `tests/test_workbench_client.py`, die
Rasterfixtures kommen aus `grid_geometry()`); 4 der 5 Browsertests sind gegen
den alten Stand rot nachgewiesen. `210 passed`, `ruff check` sauber,
`node --check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Abschlussreview R2/R6: eine Aufnahme, eine Konfiguration; ehrliches Manifest)

**Problem:** (R2) `_clip_start` kopiert das Profil einmal beim Start. Änderte
der Bediener ROI, Leseraster oder Kameraeinstellungen *zwischen* zwei
`publish()`-Aufrufen, lief die Aufnahme weiter — alle weiteren Bilder wurden
von einem veralteten Profil beschrieben. Die Absicherung aus Task 2 greift nur
bei einem Revisionswechsel *innerhalb* eines `publish()`-Aufrufs. (R6) Der
Manifesteintrag eines Bildes entstand beim Einreihen in die Schreib-Queue, und
`clip.json` wurde sofort beim Stop geschrieben: ein fehlgeschlagenes
`cv2.imwrite` (Rückgabe `False` oder Ausnahme) hinterließ ein Manifest, das
nie geschriebene Dateien auflistete, mit `dropped_frames: 0`.

**Änderung:** (R2) `_change()` — der Trichter, durch den jeder
konfigurationsändernde Befehl läuft — beendet eine laufende Aufnahme mit
`_clip_stop()` und protokolliert das, statt sie stillschweigend fortzuführen.
(R6) Der Schreib-Thread ist jetzt die einzige Stelle, die einen Frame ins
Manifest aufnimmt, und tut das erst nach erfolgreichem `cv2.imwrite`; er
schreibt am Ende auch `clip.json` selbst (neues Abschlusselement in der Queue
statt des bisherigen `None`-Sentinels). Fehlgeschlagene Schreibvorgänge zählen
wie verworfene Bilder. `_clip_stop()` bleibt damit nicht blockierend und hält
weiterhin kein Lock über ein `put` (Deadlockfix aus Task 2 unangetastet);
`close()` und `drain_clip_writer()` warten wie bisher begrenzt auf die
Schreiber. Der Livestatus zählt weiter die *eingereihten* Bilder, das Manifest
die *geschriebenen*.

**Konsequenz:** Ein Clip beschreibt genau eine Konfiguration; wer mitten in
einer Aufnahme etwas ändert, bekommt einen sauber beendeten Clip statt eines
still falsch etikettierten Datensatzes. `clip.json` erscheint erst, wenn die
Bilder wirklich auf der Platte liegen, und behauptet keine Datei, die nicht
geschrieben wurde — Bilder im Manifest plus `dropped_frames` ergeben weiterhin
die aufgenommenen. `205 passed` (9 neue Tests, davon 7 gegen den alten Stand
rot nachgewiesen), `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Abschlussreview R3/R4/R5/R7: Benchmark und Autofit-Eingabe)

**Problem:** Das Abschlussreview des ganzen Zweigs `ocr-selbstkalibrierung`
fand vier task-übergreifende Fehler, die kein Einzelreview sehen konnte.
(R3) `benchmark.normalise()` entfernte den Dezimaltrenner ganz — „28.80" und
„288.0" wurden beide zu „2880", `classify()` meldete `correct`, ein
Zehnerfehler war im Benchmark unsichtbar; die im `Outcome`-Docstring
versprochene Fehlerklasse `decimal` war nie implementiert. (R4)
`evaluate_clip` baute die URI als `f"replay://{directory}"`: bei einem
relativen Pfad las `urlparse` das erste Segment als URL-Autorität, `var` fiel
weg, geöffnet wurde ein nicht existierendes Verzeichnis. (R5)
`assert_disjoint_devices` nahm bei Annotationen ersatzweise `profile_name` —
ein Bedieneretikett: dasselbe Gerät unter zwei Profilnamen galt als zwei
Geräte, der Split sah fälschlich disjunkt aus. (R7) `parse_expected()` schnitt
mit `lstrip("+-")` jede Vorzeichenkette ab, „+-12" wurde still zu +12,
„--12" zu −12.

**Änderung:** `normalise()` vereinheitlicht nur noch Schreibweisen desselben
Werts (Komma/Punkt, „+", „1234." aus dem Ganzzahlformat, führende Null) und
behält die Dezimalstelle; `classify()` bekam die Klasse `decimal` und
vergleicht über `_parts()` Vorzeichen, Ziffernfolge und Nachkommastellen
getrennt. Neu `dispread.frames.path_uri()` (absolut + prozentkodiert) als
Bauvorschrift für Datei-URIs, benutzt von `evaluate_clip`; `_filesystem_path()`
setzt beim Öffnen `netloc` und `path` wieder zusammen, sodass auch
handgebaute `replay://relativ/pfad` (ebenso `folder://`, `video://`) nicht
mehr beschnitten werden. `_device_of()` verlangt eine ausdrückliche
`device_id` (Clip wie Annotation) und lehnt sonst ab, statt auf `profile_name`
auszuweichen; die Workbench schreibt `device_id` optional in
`annotation.json`. `parse_expected()` erlaubt genau ein führendes Vorzeichen
und wirft sonst `ValueError`.

**Konsequenz:** Ein Stellenfehler wird als eigene Klasse `decimal` gezählt
statt als Treffer; der dokumentierte CLI-Aufruf mit relativem Glob wertet das
richtige Verzeichnis aus; ein geräte­disjunkter Split wird nur noch
bescheinigt, wenn die Geräteidentität wirklich bekannt ist (Altannotationen
ohne `device_id` führen zu einer klaren Ablehnung statt zu einer falschen
Zusicherung); mehrdeutige Vorzeicheneingabe wird abgelehnt statt gedeutet.
`197 passed`, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Task 12: Doku-Abschluss der OCR-Selbstkalibrierung)

**Problem:** PLAN_2026-09-11-ocr-selbstkalibrierung.md's Tasks 1–11 sind
abgeschlossen bzw. geprüft-und-bewusst-gesperrt (Task 11); die Doku-Pflicht
aus `AGENTS.md` verlangt, das vor dem Sitzungsende in `docs/` nachzuziehen —
inklusive neuer Unbekannten, die während der Task-Reviews entdeckt wurden.

**Änderung:** `docs/project_history.md` um den Entscheidungseintrag „OCR-
Selbstkalibrierung: verankerte Werkzeuge statt genereller OCR/Klassifikator"
ergänzt (ssocr, gitterfreier Per-Ziffer-Decoder, synthetisch trainierter
Klassifikator, Rasterfeinschliff je Bild — alle verworfen, mit Begründung).
`docs/open-questions.md` um OQ-26 bis OQ-32 ergänzt: drei aus dem Plan selbst
(Nachführungsgrenzen, Rasterfeinschliff, Autofit-Eindeutigkeit) und vier neu
aus dieser Sitzung (`calibrated_on`-Zeitpunkt, nicht-atomarer `roi`-Op
gegenüber einem fehlschlagenden `QuadTracker`-Aufbau, möglicher
Regler-Stale-Zustand nach Autofit, fehlender Fallback für einen unbekannten
`kind` in `edit_row()`/`_row()`). `docs/ROADMAP.md`s P1-/P2-Zeilen korrigiert
(widersprachen zuvor der bereits fertigen `replay://`-Implementierung bzw.
ignorierten die inzwischen vier realen Clips). `CLAUDE.md`s Aufbau-Tabelle:
`replay://` von TODO auf fertig gezogen, `track` (`QuadTracker`) als neue
Pipelinestufe aufgenommen. `docs/status.md` komplett neu geschrieben
(Sitzungsendstand, nicht angehängt).

**Konsequenz:** Die Dokumentation spiegelt den tatsächlichen Endstand dieser
Sitzung wider — inklusive der bewussten Sperrung von Task 11 und der neuen,
noch offenen Punkte. `173 passed`, `ruff check` sauber, keine `src/`-Änderung
in diesem Task.

## 0.1.0.dev0 — 2026-09-18 (Task 9 Review-Fund: Reflexion wird bei LCD-Polarität verschluckt)

**Problem:** Selbstreview von Task 9 (Anzeigepolarität) deckte auf, dass
`saturated_fraction` in `SevenSegmentReader.read` auf dem für den
Segment-Dekoder umgekehrten Graustufenbild berechnet wurde
(`gray` nach der `255 - gray`-Umkehr bei `polarity == "dark_on_bright"`).
Eine echte Reflexion — roh nahe 255 — fällt nach dieser Umkehr auf nahe 0 und
verschwindet aus der Überstrahlungsmessung. Empirisch nachgestellt: ein
Reflexionsfleck, der roh 2,3 % der Fläche saturiert (über der 2 %-Schwelle),
wurde nach der Umkehr mit `saturated_fraction=0.0` gemeldet, kein
`glare`-Flag, Wert wurde weiterhin ausgegeben. Genau die stille
Fehlablesung, die Konzept.md §9 als Hauptproblem nennt und die dieser
Befund verhindern soll.

**Änderung:** `SevenSegmentReader.read` sichert das Graustufenbild vor der
Polaritätsumkehr als `raw_gray` und berechnet `saturated_fraction` daraus,
nicht aus dem für den Dekoder umgekehrten `gray`. Für `bright_on_dark`
(Default) ist `raw_gray` identisch zu `gray`, also keine Verhaltensänderung.
Neuer Regressionstest
`tests/test_sevenseg.py::test_reflexion_wird_bei_lcd_polaritaet_nicht_verschluckt`.

**Konsequenz:** Eine echte Reflexion wird unter `dark_on_bright` jetzt
zuverlässig als `glare` gemeldet statt stillschweigend als gültiger Wert
durchzugehen. `173 passed`, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Task 9: Anzeigepolarität ins Profil)

**Problem:** `SevenSegmentReader` und `DisplayLayout` gingen fest von heller
Anzeige auf dunklem Grund aus (LED). Für LCD-Anzeigen mit umgekehrter
Polarität (dunkle Segmente auf hellem Grund) fehlte jede Behandlung —
OQ-13 Fall 2. Ein LCD-Bild ungeprüft durch den Leser zu schicken hätte auf den
komplementären Segmentmustern gearbeitet, die in aller Regel keinem gültigen
Ziffernmuster entsprechen und dadurch zwar meist, aber nicht garantiert
abgelehnt worden wären — kein Ersatz für eine explizite Profilangabe.

**Änderung:** Neues Feld `DisplayLayout.polarity: str = "bright_on_dark"`
(sonst `"dark_on_bright"`), wandert über `to_dict`/`from_dict` automatisch ins
Profil; `profiles.validate_layout` lehnt unbekannte Werte ab.
`SevenSegmentReader.read` invertiert das Graustufenbild einmalig ganz am
Anfang, wenn `polarity == "dark_on_bright"` — danach gilt im ganzen Leser
wieder "hell = an", keine zweite Fallunterscheidung. Neue Auswahlzeile
`layout.polarity` in der Workbench (`fields.py`), modelliert auf
`layout.has_sign`. Gespeicherte Profile ohne das Feld bekommen beim Laden
automatisch `bright_on_dark` (bestehende Schema-3-Migration in
`profiles.validate()`) — keine Schemaversion nötig, heutiges Verhalten bleibt
unverändert. Neue Tests in `tests/test_sevenseg.py`
(`test_lcd_polaritaet_wird_gelesen`,
`test_falsche_polaritaet_wird_abgelehnt_nicht_falsch_gelesen`,
`test_unbekannte_polaritaet_wird_abgelehnt`) sowie eine erweiterte Prüfung in
`tests/test_workbench.py::test_field_rows_offer_only_valid_choices`.

**Konsequenz:** LCD-Anzeigen lassen sich jetzt über das bestätigte Profil
korrekt lesen; eine falsch eingestellte Polarität führt zur Ablehnung, nicht
zu einer stillen Fehlablesung. OQ-13 Fall 2 ist geklärt, Fall 1 (Anzeige
zeigt ausschließlich "8") bleibt offen. `172 passed`, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-18 (Task 8 Review-Fund: TUI-Absturz bei `reading.track`)

**Problem:** Die neue `reading.track`-Zeile aus Task 8
(`fields._reading_rows()`) bekam `kind="text"` — wortgetreu aus dem
Plan-Snippet übernommen, das der Reviewer nun als schlicht falsch einstuft.
`rows(state)` versorgt sowohl `workbench.js` als auch `tui.py` mit denselben
Zeilen. In `tui.py` behandelt `edit_row()` (`tui.py:195-234`) jede Zeile, die
nicht `kind="info"` oder `kind="choice"` ist, als Zahleneingabe und greift
dabei synchron, vor jeder Bedienereingabe, auf `row["min"]`/`row["max"]`/
`row["presets"]` zu. Die Zeile übergibt keine dieser Kwargs — genau wie ihre
drei Geschwister `reading.value`/`reading.gate`/`reading.evidence`, die
deshalb korrekt `kind="info"` tragen. Das Ergebnis: `KeyError: 'min'`, sobald
der Bediener die Zeile im Terminal (`dispread tui`) anwählt — ein echter,
reproduzierbarer Absturz bei normaler Bedienung, kein hypothetischer Fall.

**Änderung:** `reading.track` in `fields._reading_rows()` bekommt
`kind="info"` statt `kind="text"` — identisch zu ihren drei Geschwisterzeilen.
Sonst keine Änderung an Werten oder Kwargs. Neuer Regressionstest
`tests/test_workbench.py::test_tui_oeffnet_nachfuehrzeile_ohne_absturz`: baut
eine echte `WorkbenchTUI`, treibt sie über Textuals `run_test()`/Pilot per
Tastatur genau auf die `reading.track`-Zeile (echter, über den `roi`-Op
bestätigter Controller mit laufendem Tracker, damit die Zeile echt vorhanden
ist) und wählt sie aus — der reale `DataTable.RowSelected` → `select()` →
`edit_row()`-Pfad. Vor dem Fix schlägt der Test mit genau dem beschriebenen
`KeyError: 'min'` fehl (verifiziert); nach dem Fix zeigt `edit_row()` nur den
Hinweistext, ohne einen Eingabedialog zu öffnen.

**Konsequenz:** Die Terminal-Oberfläche stürzt beim Anwählen der
Nachführungszeile nicht mehr ab; der neue Test hätte den Fund erfasst und
verhindert eine Wiederholung. `169 passed`, `ruff check` und
`node --check workbench.js` weiterhin sauber.

## 0.1.0.dev0 — 2026-09-18 (Task 8: Nachführgüte sichtbar machen)

**Problem:** Task 7 verdrahtete den `QuadTracker`, hielt aber bewusst die
grüne "bestätigt"-Kontur an `roi_quad(image, config)` fest statt an
`track.quad` — richtig, aber damit blieb eine tatsächlich angewandte
Nachführungskorrektur für den Bediener unsichtbar: weder im Livebild noch in
der Einstelltabelle war zu erkennen, dass und wie weit nachgeführt wurde. Der
Planentwurf für diesen Task verlangte die dritte Farbe fälschlich in
`workbench.js`s `draw()` — die läuft aber nur während einer eingefrorenen
Editier-Sitzung auf einem statischen Bild, nie während des laufenden
Betriebs; das serverseitig in die MJPEG-Bytes eingebrannte Overlay in
`Controller.publish()` ist der einzige Ort, an dem der Bediener das
Livebild überhaupt sieht.

**Änderung:** `Controller.publish()` zeichnet direkt nach der grünen
bestätigten Kontur — wenn `track is not None and track.quad is not None`,
also wenn die Nachführung tatsächlich korrigiert hat — eine zweite Kontur in
Orange/Rot `(60, 140, 230)` (BGR) aus `track.quad`; von Grün `(130, 220,
130)` (bestätigt) und Gelb/Cyan `(0, 220, 220)` (Vorschlagsboxen/
Vergleichssuche) klar unterscheidbar. Ohne Tracker oder bei verworfener
Korrektur wird nichts zusätzlich gezeichnet. `fields._reading_rows()` fügt im
Normalfall (bestätigt, Livebild, lesbares Ergebnis) eine Zeile
`reading.track` an, sofern `reading["track"]` gesetzt ist: bei `corrected`
den Versatz in Prozent und die Drehung in Grad, sonst
"AUS DEM RAHMEN: <Grund>" über die neue `REASONS`-Übersetzungstabelle.

**Konsequenz:** Der Bediener sieht im Livebild sofort, ob und wie weit
nachgeführt wurde — eine stille Korrektur, die aussieht wie die eigene
Bestätigung, ist damit ausgeschlossen. Neue/erweiterte Tests:
`tests/test_workbench.py`
(`test_gruene_kontur_bleibt_die_bestaetigte_geometrie_bei_nachfuehrung` um die
Orange-Kontur-Prüfung erweitert,
`test_keine_nachfuehrungskontur_ohne_tracker_korrektur`,
`test_keine_nachfuehrungskontur_bei_abgelehnter_korrektur` (lebender Tracker,
aber verworfene Korrektur — die eigentliche Invariante),
`test_nachfuehrzeile_erscheint_im_bedienbild`,
`test_nachfuehrzeile_zeigt_ablehnungsgrund_bei_verletzter_grenze`,
`test_nachfuehrzeile_fehlt_ohne_nachfuehrung`, je mit Positivkontrolle, dass
der jeweils erwartete Zweig auch wirklich erreicht wurde) — über echte
`Controller`-Momentaufnahmen (`fields.rows(controller.snapshot())`), nicht
über handgebaute Zustände.

## 0.1.0.dev0 — 2026-09-18 (Task 7: Nachführung im Lesepfad des Workbench-Controllers)

**Problem:** Der `QuadTracker` aus Task 6 existierte, war aber an keiner
Stelle verdrahtet — ein leichter Versatz der Anzeige (Vibration, angestoßene
Kamera) brach den laufenden Ablesevorgang der Workbench genauso ab wie zuvor,
weil `Controller.publish()`/`_read()` immer nur die einmal bestätigte
`roi_quad` benutzten, ohne Nachführung.

**Änderung:** `Controller` legt im `roi`-Op (Bestätigungspfad, nicht im
`annotate`-Zweig) einen `QuadTracker` gegen das gerade eingefrorene Bild an
(`self.tracker`) und verwirft ihn in `_change()` wie das bestehende
`self.gate` — eine geänderte Konfiguration darf keine Referenz der alten
mitschleppen. `publish()` ruft `self.tracker.update(image)` auf jedem Bild
auf (unthrottled, wie in Task 6 gemessen: 2,63 ms Median) und liest/überlagert
mit dem ggf. korrigierten Quad — zeichnet aber die grüne "bestätigt"-Kontur
weiterhin aus der unveränderten `roi_quad(image, config)`
(`confirmed_quad`), niemals aus `track.quad`. Ohne diese Trennung hätte eine
begrenzte, maschinelle Nachführungskorrektur optisch nicht von der
menschlichen Bestätigung zu unterscheiden ausgesehen — ein Verstoß gegen die
eigene Invariante dieses Projekts, dass Bestätigtes und Nachgeführtes
unterscheidbar bleiben (Task 8 gibt der Nachführung eine eigene Farbe).
Verstößt die Nachführung gegen ihre Grenzen (`track.quad is None`), ersetzt
`_read()` das eingefrorene `ReadResult` (`dataclasses.replace`, da `frozen`)
um das Statusflag `tracking_lost` — ein Befund über das Bild, kein Befund des
Lesers, deshalb nicht in `sevenseg.py`. `GateConfig.blocking_flags` (in
`src/dispread/validate.py`) nimmt `tracking_lost` in die Menge der
Betriebszustände auf, die einen Zahlenwert ausschließen (Konzept.md §4: bei
Verlust der Anzeige wird der Messwert ungültig). Jedes Leseergebnis führt neu
`reading["track"] = {"score", "shift", "rotation_deg", "corrected", "reason"}`.

**Konsequenz:** Ein Bild lang toleriert die Workbench einen begrenzten
Versatz derselben bereits bestätigten Anzeige, ohne dass der Bediener erneut
bestätigen muss — eine andere Anzeige zu wählen bliebe weiterhin ein eigener
Bestätigungsakt. `config["roi_quad"]` bleibt dabei unverändert und von der
laufenden Korrektur getrennt sichtbar. Neue Tests: `tests/test_workbench.py`
(`test_verrutschte_anzeige_wird_weiter_gelesen`,
`test_zu_grosser_versatz_fuehrt_zur_ablehnung_nicht_zur_korrektur`,
`test_tracker_wird_bei_konfigurationsaenderung_verworfen`,
`test_gruene_kontur_bleibt_die_bestaetigte_geometrie_bei_nachfuehrung`) und
`tests/test_gate_und_referenz.py`
(`test_verlorene_nachfuehrung_blockiert_die_freigabe`) — alle mit echten
gerenderten Anzeigen und echtem `QuadTracker`/`SevenSegmentReader`, keine
Mocks der Trackinglogik.

## 0.1.0.dev0 — 2026-09-18 (QuadTracker: `_moved_quad` bildete unter Drehung eine geometrisch verzerrte Anzeige ab)

### Reviewfund (Critical) zu Task 6: Invertierungs-plus-Vorzeichen-Hack in `_moved_quad` ist keine gültige Transformation

**Problem:** `_moved_quad` in `src/dispread/track.py` invertierte die von
`cv2.findTransformECC` gelieferte affine Matrix mit
`cv2.invertAffineTransform` und negierte anschließend **nur** deren
Translationsspalte (`inverse[:, 2] = -inverse[:, 2]`). Das war kein Bugfix,
sondern ein Hack, um den einzigen gepinnten Test
(`test_kleine_verschiebung_wird_nachgefuehrt`, reine Verschiebung ohne
Drehung) zum Grünwerden zu bringen — bei reiner Translation fällt der Fehler
nicht auf, weil der Rotationsanteil der Matrix dort die Einheitsmatrix ist.
Für jede tatsächliche Drehung ist das Ergebnis weder die Vorwärtstransformation
noch die echte Inverse, sondern eine inkonsistente Mischung aus beiden: der
Rotationsanteil der Inversen bleibt unverändert, während nur die Translation
umgedreht wird. Der Task-Reviewer hat unabhängig nachgewiesen, dass das für
eine Szene mit 6 px Verschiebung und 2,0° Drehung (beide innerhalb der
Standardgrenzen `max_shift=10%`, `max_rotation_deg=3.0`) zu einem um ca. 17 px
verzerrten, nicht-rigiden Quad führt — unbemerkt, weil kein Test eine
akzeptierte Drehung mit tatsächlicher Geometrieprüfung abdeckte. Der
Implementierungsbericht zu Task 6 stellte das ursprünglich fälschlich als
unauffälligen Vorzeichen-Fix dar.

**Änderung:** Beide Zeilen (`cv2.invertAffineTransform` und die
Negierung der Translationsspalte) entfernt. `_moved_quad` wendet die von
`cv2.findTransformECC` zurückgegebene Matrix `warp` jetzt direkt (vorwärts,
ohne Inversion) auf die Eckpunkte an — `cv2.findTransformECC(reference,
current, warp, ...)` bestimmt `warp` so, dass es einen Punkt aus `current`
auf den entsprechenden Punkt in `reference` abbildet; angewandt auf die
referenzraum-Eckpunkte (die Arbeitsbild-Koordinaten des bestätigten Quads)
liefert es genau deren aktuelle Position im neuen Bild — ohne Inversion.
Neuer Test `test_drehung_innerhalb_der_grenze_wird_korrekt_nachgefuehrt` in
`tests/test_track.py` deckt exakt die zuvor ungetestete Lücke: eine Drehung
und Verschiebung *innerhalb* der Grenzen, mit Prüfung der zurückgegebenen
Eckpunkte gegen eine unabhängig berechnete Grundwahrheit (dieselbe affine
Transformation direkt auf die Original-Eckpunkte angewandt), nicht nur
`quad is not None`. Der Test schlägt mit der alten Hack-Implementierung
nachweislich fehl (verifiziert) und ist mit der Korrektur grün.

**Konsequenz:** Die Nachführung ist unter Drehung jetzt geometrisch korrekt
(rigide Transformation statt verzerrter Mischform); die bestehende
Vorzeichenkonvention (Test `test_kleine_verschiebung_wird_nachgefuehrt`)
bleibt unverändert erfüllt. Die neue Testabdeckung schließt die Lücke, die
den ursprünglichen Fehler durch die volle Test- und Lint-Suite hindurch
unentdeckt ließ.

## 0.1.0.dev0 — 2026-09-11 (QuadTracker: Nachfuehrung gegen Referenzbild, nicht Bild-zu-Bild)

### Bedienerrückmeldung: bei längeren Lesungen verrutscht die Kamera, Erkennung bricht ab

**Problem:** Bei längeren Messvorgängen (>10 Minuten) rutscht die Raspberry-Pi-Kamera oder der Messverstärker graduell aus der Position, und die Erkennung bricht mit `UNREADABLE` ab. Ein manueller Neustart der Workbench oder ein Neukalibrieren der ROI behebt das Problem. Ursache ist eine Kette von Bild-zu-Bild-Registrierungen, die Drift akkumuliert — nach einer Stunde ist die gemessene Geometrie weit von der ursprünglich bestätigten entfernt, ohne dass eine einzelne Registrierung je ihre Grenzen (±10%, ±3°) verletzt hätte.

**Änderung:** Neuer `QuadTracker` in `src/dispread/track.py` (Task 6 des Plans
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](docs/PLAN_2026-09-11-ocr-selbstkalibrierung.md)),
implementiert in TDD nach dem Plan-Brief mit sechs Tests. Der Tracker registriert
jedes neue Bild immer gegen das bei der ROI-Bestätigung (im `confirm`-Modus)
gespeicherte Referenzbild, niemals gegen das vorige Bild. Die gefundene
Verschiebung, Drehung und ECC-Güte werden gegen feste Grenzen (`max_shift=10%`,
`max_rotation_deg=3.0`, `min_score=0.60`) geprüft; Verletzungen führen zur
Ablehnung ohne Korrektur (sichere Richtung laut Konzept.md §7). Das Arbeitsbild
wird einschrittig direkt aus dem Rohbild auf `work_size` entzerrt, nicht aus
dem bereits `CROP_SIZE`-entzerrten Ausschnitt, damit ECC keine Resampling-Artefakte
als Bewegung misst (Konzept.md §3).

Laufzeitmessung auf realen 960×720-Bildern (`var/workbench/annotations/8a18ee05…`):
Median **2.63 ms**, P95 2.82 ms, Max 3.50 ms — deutlich unter der 10-ms-Schwelle.

**Konsequenz:** Die Nachfuehrung läuft bei jedem gelesenen Bild (keine Drosselung),
analog zur Kandidatensuche im `run`-Modus ohne `CANDIDATE_INTERVAL_S`-Throttling.
Bei 15 fps ist der Nachführungsaufwand <5 % der pro-Frame-Zeit und blockiert nicht.
Die Nachfuehrung für Task 7 wird nicht gedrosselt (`run` bei jedem Frame).
Gemessene Timing und Entscheidung sind dokumentiert in `docs/VALIDATION.md`.

## 0.1.0.dev0 — 2026-09-11 (Autofit-Vorschlag wurde nicht ungültig, wenn die Geometrie sich änderte)

### Ein veralteter Autofit-Vorschlag konnte gegen eine Geometrie übernommen werden, für die er nie gefittet wurde

**Problem:** Reviewfund zu Task 5 des Plans
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](docs/PLAN_2026-09-11-ocr-selbstkalibrierung.md)
(commit `2f98f41`). `editing.autofit` (`static/workbench.js`) wurde nie
ungültig gemacht, wenn sich die angezeigte ROI-/OCR-Geometrie änderte, ohne
dass ein frischer erfolgreicher `runAutofit()`-Lauf ein neues Ergebnis
lieferte. Zwei konkrete Pfade: (1) `runAutofit()` blendete bei einem
Fehlschlag (`!r.matched`) oder einer Ausnahme die Ergebniszeile aus
(`updateAutofitResult(null)`), ließ `editing.autofit` selbst aber unverändert
— ein Bediener, der nach einem erfolgreichen Autofit mit einem Tippfehler
erneut kalibrierte, sah scheinbar nichts Übernehmbares, aber der nächste
✓-Klick sendete trotzdem den alten Vorschlag per `layout.set_many`. (2) Ein
Klick zurück in die ROI-Box während der `ocr`-Stufe führte zurück zu Stufe A,
ohne `editing.autofit` zu löschen; eine erneut bestätigte ROI (`confirmRoi()`)
überschrieb `editing.ocr_box` per `ocr.suggest`, ließ den alten Vorschlag aber
stehen — da `rectify()` unabhängig von der Quad-Form immer auf `CROP_SIZE`
skaliert, kann eine geänderte ROI die Zifferngeometrie im Ausschnitt
tatsächlich ändern, wodurch `digit_gap_ratio`/`thickness_ratio`/etc. aus dem
alten Vorschlag nicht mehr passen. Verstößt gegen die Festlegung, dass Autofit
nur vorschlägt und ausschließlich der ✓-Klick übernimmt (AGENTS.md) — der
✓-Klick hätte sonst einen Vorschlag übernommen, den die Oberfläche nicht mehr
anzeigt und der zur aktuellen Geometrie nicht mehr passt.

**Änderung:** `editing.autofit=null` (und `updateAutofitResult(null)`, blendet
`#autofit-result` aus) an jeder Stelle ergänzt, an der sich die angezeigte
ROI-/OCR-Geometrie ändert, ohne dass `runAutofit()` gerade frisch ein neues
Ergebnis liefert: im `!r.matched`-Zweig und im `catch`-Block von
`runAutofit()`, im Klick-Handler, der aus der `ocr`-Stufe zurück zu `roi`
führt (`canvas.onpointerdown`), und in `toggleEdit()` — dort sowohl beim
Betreten des Edit-Modus (weiteres Ziehen kann die Geometrie ändern) als auch
beim Verwerfen (Rückfall auf `preEdit` ist selbst eine Geometrieänderung).
Der Ecken-/Körper-Zug per Maus (`onpointermove`) ist ausschließlich im
Edit-Modus erreichbar, der nur über `toggleEdit()` betreten wird — damit ist
dieser Pfad durch die `toggleEdit()`-Änderung mit abgedeckt, ohne eine eigene
Prüfung pro Zugbewegung zu brauchen.

**Konsequenz:** `editing.autofit` ist jetzt nie mehr gesetzt, außer er stammt
aus dem zuletzt erfolgreichen `runAutofit()`-Lauf gegen die aktuell
angezeigte Geometrie — ein ✓-Klick kann keinen unsichtbaren, veralteten
Vorschlag mehr stillschweigend übernehmen. Verifiziert mit einem
node-`vm`-Testharness, der die reale `workbench.js` lädt (kein JS-Testrunner
im Projekt, nur `node --check` — siehe
`.superpowers/sdd/PLAN_2026-09-11-ocr-selbstkalibrierung/task-5-report.md`,
Abschnitt „Fix round 1"): beide im Reviewfund genannten Szenarien schlagen
gegen den alten Code fehl und bestehen gegen den Fix.

## 0.1.0.dev0 — 2026-09-11 (Einrichtung per getipptem Wert statt per Regler)

### Die Segmentpunkte müssen exakt sitzen, sonst liest das System nicht — das Justieren kostete die meiste Einrichtzeit

**Problem:** Task 5 des Plans
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](docs/PLAN_2026-09-11-ocr-selbstkalibrierung.md).
Task 4 lieferte `fit_layout` (`src/dispread/ocr/autofit.py`), aber ohne
Anbindung an Controller oder Bedienoberfläche blieb die einzige Möglichkeit,
`digit_gap_ratio`, `sign_cell_ratio`, `thickness_ratio` und `inset_ratio` zu
setzen, weiterhin die manuelle Reglerjustage in der Einstelltabelle — Zeile
für Zeile, Probieren, erneut ablesen.

**Änderung:** Neuer Op `layout.autofit` (`src/dispread/workbench/controller.py`,
`Controller._autofit`): nimmt `{id, quad, ocr_box, text}`, entzerrt das
eingefrorene Bild, ruft `fit_layout` und liefert Raster, OCR-Box,
Trennschärfe/Gegenkandidat und eine Vorschau (`self.reader.read` auf dem
Vorschlag) — **übernimmt nichts**. Wie `ocr.suggest` bewusst außerhalb des
Controller-Locks behandelt (`command()`, vor dem `with self.lock:`-Block):
`fit_layout` braucht rund hundert Leseraufrufe, und genau eine über das Lock
blockierte Bedieneingabe während einer solchen Suche war die Ursache des am
2026-09-10 gemeldeten Race-Condition-Bugs (OQ-24). Neuer Op `layout.set_many`
setzt mehrere Layoutfelder atomar in einer Revision (Vorbild:
`camera.set_many`) und zieht — wie `layout.set` es bereits tut — die Revision
eingefrorener Bilder mit; ohne das würde der nachfolgende `roi`-Op mit
„Modus/Profil geändert" scheitern, obwohl sich nur das Leseraster geändert
hat. `self.calibrated_on` (von Task 2 vorbereitet) wird hier erstmals gesetzt:
die Frame-Sequenz des zuletzt erfolgreich verrasterten Bildes.

Bedienoberfläche (`static/index.html`, `static/workbench.js`): dritter Knopf
🎯 „kalibrieren" neben ✓/✎ in Stufe B öffnet dasselbe Werteingabefeld, das
bisher nur `annotate` zeigte (`editing.awaiting` unterscheidet jetzt, wofür
der nächste „übernehmen"-Klick bestimmt ist). `runAutofit()` folgt demselben
`editing.pending`/`editing.requestId`-Überholschutz wie `confirmRoi()` — eine
spät eintreffende Antwort auf eine bereits verlassene Bearbeitung wird
verworfen. Eine neue Ergebniszeile (`autofit-result`) zeigt gelesenen Wert und
Trennschärfe, mit sichtbarem Hinweis bei `flat_optimum`. `confirmOcr()` sendet
bei einem offenen Vorschlag zuerst `layout.set_many`, erst danach den
unveränderten `roi`-Op — die Reihenfolge ist Pflicht, damit `roi` gegen die
durch `layout.set_many` bereits erhöhte Revision läuft. **Der ✓-Klick bleibt
die einzige Stelle, an der `confirmed` wahr wird**, auch mit 🎯: der Vorschlag
selbst ändert das aktive Profil nicht.

Beim Verdrahten fiel ein Fehler in der Task-5-Vorlage auf: `fit_layout`
erwartet als `crop`-Argument den vollen entzerrten ROI-Ausschnitt (es schneidet
`ocr_box` bei jeder Auswertung selbst zu, siehe `_box_candidates` in
autofit.py — `ocr_box` ist einer der gesuchten Freiheitsgrade). Ein
vorheriges `crop_box(crop.image, ocr_box)` vor dem Aufruf hätte denselben
Ausschnitt ein zweites Mal auf dieselben Koordinaten zugeschnitten und den
Ziffernbereich verstümmelt — durch einen Test mit einem echten
gerenderten Sollwert aufgedeckt (`test_autofit_liefert_einen_vorschlag_ohne_etwas_zu_bestaetigen`
schlug mit `matched=False` fehl, obwohl Bild und Text exakt zusammenpassten).

**Konsequenz:** Der Bediener tippt einmal den angezeigten Wert; `layout.autofit`
schlägt daraus das Raster vor und zeigt, was damit gelesen wird. Die Regler
bleiben als Handkorrektur, nicht mehr als einziger Weg. Mehrdeutige (flache)
Optima werden gemeldet statt still aufgelöst — der aus Task 4 bekannte Befund
(`flat_optimum=True` bei allen fünf real gefundenen Rastern, weil
`thickness_ratio`/`inset_ratio` die tatsächliche Lesegeometrie noch gar nicht
beeinflussen) bleibt dadurch für den Bediener sichtbar statt verdeckt zu
werden; die zugrundeliegende Ursache ist weiterhin offen (siehe Task-4-Eintrag
unten, docs/VALIDATION.md).

## 0.1.0.dev0 — 2026-09-11 (Autofit: Rastergeometrie aus einem einmal getippten Sollwert)

### Vier Geometrie-Verhältnisse mussten von Hand justiert werden, und mindestens zwei davon sind unterbestimmt

**Problem:** Task 4 des Plans
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](docs/PLAN_2026-09-11-ocr-selbstkalibrierung.md).
`digit_gap_ratio`, `sign_cell_ratio`, `thickness_ratio` und `inset_ratio`
mussten bislang von Hand geschätzt werden. Die Ausgangsmessung dieser Sitzung
(docs/VALIDATION.md) zeigte zudem: zwei weit auseinanderliegende Sätze
(`thickness=0,20/inset=0,05` und `thickness=0,12/inset=0,10`) erreichen an
sechs realen Bildern dieselbe Trefferzahl — ein Autofit, der nur auf „stimmt"
optimiert, würde davon einen beliebigen wählen und der Bediener bestätigte
eine zufällige Geometrie.

**Änderung:** `src/dispread/ocr/autofit.py`, `fit_layout(crop, text, layout,
ocr_box)`: `digits`/`decimals`/`has_sign` werden aus dem einmal getippten
Sollwert abgeleitet (`parse_expected`), nicht gesucht — ein positiv gezeigter
Wert beweist keine fehlende Vorzeichenstelle. Koordinatenabstieg über zwei
Durchläufe, rund 100 deterministische, fest aufgezählte Auswertungen ohne
Zufall. Zielfunktion ist nicht bloße Übereinstimmung, sondern unter allen
exakt passenden Parametersätzen die größte Trennschärfe
(`read.diagnostics["min_margin"]`, das vorhandene, dafür gedachte Maß).
`AutofitResult` führt `separation`, `runner_up` und `flat_optimum` getrennt,
damit ein flaches Optimum als solches erkennbar bleibt statt als scheinbar
sichere Zahl anzukommen. Findet die Suche keinen exakt passenden Satz, bleibt
`matched=False` und das **unveränderte** Eingabelayout wird zurückgegeben —
keine Teilvermutung. Eigene, lokale `_crop_box`/`CROP_SIZE`-Nachbildung statt
Import aus `dispread.workbench.controller`, um den für Task 5 vorgesehenen
umgekehrten Import (Controller importiert `fit_layout`) nicht zirkulär zu
machen.

Gemessen an den sechs auswertbaren realen Annotationen (eine Geräteinstanz,
docs/VALIDATION.md): 5 finden ein passendes Raster, 1 (`8a18ee05…`) meldet
ehrlich `matched=False` — dieselbe Annotation, die Task 3 aus einem im
Dekoder liegenden Grund ablehnt, wird also durch Geometrieanpassung
folgerichtig nicht gelöst. Bei allen 5 gefundenen Rastern steht
`flat_optimum=True`; direkt nachgewiesene Ursache: `DisplayLayout.cell_boxes`/
`.sign_box` — die vom Leser tatsächlich abgetastete Geometrie — verwenden
`thickness_ratio`/`inset_ratio` gar nicht, beide Felder wirken nur auf den
synthetischen Zeichner. Jede Änderung dieser zwei von vier gesuchten
Parametern ist für die Bewertung deshalb ein exaktes Unentschieden.

**Konsequenz:** Ersetzt eine Handjustage durch eine nachvollziehbare,
deterministische Suche, die ihre eigene Unsicherheit meldet statt sie zu
verschweigen. Der `flat_optimum`-Befund ist eine neue, offene Erkenntnis für
künftige Sitzungen (docs/VALIDATION.md): `thickness_ratio`/`inset_ratio`
entweder in die Lesegeometrie einbeziehen oder als reine Zeichenparameter aus
dem Autofit-Suchraum entfernen. `8a18ee05…` bleibt ein Fall für die
Decoder-Seite, nicht für die Geometrie.

## 0.1.0.dev0 — 2026-09-11 (Benchmark mit dreigeteilter Metrik und erzwungenem Geräte-Gruppensplit)

### Eine einzelne Trefferquote verdeckt die gefährliche Zahl: die falsche Annahme

**Problem:** Task 3 des Plans
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](docs/PLAN_2026-09-11-ocr-selbstkalibrierung.md).
Es gab kein wiederholbares Werkzeug, das Leseergebnisse gegen einen Sollwert
prüft — nur Handmessungen im Sitzungs-Scratchpad (siehe
[docs/VALIDATION.md](docs/VALIDATION.md)). Eine einzelne Trefferquote
unterscheidet zudem nicht zwischen einer Ablehnung (kostet einen Messwert)
und einer falschen Annahme (verfälscht eine Kalibrierung, AGENTS.md) — genau
die Unterscheidung, auf die es in diesem Projekt ankommt.

**Änderung:** `src/dispread/benchmark.py` liest Clips (`ReplaySource`, Task 1)
und reale `var/workbench/annotations/<id>/`-Verzeichnisse und führt
korrekt/falsch/abgelehnt getrennt, schlüsselt Fehler nach Klasse auf
(Vorzeichen `sign`, Stellenzahl `count`, Ziffer `digit`) und Ablehnungen nach
Grund (aus den Reader-Diagnosen, nicht geraten). `read_frame()` geht exakt den
Weg des echten Lesepfads (`rectify` auf `CROP_SIZE`, dann `crop_box` mit der
bestätigten `ocr_box`) — ein abweichender Weg würde etwas anderes messen als
der Betrieb. `assert_disjoint_devices()` erzwingt als Test, dass
Entwicklungs- und Testsatz nie dieselbe Geräteinstanz teilen (Splitgrenze ist
laut ROADMAP die Geräteinstanz, nie der Frame). `evaluate_annotation()`
überspringt Annotationen ohne getippten Sollwert oder ohne `profile.layout`
(Altschema) statt sie stillschweigend als falsch oder korrekt zu zählen;
`evaluate_set()` fasst mehrere Verzeichnisse zu einem Gesamtbericht zusammen.
Dazu die dünne CLI `scripts/ocr-benchmark.py` (`--annotations DIR` oder
`--dev MUSTER --test MUSTER`), die nichts in die Doku schreibt.
Ausgangsmessung auf den sechs auswertbaren der neun realen Annotationen
(eine Geräteinstanz, siehe VALIDATION.md): 5 korrekt, 0 falsch angenommen,
1 abgelehnt (`8a18ee05…`, wegen `unreadable_cells`).

**Konsequenz:** Die gemessene Rate falscher Annahmen (0) ist die
konservative Obergrenze dessen, was nach der Freigabe (`validate.py`, die
nur zusätzlich ablehnen, nie zusätzlich annehmen kann) beim Bediener ankommen
könnte — Docstring in `benchmark.py`. Der Datensatz ist ausdrücklich ein
**Entwicklungssatz, kein Testsatz**: alle sechs auswertbaren Annotationen
stammen von einer einzigen Geräteinstanz. Jede künftige Decoder-Änderung
(z. B. die in Phase B/C des Plans geplante Selbstkalibrierung) lässt sich ab
jetzt gegen dieselben drei Zahlen prüfen, statt gegen eine einzelne
Trefferquote, die eine falsche Annahme hinter einer hohen Ablehnungsrate
verstecken könnte.

## 0.1.0.dev0 — 2026-09-11 (Clipaufnahme: Deadlock in `_clip_stop()` behoben, verworfene Frames bei Revisionswechsel gezählt)

### `_clip_stop()` konnte die gesamte Workbench einfrieren, nicht nur die Clipaufnahme

**Problem:** Ein Reviewfund zur Clipaufnahme (Task 2, Commit `79ba47e`): stirbt
der Schreib-Thread an einem unbehandelten `cv2.error` aus `cv2.imwrite`, ruft
er `self.log()` auf, die `self.lock` braucht. `_clip_stop()` reiht den
Beenden-Sentinel bislang per blockierendem `queue.put(None)` ein — und läuft
selbst immer unter `self.lock` (aus `clip.stop`, dem Deadline-Zweig in
`publish()` und aus `close()`). Ist die begrenzte Queue voll, blockiert
`_clip_stop()` unter dem Lock auf Platz, den nur der Schreiber per `get()`
schaffen könnte — der aber erst durch `self.log()` muss, was denselben Lock
braucht: klassischer Deadlock, der den kompletten Controller wedgt, nicht nur
die Aufnahme. Zusätzlich zählten `publish()`s zwei Revisionswechsel-Abbrüche
(`if revision != self.revision: return` — einer um die gedrosselte
OCR-Auswertung, einer am Ende der Funktion) übersprungene Frames nicht in
`clip["dropped"]` — ein Verstoß gegen die eigene Zusicherung dieses Tasks
(„gezählt, nicht stillschweigend verworfen"). Zwei
weitere Important-Funde: `close()`/`drain_clip_writer()` sammelten nur den
zuletzt gestarteten Schreiber ein, nicht jeden noch laufenden (ein
Stop/Start-Paar hätte einen vorherigen Thread verwaist); `CLIP_QUEUE_DEPTH`/
`CLIP_MAX_SECONDS` waren nicht als `Vorabdefault` gekennzeichnet, und die
20-30-ms-PNG-Zahl stand als gemessene Tatsache im Code und im Changelog, war
aber nie gemessen.

**Änderung:** `_clip_writer` fängt jetzt jede Ausnahme um `cv2.imwrite`
(nicht nur den `False`-Rückgabewert) — der Thread stirbt nie mehr und kommt
immer zu seinem nächsten `get()` zurück. `_clip_stop()` reiht den Sentinel
über `put_nowait()` ein; ist die Queue in dem seltenen Fall wirklich voll,
liefert ein kurzlebiger Hilfsthread ihn außerhalb des Locks blockierend nach
— der aufrufende Thread wartet darauf nie. `self.clip_thread` (Singular)
wurde durch `self.clip_threads` (Liste noch nicht eingesammelter Schreiber)
ersetzt; `close()` und `drain_clip_writer()` joinen jetzt alle, `_clip_start()`
wirft beendete Threads vorher aus der Liste, damit sie nicht unbegrenzt
wächst. Beide Revisionswechsel-Abbrüche in `publish()` zählen bei laufender
Aufnahme jetzt in `clip["dropped"]`. `CLIP_QUEUE_DEPTH`/`CLIP_MAX_SECONDS` sind als
`Vorabdefault` markiert, die PNG-Schreibdauer ist im Code und im Changelog
jetzt als Annahme (nicht gemessen) benannt. Fünf neue Tests: zwei belegen,
dass ein Revisionswechsel waehrend einer Aufnahme jetzt gezaehlt statt
verloren wird (frueher und spaeter Abbruchpfad in `publish()`); drei decken
den Queue-voll→`dropped_frames`-Pfad und beide Ruling-Szenarien ab (close()
ueber einen noch schreibenden Thread hinweg ohne Verlust; rasches Stop/Start
verwechselt Schreiber/Queue nicht) - von diesen drei ist nur der
Stop/Start-Test ein echter Regressionstest gegen den Vorzustand, die anderen
beiden bestaetigen lediglich, dass bereits vorhandenes Verhalten nun auch
getestet ist.

**Konsequenz:** Eine volle Clip-Queue oder ein defektes Bild kann die
Workbench nicht mehr einfrieren; ein Revisionswechsel mitten in einer
Aufnahme erzeugt eine sichtbare Lücke im Manifest statt einer stillen. Alle
124 Tests grün (121 vor diesem Fix + 3 neue), `ruff check` und
`node --check` sauber.

## 0.1.0.dev0 — 2026-09-11 (Clipaufnahme in der Workbench: ein getipptes Label je Clip)

### Labeling kostete pro Bild, nicht pro Kalibrierpunkt

**Problem:** Ein Testdatensatz für die OCR-Selbstkalibrierung braucht viele
gelabelte Bilder pro Messwert, aber annotation.json verlangt bisher pro
eingefrorenem Einzelbild eine eigene Bedienereingabe — bei mehreren Sekunden
Aufnahme je Kalibrierpunkt ein unverhältnismäßiger Tippaufwand.

**Änderung:** Neue Controller-Ops `clip.start`/`clip.stop` nehmen ein paar
Sekunden Livebild in das Clipformat aus Task 1 (`CLIP_SCHEMA_VERSION`) auf;
der Bediener tippt Gerätekennung und Sollwert genau einmal, jeder Frame
trägt danach dasselbe Label. PNGs werden in einem eigenen Thread über eine
begrenzte Queue geschrieben, damit die 15-fps-Vorschau nicht auf
PNG-Kodierung wartet (Annahme, nicht gemessen: grob 20–30 ms/Bild bei
960×720); läuft die Queue voll,
wird gezählt (`dropped_frames`) statt still verworfen. `close()` wartet
jetzt auf das Ende des Schreib-Threads, bevor der Prozess beendet — sonst
könnte er enden, während im gerade geschriebenen `clip.json` gelistete
Bilder noch nicht auf der Platte liegen. Die Workbench bekommt dafür ein
`clip-panel` (Gerätekennung, Sollwert, Dauer, Start/Stop); die Aufnahme
ändert nichts an `confirmed` und braucht keinen neuen
Bestätigungsmechanismus.

**Konsequenz:** Ein Kalibrierpunkt kostet einen Tippvorgang statt N
Annotationen. Die aufgezeichneten Clips sind über `replay://` (Task 1)
unverändert lesbar — 3 neue Tests, 121 insgesamt grün, `ruff check` sauber.

## 0.1.0.dev0 — 2026-09-11 (replay:// implementiert für gelabelte Clip-Archivierung)

### Erkennungsänderungen sind mangels Datensatz nicht belegbar

**Problem:** Jede Verbesserung des OCR-Readers braucht Validierung gegen
reale, gelabelte Bilder. Bislang gab es keinen Mechanismus, um
aufgezeichnete Clips mit einem bestätigten Sollwert zurückzuspielen —
nur synthetische oder Live-Quellen. Ein Testdatensatz musste händisch
annotation.json lesen und von außen testen; das Labeling kostet pro Bild.

**Änderung:** Neuer Frame-Source `replay://` liest Clip-Verzeichnisse mit
dem Manifestformat aus Task 2. Ein Clip trägt genau **ein** Sollwert-Label
für alle seine Frames (kein Pro-Frame-Label), der in `raw_metadata["ground_truth"]`
verfügbar ist. Aufgezeichnete Sensorzeitstempel werden als `REPLAY_RECORDED`
gefährt (tragen die Zeitaussage der Aufnahme), synthetische bleiben
`SYNTHETIC` ohne Zeitaussage — ein Replay darf aus synthetischen
Aufnahmen keine Zeitinformation erfinden.

**Konsequenz:** Labelkosten sinken von pro Bild (bei annotation.json)
auf pro Clip — dieselbe Laborstunde kann damit mehrere Order-of-Magnitude
mehr Frames abdecken. Task-2-Schreiber können jetzt Clips erzeugen und
Task-3-Tester können sie gegen beliebige Reader-Versionen auswerten,
ohne dass Pro-Frame-Annotation nötig wäre. 5 Tests grün, `ruff check`
sauber.

## 0.1.0.dev0 — 2026-09-11 (repo-maintenance.sh: toter Lauf committete trotzdem; jetzt auch andere lokale Branches)

### Ein während des Laufs abgestürzter/gekillter Claude-Prozess konnte trotzdem committet werden, und nur `master` wurde gepflegt

**Problem:** Bedienerauftrag: "Das maintenance script soll claude status
checken so das wenn ein run während des runs stirbt nicht einfach trotzdem
commitet wird. Das maintenance skript soll nicht nur main sondern auch
andere branches checken und managen." Zwei getrennte Lücken im ursprünglichen
Wrapper (Commit `82f63ff`): (1) `$CLAUDE_STATUS` wurde erfasst, aber nie
geprüft — schlimmer noch, der Fallback-Zweig für eine nicht parsebare
Commit-Message committete trotzdem mit einer generischen Nachricht statt
abzubrechen. Genau das ist die Signatur eines mittendrin getöteten Laufs
(ein gekillter, dann reaped `claude -p` kann trotzdem Exit 0 liefern). (2)
Der Wrapper kannte nur den bei Cron-Start ausgecheckten Branch (`master`);
`docs/oq22-rp2040-wedge` und `test/clahe-ocr-accuracy` wurden nie geprüft.

**Änderung:** Schleife über alle lokalen Branches (`git for-each-ref
refs/heads/`); je Branch derselbe Ablauf wie zuvor, plus: (a) Abbruch **ohne
Commit** wenn `$CLAUDE_STATUS` ungleich 0 UND Änderungen vorliegen, wenn
Dateien ausserhalb `docs/`/`CHANGELOG.md` angefasst wurden, oder wenn keine
parsebare Commit-Message-Markierung im Output steht — alle drei Fälle gelten
jetzt als Signatur eines gestorbenen Laufs, nicht mehr nur als Spezialfall.
(b) Bei Abbruch: gezielter `git stash push -u -- docs CHANGELOG.md` (nur der
betroffene Pfad, damit unrelated Werkstattunordnung im restlichen Baum nicht
mitgerissen wird), plus ein Eintrag `branch: <name>` in der Markerdatei
`~/.local/state/picam-ai-maintenance/needs-review` — **nur dieser eine
Branch** wird ab sofort übersprungen, bis ein Mensch die Zeile entfernt; alle
anderen Branches laufen im selben und in künftigen Läufen unbeeinflusst
weiter (ein reiner Stash wäre für `git status` unsichtbar und hätte sich auf
demselben Branch Nacht für Nacht unbemerkt wiederholt). (c) Die
Schmutzig-Prüfung (Start des Laufs, vor jedem Branch-Wechsel) ist jetzt auf
`docs/`+`CHANGELOG.md` beschränkt statt auf den ganzen Baum — unrelated nicht
committete Tooling-Dateien blockierten die Routine sonst dauerhaft. (d)
Branches mit identischem `docs/`+`CHANGELOG.md`-Stand (gleicher Baum-Hash)
werden übersprungen, damit dieselbe Korrektur nicht auf drei Branches
gleichzeitig landet und Merge-Konflikte erzeugt. Ein `restore_branch`-Trap
kehrt am Ende immer zum ursprünglich ausgecheckten Branch zurück (nie
erzwungen; verweigert die Rückkehr, falls dabei etwas schiefgelaufen sein
sollte, statt zu forcieren). Verifiziert mit einem Fake-`claude`-Binary gegen
Scratch-Repos: normaler Zweig-Durchlauf inkl. Dedup, gekillter Lauf ohne
Commit-Marker, Exit-Status ungleich 0, Fremdpfad-Änderung (jeweils Stash
statt Commit, gezielter Marker-Eintrag, betroffener Branch bleibt beim
Folgelauf übersprungen) sowie ein Drei-Branch-Lauf, in dem genau ein Branch
scheitert, während die beiden anderen trotzdem committet werden.

**Konsequenz:** Ein toter Lauf hinterlässt nie mehr einen stillen,
schlecht beschrifteten Commit, und ein einzelner scheiternder Branch
blockiert nicht mehr die Pflege der übrigen. Alle drei lokalen Branches
(`master`, `docs/oq22-rp2040-wedge`, `test/clahe-ocr-accuracy`) werden ab
sofort gepflegt statt nur `master`. `docs/status.md` behauptete bisher, die
beiden Skript-Dateien seien noch uncommittet — das war seit `82f63ff` falsch,
korrigiert im gleichen Zug.

## 0.1.0.dev0 — 2026-09-10 spät nachts (TUI-style zweistufiger Bestätigungsablauf; Race-Condition-Fix)

### Klick auf die ROI-Box während einer laufenden Vermutungsanfrage verwarf das Ergebnis

**Problem:** Bedienerrückmeldung: "wenn ich die roi box anklicke verliert er
die vorgeschlagene box und schlägt wieder die letzte confirmte box vor."
Ursache, durch Nachverfolgung bestätigt: `suggest()` (`workbench.js`, `R`-Zug)
rief nacheinander `roi.suggest` und `ocr.suggest` auf; beide rechneten ihre
OpenCV-Arbeit (`fit_quad_in_region`/`fit_ocr_box`) vollständig **innerhalb**
von `Controller.command()`s einzigem `with self.lock:`-Block — anders als
`publish()`, das seine OpenCV-Arbeit bewusst ausserhalb des Locks haelt.
Das machte den Umlauf langsam genug, dass ein Klick/Zug auf die ROI-Box
während der Wartezeit `onpointerdown` den **noch alten** Zustand in `drag`
einfror; ein nachfolgendes `onpointermove` überschrieb damit die gerade
eingetroffene Vermutung mit der veralteten, zuletzt bestätigten Geometrie.
Nirgends wurde die Zeigereingabe waehrend einer laufenden Anfrage gesperrt.

**Änderung:** Bei der Fehlersuche äusserte der Bediener den weitergehenden
Wunsch, die tastaturgesteuerte Bedienung (`R` Hinweisrechteck, `G`
Rahmenwechsel, `Shift+Pfeile` Eckenverschiebung, `Strg+Enter` Bestätigung)
durch einen zweistufigen, knopfbasierten Ablauf zu ersetzen:

- **Stufe A (ROI):** die laufende Live-Kandidatensuche zeigt mehrere duenne,
  einzeln anklickbare Vorschlagsboxen; ein Klick waehlt die passende aus.
  Zwei TUI-Knoepfe (✓/✎) an der aktiven Box: ✎ schaltet in einen Bearbeiten-
  Modus (Koerper verschieben, Ecken ziehen — beides bleibt erhalten, wird
  waehrenddessen zu ✕ zum Abbrechen), ✓ uebernimmt die Position.
- Nach ✓ ruft der Client automatisch `ocr.suggest` mit dieser Position auf
  und wechselt zu **Stufe B (OCR)**: derselbe ✓/✎-Ablauf an der
  OCR-Box. Ein Klick auf die jetzt inaktive ROI-Box fuehrt zurueck zu
  Stufe A, ohne die Kandidatensuche neu zu starten.
- ✓ an der OCR-Box sendet den bestehenden `roi`-Op (Quad+OCR-Box zusammen,
  im `annotate`-Modus zusaetzlich das unveraendert Ground-Truth-Textfeld) —
  weiterhin die einzige Stelle, an der `confirmed` wahr wird.
- **Kernbehebung:** waehrend eine Vermutungs-/Bestaetigungsanfrage laeuft
  (`editing.pending`), ignoriert `canvas.onpointerdown` jede Zeigereingabe
  vollstaendig und alle vier Knoepfe sind deaktiviert — genau das verhindert
  die gemeldete Race Condition strukturell, nicht nur zufaellig.
- `ocr.suggest` rechnet seine OpenCV-Arbeit jetzt ausserhalb des Controller-
  Locks (`Controller._suggest_ocr_box`, vor dem `with self.lock:` in
  `command()` abgefangen) — mirror von `publish()`s Muster.
- Der jetzt ungenutzte `roi.suggest`-Op ist entfernt (Kandidatenauswahl liest
  die ohnehin laufend berechnete Kandidatenliste, keine erneute
  hinweisgebundene Suche mehr). `fit_quad_in_region` selbst bleibt - `publish()`s
  Vergleichssuche (heute frueher ergaenzt) nutzt sie weiter unveraendert.
- `freeze()` liefert jetzt die volle Kandidatenliste statt nur der einen
  besten Vermutung (mit einmaligem Nachsuchlauf, falls nach einer
  Bestätigung in derselben Sitzung keine Kandidaten mehr zwischengespeichert
  sind); die vormittags ergänzte automatische OCR-Vorschlag-Vermutung direkt
  in `freeze()` entfällt wieder — die Vermutung passiert jetzt explizit beim
  Stufenübergang.

**Konsequenz:** Der gemeldete Bug ist strukturell behoben (keine
Zeigereingabe waehrend einer offenen Anfrage moeglich), nicht nur seltener
gemacht. Neue Tests: `test_ocr_suggest_does_not_hold_the_controller_lock_during_detection`
(Kernbehebung, Lock-Freigabe), `test_freeze_returns_all_current_candidates`,
`test_freeze_populates_candidates_even_when_none_were_cached`,
`test_command_rejects_the_removed_roi_suggest_op`. `docs/anleitung/10-kamera-livevorschau.md`
aktualisiert. Manuelle Bedienprüfung im echten Browser steht aus (OQ-21).

## 0.1.0.dev0 — 2026-09-10 nachts (Sitzungsstart erzwingt erneute Bestätigung; OCR-Box-Vorschlag beim Öffnen des Editors)

### Bedienerwunsch: jede Sitzung soll mit laufender Erkennung beginnen, nicht mit stillschweigend übernommener alter Bestätigung

**Problem:** Bedienerrückmeldung, nach Klärung per Rückfrage: Der Bediener
möchte beim Start der Web-UI aktiv laufende ROI-Erkennung sehen, daraus die
richtige Anzeige auswählen bzw. den Rahmen nachziehen, dann bestätigen -
woraufhin der Innenbereich automatisch auf Ziffern durchsucht und eine
OCR-Box vorgeschlagen wird, die er wiederum bestätigt oder korrigiert. Die
bisherige Lösung (gedrosselte, auf die bestätigte ROI eingegrenzte
Vergleichssuche) erfüllte das nicht: eine bereits bestätigte Geometrie blieb
sofort `confirmed` und damit run-fähig, ohne dass der Bediener sie in dieser
Sitzung überhaupt gesehen oder bestätigt hätte.

**Änderung:** `Controller.__init__` setzt nach dem Laden eines bereits
bestätigten Profils `confirmed` auf `false` - nur in der Laufzeitkopie, die
gespeicherte Profildatei bleibt unverändert, und `roi`/`roi_quad`/`ocr_box`
bleiben als Startpunkt für eine schnelle erneute Bestätigung erhalten. Das
reaktiviert automatisch die volle, ungedrosselte Vollbild-Kandidatensuche auf
dem Livebild (`publish()`: unbestätigt sucht wie schon immer jedes Bild) und
sperrt den `run`-Modus, bis der Bediener aktiv erneut bestätigt (Konzept.md
§4: „Bestätigung ist der Akt eines Menschen" - jetzt auch nach einem
Neustart, nicht nur einmalig). Zusätzlich ruft `Controller.command("freeze")`
jetzt automatisch `fit_ocr_box` auf dem aktuellen ROI-Ausschnitt auf und
bietet das Ergebnis direkt als `ocr_box` an (gestrichelt markiert,
`ocr_suggested` im Editier-Zustand) - der zweite Schritt des Kalibrierflusses
läuft damit ohne einen zusätzlichen manuellen `R`-Zug für die OCR-Box. Kein
Kandidat ist weiterhin inert: Rückfall auf den bisher gespeicherten oder
(Stufe 1) geschrumpften Default-Wert. Neue Tests
`test_startup_requires_re_confirmation_of_a_previously_confirmed_profile`,
`test_startup_does_not_touch_an_already_unconfirmed_profile`,
`test_freeze_suggests_a_fresh_ocr_box_for_the_current_quad`,
`test_freeze_falls_back_when_no_ocr_box_can_be_suggested`.

**Konsequenz:** End-to-End an einer echten Annotation nachgestellt (Profil
mit bestätigter Geometrie gespeichert, Controller neu instanziiert): nach dem
Neustart ist `confirmed=false`, die Kandidatensuche läuft wieder
(Vollbildsuche findet die Anzeige), `run`-Modus ist gesperrt, `freeze()`
startet am alten `roi` und bietet sofort eine frische OCR-Box-Vermutung an.
Bekannte, unveränderte Grenze: Die automatische OCR-Box-Vermutung trifft am
selben Netzteil-Beispiel wie in OQ-25 dokumentiert weiterhin gelegentlich die
falsche von zwei übereinanderliegenden Anzeigen - das ist ein reiner
Vorschlag, gestrichelt dargestellt, keine automatische Übernahme; siehe
aktualisierter [OQ-25](docs/open-questions.md). Beantwortet **nicht** die
weiterhin offene Labor-/QM-Frage [OQ-05](docs/open-questions.md), ob eine
einmalige Bestätigung je Geräteinstanz betrieblich vorgesehen ist - das ist
eine Softwareentscheidung für den Editor-Workflow.

## 0.1.0.dev0 — 2026-09-10 abends (unbeaufsichtigte Doku-Pflege-Routine)

### Doku driftet zwischen Arbeitssitzungen, niemand räumt zwischendurch auf

**Problem:** `docs/` wächst nur an (Konzept.md-Autorität, Doku-Pflicht aus
AGENTS.md), aber es gibt keinen Mechanismus, der veraltete oder redundante
Abschnitte zwischen Sitzungen kürzt oder Querverweise repariert. Der Pi ist
nachts aus, der Bediener beginnt morgens direkt mit der Arbeit.

**Änderung:** Neues Skript `scripts/repo-maintenance.sh` (per `@reboot`-
Cron kurz nach dem morgendlichen Boot) ruft `claude -p` unbeaufsichtigt mit
festem Prompt (`scripts/repo-maintenance-prompt.md`) auf. Harte Grenzen im
Prompt: nur `docs/` und `CHANGELOG.md`, nie `Konzept.md`/`AGENTS.md`/
`CLAUDE.md`/`src/`/`tests/`/`examples/`, OQ-Einträge werden nie gelöscht
(nur auf „geklärt" gesetzt). Die Claude-Session läuft mit
`--permission-mode acceptEdits` und `--disallowedTools
"Bash,Agent,WebFetch,WebSearch"` (kein Shell-Zugriff, keine Subagenten,
keine externen Abrufe — nur Datei-Tools und installierte Skills/Plugins).
Der Wrapper committet automatisch, aber nur wenn (a) der Arbeitsbaum vor
dem Lauf sauber war und (b) ausschließlich `docs/`/`CHANGELOG.md` geändert
wurden — sonst bleibt alles unangetastet bzw. uncommittet für manuelle
Prüfung liegen. Läuft im Log unter `~/.local/state/picam-ai-maintenance/`.

**Konsequenz:** Ab dem nächsten Boot räumt sich die Doku morgens selbst
auf, bevor die eigentliche Arbeitssitzung beginnt. Läuft nur an, wenn der
Baum bereits committet war — mischt sich also nie mit laufender manueller
Arbeit. Erster scharfer Lauf noch nicht beobachtet (Cron erst nach diesem
Commit eingerichtet).

## 0.1.0.dev0 — 2026-09-10 spätabends (Vergleichssuche schlug andere Bildschirme vor)

### Die wiederhergestellte Vergleichssuche suchte weiter im ganzen Bild statt nur um die bestätigte ROI

**Problem:** Bedienerrückmeldung direkt auf die spätnachmittägliche Änderung:
Nach einem Neustart mit bestätigter ROI/OCR blieb zwar die alte Geometrie
sichtbar, aber die wieder aktivierte Vergleichssuche schlug weiterhin andere
Bildschirme/ROIs im Bild vor. Ursache: Die spätnachmittägliche Änderung ließ
`find_display_candidates` — die Vollbildsuche — auch nach der Bestätigung
weiterlaufen, nur gedrosselt statt bei jedem Bild. Am realen Testaufbau
(Netzteil mit zwei Anzeigen `V`/`A`, zwei Monitore im Hintergrund, weitere
Messgeräte) fand die Suche regelmäßig ein anderes rechteckiges Objekt im
Bild statt der tatsächlich bestätigten Anzeige.

**Änderung:** Die Vergleichssuche nutzt jetzt `fit_quad_in_region` (aus
Stufe 2 der Vortagsarbeit) mit der bestätigten `config["roi"]` als
Suchfenster-Hinweis statt der Vollbildsuche — der Suchraum bleibt auf die
~25 % aufgeweitete Umgebung der bestätigten ROI beschränkt. Zusätzlich neuer
Mindestüberdeckungsfilter `MIN_HINT_OVERLAP = 0.2` in `fit_quad_in_region`
selbst: ein Kandidat muss den *ungepolsterten* Hinweisbereich zu mindestens
20 % überdecken, sonst wird er verworfen — sonst hätte bei einer großzügig
bestätigten ROI (das aufgeweitete Suchfenster kann dann beträchtlichen
Spielraum haben) weiterhin ein zufällig rechteckigeres, aber unbeteiligtes
Objekt am Rand des Fensters gewinnen können. Neuer, an einer nachgebauten
Ablenker-Szene verifizierter Test
`test_fit_quad_in_region_ignores_unrelated_objects_outside_the_hint` sowie
`test_confirmed_roi_never_triggers_the_whole_frame_candidate_search` und
`test_confirmed_roi_verification_search_is_scoped_to_the_confirmed_region`
(ersetzen den bisherigen, auf `find_display_candidates` gestützten
Drosselungstest). Ergebnis in `Controller.publish()` bleibt ein einzelnes
gelbes Vergleichsquad statt mehrerer Kandidatenboxen; `self.candidates`
bleibt (wie ursprünglich dokumentiert) ausschließlich der unbestätigten
Vollbildsuche vorbehalten, das bestätigte Vergleichsergebnis liegt getrennt
in `self.verify_quad`.

**Konsequenz:** Am realen Beispiel (`var/workbench/annotations/*`) trifft
die eingegrenzte Vergleichssuche mit der bestätigten ROI als Hinweis die
tatsächliche Anzeige (IoU ≈ 0,91, wie schon für `roi.suggest` in
[VALIDATION.md](docs/VALIDATION.md) gemessen) und ignoriert die im selben
Bild sichtbaren Monitore vollständig. Nebenbei günstiger als die vorherige
Vollbildsuche: rund 12,5 ms/Bild im (künstlich erzwungenen) Suchfall statt
16,6 ms, Leerlauf und `run`-Modus unverändert bei rund 8,0–8,1 ms/Bild —
aktualisierte Zahlen in [docs/VALIDATION.md](docs/VALIDATION.md). OQ-24
erneut präzisiert, nicht neu eröffnet.

## 0.1.0.dev0 — 2026-09-10 spätnachmittags (Kandidatensuche nach Neustart mit bestätigter ROI)

### Bestätigte Geometrie hatte nach einem Neustart nie mehr einen visuellen Vergleich

**Problem:** Bedienerrückmeldung: Beim Start der Web-UI ist die zuletzt
eingestellte ROI/OCR-Geometrie weiterhin aktiv (korrekt, `Controller.__init__`
lädt das Default-Profil unverändert), aber es wird nicht mehr automatisch
gesucht. Ursache in der mit OQ-24 (2026-09-09) eingeführten Optimierung:
`find_display_candidates` lief `boxes = () if config["confirmed"] else
find_display_candidates(...)` — sobald einmal bestätigt, für immer aus, auch
über Prozessneustarts hinweg. Der Bediener hatte damit keinerlei visuellen
Hinweis mehr (gelbe Kandidatenbox neben dem grünen bestätigten Rahmen), ob die
geladene Geometrie noch zur aktuell vor der Kamera stehenden Szene passt.

**Änderung:** Neue Konstante `CANDIDATE_INTERVAL_S = 1.0` (`controller.py`).
`publish()` sucht jetzt: vor einer Bestätigung weiterhin bei jedem Bild
(unverändert), nach einer Bestätigung gedrosselt auf höchstens einmal je
Sekunde, und **nie im `run`-Modus** — der Produktionsmodus behält die mit
OQ-24 behobenen Vollbildsuche-pro-Bild-Kosten (30,837 ms/Bild) vollständig
abgeschaltet. Zwischen zwei Suchen bleibt die zuletzt gefundene Kandidatenliste
sichtbar (`cached_candidates`), damit die gelben Boxen nicht mit der
Drosselfrequenz flackern. `Controller._load()` loggt beim Laden einer bereits
bestätigten Geometrie zusätzlich einen Warnhinweis, dass sie noch nicht gegen
die aktuelle Szene verglichen wurde. Die Bestätigung selbst bleibt
unangetastet — kein automatisches Un-Confirm, kein automatischer Ersatz der
Geometrie (Konzept.md §4: „Bestätigung ist der Akt eines Menschen"). Neuer
Test `test_confirmed_roi_throttles_candidate_search_outside_run_mode`,
`test_confirmed_roi_in_run_mode_skips_full_frame_candidate_search` (ersetzt
den bisherigen, zu unbedingten Test) und
`test_loading_a_confirmed_profile_warns_about_unverified_geometry`.

**Konsequenz:** Nach einem Neustart mit bereits bestätigter Geometrie
erscheint jetzt wieder eine gelbe Kandidatenbox neben dem grünen bestätigten
Rahmen, mit der der Bediener vergleichen kann, ob die Geometrie noch passt —
ohne dass irgendetwas automatisch übernommen wird. Kostenmessung (gleiches
Realbild wie die OQ-24-Messung): rund 8,3 ms/Bild im gedrosselten Leerlauf,
16,6 ms/Bild im (künstlich erzwungenen) Suchfall, `run`-Modus unverändert bei
rund 8,3 ms/Bild ohne jede Suche — bei 1 Hz Drosselung im Mittel weit unter
1 ms/Bild zusätzlich, siehe [docs/VALIDATION.md](docs/VALIDATION.md). OQ-24
entsprechend präzisiert (`docs/open-questions.md`), nicht neu eröffnet.

## 0.1.0.dev0 — 2026-09-10 (Workbench-Editor: Klickpriorität, automatische Box-Vorschläge, Ground-Truth-Erfassung)

Setzt [docs/PLAN_2026-09-10-workbench-editor.md](docs/PLAN_2026-09-10-workbench-editor.md)
vollständig um (alle drei dort geplanten Stufen).

### Stufe 1 — Verklicken zwischen `roi_quad` und `ocr_box`

**Problem:** Bedienerrückmeldung: Direkt nach einer frischen `roi`-Bestätigung
startet `ocr_box` deckungsgleich mit `roi_quad` (`[0,0,1,1]`). `nearestHandle`
(`workbench.js`) suchte den nächsten Punkt global über beide Boxen zusammen;
an eng benachbarten Ecken traf der Klick oft die äußere ROI statt der
gewollten inneren OCR-Box.

**Änderung:** `nearestHandle` prüft jetzt zuerst alle `ocr`-Ecken innerhalb des
Trefferradius (18 px), erst wenn keine trifft die `roi`-Ecken — die gelbe Box
liegt auch optisch über der grünen (`draw()` zeichnet `roi` zuerst).
`Controller.command("freeze")` bietet zusätzlich, wenn `ocr_box` noch der
unberührte Default ist, im **zurückgegebenen Editier-Zustand** einen spürbar
kleineren Startwert `[0.15, 0.15, 0.7, 0.7]` an — reine Editor-Sitzungsgröße,
weder `self.config` noch eine Bestätigung ändern sich dadurch. Neue Tests
`test_freeze_offers_a_smaller_default_ocr_box_without_persisting_it`,
`test_freeze_keeps_a_confirmed_ocr_box_unchanged`.

**Konsequenz:** Die beiden Rahmen sind direkt nach dem Einfrieren sichtbar
getrennt und die Trefferlogik bevorzugt den optisch obenliegenden Rahmen —
das gemeldete Verklicken tritt nicht mehr auf. Kein Schema-, Migrations- oder
Persistenzeffekt.

### Stufe 2 — Automatische `roi_quad`-/`ocr_box`-Vorschläge über einen groben Bedienerhinweis

**Problem:** Jede Kalibrierung eines neuen Geräts erforderte vollständiges
manuelles Ziehen aller acht Eckpunkte. Eine Kontursuche ohne jeden Hinweis
kann mehrere ähnlich rechteckige Objekte am Prüfstand nicht unterscheiden
(Konzept.md §7: Haupt-/Nebenanzeige-Verwechslung), Vollautomatik wäre also
unzuverlässiger als ein grober Bedienerhinweis.

**Änderung:** Neue Taste `R` im Editor startet einen von der bestehenden
Ecken-/Körper-Ziehlogik getrennten Interaktionsmodus (`hinting`/`hintDrag` in
`workbench.js`): der Bediener zieht ein grobes achsparalleles Rechteck um das
Display. Beim Loslassen ruft der Client `roi.suggest` (neue Funktion
`fit_quad_in_region` in `workbench/vision.py`: Kantenpipeline wie
`find_display_candidates`, aber `cv2.minAreaRect`/`cv2.boxPoints` statt
`cv2.boundingRect`, damit `roi_quad` ein echtes, auch rotiertes Viereck sein
kann; Eckenreihenfolge über die bestehende `dispread.rectify._order_quad`;
Flächenanteil/Rechteckigkeit wie `DetectionConfig`, Seitenverhältnis bei
vorhandenem Layout zusätzlich aus `DisplayLayout.n_cells` abgeleitet), danach
sofort `ocr.suggest` mit dem übernommenen Quad (neue Funktion `fit_ocr_box`:
Otsu-Schwelle in beiden Polaritäten, Blobs nach Höhe filtern, nach vertikaler
Mitte zu Zeilen gruppieren — lückenbasiert statt über einen laufenden
Mittelwert, sonst zieht ein einzelner Ausreißer die Gruppierung über eine
Kette benachbarter Abstände in die falsche Zeile —, größte Zeile nach
Gesamtfläche behalten). Beide neuen Controller-Ops (`roi.suggest`,
`ocr.suggest`) sind reine, synchrone Vorschlagsfunktionen ohne jede
Persistenz. Unbestätigte Vorschläge werden im Editor gestrichelt und
transparent gezeichnet (`editing.roiSuggested`/`editing.ocrSuggested`) und
fallen weg, sobald die jeweilige Box berührt wird. Findet der Server nichts,
bleibt die Editorgeometrie unverändert und eine Logzeile erklärt das — ein
Fehlschlag ist inert, nie eine schlechte Automatik-Übernahme.

**Konsequenz:** `roi_quad`-Vorschläge treffen die beiden realen
Annotationsbilder aus `var/workbench/annotations/` mit IoU ≈ 0,91 gegen die
tatsächlich bestätigte Geometrie (gemessen, siehe
[docs/VALIDATION.md](docs/VALIDATION.md)). `ocr_box`-Vorschläge sind an
denselben zwei Bildern unzuverlässig (IoU 0,0), weil der dort verwendete
Ausschnitt neben der Hauptanzeige eine baugleiche Nebenanzeige enthält — genau
die aus Konzept.md §7 bekannte, ohne weiteren Hinweis strukturell nicht
auflösbare Verwechslung. Neuer Eintrag [OQ-25](docs/open-questions.md). Die
hier gebaute Kontursuche ist **Workbench-Editorhilfe, nicht** die
`DisplayLocator`/`contour_heuristic`-Implementierung aus der ROADMAP-P0-Zeile
„`contour_heuristic`- und `imx500_detector`-Lokalisierung, `RegionTracker`" —
diese Zeile bleibt unverändert offen. `manual_roi` bleibt Primärpfad; jeder
Vorschlag muss weiterhin über den unveränderten `roi`-Op bei `Strg+Enter`
bestätigt werden.

### Stufe 3 — Getippter Ground-Truth-Wert im `annotate`-Modus

**Problem:** `annotate`-Aufnahmen enthielten bisher nur Geometrie, keinen
abgelesenen Wert, und wurden nirgends zurückgelesen — für eine spätere
Trefferquotenauswertung fehlte der einfachste Baustein: der tatsächlich
angezeigte Wert je Aufnahme.

**Änderung:** Neues, rein additives Feld `ground_truth_text` in
`annotation.json` (`Controller.command`, `op == "roi"`, `self.mode ==
"annotate"`-Zweig), vom Client mitgeschickt und ungeprüft übernommen — keine
Schema-Version, keine `validate()`-Änderung, da `annotation.json` nicht gegen
`profiles.py::validate` geprüft wird. `workbench.js` zeigt beim Bestätigen im
`annotate`-Modus ein kleines Texteingabefeld (`#ground-truth` in
`index.html`/`workbench.css`, analog zum bestehenden
Profil-Speichern-unter-Dialog), bevor der `roi`-Befehl abgeschickt wird;
`viewport.onkeydown` ignoriert Editor-Hotkeys, solange der Fokus auf einem
Eingabefeld liegt.

**Konsequenz:** `annotate`-Aufnahmen sind jetzt (Bild, `roi_quad`, `ocr_box`,
Layout, Ground Truth)-Tupel — genug für einen späteren Trefferquotentest gegen
`SevenSegmentReader`, ohne jede Trainingsinfrastruktur zu versprechen oder zu
bauen. Kein `device_id`-Feld für geräteweise Testsplits — bewusst nicht Teil
dieser Stufe (Konzept §9, ROADMAP P2).

### Verifikation

`./.venv/bin/pytest -q` (101 bestanden, inkl. 20 neuer Tests für
`fit_quad_in_region`/`fit_ocr_box`/`roi.suggest`/`ocr.suggest`/Ground-Truth,
zwei davon `skipif` gegen die realen `var/workbench/annotations/*`-Beispiele),
`./.venv/bin/ruff check src tests examples` und
`node --check src/dispread/workbench/static/workbench.js` grün. Manuelle
Bedienprüfung im echten Browser (Klickpriorität, `R`-Vorschlagsfluss,
gestrichelte Vorschlagsdarstellung, `annotate`-Eingabefeld) steht noch aus —
siehe OQ-21/OQ-24, nicht aus `file://`- oder synthetischen Tests ableitbar.

## 0.1.0.dev0 — 2026-09-09 (Editorstart an erkannter Box; Mehrbildbestätigung gegen Flackern)

### Editieren-Start ignorierte die gerade sichtbare erkannte Displayposition

**Problem:** Bedienerrückmeldung: Beim Doppelklick zum Editieren ging die
zuvor sichtbare "erkannte" ROI-Position verloren. Ursache: Die
Vollbild-Kandidatensuche (`find_display_candidates`) zeichnet vor der
Bestätigung laufend gelbe Vorschlagsboxen ins Live-Bild, aber der `freeze`-
Befehl kannte diese Kandidaten nicht - er startete ein frisches, nie
bestätigtes Profil immer an einer festen Standardbox `[0.2, 0.3, 0.6, 0.3]`
in der Bildmitte, unabhängig davon, wo das System die Anzeige gerade
erkannt hatte.

**Änderung:** `Controller` merkt sich die letzte Kandidatenliste
(`self.candidates`, gesetzt in `publish()`). `freeze` startet ein frisches
Profil jetzt an der besten aktuellen Kandidatenbox (nach Rechteckigkeit und
Fläche sortiert), sofern noch nie eine ROI bestätigt wurde; ein bereits
vorhandener - auch unbestätigter - `roi`-Wert bleibt wie zuvor unangetastet
und wird nicht überschrieben. Neuer Regressionstest
`test_freeze_starts_from_last_detected_candidate`.

**Konsequenz:** Der erste Editierschritt eines frischen Profils beginnt jetzt
in der Nähe der tatsächlichen Anzeige statt in der Bildmitte. Bereits
bestätigte oder zuvor gesetzte Geometrie ist von der Änderung nicht
betroffen.

### Live-Vorschau flackerte bei multiplexenden Anzeigen zwischen falschen Werten

**Problem:** Bedienerrückmeldung: Bei Anzeigen mit sichtbarem Flackern
(Multiplexbetrieb gegen die niedrige Kamerabildrate, OQ-20) sprang die
OCR-Vorschau zwischen falschen Werten hin und her - ein einzelnes Bild kann
mitten in einem Umschaltvorgang liegen. `ReleaseGate` unterstützt bereits
Mehrbildbestätigung (`confirm_frames`, auch in
`examples/16_end_to_end_headless.py` als CLI-Option genutzt), die
Workbench-Vorschau instanziierte ihr Gate aber immer mit dem Default `1` -
keine Bestätigung, jedes Einzelbild zählte sofort als `valid`.

**Änderung:** Neue Konstante `GATE_CONFIRM_FRAMES = 3` in `controller.py`;
die Vorschau verlangt jetzt drei übereinstimmende Bilder, bevor
`gate_status` auf `valid` wechselt (`transition`/`awaiting_confirmation`
davor, weiterhin sichtbar in der Bedienzeile „freigabepruefung"). Ein
abweichender Wert setzt die Bestätigung zurück statt zu glätten oder zu
mitteln (Konzept.md §7) - echte Sprünge bleiben sichtbar, nur ein
Flacker-Frame allein reicht nicht mehr, um kurzzeitig als bestätigt zu
gelten. Bestehender Test `test_publish_reads_synthetic_display_and_exposes_evidence`
angepasst (ruft `publish` jetzt dreimal auf, `last_ocr_at` zurückgesetzt, um
die 5-Hz-Drosselung im Test zu umgehen).

**Konsequenz:** Die Vorschau reagiert bis zu `GATE_CONFIRM_FRAMES *
OCR_INTERVAL_S` (rund 0,6 s) langsamer auf einen neuen stabilen Wert, zeigt
dafür aber deutlich seltener einen durch Multiplex-Flackern verursachten
Fehlwert als `valid` an. Behebt nicht die zugrunde liegende Multiplex-/
Belichtungsfrage aus OQ-20 - dafür bleibt eine reale Messung an typischen
Geräten nötig -, mindert aber ihre sichtbare Auswirkung in der Vorschau.
Die Vorschau bleibt ohnehin nur Anzeige, keine Messwertfreigabe.

## 0.1.0.dev0 — 2026-09-09 (Strg+Enter gegen unbeabsichtigte Bestätigung; Ziffernabstand nachgeschärft)

### Bloßes `Enter` bestätigte ROI/OCR-Rahmen zu leicht unbeabsichtigt

**Problem:** Bedienerrückmeldung: Während der ROI-/OCR-Rahmen-Bearbeitung
wurde das Profil gelegentlich ohne bewusste Bestätigung als `confirmed`
markiert. Ursache: `viewport.onkeydown` löste die Bestätigung
(`command('roi', ...)`, setzt serverseitig `confirmed=True` unbedingt,
`controller.py`) allein durch ein einzelnes `Enter` aus — ohne Rücksicht
darauf, ob gerade noch eine Ziehbewegung lief (`drag` gesetzt), und ohne
jede Rückfrage. Der Kamerabereich behält während der ganzen Editiersitzung
den Tastaturfokus; ein einzelnes `Enter`, etwa aus Gewohnheit nach einer
Pfeiltasten-Korrektur oder nach einem Seitenblick auf die Einstelltabelle,
reichte deshalb aus, um eine noch unfertige Geometrie endgültig zu
übernehmen.

**Änderung:** Die Bestätigung verlangt jetzt `Strg+Enter` (bzw. auf dem Mac
`Cmd+Enter`) statt eines einzelnen `Enter`, und wird zusätzlich ignoriert,
solange eine Ziehbewegung noch läuft. Log-Hinweis, `aria-label` und
Anleitung (`docs/anleitung/10-kamera-livevorschau.md`) wurden entsprechend
aktualisiert.

**Konsequenz:** Bestätigen bleibt ein Tastaturbefehl, verlangt aber eine
bewusste Zweitasten-Kombination statt der im übrigen Formular ohnehin
mehrfach belegten `Enter`-Taste. Das Konzept-§4-Prinzip der einmaligen,
bewussten Bediener-Bestätigung wird damit tatsächlich durchgesetzt statt nur
dokumentiert.

### `digit_gap_ratio`-Obergrenze war zu eng

**Problem:** Die frisch eingeführte Bedienzeile „ziffernabstand" ließ sich
laut Rückmeldung „nur bis zu einem bestimmten Grad" erhöhen; danach passierte
sichtbar nichts mehr. Das war die absichtliche, aber zu knapp gewählte
Obergrenze `LAYOUT_RATIOS["digit_gap_ratio"] = (0.0, 1.0)` — ein
Zwischenraum bis zur vollen Zellenbreite reicht nicht für jede reale Anzeige
oder jeden großzügig gezogenen OCR-Rahmen. Das native Zahlenfeld klemmt am
`max`-Attribut ohne jede Rückmeldung, sobald man per Spinner/Mausrad statt
per Eingabe+Bestätigung erhöht — das erzeugte den Eindruck eines defekten
Reglers statt einer erreichten, gewollten Grenze.

**Änderung:** Obergrenze auf `3.0` angehoben (weiterhin ein unvalidierter
Vorabdefault wie die übrigen `LAYOUT_RATIOS`-Einträge), Schrittweite in der
Bedienzeile von `0.02` auf `0.05` vergröbert.

**Konsequenz:** Deutlich mehr Kopfraum für reale Zwischenraumverhältnisse.
Der Regler bleibt weiterhin endlich begrenzt und klemmt am `max` weiterhin
ohne Rückmeldung, wenn per Spinner statt per Zahleneingabe bedient wird —
das ist ein allgemeines Verhalten aller Zahlenfelder dieser Oberfläche
(auch `ExposureTime`, `AnalogueGain`, `Contrast`, `sign_cell_ratio`), nicht
auf dieses Feld beschränkt, und hier bewusst nicht separat behoben.

## 0.1.0.dev0 — 2026-09-09 (Zwischenraum zwischen Ziffernstellen)

### `digit_gap_ratio` ergänzt das bisher lückenlose Ziffernraster

**Problem:** `DisplayLayout.cell_boxes` teilte den OCR-Rahmen ohne jeden
Zwischenraum durch die Stellenzahl — Ziffernzellen (und die Vorzeichenstelle)
lagen rechnerisch exakt aneinander. Bei der Bedienprüfung im Browser zeigte
sich, dass die gelben Segment-Abtastpunkte an mehreren Stellen zu weit
auseinander lagen, sobald der Bediener den OCR-Rahmen auf eine reale Anzeige
mit sichtbarem physischem Abstand zwischen den Stellen legte: Das Raster nahm
diesen Abstand fälschlich als Teil der Ziffernzelle an, wodurch die festen
relativen Segmentpunkte (`SEGMENT_SAMPLE_POINTS`) neben statt auf den
Segmenten landeten — ein weiterer Beitrag zur unter OQ-23 dokumentierten
Fehlablesung, unabhängig von der VFD-Glyphenform.

**Änderung:** `DisplayLayout` bekommt ein neues Feld `digit_gap_ratio`
(Default `0.0`, reproduziert exakt das bisherige Verhalten). `cell_boxes`,
`sign_box` und der synthetische Renderer (`synthetic_source.render_display`)
verwenden dieselbe Formel für Zellenbreite und -abstand, sodass Generator und
Leser weiterhin dasselbe Raster meinen. Ältere gespeicherte Profile ohne das
Feld werden beim Laden mit dem Default aufgefüllt, keine Vermutung über die
tatsächliche Anzeige. Die Workbench zeigt den Wert als eigene Bedienzeile
„ziffernabstand" neben „vorzeichenbreite", inklusive Presets und Grenzen aus
`LAYOUT_RATIOS`.

**Konsequenz:** Der Bediener kann den Zwischenraum zwischen den Stellen jetzt
am eingefrorenen Realbild sichtbar nachjustieren, statt ein lückenloses
Raster zu unterstellen. Behebt nicht die abweichende VFD-Glyphenform aus
OQ-23 — dafür bleibt ein bestätigter Real-Testsatz nötig —, entfernt aber
eine unabhängige Fehlerquelle in der Geometrie selbst.

## 0.1.0.dev0 — 2026-09-09 (sichtbare OCR-Rasterkalibrierung)

### Äußere Perspektiv-ROI und inneres Ziffernraster getrennt einstellbar

**Problem:** Die perspektivische ROI ließ sich bereits an vier Displayecken
ausrichten, der Segmentleser verteilte seine Zellen aber immer über den gesamten
entzerrten Ausschnitt. Enthielt dieser Rahmen Blende, Einheit oder seitlichen
Leerraum, lagen Zellen und sieben Segment-Abtastpunkte neben den Ziffern. Im
eingefrorenen Editor war das wirksame OCR-Raster außerdem nicht sichtbar.

**Änderung:** Profilschema 3 ergänzt `ocr_box` als normierten Innenausschnitt
der entzerrten ROI; Profile aus Schema 1 und 2 werden mit einem zunächst vollen
Innenausschnitt migriert. Der Browser zeichnet während der Kalibrierung die
grüne Perspektiv-ROI und darüber den gelben OCR-Rahmen, Ziffernzellen,
Vorzeichenbereich und alle tatsächlichen Abtastpunkte. Anklicken oder `g`
wechselt den aktiven Rahmen; Maus und Pfeiltasten verschieben beziehungsweise
skalieren ihn. Der Leser schneidet `ocr_box` vor der Segmentanalyse wirklich
aus, und Fokusansicht sowie Live-Overlay benutzen dieselbe Geometrie. Das
eingefrorene Overlay übernimmt reine Layoutänderungen sofort aus dem laufenden
Status; Ziffernzahl und Vorzeichenbreite bauen das Raster neu auf, die feste
Dezimalposition erscheint als eigener cyanfarbener Marker. Solche Änderungen
aktualisieren die Editierrevision, sodass `Enter` weiterhin funktioniert;
Kamera- und sonstige Profiländerungen machen das Bild weiterhin ungültig.

**Konsequenz:** Der Bediener kann das Leseraster an einem eingefrorenen echten
Frame exakt auf Vorzeichen und Ziffern kalibrieren, ohne die äußere
Perspektivkorrektur zu verlieren. Eine automatische Grenzerkennung aus einem
einzelnen Frame wurde bewusst nicht als Wahrheit übernommen: Leuchtsegmente,
Blende und Einheit sind ohne bestätigte Realbeispiele nicht zuverlässig zu
trennen. Unlesbare Raster bleiben abgelehnt statt automatisch passend geraten.

## 0.1.0.dev0 — 2026-09-09 (perspektivische OCR-ROI und Reaktionsfähigkeit)

### Vier Ecken statt starrer Box; Bildarbeit blockiert die Bedienung nicht mehr

**Problem:** Nach der ROI-Bestätigung rechnete die Workbench weiterhin in
jedem Bild die Vollbild-Kandidatensuche, Entzerrung, OCR, Overlays und
JPEG-Kompression, während sie den zentralen Controller-Lock hielt. Status-,
Editier- und Stopbefehle konnten dadurch hinter der Bildschleife verhungern.
Die ROI war außerdem nur achsparallel; ein schräg aufgenommenes Display ließ
sich nicht passend entzerren. Zum Stoppen gab es keinen lokalen
Workbench-Befehl.

**Änderung:** Die Bildarbeit läuft jetzt weitgehend außerhalb des Locks. Nach
Bestätigung entfällt die Vollbildsuche, die OCR-Vorschau läuft mit 5 Hz und das
15-fps-Kamerabild bleibt flüssig. Die Profilversion 2 speichert zusätzlich ein
normiertes Vierpunkt-`roi_quad`; v1-Rechtecke werden beim Laden automatisch und
verlustfrei migriert. Der Browsereditor bietet vier einzeln verschiebbare
Ecken, `rectify` korrigiert Perspektive und Neigung, und Zellen/Abtastpunkte
werden perspektivisch ins Kamerabild zurückprojiziert. `dispread stop` beendet
den Dienst über den nur lokal zugänglichen Unix-Socket. Auch Kamera-`stop` und
`close` haben beim Shutdown einen Wachhund.

**Konsequenz:** Bestätigte ROIs erzeugen keine dauernde Vollbildsuche mehr;
Status und Stop bleiben während der Bildverarbeitung erreichbar. Eine isolierte
Messung am gespeicherten 960×720-Bild sank von 30,837 ms/Bild vor Bestätigung
auf 5,801 ms/Bild mit bestätigter ROI und gedrosselter OCR. Die perspektivische
Entzerrung ist synthetisch getestet. Sie löst nicht die abweichende reale
VFD-Glyphengeometrie aus OQ-23; dafür werden echte, getrennte Trainings- und
Testbilder benötigt.

## 0.1.0.dev0 — 2026-09-09 (OCR-Bedienung)

### Zahlenerkennung ist in Web-Setup und TUI bedienbar

**Problem:** Der Segmentleser lief bereits auf der bestätigten Kamera-ROI und
lieferte seine Evidenz in `snapshot()["reading"]`, aber Zahlenformat und
Ergebnis waren in der gemeinsamen Einstelltabelle nicht sichtbar. Die
Bedienperson musste das Layout über Profildatei oder lokalen Rohbefehl setzen
und konnte Ablehnungsgründe nicht im Setup prüfen.

**Änderung:** `workbench/fields.py` liefert jetzt Auswahlzeilen für
Ziffernzahl, profilfeste Nachkommastellen, Vorzeichen und bestätigte Einheit
sowie ein Zahlenfeld für die Vorzeichenbreite. Unmögliche Kombinationen werden
vor der Auswahl gesperrt; geladene Sonderwerte bleiben sichtbar. Drei
Anzeigezeilen zeigen Rohtext/Zahlenwert, die Freigabevorschau und erklärbare
Segment-/Ausschnittevidenz. Web und TUI verwenden diese Zeilen ohne eigenen
OCR-Pfad. Integrationstests schicken eine synthetische Anzeige durch
`Controller.publish()` und belegen außerdem, dass eine unbekannte
Dezimalposition abgelehnt statt geraten wird.

**Konsequenz:** Die bestehende Bright-on-dark-7-Segment-Erkennung kann jetzt
vollständig aus der Workbench eingerichtet und diagnostiziert werden. Sie
bleibt bewusst eine Vorschau: kein `ValueRecord`, keine Messwertfreigabe, keine
serielle Ausgabe; Einheit und Dezimalposition stammen weiter aus dem Profil,
und `declares_confidence_calibrated` bleibt `False`. Die erste Prüfung am
beschrifteten BK-5491B-Realbild wurde sicher abgelehnt (`777?7`, kein Wert),
zeigt aber, dass das feste synthetische Segmentraster nicht auf diese
VFD-Schrift übertragbar ist; die Weiterarbeit ist als OQ-23 dokumentiert.

## 0.1.0.dev0 — 2026-09-09 (noch später)

### Power-Zyklus-Budget überlebt jetzt einen dispread-Neustart korrekt (OQ-22)

**Problem:** `geometry_cycles` lebte nur im Prozessspeicher. Der RP2040
merkt sich Power-Zyklen aber pro **Boot**, nicht pro Prozess (belegt: ein
Test mit je einem frischen Python-Prozess pro Zyklus hing trotzdem nach
~24 Zyklen). Ein Neustart von `dispread` allein — ohne Host-Reboot — hätte
den Zähler faelschlich auf 0 gesetzt und so mehr echte Power-Zyklen erlaubt,
als das Sicherheitsbudget vorsieht. Das Sicherheitsversprechen aus der
vorigen Änderung war damit lückenhaft.

**Änderung:** `geometry_cycles` wird jetzt zusammen mit der aktuellen
Kernel-Boot-ID (`/proc/sys/kernel/random/boot_id`) in
`camera_cycles.json` persistiert (`_load_geometry_cycles`,
`_save_geometry_cycles`, `atomic_json`). Stimmt beim Start die gespeicherte
Boot-ID mit der aktuellen überein, wird der Zähler fortgeführt; bei einem
echten Reboot (andere oder fehlende Boot-ID) beginnt er korrekt bei 0.

**Konsequenz:** Das Sicherheitsbudget haelt jetzt auch ueber
`dispread`-Neustarts hinweg, ohne dass ein Host-Reboot noetig ist, um den
Zaehler zu "umgehen". Zwei neue Tests beweisen beide Faelle:
`test_geometry_cycles_survive_process_restart_same_boot` (gleiche Boot-ID
-> Zaehler bleibt) und `test_geometry_cycles_reset_on_new_boot`
(abweichende Boot-ID -> Zaehler auf 0). 67 Tests und `ruff check src tests
examples` grün.

## 0.1.0.dev0 — 2026-09-09 (spätabends)

### Hartes Power-Zyklus-Budget: RP2040-Sperre kann durch Workbench-Bedienung nicht mehr ausgeloest werden (OQ-22)

**Problem:** Bislang konnte eine Bedienperson im `setup`-Tab beliebig oft
Aufloesung oder Bildrate aendern. Jede echte Aenderung kostet einen
RP2040-Power-Zyklus (bestaetigt: unbind/rebind-Test hat den Regulator
tatsaechlich auf 0 Nutzer fallen lassen). Nach real gemessenen ~20-25
Zyklen antwortet der Chip nicht mehr auf I2C - bislang ohne Vorwarnung,
mitten in einer Sitzung.

**Änderung:** Neue Konstante `MAX_GEOMETRY_CYCLES = 15` (Sicherheitsabstand
unter dem beobachteten Bereich). `Controller.geometry_cycles` zaehlt jeden
tatsaechlichen Stream-Neuaufbau in `_worker`. `_check_geometry_budget()`
verweigert `camera.set`/`camera.set_many`, sobald eine **echte** Aenderung
(nicht das Wiederwaehlen des bereits aktiven Werts) das Budget
ueberschreiten wuerde, mit klarer Fehlermeldung statt eines spaeteren,
unvorhersehbaren Ausfalls. `geometry_cycles`/`geometry_cycles_max` stehen
jetzt in `snapshot()`.

**Konsequenz:** Solange nur ueber die Workbench bedient wird, kann die
RP2040-Sperre **nicht mehr unbeabsichtigt ausgeloest werden** - die
Bedienperson bekommt stattdessen rechtzeitig die Aufforderung, `dispread`
(und danach den Host) neu zu starten, statt dass die Kamera mitten in einer
Messreihe unvorhersehbar haengt. Das behebt den RP2040-Fehler selbst nicht,
verhindert aber zuverlaessig, ueber die eigene Bedienoberflaeche
hineinzulaufen. Neuer Test
`test_geometry_budget_blocks_change_but_allows_same_value` beweist beides:
echte Aenderung wird bei erschoepftem Budget verweigert, Wiederwaehlen des
aktiven Werts bleibt erlaubt. 65 Tests und `ruff check src tests examples`
grün.

## 0.1.0.dev0 — 2026-09-09 (später)

### Aufloesungswechsel kostet jetzt deterministisch einen statt zwei Power-Zyklen (OQ-22)

**Problem:** Der `resolution`-Auswahlzeile in `fields.py` sandte Breite und
Hoehe als zwei getrennte `camera.set`-Befehle. Der zuvor ergaenzte
250-ms-Entprellpfad in `_worker` buendelt das meistens zu einem
Stream-Neuaufbau, ist aber eine Zeitfensterheuristik - kein garantiertes
Verhalten, falls die beiden Befehle mit mehr Abstand ankommen.

**Änderung:** Neuer Controller-Befehl `camera.set_many` setzt mehrere
Kamerafelder in genau einer `_change()`-Revision; die per-Feld-Logik aus
`camera.set` ist dafuer in `_apply_camera_key()` ausgelagert (von beiden
Befehlen geteilt, keine Dopplung). Die Aufloesungszeile in `fields.py`
sendet jetzt einen einzigen `camera.set_many`-Befehl mit Breite und Hoehe
zusammen statt zwei `camera.set`-Befehlen.

**Konsequenz:** Ein Aufloesungswechsel kostet garantiert genau einen
RP2040-Power-Zyklus statt (zeitfensterabhaengig) bis zu zwei - unabhaengig
vom Timing zwischen den beiden Feldern. Neuer Test
`test_camera_set_many_is_one_atomic_revision` beweist das direkt: eine
Revision, beide Felder gesetzt. 64 Tests und `ruff check src tests
examples` grün.

## 0.1.0.dev0 — 2026-09-09

### Kamerathread: Geometrie-Aenderungen buendeln, haengende Kamera-Ioctls sichtbar machen (OQ-22)

**Problem:** Ein Diagnose-Reproducer ohne `dispread`-Code hat gezeigt, dass
der RP2040-Bridge-Chip auf der AI-Camera nach rund 20-25 Power-Zyklen
(`stop`/`configure`/`start`) innerhalb einer Bootsitzung nicht mehr auf I2C
antwortet — danach haengt jeder weitere Kamerazugriff, nur ein Reboot hilft
(Details: [OQ-22](docs/open-questions.md)). `Controller._worker` loeste
bislang bei **jeder** einzelnen Aenderung von Breite, Hoehe oder Bildrate
sofort einen Neuaufbau aus; da die Weboberflaeche Breite und Hoehe als zwei
getrennte Befehle sendet, kostete eine Aufloesungsaenderung im Betrieb zwei
Power-Zyklen statt einem. Zusaetzlich hing der Worker bei einer haengenden
Kamera-Ioctl (`configure`/`start`/`stop`/`capture_request`) fuer immer
schweigend, statt den Fehler als das zu melden, was er ist.

**Änderung:** `_worker` puffert Geometrie-Aenderungen ueber ein kurzes
Zeitfenster (`GEOMETRY_DEBOUNCE_S`, 250 ms) und baut den Stream erst neu auf,
wenn Breite/Hoehe/Bildrate sich nicht mehr aendern — mehrere schnelle
Befehle buendeln sich so zu einem Neuaufbau statt mehrerer. Die riskanten
Kameraaufrufe (`stop`, `configure`, `start`, `capture_request`) laufen jetzt
ueber `_guarded()`: ein Wachhund-Thread mit `CAMERA_OP_TIMEOUT_S` (6 s).
Kehrt der Aufruf nicht zurueck, wird das als `CameraWedgedError` gemeldet
("Kamera reagiert nicht (...); vermutlich RP2040-Sperre (OQ-22), Reboot
noetig") statt als endloser Timeout; die anschliessende Aufraeumroutine
verzichtet dann bewusst auf einen weiteren `stop()`/`close()` auf demselben,
bereits blockierten Kameraobjekt.

**Konsequenz:** Reine Belichtungs-/Verstaerkungs-/Kontraständerungen waren
bereits vorher `set_controls()`-only und bleiben unveraendert kostenlos.
Aufloesungs-/Bildratenaenderungen kosten jetzt hoechstens einen Power-Zyklus
statt zwei. Eine echte RP2040-Sperre wird jetzt innerhalb von rund
`CAMERA_OP_TIMEOUT_S` als klarer Fehlerzustand sichtbar (`snapshot()["error"]`)
statt als unbestimmt haengender Kamerathread — behebt die Sperre selbst
nicht, macht sie aber sofort erkennbar. 63 Tests und `ruff check src tests
examples` weiterhin grün; die bestehenden Workbench-Tests laufen alle mit
`simulate=True` und durchlaufen den neuen Entprell-/Wachhundpfad nicht — ein
gezielter Test dafür fehlt noch.

## 0.1.0.dev0 — 2026-09-08

### Zahlenerkennung an der Kamera angeschlossen (Zwischenstand, Bedienung fehlt)

**Problem:** Die Verarbeitungskette aus Konzept §3 war fertig, lief aber nur
gegen synthetische Bilder. Die Workbench besaß Kamera und bestätigte ROI, hat
daraus aber nie einen Wert gelesen — und im Profil fehlte das Zahlenformat, das
der Segmentleser laut Konzept §4 braucht.

**Änderung:** Das Workbench-Profil führt einen `layout`-Block (`digits`,
`decimals`, `has_sign`, `unit` plus Rasterverhältnisse) mit eigener Prüfung in
`profiles.validate_layout` — unmögliche Formate wie „mehr Nachkommastellen als
Stellen" werden abgelehnt. Der Controller entzerrt bei bestätigter ROI jedes
Bild über `rectify` auf feste 400×160, liest es mit `SevenSegmentReader` und
führt die Freigabeprüfung `ReleaseGate` **als Anzeige** mit. Ergebnis, Evidenz
je Stelle, Ablehnungsgründe und Qualität des Ausschnitts stehen in `snapshot()["reading"]`.
Die Abtastpunkte der sieben Segmente werden ins Kamerabild zurückgezeichnet,
hell wenn gemessen aktiv — damit sieht der Bediener, ob das Raster sitzt. Neuer
Befehl `layout.set`.

**Konsequenz:** Aus einem scharfen Kamerabild entsteht ein gelesener Wert samt
Begründung, warum er freigegeben würde oder nicht. **Kein** `ValueRecord`, keine
Freigabe, keine serielle Ausgabe — `released` ist konstant `false`, und die
Zeitangabe der Vorschau-Veralterung ist CLOCK_MONOTONIC und ausdrücklich kein
Messwertzeitbezug. Die Einheit stammt weiter aus dem Profil
(`unit_source=profile`), sie wird nicht gelesen.

**Was noch fehlt:** Die Bedienzeilen in `fields.py` (Zahlenformat als
Auswahlfelder, Ablesung und Ablehnungsgründe als Anzeigezeilen) und die Tests
für den Lesepfad. Der Kern ist gegen einen synthetisch gerenderten Wert geprüft:
gezeichnet `-12.34`, gelesen `-012.34`, Wert −12,34, Freigabeprüfung `valid`
ohne Ablehnungsgründe. Bis das UI steht, ist das Zahlenformat nur über
`layout.set` oder die Profildatei erreichbar. 63 Tests und Ruff grün — die
Tests deckten diesen Pfad noch **nicht** ab.

### Einstelltabelle in der Weboberfläche, Werte werden ausgewählt statt getippt

**Problem:** Die Einrichtung lag nur in `dispread tui`, das der Bediener erst in
der Web-Shell von Hand starten musste. Dort war jedes Feld ein Freitextdialog
mit `json.loads`: `true`/`false` für Belichtungsautomatik und Fokusassistenz,
Zahlen für die Belichtung, aber `mode` und `role` ohne Anführungszeichen. Typ,
Grenzen und Default lagen in den Kamera-Capabilities längst maschinenlesbar vor.

**Änderung:** Neues Modul `workbench/fields.py` beschreibt Zeilen und Aktionen
einmal als Daten (`rows()`, `actions()`, `run_blocked()`); `/status` liefert sie
mit, die Weboberfläche rendert daraus einen festen `setup`-Tab neben den Shells,
der nach der Anmeldung sofort aktiv ist. Auswahlfelder für Modus, Rolle,
Auflösung, Bildrate, Belichtungsautomatik, Fokusassistenz und Profil;
Zahlenfelder mit Kameragrenzen und Schnellwahl für Belichtungszeit, Verstärkung
und Kontrast; Anzeigebereich und Erkennungsfilter als reine Anzeigezeilen.
Gesperrte Zeilen und Aktionen nennen ihren Grund, statt erst am Kommando zu
scheitern. `dispread tui` bleibt für den Betrieb ohne Browser und rendert
dieselbe Quelle mit Auswahllisten statt Freitext. `snapshot()` führt die
vorhandenen Profilnamen mit; Freitext bleibt nur für einen neuen Profilnamen.

**Konsequenz:** Einrichtung ohne zusätzliches Kommando und ohne JSON-Kenntnis;
Web und Terminal können nicht mehr auseinanderlaufen, weil beide dieselben
Optionen lesen. Der Controller bleibt die durchsetzende Instanz — `fields.py`
ist Bedienhilfe, keine Regel. Keine OCR, Messwertfreigabe oder neue
Abhängigkeit. 63 Tests und Ruff grün, darunter der Nachweis, dass jede
angebotene Auswahl vom Controller angenommen wird. setup-Tab mit 21 Prüfpunkten
in Chromium über eine `file://`-Seite mit echter `/status`-Antwort geprüft;
Netzwerknavigation dieses Chromium bleibt defekt (OQ-21). Keine erneute
Hardwaremessung.

### Authentifizierte Kamera-Workbench mit Shell, TUI und Profilen

**Problem:** Der Ein-Datei-Prototyp bot weder echte Shells noch eine gemeinsame
Steuerung für Kameraeinstellungen, gespeicherte Profile und Boxkorrekturen.

**Änderung:** `dispread serve` startet eine HTTPS-Workbench mit Linux-PAM-
Anmeldung für `me-systeme`, echten PTY-Shell-Tabs und lokaler Unix-Socket-API.
`dispread tui` bietet eine tastaturbediente Einstelltabelle. Ein Kamerathread
verwaltet validierte Live-Controls, automatische Einstellvorschläge,
Fokusassistenz, Profilkonflikte und eingefrorene Bilder für ROI/Annotationen.
Der bisherige Beispielaufruf bleibt als Einstieg erhalten. Systemabhängigkeiten
und lokal ausgelieferte xterm-Assets sind dokumentiert.

**Konsequenz:** Einheitliche Steuerung ohne Sliderwand; Browsertrennung beendet
keine Shell. Noch keine OCR, Messwertfreigabe oder Modelltraining. 58 Tests
einschließlich TLS/WebSocket/Shell/TUI grün; realer Kameradienst geprüft.
Chromium-UI mit simuliertem Transport geprüft. Vollständige HTTPS-Browserabnahme
bleibt wegen lokaler Chromium-Navigationsprobleme offen (OQ-21); ebenso
gerätespezifische Auto-Setup-Validierung (OQ-20).

### Barebones-Terminalansicht für die Kameravorschau

**Problem:** Die Vorschauseite enthielt erklärenden Fließtext und kein
eigenes Logfenster.

**Änderung:** Dunkle Monospace-Oberfläche mit Kamera- und Logfenster,
kompaktem Live-Status, Bildnummer und Verarbeitungsrate. Auf schmalen
Bildschirmen stehen die Fenster untereinander. Erklärungen, Verbindungswechsel,
Kamerafehler und periodische Statusmeldungen erscheinen im Browserlog mit
UTC-Zeitangabe. Maximal 300 Zeilen, `clear`, automatisches Scrollen nur am Ende.

**Konsequenz:** Weniger Text außerhalb des Logs. Das Log enthält
Vorschaudiagnostik, keine Shell und keine vollständige Prozess-stdout-Umleitung.
Neun Vorschautests und Ruff grün; Terminalansicht mit simuliertem Feed in
Chromium geprüft. Keine erneute Hardwaremessung.

### Kameralivebild mit Display-Kandidaten über SSH

**Problem:** Für den ersten Versuch fehlte eine Livevorschau auf dem
Windows-Rechner und eine automatische Suche nach möglichen Anzeigebereichen.

**Änderung:** `examples/17_camera_display_preview.py` verbindet Picamera2,
OpenCV-Konturfilter, gelbe Kandidatenboxen und einen lokalen MJPEG-HTTP-Server.
Windows greift über SSH-Portweiterleitung im Browser zu. Nur das neueste Bild
wird vorgehalten; die Seite blendet bei ausbleibendem Bildfortschritt oder
Verbindungsabbruch das Bild aus. Filter sind per Argument einstellbar.

**Konsequenz:** Vorschau ohne zusätzliche Abhängigkeiten; keine OCR oder
Messwertfreigabe. Neun neue Tests prüfen Erkennung, HTTP und Fehlerbehandlung.
Realer Kamerastream lokal geprüft, Windows/SSH und Erkennungsqualität am
Gerät noch offen. Anleitung: `docs/anleitung/10-kamera-livevorschau.md`.

### Kamera in Betrieb genommen und vermessen

**Problem:** Die AI Camera war an CAM/DISP0 angeschlossen, wurde aber nicht
erkannt. `rpicam-hello --list-cameras` meldete `No cameras available!`.

**Änderung:** `scripts/camera-commissioning.sh` prüft die gesamte Kette rein
lesend durch und nennt am Ende die nächste Maßnahme. Ursache war der fehlende
Reboot — `camera_auto_detect` prüft die Anschlüsse ausschließlich beim Booten,
und die Kamera war nach dem letzten Boot angesteckt worden.

**Konsequenz:** Kamera läuft. Zwei Falschmeldungen im Skript beseitigt:
`dtoverlay -l` ist kein Kriterium (firmwareseitig angewandte Overlays
erscheinen dort nicht), und die CAM-I2C-Busnummern sind nicht stabil (hier 6
und 10). Nachweis ist der Sensorknoten im Device-Tree plus die
libcamera-Enumeration. Gemessen: 6,8 s `.rpk`-Warmlauf, 15,0 Inferenzen/s,
`SensorTimestamp` in CLOCK_BOOTTIME — siehe `docs/TIMING.md`.

### Verarbeitungskette aus Konzept §3 aufgebaut

**Problem:** Das Repo enthielt nur das Konzept, keinen Code. Zugleich sind
zentrale Anforderungen offen — das GSVmulti-Telegramm ist unbekannt, es gibt
keinen Datensatz echter Geräte.

**Änderung:** Alle Trennstellen als `Protocol` definiert, mit `frozen`
Datenklassen als Vertrag: `FrameSource`, `DisplayLocator`, `ValueReader`,
`ReleaseGate`, `ValueSink`, `TelegramFormatter`. Implementiert sind
`synthetic://` als Bildquelle, `manual_roi` als Lokalisierung, die
Vierpunkt-Entzerrung, der 7-Segment-Leser mit Per-Segment-Evidenz, die
Freigabelogik, das JSONL-Audit-Log und die serielle Ausgabe mit provisorischem
ASCII-CSV.

**Konsequenz:** Die Kette läuft Ende zu Ende ohne Hardware
(`examples/16_end_to_end_headless.py`, 40/40 korrekt, 40 Telegramme auf der
Leitung). Das echte GSVmulti-Format ist später ein neuer Formatter, keine
Änderung an der Pipeline.

### Bestätigte manuelle ROI als Primärpfad statt IMX500-Detektion

**Problem:** Naheliegend wäre, die Anzeige mit einem der 23 mitgelieferten
IMX500-Modelle zu finden.

**Änderung:** Priorität umgekehrt. Gemessen liefert `network_intrinsics`
COCO-Labels (`person`, `bicycle`, `tv`) — für Messverstärker-Displays
unbrauchbar. Eigene Modelle sind auf diesem Pi nicht konvertierbar, nur der
Packager ist vorhanden.

**Konsequenz:** Werterkennung, Freigabelogik und Ausgabekette konnten sofort
gebaut und gemessen werden. Konzept §10 Ph. 2 nennt den manuellen Ausschnitt
selbst als Rückfalloption. Die Detektion bleibt austauschbar.

### Segmentschwelle aus den Segmentmessungen statt aus dem Bild

**Problem:** Zwei Fehlversuche. Eine Schwelle pro Ziffernzelle verwarf jede
`8` (bei sieben aktiven Segmenten ist der zellinterne Kontrast null). Otsu über
alle Bildpunkte erkannte den Überlauf nicht — eine 7-Segment-Anzeige hat drei
Helligkeitsstufen, und die inaktiven Segmente sind die häufigste.

**Änderung:** Die Schwelle kommt aus den gepoolten Segmentmessungen aller
Stellen.

**Konsequenz:** `8` wird gelesen, Überlauf erkannt, starke Unschärfe führt
nicht mehr zur Ablehnung aller Frames. Bekannte Grenze: zeigt die Anzeige
ausschließlich `8`, wird abgelehnt (OQ-13) — nach Konzept §7 die zulässige
Richtung.

### Invarianten aus Konzept §7 im Code verankert

**Änderung:** Der `ValueRecord`-Konstruktor verweigert einen `STALE`- oder
`UNREADABLE`-Datensatz mit Zahlenwert und eine Ablehnung ohne Begründung.
`ValueReader.read` und `ReleaseGate.evaluate` bekommen den Referenzwert
strukturell nicht als Parameter. Vorzeichen, Dezimalpunkt und Einheit sind
eigenständige Ablehnungskriterien; `sign_region_readable` ist getrennt von
`sign_detected`.

**Konsequenz:** Alle drei „stillen" Fehlermodi aus §7 haben einen Test, der
fehlschlägt, wenn das System sie zeigt — inklusive des Nachweises, dass ein um
20 % verfälschter Referenzwert identische Datensätze erzeugt.

### Zeitbasis als Pflichtfeld

**Problem:** Beim Entwickeln ohne Kamera entstehen Zeitstempel, die keine
Zeitaussage tragen. Der naheliegende Fehler wäre, sie später als reale
Latenzen zu berichten.

**Änderung:** `TimeBaseKind` ist Pflichtfeld in `Frame` und `ValueRecord`, mit
`carries_time_information`. Adapterzustand liegt in einem separaten
`TxReceipt`; der Adapter darf `capture_timestamp` nie verändern.

**Konsequenz:** `report.json` weist `timing_is_meaningful` maschinenlesbar aus.

### Dokumentation als Projektbestandteil

**Änderung:** `docs/status.md` (Momentaufnahme), `project_history.md`
(Entscheidungen), `open-questions.md` (OQ-01 bis OQ-19), `lab_journal.md`
(Experimente inklusive Fehlversuche), `TIMING.md`, `VALIDATION.md`,
`ROADMAP.md`, `HARDWARE_PROFILE.md`, `CAMERA_COMMISSIONING.md`,
`OPTICAL_SETUP.md`, `GSVMULTI_PROTOCOL.md`, `dependencies.md`. Die
Aktualisierungspflicht steht in `AGENTS.md`.

**Konsequenz:** `pyproject.toml` deklarierte zwei Konsolenskripte auf nicht
vorhandene Module — entfernt, weil ein Einsprungpunkt auf ein fehlendes Modul
erst zur Laufzeit scheitert. `CLAUDE.md` markiert je Komponente, was fertig ist.
