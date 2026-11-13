# Astra — Review des Task-1-Integrationsfixes

**Umfang:** `integration-fix.diff`, Implementierungsbericht, geänderte Fixture/Testattrappe, zugehörige Produktstruktur und bestehende Prüfassertionen. Keine Produktänderung, keine Subagents, keine breite Testwiederholung, kein Kamera-/Dienstzugriff und keine Schreibzugriffe auf Lauf-/Entwicklungsdaten. Nur dieser Bericht wurde geschrieben.

**Ergebnis: ausdrücklich mängelfrei FREIGEGEBEN. Keine offenen Befunde.** Die vorherige Task-1-Freigabe bleibt bestehen.

- Golden-Session: Drei verarbeitete Bilder mit dem injizierten `ManualRoiLocator` erzeugen drei Tracking-Beobachtungen, null Zweitversuche und null Maßstabswerte. `retry_fraction=0.0`, `n=total=0`, `window_limit=10000` und `min/median/max=null` entsprechen exakt der Implementierung. Beobachtung bedeutet hier verarbeitetes Bild; auch ohne Rahmen-Zweitfit wird der neue Nenner erhöht.
- UI-Fake: `last_start_rejection=None` entspricht dem regulären Dienststatus ohne offene Ablehnung. Die Laufszenen enthalten die vollständige neue `tracking_geometry`-Struktur; 858 Beobachtungen passen zu ihren 858 verarbeiteten Bildern, null Auditfehlern und null Zweitversuchen. `set_scene()` übernimmt den Standardstatus über `set_state()`, daher ist das neue Wurzelfeld in allen Szenen vorhanden.
- Die drei parametrisierten Ausgabe-aus-Fälle bleiben unverändert: `records.jsonl` wird bytegenau geprüft; die vollständige Session wird nach ausschließlich den bestehenden Profilhash-/Pfadnormalisierungen exakt verglichen; fehlendes `tx.jsonl` wird weiterhin verlangt. Keine Felder werden herausgefiltert und keine Assertion abgeschwächt.
- Der rekursive Vergleich sämtlicher realer Statusschlüssel in `test_fake_status_has_all_real_keys_for_every_scene` ist ebenfalls unverändert.

**Eigene schreibfreie Verifikation:** Golden-JSON nach Entfernen ausschließlich des neuen `tracking_geometry`-Blocks gleich der HEAD-Version; neue Werte exakt wie oben; `records.jsonl` byteidentisch zu HEAD; beide genannten Testfunktionen per AST-Vergleich unverändert. Alle Assertions bestanden. Die im Implementierungsbericht dokumentierten vier betroffenen und vier benachbarten Tests wurden nicht erneut ausgeführt.

Die beiden separat untersuchten Wanduhrfehler gehören nicht zu diesem Fix. Ihre Tests und Schwellen wurden hier nicht geändert; dieser Review trifft keine Aussage über deren noch laufende Integrationsprüfung.
