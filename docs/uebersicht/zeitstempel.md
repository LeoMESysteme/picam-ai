# Zeitstempel richtig lesen

Ein Zeitpunkt ist nur zusammen mit seiner **Zeitbasis**, seiner
**physikalischen Bedeutung** und seiner **Unsicherheit** auswertbar. Diese
Seite erklärt die Datensätze; Messverfahren und Zahlen stehen in
[TIMING.md](../TIMING.md). Die Anforderung kommt aus
[Konzept §6](../../Konzept.md#6-synchronitat-und-zeitliche-grenzen).

<figure class="tour-figure" data-scene="zeit-uhren" markdown="1">
<figcaption markdown="span">Kamera, Messverstärker und Kalibrierreferenz zählen mit verschiedenen Uhren. Zwei Zeitpunkte aus verschiedenen Uhren dürfen nicht einfach voneinander abgezogen werden.</figcaption>
</figure>

## Drei Fragen vor jeder Rechnung

1. **Welche Uhr?** Das Feld <code>capture_timestamp.base</code> nennt die
   Zeitbasis. <code>synthetic</code> und <code>file_mtime</code> tragen keine
   nutzbare Zeitinformation für Latenz oder Synchronität.
2. **Welches Ereignis?** <code>semantics</code> beschreibt, ob der Stempel
   etwa Belichtungsbeginn, Belichtungsmitte oder Pufferausgabe meint. Solange
   das nicht gemessen ist, steht dort <code>unknown</code>.
3. **Wie genau?** <code>uncertainty_ns=None</code> heißt „nicht bekannt“,
   nicht null Nanosekunden. Ein Offset, eine Streuung und ein unbekannter
   systematischer Rest sind getrennt zu behandeln.

Die zulässige Grundprüfung ist
<code>TimeBaseKind.carries_time_information</code> beziehungsweise
<code>Frame.is_time_bearing</code>
([Frame-API](../../api/frames.md), [Datensatz-API](../../api/vertraege.md)).
Bei einer unzulässigen Basis darf aus dem Zahlenwert in
<code>value_ns</code> keine reale Latenzaussage entstehen.

**Verarbeitungsmarken (geklärt 2026-10-23):**
<code>Timestamp.now_monotonic()</code> und die Pipeline-Ergebniszeit
<code>result_timestamp</code> stammen immer aus
<code>time.monotonic_ns()</code> und tragen <code>HOST_MONOTONIC</code>.
<code>capture_timestamp</code> behält die Zeitbasis der Quelle. Alte
Auditdateien behalten ihre bisherigen Labels; sie werden nicht umgeschrieben
([OQ-45](../open-questions.md#oq-45)). Eine Differenz aus Aufnahme- und
Ergebniszeit nur bei belegtem gemeinsamem Uhrbezug als Latenz verwenden;
Replay-Aufnahme und Verarbeitung gehören zu verschiedenen Sessions. Die
gleichbasigen Marken des <code>PipelineTrace</code> dokumentieren die
Rechenzeit.

## Welche Zeitbasis begegnet dir?

| Basis | Herkunft | Zulässiger Schluss |
| --- | --- | --- |
| <code>v4l2_monotonic</code> | V4L2-Pufferzeitstempel der aktuellen StreamCam | zeittragend; Bezug auf BOOTTIME erst mit gemessenem Versatz |
| <code>host_monotonic</code> | Host-Uhr beim Verarbeitungsabschluss | reale Verarbeitungszeit, niemals Aufnahmezeit; Bezug auf BOOTTIME erst mit gemessenem Sessionversatz |
| <code>sensor_boottime</code> | historische IMX500-Metadaten | zeittragend; Semantik des Sensorereignisses war offen |
| <code>replay_recorded</code> | erhaltene Aufnahmezeit eines Replays | zeittragend, wenn die Aufnahmemetadaten belastbar sind |
| <code>synthetic</code> | Generator | keine reale Aufnahme- oder Synchronitätszeit |
| <code>file_mtime</code> | Dateisystem | keine belastbare Aufnahmezeit |

Im Live-Lauf misst <code>ClockLog</code> den Uhrenversatz zu Beginn,
periodisch und beim Abschluss; <code>session.json</code> enthält die Proben.
Die Timing-Kalibrierung wird mit Prüfsumme dokumentiert, aber nicht auf
Aufnahmezeit oder Wert angewandt.

Die StreamCam-Aufnahmezeit und die Host-Verarbeitungszeit stammen aus
<code>CLOCK_MONOTONIC</code>. Nach BOOTTIME führt für beide ausschließlich
<code>records.to_boottime_ns</code>, wenn die jeweilige Session
Start- und Endversatz <code>BOOTTIME − MONOTONIC</code> enthält und keine
auffällige Versatzänderung durch Suspend vorliegt. Fehlende Angaben werden
abgelehnt. Die physikalische Bedeutung des V4L2-Stempels bleibt
[OQ-43](../open-questions.md#oq-43); der für die Ernte gemessene Gesamtversatz
steht in [TIMING.md](../TIMING.md). Die frühere IMX500-Messreihe dort ist
historisch und gilt nicht automatisch für UVC.

<figure class="tour-figure" data-scene="zeit-versatz" markdown="1">
<figcaption markdown="span">Die Kamerazeit wird nur an einer Stelle nach BOOTTIME umgerechnet, mit dem zu Beginn und am Ende der Aufnahme gemessenen Versatz. Fehlt er oder hat er sich verändert, wird abgelehnt.</figcaption>
</figure>

## Latenz und Unsicherheit auseinanderhalten

Ein Verarbeitungs-Trace misst, wie lange Lokalisierung, Entzerrung, Lesen
und Freigabe brauchen. Er ist **nicht** automatisch der Abstand zwischen
interner DUT-Messung und Referenzmessung. Dazwischen liegen interne
DUT-Filterung, Displayaktualisierung, Belichtung und möglicherweise die
serielle Empfangszeit
([Konzept §6](../../Konzept.md#6-synchronitat-und-zeitliche-grenzen)).

Der Aufnahmezeitstempel kann die schwankende OCR-Laufzeit aus der
Zuordnung heraushalten. Er verrät aber nicht von selbst, wann das DUT
intern gemessen hat. Für ein Unsicherheitsbudget müssen die Einzelbeiträge
M1–M7 getrennt gemessen werden
([Messprogramm](../TIMING.md#messprogramm),
[Budgetvorlage](../TIMING.md#unsicherheitsbudget-vorlage)).
Ein konstanter Versatz kann korrigierbar sein; die Streuung und der
unbekannte Rest bleiben im Budget. Der zulässige Grenzwert ist
[OQ-02](../open-questions.md#oq-02).

<figure class="tour-figure" data-scene="zeit-latenz" markdown="1">
<figcaption markdown="span">Eine feste Verzögerung lässt sich herausrechnen, eine schwankende nicht. Ins Unsicherheitsbudget geht deshalb die Streuung ein, nicht der Mittelwert.</figcaption>
</figure>

Die optionale <code>reference.jsonl</code> zeichnet schon heute den
seriellen GSV-2AS-Strom mit Empfangsstempeln in BOOTTIME auf. Das ist eine
Gegenprobe zum optischen Wert desselben Geräts, keine angebundene
Kalibrierreferenz. <code>scripts/live-reference-eval.py</code> vergleicht
nachträglich; die gemeinsame Uhr beweist noch keinen gemeinsamen
physikalischen Messzeitpunkt.

## Von Aufnahme bis GSVmulti

<code>ValueRecord.capture_timestamp</code> behält die Zeitbasis der Quelle;
<code>result_timestamp</code> ist ein anderes Ereignis.
<code>PipelineTrace</code> führt Stufenmarken für die Rechenzeit
([Messpfad](messpfad.md), [Pipeline-API](../../api/pipeline.md)).
Die Mehrbildbestätigung meldet ihre eigene
<code>confirmation_span_ns</code>. Diese Felder dürfen nicht zu
einem einzigen undifferenzierten „Zeitstempel“ zusammenfallen.

Seit 2026-10-28 ist der UserDefined-Zahlenimport dokumentiert. Dieses
einfache Profil hat kein definiertes Aufnahmezeitfeld; eine weitere Zahl
wird zunächst ein Messkanal. Versuch M8 muss seine tatsächliche Zeitachse
bei bekannten Sendefolgen, Pausen und gebündeltem Empfang prüfen.
Ungültigbehandlung und zeitliche Zuordnung sind weiter offen
([GSVmulti-Protokoll](../GSVMULTI_PROTOCOL.md),
[OQ-07](../open-questions.md#oq-07)). Ein gleichmäßiger serieller
Datenstrom belegt daher keine Synchronität zur Referenz.

<figure class="tour-figure" data-scene="zeit-zuordnung" markdown="1">
<figcaption markdown="span">Prüfling und Referenz werden nachträglich über ihre Zeitstempel zusammengeführt. Belastbar ist das erst, wenn die offenen Punkte unten auf der Bühne geklärt sind.</figcaption>
</figure>

## Ein Bericht mit belastbarer Zeitangabe

Nenne pro Ergebnis die Quelle und Zeitbasis, die Stempelsemantik, den
gemessenen Offset samt Streuung und die bekannte Unsicherheit. Trenne
Aufnahmezeit, Ergebnisfertigstellung und Empfangszeit. Markiere Messungen
auf synthetischem Material ausdrücklich als reine Rechenzeitmessung.
Ein dokumentiertes Beispiel für diese Trennung steht unter
[Verarbeitungslatenz je Stufe](../TIMING.md#verarbeitungslatenz-je-stufe-2026-09-07);
die Zahlen dort stammen von synthetischen Bildern und sind keine reale
Ende-zu-Ende-Latenz.
