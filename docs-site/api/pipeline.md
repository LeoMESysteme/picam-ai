# Pipeline und Hilfsmodule

Verdrahtung der Kette mit `PipelineTrace`, dazu Live-Sitzung, getrennte
Referenzaufnahme, Pfade und Benchmark. `Pipeline` erhält keinen Referenzwert.
`LiveSession` kombiniert den gemeinsamen Kamera-Besitzer, bestätigtes
Profil, Dot-Matrix-Leser, Gate und JSONL-Audit. Sie liest jeweils das neueste
Bild; übersprungene Bilder stehen im Trace und in der Laufzusammenfassung.

`session.json` hält Profil-, Vorlagen- und Kalibrierprüfsummen,
Kameraeinstellungen, Gate-Konfiguration und Uhrenversatz fest. Die
Timing-Kalibrierung ist beim Start Pflicht, wird aber nicht angewandt.
Testlauf und angepasste Toleranz werden dort gesondert markiert.
Im Testlauf setzt `LiveSession.step()` jeden VALID-Pipeline-Record vor dem
Audit auf `UNREADABLE`, mit `value=None` und dem ersten Ablehnungsgrund
`testlauf_keine_freigabe`. Die ursprüngliche Gate-Entscheidung bleibt nur
in der getrennten Leser-Vermutung als Diagnose sichtbar; die Seite zeigt
keinen gültigen Testlaufwert ([OQ-44](../docs/open-questions.md#oq-44)).

::: dispread.pipeline

## Live-Sitzung

::: dispread.live.session

::: dispread.live.clock

## Getrennte serielle Gegenprobe

`ReferenceRecorder` zeichnet den seriellen GSV-2AS-Ausgang in BOOTTIME auf.
Ein optionaler Werteplan ändert `set norm`; beim Stopp wird zurückgestellt.
Das Ende des Plans stoppt den Live-Lauf nicht automatisch. Der spätere
Vergleich mit `scripts/live-reference-eval.py` verändert weder Leser noch
Freigabe oder `records.jsonl`. Der Gerätestrom ist keine unabhängige
Kalibrierreferenz.

::: dispread.live.reference

## Hilfsmodule

::: dispread.paths

::: dispread.benchmark
