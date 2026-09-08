# 7 — Lokalisierung ohne Bediener

**Ziel:** `contour_heuristic` findet den Anzeigebereich im Bild selbst, ein
`RegionTracker` verfolgt ihn über Frames — und wenn er verloren geht, wird der
Wert ungültig statt weiterzulaufen.

**Warum jetzt:** Nicht, um den Bediener zu ersetzen. Der bestätigte ROI-Pfad
bleibt Primärpfad (`manual_roi`), weil er ohne Modell und ohne Datensatz
funktioniert. Die Heuristik hat zwei andere Zwecke: sie **schlägt** dem
Bediener eine ROI vor (das macht `dispread roi` erst brauchbar), und der
Tracker **merkt**, wenn Kamera oder Gerät verrutschen. Letzteres ist eine
Anforderung aus Konzept §4: geht die Anzeige verloren, muss der Wert ungültig
werden. Hakt die ROADMAP-Zeile „`contour_heuristic`- und
`imx500_detector`-Lokalisierung, `RegionTracker`" an.

**Vorbedingungen:** [Kapitel 4](04-geraeteprofile.md). Tests laufen ohne
Hardware (synthetische Quelle mit Perspektivverzerrung).

## Der Vertrag

```python
def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]: ...
@property
def locator_id(self) -> str: ...
```

`DisplayCandidate`: `quad` (4 Punkte, im Uhrzeigersinn ab oben links), `score`,
`locator_id`, `locator_version`, `role_hint`.

Drei Dinge, die dabei zählen mehr als die Trefferquote:

1. **Nichts gefunden ist ein gültiges Ergebnis.** Leeres Tupel. Die Pipeline
   macht daraus `UNREADABLE` mit `display_not_located`. Ein „bester Rateversuch"
   wäre der Anfang stiller Fehlablesungen.
2. **`role_hint` ist Pflicht.** Konzept §7 nennt die Verwechslung von Haupt-
   und Nebenanzeige als kritischen Fehler. Viele Messverstärker zeigen zwei
   Zahlen. Wenn du nicht entscheiden kannst, welche die Hauptanzeige ist, ist
   `None` ehrlicher als eine Vermutung — und das Gate muss es ablehnen.
3. **`score` muss über Frames vergleichbar sein.** Sonst kann der Tracker
   nicht entscheiden, ob eine neue Lokalisierung besser ist als die alte.
   Definiere ihn explizit (z. B. gewichtete Summe aus Fläche-Plausibilität,
   Seitenverhältnis-Treffer und Rechteckigkeit, normiert auf 0..1) und
   dokumentiere die Definition im Docstring.

## Teil A — `contour_heuristic`

`src/dispread/detect/contour_heuristic.py`. Verfahren, Schritt für Schritt:

```
Graustufen
  → leichte Glättung (GaussianBlur), damit Rauschen keine Konturen erzeugt
  → Kanten oder Schwelle:
       Variante 1  cv2.Canny + cv2.morphologyEx(CLOSE)  – gut bei Rahmen
       Variante 2  cv2.adaptiveThreshold                – gut bei dunklem Panel
  → cv2.findContours(RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)
  → filtern: Fläche, Seitenverhältnis, Solidität (Fläche/Hüllfläche)
  → cv2.minAreaRect → cv2.boxPoints → Quad
  → Score berechnen, absteigend sortieren, zurückgeben
```

Die Filter sind der eigentliche Inhalt. Beziehe sie **aus dem Profil**, nicht
aus Zahlen im Code:

* Erwartetes Seitenverhältnis: aus `DisplayLayout.n_cells` (fünf Stellen plus
  Vorzeichen sind breiter als drei Stellen).
* Erwartete Fläche: aus dem bestätigten Profil, wenn es eines gibt — dann ist
  die Heuristik nur noch Nachführung und kein Suchproblem.
* Ohne Profil (Erstbestätigung): weiter Bereich, mehrere Kandidaten
  zurückgeben und den Menschen wählen lassen.

### Test zuerst

Die synthetische Quelle liefert dir Wahrheit und Verzerrung gratis:
`raw_metadata["digit_area"]` ist der gezeichnete Ziffernbereich, und
`?perspective=…` verzerrt so, dass die achsparallele Box nicht mehr exakt
passt — genau der Fall, den die Lokalisierung wiederfinden soll.

```python
def _iou(a_quad, b_box) -> float:
    """Flaechenueberlappung von Quad und Box, als Maske gerechnet."""
    # cv2.fillPoly auf zwei uint8-Masken, dann logisches Und/Oder zaehlen.
    ...


def test_findet_die_anzeige_ohne_verzerrung() -> None:
    src = open_source("synthetic://seven-seg?count=1")
    src.open()
    frame = next(iter(src.frames()))
    kandidaten = ContourHeuristicLocator().locate(frame)
    assert kandidaten
    assert _iou(kandidaten[0].quad, frame.raw_metadata["digit_area"]) > 0.7


def test_leeres_bild_liefert_keinen_kandidaten() -> None:
    frame = _frame_aus(np.zeros((200, 480, 3), np.uint8))
    assert ContourHeuristicLocator().locate(frame) == ()


def test_score_ist_normiert() -> None:
    ...   # 0 <= score <= 1 fuer alle Kandidaten
```

Der zweite Test ist der wichtigere. Eine Heuristik, die auf einem schwarzen
Bild irgendetwas findet, findet auch bei abgedeckter Kamera „eine Anzeige".

Danach die Härteprüfung über Parameter statt neuer Testfälle:
`?perspective=3&glare=0.4&blur=1.0` — und notiere, ab welchem Wert die
IoU unter 0,7 fällt. Diese Zahl gehört in
[../VALIDATION.md](../VALIDATION.md), sonst ist sie in einer Woche vergessen.

## Teil B — `RegionTracker`

`TrackResult` ist schon definiert (`detect/__init__.py`):

```python
@dataclass(frozen=True, slots=True)
class TrackResult:
    candidate: DisplayCandidate | None
    lost: bool                      # True ⇒ Wert muss ungueltig werden
    relocalize_needed: bool = False
```

Aufgabe des Trackers:

* Kandidat halten, solange er plausibel bleibt.
* Bewegt sich das Quad um mehr als eine Toleranz (z. B. 2 % der Bildbreite),
  `relocalize_needed=True` setzen.
* Fällt der Score unter eine Schwelle oder findet die Lokalisierung *n* Frames
  hintereinander nichts, `lost=True`.
* **Nie glätten.** Kein Mittelwert über die letzten Quads, der eine tatsächlich
  verrutschte Anzeige „stabil" aussehen lässt. Bewegung ist ein Befund.

### Anschluss an die Pipeline

`Pipeline.process()` hält heute selbst einen Kandidaten und lokalisiert nur
jeden `locate_every`-ten Frame:

```python
if self._candidate is None or self._frames_since_locate >= self.config.locate_every:
    candidates = self.locator.locate(frame)
    self._candidate = candidates[0] if candidates else None
    self._frames_since_locate = 0
else:
    self._frames_since_locate += 1
```

Minimaler Umbau: einen optionalen Tracker in den Konstruktor, und aus
`lost=True` denselben Weg nehmen, den `self._candidate is None` schon geht —
`UNREADABLE` mit `display_not_located` (oder einem neuen Grund
`display_lost`). Achte darauf:

* **Kein zusätzlicher Pfad, auf dem ein alter Kandidat weiterläuft.** Genau
  dort entstehen unmarkierte Altwerte.
* `PipelineTrace.t_locate_done_ns` weiter setzen, auch wenn nicht lokalisiert
  wurde — sonst fehlen Marken in der Latenzauswertung.
* Neuer `reject_reason` heißt: `docs/` und die Liste in
  [Kapitel 2](02-vertraege.md) nachziehen.
* Ein Test, der belegt: Anzeige verschwindet mitten im Lauf ⇒ **kein**
  `VALID`-Datensatz danach, und der letzte Wert wird nicht wiederholt.

## Fallen

* **Reflexionen erzeugen Konturen.** Ein Glanzfleck hat schöne Kanten und
  plausible Fläche. Deshalb gehört die Sättigungsprüfung
  (`DisplayCrop.saturated_fraction`, `glare`-Flag) in die Kette und nicht in
  die Heuristik — aber die Heuristik darf sich davon nicht anziehen lassen.
* **`rectify._order_quad()` sortiert über Summe und Differenz der
  Koordinaten.** Das ist für leicht gekippte Rechtecke richtig und für stark
  rotierte (~45°) nicht mehr eindeutig. Wenn deine Heuristik solche Quads
  liefert, liefere sie **schon sortiert** — oder erweitere `_order_quad` und
  belege die Erweiterung mit einem Test.
* **`cv2.boxPoints` liefert `float32` in eigener Reihenfolge.** Auf das
  Projektformat bringen: Tupel von vier `(float, float)`, im Uhrzeigersinn ab
  oben links.
* **Zwei Anzeigen im Bild.** Genau der kritische Fall aus §7. Wenn Fläche und
  Seitenverhältnis beider Kandidaten ähnlich sind, entscheidet die Position aus
  dem Profil — und wenn es kein Profil gibt, entscheidet der Mensch.
* **Nicht die bestätigte ROI „verbessern".** Findet die Heuristik im Betrieb
  ein besseres Quad als das Profil, ist das ein **Vorschlag**, kein Ersatz. Die
  Bestätigung ist der Akt eines Menschen (Konzept §4,
  [OQ-05](../open-questions.md)).
* **Kein `imx500_detector` als Abkürzung.** Die Stock-Modelle liefern
  COCO-Labels (`person`, `tv`) — für Messverstärker-Displays unbrauchbar.

## Fertig, wenn

* [ ] `contour_heuristic` findet die synthetische Anzeige mit IoU > 0,7,
      liefert bei leerem Bild `()` und hat einen dokumentierten `score`
* [ ] `RegionTracker` setzt `lost=True`, und die Pipeline macht daraus einen
      abgelehnten Datensatz — mit Test
* [ ] Grenzwerte (ab welcher Verzerrung/Glanzstärke die Erkennung kippt) in
      [../VALIDATION.md](../VALIDATION.md)
* [ ] `manual_roi` ist weiterhin der Default; die Umstellung erfordert eine
      bewusste Entscheidung, keine Konfigurationsänderung
* [ ] `CHANGELOG.md`, ROADMAP, ggf. neuer `OQ-nn`

Weiter mit [Kapitel 8 — Weitere OCR-Backends](08-ocr-backends.md).
