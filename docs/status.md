# Status und Übergabe — 2026-11-11

> **KRITISCHER NUTZERAUFTRAG 2026-11-11:** Vor Bridge-/EXE-Features den Workbench-Blocker bearbeiten.
> Einstieg: [/home/me-systeme/picam-ai/docs/WORKBENCH_BLOCKER.md](/home/me-systeme/picam-ai/docs/WORKBENCH_BLOCKER.md).
> Originale, Quellstände, Logs und Regressionen sind im Hauptcheckout gesichert.
> Ziel Freitag 2026-11-13; keine Hardwarefreigabe ohne Beleg.

Auftrag `.superpowers/sdd/2026-11-11-bruecke-ux2/codex-session-catalog.md`
im vorhandenen Worktree `bruecke-ux` (`feat/bruecke-ux`) umgesetzt. Alle
Änderungen bleiben uncommittet. Kein Merge, Push, Deployment, Hardwareeingriff
oder neue Abhängigkeit. Der parallel bearbeitete UI-Bereich wurde durch diesen
Auftrag nicht verändert; bestehende Änderungen in `app_controller.py` bleiben
neben den gezielten Exportanpassungen erhalten.

Der exportierbare Vorlagenkatalog steht zentral in `session_templates.py`:

- `bruecke-session-com8-20261106`: `Session-COM8.ucf`, `single_value`,
  `active`, ein Kanal, keiner ausgeblendet, kein Aufnahmehinweis erforderlich.
- `bruecke-session-4ch-hidden-20261111`: `versuch2b-session-hidden.ucf`,
  `gsvmulti_userdefined_4ch_v1`, `prepared`, vier Kanäle, drei ausgeblendet,
  „Record Hidden Channels“ erforderlich.

SHA-256 und Herkunft sind im Code gepinnt, die neue Paketdatei entspricht dem
Original und dessen `SHA256SUMS`. Kanalzahl, Sichtbarkeit und Baudrate werden
beim Laden aus der Datei gelesen. Alle Katalogvorlagen müssen dieselbe Baudrate
tragen (derzeit 115200). `ACTIVE_SESSION_TEMPLATE` wählt die reguläre Vorlage;
zusätzlich muss ihr Status `active` sein. Der öffentliche Export bietet keine
Vorlagenauswahl. Vorbereitete Vorlagen benötigen den Entwicklereinstieg mit
`allow_prepared=True`. Die Aktivierung bleibt eine geprüfte Codeänderung.

Portersetzung ändert ausschließlich `ComNr`/`Name` in jedem `[chN]` und
`UserDevice.ComNo`; die Kanalnummer im Namen kommt aus `Input`. Sonstige Bytes,
Zeilenenden und Reihenfolge bleiben erhalten. COM8 ist für beide Vorlagen
byte-identisch zum jeweiligen Beleg, COM4 ändert bei vier Kanälen genau neun
Zeilen. `SessionExport` trägt die abgeleiteten Kanal-/Aufnahmehinweise; Diagnose-
und Kontextlogik bleiben unverändert. Beide PyInstaller-Specs paketieren beide
Dateien; das bestehende setuptools-Muster erfasst sie ebenfalls. Erkannte
Archivoriginale bleiben vom exportierbaren Katalog getrennt.

Prüfstand:

- Angeforderte fünf Testdateien: **141 bestanden, ein natives Windows-Gate
  übersprungen**. Einschließlich separater Prozessprüfung der späteren
  Vierkanal-Aktivierung mit Export- und Kontextmetadaten.
- Ruff, `git diff --check`, OQ-Index, Tour-Fakten und Wiki-Check bestanden.
- Unabhängiges Review: keine kritischen, wichtigen oder kleinen Befunde.
- Gesamte Brücken-Suite: **589 bestanden, vier übersprungen, 14 fehlgeschlagen**.
  Dreizehn Fälle in `test_app_controller_integration.py` und `test_transports.py`
  benötigen Sockets, die die Sandbox verbietet (`PermissionError: [Errno 1]`);
  dazu gehört der Versionswächter, der schon `network_unavailable` erhält.
  Ein Unterprozessfall in `test_worker.py` findet das Brückenpaket ohne
  `PYTHONPATH` nicht; separat mit `PYTHONPATH=src:../../src` bestanden.
  Alle Fehlernamen und die vollständige Dateiliste stehen im Abschlussbericht
  `.superpowers/sdd/2026-11-11-bruecke-ux2/codex-session-catalog-abschluss.txt`.

Offen bleibt die Senderumstellung von Pi/Brücke auf das Vierkanalformat sowie
die anschließende Windows-/GSVmulti-Abnahme. `prepared` wird hier nicht aktiviert.
„Record Hidden Channels“ muss in GSVmulti selbst eingeschaltet werden; die UCF
kann diese Einstellung nicht speichern. Die vorherigen UX2-Backend- und
parallelen UI-Arbeiten bleiben eigenständige Aufträge; Details des ursprünglichen
Backend-Abschlusses stehen in
`.superpowers/sdd/2026-11-11-bruecke-ux2/codex-backend-abschluss.txt`.
