# Plan: Workbench-Editor — Klickpriorität, automatische Box-Vorschläge, Ground-Truth-Erfassung

Status: **umgesetzt am 2026-09-10**, siehe `CHANGELOG.md` (oberster
Abschnitt), `docs/VALIDATION.md` (reale Vorschlagsqualität) und
[OQ-25](open-questions.md) (bekannte Grenze: Haupt-/Nebenanzeige-
Verwechslung bei `ocr.suggest`). Entstanden aus Bedienerrückmeldung und
Recherche in der Sitzung vom 2026-09-09 (`docs/status.md`, `CHANGELOG.md`
desselben Tages).

**Update 2026-09-10, spät — Stufe 2 (der `R`-Zug-Vorschlagsfluss dieses
Plans) noch am selben Tag abgelöst.** Ein gemeldeter Bug (Klick auf die
ROI-Box während einer laufenden `roi.suggest`/`ocr.suggest`-Anfrage verwarf
die eintreffende Vermutung und schlug wieder die alte bestätigte Geometrie
vor — Ursache: beide Ops rechneten ihre OpenCV-Arbeit innerhalb des
Controller-Locks, anders als `publish()`) führte zu einem grösseren
Bedienerwunsch: die Tastatursteuerung (`R`, `G`, `Shift+Pfeile`,
`Strg+Enter`) wich einem zweistufigen, TUI-artigen Knopf-Ablauf (✓/✎ an ROI-
und OCR-Box, anklickbare Live-Kandidaten). Der `roi.suggest`-Op aus diesem
Plan ist entfernt; `fit_quad_in_region`/`fit_ocr_box` selbst bleiben
(anderweitig weiterverwendet). Details: `CHANGELOG.md`, Eintrag "TUI-style
two-stage confirm workflow"; `docs/anleitung/10-kamera-livevorschau.md`
entsprechend aktualisiert. Dieser Plan bleibt als Entstehungsgeschichte
stehen, beschreibt aber nicht mehr den aktuellen Bedienablauf.

## Kontext

Die Kalibrierung eines neuen Geräteprofils im Browser-Editor
(`src/dispread/workbench/static/workbench.js`) ist heute vollständig manuell:
der Bediener zieht sowohl die grüne perspektivische `roi_quad` als auch die
gelbe achsparallele `ocr_box` (Ziffernbereich) pixelgenau per Hand. Das hat
zwei konkrete Probleme, die der Bediener in dieser Sitzung gemeldet hat:

1. **Verklicken beim Verschieben.** Direkt nach einer frischen `roi`-Bestätigung
   startet `ocr_box` als `[0,0,1,1]` — exakt deckungsgleich mit `roi_quad`. Die
   Ecken-Trefferlogik (`nearestHandle` in `workbench.js`) sucht global den
   nächsten Punkt über *beide* Boxen zusammen und bevorzugt bei Gleichstand
   `roi`; auch danach kann bei eng benachbarten Ecken der falsche Rahmen
   getroffen werden. Der Bediener wollte eigentlich die kleinere, innere
   OCR-Box bewegen und verschiebt stattdessen die äußere ROI.
2. **Mühsame manuelle Platzierung ohne jede Automatik.** Es gibt zwar
   `find_display_candidates()` (`workbench/vision.py`) für grobe,
   achsparallele Kandidatenboxen über das *ganze* Bild (nur vor der ersten
   Bestätigung genutzt), aber keinerlei automatische Erkennung der
   perspektivischen `roi_quad` und überhaupt keine automatische Erkennung der
   `ocr_box`. Jede Kalibrierung eines neuen Geräts erfordert vollständiges
   manuelles Ziehen aller acht Eckpunkte.

Der Bediener möchte wissen, welche Automatisierungsansätze es gibt, welcher am
vielversprechendsten ist, ob die im neuen `annotate`-Modus gesammelten
Aufnahmen dabei helfen können, und ob ein grober Bediener-Hinweis (statt
Vollautomatik ohne jeden Hinweis) der bessere Weg ist.

**Recherche-Ergebnis, das diesen Plan trägt** (siehe Sitzungsverlauf,
`Konzept.md` §4/§5/§10, `docs/project_history.md` 2026-09-07,
`docs/ROADMAP.md`, `docs/anleitung/07-lokalisierung.md`,
`docs/status.md`, `docs/anleitung/10-kamera-livevorschau.md`):

- `manual_roi` bleibt laut ausdrücklicher Projektentscheidung der
  Primärpfad; jede Automatik darf nur einen **Vorschlag** liefern, den der
  Bediener bestätigen muss — nie automatisch übernommene Geometrie
  (`docs/status.md`, `docs/anleitung/07-lokalisierung.md`: "Nicht die
  bestätigte ROI 'verbessern'... Die Bestätigung ist der Akt eines
  Menschen").
- Ein trainiertes Modell (YOLO/SSD, IMX500-Inferenz) ist explizit **nicht**
  der nächste Schritt: die 23 mitgelieferten `.rpk` sind COCO-/ImageNet-Modelle
  (unbrauchbar für Messverstärker-Displays), auf dem Pi fehlt der
  Modell-Converter (nur Packager vorhanden, OQ-11), und das ist ROADMAP-Phase
  **P8 — optional, letzte Phase**, gated auf einen belegten Latenz-/Lastgewinn.
- Ein grober Bediener-Hinweis ist **zuverlässiger als Vollautomatik ohne
  Hinweis**, nicht nur "genauso schwer umzusetzen": Ohne jeden Hinweis kann
  eine Kontursuche mehrere ähnlich rechteckige Objekte auf dem Prüfstand
  (andere Messgeräte, Gehäusekanten, Papier) nicht unterscheiden — genau der
  in `docs/anleitung/07-lokalisierung.md` benannte Fall (auch die
  Haupt-/Nebenanzeige-Verwechslung aus Konzept §7 ist ohne jeden Hinweis
  strukturell unlösbar). Für die `ocr_box` liefert die bereits entzerrte
  `roi_quad`-Fläche selbst schon einen sehr starken impliziten Hinweis — dort
  braucht es keinen zweiten Bediener-Klick.
- `annotate`-Aufnahmen enthalten aktuell **keinen** abgelesenen Wert (nur
  Geometrie) und werden nirgends zurückgelesen — eine wachsende, für Training
  nutzbare Datenbasis braucht als kleinsten nächsten Schritt einen getippten
  Ground-Truth-Wert je Aufnahme, keine Trainingsinfrastruktur.

Bestätigt vom Bediener für diesen Plan: grober Hinweis per Taste `R` +
Rechteck-Ziehen um das Display, danach automatischer `ocr_box`-Vorschlag ohne
zweiten Klick; unbestätigte Vorschläge werden gestrichelt/transparent
dargestellt, bis sie berührt oder bestätigt werden; alles wird in einem
zusammenhängenden, intern gestuften Vorgehen umgesetzt.

## Stufe 1 — Klickpriorität und Startzustand der Editor-Boxen

**Datei:** `src/dispread/workbench/static/workbench.js`

- `nearestHandle(x,y)`: von "global nächster Punkt über beide Boxen" auf
  "zuerst alle `ocr`-Ecken innerhalb des Trefferradius (18px) prüfen, nur wenn
  keine trifft die `roi`-Ecken prüfen" umstellen — die gelbe Box liegt auch
  optisch über der grünen (`draw()` zeichnet `roi` zuerst, `ocr`-Konturen und
  -Ecken danach), Trefferlogik soll das widerspiegeln.
- Der Körper-Drag-Fallback in `canvas.onpointerdown` (`inside ocr_box ? 'ocr' :
  'roi'`) ist schon richtig priorisiert und bleibt unverändert.

**Datei:** `src/dispread/workbench/controller.py`, `op == "freeze"`

- Wenn `self.config["ocr_box"]` noch der unberührte Default `[0,0,1,1]`
  (`DEFAULT["ocr_box"]` aus `profiles.py`) ist, im **zurückgegebenen
  Editier-Zustand** (nicht in `self.config`!) stattdessen einen spürbar
  kleineren Startwert setzen, z. B. `[0.15, 0.15, 0.7, 0.7]` — reine
  Editor-Sitzungsgröße, nichts wird dadurch persistiert oder automatisch
  bestätigt. Verhindert deckungsgleiche Boxen direkt nach einer frischen
  `roi`-Bestätigung.

Kein Schema-/Migrationsaufwand, keine Persistenzänderung — beide Fixes sind
lokal, reversibel, ohne Seiteneffekt auf gespeicherte Profile.

## Stufe 2 — Automatische Vorschläge für `roi_quad` und `ocr_box`

### Bedienfluss (neu, Taste `R` im Editor)

1. Bediener drückt `R`, zieht ein grobes achsparalleles Rechteck um das
   Display (neuer, von der bestehenden Ecken-/Körper-Ziehlogik getrennter
   Interaktionsmodus in `workbench.js` — braucht ein eigenes `hinting`-Flag
   analog zu `drag`, damit `onpointerdown`/`onpointermove` nicht kollidieren).
2. Beim Loslassen: Client ruft `roi.suggest` mit dem Rechteck (normiert, im
   Rohbild-Koordinatensystem — `point(event)` liefert das beim eingefrorenen
   Vollbild bereits direkt, keine Homographie nötig) auf.
3. Liefert der Server ein Quad, ersetzt der Client `editing.quad` damit
   **und ruft sofort `ocr.suggest`** mit genau diesem Quad auf — ohne
   weiteren Bedienerklick, wie bestätigt.
4. Beide übernommenen Boxen werden bis zur ersten manuellen Berührung
   gestrichelt/transparent gezeichnet (neues `editing.roiSuggested` /
   `editing.ocrSuggested`-Flag, in `draw()` ausgewertet; Flag fällt weg,
   sobald `onpointerdown` diese Box anfasst).
5. Weiter wie bisher: frei nachziehen, `Strg+Enter` bestätigt, `Esc` verwirft
   — kein neuer Bestätigungsmechanismus.

Findet der Server nichts, bleibt `editing.quad`/`editing.ocr_box` unverändert
und eine Logzeile erklärt das ("kein Kandidat im markierten Bereich
gefunden") — ein Fehlschlag ist inert, nie eine schlechte Automatik-Übernahme.

### `roi_quad`-Vorschlag: `fit_quad_in_region`

**Neue Funktion in `src/dispread/workbench/vision.py`:**
`fit_quad_in_region(image, hint_box, config=DetectionConfig()) -> Quad | None`

1. `hint_box` (normiert `[x,y,w,h]`, Rohbild) um ~25 % aufweiten, an
   Bildgrenzen clippen — die Suche bleibt lokal (Bruchteil des Bildes), das
   macht sie robuster als `find_display_candidates`' Vollbildsuche.
2. Auf den aufgeweiteten Bereich zuschneiden, dieselbe Kanten-Pipeline wie
   `find_display_candidates` fahren (Graustufen → `GaussianBlur` → `Canny` →
   `morphologyEx(CLOSE)` → `findContours`), aber pro Kontur `cv2.minAreaRect`
   → `cv2.boxPoints` statt `cv2.boundingRect` — `roi_quad` muss ein echtes,
   auch rotiertes Viereck sein, keine achsparallele Box.
3. Eckenreihenfolge wie in `dispread.rectify._order_quad` (TL/TR/BR/BL nach
   Summe/Differenz) — bestehende Funktion wiederverwenden, nicht duplizieren.
4. Filtern/Bewerten wie `DetectionConfig` (Flächenanteil am aufgeweiteten
   Bereich, Seitenverhältnis, Rechteckigkeit); ist bereits ein Profil mit
   `layout` vorhanden, das erwartete Seitenverhältnis zusätzlich aus
   `DisplayLayout.n_cells` ableiten statt nur der festen `1.5..8.0`-Spanne.
5. Bestes Quad zurück in volle Bildkoordinaten übersetzen; `None` wenn kein
   Kandidat die Filter besteht. Nur Top-1 für diese Stufe.

### `ocr_box`-Vorschlag: `fit_ocr_box`

**Neue Funktion in `src/dispread/workbench/vision.py`:**
`fit_ocr_box(rectified_crop) -> tuple[float, float, float, float] | None`

Arbeitet auf dem bereits über `dispread.rectify.rectify(image, quad,
target_size=CROP_SIZE)` entzerrten 400×160-Ausschnitt (Controller ruft
`rectify()` genau wie in `_read()`/`publish()` schon, dann `fit_ocr_box` auf
`crop.image`):

1. Graustufen; Otsu-Schwellwert in beide Richtungen (hell-auf-dunkel für
   LED, dunkel-auf-hell für LCD), automatische Polaritätswahl über die
   Blob-Struktur aus Schritt 4 — kein neuer Bedienregler in dieser Stufe.
2. `morphologyEx(CLOSE)` (Segmentstriche einer Ziffer zu einem Blob
   verschmelzen) gefolgt von `morphologyEx(OPEN)` (einzelne Pixel/Reflexe
   entfernen).
3. `cv2.connectedComponentsWithStats`; Blobs nach Höhe filtern (zu klein →
   Staub/Dezimalpunkt/Einheitentext, zu groß → Gehäusekante), verbleibende
   Blobs nach vertikaler Mitte clustern, größtes Cluster nach Gesamtfläche
   behalten — das schließt Einheitentext und Blende aus, ohne sie explizit
   zu kennen.
4. Vereinigungsbox des behaltenen Clusters, kleiner Rand (~1-2 % der
   Cropgröße) gegen abgeschnittene Segmentspitzen, auf `[0,1]` clippen, als
   normierte `[x,y,w,h]` zurückgeben.
5. `None` bei zu wenig Evidenz (< 2 Blobs), degenerierter Fläche (< 5 % oder
   > 90 % der Cropfläche), oder — falls ein Layout vorliegt — grob
   unpassendem Seitenverhältnis gegenüber `DisplayLayout.cell_boxes()`.

### Validierung gegen echte Daten

Die zwei realen Annotationen aus dieser Sitzung
(`var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd/`,
`.../8a18ee05e31241b9b6702c5bb904ec97/`) enthalten `image.png` +
`roi_quad`/`ocr_box` in genau den Koordinatensystemen, die `fit_ocr_box`
braucht — neuer Test lädt beide, entzerrt mit dem gespeicherten `roi_quad`,
lässt `fit_ocr_box` laufen, vergleicht per IoU gegen den gespeicherten
`ocr_box`. Da `var/` per `.gitignore` nicht versioniert ist, muss der Test
`pytest.mark.skipif` greifen, wenn die Ordner fehlen (z. B. auf einem
frischen Checkout/CI). Die konkrete IoU-Schwelle wird an diesen zwei Bildern
gemessen und in `docs/VALIDATION.md` festgehalten, nicht vorab geraten.

### Controller-Anbindung

**Datei:** `src/dispread/workbench/controller.py`, zwei neue Ops nach
demselben Muster wie `freeze`/`roi` (synchron, innerhalb `self.lock`, kein
Hintergrund-Thread wie `auto.start` — hier reicht ein einzelner
OpenCV-Aufruf auf einem bereits eingefrorenen Bild):

- **`roi.suggest`** — Args `{id, hint_box}`. Holt `self.frames[id]["image"]`,
  ruft `fit_quad_in_region`, gibt `{"quad": [...]|None}` zurück. Verändert
  weder `self.config` noch `self.frames[id]`.
- **`ocr.suggest`** — Args `{id, quad}` (das *aktuelle, evtl. unbestätigte*
  Editor-Quad, explizit vom Client mitgeschickt — genau wie der bestehende
  `roi`-Op sein `quad` explizit bekommt statt aus `self.config` zu lesen).
  Rectifiziert `self.frames[id]["image"]` mit dem gegebenen Quad, ruft
  `fit_ocr_box`, gibt `{"ocr_box": [...]|None}` zurück.

Beide Ops sind reine Vorschlagsfunktionen ohne jede Persistenz — bestätigt
wird weiterhin ausschließlich über den unveränderten `roi`-Op bei
`Strg+Enter`.

## Stufe 3 — Ground-Truth-Eingabe im `annotate`-Modus

**Datei:** `src/dispread/workbench/controller.py`, `op == "roi"`,
`self.mode == "annotate"`-Zweig — vor dem Schreiben von `annotation.json`
einen kurzen, vom Client mitgeschickten getippten Anzeigewert
(`ground_truth_text`) als zusätzliches Feld übernehmen.

**Datei:** `src/dispread/workbench/static/workbench.js` — kleines
Text-Eingabefeld analog zum bestehenden `$('name-input')`/`setup-name`-Overlay
(Profil-Speichern-unter-Dialog), das beim Bestätigen im `annotate`-Modus
erscheint, bevor der `roi`-Befehl mit `ground_truth_text` abgeschickt wird.

Rein additiv — keine Schema-Version, keine `validate()`-Änderung, da
`annotation.json` nicht gegen `profiles.py::validate` geprüft wird. Macht
bestehende Geometriebeispiele zu (Bild, `roi_quad`, `ocr_box`, `layout`,
Ground Truth)-Tupeln, genug für einen späteren Trefferquote-Test gegen
`SevenSegmentReader` — ohne jede Trainingsinfrastruktur zu versprechen oder
zu bauen. Ein `device_id`-Feld für geräteweise Testsplits (Konzept §9,
ROADMAP P2) ist bewusst **nicht** Teil dieser Stufe.

## Dokumentationspflicht (`AGENTS.md`)

- `CHANGELOG.md`, oberster Abschnitt: alle drei Stufen, mit Problem/Änderung/
  Konsequenz wie bisher in dieser Sitzung gehandhabt.
- `docs/ROADMAP.md`: P0-Zeile "`contour_heuristic`- und
  `imx500_detector`-Lokalisierung, `RegionTracker`" bleibt unangetastet — die
  hier gebaute Kontursuche ist Workbench-Editorhilfe, nicht die
  Pipeline-`DisplayLocator`-Implementierung aus Kapitel 7; das im
  CHANGELOG-Eintrag explizit klarstellen, damit es nicht als Erledigung
  dieser Roadmap-Zeile missverstanden wird.
- `docs/open-questions.md`: neuer kurzer OQ-Eintrag für die
  Vorschlagsqualität von `fit_quad_in_region`/`fit_ocr_box` an realen
  Geräten (Vorabdefault-Filterwerte, wie bei `DetectionConfig` schon üblich),
  mit Verweis auf die IoU-Messung in `VALIDATION.md`.

## Verifikation

- `./.venv/bin/pytest -q` und `./.venv/bin/ruff check src tests examples`
  müssen grün bleiben; neue Tests für `fit_quad_in_region` (synthetische
  Quelle mit `?perspective=…`, analog zum Testmuster aus
  `docs/anleitung/07-lokalisierung.md`) und `fit_ocr_box` (synthetisch **und**
  gegen die zwei realen `var/workbench/annotations/*`-Beispiele, dort
  `skipif` bei fehlendem Ordner).
- `node --check src/dispread/workbench/static/workbench.js`.
- Manuelle Bedienprüfung im echten Browser (Windows, siehe OQ-21/OQ-24):
  Klickpriorität an eng benachbarten Ecken, `R`-Vorschlagsfluss an einem
  echten Gerät, gestrichelte Vorschlagsdarstellung, `annotate`-Eingabefeld.
  Nicht aus `file://`- oder synthetischen Tests ableitbar.
