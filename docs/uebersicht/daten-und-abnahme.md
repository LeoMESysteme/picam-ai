# Daten, Kennzahlen und Abnahme

Diese Seite hilft, einen Datensatz oder Ergebnisbericht einzuordnen.
Die verbindlichen Anforderungen stehen in
[Konzept §9–10](../../Konzept.md#9-optischer-aufbau-und-trainingsdaten);
die aktuellen Zahlen und noch offenen Grenzen in
[VALIDATION.md](../VALIDATION.md). Der
[Sammelmodus](../anleitung/11-datensatz-sammeln.md) beschreibt die Bedienung.

## Die Einheit der Unabhängigkeit

Ein Frame ist keine unabhängige Geräteprobe. Benachbarte Bilder derselben
Aufnahme teilen Aufbau, Reflexionen und oft denselben Anzeigenzustand.
Die Splitgrenze ist deshalb die **physische Geräteinstanz** und nicht
Bildnummer oder Dateiname. Ein Gerät, dessen Bilder beim Training oder bei
Schwellenentscheidungen verwendet wurden, darf nicht als unberührtes
Abnahmegerät zählen
([Datensatzregeln](../VALIDATION.md#datensatzaufbau),
[Roadmap](../ROADMAP.md#fehlerklassen-und-datensatzregeln)).

Im Sammelmodus erhält jede physische Instanz eine unveränderliche ID.
Eine neue Situation dokumentiert eine bewusste Änderung des Aufbaus;
eine neue Aufnahme derselben Situation erzeugt noch keine zusätzliche
unabhängige Bedingung. Bei mehreren Aufnahmen pro Situation braucht der
Export einen ausdrücklich gewählten Vertreter. Details und Grenzen stehen
in der [Sammelmodus-Anleitung](../anleitung/11-datensatz-sammeln.md#grenzen-der-unabhangigkeitsheuristik).

## Welche Rolle hat ein Ergebnis?

| Material oder Lauf | Was es belegt | Was es nicht belegt |
| --- | --- | --- |
| synthetische Bilder | Funktion der Kette und gezielte Fehlerfälle | Trefferquote an realen Geräten |
| reale Entwicklungsgeräte | Schwellen und Fehleranalyse während der Entwicklung | unabhängige Abnahme |
| vor Entwicklung gesperrte Geräte | einmaliger Test gegen vorab festgelegte Kriterien | nachträgliches Tuning auf denselben Geräten |
| technischer Kamerastream-Test | Bildfluss, Metadaten und Betriebsverhalten | korrekte Werterkennung |

Die aktuelle Anzahl und Rolle der Proben können sich ändern. Nutze für
Zahlen die datierte [Validierung](../VALIDATION.md) und den
[interaktiven Fortschritt](../FORTSCHRITT.md); für den Versuchsaufbau das
[Laborjournal](../lab_journal.md). Reale Zielhardware ist LCD
([OQ-04](../open-questions.md#oq-04)); LED/VFD-Entwicklungsdaten allein
belegen diese Zielhardware nicht.

## Welche Fehler einzeln zählen?

Die vollständige Freigabeentscheidung ist wichtiger als eine
Zeichentrefferquote. Zähle mindestens falsche Ziffer, fehlendes oder
zusätzliches Vorzeichen, falschen Dezimalpunkt, falsche Einheit,
Verwechslung von Haupt- und Nebenanzeige, falschen Betriebszustand und
unmarkierten Altwert getrennt
([Fehlerklassen](../VALIDATION.md#fehlerklassen-getrennt-zu-zahlen),
[Messpfad](messpfad.md#wie-das-gate-entscheidet)).

Zwei Raten beantworten unterschiedliche Fragen:

- **Unerkannte Fehlablesung:** als gültig freigegeben, aber gegenüber dem
  unabhängig erfassten Anzeigewert falsch. Das ist der kritische Fehlermodus.
- **Falschablehnung:** ein korrekt lesbarer Wert wurde abgelehnt. Das
  mindert die Verfügbarkeit und muss separat berichtet werden.

Jede Rate braucht ihren Nenner, die Anzahl Geräteinstanzen und die
Aufteilung nach Fehlerklasse. Für eine Abnahme braucht die Quote stiller
Fehler eine statistische Obergrenze; bloß „0 Fehler beobachtet“ reicht
nicht als Zusage für beliebige Geräte
([Abnahmekriterien](../VALIDATION.md#abnahmekriterien)).
Konfidenzwerte des Lesers sind ohne reale Kalibrierung keine
Fehlerwahrscheinlichkeiten ([OQ-14](../open-questions.md#oq-14)).

## Vor einem Abnahmelauf festhalten

1. Benenne Geräteumfang und Sperrgeräte vor Entwicklung
   ([OQ-04](../open-questions.md#oq-04)).
2. Lege Fehlerklassen, zulässige Grenzwerte und Auswertungsmethode vorher
   fest; die offenen Platzhalter in [VALIDATION.md](../VALIDATION.md#abnahmekriterien)
   sind keine erreichten Grenzwerte.
3. Dokumentiere Licht, Abstand, Blickwinkel, Belichtung, Profil und
   Geräteidentität im [Laborjournal](../lab_journal.md).
4. Archiviere Rohbilder, Labels, Versionen und Ausgabedatensätze; erhalte
   die Trennung von erkanntem Wert und serieller Übertragung
   ([Messpfad](messpfad.md#ausgabe-und-fehlersuche)).
5. Prüfe den Zeitbezug separat. Ein synthetischer oder aus Dateizeit
   abgeleiteter Stempel darf keine Latenzbehauptung stützen
   ([Zeitstempel](zeitstempel.md), [TIMING.md](../TIMING.md)).

Die P7-Abnahme ist erst erreicht, wenn der Lauf auf gesperrten Geräten
gegen diese vorher festgelegten Kriterien ausgewertet wurde
([Roadmap](../ROADMAP.md)). Ein Entwicklungsbenchmark ist dafür kein Ersatz.
