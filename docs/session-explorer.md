---
weg: bedienen
---

# Session-Explorer

Wie zuverlässig hat das System in den aufgezeichneten Messläufen gelesen?
Oben steht, welcher Lauf auffällt. Die Tabelle zeigt jeden Lauf mit seinen
Kennzahlen und Originaldateien; „Ansehen“ öffnet ihn darunter Frame für Frame.

<!-- SESSION-SNAPSHOT:START -->
<p class="session-archive-notice">Keine Sessions veröffentlicht. Neue Läufe
werden bei beendeter Workbench vorbereitet und mit dem nächsten regulären
Wiki-Deploy übernommen. Ein fehlendes Archiv verhindert den Wiki-Build nicht.</p>
<!-- SESSION-SNAPSHOT:END -->

## Überblick {#ueberblick}

<div id="session-dashboard" aria-busy="true"><p class="session-load-status">Die Übersicht braucht JavaScript. Alle Zahlen stehen ohne JavaScript in der Tabelle „Archivkennzahlen und Dateien“ oben.</p></div>

## Läufe im Vergleich {#laeufe}

<div id="session-trends"><p class="session-load-status">Der Verlauf braucht JavaScript; die Tabelle oben enthält Statusanteile, Verarbeitung und Leserate je Lauf.</p></div>
<div id="session-list"><p class="session-load-status">Ohne JavaScript stehen die Downloads in der Tabelle oben.</p></div>

## Einzelansicht {#untersuchen}

<div id="session-viewer"><p class="session-load-status">Die Einzelansicht braucht JavaScript.
<a href="../assets/records-explorer/index.html" target="_blank" rel="noopener">Explorer ohne Lauf öffnen</a></p></div>

## Kennzahlen einordnen

**Auffällig** heißt: Ein Lauf liegt bei VALID-Anteil, Leserate oder
Konfidenzmedian unter, bei Verarbeitung p95 oder Trackingverlusten über dem
Bereich, den die Gruppe sonst hat. Als Grenze gilt das 1,5-Fache des
Interquartilsabstands unter dem unteren bzw. über dem oberen Quartil der Gruppe
(Tukey). Die Regel braucht mindestens vier Läufe mit Werten. Auffällig ist ein
Hinweis zum Nachsehen, kein Urteil über die Messrichtigkeit; ein unauffälliger
Lauf ist dadurch nicht freigegeben.

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

Der Verlauf zeigt jeden Lauf als eigene Spalte in der Reihenfolge
des dokumentierten UTC-Starts; Abstände zwischen Spalten sind keine Zeitabstände.
Die Leserate-Achse beginnt nicht bei null, damit kleine Unterschiede sichtbar
bleiben; die gepunktete Linie ist die eingestellte Bildrate der Kamera.
Leseraten benötigen eine belastbare Aufnahmezeitbasis; Verarbeitungsdauern
stammen separat aus den dokumentierten monotonen Trace-Marken.
Unbekannte Angaben bleiben unbekannt. Tests und erhöhte Lesetoleranz werden
sichtbar gekennzeichnet. Softwarewechsel werden am Verlauf ausgewiesen, sobald es mehr als einen Stand gibt.

## Originaldateien und Einzelansicht

„Details und Dateien“ in der Tabelle bietet das unveränderte Original per Browserdownload und die
komprimierten Einzelteile. Das Manifest beschreibt Reihenfolge, Länge und
SHA-256-Prüfsummen der komprimierten und ursprünglichen Blöcke. Ohne
Browserentpackung die Teile einzeln mit gzip entpacken und **in der im Manifest
genannten Reihenfolge binär zusammenfügen**. Ohne JavaScript bleiben Tabellen,
Manifeste und komprimierte Downloads verfügbar.

Der Explorer lädt nur die gewählte Aufnahme. Lokale Dateien lassen sich
weiterhin per Dateiauswahl oder Drag & Drop untersuchen; sie werden nicht
hochgeladen. Referenz und Markierungen stehen zunächst als Dateien bereit.
Die relative A/B-Ausrichtung weist keine physikalische Synchronität nach.

[Explorer ohne Lauf öffnen](../assets/records-explorer/index.html){ target="_blank" rel="noopener" }
· [Messpfad und Freigabe](uebersicht/messpfad.md)
· [Zeitstempel richtig lesen](uebersicht/zeitstempel.md)
