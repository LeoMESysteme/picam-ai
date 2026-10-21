# Displaybus-Abgriff als Ground-Truth-Quelle

**Abgleich: 2026-10-21.** Displaybus-Konzept vom 2026-09-22, nicht gebaut
und nicht vermessen. Der serielle Alternativweg ist inzwischen gebaut und
vermessen; dessen Belege gelten nicht automatisch für einen Bus-Abgriff.

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
>    Paare für eine direkte Gegenprobe der Zeichensatz-ROM-Variante des
>    Displaycontrollers (`°`/`Ω`/`µ`). Die jetzige Leserprüfung und
>    [Abnahme](VALIDATION.md) betreffen nur `mV/V`.
>
> Die Abschnitte „Der kritische Punkt" (optische Einschwingzeit),
> „Zeitbasis" und „Anbindung an den Sammelmodus" beschreiben auch
> Voraussetzungen für den seriellen Weg; sein heutiger Umsetzungsstand
> steht in den Nachträgen unten.

Diese Datei beschreibt, *wie* ein passiver Mitleser am Displaybus des GSV
aussehen würde und *was vorher gemessen sein muss*. Sie ist kein Bauplan und
keine Freigabe. Die Grenze des Verfahrens steht in
[OQ-39](open-questions.md).

## Wozu

Der Sammelmodus braucht zu jedem lesbaren Bild einen Sollwert
(`expected_text`). Er kann manuell eingegeben oder inzwischen aus dem
seriellen GSV-2AS-Strom abgeleitet werden (`sync-record.py`, `gate-label.py`,
`import-harvest.py`). Der Bus-Abgriff wäre eine zusätzliche Quelle; er ist
nicht nötig, um das bestehende Auto-Labeling zu nutzen.

Der Displaybus führt genau den Zeichenstring, den der Gerätecontroller in das
Displayregister schreibt — unabhängig davon, was das Gerät sonst nach aussen
gibt. Für das GSV-2AS ist diese Unabhängigkeit laut Anleitung nicht nötig
(ASCII-Ausgabe entspricht dem Anzeigewert; die führende Null wird auf
dem Glas jedoch unterdrückt, [OQ-41](open-questions.md#oq-41)); für ein
Gerät ohne solche Zusage wäre sie das entscheidende Argument.

## Was bekannt ist und was nicht

| Punkt | Stand |
| --- | --- |
| Anzeige ist ein Displaytech 161A, 16×1, HD44780-kompatibel | belegt (Platinenaufdruck, CLAUDE.md) |
| Verbindung ist ein 16-poliges Flachband zur Hauptplatine | belegt (Foto `gsv_front_geöffnet.jpg`) |
| Pinbelegung folgt der HD44780-Standardreihenfolge (1 VSS … 16 K) | **angenommen, nicht verifiziert** |
| Busbreite: 4-bit (D4–D7) oder 8-bit (D0–D7) | **ungemessen** |
| Logikpegel: 5 V oder 3,3 V | **ungemessen** |
| R/W fest auf Masse (nur Schreibzugriffe) | **ungemessen** |
| Bus-Aktualisierung und Zeichenadressierung | **ungemessen**; serielle Rate und optische Wechsel sind separat in [VALIDATION.md](VALIDATION.md) vermessen |
| Optische Einschwingzeit des LCD | Für den seriellen Ernteweg empirisch kalibriert; eigener Busbezug nicht vermessen (siehe unten) |

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

* `Clear Display` → Puffer leeren, Cursor auf die Ausgangsposition
* `Return Home` → Cursor und Anzeigeverschiebung zurücksetzen; vorhandene
  Zeichen bleiben erhalten
* `Set DDRAM Address` → Cursorposition setzen
* Datenschreibvorgang → Zeichen an Cursorposition, Cursor weiterzählen
  (Richtung aus `Entry Mode Set`)

Die Zuordnung der DDRAM-Adressen zu den 16 sichtbaren Zellen muss am
konkreten Modul geprüft werden. Ein linearer Puffer allein ersetzt diese
Zuordnung und die Behandlung von Anzeigeverschiebungen nicht.

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

Solange diese Zeit nicht gemessen ist, ist der Busweg nicht abnahmefähig.
Für den seriellen StreamCam-Ernteweg liegt seit 2026-09-29 eine empirische
Kalibrierung vor: Schutzintervall M = 325,9 ms und Anzeigeversatz 89,6 ms
([VALIDATION.md](VALIDATION.md), „Neue Kalibrierung (2026-09-29)“).
Das ist keine getrennte Messung aller Beiträge des Unsicherheitsbudgets und
keine Kalibrierung eines noch nicht gebauten Bus-Abgriffs.

## Zeitbasis

Der RP2040 würde in seiner eigenen Zeitdomäne zählen. Die aktive StreamCam
liefert V4L2-Pufferzeitstempel in CLOCK_MONOTONIC (`v4l2_monotonic`); der
Versatz nach BOOTTIME wird je Aufnahme gemessen
([TIMING.md](TIMING.md), [OQ-43](open-questions.md#oq-43)). Ein Zeitstempel ohne `TimeBaseKind` ist nach
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
Seit Schema 2 gibt es außerdem das Pflichtfeld `label_origin`
(`manual` oder `serial_ascii`) und `label_origin_detail`; Export-Schema 2
gibt die Herkunft weiter. Für serielle Labels sind Quelle, Schutzintervall,
Plateaugrenzen und Telegrammzahl Pflicht. `import-harvest.py` nutzt diesen
Weg bereits.

Ein zukünftiges Buslabel dürfte nicht als `serial_ascii` ausgegeben werden.
Es bräuchte eine explizite Herkunft samt Zeitbasis und Messbelegen sowie
eine passende Erweiterung der Schema-Prüfung. Ein solches Busformat ist
noch nicht implementiert.

Der so gewonnene Sollwert ist Datensatzmaterial. Er erreicht wie jedes andere
Label **nie** `ValueReader`, `ReleaseGate` oder die Produktionskette.

## Was dieser Abgriff nicht löst

Ein zusätzlicher Mitleser vergrößert zunächst die Bilderzahl. Er erzeugt
keine neue Geräte- oder Zeichensatzabdeckung. Die frühere Annahme eines
unveränderlichen Stimulus ist überholt: bewegliche Stimulatoren und
`set norm` erlauben inzwischen verschiedene Werte und Punktpositionen.
Das Format oberhalb 10 wurde am 2026-09-22 geprüft
([OQ-37](open-questions.md#oq-37)). Negative Werte bleiben am vorhandenen
Firmwarestand unbelegt ([OQ-39](open-questions.md#oq-39)).

Die Dot-Matrix-Abnahme vom 2026-09-30 umfasst mehrere Aufstellungen,
aber nur ein GSV-2AS und die Einheit `mV/V`. Beliebig viele weitere Bilder
desselben Geräts belegen keine Übertragbarkeit auf andere Geräte.

## Reihenfolge, falls gebaut wird

1. Pegel und Busbreite am laufenden Gerät messen (Oszilloskop/Logikanalysator,
   **vor** jedem Anschluss eines RP2040).
2. Pinbelegung des Displaytech 161A gegen die HD44780-Reihenfolge prüfen.
3. Mitleser aufbauen, gegen den sichtbaren Displayinhalt verifizieren:
   Bus-String und abfotografierter String müssen über eine längere Strecke
   zeichenweise übereinstimmen, sonst ist die Dekodierung falsch.
4. Optische Einschwingzeit messen, Schutzintervall festlegen.
5. Zeitbasis und Transportverzögerung messen.
6. Erst danach: busbezogene Herkunft und Zeitbasis im `DatasetStore`
   ergänzen, dann busbasiertes automatisches Labeln. Die serielle
   Labelherkunft existiert bereits.

Schritte 1, 3, 4 und 5 sind Messungen und gehören nach
[VALIDATION.md](VALIDATION.md) (Zahlen) und
[lab_journal.md](lab_journal.md) (Aufbau, Deutung).
