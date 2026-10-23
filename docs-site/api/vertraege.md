# Verträge und Datensätze

Am Ende der Kette steht für jedes ausgewertete Kamerabild ein `ValueRecord`:
ein Datensatz, der festhält, was das System erkannt hat. Er entsteht auch
dann, wenn kein Wert freigegeben wurde, und wird danach von niemandem mehr
verändert. Das JSONL-Log schreibt ihn vollständig mit. Eine serielle Senke
kann ihn über einen Formatter übersetzen; im aktuellen Live-Lauf ist diese
Ausgabe noch nicht angeschlossen.

<figure class="tour-figure" data-scene="erkennung-ausgabe" markdown="1">
<figcaption markdown="span">Der Datensatz mit seinen neun Pflichtfeldern und
wohin er geht: ins Audit-Log; die serielle Anbindung des Live-Laufs ist
noch offen, ebenso das
GSVmulti-Telegrammformat
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
| `unit` | Einheit des Leseergebnisses; im Dot-Matrix-Pfad aus dem bestätigten Profil | Die Pipeline setzt sie nur bei `VALID`. |
| `status` | `VALID`, `TRANSITION`, `UNREADABLE` oder `STALE` | Nur `VALID` ist ein freigegebener Wert. Jeder andere Zustand nennt in `reject_reasons` mindestens einen Grund. |
| `confidence` | Qualitätskennzahl der Erkennung | Eine Kennzahl, **keine** Fehlerwahrscheinlichkeit. |
| `profile_id` | Geräte- und Anzeigeprofil, mit dem gelesen wurde | Belegt, welche Einstellungen für diesen Wert galten. |
| `trigger_sequence` | Optional zugeordnetes Triggerereignis | Bisher setzt keine Bildquelle einen Trigger; das Feld ist deshalb leer. |
| `result_timestamp` | Zeitpunkt, an dem die Kette den Datensatz fertig hatte, in `HOST_MONOTONIC` | Für jede Quelle aus `time.monotonic_ns()`; für Rechenzeit die gleichbasigen Marken im `trace` verwenden. |

Dahinter folgen Felder zur Nachvollziehbarkeit: der gelesene Rohtext
(`raw_text`), die Ablehnungsgründe (`reject_reasons`), wie viele Bilder einen
Wert bestätigt haben und wie lange das gedauert hat (`frames_confirmed`,
`confirmation_span_ns`), die Verarbeitungsmarken je Stufe (`trace`) und die
Versionen der beteiligten Komponenten. Ohne sie ließe sich später nicht
belegen, warum ein Wert freigegeben oder abgelehnt wurde.

Der aktuelle Dot-Matrix-Leser speichert als `raw_text` die geparste Zahl
mit Pluszeichen, keine vollständige Abschrift der Displayzellen. Bei
Ablehnung kann der Text leer sein. Im Testlauf setzt `LiveSession` jede
Gate-Freigabe vor dem Audit auf `UNREADABLE`, mit `value=None` und dem ersten
Ablehnungsgrund `testlauf_keine_freigabe`. `raw_text`, `frames_confirmed`
und `confirmation_span_ns` der Ablesung bleiben als Diagnose erhalten.
Die Seite zeigt nur die getrennte Leser-Vermutung
([OQ-44](../docs/open-questions.md#oq-44)). Historische Testläufe mit
VALID-Records bleiben für Messungen gesperrt; `TESTLAUF.json` und die
Markierung in `session.json` sind mit auszuwerten. Die Laufkennzeichnung ist kein
Feld des einzelnen `ValueRecord`.

Die Pipeline kennzeichnet `result_timestamp` für jede Quelle als
`HOST_MONOTONIC` aus `time.monotonic_ns()`; auch
`Timestamp.now_monotonic()` verwendet diese Basis.
`capture_timestamp` behält unverändert die Quellbasis. Nach BOOTTIME führt
nur `to_boottime_ns` mit dem Versatz der jeweiligen Session und
Suspend-Prüfung. Alte Auditdateien behalten ihre bisherigen Labels. Für
Rechenzeiten die gleichbasigen Trace-Marken verwenden; Aufnahme- und
Ergebnisstempel nur bei belegtem gemeinsamem Uhrbezug vergleichen
([OQ-45, geklärt 2026-10-23](../docs/open-questions.md#oq-45)).

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
