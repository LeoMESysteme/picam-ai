# 8 — Weitere OCR-Backends

**Ziel:** Ein zweites Backend hinter `ValueReader`, und ein Vergleichsharnisch,
der es **pro Fehlerklasse** gegen den Segmentleser stellt.

**Warum jetzt:** Der Segmentleser ist Primärpfad, weil er erklärbare Evidenz
liefert. Ob ein anderes Verfahren auf **realen** Anzeigen besser trägt, ist
offen ([OQ-18](../open-questions.md)) — und ohne Vergleich auf echten Daten
bleibt es offen. Wichtig ist die Reihenfolge: **erst der Harnisch, dann das
Backend.** Ein Backend ohne Vergleichszahlen ist eine Meinung.

**Vorbedingungen:** [Kapitel 6](06-kamera-aufnahme-replay.md) — reale Frames
mit Label. Auf synthetischem Material ist der Vergleich wertlos: der Generator
zeichnet mit demselben Layout, gegen das der Segmentleser abtastet.

## Was ein neues Backend liefern muss

`ReadResult` verlangt mehr als einen String. Das ist der Punkt, an dem
generische OCR anstrengend wird — und genau deshalb ist er im Vertrag:

| Feld | Wie du es mit generischer OCR füllst |
| --- | --- |
| `raw_text` | die erkannte Zeichenkette, unverändert |
| `value` | `None`, wenn die Zeichenkette nicht dem Profilformat entspricht — **nicht** zurechtbiegen |
| `sign_detected` | den Vorzeichenbereich (`layout.sign_box`) **separat** auswerten, nicht aus dem Gesamtstring lesen |
| `sign_region_readable` | war der Bereich überhaupt beurteilbar? Kontrast/Sättigung dort messen |
| `decimal_point_detected` | eigene Prüfung; aus dem Profil übernommen ⇒ `False` wäre falsch, aber `unit_source`-Logik analog vermerken ([OQ-17](../open-questions.md)) |
| `unit_text` + `diagnostics["unit_source"]` | gelesen (`read`) oder aus dem Profil (`profile`) — Unterschied muss sichtbar bleiben |
| `glyphs` | pro Stelle eine `GlyphEvidence`. Hat das Backend keine Per-Zeichen-Konfidenz, dann `confidence=0.0` und `margin=0.0` — **nicht** die Gesamtkonfidenz auf die Stellen verteilen |
| `diagnostics["contrast"]`, `["min_margin"]`, `["unreadable_cells"]` | faktisch Vertragsbestandteil: das Gate urteilt daraus. Was du nicht messen kannst, meldest du als 0 — und das Gate lehnt dann ab. Das ist die richtige Richtung |
| `declares_confidence_calibrated` | `False`. Nur `True`, wenn eine Kalibriermessung in [../VALIDATION.md](../VALIDATION.md) steht |

Merksatz: **ein Backend, das keine Evidenz liefert, bekommt keine Freigabe.**
Nicht weil es schlechter ist, sondern weil das Gate nichts zu prüfen hat
([OQ-19](../open-questions.md)).

## Teil A — Der Vergleichsharnisch (zuerst)

`examples/08_backend_vergleich.py`, im Stil von `examples/16` (Docstring-Kopf:
Zweck / Hardware / Ausgabe / Referenz).

Aufbau:

```
replay:// oder folder://  (reale Frames + Labels)
      │
      ├── SevenSegmentReader ─┐
      └── NeuesBackend ───────┤ gleiche Frames, gleiche ROI, gleiches Layout
                              ▼
             Auswertung pro Fehlerklasse aus docs/VALIDATION.md
```

Zähle getrennt — die Klassen stehen in [../VALIDATION.md](../VALIDATION.md):
`wrong_digit`, `missing_sign`, `wrong_decimal_point`, `wrong_unit`,
`wrong_state`, `false_reject`. Und darüber die zwei Kennzahlen, die nicht
verhandelbar sind:

1. **Rate unerkannter Fehlablesungen** — als `VALID` ausgegeben, aber falsch.
   Nur diese ist metrologisch gefährlich.
2. **Rate der Falschablehnungen** — störend, nicht gefährlich.

Ein Backend mit 99,5 % Zeichenquote und 0,5 % stillen Fehlern ist **schlechter**
als eines mit 95 % und 0 % stillen Fehlern. Der Harnisch muss das sichtbar
machen, sonst optimiert man die falsche Zahl. Deshalb: eine Zeile pro
Fehlerklasse und Backend, keine Gesamtnote.

Was der Bericht außerdem nennen muss: Datensatzgröße, Zahl der
Geräteinstanzen, und dass die Splitgrenze die **Geräteinstanz** ist, nie der
Frame — Nachbarframes derselben Aufnahme in Training und Test sind laut
Konzept §9 der klassische Selbstbetrug.

## Teil B — `tesseract_cli`

**Blockiert durch [OQ-15](../open-questions.md):** `tesseract-ocr` ist nicht
installiert, und `sudo` verlangt seit dem Reboot ein Passwort. Ein Mensch mit
`sudo` muss einmal:

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-eng socat chrony
```

(`socat` für serielle Gegenstellen, `chrony` für Messung M1 — dieselbe
Gelegenheit nutzen.) Danach `docs/dependencies.md` ergänzen und OQ-15 auf
`geklärt` setzen, **nicht** löschen.

Umsetzung als Unterprozess, nicht über eine Python-Bindung:

```python
def read(self, crop: np.ndarray, layout: DisplayLayout) -> ReadResult:
    # Nur Ziffern und Minus zulassen, eine Zeile, kein Woerterbuch.
    args = [
        "tesseract", "stdin", "stdout",
        "--psm", "7",
        "-c", "tessedit_char_whitelist=0123456789-.",
    ]
    ...
```

Warum CLI: eine PyPI-Bindung wäre eine neue Abhängigkeit im venv und würde die
Regel aus [../dependencies.md](../dependencies.md) berühren. Das Programm ist
ein Systempaket; ruf es als solches auf.

Realistische Erwartung: 7-Segment-Ziffern sind für die Standard-`traineddata`
schwierig — die Segmente sind getrennte Balken, keine geschlossenen
Buchstabenformen. Deshalb steht in [OQ-10](../open-questions.md) die Frage nach
spezialisierten `traineddata` (`ssd`, `letsgodigital`). Nimm es als
**Vergleichsmaßstab**, nicht als Kandidaten für den Primärpfad.

## Teil C — Neuronaler Zeilenleser (nur mit realen Daten)

Die Tool-Recherche vom 2026-09-08
([../tool_review_2026-09-08.md](../tool_review_2026-09-08.md)) empfiehlt einen
kleinen neuronalen Zeilenleser über ONNX Runtime auf dem Pi; RapidOCR ist
Integrationskandidat, PP-OCRv5 mobile und PP-OCRv6 tiny/small sind die zu
vergleichenden Modelle. **Das ist eine Empfehlung, keine beschlossene
Migration.** Bedingungen, bevor du anfängst:

* Realer Datensatz existiert (P2): ≥ 6 Geräteinstanzen über ≥ 3
  Displaytypen, davon **2 gesperrt**.
* Der Harnisch aus Teil A läuft und liefert Zahlen pro Fehlerklasse.
* Die neue Abhängigkeit (ONNX Runtime) ist in
  [../dependencies.md](../dependencies.md) begründet — inklusive der Frage, ob
  sie als Systempaket verfügbar ist. Eine PyPI-Installation neben System-`numpy`
  ist genau der Fall, den die venv-Regel verhindert.
* Und: das gilt für das **Lesen**, nicht für den Messpfad insgesamt.
  Sprachmodelle oder generative KI sind für den laufenden Messpfad ausdrücklich
  nicht vorgesehen.

## Am Segmentleser weiterarbeiten (oft der bessere Hebel)

Bevor du ein zweites Verfahren einführst, sind das hier bekannte, benannte
Lücken im vorhandenen:

* **[OQ-13](../open-questions.md) — „alle Stellen zeigen 8".** Dann gibt es
  keine inaktive Segmentklasse, der Kontrast ist klein, und der Ausschnitt wird
  abgelehnt. Falschablehnung ist die erlaubte Richtung, aber im Betrieb
  störend. Lösungsansatz: Polarität und erwartetes Helligkeitsniveau aus dem
  Profil, statt die Schwelle nur aus dem Bild zu ziehen.
* **[OQ-17](../open-questions.md) — Dezimalpunkt optisch messen.** Heute kommt
  er aus dem Profil. Der Punkt ist ein kleiner heller Fleck an bekannter
  relativer Position; das ist mit denselben Abtastmitteln machbar wie ein
  Segment — und macht `decimal_point_detected` erst zu einer echten Aussage.
* **Einheit lesen statt bestätigen.** `unit_source` steht bereit; die
  Einheitenzeile ist im Layout beschrieben.
* **Segmentausfall und Multiplex-Flimmern.** Der Generator kann das
  (`dropout_segments` in `render_display`) — gibt es einen Test, der belegt,
  dass ein ausgefallenes Segment zur Ablehnung führt und nicht zu einer
  ähnlichen Ziffer?

Jede dieser vier Aufgaben ist kleiner als ein neues Backend und verbessert den
Pfad, der ohnehin produktiv ist.

## Fallen

* **Konfidenz eines Modells ist keine Fehlerwahrscheinlichkeit.** Kein
  Schwellwert auf eine unkalibrierte Konfidenz, der als Freigabekriterium
  verkauft wird.
* **Kein Nachbessern per Plausibilität.** „Der Wert ist 100× zu groß, also war
  es der Dezimalpunkt" ist eine Korrektur, die echte Sprünge glättet und
  Fehlablesungen verdeckt.
* **Referenzwert nicht hineinreichen.** Auch nicht „nur zum Auswerten": der
  Harnisch führt das Label **außerhalb** der Kette, wie es
  `examples/16` mit `_run_with_truth()` vormacht.
* **Nicht auf synthetischem Material entscheiden.** Der Generator benutzt
  dasselbe `DisplayLayout`; der Segmentleser hat dort strukturell Heimvorteil.
* **Backend-Wechsel ist eine Entscheidung, keine Konfiguration.** Neuer
  Primärpfad ⇒ Eintrag in `docs/project_history.md` (Problem / Entscheidung /
  Begründung / Alternativen / Konsequenz) und Zahlen in
  [../VALIDATION.md](../VALIDATION.md).

## Fertig, wenn

* [ ] Harnisch läuft über eine reale Session und gibt eine Tabelle pro
      Fehlerklasse und Backend aus
* [ ] Neues Backend erfüllt `ValueReader` (isinstance-Test) und füllt die drei
      `diagnostics`-Schlüssel
* [ ] `declares_confidence_calibrated` ist `False` — oder es gibt eine
      Kalibriermessung, die das Gegenteil belegt
* [ ] Zahlen in [../VALIDATION.md](../VALIDATION.md), Aufbau im
      [../lab_journal.md](../lab_journal.md)
* [ ] `OQ-15`/`OQ-18`/`OQ-19` fortgeschrieben (Status, Antwort, Verweis — nie
      gelöscht)
* [ ] `CHANGELOG.md`, `docs/dependencies.md` bei neuer Abhängigkeit

Weiter mit [Kapitel 9 — Betrieb](09-betrieb.md).
