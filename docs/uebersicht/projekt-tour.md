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

Stand der Tour: 2026-10-12. Fertig sind **Überblick** und **Erkennung**; die
übrigen Kapitel sind angelegt und beschreiben, was sie zeigen werden.

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
Datensatz. Die Kapitel **Zeit**, **Training**, **Bedienung** und **Regeln**
sind geplant; ihre Karten zeigen, was sie enthalten werden.

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

Bei der Einrichtung legt der Bediener ein Viereck um das Display (die vier
türkisen Punkte). Dazu bestätigt er ein Profil: wie viele Zeichen das Display
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
gilt dann als unlesbar, und der Grund steht im Datensatz.

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
Gelesen werden nur die ersten neun Kästchen: das Vorzeichen, sieben
Kästchen für die Zahl samt Punkt und ein Kästchen, das leer sein muss.

Die Einheit (mV/V) wird nicht gelesen, sie steht im bestätigten Profil. So
kann keine falsch gelesene Einheit entstehen.

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
genau ein Punkt, sechs Ziffern, Kästchen 8 leer.

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

Jedes Bild liefert einen gelesenen Wert. Die Freigabe kann verlangen, dass
mehrere Bilder hintereinander denselben Wert zeigen (`confirm_frames`).
Solange das nicht erreicht ist, heißt der Wert **Übergang**: Die Anzeige
wechselt vielleicht gerade. In der Grundeinstellung genügt ein Bild; die
Bühne zeigt zur Verdeutlichung zwei.

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

Hält der Zustand an, wird aus „unlesbar“ **veraltet**. Das geschieht, sobald
seit dem letzten gültigen Wert mehr als `stale_after` vergangen ist
(vorläufig 0,5 s; bei 30 Bildern pro Sekunde wären das etwa 15 Bilder).

* **Unlesbar** heißt: Dieses eine Bild ließ sich nicht lesen.
* **Veraltet** heißt: Schon länger gibt es keinen aktuellen Wert mehr.

Wer die Daten auswertet, sieht so, ob nur einzelne Bilder fehlten oder ob die
Messung eine echte Lücke hat.

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
serielle Ausgabe für GSVmulti ist gebaut. Welches Telegrammformat GSVmulti
erwartet, ist aber noch nicht geklärt (OQ-07). Was tatsächlich über die
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
einem einzigen „Zeitstempel“ zusammengelegt.

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
Prüflings (M5). Sie ist noch nicht gemessen, und keine Software macht sie
kleiner.

Mehr dazu: [Messprogramm](../TIMING.md#messprogramm) ·
[OQ-02](../open-questions.md#oq-02) · [OQ-07](../open-questions.md#oq-07)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="training" data-label="Training" data-state="geplant" markdown="1">

## Training {#training}

<div class="tour-step" markdown="1">

### Geplant: vom Gerät zum Label {#training-geplant}

Das Kapitel wird zeigen, wie der GSV-2AS über RS232 (`set norm`) gezielt
andere Werte anzeigt und sein ASCII-Strom das Label liefert. Danach kommen
Ernteplan, Zuordnung mit Sicherheitsabstand, Vorlagen je Zeichen, die
ROM-Gegenprobe und die Abnahme.

Bis dahin: [Daten und Abnahme](daten-und-abnahme.md) ·
[Fortschritt Ernten/Training](../FORTSCHRITT.md) ·
[Datensatz sammeln](../anleitung/11-datensatz-sammeln.md)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="bedienung" data-label="Bedienung" data-state="geplant" markdown="1">

## Bedienung {#bedienung}

<div class="tour-step" markdown="1">

### Geplant: einrichten und lesen {#bedienung-geplant}

Das Kapitel wird die Einrichtung zeigen: Kamera am USB3-Port, Fokus,
Inbetriebnahme-Skript, Einrichtungsassistent, Bestätigen von Viereck und
Profil, dann Lesen mit Status.

Bis dahin: [Kamera-Livevorschau](../anleitung/10-kamera-livevorschau.md) ·
[Kamera-Inbetriebnahme](../CAMERA_COMMISSIONING.md)
{ .tour-more }

</div>

</section>

<section class="tour-chapter" data-chapter="regeln" data-label="Regeln" data-state="geplant" markdown="1">

## Regeln {#regeln}

<div class="tour-step" markdown="1">

### Geplant: was das System nicht tut {#regeln-geplant}

Das Kapitel wird die nicht verhandelbaren Regeln zeigen: keine unmarkierten
Altwerte, keine Korrektur mit dem Referenzwert, keine Glättung echter Sprünge,
Konfidenz ist keine Fehlerwahrscheinlichkeit. Dazu kommen die offenen Grenzen:
weitere Geräte, andere Lichtquellen und das GSVmulti-Protokoll.

Bis dahin: [Messpfad und Freigabe](messpfad.md) ·
[Offene Punkte](../open-questions.md)
{ .tour-more }

</div>

</section>

</div>
