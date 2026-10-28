---
weg: konfigurieren
---

# Messpfad und Freigabe im Detail

Diese Seite erklärt, welche Entscheidung aus einem Kamerabild einen
ausgegebenen Messwert macht. Für die Anforderungen gilt
[Konzept §7](../../Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung);
die aktuellen Signaturen stehen in den [Verträgen](../anleitung/02-vertraege.md)
und in der [API-Referenz](../../api/index.md). Der
[schrittweise Durchlauf](../anleitung/01-kette-verstehen.md) zeigt dieselbe
Kette an einem synthetischen Beispiel.

Stand: 2026-10-21. Der aktive Live-Pfad läuft mit StreamCam,
`CameraOwner`, bestätigtem Profil, `DotMatrixReader` und JSONL-Audit.
Einrichtungsprüfung, namentliche Bestätigung und Laufsteuerung erfolgen auf
`/live`. Die ältere Werkbank erhält Vorschau-Bilder desselben Owners.

## Vom Bild zum Datensatz

| Schritt | Eingang → Ergebnis | Wer entscheidet? | Nachlesen |
| --- | --- | --- | --- |
| Bildquelle | Aufnahme → Frame mit Zeitbasis und Metadaten | FrameSource | [Bildquellen](../../api/frames.md), [Zeitstempel](zeitstempel.md) |
| Anzeige finden | Frame → Anzeigeviereck oder keine Anzeige | DisplayLocator | [Lokalisierung](../../api/detect.md), [optischer Aufbau](../OPTICAL_SETUP.md) |
| Entzerren | Anzeigeviereck → rechteckiger Ausschnitt | Geometrie | [Geometrie](../../api/geometrie.md) |
| Lesen | Ausschnitt und bestätigtes Layout → ReadResult | ValueReader | [OCR](../../api/ocr.md), [Profile](../anleitung/04-geraeteprofile.md) |
| Freigeben | ReadResult und Aufnahmezeit → GateDecision | ReleaseGate | [Freigabe-API](../../api/validate.md) |
| Dokumentieren | Entscheidung → ValueRecord → Ausgaben | Pipeline und ValueSink | [Datensatz](../../api/vertraege.md), [Ausgabe](../../api/sink.md) |

<figure class="tour-figure" data-scene="ueberblick-weg" markdown="1">
<figcaption markdown="span">Der Weg eines Werts von der Anzeige bis zum Datensatz. Die Kalibrierreferenz läuft getrennt darunter und wird erst nachträglich über die Zeitstempel zugeordnet.</figcaption>
</figure>

Der bevorzugte Betrieb bestätigt die ROI einmalig
([Konzept §4](../../Konzept.md#4-bedienkonzept-fur-wechselnde-gerate)).
Ein Fundkandidat ist damit noch keine bestätigte Geometrie. Die
[Workbench-Anleitung](../anleitung/10-kamera-livevorschau.md) beschreibt die
Bedienung; [Kapitel 7](../anleitung/07-lokalisierung.md) beschreibt die
weitergehende Lokalisierung als Bauaufgabe. Der aktive Kamerapfad ist
[UVC/StreamCam](../HARDWARE_PROFILE.md); die IMX500 ist außer Betrieb.

## Was die Lesung belegen muss

Der Vertrag sieht vor, die sichtbare Zeichenfolge und ihre numerische
Interpretation getrennt zu halten. Der aktuelle Dot-Matrix-Leser schreibt
in <code>raw_text</code> jedoch nur die geparste Zahl mit Pluszeichen,
ohne die führenden Leerstellen und restlichen Displayzellen. Bei Ablehnung
ist der Text leer. Eine vollständige Abschrift der 16 Zellen fehlt noch
([Arbeitsliste](../../TODO.md)). Negative Werte sind für diesen Leser nicht
freigegeben. Vorzeichen,
Dezimalpunkt und Einheit sind eigene Evidenzen. Stammt die Einheit aus dem
Profil, muss ihre Herkunft in den Diagnosen erkennbar sein
([Kapitel 1](../anleitung/01-kette-verstehen.md),
[OQ-17](../open-questions.md#oq-17)).

<figure class="tour-figure" data-scene="erkennung-format" markdown="1">
<figcaption markdown="span">Erst wenn jedes Kästchen sicher erkannt ist und die Zeichenfolge zur Formatregel des Geräts passt, gilt der Wert als gelesen. Ein einziges unsicheres Kästchen verwirft den ganzen Wert.</figcaption>
</figure>

Der Leser kennt **keinen Referenzwert**. Die Signaturen von
<code>ValueReader.read</code> und <code>ReleaseGate.evaluate</code> lassen ihn
nicht zu. Ein Vergleich mit der Kalibrierreferenz findet erst außerhalb des
Erkennungspfads statt. Das verhindert, dass eine vermeintlich plausible
Referenz den DUT-Wert still korrigiert
([Konzept §7](../../Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung),
[Nachweistabelle](../VALIDATION.md#nachweise-gegen-die-stillen-fehlermodi-aus-konzept-7)).

<figure class="tour-figure" data-scene="regeln-referenz" markdown="1">
<figcaption markdown="span">Leser und Freigabe bekommen den Referenzwert gar nicht übergeben; ihre Signaturen lassen ihn nicht zu.</figcaption>
</figure>

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

<figure class="tour-figure" data-scene="erkennung-freigabe" markdown="1">
<figcaption markdown="span">Gültig oder Übergang: Verlangt die Freigabe mehrere gleiche Bilder hintereinander, heißt der Wert bis dahin Übergang. Ein echter Sprung wird danach übernommen, nicht geglättet.</figcaption>
</figure>

| Situation | Status oder Reaktion | Was im Nachweis steht |
| --- | --- | --- |
| Wert vollständig und eindeutig | <code>valid</code> | Wert, Einheit, Lesetext, Zeitbasis, Profil und Versionen |
| Mischziffern kurz nach Freigabe, übrige Zellen unverändert | <code>transition</code> | Grund <code>anzeige_wechselt</code>, kein Zahlenwert |
| Sonst gültige Aufnahme während werkbankgesteuerter Geräteumkonfiguration | <code>transition</code> | Grund <code>geraet_umkonfiguriert</code>, kein Zahlenwert |
| Mehrbildbestätigung noch offen | <code>transition</code> | Grund <code>awaiting_confirmation</code>, Anzahl und Zeitspanne |
| Anzeige fehlt oder Zeichen sind unlesbar | <code>unreadable</code> | kein freigegebener Zahlenwert, konkreter Ablehnungsgrund |
| Nach einer Freigabe kommt lange keine neue gültige Lesung | <code>stale</code> | alter Wert wird nicht als aktueller Wert fortgeführt |
| Glanz, Menü, Hold oder Überlauf | blockierende Statusflags | keine gültige Zahlenfreigabe |

Im Live-Pfad müssen zwei Bilder denselben Zahlenwert bestätigen; der
allgemeine <code>GateConfig</code>-Default bleibt ein Bild.
<code>anzeige_wechselt</code> ist auf höchstens drei unlesbare Zellen und
das kürzere Fenster aus Übergangsfrist und Veraltungsfrist beschränkt
(aktuell höchstens 0,5 s). Alle lesbaren Zellen müssen der letzten Freigabe
entsprechen; andere Fehler werden dadurch nicht zu Übergängen.

**Grenze:** Die Pipeline meldet bei einer nicht gefundenen Anzeige
<code>unreadable</code> direkt; sie ruft dafür das Gate nicht auf. Für andere
Ablehnungen entscheidet das Gate anhand der Aufnahmezeit, ob
<code>unreadable</code>, <code>transition</code> oder <code>stale</code>
vorliegt. Blockierende Zustandsflags bleiben <code>unreadable</code>. Diese Unterscheidung
steht im [Pipeline-Code](../../api/pipeline.md) und in der
[Freigabe-API](../../api/validate.md).

<figure class="tour-figure" data-scene="erkennung-veraltet" markdown="1">
<figcaption markdown="span">Unlesbar und veraltet: Ist die Anzeige verdeckt, gibt es keinen Zahlenwert, auch nicht den letzten gültigen. Bei einer fortgesetzten Leseablehnung ohne blockierendes Statusflag wird nach <code>stale_after</code> aus „unlesbar“ „veraltet“. Trackingverlust bleibt im Audit UNREADABLE.</figcaption>
</figure>

Fehlen neue Kamerabilder, kennzeichnet die Live-Oberfläche den zuletzt
gelesenen Datensatz nach der Altersgrenze als STALE; ohne neues Bild
entsteht kein zusätzlicher Record. Der Streamstillstand beendet den Lauf
derzeit erst nach dem OpenCV-Timeout. Große Wertwechsel können außerdem
<code>tracking_lost:low_score</code> auslösen, weil das Tracking noch den
Zifferninhalt berücksichtigt ([OQ-26](../open-questions.md#oq-26)).

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
[Sink-Vertrag](../../api/sink.md)). Der aktuelle Live-Lauf nutzt ausschließlich das JSONL-Log als Auditspur.
Eine serielle GSVmulti-Ausgabe ist dort noch nicht angeschlossen.
Das serielle ASCII-CSV ist nur ein als <code>provisional=True</code>
gekennzeichneter Platzhalter. Der
[UserDefined-Einstieg](../GSVMULTI_PROTOCOL.md#userdefined-format) ist seit
2026-10-28 dokumentiert; der zugehörige Adapter und seine Abnahme fehlen.

Die optionale serielle GSV-2AS-Aufzeichnung steht getrennt in
<code>reference.jsonl</code>; der Nachvergleich erfolgt mit
<code>scripts/live-reference-eval.py</code>. Der Referenzwert verändert
weder Leserentscheidung noch Freigabe. Ein Testlauf bei Lesesperre trägt
<code>TESTLAUF.json</code> und die Markierung in <code>session.json</code>;
die Live-Sitzung setzt jede Gate-Freigabe vor dem Audit von
<code>VALID</code> auf <code>UNREADABLE</code>, mit <code>value=null</code>
und dem ersten Ablehnungsgrund <code>testlauf_keine_freigabe</code>.
Die Oberfläche zeigt nur die getrennte Leser-Vermutung als Diagnose,
niemals einen gültigen Testlaufwert
([OQ-44](../open-questions.md#oq-44)). Eine angepasste Lesetoleranz setzt eine
serielle Einrichtungsgegenprobe und ausdrückliche Bestätigung voraus;
sie bleibt als nicht validiert markiert.

Eigene **Schreibsequenzen** des Werteplans und der Rückstellung sperren
dagegen die Freigabe: vom BOOTTIME-Zeitpunkt vor dem ersten STOP bis nach
<code>resume_transmission</code> plus **695 ms Nachlauf**. Dieser Nachlauf
übernimmt das bestehende GUARD-Schutzintervall aus dem Referenzabgleich für
Anzeigeverzögerung und LCD-Umschaltung; er ist keine neue Zeitmessung.
Die Live-Sitzung rechnet die Aufnahmezeit mit
<code>records.to_boottime_ns</code> und dem gemessenen Sessionversatz um.
Vor jeder sonst gültigen Aufnahme mit Werteplan wird der Versatz frisch
geprüft, damit Suspend auch vor der nächsten periodischen Auditprobe
erkannt wird; zusätzliche Versatzsprünge bleiben im Sessionaudit erhalten.
Ein sonst gültiger Datensatz im Fenster wird vor Audit und Ausgabe
<code>TRANSITION</code>, mit <code>value=null</code> und erstem Grund
<code>geraet_umkonfiguriert</code>.
<code>summary.reconfiguration_suppressed</code> zählt diese Bilder in
<code>session.json</code>; der Zähler erscheint nur bei aktiviertem Werteplan.

Die Referenzaufzeichnung hält die Intervalle thread-sicher auch nach ihrem
Ende vor. Daher bleibt ein Bild aus dem Fenster bei später Verarbeitung
gesperrt; eine Aufnahme vor STOP zeigt noch den alten Gerätezustand und
darf gültig bleiben. Reine Register-Lesepausen (Precheck und
Rückstellungsprüfung) schreiben keine Anzeigeparameter und sind ausgenommen.
Bei Abbruch ohne Resume bleibt das Fenster offen; bei nicht umrechenbarer
Aufnahmezeit wird mit aktivem Werteplan vorsorglich gesperrt. Andere Status,
insbesondere <code>UNREADABLE</code>, werden nicht geändert. Die
Testlauf-Sperre R13-17 hat Vorrang und bleibt <code>UNREADABLE</code>.

Zur Diagnose zuerst den <code>status</code> und
<code>reject_reasons</code> im JSONL-Record prüfen, dann
<code>raw_text</code>, Lesediagnosen und <code>component_versions</code>.
Bei Zeitfragen <code>capture_timestamp.base</code> und
<code>uncertainty_ns</code> prüfen
([Zeitstempel](zeitstempel.md)); bei einer Ausgabeabweichung den
<code>TxReceipt</code> und die Sink-Gesundheit prüfen. Konkrete
Befehle stehen in den [Rezepten](../anleitung/rezepte.md#5-valuesjsonl-auswerten)
und die Fehlerklassen in [VALIDATION.md](../VALIDATION.md#fehlerklassen-getrennt-zu-zahlen).
