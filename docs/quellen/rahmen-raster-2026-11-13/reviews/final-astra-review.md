# Astra — unabhängiges Gesamtreview Rahmen/Raster

Stand: 2026-11-13. Ausgangsstand `fab15a93f0f2300fb8a4d8ca7c9a0e605e3236f5`, uncommittierter Worktree `fix/rahmen-raster`.

## Endgültiges Urteil

**Gesamtänderung ausdrücklich MÄNGELFREI FREIGEGEBEN. Aufgaben 1–3 erfüllen die vereinbarte Spezifikation; Codequalität, Integration, Tests, Offline-Evidenz und Abschlussbericht sind freigegeben. Keine offenen Befunde, keine zurückgestellten Mängel und keine ausstehenden Review-/Prüfgates.**

Die vier im ersten Durchgang festgestellten P3-Präzisierungen sind vollständig behoben und nachgeprüft. Die folgende Befundliste bewahrt ihre Historie; sie bezeichnet keine offenen Punkte. Die Freigabe gilt ohne verbleibenden Reviewvorbehalt für den ausdrücklich autorisierten Offline-Implementierungsumfang. Sie ist keine Hardwarekalibrierung oder Deployment-/Mergeentscheidung.

## Umfang und eigene Prüfung

AGENTS.md, CLAUDE.md, Konzept.md, TODO-Einstieg, OQ-Übersicht, Originalhandoff, REPORT-codex.md, neu geschriebener Status, kompletter 3452-zeiliger Reviewdiff, Fortschrittsledger, alle drei abschließenden Aufgabenreviews, Integrationsreview und Doku-Buildbericht gelesen. Die tatsächlichen Dienst-/Fokus-/Session-/Storage-/Importerpfade und die geänderten UI- und Testpfade zusätzlich gezielt geprüft.

- Fokus: zweiseitige Prüfung nach Neustart, ungültige/fehlende Evidenz sperrt. Ablehnung erfolgt vor LiveSession und Referenzrecorder; bestehender gestoppter Lauf bleibt erhalten, Brückenreservierung wird im Fehlerpfad freigegeben. Separater abgeschlossener Auditvertrag, UTC-Ende, Importerausschluss und bestehende Aufbewahrung passen zusammen. Erfolgreicher Folgestart/neue Einrichtung erledigt die aktive Warnung, ohne historische Artefakte zu löschen.
- Diagnose: Nenner und Zweitversuche werden gemeinsam vor Ausgabe/Audit gezählt. Maßstabfenster, Stichprobenzahl und Gesamtzahl sind ausdrücklich gekennzeichnet. Fokusbefund bleibt bei akzeptierten Starts sichtbar. Neue Felder ergänzen den bisherigen Vertrag; Golden- und Fakeanpassungen schwächen keine Assertions ab.
- Raster: A1 bleibt auf den Rand der Lückenspalte beschränkt; regulär zugeordnete Leerzellenpunkte bleiben geprüft. B1 läuft nur nach drei tatsächlichen keine_startlage-Ergebnissen; frühe Fits, Mehrdeutigkeit, Minus und andere terminale Ablehnungen bleiben erhalten. Unveränderte Annahmegrenzen und Alternativ-Hough-Guards sind erkennbar und getestet.
- Dokumentationsbuild: Die zwei ausdrücklich referenzierten Windows-Seiten werden gezielt eingebunden; der fehlende Scratch-Recherchepfad bleibt als Text erhalten. Kein ganzer Windows-Quellbaum wird eingebunden.
- Eigenes schreibfreies Prüfskript (Exit 0): alle 40 im Paket referenzierten Artefakte nach Größe/SHA-256 geprüft; aktueller Rastercode bytegleich zur eingefrorenen A1+B1-Quelle. Alle 90 tatsächlichen Bild-/Textdateihashes stimmen mit dem Manifest überein. Je Variante genau 90 eindeutige Manifestpfade, keine Fehlerzeile, passende Bildhashes und gleiche Labels. Fits Baseline/A1/B1/Kombination = 80/85/82/88. Alle alten Fits erhalten; Drift 0 / 0,5224298057906849 / 0 / 0,5224298057906849 px. Keine Fits erneut berechnet.
- Eigene Fokusdateninventur: 17 protokollierte Starts, davon drei ohne verarbeitete Bilder; damit 14 auswertbare Starts wie berichtet. Die engen Werte, beiden Problemverhältnisse und das gute Gegenbeispiel 1,418 stimmen mit den Quellen überein.
- Vorliegende Logs nachgelesen: einmalige Vollsuite 4219 bestanden, 6 fehlgeschlagen, 20 übersprungen, 2 xfailed. Vier Fake-/Goldenfälle sind separat korrigiert und geprüft; das Integrationsreview bestätigt unveränderte Prüfassertionen. Die beiden unveränderten Zeitgrenzen bestehen isoliert (2 in 11,70 s). 289 Node- und drei Harness-Tests grün; Ruff grün; strikter Doku-Build „No issues found“. Der ursprüngliche Vollsuite-Exit 1 wird zutreffend nicht zu einem vollständig grünen Wiederholungslauf umgedeutet.

## Befunde

1. **F-FINAL-1, P3 — Fokusreferenz-Docstring sachlich überholt.** `src/dispread/live/setup.py:559-560`: Die Aussage, ein Mittelbild könne nur zu milde und nie zu strenge Urteile erzeugen, gilt mit der neuen oberen Grenze nicht mehr. Eine kleinere Referenzschärfe kann den Quotienten über 1,05 erhöhen und einen Start sperren. Erklärung an den zweiseitigen Vergleich anpassen.
2. **F-FINAL-2, P3 — Falsche Overlay-Dateibenennung.** `docs/quellen/raster-recherche-2026-11-13/korpus/README.md:90-91`: Zu `truth-a1b1-*` werden „gleichnamige Bilder“ behauptet, die tatsächlichen Bilder heißen `live-20261113T*-still[-versuch-1].png`. Exakte Zuordnung nennen.
3. **F-FINAL-3, P3 — Veralteter Auswertungsstatus.** `docs/quellen/raster-recherche-2026-11-13/README.md:135-136`: „laufenden Ergebnissen“ steht unmittelbar vor dem abgeschlossenen Korpusbefund. Als abgeschlossen bezeichnen.
4. **F-FINAL-4, P3 — Vergleichsbild zeitlich falsch benannt.** `tests/test_dotlattice_setup_2026_11_13.py:49-61`: Testname `prior_setup` und Variable `prior_quad` bezeichnen das dokumentierte Folgebild von `still-versuch-1.png`. Als Folgebild-/Vergleichsquad benennen und Bewegungsvorbehalt nennen; Zahlen und Assertion erhalten.

## Bewusst abgegrenzte Punkte

- Das Fokusband ist konservativ und unkalibriert; es kann brauchbare Starts sperren und beweist weder Fokusatmung noch Maßstabsursache. Hardwareversuche waren ausdrücklich ausgeschlossen; OQ-74 und die nächste Hardwareabnahme bleiben offen. Dies ist keine offene Implementierungsreparatur.
- B1 sucht bei bereits akzeptierter ursprünglicher Hypothese keine konkurrierende Alternativgeometrie. Diese bewusst begrenzte, dokumentierte Suche erfüllt den vereinbarten Scope; eine globale Eindeutigkeitsgarantie wird nicht behauptet.
- Korpuswahrheit ist auf die geprüften Eingaben begrenzt. ROM-Offsetwarnungen bleiben erhalten; Quads anderer Bilder und alte erfolgreiche Fits werden nicht zu unabhängigen Sollgeometrien erklärt. Vorherige Aufgabenreviews haben die einzelnen Overlays und Truth-Prüfungen unabhängig geprüft; das Gesamtreview sichert deren unveränderte Artefakte und Integration.
- Audit-I/O-Fehler und Kamera-Neustartfehler verhindern weiter den Lauf. Wiederherstellung der aktiven UI-Warnung nach einem vollständigen Dienstneustart wird nicht versprochen; Auditdateien bleiben die dauerhafte Historie.
- Bestehende Timing-Lastempfindlichkeit wird anhand unveränderter isolierter Tests eingeordnet, ohne Schwellenänderung oder unbelegtes Sandboxetikett. Broad-Suite-Wiederholung und vollständige Rasterneuberechnung sind nicht erforderlich und wurden nicht durchgeführt.
- Keine neuen Protokolle, keine Referenzkorrektur der DUT-Erkennung, keine Mittelung von Messwertsprüngen, keine gehaltene ungeprüfte Lage und keine Änderung der Residualgrenzen gefunden. Kein Hardware-, Dienst-, var-/Eingabeschreibzugriff, Commit oder Merge durch dieses Review; geschrieben wird ausschließlich diese Datei.

## Re-Review der Schlusskorrekturen

`final-fix.diff`, `final-fix-report.md` und die tatsächlichen vier Stellen nachgelesen. **F-FINAL-1 bis F-FINAL-4 vollständig ADDRESSED / behoben; keine offenen Code- oder Dokumentationsfindings.** Der Docstring beschreibt die Wirkung des zweiseitigen Bands korrekt; die drei Truth-Dateien haben explizite richtige Overlay-Ziele; Korpusstatus und Folgebildherkunft sind richtig benannt. Alle drei Linkpaare zusätzlich schreibfrei gegen Existenz und den tatsächlichen `path` der Truth-Datei geprüft, Exit 0. Testzahlen, Vergleichsquad und 1-px-Assertion sind unverändert; nur Test-/Variablenname und Kommentar wurden korrigiert. Der CHANGELOG-Nachtrag erfüllt die Dokumentationspflicht. Zwei bestehende fokussierte Tests sowie Ruff und Diffprüfung sind im Implementierungsbericht grün belegt; keine erneute breite Prüfung erforderlich.

Zum Zeitpunkt dieses Re-Reviews waren nur die Doku-Gates noch ausstehend. Sie sind mit dem nachfolgenden Abschluss geschlossen. Die vier P3-Befunde sind behoben, nicht zurückgestellt.


## Abschließende Gate- und Berichtskontrolle

Die finalen Logs selbst nachgelesen; der Root hat zusätzlich die beendeten Prozesse mit Exit 0 bestätigt:

- `validation/docs-playwright.log`: **91 passed (6.3m)**, kein fehlgeschlagener oder als flaky ausgewiesener Fall.
- `validation/docs-build-verified.log`: **No issues found**, Build beendet in 68,70 s; enthält die letzten Quellenbeschriftungen und Links.
- `validation/ruff-verified.log`: **All checks passed!**; abschließendes `git diff --check` vom Root ebenfalls Exit 0.

Den aktuellen vollständigen `REPORT-codex.md` nach diesen Aktualisierungen erneut gelesen. Die Ergebniszahlen und Einschränkungen stimmen mit geprüften Quellen und Logs überein. Ursprüngliche Vollsuite (Exit 1), behobene vier Fake-/Goldenfehler, isoliert erfolgreiche Zeitgrenzentests, Corpus-Wrapper-Exit 143 sowie die später bestandenen Zusatztests sind transparent getrennt. Die Dokumentations-Browsertests liefen vor den letzten reinen Beschriftungs-/Linkpräzisierungen; deren erneuter strikter Build reicht aus, da Website-Logik und Gestaltung unverändert sind. Kein erfolgreicher Lauf wird erfunden und keine Warnung als uneingeschränkte Validierung dargestellt.

**Spezifikation: FREIGEGEBEN. Qualität und Integration: FREIGEGEBEN. Tests und Offline-Evidenz: FREIGEGEBEN. Dokumentation und REPORT: FREIGEGEBEN. Alle Aufgaben- und Gesamtbefunde geschlossen.** Kein erneuter Vollsuite- oder Corpuslauf erforderlich. Claude-Review, Übernahmeentscheidung und Hardwarekalibrierung bleiben die im Handoff vorgesehenen nächsten menschlichen Schritte; sie sind keine unerledigte Implementierung innerhalb dieser Freigabe.
