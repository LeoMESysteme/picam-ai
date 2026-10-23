# Roadmap als begehbare Meilenstein-Karte

Stand: 2026-10-23. Grundlage sind die ausgewählten Meilenstein-Inseln und
die anschließende Präzisierung: Der Zoom führt **in** den Meilenstein, seine
Schritte erscheinen als eigene Karten auf derselben frei beweglichen Bühne.

## Verbindlicher Entwurf

* Zensical-Schrift, Theme, Navigation und Statusfarben bleiben maßgeblich.
  Die Roadmap erhält auf ihrer Seite mehr Breite und eine Bühne mit
  zurückhaltendem Punktraster. P0–P8 bleiben die großen Meilensteine.
* Eine Insel zeigt Titel, Status und höchstens zwei kleine Checkpoints.
  Die Checkpoints folgen der Bildvorlage: dünne senkrechte Verbindung,
  kleine Häkchen für gebaute/belegte Schritte, Titel links und Status rechts.
  Eine kleine, angeschnittene Kartenlandschaft innerhalb der Insel macht
  die enthaltene Ebene sichtbar. Es gibt keinen erklärenden Zoomtext.
* Hintergrundziehen verschiebt die Karte. Der Griff im Kartenkopf bewegt
  die Insel samt ihren Inhalten; Verbindungslinien folgen. Positionen werden
  je Browser gespeichert, ohne Dokumentationsinhalte zu ändern.
* Klick, Enter und Hineinzoomen führen durch denselben Übergang. Die
  gewählte Karte wächst bis zum Bühnenrand. Ihre Texte und Füllung
  verblassen; ihr Umriss geht in die Fensterbegrenzung über. Eigene
  Schrittkarten erscheinen auf der inneren Karte, kein Dialog und kein
  zentriertes Detailfenster. Ein dezenter Lichtsaum und eine statische
  Punktwolke am Rand kennzeichnen die innere Ebene.
* Herauszoomen oder die Zurück-Steuerung kehrt den Übergang um und stellt
  den vorherigen Ausschnitt wieder her. Karte und Schrittkarten bleiben
  auf beiden Ebenen frei beweglich. Suchfeld, Minimap, Zoomtasten,
  Gesamtansicht, Vollbild und Rücksetzen sind echte Bedienelemente.
* Die lokale Anime.js-Version 4.5.0 führt eine etwa 600-ms-Timeline mit
  natürlichem Abbremsen, überlappendem Verblassen und gedeckelter
  Staffelung der Schritte aus. Direkte Eingaben unterbrechen Fahrten.
  Reduzierte Bewegung wechselt unmittelbar; die Ebenen bleiben erkennbar.

## Dokumentierte Daten

Die erste Tabelle in `docs/ROADMAP.md` bleibt die Phasenquelle: P0–P8,
sechs Spalten und die vier bisherigen Statuswörter. Eine zusätzliche
Schrittetabelle liefert Phase, stabile ID, Schritt, Stand, optionales
belegtes Datum und Beleglink. Ihre Reihenfolge definiert die offenen
Folgeschritte je Phase. Keine parallel gepflegte JSON-Datenquelle.

Die Übersicht wählt einen zuletzt dokumentierten Checkpoint und den
ersten anderen offenen Schritt. Ist keiner offen, füllt ein zweiter
dokumentierter Schritt die Übersicht; ohne Datum gilt die Quellenreihenfolge.
Undatierte Arbeiten werden als gebaut oder
dokumentiert gezeigt, ohne einen Zeitpunkt zu erfinden. Gebaut, belegt,
vorhanden, offen, blockiert und ruhend bleiben getrennt. Es gibt keine
abgeleitete Fertigstellungsquote. Der historische P0-Block bleibt erhalten.
Die Phasenfolge stellt keine zusätzlichen kausalen Abhängigkeiten dar.

## Grenzen und Fehlerfälle

Die Quelltabellen bleiben ohne JavaScript lesbar und sind über die
Tabellenansicht erreichbar. Fehlerhafte Quelldaten verhindern das
Verstecken der Tabellen. Fehlendes Anime.js lässt die Karte ohne Animation
arbeiten. Defekter Browser-Speicher führt zum Standardlayout.

Die Karte unterstützt Tastatur, Pointer und Touch/Pinch, schmale Ansichten
und beide Themes. Sichtbare Steuerungen erhalten passende Namen;
dekorative Miniaturen und Randpunkte werden nicht vorgelesen. Nach
Zensical-Sofortnavigation bleiben keine aktiven Pointer, Observer oder
Animationen der alten Seite zurück.

## Verworfene Ansätze

Das Akkordeon zeigt keine räumliche Hierarchie. Raster und Sternkarte
wurden zugunsten der Inseln verworfen. Ein aufgezoomtes Detailpanel wurde
ausdrücklich durch die innere Kartenebene ersetzt. Erklärtexte über den
Zoom entfallen zugunsten der sichtbaren Kartenstruktur.
