---
weg: bedienen
---

# Session-Explorer

Wie entwickeln sich Verfügbarkeit und Verarbeitung über die Messläufe?
Die Übersicht vergleicht dokumentierte Bedingungen und führt von jeder
Session zu ihren Originaldateien und zur Untersuchung einzelner Frames.

<!-- SESSION-SNAPSHOT:START -->
<p class="session-archive-notice">Keine Sessions veröffentlicht. Neue Läufe
werden bei beendeter Workbench vorbereitet und mit dem nächsten regulären
Wiki-Deploy übernommen. Ein fehlendes Archiv verhindert den Wiki-Build nicht.</p>
<!-- SESSION-SNAPSHOT:END -->

## Überblick {#ueberblick}

<div id="session-dashboard" aria-busy="true"><p class="session-load-status">Die Übersicht braucht JavaScript. Alle Zahlen stehen ohne JavaScript in der Archivtabelle oben.</p></div>

## Entwicklung der Messläufe {#entwicklung}

<div id="session-trends"><p class="session-load-status">Die Verlaufsdiagramme brauchen JavaScript; die Archivtabelle oben enthält dieselben Werte je Lauf.</p></div>

## Sessions und Dateien {#sessions}

<div id="session-list"><p class="session-load-status">Die Downloads stehen ohne JavaScript in der Archivtabelle oben.</p></div>

## Einzelne Frames untersuchen {#untersuchen}

<div id="session-viewer"><p class="session-load-status">Der Explorer braucht JavaScript.
<a href="../assets/records-explorer/index.html" target="_blank" rel="noopener">Explorer ohne Session öffnen</a></p></div>

## Kennzahlen einordnen

**Jeder Lauf zählt gleich** beschreibt eine typische Session: Quoten sind
Mittelwerte der Session-Quoten, Verarbeitungsmediane sind Mediane der
Session-Mediane. Bei p95 steht der Median der Session-p95.
**Alle Frames gemeinsam** verwendet addierte Zähler und echte Quantile aus
Einzelbeobachtungen. Lange Läufe beeinflussen diese Ansicht stärker.

VALID bedeutet einen freigegebenen Datensatz, keinen nachgewiesen richtigen
Messwert. Frameanteile sind keine Zeitanteile. Die Modellkonfidenz ist keine
Fehlerwahrscheinlichkeit. Eine höhere Verfügbarkeit allein belegt keine
bessere Messrichtigkeit; dazu braucht es einen geeigneten Referenzvergleich.
Der Messwertmedian eines Laufs steht als Detail bereit, nicht als Qualitätsnote.

Die Verlaufsdiagramme zeigen jeden Lauf als eigene Spalte in der Reihenfolge
des dokumentierten UTC-Starts; Abstände zwischen Spalten sind keine Zeitabstände.
Leseraten benötigen eine belastbare Aufnahmezeitbasis; Verarbeitungsdauern
stammen separat aus den dokumentierten monotonen Trace-Marken.
Unbekannte Angaben bleiben unbekannt. Tests und erhöhte Lesetoleranz werden
sichtbar gekennzeichnet. Softwarewechsel werden am Verlauf ausgewiesen.

## Originaldateien und Einzelansicht

Die Dateiliste bietet das unveränderte Original per Browserdownload und die
komprimierten Einzelteile. Das Manifest beschreibt Reihenfolge, Länge und
SHA-256-Prüfsummen der komprimierten und ursprünglichen Blöcke. Ohne
Browserentpackung die Teile einzeln mit gzip entpacken und **in der im Manifest
genannten Reihenfolge binär zusammenfügen**. Ohne JavaScript bleiben Tabellen,
Manifeste und komprimierte Downloads verfügbar.

Der Explorer lädt nur die gewählte Aufnahme. Lokale Dateien lassen sich
weiterhin per Dateiauswahl oder Drag & Drop untersuchen; sie werden nicht
hochgeladen. Referenz und Markierungen stehen zunächst als Dateien bereit.
Die relative A/B-Ausrichtung weist keine physikalische Synchronität nach.

[Explorer ohne Session öffnen](../assets/records-explorer/index.html){ target="_blank" rel="noopener" }
· [Messpfad und Freigabe](uebersicht/messpfad.md)
· [Zeitstempel richtig lesen](uebersicht/zeitstempel.md)
