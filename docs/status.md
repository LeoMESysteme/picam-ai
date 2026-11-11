# Status und Übergabe — 2026-11-11

Windows-Brücke UX2, Backend-Auftrag aus
`.superpowers/sdd/2026-11-11-bruecke-ux2/codex-backend.md` umgesetzt im
Worktree `bruecke-ux` (`feat/bruecke-ux`). Änderungen liegen uncommittet im
Arbeitsbaum; kein Merge, Push, Deployment, Hardwareeingriff oder neue Abhängigkeit.
Die parallel bearbeiteten UI-Dateien gehören zum separaten UI-Auftrag.
`ui/port.py` wurde vom Backend nicht verändert.

AppController erfüllt den UX2-Port einschließlich drei Wegen, Prüfungen mit
2,8-s-Gesamtbudget, Session-Erzeugung, Aktivitätszähler und gecachter
Adapterpräsenz. `uart_direct` benötigt weder Kopplung noch Worker; Varianten
D1–D4. Session-Metadaten sind nach Weg und Port getrennt, Abschlusszustände
werden bei Änderungen verworfen, verspätete Prüfergebnisse können keinen
anderen Assistenten fortsetzen. Credential-Lesezugriffe sind aus `context()`
entfernt. PnP-Erfolge und Fehler werden 30 s gecacht; explizite Neusuche
erneuert sie. Windows-Subprozesse verwenden CREATE_NO_WINDOW.

Der Generator verändert nur drei COM-Felder der gepinnten COM8-Vorlage;
COM8 bleibt byte-identisch, COM4 passt zum unabhängigen Archivbeleg.
Gemeinsame Pi↔Brücke-UART-Quelle: `dispread.bridge.baud.UART_BAUD` (460800),
optional im v2-Profil; v1 nutzt dieselbe Quelle. GSVmulti liest die eigene
Baudrate aus der Vorlage; direkte Pi-Ausgabe bleibt getrennt.

Prüfstand des Backend-Abschlusslaufs:

- Windows: 228 bestanden, ein natives Windows-Gate übersprungen,
  zehn bestehende Socket-Tests ausgeschlossen. Der vorherige vollständige
  Lauf der betroffenen Dateien scheiterte an diesen zehn Tests, weil die
  Sandbox lokale Sockets verbietet (221 bestanden, ein übersprungen).
- Pi: 119 bestanden, fünf bestehende Socket-Tests ausgeschlossen. Vorherige
  Versuche dieser fünf Fälle scheiterten ebenfalls an der Socket-Sperre.
- Ruff und `git diff --check` bestanden. OQ-Index, Tour-Fakten und Wiki-Check
  bestanden. Strenger Doku-Build scheitert am bestehenden TODO-Link auf
  `windows/bridge/TESTLAUF.md` (vom Doku-Baum nicht erfasst).
  Playwright-Doku-Tests scheitern beim Start ihres lokalen Webservers an
  `PermissionError: [Errno 1] Operation not permitted`.
- Unabhängiges Backend-Review: drei wichtige Zustands-/Nebenläufigkeitsbefunde
  behoben, mit zuerst fehlgeschlagenen Regressionstests. Keine offenen
  wichtigen Review-Befunde; keine Windows-/Hardware-/GSVmulti-Abnahme behauptet.

Vollständiger Abschlussbericht mit Dateiliste, Fehlercodes, D1–D4-Daten,
Baud-Fundstellen und Testbefehlen:
`.superpowers/sdd/2026-11-11-bruecke-ux2/codex-backend-abschluss.txt`.
Offen bleiben der separate UI-Abschluss (neue Varianten und Fehlercodes),
Tests außerhalb der Socket-Sandbox sowie native Windows-/GSVmulti-Prüfung
(N3/OQ-53). Pi und Windows-Brücke müssen für die neue UART-Rate gemeinsam
aktualisiert werden.
