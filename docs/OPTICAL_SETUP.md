# Optischer Aufbau

Setzt Konzept.md §9 um. Kurzfassung: **auch KI braucht lesbare Bilder.**

## Warum das kein Nebenthema ist

Die Messreihe vom 2026-09-07 ([VALIDATION.md](VALIDATION.md)) zeigt eine klare
Rangfolge der Störungen:

| Störung | Verhalten des Dekoders |
| --- | --- |
| Rauschen σ=0,3 | fehlerfrei |
| Unschärfe bis σ=10 | fehlerfrei |
| Unschärfe σ=12–15 | Ablehnung, **keine** stillen Fehlablesungen |
| **starker Glanz** | **2 von 40 stillen Fehlablesungen** |

Unschärfe und Rauschen versagen gutartig — das System lehnt ab. **Reflexionen
sind der gefährliche Fall**, weil dabei Werte entstehen, die als gültig
ausgegeben und trotzdem falsch sind. Abschirmung und Beleuchtung sind damit
Voraussetzung, nicht Feinarbeit.

## Halterung

* Verstellbar und **stabil**. Nach der Einrichtung darf sich nichts mehr
  bewegen — eine Kameraverschiebung während der Messung führt zum Verlust der
  bestätigten ROI und damit zu ungültigen Werten.
* Reproduzierbar: wiederkehrende Geräte sollen ohne Neuausrichtung wieder
  passen. Der Bildausschnitt wird trotzdem jedes Mal neu bestätigt
  (Konzept §4).
* Der Arbeitsabstand muss zum **manuellen Fokus** der AI Camera passen. Bei der
  ersten Aufnahme am 2026-09-07 war der Fokus deutlich verstellt — das
  Fokuswerkzeug liegt dem Modul bei. Unter etwa 20 cm kann das Objektiv nicht
  scharfstellen, egal wie weit man dreht (Herstellerangabe 20 cm – ∞).
* **Stand 2026-09-08: Fokus eingestellt, aber nicht gesichert.** Schärfe 216,6
  gegenüber 11,53 in der Ausgangslage; am Testgerät 37 px Ziffernhöhe. Objektiv
  gegen Verdrehen sichern (Konterring, sonst ein Tropfen Schraubensicherung) und
  die Halterung starr ausführen — sonst ist die Einstellung beim nächsten
  Anstoßen verloren. Zahlen in [VALIDATION.md](VALIDATION.md).

## Ziffernhöhe im Bild

Zielmarke: **≥ 30 px Ziffernhöhe** im verwendeten Stream.

Am 2026-09-08 gemessen: **960×720 erreicht diese Marke** am Testgerät mit
≈ 37 px, ohne `ScalerCrop` und ohne den höher auflösenden Modus. Damit ist die
Vorschaugröße für die Auslesung brauchbar — was wichtig ist, weil die großen
Sensormodi im Verdacht stehen, den Treiberfehler aus
[OQ-22](open-questions.md) häufiger auszulösen. Reicht die Ziffernhöhe an einem
Gerät nicht, ist `ScalerCrop` der Weg: digitaler Ausschnitt auf die Anzeige bei
gleicher Ausgabegröße; der Sensormodus bleibt ohnehin 2028×1520.

Begründung: der Dekoder tastet je Ziffernzelle sieben Segmentpositionen mit
einem Fenster von ±6 % der Zellenbreite ab. Bei deutlich kleineren Ziffern
fallen benachbarte Segmente in dasselbe Fenster, und der Kontrast zwischen
aktiv und inaktiv bricht zusammen.

Sensormodi: 2028×1520 bei 30 fps oder 4056×3040 bei 10 fps. Der höher
auflösende Modus bringt Ziffernhöhe, kostet aber Bildrate — was nur dann
relevant ist, wenn die Anzeige selbst schneller aktualisiert (Konzept §6: ein
höherer Takt liefert keine zusätzlichen unabhängigen Messwerte, wenn die
Anzeige langsamer ist).

## Beleuchtung und Reflexionen

* **Reproduzierbar** beleuchten, nicht Umgebungslicht ausgeliefert sein.
* Abschirmung gegen Streulicht und Spiegelbilder ist die erste Maßnahme.
* Polarisationsfilter können Spiegelungen reduzieren — **aber** Konzept §9
  weist ausdrücklich darauf hin, dass ihr Einfluss auf den LCD-Kontrast zu
  prüfen ist. LCDs sind selbst polarisiert; ein falsch orientierter Filter kann
  die Anzeige unlesbar machen. Beide Varianten messen und in
  [lab_journal.md](lab_journal.md) festhalten.
* Der Dekoder meldet den Anteil gesättigter Bildpunkte und setzt ab 2 % das
  Flag `glare`, das die Freigabe blockiert. Das ist eine Rückmeldung über den
  **Aufbau**, kein Ersatz für ihn: ein Aufbau, der das Flag regelmäßig auslöst,
  ist nicht brauchbar, auch wenn nichts Falsches gesendet wird.

## Belichtung fixieren

Nach der Einrichtung sollen Belichtungszeit und Verstärkung **konstant
bleiben** und ins Geräteprofil geschrieben werden. Eine mitlaufende
Automatik verändert die gemessenen Segmenthelligkeiten und damit genau die
Evidenz, die die Freigabe bewertet.

Gemessene Startwerte am 2026-09-07 (Automatik, Innenraum): `ExposureTime`
21,06 ms, `AnalogueGain` 1,50, `FrameDuration` 33,31 ms.

## Multiplexing und Flimmern

Viele Anzeigen multiplexen die Stellen. Ist die Belichtungszeit kürzer als eine
Multiplexperiode, erscheinen Stellen unvollständig oder gar nicht — der Dekoder
sieht ein Segmentmuster, das in keiner Tabelle steht, und lehnt ab.

* Belichtungszeit **≥ Multiplexperiode** wählen. Der richtige Wert ist
  experimentell je Gerätetyp zu bestimmen und gehört ins Profil.
* Ziffernwechsel erzeugen Übergangsframes mit überlagerten Zeichen. Die sind
  als `TRANSITION` zu behandeln, nicht zu raten.
* Rolling Shutter kann einen Ziffernwechsel zusätzlich auseinanderreißen — der
  Frame enthält dann oben den alten und unten den neuen Wert. Der Zeilenversatz
  ist Messung M3 in [TIMING.md](TIMING.md).

## Haupt- und Nebenanzeige

Konzept §7 nennt die Verwechslung von Haupt- und Nebenanzeige als kritischen
Fehler. Der Aufbau soll die Hauptanzeige eindeutig und formatfüllend zeigen.
Im Code trägt jeder Lokalisierungskandidat einen `role_hint` (`main` oder
`secondary`), damit die Rolle nicht implizit bleibt.

## Checkliste vor der ersten Messreihe

- [ ] Halterung fest, Kamera bewegt sich nicht
- [ ] Ziffernhöhe ≥ 30 px geprüft
- [ ] Fokus auf den Arbeitsabstand eingestellt
- [ ] Beleuchtung reproduzierbar, Abschirmung gegen Spiegelungen
- [ ] `glare`-Flag löst im Normalbetrieb **nicht** aus
- [ ] Belichtung und Verstärkung fixiert und im Profil hinterlegt
- [ ] Belichtungszeit gegen Multiplexflimmern geprüft
- [ ] Hauptanzeige eindeutig im Bild, Nebenanzeige nicht verwechselbar
- [ ] Aufbau in [lab_journal.md](lab_journal.md) dokumentiert
