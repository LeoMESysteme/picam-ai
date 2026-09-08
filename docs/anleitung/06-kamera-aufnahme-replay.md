# 6 — Kamera, Aufnahme, `replay://`

**Ziel:** Drei Module: `picamera2://` liefert Live-Frames mit echtem
Sensorzeitstempel, `dispread record` schreibt eine Aufnahmesession mit
Manifest, `replay://` spielt sie mit den **originalen** Zeitstempeln wieder ab.

**Warum jetzt:** Ab hier hat das Projekt reale Daten. Bisher stammen alle
Zahlen aus synthetischem Material, und Konzept §9 ist eindeutig, dass das kein
Nachweis ist ([OQ-04](../open-questions.md),
[OQ-14](../open-questions.md)). `replay://` macht die Kette gegen echtes
Material **regressionsfähig** — das ist der eigentliche Gewinn dieses
Kapitels, nicht das Livebild. Schließt P1 ab und öffnet P2/P3.

**Vorbedingungen:** [Kapitel 3](03-erste-bildquelle-folder.md),
[Kapitel 4](04-geraeteprofile.md), [Kapitel 5](05-cli.md).
Hardware: Kamera an CAM/DISP0, `./scripts/camera-commissioning.sh` mit Exit 0.
Lesen: [../CAMERA_COMMISSIONING.md](../CAMERA_COMMISSIONING.md),
[../TIMING.md](../TIMING.md), [../OPTICAL_SETUP.md](../OPTICAL_SETUP.md).

## Reihenfolge: erst der Aufbau, dann Code

Der optische Aufbau ist hier **Voraussetzung, nicht Feinarbeit**. Gemessen
entstehen die stillen Fehlablesungen bei Glanz (2 von 40, siehe
[../VALIDATION.md](../VALIDATION.md)), und der Fokus der Kamera ist derzeit
verstellt. Kein Softwareaufwand ersetzt eine Abschirmung. Halte deshalb
zuerst [../OPTICAL_SETUP.md](../OPTICAL_SETUP.md) her: Abstand, Ziffernhöhe in
Pixeln, Beleuchtung, keine Spiegelung im Sichtfeld — und dokumentiere den
Aufbau im [../lab_journal.md](../lab_journal.md), bevor du Frames sammelst.
Aufnahmen aus einem unbekannten Aufbau sind später nicht deutbar.

## Teil A — `Picamera2Source`

Registry-Signatur (schon vorhanden): `Picamera2Source(size=(2028, 1520), fps=None)`.

Der Sensor kann 2028×1520 @ 30,02 fps und 4056×3040 @ 10,00 fps
([../HARDWARE_PROFILE.md](../HARDWARE_PROFILE.md)). Nimm den ersten Modus.

Muster, an dem alles hängt — **Bild und Metadaten aus derselben Aufnahme**
(Konzept §6 verlangt das ausdrücklich):

```python
def frames(self) -> Iterator[Frame]:
    while True:
        request = self._picam2.capture_request()      # ein Request = eine Aufnahme
        try:
            image = request.make_array("main")        # ndarray
            md = request.get_metadata()               # SensorTimestamp, ExposureTime, ...
        finally:
            request.release()                         # PFLICHT, sonst Pufferhunger
        self._seq += 1
        yield Frame(
            frame_sequence=self._seq,
            image=image,
            capture_timestamp=Timestamp(
                value_ns=int(md["SensorTimestamp"]),
                base=TimeBaseKind.SENSOR_BOOTTIME,      # gemessen 2026-09-07
                semantics=TimestampSemantics.UNKNOWN,   # bis Messung M2 geklaert ist
                uncertainty_ns=None,
            ),
            source_id=self.source_id,
            exposure_time_us=md.get("ExposureTime"),
            frame_duration_us=md.get("FrameDuration"),
            analogue_gain=md.get("AnalogueGain"),
            raw_metadata=dict(md),                      # unveraendert mitfuehren
        )
```

Punkte, die man nicht raten sollte:

* **`request.release()` gehört in ein `finally`.** Nicht freigegebene Requests
  halten Kamerapuffer fest; nach wenigen Frames bleibt die Kamera stehen. Das
  sieht wie ein Aufhänger aus und ist ein Leck.
* **`semantics` bleibt `UNKNOWN`.** Die Domäne ist gemessen
  (`CLOCK_BOOTTIME`), die Semantik nicht — das ist Messung M2 in
  [../TIMING.md](../TIMING.md). Einen Wert hinzuschreiben, weil er plausibel
  ist, wäre eine erfundene Messung.
* **`uncertainty_ns=None`.** Nicht 0.
* **`raw_metadata` unverändert.** Der rohe Sensorzeitstempel wird nie
  überschrieben, nur ergänzt.
* **Farbreihenfolge prüfen, nicht annehmen.** Die libcamera-Formatnamen
  beschreiben Bytereihenfolgen; welches Format bei `make_array` ein
  OpenCV-taugliches BGR-Array ergibt, prüfst du **einmal** mit einer bekannten
  Farbfläche und schreibst das Ergebnis in
  [../HARDWARE_PROFILE.md](../HARDWARE_PROFILE.md). Ein verdrehter Kanal fällt
  bei einer roten LED-Anzeige nicht sofort auf — der Segmentleser rechnet in
  Graustufen weiter und liest trotzdem Zahlen. Genau die Sorte Fehler, die
  still bleibt.
* **`capabilities`:** `LIVE`, dazu `EXPOSURE_CONTROL`, wenn du
  `set_controls()` anbietest — aber **nicht** `SEEK`.
* **Import lazy halten.** `from picamera2 import Picamera2` steht in der
  Methode oder ganz unten in der Factory, niemals auf Modulebene der CLI.

Test dafür ist `@pytest.mark.hardware` — und zusätzlich ein Mock-Test, der
prüft, dass das Modul **ohne** `picamera2` importierbar bleibt und die richtige
Fehlermeldung liefert.

Erwartete Zustände ohne Kamera (keine Bugs):
`Picamera2.global_camera_info() == []`,
`RuntimeError: IMX500: Requested camera dev-node not found`. Und:
`camera_auto_detect` greift nur beim Booten — nach dem Anstecken **Reboot**.

## Teil B — Aufnahmesession

Ohne Manifest ist eine Aufnahme in zwei Wochen unbrauchbar, weil niemand mehr
weiß, welches Gerät, welcher Aufbau, welche Belichtung. Vorschlag für das
Verzeichnis (`paths.VAR_LIB / "sessions"`):

```
2026-09-15_gsv2asd-labor1/
    manifest.json          Aufbau, Profil, Kameraconfig, Softwarestand
    metadata.jsonl         je Frame eine Zeile: seq, sensor_timestamp_ns, exposure, gain, datei
    frames/000001.png      verlustfrei
    frames/000002.png
    notes.md               was der Mensch beobachtet hat
```

`manifest.json` mindestens:

```python
{
  "session_id": "2026-09-15_gsv2asd-labor1",
  "created_at": "2026-09-15T10:12:00+02:00",
  "dispread_version": __version__,
  "git_commit": "…",                    # subprocess: git rev-parse HEAD
  "source": source.describe(),
  "profile": profil.to_dict(),
  "camera": {"size": [2028, 1520], "controls": {...}, "sensor_mode": "..."},
  "timebase": "sensor_boottime",
  "timestamp_semantics": "unknown",     # M2 offen
  "boot_id": "…",                       # /proc/sys/kernel/random/boot_id
  "frame_count": 1234,
  "optical_setup": {"distance_mm": 420, "digit_height_px": 96, "lighting": "Ringlicht, Streuscheibe"},
  "notes": "…"
}
```

Warum `boot_id` mit hinein: `CLOCK_BOOTTIME` zählt ab dem Booten. Zwei
Sessions von verschiedenen Boots haben Zeitstempel, die **nicht** vergleichbar
sind. Ohne `boot_id` merkt das später niemand.

Weitere Entscheidungen:

* **PNG, nicht JPEG.** JPEG-Artefakte an Segmentkanten verändern genau die
  Messgröße. Der Preis ist Platz — und es sind nur **34 GB frei**
  ([../HARDWARE_PROFILE.md](../HARDWARE_PROFILE.md)). Also: harte Obergrenze
  für die Frameanzahl, Abbruch mit Meldung statt volle Platte.
* **Nichts während der Aufnahme verarbeiten.** Aufnehmen und Auswerten
  trennen; sonst hängt die Aufnahmerate an der Verarbeitungszeit.
* **Sollwert notieren, wenn es einen gibt.** Bei M5-Messungen kommt er aus dem
  Anregungsaufbau, nie aus der Erkennung — und er landet in `metadata.jsonl`
  bzw. `notes.md`, **nicht** im `ValueRecord`.

## Teil C — `ReplaySource`

Registry-Signatur: `ReplaySource(session_dir=…)`.

Der Kern ist eine Zeile Haltung: der Zeitstempel kommt aus
`metadata.jsonl`, nicht von der Uhr —

```python
capture_timestamp=Timestamp(
    value_ns=int(zeile["sensor_timestamp_ns"]),
    base=TimeBaseKind.REPLAY_RECORDED,     # traegt die Zeitaussage der AUFNAHME
    semantics=TimestampSemantics.UNKNOWN,
    uncertainty_ns=None,
)
```

`REPLAY_RECORDED` trägt laut `carries_time_information` eine Zeitaussage —
aber die der Aufnahme, nicht die des Abspielens. Deshalb darfst du daraus
Displayverzögerungen (M5) auswerten, aber **keine** Pipeline-Latenzen des
Replay-Laufs als reale Latenzen berichten.

Weiter:

* `capabilities`: `SEEK`; Abspieltakt entweder „so schnell wie möglich" (für
  Regressionstests) oder in Originalgeschwindigkeit aus den Zeitstempel-Deltas.
* `describe()` nennt `session_id`, `frame_count`, `boot_id` und den
  Softwarestand der Aufnahme.
* **Manifest prüfen, nicht raten.** Fehlt es, ist es keine Session — Fehler mit
  Verweis auf dieses Kapitel.
* Ein `replay://`-Regressionstest gehört in den **Mock**-Pfad: kleine Session
  (5–10 Frames) mit erwarteten Werten als Testdaten einchecken. Das ist der
  erste Test des Projekts, der gegen reale Anzeigen prüft — und ab da kann
  keine Änderung am Leser unbemerkt die Erkennung verschlechtern.

## Teil D — `Imx500Source` (später, optional)

`imx500://?rpk=…` ist **nicht** der Weg zur Anzeigenerkennung: die 23
mitgelieferten `.rpk` sind COCO-/ImageNet-Modelle (`person`, `bicycle`, `tv`),
und der *Converter* für eigene Modelle fehlt auf dem Pi, nur der *Packager* ist
vorhanden ([OQ-11](../open-questions.md)). Bau es nur, wenn du die
On-Sensor-Inferenz vermessen willst (P8). Gemessen: **6,8 s** Warmlauf beim
ersten `.rpk`-Upload, **15,0 Inferenzen/s**, `CnnKpiInfo` mit dnn 13,96 ms /
dsp 12,36 ms; `CnnInputTensor` fehlt in den Standardmetadaten. Ergebnisse
gehören in `Frame.inference` als `InferenceResult` (Tensoren unverändert,
Laufzeiten aus `CnnKpiInfo`).

## Messungen, die du hier mitnehmen kannst

Wenn die Kamera schon läuft, sind zwei Messungen billig — und beide sind für
das Projekt wichtiger als weitere Software:

* **M2** (Semantik von `SensorTimestamp`): LED per GPIO zu bekannten
  Monotonic-Zeitpunkten pulsen, Belichtungszeit systematisch variieren. Wandert
  der Zeitstempel mit der Belichtungszeit, bezieht er sich auf das Auslese-Ende.
  Danach darf `TimestampSemantics` einen belegten Wert bekommen.
* **M5** (Displayaktualisierung und Haltezeit): mit hoher Wahrscheinlichkeit
  der **dominierende** Term im Zeitbudget — und von keiner Softwareoptimierung
  kleiner. Sprunganregung, ≥ 30 Wiederholungen je Gerätetyp.

Pflicht danach: Zahlen in [../VALIDATION.md](../VALIDATION.md) bzw.
[../TIMING.md](../TIMING.md), Aufbau und Deutung in
[../lab_journal.md](../lab_journal.md) — am selben Tag.

## Fallen

* **Kein Reboot nach dem Anstecken** → Kamera bleibt unsichtbar. Häufigster
  Fehler in diesem Projekt, schon einmal passiert.
* **`dtoverlay -l` sagt `No overlays loaded`, obwohl die Kamera läuft.** Kein
  Kriterium. Nachweis ist der Sensorknoten im Device-Tree plus die
  libcamera-Enumeration.
* **`/dev/serial0` ist der Debug-Header**, nicht der Datenport. Datenport ist
  `/dev/ttyAMA0` (relevant, sobald du im Livebetrieb sendest).
* **Autofokus gibt es nicht.** Das Objektiv wird mechanisch eingestellt und
  danach fixiert. Fokus prüfen über `DisplayCrop.sharpness` an derselben
  Stelle — Absolutwerte sind nur innerhalb eines Aufbaus vergleichbar.
* **Belichtung automatisch = Zeitbezug wackelig.** Für Messreihen Belichtung
  und Verstärkung fixieren und im Manifest festhalten.
* **Aus `folder://`-Frames einer Session keine Zeitaussagen ziehen.** Wer eine
  Session mit `folder://` abspielt, bekommt `FILE_MTIME` und verliert den
  Sensorzeitstempel. Dafür gibt es `replay://`.

## Fertig, wenn

* [ ] `picamera2://` liefert Frames mit `base=sensor_boottime`,
      `semantics=unknown`, `uncertainty_ns=None`
* [ ] Modul ist ohne `picamera2` importierbar; Hardware-Tests mit
      `@pytest.mark.hardware` markiert
* [ ] `dispread record` schreibt Session mit vollständigem Manifest inkl.
      `boot_id` und `git_commit`
* [ ] `replay://` spielt sie mit `REPLAY_RECORDED` ab; kleine Session als
      Regressionstest im Mock-Pfad eingecheckt
* [ ] Aufbau in [../lab_journal.md](../lab_journal.md), Zahlen in
      [../VALIDATION.md](../VALIDATION.md)/[../TIMING.md](../TIMING.md)
* [ ] `CHANGELOG.md`, ROADMAP (P1-Zeile) aktualisiert; `docs/status.md` neu

Weiter mit [Kapitel 7 — Lokalisierung](07-lokalisierung.md).
