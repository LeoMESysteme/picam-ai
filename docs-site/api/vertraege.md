# Verträge und Datensätze

Am Ende der Kette steht für jedes ausgewertete Kamerabild ein `ValueRecord`:
ein Datensatz, der festhält, was das System erkannt hat. Er entsteht auch
dann, wenn kein Wert freigegeben wurde, und wird danach von niemandem mehr
verändert. Das JSONL-Log schreibt ihn vollständig mit, der serielle Ausgang
übersetzt ihn in ein Telegramm.

<figure class="tour-figure" data-scene="erkennung-ausgabe" markdown="1">
<figcaption markdown="span">Der Datensatz mit seinen neun Pflichtfeldern und
wohin er geht: ins Audit-Log und an die serielle Schnittstelle. Das
GSVmulti-Telegrammformat ist noch offen
([OQ-07](../docs/open-questions.md#oq-07)).</figcaption>
</figure>

## Die neun Pflichtfelder

Die Felder kommen aus [Konzept.md §8](../Konzept.md#interner-datensatz).
Sie stehen im Code zuerst und in dieser Reihenfolge.

| Feld | Inhalt | Worauf es ankommt |
| --- | --- | --- |
| `frame_sequence` | Laufende Nummer des Kamerabilds | Verbindet den Datensatz mit dem Bild in Aufnahme und Log. |
| `capture_timestamp` | Aufnahmezeit des Bilds, mit Zeitbasis (`base`), Bedeutung (`semantics`) und Unsicherheit | Wird nie durch eine Verarbeitungszeit ersetzt. Mit seriellen Telegrammen vergleichbar nur über `to_boottime_ns`, siehe [Zeitstempel richtig lesen](../docs/uebersicht/zeitstempel.md). |
| `value` | Erkannter Zahlenwert | Bei `STALE` und `UNREADABLE` immer leer; ein Datensatz mit Zahl und einem dieser Zustände lässt sich gar nicht erzeugen. |
| `unit` | Vom Leser erkannte Einheit | Nur bei `VALID` gesetzt. |
| `status` | `VALID`, `TRANSITION`, `UNREADABLE` oder `STALE` | Nur `VALID` ist ein freigegebener Wert. Jeder andere Zustand nennt in `reject_reasons` mindestens einen Grund. |
| `confidence` | Qualitätskennzahl der Erkennung | Eine Kennzahl, **keine** Fehlerwahrscheinlichkeit. |
| `profile_id` | Geräte- und Anzeigeprofil, mit dem gelesen wurde | Belegt, welche Einstellungen für diesen Wert galten. |
| `trigger_sequence` | Optional zugeordnetes Triggerereignis | Bisher setzt keine Bildquelle einen Trigger; das Feld ist deshalb leer. |
| `result_timestamp` | Zeitpunkt, an dem die Kette den Datensatz fertig hatte | Zeigt zusammen mit `capture_timestamp`, wie lange die Auswertung gedauert hat. |

Dahinter folgen Felder zur Nachvollziehbarkeit: der gelesene Rohtext
(`raw_text`), die Ablehnungsgründe (`reject_reasons`), wie viele Bilder einen
Wert bestätigt haben und wie lange das gedauert hat (`frames_confirmed`,
`confirmation_span_ns`), die Verarbeitungsmarken je Stufe (`trace`) und die
Versionen der beteiligten Komponenten. Ohne sie ließe sich später nicht
belegen, warum ein Wert freigegeben oder abgelehnt wurde.

Was tatsächlich über die Leitung ging, steht **nicht** im Datensatz, sondern
in einem getrennten `TxReceipt`. So bleibt unterscheidbar, wann ein Wert
aufgenommen und wann er gesendet wurde.

## Referenz aus dem Code

Der folgende Teil wird aus den Docstrings erzeugt und ist damit immer auf dem
Stand des Codes.

::: dispread.records

::: dispread.layout

::: dispread.charcells

::: dispread.session_profile
