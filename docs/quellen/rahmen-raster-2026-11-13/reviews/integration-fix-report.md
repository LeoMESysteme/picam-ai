# Integrationsfix: Task-1-Status und Golden-Session

Der vollständige Suite-Lauf meldete vier Task-1-bedingte Fehler: Der UI-Fake enthielt das neue Statusfeld `last_start_rejection` nicht und die drei parametrisierten Prüfungen der ausgabe-losen Session verglichen gegen ein Golden ohne `tracking_geometry`. Die vollständigen Tracebacks stehen in `validation/full-pytest.log`.

- `tests/live_ui_server.py`: Standardstatus um `last_start_rejection: None` ergänzt; die Laufszenen enthalten die vollständige Struktur der Trackingdiagnose mit zur Szene passenden 858 Beobachtungen und keinen Zweitversuchen. Der bestehende rekursive Vergleich aller realen Statusschlüssel bleibt unverändert.
- `tests/fixtures/live_output_disabled/session.json`: Ausschließlich die tatsächlich neu hinzugekommene Diagnose ergänzt: 3 Beobachtungen, 0 Zweitversuche, leeres Maßstabsfenster mit Limit 10000. Die bytegenauen Vergleiche für `records.jsonl` und die vollständige normalisierte Session sowie der Test auf Abwesenheit von `tx.jsonl` bleiben unverändert. `records.jsonl` wurde nicht geändert.

Prüfungen:

- `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_live_api.py::test_fake_status_has_all_real_keys_for_every_scene tests/test_live_session.py::test_output_disabled_keeps_legacy_bytes` — **4 bestanden** (alle drei Ausgabeoptionen).
- `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_live_api.py::test_fake_full_status_carries_cause_texts tests/test_live_session.py::test_r19b_session_zaehlt_zweiten_versuch_und_erfolg tests/test_live_session.py::test_tracking_fraction_keeps_same_denominator_when_audit_fails tests/test_live_session.py::test_tracking_scale_window_is_explicit_for_long_runs` — **4 bestanden**.
- `PYTHONPATH=src ./.venv/bin/ruff check tests/live_ui_server.py` — bestanden.

Die zwei übrigen Fehler des vollständigen Suite-Laufs betreffen bestehende Wanduhrgrenzen (`test_sweep_richtig_oder_abgelehnt_nie_falsch` und `test_listener_reads_available_bytes_instead_of_waiting_for_full_timeout`); diese Tests und Grenzen wurden nicht geändert und werden vom Integrator separat geprüft. Keine Hardware, kein Schreiben nach `var/`, kein Commit.
