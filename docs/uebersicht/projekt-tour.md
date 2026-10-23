---
hide:
  - navigation
  - toc
---

# Projekt-Tour

Die Projekt-Tour stellt das Projekt als Animation in Kapiteln vor. Jedes
Kapitel besteht aus kurzen Schritten, die nacheinander ablaufen oder sich
einzeln anwählen lassen. Beschriftete Kästen auf der Bühne mit „↗“ führen zur
passenden Doku-Seite. Die Bühne ist schematisch; Zahlen darauf sind
Beispielwerte, keine Messergebnisse. Maßgeblich bleiben
[Konzept.md](../../Konzept.md), der [Messpfad](messpfad.md) und die
[API-Referenz](../../api/index.md).

Stand der Tour: 2026-10-23. Alle sechs Kapitel sind fertig: Überblick,
Erkennung, Zeit, Training, Bedienung und Regeln.

<div class="tour" data-tour markdown="1">

<section class="tour-chapter" data-chapter="ueberblick" data-label="Überblick" markdown="1">

## Überblick {#ueberblick}

<div class="tour-step" markdown="1">

### Der Aufbau {#ueberblick-aufbau}

**Kurz:** Eine Kamera liest die Anzeige eines Messverstärkers ab, damit der
Wert automatisch und mit Zeitstempel im Rechner landet.

Links steht der Prüfling, hier ein GSV-2AS. Seine Anzeige ist ein
Punktraster-LCD. Eine Logitech StreamCam filmt sie über USB 3, und ein
Raspberry Pi 5 liest den Wert aus jedem Bild. Eingerichtet wird das Ganze im
Browser an der Werkbank. Am Ende soll der Wert seriell an das Programm
GSVmulti gehen. Diese Verbindung ist noch offen, weil das Datenformat fehlt,
das GSVmulti erwartet.

Die beschrifteten Etiketten auf der Bühne öffnen die Kapitel.

Mehr dazu: [Konzept](../../Konzept.md) · [Aktueller Stand](../status.md) ·
[Hardwareprofil](../HARDWARE_PROFILE.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Der Weg eines Werts {#ueberblick-weg}

**Kurz:** Aus jedem Kamerabild wird entweder ein geprüfter Wert oder eine
begründete Ablehnung, nie ein geratener Wert.

Der Punkt läuft den Weg eines Werts entlang: von der Anzeige über die Kamera
zum Pi. Dort entsteht ein Datensatz, der ins Audit-Protokoll (JSONL) geschrieben
wird, auch wenn der Wert abgelehnt wurde. Der Weg zu GSVmulti endet beim „?“,
weil das Datenformat noch offen ist.

Unten läuft die Kalibrierreferenz, also das Vergleichsgerät des Labors. Ihr
Wert wird erst **nachher** über die Zeitstempel zugeordnet. In die Erkennung
fließt er nie ein: Sonst könnte das System den abgelesenen Wert
„passend machen“, und die Kalibrierung wäre wertlos.

Im Messpfad arbeitet kein Sprachmodell und keine generative KI. Es ist eine
klassische Bildverarbeitung mit festen Regeln, die im Zweifel ablehnt.

Mehr dazu: [Messpfad und Freigabe](messpfad.md) ·
[Zeitstempel](zeitstempel.md) ·
[Konzept §7](../../Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Kapitel wählen {#ueberblick-kapitel}

**Erkennung** verfolgt ein Kamerabild Schritt für Schritt bis zum fertigen
Datensatz. **Zeit** erklärt die Uhren und warum Latenz keine Unsicherheit
ist. **Training** zeigt, wie das Gerät seine eigenen Labels liefert und wie
der Leser geprüft wird. **Bedienung** führt durch Aufstellen und Einrichten.
**Regeln** sammelt, was das System bewusst nicht tut.

Mehr dazu: [Lernpfad](../anleitung/README.md) · [Roadmap](../ROADMAP.md)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="erkennung" data-label="Erkennung" markdown="1">

## Erkennung {#erkennung}

<div class="tour-step" markdown="1">

### Bild und Zeitstempel {#erkennung-bild}

**Kurz:** Jedes Kamerabild bekommt eine laufende Nummer und den Zeitpunkt
seiner Aufnahme.

Die StreamCam liefert Bilder mit 1920 × 1080 Punkten. Jedes Bild wird
durchnummeriert (`frame_sequence`) und trägt den Zeitstempel, den der
Kameratreiber vergibt. Er stammt aus der Uhr CLOCK_MONOTONIC des Pi.

Die seriellen Daten im Labor stempelt der Pi mit einer anderen Uhr
(BOOTTIME). Damit beide vergleichbar sind, wird der Unterschied zwischen den
Uhren vorher gemessen und in `session.json` gespeichert. Fehlt diese Messung,
lehnt das System den Vergleich ab, statt zwei Uhren zu vermischen.

Mehr dazu: [Zeitstempel richtig lesen](zeitstempel.md) ·
[Zeitverhalten](../TIMING.md) · [Bildquellen (API)](../../api/frames.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Die bestätigte Anzeige {#erkennung-roi}

**Kurz:** Ein Mensch zeigt dem System einmal, wo die Anzeige ist und wie sie
aufgebaut ist.

Bei der Live-Einrichtung schlägt der Assistent das Viereck und Punktraster
vor; der Bediener prüft die Kontrollbilder (die vier türkisen Punkte) und
bestätigt ein Profil: wie viele Zeichen das Display
hat, welches Zahlenformat gilt und welche Einheit angezeigt wird. Danach
sucht das System die Anzeige nicht mehr selbst.

Warum so? Eine automatische Suche könnte die falsche Stelle finden, zum
Beispiel eine zweite Anzeige daneben. Ein bestätigtes Viereck ist ein
Nachweis, ein gefundenes nur ein Vorschlag.

Mehr dazu: [Geräteprofile](../anleitung/04-geraeteprofile.md) ·
[Kamera-Livevorschau](../anleitung/10-kamera-livevorschau.md) ·
[Konzept §4](../../Konzept.md#4-bedienkonzept-fur-wechselnde-gerate)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Nachführen {#erkennung-nachfuehrung}

**Kurz:** Wackelt die Kamera ein wenig, rückt das Viereck mit; bei einem
zu großen Ruck wird abgelehnt.

Jedes neue Bild wird mit dem Bild vom Moment der Bestätigung verglichen
(oben rechts). Das Verfahren heißt ECC-Bildregistrierung. Es misst, wie weit
sich die Anzeige verschoben hat, und das Viereck wird entsprechend
korrigiert. Verglichen wird immer mit diesem Bestätigungsbild, nie mit dem
vorigen Bild. Sonst würden sich kleine Messfehler über Stunden aufsummieren.

Die Korrektur hat Grenzen: höchstens 10 % Verschiebung und 3° Drehung
(vorläufige Werte). Bei einem größeren Ruck wird nicht korrigiert. Das Bild
gilt dann als unlesbar, und der Grund steht im Datensatz. Auch eine zu
geringe Bildähnlichkeit führt zu `tracking_lost`. Beim Werteplan am
2026-10-21 trat das nach einem großen Wertwechsel auf; die Nachführung
benutzt noch den Zifferninhalt. Wertunabhängiges Tracking ist offen
([OQ-26](../open-questions.md#oq-26)).

Mehr dazu: [Lokalisierung und Nachführung](../anleitung/07-lokalisierung.md) ·
[Geometrie (API)](../../api/geometrie.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Entzerren {#erkennung-entzerren}

**Kurz:** Das schräg gefilmte Display wird gerade gezogen, als hätte man es
von vorn fotografiert.

Die vier Ecken des Vierecks werden auf ein Rechteck abgebildet
(Vierpunkt-Transformation). Das geschieht in einem Schritt direkt aus dem
Originalbild. So wird das Bild nicht zweimal umgerechnet und dabei unscharf.
Ab hier sieht der Leser nur noch diesen geraden Ausschnitt.

Mehr dazu: [Geometrie (API)](../../api/geometrie.md) ·
[Optischer Aufbau](../OPTICAL_SETUP.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Das Zellraster {#erkennung-raster}

**Kurz:** Das Display besteht aus 16 Kästchen zu je 5 × 8 Punkten, und das
System weiß vorher, wo jedes Kästchen liegt.

Die Anzeige des GSV-2AS ist ein Displaytech 161A: 16 Zeichen in einer Zeile.
Klassifiziert werden die ersten neun Kästchen: das Vorzeichen, sieben
Kästchen für die Zahl samt Punkt und ein Kästchen, das leer sein muss.

Zusätzlich müssen die Restkästchen 13–15 leer sein. Die Einheit (mV/V)
wird nicht gelesen; sie steht im bestätigten Profil. Der Bediener muss
deshalb prüfen, dass sie zur sichtbaren Anzeige passt.

Mehr dazu: [Geräteprofile](../anleitung/04-geraeteprofile.md) ·
[OCR-Backends](../anleitung/08-ocr-backends.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Eine Zelle lesen {#erkennung-zelle}

**Kurz:** Jedes Kästchen wird mit gelernten Mustern aller möglichen Zeichen
verglichen. Gewinnt keines klar, wird abgelehnt.

Links misst der Leser die Helligkeit der 40 Punkte. Rechts vergleicht er
dieses Muster mit der gelernten Vorlage jedes Zeichens, das vorkommen darf:
0 bis 9, Punkt, Plus und Leerzeichen. Der Balken zeigt den Abstand: Je kürzer
er ist, desto ähnlicher sind sich die Muster.

Zwei Bedingungen müssen beide erfüllt sein:

* Das beste Zeichen ist nah genug, sein Balken endet also vor der
  gestrichelten Linie (`D_max`).
* Es liegt deutlich vor dem zweitbesten (Vorsprung `margin_min`).

Sonst heißt die Zelle „unbekannt“ oder „mehrdeutig“. Beide Schwellen stammen
aus dem Training. Auf der Bühne ist der Abstand vereinfacht gegen das
Musterzeichen aus dem Datenblatt gerechnet.

Mehr dazu: [OCR (API)](../../api/ocr.md) ·
[Daten und Abnahme](daten-und-abnahme.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Der ganze Wert {#erkennung-format}

**Kurz:** Erst wenn alle Kästchen sicher erkannt sind und zusammen eine
gültige Zahl ergeben, gilt der Wert als gelesen.

Zuerst prüft der Leser, ob das Bild überhaupt brauchbar ist. Höchstens 2 %
der Bildpunkte dürfen übersteuert sein, und der Kontrast muss reichen.
Danach muss die Zeichenfolge zur Formatregel des Geräts passen: Plus vorn,
genau ein Punkt, sechs Plätze für Ziffern oder führende Leerzeichen,
Kästchen 8 leer. Auch die Restkästchen müssen leer sein.

Ist auch nur ein Kästchen unsicher (unten das „?“), wird der **ganze** Wert
verworfen. Ein halber Wert wie „0.4?761“ wäre gefährlicher als gar keiner.

Mehr dazu: [Messpfad: was die Lesung belegen muss](messpfad.md#was-die-lesung-belegen-muss) ·
[OCR (API)](../../api/ocr.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Freigabe: gültig oder Übergang {#erkennung-freigabe}

**Kurz:** Ein gelesener Wert wird erst ausgegeben, wenn die Freigabe ihn für
gültig erklärt.

Jedes ausgewertete Bild liefert ein Leseergebnis. Die Live-Freigabe verlangt
zwei gleiche Bilder hintereinander (`LiveConfig.confirm_frames`); der
allgemeine `GateConfig`-Default ist ein Bild. Bis zur Bestätigung heißt der
Status **Übergang** mit Grund `awaiting_confirmation`.

Auch Mischziffern beim LCD-Umschalten können **Übergang** heißen
(`anzeige_wechselt`): Höchstens drei Zellen sind unlesbar, alle übrigen
stimmen mit der letzten Freigabe überein und diese liegt höchstens im
effektiven Übergangsfenster zurück. Im aktuellen Live-Pfad endet es nach
0,5 s, weil STALE Vorrang hat. Kontrast-, Zustands-, Einheiten- oder
Trackingfehler werden so nicht umgedeutet. Beide Übergangsarten geben
keinen Zahlenwert frei.

Springt der Messwert wirklich, folgt die Ausgabe dem Sprung, sobald er
bestätigt ist. Gemittelt oder geglättet wird nichts.

Den Referenzwert der Kalibrieranlage bekommt die Freigabe gar nicht erst
übergeben (unten). Sie kann den gelesenen Wert deshalb auch nicht
„passend machen“.

Mehr dazu: [Freigabe (API)](../../api/validate.md) ·
[Messpfad und Freigabe](messpfad.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Unlesbar und veraltet {#erkennung-veraltet}

**Kurz:** Ist die Anzeige nicht sicher lesbar, gibt das System keine Zahl
aus, auch nicht die zuletzt gelesene.

Ab dem zweiten Bild verdeckt eine Hand die Anzeige. Genauso gut könnten es
eine Spiegelung, Unschärfe oder ein Menü auf dem Display sein. Der Leser
lehnt diese Bilder ab, statt zu raten. Jedes solche Bild bekommt den Status
**unlesbar** und keinen Zahlenwert.

Der letzte gültige Wert (0.51230) wird **nicht** einfach weiter ausgegeben.
Niemand weiß, ob er hinter der Hand noch stimmt.

Bei einer anhaltenden Leseablehnung ohne blockierendes Statusflag wird aus
„unlesbar“ **veraltet**. Das geschieht, sobald
seit dem letzten gültigen Wert mehr als `stale_after` vergangen ist
(vorläufig 0,5 s; bei 30 Bildern pro Sekunde wären das etwa 15 Bilder).

* **Unlesbar** heißt: Dieses eine Bild ließ sich nicht lesen.
* **Veraltet** heißt: Schon länger gibt es keinen aktuellen Wert mehr.

Wer die Daten auswertet, sieht so, ob nur einzelne Bilder fehlten oder ob die
Messung eine echte Lücke hat. Trackingverlust läuft außerhalb des Gates:
Er bleibt im Audit `UNREADABLE`, ebenso blockierende Zustandsflags im Gate.
Bleibt dagegen ein neues Bild ganz aus, zeigt die Oberfläche den letzten
Datensatz als STALE; ohne neues Bild entsteht kein zusätzlicher Record.

Mehr dazu: [Freigabe (API)](../../api/validate.md) ·
[Konzept §7](../../Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Datensatz und Ausgabe {#erkennung-ausgabe}

**Kurz:** Jedes Ergebnis wird als Datensatz mit festen Feldern gespeichert,
auch jede Ablehnung.

Der `ValueRecord` hat die neun Felder aus Konzept §8: Bildnummer,
Aufnahmezeit, Wert, Einheit, Status und weitere. Die Konfidenz ist eine
Qualitätskennzahl. Sie sagt **nicht**, wie wahrscheinlich der Wert falsch
ist.

Jeder Datensatz geht als eine JSON-Zeile in das Audit-Protokoll. Die
serielle Senke als Baustein ist gebaut; der aktuelle Live-Lauf schreibt
ausschließlich das JSONL-Audit. Die Anbindung an GSVmulti ist noch offen,
weil dessen Telegrammformat nicht geklärt ist (OQ-07). Was tatsächlich über die
Leitung ging, hält ein eigener `TxReceipt` fest, getrennt vom Datensatz.

Mehr dazu: [Verträge (API)](../../api/vertraege.md) ·
[Ausgabe (API)](../../api/sink.md) ·
[GSVmulti-Protokoll](../GSVMULTI_PROTOCOL.md) ·
[OQ-07](../open-questions.md#oq-07)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="zeit" data-label="Zeit" markdown="1">

## Zeit {#zeit}

<div class="tour-step" markdown="1">

### Drei Uhren {#zeit-uhren}

**Kurz:** Kamera, Messverstärker und Referenz liefern ihre Daten mit
verschiedenen Uhren, und ein Zeitpunkt ist nur zusammen mit seiner Uhr
auswertbar.

Die StreamCam-Bilder tragen den Zeitstempel, den der Kameratreiber vergibt.
Er kommt aus der Uhr CLOCK_MONOTONIC des Pi; im Datensatz steht dazu die
Zeitbasis `v4l2_monotonic`. Die seriellen Telegramme des Messverstärkers
stempelt der Pi beim Empfang mit CLOCK_BOOTTIME. Beide Uhren zählen ab dem
Start des Pi. MONOTONIC hält aber im Ruhezustand (Suspend) an, BOOTTIME
läuft weiter.

Die Kalibrierreferenz hat eine dritte, eigene Uhr. Ob sie einen Trigger oder
einen Zeitstempel liefern kann, ist noch offen (OQ-03).

Warum so genau? Zwei Zeitpunkte aus verschiedenen Uhren darf man nicht
einfach voneinander abziehen. Deshalb trägt jeder Zeitstempel seine
Zeitbasis mit. Basen wie `synthetic` oder `file_mtime` gelten ausdrücklich
als „ohne Zeitaussage“.

Mehr dazu: [Zeitstempel richtig lesen](zeitstempel.md) ·
[Zeitverhalten](../TIMING.md) · [OQ-03](../open-questions.md#oq-03)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Kamerazeit umrechnen {#zeit-versatz}

**Kurz:** Bevor Kamerabild und Telegramm verglichen werden, rechnet das
System die Kamerazeit mit einem gemessenen Versatz in BOOTTIME um. Fehlt
der Versatz, wird abgelehnt.

Zu Beginn und am Ende jeder Aufnahme misst das Aufnahmeprogramm den Abstand
BOOTTIME − MONOTONIC. Es nimmt jeweils den Median aus mehreren, eng
geklammerten Einzelmessungen und schreibt beide Werte in `session.json`.
Umgerechnet wird nur an einer Stelle, in `records.to_boottime_ns`: Bildzeit
plus Startversatz.

Diese Funktion rät nicht. Fehlt der Versatz, lehnt sie ab. Weichen Start
und Ende um mehr als 1 ms voneinander ab, war der Pi vermutlich im
Ruhezustand, und sie lehnt ebenfalls ab. Ohne Suspend liegt der Versatz bei
wenigen Nanosekunden; die Bühne zeichnet ihn zur Verdeutlichung groß.

Mehr dazu: [Zeitstempel richtig lesen](zeitstempel.md) ·
[Verträge (API)](../../api/vertraege.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Telegramm und Anzeige {#zeit-anzeige}

**Kurz:** Zwischen dem Telegramm des Geräts und dem neuen Wert auf dem
Display vergeht Zeit. Wie viel, wird je Kamera gemessen und nicht
angenommen.

Fürs Ernten von Trainingsbildern sendet der GSV-2AS seinen Wert als
Telegramm, und die Kamera filmt dabei das Display. `display-offset.py` misst
nur, **wann** sich das Glas ändert, ohne zu lesen, was dort steht: Jedes
Bild bekommt einen Anteil p zwischen „ganz alter Wert“ (0) und „ganz neuer
Wert“ (1). Der Zeitpunkt bei p = 0,5 abzüglich der Telegrammzeit ist der
Anzeigeversatz δ.

`timing-calibration.py` schreibt δ und den Schutzabstand M nach
`var/calibration/timing-streamcam.json`, zusammen mit der USB-ID der Kamera
und den Quelldateien samt Prüfsumme. M ist der größte gemessene Wert. Beim
Ernten bekommen alle Bilder im Fenster ±M um einen Telegrammwechsel kein
Label. Ohne passende Datei startet `harvest.py` nicht.

Warum messen statt rechnen? Was der Kamera-Zeitstempel genau markiert
(Belichtung oder Pufferempfang), ist nicht geklärt (OQ-43). Die Messung
deckt das empirisch ab.

Mehr dazu: [Zeitverhalten](../TIMING.md) ·
[OQ-43](../open-questions.md#oq-43) ·
[Daten und Abnahme](daten-und-abnahme.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Latenz ist nicht Unsicherheit {#zeit-latenz}

**Kurz:** Eine feste Verzögerung lässt sich herausrechnen, eine schwankende
nicht. Deshalb zählt die Streuung, nicht der Mittelwert.

Der Datensatz trägt die **Aufnahmezeit** (`capture_timestamp`). Wie lange
Lesen und Freigabe danach rechnen, verschiebt sie nicht; diese Rechenzeit
steht getrennt im `PipelineTrace`, die Fertigstellung in
`result_timestamp`. Wartet die Freigabe auf mehrere gleiche Bilder, steht
diese Wartezeit eigens in `confirmation_span_ns`. Die Felder werden nie zu
einem einzigen „Zeitstempel“ zusammengelegt. Die aktuelle Kennzeichnung
der Ergebniszeit übernimmt noch die Basis des Frames, obwohl die Uhr
MONOTONIC ist. Außerhalb des V4L2-Pfads ist sie deshalb nicht zuverlässig;
Rechenzeit nur aus den gleichbasigen Trace-Marken bestimmen
([OQ-45](../open-questions.md#oq-45)).

Das Beispiel aus TIMING.md rechts: Konstante 200 ms verschieben den
Zeitbezug, verschlechtern ihn aber nicht. 50 ms ± 40 ms sind trotz kleinerem
Mittelwert schlechter, weil die Streuung ins Unsicherheitsbudget eingeht.
Jeder Bericht weist deshalb Mittelwert und Streuung getrennt aus.

Mehr dazu: [TIMING: Grundsatz](../TIMING.md#grundsatz-latenz-ist-nicht-zeitunsicherheit) ·
[Pipeline (API)](../../api/pipeline.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Prüfling und Referenz zuordnen {#zeit-zuordnung}

**Kurz:** Am Ende sollen Prüfling und Referenz über ihre Zeitstempel
zusammengeführt werden. Mehrere Bausteine dafür sind noch offen.

Die Werte des Prüflings liegen mit Aufnahmezeit im JSONL-Audit. Die
Referenz misst mit ihrer eigenen Uhr. Die Zuordnung geschieht nachträglich
und außerhalb der Erkennung. Die Erkennung bekommt den Referenzwert nie zu
sehen.

Belastbar ist die Zuordnung erst, wenn geklärt ist,

* wie die Referenz zu einem Zeitstempel kommt (OQ-03),
* welche Abweichung zulässig ist (OQ-02),
* was der Kamera-Zeitstempel bedeutet (OQ-43),
* ob GSVmulti die gelieferte Aufnahmezeit überhaupt verwendet (Versuch M8,
  blockiert durch OQ-07).

Der größte Einzelbeitrag ist vermutlich die Displayaktualisierung des
Prüflings (M5). Der gemessene Anzeigeversatz und die Live-Wechselzeiten
enthalten mehrere Beiträge; M5 ist damit noch nicht isoliert bestimmt.
Software beseitigt die physikalische Verzögerung der Anzeige nicht.

Die optionale `reference.jsonl` des Live-Laufs zeichnet bereits den
seriellen GSV-2AS-Strom in BOOTTIME auf. Das ist eine Gegenprobe zum
optischen Wert desselben Geräts, noch keine angebundene Kalibrierreferenz.
`scripts/live-reference-eval.py` vergleicht sie nachträglich. Die
Timing-Kalibrierung wird im Lauf dokumentiert, nicht auf den Wert angewandt.

Mehr dazu: [Messprogramm](../TIMING.md#messprogramm) ·
[OQ-02](../open-questions.md#oq-02) · [OQ-07](../open-questions.md#oq-07)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="training" data-label="Training" markdown="1">

## Training {#training}

<div class="tour-step" markdown="1">

### Warum Daten nötig sind {#training-vorlagen}

**Kurz:** Der Leser vergleicht jedes Kästchen mit einer gelernten Vorlage je
Zeichen. Diese Vorlagen entstehen aus echten Kamerabildern.

Das Datenblatt des Displays zeigt jedes Zeichen als ideales Punktmuster
(links). Die Kamera sieht es nie so: Das Bild ist etwas unscharf, schräg oder
ungleich beleuchtet (Mitte). Deshalb lernt das System für jedes Zeichen, wie
es auf echten Bildern aussieht, und bildet daraus eine Vorlage (rechts).

Der Leser kennt 13 Zeichen: die Ziffern 0 bis 9, Punkt, Plus und das leere
Kästchen. Für jedes braucht es genug echte Beispiele mit dem richtigen
Label.

Mehr dazu: [OCR-Backends](../anleitung/08-ocr-backends.md) ·
[Daten und Abnahme](daten-und-abnahme.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Das Gerät als Lehrer {#training-lehrer}

**Kurz:** Der Messverstärker sagt über seine serielle Schnittstelle selbst,
welchen Wert er gerade anzeigt. Damit beschriftet sich jedes Bild fast von
allein.

Das Ernte-Skript schickt dem GSV-2AS über RS232 den Befehl `set norm`. Er
ändert den Normierungsfaktor, und die Anzeige springt auf einen neuen Wert
(Anzeige = Faktor × Messwert). So entstehen viele verschiedene Ziffern, ohne
dass jemand am Aufbau etwas verstellt. Das Zahlenfeld umfasst sechs Plätze für Ziffern und führende Leerzeichen;
auch der Punkt kann wandern.

Zugleich sendet das Gerät seinen Wert als ASCII-Text. Dieser Text wird zum
Label der Kamerabilder aus derselben Zeit.

So entstehen Labels für Trainingsdaten. Im Live-Betrieb kann derselbe
serielle Strom getrennt als Referenz-Audit mitgeschrieben werden, auch mit
einem Werteplan. Er liefert dort keine Labels an den Leser und korrigiert
keinen gelesenen Wert: Der Leser bekommt ausschließlich das Bild und Layout.

Mehr dazu: [Datensatz sammeln](../anleitung/11-datensatz-sammeln.md) ·
[Fortschritt Ernten/Training](../FORTSCHRITT.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Ernte: nur sichere Bilder {#training-ernte}

**Kurz:** Ein Bild bekommt nur dann ein Label, wenn es sicher mitten in
einem stabilen Anzeigewert liegt. Alles am Rand eines Wechsels wird
verworfen.

Eine Ernte folgt einem festen Plan (`scripts/harvest.py`). Die Anzeige hält
jeden Wert einige Sekunden (Vorgabe 4 s). Aufeinanderfolgende Faktoren
liegen mindestens um das 1,3-Fache auseinander, damit jeder Schritt ein
deutlicher Wechsel ist. `sync-record.py` zeichnet Kamerabilder und
Telegramme gemeinsam auf.

Danach entscheidet `gate-label.py`: Bilder kurz vor und nach einem Wechsel
bekommen kein Label. Sie liegen innerhalb des Sicherheitsabstands **M**
(roter Bereich), denn dort könnte die Anzeige schon oder noch den anderen
Wert zeigen. M wird für jede Kamera gemessen und steht in ihrer
Timing-Kalibrierung; ohne passende Kalibrierung startet die Ernte nicht.
Auch Lücken im Telegrammstrom und das offene Ende des letzten Werts werden
verworfen.

Mehr dazu: [Kapitel Zeit: Telegramm und Anzeige](#zeit-anzeige) ·
[Zeitverhalten](../TIMING.md) ·
[Zeitstempel richtig lesen](zeitstempel.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Vorlagen lernen und gegenprüfen {#training-lernen}

**Kurz:** Aus vielen beschrifteten Kästchen entsteht je Zeichen eine
Vorlage. Sie muss zum Zeichensatz aus dem Datenblatt passen, sonst wird gar
nichts gespeichert.

Der Import schneidet aus jedem beschrifteten Bild die 16 Kästchen aus. Bilder
mit schlechter Bildgüte oder mit Kästchen, die nicht zu den anderen passen,
fliegen raus. Aus den übrigen Kästchen eines Zeichens berechnet das Training
die Vorlage.

Dann folgt die **ROM-Gegenprobe**: Die Vorlage wird mit dem Muster aus dem
Datenblatt des Displaycontrollers (HD44780) verglichen. Weicht sie in mehr
als einem Punkt ab, schreibt `dotmatrix-train.py` keine Vorlagen (Exit 3).
Eine solche Abweichung deutet auf falsche Labels oder ein verschobenes
Raster hin. Die Schwellen werden dann nicht nachgebessert.

Zum Schluss legt das Training die beiden Schwellen des Lesers fest
(`D_max` und `margin_min`, Formel `thresholds_v1`). Die fertigen Vorlagen
werden mit Prüfsumme eingefroren.

Mehr dazu: [OCR (API)](../../api/ocr.md) ·
[Validierung](../VALIDATION.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Unabhängig prüfen {#training-abnahme}

**Kurz:** Ob der Leser taugt, zeigt erst ein Test an Aufstellungen, die das
Training nie gesehen hat, mit einem vorher festgelegten Kriterium.

Während der Entwicklung misst `loo` (leave one group out): Jede Aufstellung
wird einmal zurückgehalten, die Vorlagen werden nur aus den übrigen gelernt
und an der zurückgehaltenen geprüft.

Für Abnahme 3 (2026-09-30) wurden die Vorlagen zuerst eingefroren. Danach
entstanden zwei neue Aufstellungen: `ab5` fast frontal und gedreht, `ab6`
schräg von links. Das Kriterium stand vorher fest: 0 falsch, höchstens 20 %
abgelehnt. Ergebnis: **215 Proben richtig, 0 falsch, 0 abgelehnt** über 85
Anzeigewerte (Plateaus). Die statistische Obergrenze der Fehlerrate liegt
bei 3,5 % (95 %).

Die Grenzen gehören zum Ergebnis: Es gibt nur ein Gerät, nur Raumlicht, nur
die Einheit mV/V und keine negativen Werte. Die neuen Aufstellungen stammen
vom selben Gerät; ein zweites Gerät fehlt noch.

Mehr dazu: [Validierung](../VALIDATION.md) ·
[Daten und Abnahme](daten-und-abnahme.md) ·
[Fortschritt Ernten/Training](../FORTSCHRITT.md)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="bedienung" data-label="Bedienung" markdown="1">

## Bedienung {#bedienung}

<div class="tour-step" markdown="1">

### Kamera aufstellen {#bedienung-kamera}

**Kurz:** Die Kamera steht möglichst gerade vor der Anzeige und hängt an
einem blauen USB3-Anschluss des Pi.

Die StreamCam liefert die volle Auflösung von 1920 × 1080 Punkten nur im
Format YUYV und nur über USB3. An einem USB2-Anschluss fällt sie auf
kleinere Bilder zurück, und die Bildquelle bricht dann ab. Den Fokus stellt
die Software ein, nicht die Hand: Erst wird der Autofokus ausgeschaltet,
dann ein fester Wert gesetzt. Am GSV-Aufbau war 48 der beste Wert.

Warum gerade davor? Der Einrichtungsassistent findet das Punktraster bei
einer frontalen Aufstellung selbst. Schräge Aufstellungen lehnt er bisher ab;
die richtet man noch von Hand ein.

Mehr dazu: [Hardwareprofil](../HARDWARE_PROFILE.md) ·
[Optischer Aufbau](../OPTICAL_SETUP.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Inbetriebnahme prüfen {#bedienung-inbetriebnahme}

**Kurz:** Ein Prüfskript sagt in einer Minute, ob die Kamera einsatzbereit
ist.

`./scripts/camera-commissioning.sh` geht sechs Punkte durch: Ist das
Werkzeug `v4l2-ctl` da? Ist die StreamCam angeschlossen? Läuft sie über USB3?
Bietet sie YUYV in 1920 × 1080 an? Lassen sich Autofokus und Fokuswert
setzen und zurücklesen? Kommt ein Testbild in voller Größe an?

Jede Zeile endet mit OK, WARNUNG oder FEHLER. Einsatzbereit (Exit 0) ist
die Kamera nur ohne FEHLER. Ein USB2-Anschluss ist dort nur eine Warnung,
für die volle Auflösung aber trotzdem zu wenig. Die geänderten Regler stellt
das Skript am Ende wieder zurück.

Mehr dazu: [Kamera-Inbetriebnahme](../CAMERA_COMMISSIONING.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Der Einrichtungsassistent {#bedienung-assistent}

**Kurz:** Der Assistent erledigt Fokus, Standbilder, Punktraster und
Prüfungen und macht daraus einen Vorschlag.

`harvest-setup.py assist` sucht zuerst den schärfsten Fokuswert. Dann nimmt
er zwei Standbilder im Abstand von mindestens 30 Sekunden auf: So fällt auf,
wenn sich Kamera oder Gerät bewegt haben. Danach legt er das Punktraster über
die Anzeige. Damit er weiß, was die Anzeige gerade zeigen sollte, liest er
den Wert über die serielle Schnittstelle des GSV-2AS mit.

Danach prüft er Kontrast, Kanten, Rahmen, Glanz, Auflösung, Raster,
Stabilität und den Versatz des Rasters. Jede Prüfung meldet OK, WARNUNG oder
FEHLER. Am Ende stehen ein Vorschlag (`proposal.json`) und Kontrollbilder,
auf denen man das Raster sieht.

Im Live-Browser unter `/live` nutzt die Einrichtung dieselben Messbausteine
über den gemeinsamen `CameraOwner`. Dort prüft zusätzlich `gegenlesen` den
Leser am Standbild; schwankende Zellen können maskiert werden. Für einen
normalen Lauf muss diese Lesesperre aufgehoben sein.

Mehr dazu: [Datensatz sammeln](../anleitung/11-datensatz-sammeln.md) ·
[Kamera-Workbench](../anleitung/10-kamera-livevorschau.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Der Mensch bestätigt {#bedienung-bestaetigen}

**Kurz:** Erst wenn ein Mensch die Kontrollbilder angesehen und bestätigt
hat, wird aus dem Vorschlag ein gültiges Profil.

Mit `harvest-setup.py confirm` wird der Vorschlag zum Profil der Sitzung.
Darin stehen das Viereck, das Raster, die Kameraeinstellungen und wer
bestätigt hat. Steht bei einer Prüfung FEHLER, geht das nur mit einer
ausdrücklichen Begründung (`--override-reason`), und die Begründung wird im
Profil gespeichert. Gibt es gar keine Prüfungen, steht im Profil ehrlich
„NICHT_GEPRUEFT“.

Findet der Assistent bei einer schrägen Aufstellung keine eindeutige
Startlage, richtet man das Raster von Hand mit `profile-regrid.py still`
ein und bestätigt danach genauso.

Die Live-Oberfläche bestätigt getrennt mit Namen sowie geprüfter Einheit
und Format. FEHLER der Einrichtung lassen sich dort nicht übergehen;
WARNUNG verlangt eine ausdrückliche Kenntnisnahme. Eine angebotene
angepasste Lesetoleranz setzt eine serielle Gegenprobe und ein eigenes
Häkchen voraus. Sie ist nur für diese Aufstellung geprüft und bleibt als
**nicht validiert** in Oberfläche und Laufmetadaten gekennzeichnet.

Mehr dazu: [Geräteprofile](../anleitung/04-geraeteprofile.md) ·
[Datensatz sammeln](../anleitung/11-datensatz-sammeln.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Werkbank und Betrieb {#bedienung-werkbank}

**Kurz:** `/live` führt von der Einrichtung über die namentliche Bestätigung
zum laufenden Dot-Matrix-Lesen mit der StreamCam und einem Audit je Lauf.

`dispread serve` hält die StreamCam über einen gemeinsamen `CameraOwner`.
Die geschützte Live-Seite steuert Einrichtung, Bestätigung, Laufstart und
Stopp. Die ältere Werkbank erhält gedrosselte Bilder desselben Owners;
Kamerabedienung erfolgt über `/live`. Andere Kameraprozesse bekommen während
der Serverlaufzeit „belegt“.

Jeder Lauf schreibt `records.jsonl` und `session.json` unter
`var/live/<sitzung>/run-NN/`. Optional kommt der getrennte serielle
GSV-2AS-Strom als `reference.jsonl` hinzu. Ein Werteplan mit `set norm` und
anschließender Rückstellung dient kontrollierten Gegenproben; das Planende
stoppt den Lauf nicht automatisch.

Bei Lesesperre ist nur ein ausdrücklich markierter Testlauf möglich
(`TESTLAUF.json`, Banner). Vermutungen zu abgelehnten Bildern sind als nicht freigegeben beschriftet.
Jede Gate-Freigabe wird vor dem Audit als unlesbar ohne Zahlenwert
protokolliert; die Oberfläche zeigt niemals gültige Testlaufwerte.
Die ursprüngliche Gate-Entscheidung bleibt eine getrennte Leser-Diagnose.
Testläufe sind von Messnachweisen ausgeschlossen; die technische
Freigabesicherung ist umgesetzt ([OQ-44](../open-questions.md#oq-44)).

Der Live-Pfad ist am Aufbau gelaufen, aber noch nicht umfassend abgenommen:
Große Wertwechsel können die Nachführung verlieren lassen (OQ-26), die
angepasste Toleranz bleibt nicht validiert. Die Ausgabe an GSVmulti bleibt
offen, bis das Telegrammformat feststeht (OQ-07).

Mehr dazu: [Kamera-Workbench](../anleitung/10-kamera-livevorschau.md) ·
[Arbeitsliste](../../TODO.md) · [Betrieb](../anleitung/09-betrieb.md)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="regeln" data-label="Regeln" markdown="1">

## Regeln {#regeln}

<div class="tour-step" markdown="1">

### Kein Altwert ohne Markierung {#regeln-altwert}

**Kurz:** Ein alter Wert darf nie so aussehen, als sei er aktuell.

Was könnte passieren? Die Kamera verliert die Anzeige, und die Ausgabe
wiederholt einfach den letzten Wert. In den Daten sähe das aus wie eine
ruhige, gültige Messung, obwohl in Wahrheit niemand mehr hinschaut.

Darum ist es zweimal gesperrt. Bei einer fortgesetzten Leseablehnung ohne
blockierendes Statusflag stellt die Freigabe nach `stale_after` auf
**veraltet**. Und ein Datensatz mit dem Status
„veraltet“ oder „unlesbar“ **und** einer Zahl lässt sich gar nicht erst
anlegen: Der Konstruktor von `ValueRecord` bricht dann mit einem Fehler ab.
Beides prüfen eigene Tests. Bei Trackingverlust entsteht unmittelbar
`UNREADABLE`; ohne neue Kamerabilder kennzeichnet die Oberfläche das Alter
als STALE, ohne einen weiteren Bilddatensatz zu erfinden.

Mehr dazu: [Nicht verhandelbar (AGENTS.md)](../../AGENTS.md#nicht-verhandelbar-konzeptmd-7) ·
[Verträge (API)](../../api/vertraege.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Die Referenz korrigiert nie den Prüfling {#regeln-referenz}

**Kurz:** Der Wert der Kalibrieranlage kommt an Leser und Freigabe gar nicht
heran.

Was könnte passieren? Liest das System „0.4?761“ und kennt den
Referenzwert 0.46761, wäre es verlockend, die Lücke passend zu füllen. Dann
würde die Kalibrierung den Prüfling mit sich selbst vergleichen und immer
bestehen.

Darum hat der Leser nur Bild und Layout als Eingang (`read(crop, layout)`),
die Freigabe nur das Leseergebnis und die Aufnahmezeit
(`evaluate(read, capture_ns)`). Ein Test prüft genau diese Signaturen. Ein
zweiter Test lässt dieselbe Kette zweimal laufen, einmal mit einem um 20 %
verfälschten Referenzwert in den Bilddaten. Die Datensätze müssen gleich
sein, und sie sind es.

Mehr dazu: [Freigabe (API)](../../api/validate.md) ·
[Konzept §7](../../Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Echte Sprünge bleiben Sprünge {#regeln-spruenge}

**Kurz:** Springt der Messwert, springt auch die Ausgabe, ohne Mittelung und
ohne Begrenzung.

Was könnte passieren? Eine „Plausibilitätsregel“ hält einen Sprung von 1 auf
500 für einen Lesefehler und glättet ihn weg. Dann verschwindet genau das
Ereignis, das man im Labor sehen will, etwa eine Lastspitze.

Darum gibt es keinen Glättungsfilter. Die einzige erlaubte Verzögerung ist
die Mehrbildbestätigung (`confirm_frames`), und ihre Dauer steht im Datensatz
(`confirmation_span_ns`). Ein Test schickt die Folge 1, 1, 500, 500, −500, 0
durch die Freigabe und verlangt sie unverändert zurück. Das belegt die
Freigabelogik. Im gesamten Live-Pfad kann die Nachführung bei großen
Wertwechseln noch ausfallen (OQ-26); dann gibt es eine markierte Messlücke.

Mehr dazu: [Freigabe (API)](../../api/validate.md) ·
[Messpfad und Freigabe](messpfad.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Konfidenz ist keine Fehlerwahrscheinlichkeit {#regeln-konfidenz}

**Kurz:** Eine Konfidenz von 0,31 heißt **nicht** „31 % Risiko“ und auch
nicht „69 % sicher“.

Was könnte passieren? Jemand liest die Konfidenz als Wahrscheinlichkeit und
verlässt sich auf eine Fehlerquote, die nie gemessen wurde.

Darum ist sie ausdrücklich nur eine Qualitätskennzahl. Beim
Punktraster-Leser ist sie der knappste Abstand zu einer Schwelle, gemessen in
Einheiten der Vorlagen. Jeder Leser meldet
`declares_confidence_calibrated = False`, und Tests halten das fest. Auf
True darf das erst wechseln, wenn eine Kalibriermessung in der Validierung
steht.

Mehr dazu: [OCR (API)](../../api/ocr.md) ·
[Validierung](../VALIDATION.md)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Kein erfundenes Protokoll {#regeln-protokoll}

**Kurz:** Solange niemand weiß, welches Telegramm GSVmulti erwartet, wird
keines geraten.

Was könnte passieren? Ein ausgedachtes Format würde in Tests grün
erscheinen, in Berichten als „Ausgabe funktioniert“ stehen und erst am
Laborplatz auffallen.

Darum wirft der Platzhalter für das echte GSVmulti-Format
(`GsvAsciiFormatter`) absichtlich einen Fehler und verweist auf OQ-07. Zum
Testen der Kette gibt es nur ein CSV-Format, das sichtbar als vorläufig
markiert ist (`provisional = True`). Nach der Projektregel in `AGENTS.md`
gehört diese Markierung in jedes Laufergebnis. Belastbar wäre ein Mitschnitt: ein echtes GSV-Gerät an
GSVmulti anschließen und den Datenstrom aufzeichnen.

Mehr dazu: [GSVmulti-Protokoll](../GSVMULTI_PROTOCOL.md) ·
[OQ-07](../open-questions.md#oq-07)
{ .tour-more }

</div>

<div class="tour-step" markdown="1">

### Was noch nicht geprüft ist {#regeln-grenzen}

**Kurz:** Der Leser ist für ein Gerät belegt. Alles darüber hinaus ist offen
und wird auch so genannt.

Belegt ist der Punktraster-Leser am GSV-2AS mit dem Display Displaytech 161A.
Abnahme 3 ergab 215 von 215 Proben richtig, 0 falsch und 0 abgelehnt; die
Obergrenze der Fehlerrate liegt bei 3,5 %.

Offen sind:

* weitere Messverstärker (GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI, AST-Geräte),
* andere Lichtquellen,
* das Minuszeichen: Dieses Gerät zeigt nie negative Werte, deshalb kennt der
  Leser nur „+“,
* Freigabeschwellen an realen Geräten (OQ-14),
* das GSVmulti-Format (OQ-07),
* die Nachführung bei großen Wertwechseln (OQ-26) und die vollständige
  Live-Abnahme,
* eine belastbare Validierung der angepassten Lesetoleranz.

Wer die Werte freigibt, nennt diese Grenzen mit.

Mehr dazu: [Validierung](../VALIDATION.md) ·
[Offene Punkte](../open-questions.md) ·
[Fortschritt Ernten/Training](../FORTSCHRITT.md)
{ .tour-more }

</div>

</section>

</div>
