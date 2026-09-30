# Messpfad und Freigabe im Detail

Diese Seite erklärt, welche Entscheidung aus einem Kamerabild einen
ausgegebenen Messwert macht. Für die Anforderungen gilt
[Konzept §7](../../Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung);
die aktuellen Signaturen stehen in den [Verträgen](../anleitung/02-vertraege.md)
und in der [API-Referenz](../../api/index.md). Der
[schrittweise Durchlauf](../anleitung/01-kette-verstehen.md) zeigt dieselbe
Kette an einem synthetischen Beispiel.

## Vom Bild zum Datensatz

| Schritt | Eingang → Ergebnis | Wer entscheidet? | Nachlesen |
| --- | --- | --- | --- |
| Bildquelle | Aufnahme → Frame mit Zeitbasis und Metadaten | FrameSource | [Bildquellen](../../api/frames.md), [Zeitstempel](zeitstempel.md) |
| Anzeige finden | Frame → Anzeigeviereck oder keine Anzeige | DisplayLocator | [Lokalisierung](../../api/detect.md), [optischer Aufbau](../OPTICAL_SETUP.md) |
| Entzerren | Anzeigeviereck → rechteckiger Ausschnitt | Geometrie | [Geometrie](../../api/geometrie.md) |
| Lesen | Ausschnitt und bestätigtes Layout → ReadResult | ValueReader | [OCR](../../api/ocr.md), [Profile](../anleitung/04-geraeteprofile.md) |
| Freigeben | ReadResult und Aufnahmezeit → GateDecision | ReleaseGate | [Freigabe-API](../../api/validate.md) |
| Dokumentieren | Entscheidung → ValueRecord → Ausgaben | Pipeline und ValueSink | [Datensatz](../../api/vertraege.md), [Ausgabe](../../api/sink.md) |

Der bevorzugte Betrieb bestätigt die ROI einmalig
([Konzept §4](../../Konzept.md#4-bedienkonzept-fur-wechselnde-gerate)).
Ein Fundkandidat ist damit noch keine bestätigte Geometrie. Die
[Workbench-Anleitung](../anleitung/10-kamera-livevorschau.md) beschreibt die
Bedienung; [Kapitel 7](../anleitung/07-lokalisierung.md) beschreibt die
weitergehende Lokalisierung als Bauaufgabe. Der aktive Kamerapfad ist
[UVC/StreamCam](../HARDWARE_PROFILE.md); die IMX500 ist außer Betrieb.

## Was die Lesung belegen muss

Das Leseergebnis trennt die sichtbare Zeichenfolge von ihrer numerischen
Interpretation. Eine führende Null oder ein Minuszeichen bleibt in
<code>raw_text</code> erhalten, auch wenn der Zahlenwert gleich wäre. Vorzeichen,
Dezimalpunkt und Einheit sind eigene Evidenzen. Stammt die Einheit aus dem
Profil, muss ihre Herkunft in den Diagnosen erkennbar sein
([Kapitel 1](../anleitung/01-kette-verstehen.md),
[OQ-17](../open-questions.md#oq-17)).

Der Leser kennt **keinen Referenzwert**. Die Signaturen von
<code>ValueReader.read</code> und <code>ReleaseGate.evaluate</code> lassen ihn
nicht zu. Ein Vergleich mit der Kalibrierreferenz findet erst außerhalb des
Erkennungspfads statt. Das verhindert, dass eine vermeintlich plausible
Referenz den DUT-Wert still korrigiert
([Konzept §7](../../Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung),
[Nachweistabelle](../VALIDATION.md#nachweise-gegen-die-stillen-fehlermodi-aus-konzept-7)).

## Wie das Gate entscheidet

Das Gate prüft Betriebszustand, Kontrast, lesbare Zellen, Segmentmarge,
Vorzeichenbereich, Dezimalpunkt und bestätigte Einheit. Jeder Grund erscheint
maschinenlesbar in <code>reject_reasons</code>. Die Schwellen in
<code>GateConfig</code> sind Vorabdefaults; reale Freigabegrenzen bleiben
[OQ-14](../open-questions.md#oq-14). Ein anderer OCR-Backend liefert nicht
automatisch vergleichbare Margen: Der Dot-Matrix-Leser verwendet eigene
Schwellen; die Bedeutung seiner Marge ist in der
[Freigabe-API](../../api/validate.md) dokumentiert. [Kapitel 8](../anleitung/08-ocr-backends.md)
erklärt, welche Evidenz ein neuer Leser liefern muss.

| Situation | Status oder Reaktion | Was im Nachweis steht |
| --- | --- | --- |
| Wert vollständig und eindeutig | <code>valid</code> | Wert, Einheit, Lesetext, Zeitbasis, Profil und Versionen |
| Mehrbildbestätigung noch offen | <code>transition</code> | Grund <code>awaiting_confirmation</code>, Anzahl und Zeitspanne |
| Anzeige fehlt oder Zeichen sind unlesbar | <code>unreadable</code> | kein freigegebener Zahlenwert, konkreter Ablehnungsgrund |
| Nach einer Freigabe kommt lange keine neue gültige Lesung | <code>stale</code> | alter Wert wird nicht als aktueller Wert fortgeführt |
| Glanz, Menü, Hold oder Überlauf | blockierende Statusflags | keine gültige Zahlenfreigabe |

**Grenze:** Die Pipeline meldet bei einer nicht gefundenen Anzeige
<code>unreadable</code> direkt; sie ruft dafür das Gate nicht auf. Für andere
Ablehnungen entscheidet das Gate anhand der Aufnahmezeit, ob
<code>unreadable</code> oder <code>stale</code> vorliegt. Diese Unterscheidung
steht im [Pipeline-Code](../../api/pipeline.md) und in der
[Freigabe-API](../../api/validate.md).

Eine Mehrbildbestätigung kann die Ausgabe verzögern. Ihr
<code>confirmation_span_ns</code> gehört in den
[Zeitbezug](zeitstempel.md). Sie bildet keinen Mittelwert; echte
Messwertsprünge bleiben erhalten. Auch die Kennzahl <code>confidence</code>
ist **keine** gemessene Fehlerwahrscheinlichkeit. Die dafür nötige
Kalibrierung ist nicht belegt
([Validierung](../VALIDATION.md), [OQ-14](../open-questions.md#oq-14)).

## Ausgabe und Fehlersuche

<code>ValueRecord</code> dokumentiert, was erkannt und entschieden wurde.
<code>TxReceipt</code> dokumentiert getrennt, was über eine Senke ging.
Bei einer gestörten Leitung darf der Übertragungsfehler nicht als
Erkennungsfehler erscheinen
([Datensatzvertrag](../../api/vertraege.md),
[Sink-Vertrag](../../api/sink.md)). Das JSONL-Log dient als Auditspur.
Das serielle ASCII-CSV ist nur ein als <code>provisional=True</code>
gekennzeichneter Platzhalter; das GSVmulti-Format ist
[unbekannt](../GSVMULTI_PROTOCOL.md).

Zur Diagnose zuerst den <code>status</code> und
<code>reject_reasons</code> im JSONL-Record prüfen, dann
<code>raw_text</code>, Lesediagnosen und <code>component_versions</code>.
Bei Zeitfragen <code>capture_timestamp.base</code> und
<code>uncertainty_ns</code> prüfen
([Zeitstempel](zeitstempel.md)); bei einer Ausgabeabweichung den
<code>TxReceipt</code> und die Sink-Gesundheit prüfen. Konkrete
Befehle stehen in den [Rezepten](../anleitung/rezepte.md#5-valuesjsonl-auswerten)
und die Fehlerklassen in [VALIDATION.md](../VALIDATION.md#fehlerklassen-getrennt-zu-zahlen).
