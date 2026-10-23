# 2 — Die Verträge (Nachschlagewerk)

Alle [Trennstellen](glossar.md#trennstelle) und Datenklassen auf einer Seite. Nicht zum Durchlesen,
sondern zum Danebenlegen, während du ein neues Modul schreibst.

Für den ersten Durchlauf empfiehlt sich [Kapitel 1](01-kette-verstehen.md):
es zeigt, wie die sechs Stufen zusammenspielen. Hier stehen ihre konkreten
Schnittstellen und die Regeln für Daten, die zwischen ihnen weitergegeben
werden.

Quelle der Wahrheit bleibt der Code — bei Abweichung gilt der Code, und diese
Seite ist zu korrigieren.

## Die sechs Trennstellen

Fünf Trennstellen sind `typing.Protocol` mit `@runtime_checkable`. Du erbst
**nicht** von ihnen; du schreibst eine Klasse mit den passenden Methoden.
Der Test prüft zum Beispiel `isinstance(meine_klasse, FrameSource)`. Die
Freigabe ist die sechste Trennstelle und wird durch die konkrete Klasse
`ReleaseGate` umgesetzt.

### `FrameSource` — `src/dispread/frames/__init__.py`

```python
def open(self) -> None: ...
def close(self) -> None: ...
def frames(self) -> Iterator[Frame]: ...
@property
def source_id(self) -> str: ...
@property
def capabilities(self) -> frozenset[Capability]: ...
def describe(self) -> dict[str, Any]: ...      # wandert ins Runartefakt
```

`Capability`: `LIVE`, `INFERENCE`, `SEEK`, `EXPOSURE_CONTROL`. Das ist der
einzige Ort, an dem die Pipeline Unterschiede zwischen Quellen bemerken darf.

### `DisplayLocator` — `src/dispread/detect/__init__.py`

```python
def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]: ...
@property
def locator_id(self) -> str: ...
```

Leeres Tupel ist ein legitimes Ergebnis und bedeutet „nicht gefunden" — die
Pipeline macht daraus `UNREADABLE` mit Grund `display_not_located`.

### `ValueReader` — `src/dispread/ocr/__init__.py`

```python
def read(
    self, crop: np.ndarray, layout: DisplayLayout | CharLayout,
) -> ReadResult: ...  # (1)!
@property
def backend_id(self) -> str: ...
@property
def declares_confidence_calibrated(self) -> bool: ...   # False, solange unbelegt
```

1. Die Signatur lässt keinen Referenzwert zu. Der Leser verarbeitet nur den
   Bildausschnitt und das bestätigte Layout; die Referenz bleibt außerhalb
   dieses Erkennungspfads.

`DisplayLayout` beschreibt die Siebensegment-Geometrie; `CharLayout` das
bestätigte Punktraster für `DotMatrixReader`. Der Leser bekommt **nur**
Bildausschnitt und bestätigtes Layout. Kein Referenzwert, keine
Historie, kein letzter Wert. Diese Signatur ist der strukturelle Schutz gegen
die verbotene Korrektur aus Konzept §7.

### `ReleaseGate` — `src/dispread/validate.py` (Klasse, kein Protocol)

```python
def evaluate(self, read: ReadResult, capture_ns: int) -> GateDecision: ...
def reset(self) -> None: ...
def interrupt(self) -> None: ...  # Bestaetigung und Uebergangszellen verwerfen
```

Die [Freigabe](glossar.md#freigabe-gate) ist zustandsbehaftet
(Mehrbildbestätigung, Veralterung). Auch hier: kein
Referenzwert.

### `ValueSink` — `src/dispread/sink/__init__.py`

```python
def open(self) -> None: ...
def close(self) -> None: ...
def emit(self, record: ValueRecord) -> TxReceipt: ...
def health(self) -> SinkHealth: ...
```

Die [Senke](glossar.md#senke-sink) **wirft nicht** bei Übertragungsfehlern,
sondern zählt sie in
`health()` und liefert einen Receipt mit `t_complete_ns=None`. Ein Sink darf
den Messbetrieb nicht anhalten — aber der Fehler darf auch nicht verschwinden.

### `TelegramFormatter` — `src/dispread/sink/protocol/__init__.py`

```python
@property
def capabilities(self) -> FormatterCapabilities: ...
def format(self, record: ValueRecord) -> bytes | None: ...   # None = Datensatz entfällt
```

`FormatterCapabilities.provisional` bleibt `True`, bis eine echte Spezifikation
geprüft wurde. Das Flag gehört in jedes Runartefakt.

## Die Datenklassen

Alle Ergebnisobjekte sind `frozen=True, slots=True`. Änderung nur über
`dataclasses.replace()` — und das heißt: neues Objekt, nicht Korrektur.

### `Frame` — `frames/types.py`

| Feld | Bedeutung |
| --- | --- |
| `frame_sequence` | UVC zählt gelieferte Quellbilder ab 1; Live-Records können durch übersprungene Bilder Lücken haben, Replay erhält aufgezeichnete Nummern |
| `image` | BGR (HxWx3) **oder** Graustufen (HxW) |
| `capture_timestamp` | `Timestamp` mit Zeitbasis |
| `source_id` | wer hat das erzeugt |
| `exposure_time_us`, `frame_duration_us`, `analogue_gain` | Kamerawerte oder `None` |
| `raw_metadata` | Kamerametadaten unverändert; bei `synthetic://` auch `ground_truth` und `digit_area` |
| `inference` | `InferenceResult` bei On-Sensor-Inferenz, sonst `None` |
| `trigger_sequence` | externer Trigger, falls vorhanden |

Abgeleitet: `timebase`, `is_time_bearing`, `size` (Breite, Höhe).

### `Timestamp` — `records.py`

| Feld | Regel |
| --- | --- |
| `value_ns` | Nanosekunden, ganzzahlig |
| `base` | `V4L2_MONOTONIC` · `SENSOR_BOOTTIME` · `REPLAY_RECORDED` · `SYNTHETIC` · `FILE_MTIME` |
| `semantics` | `UNKNOWN` bis Messung M2 geklärt hat, worauf sich der Sensorzeitstempel bezieht |
| `uncertainty_ns` | `None`, solange nicht gemessen. **Nie 0.** |

`base.carries_time_information` ist eine notwendige Voraussetzung für eine
Zeitaussage. Zusätzlich müssen Zeitdomänen, Semantik und Umrechnung passen:
`to_boottime_ns()` verlangt für UVC den gemessenen BOOTTIME−MONOTONIC-Versatz
und lehnt fehlende Angaben oder Suspend ab. `REPLAY_RECORDED` trägt die Zeit
der Aufnahme; sie ist keine neue Aufnahmezeit des Replay-Laufs.

### `DisplayCandidate` — `detect/__init__.py`

`quad` (4 Punkte, im Uhrzeigersinn ab oben links), `score`, `locator_id`,
`locator_version`, `role_hint` (`"main"` / `"secondary"` oder `None`).
Die Rolle muss im bestätigten Ablauf eindeutig sein; der Konstruktor erlaubt
`None`, und die allgemeine Pipeline prüft die Rolle nicht selbst. Der Live-
Locator setzt für die bestätigte Anzeige `"main"`.

### `DisplayCrop` — `rectify.py`

`image`, `source_quad`, `homography` (9 Werte, erlaubt Rückprojektion für
Diagnosebilder), `sharpness` (Laplace-Varianz, nur innerhalb eines Aufbaus
vergleichbar), `saturated_fraction`, `clipped_dark_fraction`, `diagnostics`.
Abgeleitet: `exposure_ok`.

### `ReadResult` — `ocr/__init__.py`

| Feld | Warum eigenständig |
| --- | --- |
| `raw_text` | Textrepräsentation des Lesers; beim Dot-Matrix-Leser die geparste Zahl mit Vorzeichen und Punkt, nicht alle 16 Displayzellen |
| `value` | Interpretation; `None`, wenn nicht sicher lesbar |
| `sign_detected` | Minus gesehen? |
| `sign_region_readable` | War der Bereich überhaupt auswertbar? Getrennt, weil „nicht lesbar" nicht „positiv" bedeutet |
| `decimal_point_detected`, `decimal_point_index` | übersehener Dezimalpunkt ist ein eigener kritischer Fehler |
| `unit_text` | falsche Einheit ist ein eigener kritischer Fehler |
| `status_flags` | Betriebszustände: `overflow`, `menu`, `hold`, `glare` |
| `glyphs` | `GlyphEvidence` je Stelle: `text`, `confidence`, `segments`, `ambiguous_with`, `margin` |
| `backend_id`, `backend_version` | wer hat gelesen |
| `diagnostics` | freies Dict; das Gate liest daraus `contrast`, `min_margin`, `unreadable_cells` |

**Wenn du ein neues Backend schreibst:** diese drei `diagnostics`-Schlüssel
sind faktisch Teil des Vertrags, sonst kann das Gate nicht urteilen. Und
`unit_source` gehört hinein, wenn die Einheit aus dem Profil stammt statt
gelesen zu sein.

### `GateDecision` — `validate.py`

`status`, `confidence` (Qualitätsmaß, **keine** Fehlerwahrscheinlichkeit),
`reject_reasons` (bei `status != VALID` nie leer), `frames_confirmed`,
`confirmation_span_ns`, `gate_version`.

Bekannte Gründe heute: `state:<flag>`, `low_contrast`,
`unreadable_cells:<n>`, `low_segment_margin`, `sign_region_unreadable`,
`decimal_point_unknown`, `unit_mismatch:<gelesen>`, `no_value`,
`awaiting_confirmation`, `anzeige_wechselt` (TRANSITION bei Ziffernwechsel,
steht dann an erster Stelle vor den Lesbarkeitsgründen),
`display_not_located` oder `tracking_lost:<grund>` bei fehlendem Kandidaten
der Live-Nachführung. Neue Gründe sind
maschinenlesbare Kurzstrings im selben Stil — sie werden ausgewertet, nicht
gelesen.

### `ValueRecord` — `records.py`

Die neun Pflichtfelder aus Konzept §8 zuerst, danach Nachvollziehbarkeit.
Die [API-Referenz](../../api/vertraege.md#dispread.records.ValueRecord "ValueRecord: der interne Datensatz mit Wert, Status und Zeitbezug")
zeigt die aktuelle Signatur.

| Feld | Erzeuger | darf ändern |
| --- | --- | --- |
| `frame_sequence` | `FrameSource` | niemand |
| `capture_timestamp` | `FrameSource` | niemand, **nie** ein Adapter |
| `value`, `unit`, `raw_text` | `ValueReader` | niemand |
| `status`, `confidence`, `reject_reasons` | `ReleaseGate` | niemand |
| `profile_id` | Session / ProfileStore | niemand |
| `trigger_sequence` | `FrameSource` / Trigger | niemand |
| `result_timestamp` | Pipeline beim Abschluss, `HOST_MONOTONIC` | niemand |

**Verarbeitungszeitbasis (geklärt 2026-10-23,
[OQ-45](../open-questions.md#oq-45)):** Die Pipeline setzt
`result_timestamp` für jede Quelle aus `time.monotonic_ns()` mit der Basis
`HOST_MONOTONIC`; auch `Timestamp.now_monotonic()` verwendet diese Basis.
`capture_timestamp` behält unverändert die Zeitbasis der Quelle. Nach
BOOTTIME führt nur `to_boottime_ns` mit dem Versatz der jeweiligen Session
und bestandener Suspend-Prüfung. Alte Auditdateien behalten ihre bisherigen
Basenkennzeichnungen. Aufnahme- und Ergebniszeit deshalb nur bei belegtem
gemeinsamem Uhrbezug vergleichen; reine Rechenzeiten stehen in den
monotonen Stufenmarken des `PipelineTrace`.

Zwei Invarianten, im Konstruktor erzwungen:

1. `status != VALID` ⇒ `reject_reasons` nicht leer.
2. `status in (STALE, UNREADABLE)` ⇒ `value is None`.

[to_dict()](../../api/vertraege.md#dispread.records.ValueRecord.to_dict "Serialisiert den ValueRecord für das JSONL-Log") /
`from_dict()` müssen verlustfrei sein — das ist ein
Abnahmekriterium aus P0 und in `tests/test_records.py` geprüft.

### `TxReceipt` — `records.py`

Was tatsächlich über die Leitung ging: `tx_sequence`, `format_id`,
`wire_bytes` (Beweismittel bei Formatstreit), `t_enqueue_ns`,
`t_complete_ns` (`None` = fehlgeschlagen), `channel`, `retry_count`,
`invalid_policy`, `omitted`.

**Nie** mit `ValueRecord` mischen: dort steht die Aufnahmezeit, hier die
Sendezeit. Wer beides in einem Objekt führt, kann später nicht mehr belegen,
welche Zeit welche war.

### `PipelineTrace` — `records.py`

Marken je Stufe in `CLOCK_MONOTONIC` plus `queue_depth` und
`dropped_frames`. `stage_durations_us()` liefert `locate`, `rectify`, `read`,
`gate`, `build`, `total`. Verworfene Frames werden **gezählt**, nicht
stillschweigend ignoriert.

### `DisplayLayout` — `layout.py`

`digits`, `decimals` (`None` = Dezimalpunkt muss erkannt werden), `has_sign`,
`unit`, `sign_cell_ratio`, `thickness_ratio`, `inset_ratio`. Methoden:
`cell_boxes(w, h)`, `sign_box(w, h)`, `decimal_point_index()`,
`format_value()`, `to_dict()`/`from_dict()`.

Im Betrieb kommt das Layout aus dem bestätigten Geräteprofil
([Kapitel 4](04-geraeteprofile.md)), nicht aus Vermutungen im Code.

<figure class="tour-figure" data-scene="erkennung-raster" markdown="1">
<figcaption markdown="span">Ein bestätigtes Raster am Punktraster-Display des GSV-2AS: Das System weiß vorher, wo jedes Zeichen liegt und welche Kästchen gelesen werden.</figcaption>
</figure>

### `CharLayout` — `layout.py`

`grid`, `unit`, `format_id`, `classified_cells` und `blank_cells` beschreiben
den Dot-Matrix-Pfad. `CharLayout.from_profile()` verlangt ein bestätigtes
`SessionProfile` mit bestandenem Auflösungs-Gate. Der Leser klassifiziert die
Zellen 0–8, prüft 13–15 auf Leerinhalt und übernimmt die Einheit aus dem Profil.

## Statuslogik in einem Bild

```
                     Freigabe erteilt ────────────────► VALID
                            ▲
   ReadResult ──► Gate ─────┼── Wert wechselt / zu wenige Frames ──► TRANSITION
                            │
                            ├── Grund liegt vor, Ablehnung frisch ──► UNREADABLE
                            │
                            └── keine Freigabe länger als
                                stale_after_ns (Default 500 ms) ──► STALE
```

Das Schema zeigt den Lesbarkeitszweig des Gates nach einer früheren Freigabe.
Blockierende Zustände bleiben dort `UNREADABLE`; ein fehlender bzw. verlorener
Kandidat umgeht `evaluate()` und wird in der Pipeline ebenfalls `UNREADABLE`.
Die Live-Anzeige prüft zusätzlich das Alter eines freigegebenen Wertes und
setzt die sichtbare Ausgabe bei Stream- oder Verbindungsverlust auf STALE.

`TRANSITION` und `UNREADABLE` sind **Aussagen über die Anzeige**, keine Fehler
des Systems. `STALE` heißt: es gibt keinen aktuellen Wert — und ein
`STALE`-Datensatz trägt deshalb keinen Zahlenwert.

<figure class="tour-figure" data-scene="erkennung-veraltet" markdown="1">
<figcaption markdown="span">Dieselbe Statuslogik als Ablauf: Eine verdeckte Anzeige liefert „unlesbar“ ohne Zahlenwert, und hält das an, wird daraus „veraltet“.</figcaption>
</figure>

## Checkliste für jedes neue Modul

* [ ] Modul-Docstring: warum, mit Verweis auf `Konzept.md §n` oder `OQ-nn`
* [ ] Erfüllt genau ein Protokoll; Konformität im Test per `isinstance` geprüft
* [ ] Ergebnisobjekte `frozen=True, slots=True`
* [ ] Kein Referenzwert, kein letzter guter Wert, keine Glättung
* [ ] Zeitstempel mit korrekter `TimeBaseKind`, `uncertainty_ns=None` wenn ungemessen
* [ ] Fehler werden gezählt und benannt, nicht verschluckt
* [ ] `describe()`/`capabilities` sagen die Wahrheit über die eigenen Grenzen
* [ ] Test läuft im Mock-Modus, ohne Hardware
