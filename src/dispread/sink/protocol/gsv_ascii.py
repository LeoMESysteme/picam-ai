"""Platzhalter fuer das echte GSVmulti-Telegramm.

Bewusst nicht implementiert. Die Spezifikation der eingesetzten
GSVmulti-Version liegt nicht vor (OQ-07) und me-systeme.de blockt automatische
Abrufe mit HTTP 403 - sie muss intern von einem Menschen beschafft werden.

Ein geratenes Format waere hier schaedlicher als keines: es wuerde in Tests
gruen erscheinen, in Messberichten als "Ausgabe funktioniert" auftauchen und
erst am Laborplatz auffallen. Deshalb wirft dieses Modul und verweist auf die
Klaerungsliste.

Was vor der Implementierung geklaert sein muss (Konzept.md §8):

* konkrete GSVmulti-Version und unterstuetzte Geraeteanbindung
* Beispieltelegramm oder verbindliche Protokollspezifikation
* Baudrate, Zeichenformat, Trennzeichen, Zeilenende
* Dezimaltrennzeichen, Vorzeichen, Einheit, Kanalzahl
* Geraeteidentifikation und Initialisierungskommandos
* Behandlung von Aufnahmezeit, ungueltigen und veralteten Werten
* Streaming-, Abfrage- und Wiederverbindungsverhalten

Belastbarste Quelle ist nicht die Dokumentation, sondern ein Mitschnitt: ein
vorhandenes GSV-2/GSV-3 im ASCII-Modus an GSVmulti haengen und den realen
Datenstrom aufzeichnen. Siehe docs/GSVMULTI_PROTOCOL.md.
"""

from __future__ import annotations

from dispread.records import ValueRecord
from dispread.sink.protocol import FormatterCapabilities

_MESSAGE = (
    "Das GSVmulti-Telegrammformat ist nicht bekannt (OQ-07). "
    "Siehe docs/GSVMULTI_PROTOCOL.md fuer die Klaerungsliste. "
    "Zum Testen der Kette AsciiCsvFormatter verwenden - der ist als "
    "provisorisch gekennzeichnet und wird nicht mit dem echten Format verwechselt."
)


class GsvAsciiFormatter:
    """Nicht implementiert - siehe Modul-Docstring."""

    @property
    def capabilities(self) -> FormatterCapabilities:
        raise NotImplementedError(_MESSAGE)

    def format(self, record: ValueRecord) -> bytes | None:
        del record
        raise NotImplementedError(_MESSAGE)
