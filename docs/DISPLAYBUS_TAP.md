# Displaybus-Abgriff als Ground-Truth-Quelle

**Stand: 2026-09-22 — Konzeptskizze, nicht gebaut, nichts gemessen.**

> **Rückfallebene, nicht Primärweg.** Diese Skizze entstand, solange das Gerät
> für undokumentiert gehalten wurde. Seit es als **GSV-2AS** identifiziert ist
> (Startmeldung `GSV-2AS (GSV21 V1.3.07)`), ist der Primärweg **RS232 im
> ASCII-Modus** über die vorhandene 5-polige Klemme `A/B/C` — die
> Herstellerdokumentation sagt für diesen Modus ausdrücklich, dass die
> gesendete Zeichenkette *der Anzeige im Display entspricht*. Damit fällt das
> Hauptargument weg, das hier für den Displaybus sprach. Begründung und
> Belegstellen: [OQ-38](open-questions.md).
>
> Die Skizze bleibt aus zwei Gründen stehen:
> 1. als **Gegenprobe**, falls sich Inhalt oder Zeitlage von Stream und
>    Anzeige am realen Gerät doch unterscheiden;
> 2. für den **einen Zweck, den die Serielle nicht erfüllt**: Code-zu-Glyph-
>    Paare zur Klärung der Zeichensatz-ROM-Variante des Displaycontrollers
>    (`°`/`Ω`/`µ`, siehe CLAUDE.md).
>
> Die Abschnitte „Der kritische Punkt" (optische Einschwingzeit),
> „Zeitbasis" und „Anbindung an den Sammelmodus" gelten **unverändert auch für
> den seriellen Weg**.

Diese Datei beschreibt, *wie* ein passiver Mitleser am Displaybus des GSV
aussehen würde und *was vorher gemessen sein muss*. Sie ist kein Bauplan und
keine Freigabe. Die Grenze des Verfahrens steht in
[OQ-39](open-questions.md).

## Wozu

Der Sammelmodus braucht zu jedem Bild einen Sollwert (`expected_text`). Heute
tippt ihn ein Mensch ein. Das begrenzt die Datensatzgrösse und ist bei
zappelnden letzten Stellen nicht zuverlässig durchzuhalten.

Der Displaybus führt genau den Zeichenstring, den der Gerätecontroller in das
Displayregister schreibt — unabhängig davon, was das Gerät sonst nach aussen
gibt. Für das GSV-2AS ist diese Unabhängigkeit laut Anleitung nicht nötig
(ASCII-Ausgabe = Anzeige); für ein Gerät ohne solche Zusage wäre sie das
entscheidende Argument.

## Was bekannt ist und was nicht

| Punkt | Stand |
| --- | --- |
| Anzeige ist ein Displaytech 161A, 16×1, HD44780-kompatibel | belegt (Platinenaufdruck, CLAUDE.md) |
| Verbindung ist ein 16-poliges Flachband zur Hauptplatine | belegt (Foto `gsv_front_geöffnet.jpg`) |
| Pinbelegung folgt der HD44780-Standardreihenfolge (1 VSS … 16 K) | **angenommen, nicht verifiziert** |
| Busbreite: 4-bit (D4–D7) oder 8-bit (D0–D7) | **ungemessen** |
| Logikpegel: 5 V oder 3,3 V | **ungemessen** |
| R/W fest auf Masse (nur Schreibzugriffe) | **ungemessen** |
| Aktualisierungsrate der Anzeige | **ungemessen** |
| Optische Einschwingzeit des LCD | **ungemessen** — siehe unten, das ist der kritische Wert |

## Aufbau

Ein RP2040 liest den Bus **passiv** mit: nur Eingänge, keine Leitung wird
getrieben, das Gerät bekommt keinen zusätzlichen Signalpfad. Benötigt werden
RS, E, die genutzten Datenleitungen und eine gemeinsame Masse.

```
GSV-Hauptplatine ──16-pol. Flachband──> Displaytech 161A
                          │ (nur mitgehört: RS, E, D4..D7, GND)
                          v
                   Pegelanpassung
                          v
                      RP2040 (PIO)
                          v
                    USB-CDC an den Pi:  <Zeit> <16-Zeichen-String>
```

**Pegel: nicht überspringen.** RP2040-GPIO ist 3,3 V und **nicht 5-V-fest**.
Führt der Bus 5 V, braucht es eine Pegelanpassung (Spannungsteiler oder ein
Puffer wie 74LVC245), sonst wird der RP2040 beschädigt. Das ist dieselbe
Klasse von Fehler wie [OQ-09](open-questions.md) (Pi-GPIO nicht direkt an
RS-232). Die Pegelmessung kommt vor jedem Anschluss, nicht danach.

Der RP2040 wird **nicht** aus dem GSV versorgt, sondern über USB vom Pi. Die
Massen müssen verbunden sein; ob das eine unerwünschte Brummschleife über die
Sensormasse erzeugt, ist zu prüfen.

## Dekodierung

Der HD44780 kennt Kommandos (RS = 0) und Daten (RS = 1), jeweils übernommen
mit der fallenden Flanke von E. Der Mitleser führt einen **Schattenpuffer**
von 16 Zeichen:

* `Clear Display` / `Return Home` → Puffer leeren, Cursor auf 0
* `Set DDRAM Address` → Cursorposition setzen
* Datenschreibvorgang → Zeichen an Cursorposition, Cursor weiterzählen
  (Richtung aus `Entry Mode Set`)

Ausgegeben wird nicht jeder Schreibvorgang, sondern der **Puffer nach
Ruhe**: wenn für eine definierte Zeit kein Schreibvorgang mehr kommt, ist die
Aktualisierung abgeschlossen und der String steht fest. Dazu gehört der
Zeitpunkt der **letzten** Flanke, nicht der ersten.

Rohbytes werden zusätzlich mitgeschrieben. Sie sind die Grundlage für die
Code-zu-Glyph-Paare, mit denen sich die Zeichensatz-ROM-Variante des
Controllers klären lässt (CLAUDE.md: bei Ziffern fällt eine falsch
angenommene Variante nicht auf, erst bei `°`/`Ω`/`µ`).

## Der kritische Punkt: das Glas hinkt dem Bus hinterher

Ein Zeichen-LCD dieser Bauart schaltet **langsam** — Einschwingzeiten im
Bereich von 100 ms und mehr sind für STN-Module bei Raumtemperatur normal, und
sie steigen bei Kälte deutlich. Zwischen „der Controller hat den neuen String
geschrieben" und „die Kamera sieht den neuen String" liegt also eine
nennenswerte Zeit, in der auf dem Glas ein **Mischbild** steht.

Wer in diesem Fenster ein Bild mit dem neuen String labelt, erzeugt genau die
Art von Fehler, die dieses Projekt nicht haben will: ein falsches Label, das
wie Wahrheit aussieht. Deshalb gehört zum Verfahren zwingend:

1. eine **gemessene** Einschwingzeit (Hochgeschwindigkeitsaufnahme eines
   Wechsels, Auswertung, wann das Glas stabil ist),
2. ein **Schutzintervall** um jeden Buswechsel herum,
3. Bilder innerhalb des Schutzintervalls werden **nicht** automatisch
   gelabelt. Sie bekommen `label_state="uncertain"` oder fallen raus — sie
   bekommen keinen geratenen Wert. Das entspricht dem `TRANSITION`-Zustand
   der Produktionskette und der Regel „Unlesbares ablehnen statt raten"
   ([AGENTS.md](../AGENTS.md)).

Solange diese Zeit nicht gemessen ist, ist das Verfahren nicht abnahmefähig.

## Zeitbasis

Der RP2040 zählt in seiner eigenen Zeitdomäne, die Kamera liefert
`SensorTimestamp` in CLOCK_BOOTTIME ([TIMING.md](TIMING.md), Messung M2 zur
Semantik ist offen). Ein Zeitstempel ohne `TimeBaseKind` ist nach
[AGENTS.md](../AGENTS.md) keine verwertbare Angabe, also braucht der Abgriff
eine eigene, benannte Zeitbasis und eine **gemessene** Umrechnung — nicht die
stillschweigende Annahme, Ankunftszeit auf dem Pi sei gleich Ereigniszeit.
Die unbekannte Unsicherheit ist `None`, nicht `0`.

Praktikabel: Ankunftszeit auf dem Pi in CLOCK_BOOTTIME nehmen und die
Transportverzögerung einmal messen und als Konstante mit Streuung
dokumentieren. Sauberer, falls nötig: ein gemeinsamer Synchronimpuls.

## Anbindung an den Sammelmodus

`DatasetStore` führt heute `expected_text`, `label_state`, `target_label`,
`label_history` und `revision` (siehe
[src/dispread/workbench/datasets.py](../src/dispread/workbench/datasets.py)).
Ein **Herkunftsmerkmal für das Label gibt es nicht**.

Das braucht es, bevor automatisch gelabelt wird: von Hand gelabelte und
buslabelte Proben müssen unterscheidbar bleiben. Sonst wandert ein
systematischer Fehler des Abgriffs unsichtbar in jede Benchmarkzahl, und der
Datensatz lässt sich nicht mehr entmischen. Umsetzung offen — entweder ein
eigenes Feld oder ein verpflichtender Eintrag in `label_history`.

Der so gewonnene Sollwert ist Datensatzmaterial. Er erreicht wie jedes andere
Label **nie** `ValueReader`, `ReleaseGate` oder die Produktionskette.

## Was dieser Abgriff nicht löst

Er vergrössert die Bilderzahl, nicht die Ziffernabdeckung. Der Brückensimulator
am GSV ist verklebt, der Anzeigewert steht damit künftig fest — neue Bilder
zeigen nichts, was die vorhandenen 11 bestätigten Proben nicht schon zeigen
(drei Cluster: ~`0.0004`, ~`0.948`, `1.05000`). Kein einziger negativer Wert
ist darunter, Werte ab 10 mV/V fehlen ebenfalls
([OQ-37](open-questions.md)). Eine hohe Trefferquote auf beliebig vielen
Bildern derselben Anzeige ist keine Aussage über die Erkennung im Feld. Das
ist [OQ-39](open-questions.md), und es bleibt offen.

## Reihenfolge, falls gebaut wird

1. Pegel und Busbreite am laufenden Gerät messen (Oszilloskop/Logikanalysator,
   **vor** jedem Anschluss eines RP2040).
2. Pinbelegung des Displaytech 161A gegen die HD44780-Reihenfolge prüfen.
3. Mitleser aufbauen, gegen den sichtbaren Displayinhalt verifizieren:
   Bus-String und abfotografierter String müssen über eine längere Strecke
   zeichenweise übereinstimmen, sonst ist die Dekodierung falsch.
4. Optische Einschwingzeit messen, Schutzintervall festlegen.
5. Zeitbasis und Transportverzögerung messen.
6. Erst danach: Herkunftsmerkmal im `DatasetStore`, dann automatisches Labeln.

Schritte 1, 3, 4 und 5 sind Messungen und gehören nach
[VALIDATION.md](VALIDATION.md) (Zahlen) und
[lab_journal.md](lab_journal.md) (Aufbau, Deutung).
