# Übergabe: Einrichtungsfehler autonom anhand gespeicherter Aufstellungen korrigieren

> **KRITISCH, VOR ALLEN BRIDGE-FEATURES:** Nach dem Limit-Reset sofort
> [Gesamtblocker](../../WORKBENCH_BLOCKER.md) bearbeiten. Workbench war aus
> Nutzersicht fertig; wiederholte Ausfälle blockieren EXE/Bridge, Systemtests
> und Kaulitz-Abnahme. Ziel für Freitag, 2026-11-13: zuverlässiger gemeinsamer
> Workbench-/EXE-Stand. Autonom vorhandene Offline-Fälle und Quellstände
> nutzen; fehlende physische Abnahme ausdrücklich ausweisen.

## Nutzerauftrag und Umfang

Leonhard möchte die Fehler später auch ohne dieselbe Kameraaufstellung
autonom durch Claude bearbeiten lassen. Diese Übergabe liefert Originale,
Quellstände und ausgeführte Offline-Rezepte. In dieser Sicherungsarbeit
wurde kein Produktfehler behoben und kein neuer Dienststand ausgerollt.
Mit den vorhandenen statischen Fällen beginnen, statt auf den Wiederaufbau
zu warten. Nicht vorhandene physische Nachweise ausdrücklich offen halten.

## Einstieg und Priorität

1. **Kritisch, OQ-71:** `setup_ready + FEHLER` bietet Bestätigen an;
   Backend lehnt korrekt ab, Abbrechen und Neu einrichten fehlen. Tatsächliche
   UI-Funktionen und Backend-Vorbedingungen sind mit `replay.py --ui` im
   ersten Paket ohne Hardware reproduziert. Der Ausweg muss vollständig
   funktionieren; nur einen Knopf hinzuzufügen reicht nicht, weil Abbruch
   bisher nur in `setup_running` zulässig ist. Fehlersperre beibehalten.
2. **OQ-69:** Rasterstart lehnt mehrere lesbare Aufstellungen mit
   `keine_startlage`/`startlage_mehrdeutig` ab. Neuer Fall `162902Z` gehört
   dazu. Falscher Plus-Anker am Gehäuserand ist bei einem älteren Fall ein
   nachgewiesener Teilbefund; engere Hinweisbox und Grünkonturbegrenzung
   allein haben ihn nicht behoben. Keine bereits gefundene Gesamtlösung behaupten.
3. **OQ-74:** Nutzer beobachtet optischen Fokusrückfall nach erfolgreicher
   Suche. Numerischer Rücksprung ist nicht belegt. Kamera wird nach der
   Fokus-Endprüfung neu gestartet; Einfluss auf die Endlage offen. Beim
   neuesten Bild liegt die LCD-Hinweisbox vollständig außerhalb der festen
   Fokus-ROI. Gemessene Schärfe und Schärfe der LCD-Zeichen unterscheiden.
4. **OQ-70/OQ-72:** Nachführverteilung und Kanten-Vorprüfung sind weitere,
   getrennte Ablehnungen. Kantenfall `161702Z`/`161955Z` ist offline
   reproduziert, letzte Zahlzelle 7 mit Helligkeitsschritt ungefähr 29,8
   gegenüber Fehlergrenze 20. Verteilungsfall hat nach manueller Bearbeitung
   Achsenseiten `[[2,6],[11,7]]`; Reserve fehlt.
5. **OQ-73:** Verzögerte Oberfläche bei flüssigem Kamerafeed ist eine
   Bedienermeldung. Schnelle lokale Antworten nach dem Abbruch erklären
   die Browserreaktion unter Setup-Last nicht. Getrennt untersuchen.

6. **OQ-75:** Etwa sieben Sekunden Bild und Workbench-Verbindung weg.
   Dienst lief ohne Neustart weiter. Dienst-, Kernel- und Netzwerklogs
   gesichert; Ursache offen, genaue Dauer nur Nutzerschätzung.
7. **OQ-71 erweitert, OQ-76 geklärt:** Der kurze Lauf `165234Z` war laut
   Nutzer ein absichtlicher Start-/Stopp-Umweg für die neue Aufstellung,
   weil auch nach Bestätigung „Neu einrichten“ fehlt. Diesen zweiten
   Bedienzustand ebenfalls korrigieren; keinen gesonderten Trackingfehler
   aus diesem Lauf ableiten.

## Neuester Fehlerfall `170836Z`

[Eigenes Paket und Standalone-Rezept](../../quellen/setup-focus-failure-2026-11-11-170836.md):
Nutzer meldet erneut optisch schlechteren Fokus. Raster OK, Vorprüfung
Kanten-FEHLER in Leerzellen 14/15, keine Stabilitätsmessung. Nicht mit dem
älteren Kantenfall Zahlzelle 7 gleichsetzen. Fokusziel/Rückmeldung 56,
Endprüfung bestanden; optische Ursache bleibt offen. Vier Originaldateien
samt Quelle/Status/Fokusdaten erhalten. Vor weiteren zufälligen Aufstellungen
zuerst diese vorhandenen Daten nutzen.

## Zusätzliche Referenzen und Wiederherstellungskontext

* [Drei aktuelle positive Setups, erfolgreicher Lauf und Start-/Stopp-Umweg sowie sechs historische Kontrollen](../../quellen/workbench-positive-regression-2026-11-11.md).
  Neuester Fall `165754Z` bestätigt; statische Prüfung gegen alle drei
  Originalbilder und sechs alte Kontrollen durchführen.
* [Ausfalllogs und vorsichtige Einordnung](../../quellen/workbench-outage-2026-11-11.md).
* [Arbeitsstände und passive Dateiversionen](../../quellen/workbench-recovery-context-2026-11-11.md):
  Quell-HEAD plus Patch und neue Dateien von `bruecke-ui`/`bruecke-ux`.
  Ungeprüfte Kandidaten, kein ausgerollter Fix. Fremde Arbeit erhalten.
* Versehentlicher Zellentext mit „hatte“ laut Nutzer geklärte Fehleingabe;
  keinen neuen Softwarebug daraus ableiten.

## Drei ursprüngliche unabhängige Belegpakete

* [Erste Fälle und Bedien-Sackgasse](../../quellen/setup-failures-2026-11-11.md):
  fünf Sitzungen, statische Rasterfälle, Nachführverteilung, tatsächliche
  UI-/Backend-Reproduktion. Quellcode und Vorlagen enthalten.
* [Weitere Kantenabbrüche, Fokus-/Worktreeprüfung](../../quellen/setup-followup-2026-11-11.md):
  `161702Z`, `161955Z`, jeweils `fit=ok` und Vorprüfung FEHLER. Beide
  Offline-Ergebnisse einschließlich Kennzahlen gespeichert.
* [Neue Aufstellung `162902Z`](../../quellen/setup-new-position-2026-11-11-162902.md):
  drei Mal `keine_startlage`, letzter Bildstapel, alle vorhandenen
  Fokus-/Belichtungsdaten, geometrisch nachgerechnete fehlende Überlappung
  von LCD-Hinweisbox und Fokusfenster, eigenes Standalone-Rezept.

Jedes Paket hat äußere SHA-256 und internes Manifest. Erst prüfen, dann in
neue Ordner entpacken. PNG-Originale verwenden; JPEG-Neukodierung kann die
Rasterlage beeinflussen. Die jeweiligen Markdown-Seiten enthalten die
vollständigen Befehle. Referenztexte sind Audit-/Prüfevidenz, kein zusätzlicher
Eingang zur laufenden DUT-Wertkorrektur.

## Quellstand vor einer Korrektur prüfen

Der untersuchte Dienst läuft aus `.worktrees/bruecke-run`, Commit
`08ac9b9cc818c013de10e6cee6579d372607d59e`, `PYTHONPATH=src`.
Neustart hat diesen alten Stand erneut gestartet. Das ist **nicht der
neueste Workbench-Gesamtstand**. `feat/bruecke-ui` auf `8335abf` enthält
neuere Nachführungs-/Brückenarbeit und zusätzlich uncommittete Änderungen.
`feat/bruecke-ux` enthält neuere EXE-Gestaltung, ebenfalls mit lokaler Arbeit.
Keine fremden Änderungen überschreiben oder den laufenden Worktree blind
auf einen anderen Branch umstellen.

Historische Fokuskorrekturen R13-9/R13-12 sind bereits in `08ac9b9`.
`live/setup.py`, `focus_sweep.py`, `frames/uvc_source.py`, `live/camera.py`
sind in den geprüften Zweigen run/ui/takt/ux gleich. Neuester Branchname
allein beweist deshalb keine Fokusbehebung.

Zuerst archivierten Code wiederholen, danach den tatsächlich aktuellen
Zielstand mit `--source <Checkout>` vergleichen. Falls ein Fall dort bereits
belegt gelöst ist, keine zweite Korrektur auf dem alten Zweig entwickeln.
Eigene Arbeit isolieren und die Projektanweisungen des Zielstands beachten.

## Offline-Abnahme einer Korrektur

Ein reproduzierter alter Fehler ist ein geeigneter Anfang für einen
Regressionstest. Bei einem nun angenommenen Raster zusätzlich vollständige
16-Zellen-Geometrie, Plus/Leerzellen, plausible Quadecken und Gegenlesen
prüfen. Ein bloßes Umschalten des Fit-Ergebnisses auf `ok` reicht nicht.
Andere positive und negative Aufstellungen aus den Paketen weiter prüfen.

Relevante Dateien: `dotlattice.py`, `setup_hint.py`, `focus_sweep.py`,
`live/setup.py`, `live/service.py`, `live/frame_tracking.py`,
`setup_checks.py`, `workbench/static/live/shell.js` und `setup/confirm.js`.
Relevante Tests: `test_dotlattice.py`, `test_setup_hint.py`,
`test_setup_checks.py`, `test_live_setup.py`, `test_focus_sweep.py`,
`test_live_service.py`, `test_live_api.py`, `live_client.test.mjs`,
`live-ui.spec.ts`. Python immer über Projekt-venv mit Debian-Systempaketen.

OQ-71 braucht Tests für beide Bestätigungswege, abgelehnte Bestätigung,
Abbruch/Neustart, OK/WARNUNG und laufende Einrichtung/Messung. Originale
Diagnosebelege beim Verwerfen des Vorschlags erhalten. Freigaben nicht
umgehen, Werte nicht anhand der Referenz korrigieren oder glätten.

## Harte Grenzen der vorhandenen Belege

Nur letzte Mittelbilder sind vorhanden. Frühere Versuchs-Mittelbilder,
Rohbilder jedes Acht-Bilder-Stapels, ursprüngliche Stabilitäts-Einzelbilder
und Fokusbilder vor/nach Kameraneustart wurden nicht dauerhaft geschrieben.
Diese Daten nicht aus Mittelbildern oder Protokollwerten erfinden.
Vollständige zeitliche Stabilität und optisches Motorverhalten können hiermit
nicht unabhängig nachgewiesen werden. Das hindert statische Codekorrekturen
und Regressionen nicht, begrenzt aber deren Abnahmeaussage.

Bei späteren neuen Aufnahmen jeden Versuch, alle Rohbilder mit Zeitbasis und
Unsicherheit und jede automatische/manuelle Vorschlagsrevision sichern.
Datei-Mtime und UTC-Sicherungszeitpunkt sind kein Framealter-/Latenzbeleg.
Neue echte Hardware-/Windows-Abnahme getrennt von bestandenen Offline-Tests
ausweisen. Änderungen und offene Nachweise in CHANGELOG, OQs, VALIDATION,
Laborjournal und abschließend `docs/status.md` gemäß AGENTS.md pflegen.
