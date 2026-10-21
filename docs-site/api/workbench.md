# Workbench

Bedienoberfläche: Server, Controller, Datensätze und Live-Messpfad. Unter
`/live` steuert die angemeldete Person Einrichtung, namentliche Bestätigung
und Messlauf. Die ältere Werkbank erhält gedrosselte Bilder vom gleichen
`CameraOwner`; Kameraänderungen erfolgen über die Live-Seite.

Ein normaler Lauf setzt erfolgreiches Gegenlesen voraus. Ein ausdrücklich
markierter Testlauf kann die Lesesperre umgehen; sein Banner und
`TESTLAUF.json` untersagen die Messnutzung. Gegenwärtig verhindert das
jedoch weder VALID-Records noch ihre VALID-Anzeige
([OQ-44](../docs/open-questions.md#oq-44)). Angepasste Lesetoleranz setzt
eine serielle Einrichtungsgegenprobe und ausdrückliche Bestätigung voraus
und bleibt als nicht validiert markiert.

Bedienablauf und Grenzen: [Projekt-Tour](../docs/uebersicht/projekt-tour.md#bedienung-werkbank).

::: dispread.workbench

## Live-Steuerung und Einrichtung

::: dispread.live.service

::: dispread.live.setup
