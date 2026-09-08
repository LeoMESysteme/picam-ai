# 1 — Die Kette verstehen

**Ziel:** Du kannst einen einzelnen Frame von Hand durch alle sechs Stufen
schieben und für jede Zwischengröße sagen, wer sie erzeugt hat und was sie
bedeutet. Kein neuer Code, aber Übungen.

**Vorbedingungen:** [Kapitel 0](00-werkzeuge.md).

## Erst laufen lassen

```bash
./.venv/bin/python examples/16_end_to_end_headless.py
```

Ausgabe (gekürzt, so sah sie am 2026-09-08 aus):

```
Quelle:      synthetic://seven-seg?digits=5&decimals=2&unit=N&count=40&…
Zeitbasis:   synthetic  (traegt Zeitaussage: False)
Frames:      40
Status:      {'valid': 40}
korrekt:     40
abgelehnt:   0
STILL FALSCH:0   <- als gueltig ausgegeben, aber falsch
Telegramme:  40 auf der Leitung  (Format ascii_csv/provisional, provisorisch)
  erstes: 1;1;-12.500;N;valid;3371298733296;synthetic
```

Fünf Dinge, die man daran ablesen muss:

1. **`traegt Zeitaussage: False`** — die Quelle ist synthetisch. Die weiter
   unten gezeigten Latenzen sind Verarbeitungszeiten der Software, **keine**
   Aussage über die reale Kette von der Anzeige bis zum Telegramm.
2. **`STILL FALSCH`** ist die einzige Zahl, die den Lauf fehlschlagen lässt.
   `abgelehnt` ist kein Fehler — Ablehnen ist die erlaubte Richtung.
3. **`provisorisch`** klebt am Formatnamen. Das Telegramm ist erfunden und
   nicht das GSVmulti-Format ([OQ-07](../open-questions.md)).
4. Im Telegramm steht hinter dem Zeitstempel die **Zeitbasis** (`synthetic`).
   Eine Zeit ohne Basis wäre laut Konzept §6 keine verwertbare Angabe.
5. Die Artefakte unter `var/examples/16_end_to_end/` (`values.jsonl`,
   `telegrams.txt`, `report.json`) sind der Nachweis, nicht die Konsolenausgabe.

Schau in `report.json` nach `timing_is_meaningful` und in `values.jsonl` in die
erste Zeile — das ist ein vollständiger `ValueRecord`.

## Die sechs Stufen und wo sie wohnen

```
             Datei                                     erzeugt
  ─────────────────────────────────────────────────────────────────────────
1 frames/synthetic_source.py    Bildquelle             Frame
2 detect/manual_roi.py          Anzeige finden         DisplayCandidate
3 rectify.py                    Entzerren              DisplayCrop
4 ocr/sevenseg.py               Wert lesen             ReadResult
5 validate.py                   Freigabe               GateDecision
6 sink/jsonl.py, sink/serial_out.py  Ausgabe           TxReceipt
  ─────────────────────────────────────────────────────────────────────────
  pipeline.py verdrahtet 1–6 und baut aus 4 + 5 den ValueRecord
```

**Lesereihenfolge des Codes** (so ist es am schnellsten verständlich):

1. `src/dispread/records.py` — `Timestamp`, `ValueStatus`, `ValueRecord`. Der
   ganze Rest existiert, um dieses Objekt korrekt zu füllen.
2. `src/dispread/frames/types.py` — `Frame`, insbesondere `is_time_bearing`.
3. `src/dispread/frames/__init__.py` — das `FrameSource`-Protokoll und die
   URI-Registry. Beachte die *lazy imports* in den `_open_*`-Funktionen.
4. `src/dispread/layout.py` — das Ziffernraster. Ohne das liest der Dekoder
   „irgendwie" statt gegen ein bestätigtes Format.
5. `src/dispread/ocr/sevenseg.py` — vor allem `segment_threshold()`. Der
   Docstring erklärt zwei Fehlversuche und warum die Schwelle über *alle*
   Segmentmessungen gepoolt wird.
6. `src/dispread/validate.py` — jede Regel des Gates ist eigenständig
   ablehnbar: Vorzeichen, Dezimalpunkt, Einheit, Kontrast, Marge, Zustand.
7. `src/dispread/pipeline.py` — dünn. Sie entscheidet fast nichts selbst.

## Ein Frame zu Fuß

Das ist die Übung, die am meisten trägt. Schreibe das Folgende in
`var/scratch.py` (nicht versioniert) und lass es laufen — Zeile für Zeile,
nicht als Blackbox:

```python
from dispread.frames import open_source
from dispread.detect.manual_roi import ManualRoiLocator, quad_from_box
from dispread.rectify import rectify
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.validate import GateConfig, ReleaseGate

src = open_source("synthetic://seven-seg?digits=5&decimals=2&unit=N&count=3")
src.open()
frame = next(iter(src.frames()))
print("Frame   ", frame.frame_sequence, frame.size, frame.timebase, frame.is_time_bearing)
print("Wahrheit", frame.raw_metadata["ground_truth"])

x, y, w, h = frame.raw_metadata["digit_area"]           # im Betrieb: aus dem Profil
cand = ManualRoiLocator(quad_from_box(x, y, w, h), role_hint="main").locate(frame)[0]
print("ROI     ", cand.quad, cand.locator_id, cand.score)

crop = rectify(frame.image, cand.quad, target_size=(400, 160))
print("Crop    ", crop.image.shape, round(crop.sharpness, 1), crop.exposure_ok)

read = SevenSegmentReader().read(crop.image, src.layout)   # src.layout: nur die synthetische Quelle hat das
print("Lesung  ", repr(read.raw_text), read.value, "Vorzeichen:", read.sign_detected,
      "| lesbar:", read.sign_region_readable, "| dp:", read.decimal_point_detected)
print("Glyphen ", [(g.text, round(g.margin, 2)) for g in read.glyphs])
print("Diag    ", read.diagnostics)

gate = ReleaseGate(GateConfig(expected_unit="N"))
d = gate.evaluate(read, frame.capture_timestamp.value_ns)
print("Freigabe", d.status.value, d.reject_reasons, round(d.confidence, 3))
src.close()
```

Erwartete Ausgabe (gemessen):

```
Frame    1 (480, 200) synthetic False
Wahrheit {'value': -12.5, 'unit': 'N', 'text': '-12.50'}
ROI      ((19.0, 20.0), (461.0, 20.0), (461.0, 136.0), (19.0, 136.0)) manual_roi 1.0
Crop     (160, 400, 3) 375.7 True
Lesung   '-012.50' -12.5 Vorzeichen: True | lesbar: True | dp: True
Glyphen  [('0', 0.71), ('1', 0.71), ('2', 0.78), ('5', 0.8), ('0', 0.71)]
Diag     {'unreadable_cells': 0, 'min_margin': 0.711, 'contrast': 0.256, …, 'unit_source': 'profile'}
Freigabe valid () 0.711
```

Was hier zu bemerken ist:

* `raw_text` ist `'-012.50'` — **exakt wie gelesen**, mit führender Null. Der
  Zahlenwert daneben ist die Interpretation. Beides wird getrennt geführt, weil
  sonst nicht mehr rekonstruierbar ist, was auf der Anzeige stand.
* `margin` pro Ziffer ist der Abstand der knappsten Segmentmessung zur
  Schwelle. Das ist die **erklärbare Evidenz**, die dem Gate erlaubt, „knapp
  entschieden" von „klar" zu unterscheiden. Eine generische OCR liefert das
  nicht — siehe [Kapitel 8](08-ocr-backends.md).
* `unit_source: 'profile'` — die Einheit wurde **nicht gelesen**, sie kommt aus
  dem Layout. Dasselbe gilt für den Dezimalpunkt
  ([OQ-17](../open-questions.md)). Wer das übersieht, hält eine
  Profilannahme für eine Messung.
* `d.confidence` ist die Marge, **keine** Fehlerwahrscheinlichkeit.

## Übungen

Jede Übung ist eine Änderung an `var/scratch.py` oder ein Beispielaufruf mit
anderen Parametern. Notiere jeweils, *welche* Ablehnungsgründe erscheinen.

1. **Glanz erzwingen.**
   `./.venv/bin/python examples/16_end_to_end_headless.py --glare 0.9`
   Gemessen: `{'unreadable': 35, 'valid': 5}`, davon **2 still falsch** — der
   Lauf endet mit Exit-Code 1. Das reproduziert den Befund aus
   [../VALIDATION.md](../VALIDATION.md). Suche die beiden Datensätze in
   `values.jsonl` (`status == "valid"`, aber `value` weicht ab) und schau dir
   ihre `min_margin` an. Merksatz: das `glare`-Flag fängt den Großteil, aber
   **nicht alles** — der optische Aufbau ist die eigentliche Gegenmaßnahme
   ([../OPTICAL_SETUP.md](../OPTICAL_SETUP.md)).
2. **Mehrbildbestätigung.** `--confirm-frames 3`. Gemessen:
   `{'transition': 37, 'valid': 3}`. Warum so wenige `valid`? Weil die
   synthetische Wertfolge ständig springt und jeder neue Wert die Bestätigung
   zurücksetzt. Was kostet die Bestätigung an Zeit? Steht als
   `confirmation_span_ns` im Record — und muss laut Konzept §7 im Zeitbezug
   berücksichtigt werden.
3. **Einheit falsch erwarten.** Im Skript `GateConfig(expected_unit="kg")`.
   Erwartung: `unit_mismatch:N`, Status nicht `valid` — die Einheit ist ein
   eigenständiges Kriterium, kein Kosmetikfeld.
4. **Invariante brechen.** Versuche in einem Python-Einzeiler, einen
   `ValueRecord` mit `status=ValueStatus.STALE` und `value=1.0` zu bauen.
   Erwartung: `ValueError`. Lies die Meldung — das ist Konzept §7 als Code.
5. **Vorzeichen unlesbar.** Setze `read.sign_region_readable` künstlich auf
   `False` (neues `ReadResult` per `dataclasses.replace`). Erwartung:
   `sign_region_unreadable`, **nicht** stillschweigend „positiv".
6. **Ziffer unbekannt.** Nimm ein Segmentmuster, das in keiner Tabelle steht
   (`layout.py`, `DIGIT_SEGMENTS`). Erwartung: Glyphe `'?'`,
   `ambiguous_with` nennt die nächstliegenden Kandidaten, `value is None`.

## Fertig, wenn du diese Fragen beantworten kannst

* Wer setzt `capture_timestamp`, und wer darf ihn ändern? (Antwort:
  `FrameSource`; niemand — insbesondere kein Ausgabeadapter.)
* Warum ist `TxReceipt` vom `ValueRecord` getrennt?
* Was ist der Unterschied zwischen `UNREADABLE` und `STALE`?
* Warum bekommt `ValueReader.read()` das Layout, aber nie den Referenzwert?
* Warum ist `rectify(..., apply_enhance=False)` der Default?
* Warum poolt `segment_threshold()` über alle Ziffernstellen statt pro Zelle?

Weiter mit [Kapitel 2 — Die Verträge](02-vertraege.md) als Nachschlagewerk oder
direkt zum ersten eigenen Modul in
[Kapitel 3](03-erste-bildquelle-folder.md).
