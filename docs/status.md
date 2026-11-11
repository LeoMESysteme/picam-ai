# Status und Übergabe — 2026-11-11

Auftrag `.superpowers/sdd/2026-11-11-bruecke-ux2/codex-session-format.md`
im vorhandenen Worktree `bruecke-merge` umgesetzt. Änderungen bleiben
uncommittet. Unter `windows/bridge/src/dispread_bridge_app/ui/` wurde nur
`port.py` um die beauftragten Felder und den Formatparameter ergänzt.

`DEFAULT_SESSION_FORMAT = 'single'` in `session_templates.py:35` ist die einzige
Formatvorgabe. Der Kommentar nennt die Umstellung auf `4ch` nach dem Einspielen
von U1 auf dem Pi. `ACTIVE_SESSION_TEMPLATE` entfällt. Beide Formate sind regulär
exportierbar; `vorlage-4kanal-mvv.ucf` ist mit SHA-256
`6bc26b61323e054bfea2dd32c375617ec46725e8eb56f455daf45454b3d8ec43` paketiert,
Versuch 2b bleibt im Quellenordner als Beleg. COM8 bleibt bytegleich zum
jeweiligen Original, COM4 ändert ausschließlich die erlaubten Portzeilen.

Sessionpfad und -format werden je Weg/Port gespeichert (`sessions` und
`session_formats`). Alte Zustände ohne Formatmetadaten werden als Einkanal
übernommen. `SessionExport.fmt`, `UiContext.session_format`, `run_format` und
`default_session_format` stehen bereit; `session_channels` folgt der erzeugten
Session oder, wenn keine vorliegt, der Vorgabe. Paketmetadaten werden für
`context()` gecacht; dort gibt es keine zusätzlichen Dateizugriffe.

Die bestehende validierte Verbindung erkennt `tick` als `4ch`, `record` als
`single`. Unter der Metadatensperre werden Laufwechsel/kein Lauf/Ende auf
unbekannt zurückgesetzt; das vorhandene Aktivitätsereignis trägt Format,
Lauf-ID und Verbindungsgeneration zum Controller. Der Controller übernimmt dies
unter seiner Sperre; bei Verbindungsverlust oder unpassender Lauf-/Generations-ID
liefert der Kontext unbekannt. Die markierte Stelle in `connection.py` kann ein
später im Protokoll validiertes `output_format` aus Hello/Idle mit einem Einzeiler
vorrangig übernehmen. Keine Protokollfelder vorweggenommen.

Prüfstand:

- TDD: neue Format-/Persistenz-/Lauferkennungstests zunächst rot, dann grün.
- Angeforderte sieben Testdateien ohne zusätzliches `PYTHONPATH`: 236 bestanden,
  einer übersprungen, der im Auftrag bekannte Unterprozesstest fehlgeschlagen
  (`test_real_process_exit_after_fake_com_preserves_unknown_intent`, Paket nicht
  im Importpfad). Danach ein zusätzlicher Cachetest ergänzt.
- Abschlusslauf derselben sieben Dateien mit `PYTHONPATH=src:../../src`:
  **238 bestanden, einer übersprungen**, einschließlich des Unterprozesstests.
- Ruff der betroffenen Python-Dateien, `git diff --check`, OQ-Index, Tour-Fakten
  und Wiki-Check bestanden.
- `./scripts/docs-site.sh build -s` ausgeführt: scheitert an zwei vorhandenen
  Links auf nicht ins Doku-Site eingebundene Windows-Dateien, in `TODO.md:16`
  und `docs/superpowers/specs/2026-11-11-gsvmulti-takt-vierkanal-design.md:7`.
- Playwright-Dokuprüfung ausgeführt: Webserverstart scheitert an der
  Socket-Sperre (`PermissionError: [Errno 1] Operation not permitted`).
  Logs: `/tmp/bruecke-session-format-docs-build.log` und
  `/tmp/bruecke-session-format-docs-playwright.log`.

U1-Einspielung und Windows-/GSVmulti-Empfangsabnahme stehen weiterhin aus.
Der UI-Hinweis bei abweichenden Formaten gehört zur separaten Oberflächenarbeit.
„Record Hidden Channels“ bleibt bei der Vierkanalvorlage erforderlich.
Kein Merge, Push, Deployment, Hardwareeingriff oder neue Abhängigkeit.
Dateiliste und Abschlussbericht:
`.superpowers/sdd/2026-11-11-bruecke-ux2/codex-session-format-abschluss.txt`.
