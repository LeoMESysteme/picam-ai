# Zeitstempel richtig lesen

Ein Zeitpunkt ist nur zusammen mit seiner **Zeitbasis**, seiner
**physikalischen Bedeutung** und seiner **Unsicherheit** auswertbar. Diese
Seite erklärt die Datensätze; Messverfahren und Zahlen stehen in
[TIMING.md](../TIMING.md). Die Anforderung kommt aus
[Konzept §6](../../Konzept.md#6-synchronitat-und-zeitliche-grenzen).

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

## Welche Zeitbasis begegnet dir?

| Basis | Herkunft | Zulässiger Schluss |
| --- | --- | --- |
| <code>v4l2_monotonic</code> | V4L2-Pufferzeitstempel der aktuellen StreamCam | zeittragend; Bezug auf BOOTTIME erst mit gemessenem Versatz |
| <code>sensor_boottime</code> | historische IMX500-Metadaten | zeittragend; Semantik des Sensorereignisses war offen |
| <code>replay_recorded</code> | erhaltene Aufnahmezeit eines Replays | zeittragend, wenn die Aufnahmemetadaten belastbar sind |
| <code>synthetic</code> | Generator | keine reale Aufnahme- oder Synchronitätszeit |
| <code>file_mtime</code> | Dateisystem | keine belastbare Aufnahmezeit |

Die StreamCam liefert einen Stempel in <code>CLOCK_MONOTONIC</code>.
<code>records.to_boottime_ns</code> rechnet nur um, wenn die Session
Start- und Endversatz <code>BOOTTIME − MONOTONIC</code> enthält und keine
auffällige Versatzänderung durch Suspend vorliegt. Fehlende Angaben werden
abgelehnt. Die physikalische Bedeutung des V4L2-Stempels bleibt
[OQ-43](../open-questions.md#oq-43); der für die Ernte gemessene Gesamtversatz
steht in [TIMING.md](../TIMING.md). Die frühere IMX500-Messreihe dort ist
historisch und gilt nicht automatisch für UVC.

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

## Von Aufnahme bis GSVmulti

<code>ValueRecord.capture_timestamp</code> behält die Zeitbasis der Quelle;
<code>result_timestamp</code> ist ein anderes Ereignis.
<code>PipelineTrace</code> führt Stufenmarken für die Rechenzeit
([Messpfad](messpfad.md), [Pipeline-API](../../api/pipeline.md)).
Die Mehrbildbestätigung meldet ihre eigene
<code>confirmation_span_ns</code>. Diese Felder dürfen nicht zu
einem einzigen undifferenzierten „Zeitstempel“ zusammenfallen.

Ob GSVmulti die übermittelte Aufnahmezeit verwendet, muss Versuch M8 zeigen.
Die Telegrammspezifikation und das Verhalten bei ungültigen Werten sind offen
([GSVmulti-Protokoll](../GSVMULTI_PROTOCOL.md),
[OQ-07](../open-questions.md#oq-07)). Ein gleichmäßiger serieller
Datenstrom belegt daher keine Synchronität zur Referenz.

## Ein Bericht mit belastbarer Zeitangabe

Nenne pro Ergebnis die Quelle und Zeitbasis, die Stempelsemantik, den
gemessenen Offset samt Streuung und die bekannte Unsicherheit. Trenne
Aufnahmezeit, Ergebnisfertigstellung und Empfangszeit. Markiere Messungen
auf synthetischem Material ausdrücklich als reine Rechenzeitmessung.
Ein dokumentiertes Beispiel für diese Trennung steht unter
[Verarbeitungslatenz je Stufe](../TIMING.md#verarbeitungslatenz-je-stufe-2026-09-07);
die Zahlen dort stammen von synthetischen Bildern und sind keine reale
Ende-zu-Ende-Latenz.
