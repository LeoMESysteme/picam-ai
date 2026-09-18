# Status — Stand 2026-09-18

Wird **überschrieben**, nicht angehängt. Historie und Messaufbauten stehen in
[project_history.md](project_history.md) und [lab_journal.md](lab_journal.md).
Die volle Entstehungsgeschichte (Task-für-Task, je mit Implementierung →
Review → ggf. Fix-Runde → Re-Review, plus das abschließende
Gesamtbranch-Review mit eigener Fix-Runde) steht im `CHANGELOG.md`; dieser
Abschnitt beschreibt nur den **aktuellen** Endzustand.

## Sofort zu wissen

Branch `ocr-selbstkalibrierung`, HEAD `595a9ff`. Alle 12 Tasks des
[Selbstkalibrierungsplans](PLAN_2026-09-11-ocr-selbstkalibrierung.md) sind
umgesetzt bzw. bewusst gesperrt (Task 11). Ein anschließendes
Gesamtbranch-Review (extern durchgeführt, während der ursprüngliche Reviewer
kurzzeitig ratenlimitiert war, dann von Claude übernommen und in Teilen
selbst nachverifiziert) fand acht echte Integrationsprobleme, die aus
keiner Einzel-Task-Prüfung sichtbar gewesen wären (R1–R8b). Eine
eigens dafür angesetzte Fix-Runde hat **alle acht behoben**, ein
Re-Review hat das bestätigt (inkl. eigenständiger Nachvollziehung der
sicherheitsrelevanten Nebenläufigkeitsänderungen und Reproduktion der
RED-Belege gegen den unbereinigten Baum).

**Merge-Einschätzung: bereit, mit dokumentierten Restpunkten (siehe unten) —
keiner davon ist tragend für Korrektheit oder Sicherheit.**

**Task-Stand im Einzelnen:**

* **Tasks 1–9:** gebaut, getestet, reviewt — siehe CHANGELOG für die
  Einzelfunde. Nennenswert:
  - Task 1: `src/dispread/frames/replay_source.py`, `CLIP_SCHEMA_VERSION=1`.
  - Task 2: Clipaufnahme im Controller (`clip.start`/`clip.stop`), inkl. eines
    in der Fix-Runde behobenen Deadlocks in `_clip_stop()`.
  - Task 3: `src/dispread/benchmark.py` + `scripts/ocr-benchmark.py` —
    Baseline auf den sechs gelabelten realen Annotationen: **5 korrekt, 0
    falsch, 1 abgelehnt** (siehe [VALIDATION.md](VALIDATION.md); die
    Dezimalstellen-Erkennung wurde im Gesamtbranch-Review nachgeschärft,
    siehe R3 unten — eine Reproduktion mit dem korrigierten Benchmark steht
    noch aus).
  - Task 4: `src/dispread/ocr/autofit.py`, `fit_layout` — Fund:
    `thickness_ratio`/`inset_ratio` sind für den aktuellen
    Punktabtast-Decoder strukturell wirkungslos (nie gelesen in
    `sevenseg.py`); zwei gleich gut punktende, unterschiedliche
    Parametersätze am realen Datensatz gefunden ([OQ-28](open-questions.md)).
  - Task 5: Autofit in der Workbench-UI verdrahtet, Einrichtung per
    getipptem Wert statt nur per Regler.
  - Task 6/7: `src/dispread/track.py`, `QuadTracker` — begrenzte
    ECC-Nachregistrierung eines bestätigten Quads, immer gegen die
    Bestätigungsreferenz, nie Frame-zu-Frame (Drift-Vermeidung); in
    `Controller.publish()`/`_read()` eingebunden, `tracking_lost` blockiert
    die Freigabe (`GateConfig.blocking_flags`).
  - Task 8: Nachführungsgüte sichtbar — `reading.track`-Zeile in der
    Einstelltabelle, dritte Overlay-Farbe im Livebild; Review fand und behob
    einen Absturz (`kind="text"` statt `"info"` ließ `dispread tui`
    crashen — siehe [OQ-32](open-questions.md) für die verbleibende Lücke).
  - Task 9: `DisplayLayout.polarity` (LED/LCD) — schließt OQ-13 Fall 2. Fall 1
    (Anzeige zeigt ausschließlich „8") bleibt offen, unverändertes,
    unabhängiges Problem. Self-Review fand zusätzlich, dass
    `saturated_fraction` auf dem für `dark_on_bright` umgekehrten Bild
    berechnet wurde und eine echte Reflexion verschluckte — behoben, eigener
    Commit.
* **Task 10:** war bereits erledigt — reiner Doku-Task, dessen Inhalt in den
  Eröffnungscommit dieses Plans eingeflossen war.
* **Task 11 (Messänderung am Decoder): bleibt gesperrt.** Zuletzt vor Task 12
  gegen die realen Daten geprüft: `var/workbench/annotations/` hat 9
  Einträge (`ground_truth_text` ∈ {11,00 / 12,76 / 28,80} plus unlabeled),
  `var/workbench/clips/` hat **4 reale, persistente Clips** (je 75 Frames,
  `device_id="RND Lab"`, Werte {0.000, 28,80}) — echte, zwischen Sitzungen
  aufgenommene Daten aus dem Tagesbetrieb der Workbench, keine Testartefakte.
  Kombiniert bleibt es bei **einer** Geräteinstanz. Sperrbedingungen 1
  (≥ 6 Geräteinstanzen/≥ 3 Displaytypen) und 3 (≥ 8 Werte inkl.
  Vorzeichenwerten und 0/8 an jeder Ziffernstelle) **nicht erfüllt**;
  Bedingung 5 (Task 3's Baseline-Messung) **erfüllt**. Kein Code für Task 11
  angefasst. Die RND-Labs-Aufnahmen belegen keine geräteübergreifende
  Decoderqualität.
* **Task 12:** Doku-Abschluss — `project_history.md`, `open-questions.md`
  (OQ-26–OQ-32), `ROADMAP.md`, `CLAUDE.md`, diese Datei.
* **Gesamtbranch-Review (nach Task 12) + Fix-Runde:** acht Funde (R1–R8b),
  alle behoben — Details im nächsten Abschnitt.

**Neue Erkenntnis, wert es hier festzuhalten:** Die echte Clipaufnahme aus
Task 2 wird inzwischen tatsächlich im Laborbetrieb genutzt — die vier realen
Clips unter `var/workbench/clips/` sind der erste Beleg dafür, dass reale
Datensammlung für ROADMAP-P2 begonnen hat. Das Werkzeug-Problem ist damit
gelöst, das Diversitätsproblem (eine Geräteinstanz) nicht.

**Nebenbei, unabhängig von diesem Plan:** Ein `docs-cleanup`-Durchlauf auf
`master` prüfte die Projektdokumentation gegen den aktuellen Code und fand
**nichts Korrekturbedürftiges** — `master` blieb von der Arbeit an diesem
Plan unberührt (diese lief ausschließlich auf `ocr-selbstkalibrierung`).

## Gesamtbranch-Review: acht Funde, alle behoben

Ein Review über den gesamten Branch (nicht nur je Einzel-Task) fand acht
Integrationsprobleme, die keine Einzel-Task-Prüfung hätte sehen können. Eine
Fix-Runde hat alle acht behoben (4 Commits, je mit CHANGELOG-Eintrag); ein
Re-Review hat jeden Fund unabhängig nachvollzogen, inkl. eigenständiger
Reproduktion der Fehlschläge gegen den unkorrigierten Baum.

* **R1 (behoben):** Die Autofit-Vorschau zeichnete das alte (bestätigte)
  Raster statt des vorgeschlagenen; die Bestätigung übernahm dann ein Layout,
  das der Bediener nie gesehen hatte. Server liefert jetzt `ocr_grid` für den
  Vorschlag mit; Polling überschreibt den anstehenden Vorschlag nicht mehr.
* **R2 (behoben):** Eine laufende Clipaufnahme lief nach einer
  Konfigurationsänderung (ROI/Layout/Kamera) zwischen zwei Bildern unbemerkt
  mit dem alten Profil weiter. `_change()` beendet jetzt eine laufende
  Aufnahme (nicht-blockierend, bestehender Deadlock-Fix bleibt intakt).
* **R3 (behoben):** Der Benchmark entfernte Dezimaltrenner ohne
  Positionsprüfung — ein Faktor-10-Fehler (`28.80` vs. `288.0`) zählte als
  „korrekt". Eine eigene `decimal`-Fehlerklasse ist jetzt implementiert
  (das Datenklassen-Docstring hatte sie schon lange versprochen).
* **R4 (behoben):** Relative Clip-Pfade wurden als Replay-URL falsch
  aufgelöst (`var` wurde zur URL-Autorität statt zum Pfad). Neue
  `path_uri()`/`_filesystem_path()`-Helfer in `frames/__init__.py`.
* **R5 (behoben, mit dokumentierter Lücke):** `profile_name` war kein
  Nachweis physischer Geräteidentität — ein Gerät unter zwei Profilnamen
  konnte fälschlich als „disjunkt" durchgehen. Verlangt jetzt einen
  expliziten `device_id`; verweigert die Zertifizierung statt zu raten.
  **Lücke:** noch kein Bedienfeld, über das eine Annotation eine
  `device_id` bekommt — Annotationen ohne sie werden im `--dev/--test`-Pfad
  korrekt abgelehnt (strengere Prüfung, nicht schwächer als vorher); der
  einzige heute mit echten Daten genutzte `--annotations`-Pfad ist davon
  nicht betroffen.
* **R6 (behoben):** Das Clip-Manifest wurde vor erfolgreichem Schreiben
  finalisiert; ein fehlgeschlagenes `imwrite` hinterließ fehlende Dateien
  ohne ehrliche Bilanz. Der Schreib-Thread trägt jetzt als einzige Stelle
  erfolgreich geschriebene Frames ins Manifest ein und schreibt `clip.json`
  selbst als letzten Schritt; neues Feld `write_failures` trennt echte
  Schreibfehler von wegen voller Warteschlange verworfenen Bildern.
* **R7 (behoben):** Der Autofit-Sollwertparser akzeptierte mehrfache/
  vermischte Vorzeichen (`--12`, `+-12`). Genau ein führendes Vorzeichen wird
  jetzt verlangt, alles andere wird abgelehnt.
* **R8a (behoben, = [OQ-31](open-questions.md), jetzt geklärt):** Eine
  manuelle Regler-Bearbeitung nach einem erfolgreichen Autofit konnte beim
  Bestätigen vom alten Vorschlag überschrieben werden. Neues
  `invalidateAutofit()` verwirft den Vorschlag bei jeder manuellen
  Layout-Änderung, auch bei einer noch ausstehenden Autofit-Antwort.
* **R8b (behoben, wie vom Betreuer entschieden):** Die Nachführungsanzeige
  blieb zwischen gedrosselten OCR-Zyklen stehen, auch wenn die Nachführung
  im aktuellen Bild bereits verloren war. `reading["track"]` wird jetzt
  jedes Bild aktuell gehalten; der zwischengespeicherte Rohwert/Freigabestatus
  bleibt unverändert (keine Drosselungsregression). Ausdrücklich **kein**
  Nachweis, dass ein neu ausgewerteter Messwert die Freigabe umgehen könnte.

**Verbleibende, nicht blockierende Restpunkte** (alle vom Re-Review geprüft
und als nicht tragend eingestuft):
- R5s Bedienfeld-Lücke (oben).
- Ein tatsächlich hängender Schreib-Thread (z. B. volle Festplatte) liefert
  jetzt gar kein `clip.json` statt eines unehrlich vollständigen — die
  richtige Richtung, kein normaler Abschaltpfad kann das auslösen.
- `tests/test_workbench.py`/`test_replay_source.py` bauen an einzelnen
  Stellen noch `f"replay://{path}"` von Hand — genau das Muster, das die neue
  `frames/__init__.py`-Konvention verbietet; unschädlich (absolute
  `tmp_path`-Pfade haben keine URL-Autorität), aber inkonsistent.
- `camera.set`/`camera.set_many` rufen `invalidateAutofit()` nicht auf —
  beißt heute nicht (der nachfolgende `layout.set_many` beim Bestätigen
  stempelt die Revision ohnehin neu), aber aus Zufall, nicht aus Design.
- R3s neue `decimal`-Klasse kann nur einen Profil-Dezimalpositionsfehler
  erkennen (der Leser setzt den Punkt aus dem Profil, nicht optisch —
  [OQ-17](open-questions.md)), noch nicht ein tatsächlich falsch gelesenes
  Komma.

## Implementierter Stand

Die Verarbeitungskette (siehe `CLAUDE.md`, Abschnitt „Aufbau") hat eine
zusätzliche, austauschbare Trennstelle `track` zwischen `detect/` und
`rectify`: `QuadTracker` registriert eine bestätigte Anzeige innerhalb enger
Grenzen neu nach, bevor gelesen wird. `frames/` kennt jetzt zwei lauffähige
Schemata (`synthetic://`, `replay://`); `picamera2://`, `imx500://`,
`folder://`, `video://` bleiben `ImportError`.

Alles Bisherige aus früheren Sitzungen bleibt unverändert gültig: zweistufige
manuelle ROI-/OCR-Box-Kalibrierung, Bildpfad-Entkopplung, OCR-Drosselung,
`dispread stop`, RP2040-Power-Zyklus-Budget ([OQ-22](open-questions.md)),
`manual_roi` als Primärpfad — kein automatisch übernommener Wert ohne
expliziten ✓-Klick, auch nicht durch Autofit oder Nachführung.

## Verifiziert

```text
./.venv/bin/pytest -q                                      210 passed
./.venv/bin/ruff check src tests examples scripts           All checks passed!
node --check src/dispread/workbench/static/workbench.js     Exit 0
```

Reale Messungen aus dieser Sitzung stehen in [VALIDATION.md](VALIDATION.md):
Benchmark-Baseline (Task 3, vor der R3-Korrektur — eine Reproduktion mit dem
korrigierten Benchmark ist ein offener Folgeschritt, kein rückwirkend
widerlegtes Ergebnis, da R3 nur Dezimalpositionsfehler betrifft), Autofit
gegen die sechs Annotationen (Task 4), Nachführung auf realen Bildern
(Task 6). Manuelle Browser-/Hardwareabnahme (Clipaufnahme am echten Gerät,
Kalibrierschritt im Browser, Nachführung bei echtem Kamerastoß während eines
Laufs) steht weiterhin aus — [OQ-21](open-questions.md)/[OQ-24](open-questions.md).

## Offene reale Abnahme

* Kalibrierschritt (Autofit) und Clipaufnahme im echten Browser gegen eine
  angeschlossene Kamera — nicht aus `synthetic://`-/`replay://`-Tests
  ableitbar ([OQ-21](open-questions.md)/[OQ-24](open-questions.md)).
* Nachführungsverhalten, wenn die Kamera während eines laufenden Betriebs
  tatsächlich angestoßen wird — [OQ-26](open-questions.md).
* BK-5491B-VFD-Rastererkennung ([OQ-23](open-questions.md)), GSVmulti-
  Telegrammformat ([OQ-01](open-questions.md)/[OQ-07](open-questions.md)),
  RS-232-Transceiver ([OQ-09](open-questions.md)), RP2040-Bridge-Fehler
  ([OQ-22](open-questions.md), bei Raspberry Pi gemeldet, kein Fix ohne
  Reboot verifiziert) — unverändert offen, von dieser Sitzung nicht berührt.

## Neu erkannte offene Punkte aus dieser Sitzung

Die Reviews von Task 5, 7 und 8 deckten vier weitere Unbekannte auf, die
über die drei im Plan selbst schon benannten (OQ-26–OQ-28) hinausgehen. Alle
sieben stehen in [open-questions.md](open-questions.md):

* [OQ-26](open-questions.md) — Nachführungsschwellen (`max_shift`,
  `max_rotation_deg`, `min_score`) unvalidiert an echten Geräten. Offen.
* [OQ-27](open-questions.md) — Rasterfeinschliff je Bild bewusst nicht
  gebaut. Offen.
* [OQ-28](open-questions.md) — Eindeutigkeit der Autofit-Geometrie
  (`flat_optimum`) an echten Geräten ungeprüft. Offen.
* [OQ-29](open-questions.md) — `calibrated_on`/`calibrated_on_frame_sequence`
  wird beim Autofit-Treffer gesetzt, nicht erst bei der Bestätigung. Offen,
  begrenzte Auswirkung (nur `clip.json`-Provenienz).
* [OQ-30](open-questions.md) — `roi`-Op committet die Bestätigung, bevor der
  `QuadTracker` aufgebaut wird. Offen, selbstlimitierend.
* [OQ-31](open-questions.md) — **Geklärt (2026-09-18)** durch R8a: eine
  Autofit-Stale-State-Lücke bei manueller Regler-Bearbeitung ist behoben,
  mit Regressionstest.
* [OQ-32](open-questions.md) — `edit_row()`/`_row()` haben keinen sicheren
  Fallback für einen unbekannten `kind`. Der akute Absturz (Task 8) ist
  gefixt, die zugrunde liegende Lücke nicht. Offen.

Keiner dieser Punkte blockiert etwas Bereits-Gebautes; alle sind Kandidaten
für künftige Aufgaben.

## Vom Nutzer präzisiertes Produktziel — separate Architekturfrage

Der Nutzer hat den eigentlich gewünschten Endanwender-Ablauf präzisiert und
ausdrücklich von den obigen Review-Fixes getrennt gehalten: Start → Anzeigen
automatisch erkennen → gewünschte Anzeige auswählen → Segmentraster
automatisch einpassen → lesen; auch bei schräger Ansicht. Hunderte
Displaytypen, keine vom Endanwender zu erstellenden Trainingsdaten/
Annotationen und keine aufwendige Einrichtung je Gerät im Normalbetrieb.

Der jetzige Sollwert-Autofit (Task 4/5 dieses Plans) ist damit ausdrücklich
ein Fallback, keine Erfüllung dieses Ziels. Diskutiert, aber **nicht
ausgewählt, implementiert oder validiert**: ein vortrainierter
Anzeige-/Text-Detektor + spezialisierte Siebensegment-Erkennung +
automatische Geometrieanpassung/lokale Nachführung; ggf. synthetisch erzeugte
Trainingsbilder in der Entwicklung; optionale Cloud-Einrichtungshilfe. Kein
Cloud-Anbieter gewählt, keine Bilder hochgeladen, keine
Genauigkeits-/Performance-Behauptung aufgestellt.

**Nächster Architekturschritt:** Kandidatenvergleich und eine gemeinsam
abgestimmte Planrevision — ein separates Gespräch, keine Ableitung aus den
obigen Bugfixes. Die Sperrbedingungen von Task 11 (Produktionsänderung am
Decoder) gelten unverändert und werden durch nichts hier stillschweigend
aufgehoben.
