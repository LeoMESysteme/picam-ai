# Wiki-Abgleich vom 2026-10-21

Alle **52 Navigationsseiten** aus `zensical.toml` wurden seitenweise
geprüft. Zusätzlich geprüft: `docs/README.md`, die fünf Tour-Skripte, die
zugehörigen Fakten und alle 34 Tour-Schritte. Drei Subagents bearbeiteten
getrennte Seitenbereiche; ein weiterer Agent las die Korrekturen unabhängig
gegen. Grundlage: Arbeitsverzeichnis auf `master`, Ausgangscommit `339703d`.
Vorhandene uncommittierte Messdokumente wurden erhalten und während des
Abgleichs neu hinzugekommene Abschlussbelege einbezogen.

## Maßstab und Ablauf

1. Navigationsseiten vollständig lesen; Aussagen gegen Implementierung,
   Tests, datierte Messbelege und `Konzept.md` prüfen.
2. Vorhandenes, Geplantes, historische Befunde und formale Freigabe
   auseinanderhalten. Keine Protokolle, Messwerte oder Freigaben ergänzen,
   für die ein Beleg fehlt.
3. Freigabe-/Zeitregeln aus `AGENTS.md` anwenden: keine Referenzkorrektur,
   keine Glättung, keine unmarkierten Altwerte, unbekannte Unsicherheit
   bleibt unbekannt, synthetische Zeiten belegen keine Latenz.
4. Tourtexte und Szenen gemeinsam pflegen. Den angeforderten Skill
   `animejs-animation` mit den bestehenden lokalen Anime.js-Timelines und
   Staffelungen anwenden; Codewerte aus dem Faktengenerator lesen.
5. Index/Fakten, strengen Zensical-Build, Browserverhalten, Mobilansicht,
   Fallbacks und geänderte Szenen prüfen.

Externe historische Modell-, Tarif- und Werkzeugempfehlungen sind als
historisch gekennzeichnet. Sie wurden nicht als aktuelle Empfehlungen neu
recherchiert. Die API-Referenz wird aus Docstrings erzeugt; offene
Codewidersprüche sind in den handgepflegten Einleitungen benannt.

## Seitenprotokoll

„Geprüft, unverändert“ bedeutet: kein belegter Korrekturbedarf. Alle anderen
Zeilen nennen die vorgenommenen Korrekturen. API-Links führen im gebauten
Wiki zu den aus `docs-site/api/` stammenden Seiten.

| Seite | Ergebnis |
| --- | --- |
| [README.md (Start)](../index.md) | Live-Einstieg, JSONL und begrenzter Geräteumfang aktualisiert; alle Navigationsziele bleiben verlinkt. |
| [docs/uebersicht/projekt-tour.md](uebersicht/projekt-tour.md) | Alle 34 Schritte geprüft; 16 Szenen mit Text zusammen aktualisiert, Stand-Datum gesetzt. |
| [Konzept.md](../Konzept.md) | Aktive Kamera und begrenzte Prototypbelege ergänzt; normative Anforderungen und offene GSVmulti-Anbindung erhalten. |
| [docs/status.md](status.md) | Session-Snapshot neu geschrieben; Wiki-Prüfung, Laufabschluss, R13 und neue OQs aufgenommen. |
| [TODO.md](../TODO.md) | R13 als ausgelöste Aufgabe, OQ-44/45 und erledigtes Rückstell-Snippet aktualisiert; Einstieg an CLAUDE angeglichen. |
| [docs/ROADMAP.md](ROADMAP.md) | P2/P3/P5/P6 mit belegtem Teilfortschritt und unerfüllten Exit-Kriterien; Tabellenvertrag unverändert. |
| [PLANNED_FEATURES.md](../PLANNED_FEATURES.md) | Gebautes von geplantem Verhalten getrennt; Messwertglättung und Referenzkorrektur entfernt. |
| [CHANGELOG.md](../CHANGELOG.md) | Obersten Abschnitt um Wiki-Korrekturen, Tour-Fakten und offene Code-Lücken ergänzt. |
| [docs/anleitung/README.md](anleitung/README.md) | Aktueller Live-Einstieg; vorhandene Trennstellen und Übungen eingeordnet. |
| [docs/anleitung/00-werkzeuge.md](anleitung/00-werkzeuge.md) | Testname und CLI-Einstieg gegen tests/test_sevenseg.py und pyproject.toml korrigiert. |
| [docs/anleitung/01-kette-verstehen.md](anleitung/01-kette-verstehen.md) | Geprüft, unverändert: synthetisches Beispiel und historische Zahlen passend abgegrenzt. |
| [docs/anleitung/02-vertraege.md](anleitung/02-vertraege.md) | CharLayout, UVC-Zeitbasis, Unterbrechung, Rollenprüfung, Rohtext und STALE-Zweige berichtigt; OQ-45. |
| [docs/anleitung/03-erste-bildquelle-folder.md](anleitung/03-erste-bildquelle-folder.md) | Geprüft, unverändert: Factory-Eintrag vorhanden, folder_source.py fehlt weiterhin. |
| [docs/anleitung/04-geraeteprofile.md](anleitung/04-geraeteprofile.md) | Gebautes SessionProfile und Live-Bestätigung vom geplanten ProfileStore getrennt. |
| [docs/anleitung/05-cli.md](anleitung/05-cli.md) | Vorhandene live-Kommandos ergänzt; Bestätigung/Laufstart im Browser und freie Pipeline-CLI unterschieden. |
| [docs/anleitung/06-kamera-aufnahme-replay.md](anleitung/06-kamera-aufnahme-replay.md) | clip.json-Replay und Erhalt der Aufnahmezeitbasis erklärt; historischen Manifestentwurf eingeordnet. |
| [docs/anleitung/07-lokalisierung.md](anleitung/07-lokalisierung.md) | TrackedQuadLocator und Bestätigungsunterbrechung beschrieben; unbelegte automatische Rollenprüfung berichtigt. |
| [docs/anleitung/08-ocr-backends.md](anleitung/08-ocr-backends.md) | Dot-Matrix-Livepfad, Benchmarks und leserspezifische Evidenz; erledigten OQ-15-Blocker entfernt. |
| [docs/anleitung/09-betrieb.md](anleitung/09-betrieb.md) | Installations-/Speicherstand datiert; Fehlerzustände an tatsächliche Audit-/STALE-Logik angeglichen. |
| [docs/anleitung/10-kamera-livevorschau.md](anleitung/10-kamera-livevorschau.md) | Live-Artefakte, Laufabschluss/R13, Testlauf-Lücke, Rückstellpunkt-Anschluss und Kameraeinstellungen berichtigt. |
| [docs/anleitung/11-datensatz-sammeln.md](anleitung/11-datensatz-sammeln.md) | Datensatzschema, Exportgrenzen, LCD-Zielgerät und historische Testzahlen präzisiert. |
| [docs/anleitung/rezepte.md](anleitung/rezepte.md) | Installierte Werkzeuge, CLI/Kamerabesitz und Ergebniszeitbasis präzisiert; OQ-45. |
| [docs/anleitung/glossar.md](anleitung/glossar.md) | Protocols versus konkrete Klassen, backendabhängige Marge/Konfidenz und serielle Rollen berichtigt; IDs erhalten. |
| [docs/uebersicht/messpfad.md](uebersicht/messpfad.md) | Live-/Referenzpfad, Rohtextgrenze, TRANSITION, Tracking/STALE, Testlauf und Toleranz mit Code abgeglichen. |
| [docs/uebersicht/zeitstempel.md](uebersicht/zeitstempel.md) | Uhrenversatz, nur dokumentierte Timing-Kalibrierung, Referenzabgleich und OQ-45 ergänzt. |
| [docs/uebersicht/daten-und-abnahme.md](uebersicht/daten-und-abnahme.md) | Bedienerläufe von formaler Abnahme getrennt; Testlauf-, Toleranz- und Trackinggrenzen ergänzt. |
| [docs/CAMERA_COMMISSIONING.md](CAMERA_COMMISSIONING.md) | Aktuelle StreamCam-Schritte vor historische IMX500-Anleitung gestellt; tatsächlichen Diagnoseskript-Ablauf erklärt. |
| [docs/HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) | Aktuelle StreamCam-Sitzung erhalten; PL2303-Referenz, historische Portliste, chrony und Speichersnapshot präzisiert. |
| [docs/OPTICAL_SETUP.md](OPTICAL_SETUP.md) | Reale Dot-Matrix-Belege von synthetischen Segmenttests getrennt; Schatten, Nachführung und Glanzschwelle berichtigt. |
| [docs/DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md) | Serielles Auto-Labeling, Schema-2-Herkunft/Export und Zeitbasis aktualisiert; Bus bleibt Rückfallebene. |
| [docs/GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md) | Referenzeingang vom geplanten Ausgang getrennt; Formatter-/Artefakt-Aussagen berichtigt, OQ-07 offen. |
| [docs/dependencies.md](dependencies.md) | Vorhandene Weboberfläche, getrennte Doku-Umgebung und lokal geladene Tour-Bibliothek berücksichtigt. |
| [docs/HOSTING.md](HOSTING.md) | Deployment-/Pflege-Gate und CI-Störung abgeglichen; damalige Tarifannahmen als historisch gekennzeichnet. |
| [docs/FORTSCHRITT.md](FORTSCHRITT.md) | Daten-Snapshot 2026-09-30 und manuelle Erzeugung erklärt; Leserabnahme ist keine Systemabnahme. |
| [docs/VALIDATION.md](VALIDATION.md) | Veraltete synthetische Gesamtwarnung durch aktuellen Belegumfang ersetzt; vorhandene Messdaten und Abschlussauswertung erhalten. |
| [docs/TIMING.md](TIMING.md) | Messprogramm, StreamCam-Kalibrierung, Zeitunsicherheit und offene Zeitbasis-Bezeichnung OQ-45 präzisiert. |
| [docs/lab_journal.md](lab_journal.md) | Chronologische Messbelege erhalten; Ende/Rückstellung des parallelen Versuchs und vorhandene Abschlussauswertung berücksichtigt. |
| [docs/open-questions.md](open-questions.md) | OQ-19/26 aktualisiert; OQ-44/45 sofort erfasst und Index aus TODO erzeugt; keine Frage gelöscht. |
| [docs/project_history.md](project_history.md) | Geprüft, unverändert: datierte Entscheidungen einschließlich Kamerawechsel und getrenntem Referenzaudit sind weiterhin nachvollziehbar. |
| [docs/tool_review_2026-09-08.md](tool_review_2026-09-08.md) | Historische Werkzeugempfehlungen eingeordnet; aktueller Dot-Matrix-Pfad und geklärte OQs ergänzt. |
| [api/index.md](../api/index.md) | Aktive Quelle, DotMatrix, Live-Sitzung und Werkbankrollen ergänzt. |
| [api/vertraege.md](../api/vertraege.md) | Profileinheit, Rohtextgrenze, Testlauf-Laufkennzeichnung und Ergebniszeitbasis OQ-45 präzisiert. |
| [api/frames.md](../api/frames.md) | V4L2/CameraOwner und offene Ergebniszeitbasis OQ-45 ergänzt. |
| [api/detect.md](../api/detect.md) | Bestätigtes Live-Quad und Vorschlagsrollen erläutert. |
| [api/geometrie.md](../api/geometrie.md) | Verlustregeln des Trackers und R13/OQ-26 beschrieben. |
| [api/ocr.md](../api/ocr.md) | Aktiver Dot-Matrix-Leser, leserabhängige Evidenz, Rohtext und Toleranzgrenze ergänzt. |
| [api/validate.md](../api/validate.md) | Backendabhängige Schwellen, Live-Mehrbildbestätigung, Mischziffern und STALE präzisiert. |
| [api/sink.md](../api/sink.md) | JSONL-Livepfad und offene GSVmulti-/Aufbewahrungsfragen klargestellt. |
| [api/pipeline.md](../api/pipeline.md) | Live-Sitzung, getrennter Referenzrecorder, ClockLog und relevante API-Blöcke ergänzt. |
| [api/workbench.md](../api/workbench.md) | Live-Steuerung, Lesesperre und Grenzen von Testlauf/Toleranz ergänzt. |
| [AGENTS.md](../AGENTS.md) | Geprüft, unverändert: verbindlicher Maßstab für alle Korrekturen; Generatormarken nicht manuell verändert. |
| [CLAUDE.md](../CLAUDE.md) | Aktuellen Dot-Matrix-Pfad und gebaute Konturhilfe ergänzt; fehlende Folder-/Video-Quellmodule weiter als offen benannt. |

## Offene Befunde

* [OQ-26](open-questions.md#oq-26): Der inzwischen beendete Werteplan-Lauf
  zeigt Nachführungsverluste bei großen Wertwechseln. Die parallel
  dokumentierte [Abschlussauswertung](VALIDATION.md#messpfad-live-werteplan-2026-10-21)
  widerlegt eine ausreichende Verfügbarkeit bei Faktor 2 und 5. Eine
  vom Zifferninhalt unabhängige Nachführung bleibt zu entwickeln.
* [OQ-44](open-questions.md#oq-44): Testlaufmarkierungen und Banner
  verhindern technisch weder gültige Audit-Datensätze noch deren Anzeige.
  Solche Daten sind nicht für Messungen freigegeben.
* [OQ-45](open-questions.md#oq-45): MONOTONIC-Verarbeitungsmarken sind
  teilweise mit einer unpassenden Zeitbasis bezeichnet. Keine allgemeine
  Aussage über Aufnahme-/Ergebniszeitdifferenzen daraus ableiten.
* GSVmulti ([OQ-07](open-questions.md#oq-07)), weitere Geräte/Lichtquellen,
  Toleranzvalidierung und Audit-Aufbewahrung bleiben offen.

Diese Dokumentationsrunde ändert das Verhalten des Messpfads nicht.
Ein offener Codebefund wird durch einen korrigierten Beschreibungstext
nicht behoben.

## Prüfbelege

* `./.venv/bin/pytest -q tests/test_tour_facts.py tests/test_oq_index.py`:
  **13 Tests erfolgreich**; OQ-Index und Tour-Fakten bestehen zusätzlich
  den jeweiligen Generatorlauf mit `--check`.
* `./.venv/bin/ruff check scripts/tour-facts.py` und `git diff --check`:
  erfolgreich. Alle 28 Python-Codeblöcke im Lernpfad sind mit `ast.parse`
  syntaktisch geprüft; diese Prüfung führt die Beispiele nicht aus.
* `./scripts/docs-site.sh build -s`: erfolgreich, keine Buildprobleme.
* `npx playwright test -c playwright.docs.config.ts --workers=1`:
  **29 Tests erfolgreich**. Geprüft sind Suche/Filter, Roadmap,
  Vorschauen, Tastatur, Sofortnavigation, Diagramme, alle Tour-Schritte,
  Faktenänderungen, reduzierte Bewegung und Fallbacks ohne JavaScript.
* Separater Browserdurchlauf: alle **52 Navigationsseiten** liefern
  HTTP 200 und eine Hauptüberschrift; keine JavaScript-`pageerror`-Ereignisse.
  Vier geänderte Tour-Szenen per Screenshot gesichtet; mobile Werkbank-
  Szene und Begleittext bei 375 Pixeln ohne horizontalen Überlauf.

Der erste Browserlauf fand eine vom Kopierknopf verdeckte Code-Anmerkung.
Die längere Lesersignatur ist nun mehrzeilig. Der betroffene Einzeltest und
der anschließende vollständige Browserlauf bestehen. Die Prüfungen liefen
erst nach dem Ende des parallelen Messversuchs; es wurde keine Hardware
bedient und kein neuer Messlauf gestartet.
