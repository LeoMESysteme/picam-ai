# Ausgabe (`sink/`)

JSONL-Audit, serielle Ausgabe und Telegrammformate als austauschbare Senken.
Der aktive Live-Lauf schreibt `records.jsonl` und Laufmetadaten; eine
GSVmulti-Senke ist dort noch nicht angeschlossen. `AsciiCsvFormatter` ist
vorläufig (`provisional=True`), `GsvAsciiFormatter` wirft absichtlich,
auch nach dem inzwischen dokumentierten UserDefined-Einstieg
([OQ-07](../docs/open-questions.md#oq-07)). Der neue Adapter ist noch nicht
implementiert; siehe [Bewertung und Anbindungsnaht](../docs/GSVMULTI_PROTOCOL.md#die-naht-im-code).

`ValueRecord` belegt die Erkennung, `TxReceipt` getrennt die Übertragung.
Die `JsonlSink` rotiert und begrenzt ihre Generationen; für lange Live-Läufe
ist die dauerhafte Audit-Aufbewahrung noch zu lösen
([Arbeitsliste](../TODO.md)). Die optionale serielle GSV-2AS-Gegenprobe
steht separat in `reference.jsonl` und beeinflusst diese Records nicht.

::: dispread.sink
