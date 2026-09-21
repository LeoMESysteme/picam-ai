# Design: `tesseract_cli` OCR-Backend für dot-matrix-Anzeigen (GSV-Sensor)

**Stand 2026-09-21.** Ausgangspunkt: das neu angelegte Gerät „GSV"
(`family=GSV_Sensor`, `technology=LCD`) ist eine dot-matrix-Zeichen-LCD
(HD44780-artig, z. B. `+1.05000 mV/V`), keine 7-Segment-Anzeige. Der
bestehende `sevenseg`-Leser kann sie strukturell nicht lesen — nicht wegen
falscher Geometrie/Kalibrierung, sondern weil `DIGIT_SEGMENTS` Balkenmuster
kennt, keine Punktraster-Glyphen, und weil Buchstaben (`m`, `V`, `/`) gar
nicht im Alphabet vorkommen. `tesseract-ocr` 5.5.0 ist auf dem Pi bereits
installiert (OQ-15s Installationsblocker ist damit erledigt, der Eintrag war
nur nicht aktualisiert).

Umfang laut Nutzerentscheidung: **volle Live-Workbench-Integration**
(Profilschema, `Controller`-Verdrahtung, UI), nicht nur ein isoliertes
Backend-Modul.

## Architekturüberblick

Neues Modul `src/dispread/ocr/tesseract_cli.py` implementiert dieselbe
`ValueReader`-Schnittstelle (`read(crop, layout) -> ReadResult`) wie
`sevenseg.py` — keine Schnittstellenänderung nötig.
`DisplayLayout.digits`/`decimals`/`has_sign`/`unit`/`polarity` werden als
bestätigtes Zahlenformat wiederverwendet (dieselbe Bedeutung wie bei
`sevenseg`); die segment-spezifischen Felder (`sign_cell_ratio`,
`thickness_ratio`, `inset_ratio`, `digit_gap_ratio`, `cell_boxes()`) bleiben
ungenutzt — sie sind reine `sevenseg`-Geometrie und für einen
Zeichen-OCR-Leser bedeutungslos.

```
Controller._read()
  └─ self._reader_for(config["backend"]).read(reader_crop, layout)
       ├─ backend="sevenseg"      -> SevenSegmentReader (unverändert)
       └─ backend="tesseract_cli" -> TesseractReader (neu)
```

## 1. `TesseractReader.read()` — Ablauf

1. **Vorverarbeitung** (auf dem übergebenen `crop`, bereits durch den
   bestätigten `ocr_box` zugeschnitten — keine eigene Geometrie-Heuristik,
   der Bediener bestätigt den Rahmen wie bei `sevenseg`):
   - Graustufen.
   - Polarität normieren: `layout.polarity == "bright_on_dark"` (LED-Default)
     → invertieren, damit dunkler Text auf hellem Grund entsteht (das
     erwartet Tesseract). `dark_on_bright` (LCD) bleibt unverändert.
   - Hochskalieren (kleine Ausschnitte erkennt Tesseract schlecht) auf eine
     Mindesthöhe, z. B. 120 px — ein dokumentierter Vorabdefault, wie
     `sevenseg._MIN_CONTRAST` einer ist, keine an mehreren Geräten validierte
     Grenze.
2. **Zeichen-Whitelist aus dem bestätigten Profil bauen** (nie geraten):
   Ziffern `0-9`, `.` immer; `+`/`-` wenn `has_sign`; die Zeichen aus
   `layout.unit` (falls gesetzt) plus Leerzeichen. Beispiel für das
   GSV-Profil (`unit="mV/V"`, `has_sign=True`): `0123456789.+-mV/ `.
3. **`tesseract` als Subprozess aufrufen**, TSV-Ausgabemodus (liefert Text
   **und** Wortkonfidenz in einem Aufruf, kein zweiter Aufruf für Konfidenz
   nötig): `--psm 7` (eine Textzeile — passt zur Annahme, dass `ocr_box`
   genau eine Ausgabezeile umschließt, analog zur bestätigten ROI bei
   `sevenseg`), `-c tessedit_char_whitelist=<Schritt 2>`.
4. **Parsen + Formatprüfung** (die eigentliche „ablehnen statt raten"-Stelle):
   TSV-Zeilen zu einer Textzeile zusammensetzen, gegen ein aus
   `layout.digits`/`decimals`/`has_sign` gebautes Muster prüfen (analog
   `parse_expected`/`decimal_point_index()` — die Position des Punkts kommt
   aus dem Profil, nicht aus dem gelesenen Text, exakt wie bei `sevenseg`
   und mit derselben bekannten Grenze, OQ-17). Passt die erkannte
   Ziffernfolge nicht in `digits` Stellen, oder ist ein erwartetes
   Vorzeichenzeichen weder `+` noch `-` noch eindeutig lesbar → **ablehnen**
   (`value=None`), nie auf die nächstliegende Interpretation raten.
5. **Konfidenzschwelle** als zweites, unabhängiges Ablehnungskriterium:
   unterhalb eines dokumentierten Vorabdefaults (z. B. Wortkonfidenz < 60)
   wird abgelehnt, selbst wenn das Muster zufällig passt.
6. **`ReadResult` bauen:**
   - `raw_text`: exakt wie erkannt (inkl. Vorzeichen/Punkt).
   - `sign_detected`: `True` nur bei explizit erkanntem `-`. Ein `+` zählt
     wie überall im Projekt als „kein Minus" (siehe
     `benchmark.normalise`/`autofit.parse_expected`).
   - `sign_region_readable`: `False`, wenn `has_sign` gesetzt ist, aber im
     erkannten Text **gar kein** Vorzeichenzeichen auftaucht (nicht auf
     „positiv" raten — Konzept.md §7).
   - `decimal_point_detected`: `True` (Position kommt aus dem Profil, wie
     bei `sevenseg` — bekannte, bereits dokumentierte Grenze aus OQ-17).
   - `unit_text`: `layout.unit`, `diagnostics["unit_source"]="profile"` —
     nicht gemessen, exakt wie bei `sevenseg` (kein neuer Anspruch).
   - `glyphs`: ein `GlyphEvidence` je Ziffernstelle, `text=<erkanntes
     Zeichen>`, `confidence=<Wortkonfidenz, gleichmäßig auf alle Stellen
     angewandt>`, `segments=None` (keine Segment-Evidenz — **ehrlich als
     Grenze dokumentiert**: gröber als `sevenseg`s echte
     Pro-Segment-Unabhängigkeit, nicht verschleiert).
   - `backend_id="tesseract_cli"`, `backend_version=<tesseract --version>`.
   - `declares_confidence_calibrated`: `False` (wie bei `sevenseg` — keine
     Kalibriermessung gegen echte Fehlerraten, Konzept.md §7).

## 2. Profilschema

`src/dispread/workbench/profiles.py`:
- `DEFAULT["backend"] = "sevenseg"`, `schema_version` 3 → 4.
- Migration: fehlt `backend` in einem geladenen Profil (Schema < 4), wird es
  auf `"sevenseg"` gesetzt — reproduziert exakt das bisherige Verhalten,
  keine Vermutung über die tatsächliche Anzeige (gleiches Muster wie die
  bestehenden `digit_gap_ratio`-Nachrüstung).
- `validate()`: `backend in ("sevenseg", "tesseract_cli")`, sonst
  `ValueError`.

## 3. `Controller`-Verdrahtung

- `self.reader` (fest instanziiert in `__init__`) wird durch
  `self._reader_for(backend: str) -> ValueReader` ersetzt — ein kleiner,
  je-Backend gecachter Dict-Lookup (`SevenSegmentReader`/`TesseractReader`
  sind zustandslos genug für Wiederverwendung über mehrere Reads).
- Die drei bisherigen `self.reader.read(...)`-Aufrufstellen (`_read`,
  `_autofit`-Preview) verwenden stattdessen
  `self._reader_for(config["backend"]).read(...)`.
- `layout.autofit` (`_autofit`): wenn `config["backend"] ==
  "tesseract_cli"`, **sofort ablehnen** mit einer erklärenden Meldung („nicht
  anwendbar für dieses Backend - die gesuchten Glyphenverhältnisse
  existieren nur bei sevenseg") statt eine bedeutungslose Segment-Suche
  laufen zu lassen.
- `ocr.suggest` (`_suggest_ocr_box`, `fit_ocr_box`-Blobsuche) bleibt für
  beide Backends aktiv — reine Geometrie, kein Segmentwissen nötig. Bekannte,
  unvalidierte Grenze: die Blobhöhen-/Flächenfilter wurden nie gegen eine
  dot-matrix-Anzeige geprüft; kann in der Praxis schlechter vorschlagen als
  bei 7-Segment-Displays. Wird dokumentiert, nicht vorab "gefixt" ohne
  Messung.

## 4. UI

`static/index.html`/`static/dataset.js`/`workbench.js`/`fields.py`: neues
Auswahlfeld „Leser-Backend" (sevenseg/tesseract_cli) im Profil-/Layout-Editor,
analog zum bestehenden `polarity`-Feld (`fields.py:162` ff.). Bei
`tesseract_cli` wird der Autofit-Knopf ausgeblendet oder als „nicht
anwendbar" markiert (Backend-Anzeige, kein neuer Serverzustand). Die
Live-Vorschau zeigt weiterhin `raw_text`/`value`/`status_flags`; die
segment-spezifischen Felder (`segments`, `min_margin`, `contrast`) bleiben
für `tesseract_cli`-Reads leer/`0` — ehrlich (nichts zu zeigen), nicht
kaputt.

## 5. Tests

- `tests/test_tesseract_reader.py` (neu): gegen die 3 echten GSV-Rohbilder
  (`var/workbench/datasets/samples/{id}/image.png`, mit dem gespeicherten
  `bbox` zugeschnitten) — erwartet `value == 1.05` bei mindestens einer der
  drei Aufnahmen (frontal, beste Bildqualität); die anderen dürfen ablehnen,
  aber nicht falsch lesen. Adversariale Fälle: leerer/grauer Ausschnitt →
  `value is None`; Ziffernzahl-Mismatch (Whitelist erzwingt ein anderes
  `digits` als tatsächlich im Bild steht) → Ablehnung, kein Rateergebnis.
  Übersprungen (`pytest.mark.skipif`), falls `tesseract`-Binary fehlt —
  gleiches Muster wie `test_dataset_export.py`s Skip bei fehlendem
  Experiment-Worktree.
- `tests/test_profiles.py` (falls vorhanden, sonst wo `validate()` bereits
  getestet wird): Migration alter Profile ohne `backend`-Feld,
  `validate()` lehnt unbekannte Backend-Werte ab.
- `tests/test_workbench.py`/`tests/test_controller*.py`: Backend-Wechsel im
  Profil ändert tatsächlich, welcher Reader antwortet (Mock/Fake-Reader oder
  Vergleich `backend_id` im Ergebnis); `layout.autofit` lehnt bei
  `backend=tesseract_cli` ab, ohne eine Segment-Suche zu starten.

## Bewusst nicht Teil dieses Entwurfs

- Kein neuer synthetischer Generator für dot-matrix-Bilder — es gibt echte
  GSV-Fotos, ein synthetischer Ersatz wäre zusätzlicher Aufwand ohne klaren
  Nutzen gegenüber echten Bildern für dieses eine Gerät.
- Keine automatische `ocr_box`-Nachjustierung für `tesseract_cli` (kein
  Analogon zu `fit_layout`s Rahmen-Feintuning) — der bestätigte Rahmen wird
  unverändert übernommen, wie es die Primärpfad-Philosophie
  (`manual_roi`) ohnehin verlangt.
- Keine echte Pro-Zeichen-Konfidenz (nur Pro-Wort, gleichmäßig verteilt) —
  dokumentierte Grenze, kein Bauprojekt für ein LSTM-internes Scoring.
