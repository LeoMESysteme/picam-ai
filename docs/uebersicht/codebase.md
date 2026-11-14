---
weg: projekt
hide:
  - toc
---

# Codebase im Überblick

Diese Seite zeigt den Code des Projekts selbst: wie er gewachsen ist, wie
die Branches verlaufen, wann gearbeitet wird, woraus er besteht, wo er
schwer zu prüfen ist und was aufgeräumt werden kann. Sie richtet sich an
Entwickler und an alle, die einen Eindruck von Umfang und Zustand
bekommen wollen. Für das Messsystem selbst gibt es die
[Projekt-Tour](projekt-tour.md) und den [Messpfad](messpfad.md).

Alle Zahlen erzeugt `scripts/codebase-facts.py` aus Git und dem Quelltext;
keine davon ist von Hand eingetragen. Der Stand steht in der ersten Zeile
unten. Die interaktive Bühne zeigt dieselben Daten; ohne JavaScript oder
in der ruhigen Darstellung bleiben die Tabellen die Quelle.

<div id="codebase-stage" class="wiki-codebase-stage"></div>

<!-- CODEBASE-FACTS:BEGIN -->
Stand: Commit `d6d5ab5` auf `master`, erzeugt am 14.11.2026.

## Wachstum {#wachstum}

Der Bestand wuchs von 2.322 Zeilen am 07.09.2026 auf 214.460 Zeilen in 792 Dateien; davon sind 65.669 Code (Kern, Werkbank, Brücke, Skripte), 67.100 Tests und 80.871 Doku. Daten- und Fremddateien zählen nicht mit.

<div class="wiki-chart" data-chart="bar" data-title="Zeilen am Ende jeder Kalenderwoche" data-unit="Zeilen" markdown="1">

| Woche | Zeilen |
| --- | --- |
| KW 37 (ab 07.09.) | 22.936 |
| KW 38 (ab 14.09.) | 28.699 |
| KW 39 (ab 21.09.) | 52.648 |
| KW 40 (ab 28.09.) | 77.385 |
| KW 41 (ab 05.10.) | 77.385 |
| KW 42 (ab 12.10.) | 92.428 |
| KW 43 (ab 19.10.) | 108.554 |
| KW 44 (ab 26.10.) | 133.531 |
| KW 45 (ab 02.11.) | 163.187 |
| KW 46 (ab 09.11.) | 214.460 |

</div>

## Branches {#branches}

Neben dem Fokus `master` gibt es 44 Refs: 9 still, 9 offen und 26 gemergt. Insgesamt enthält die Historie 677 Commits und 49 Merges.

| Branch | Zustand | Commits (nicht im Fokus) | letzter Commit |
| --- | --- | --- | --- |
| `test/clahe-ocr-accuracy` | still | 4 | 10.09.2026 |
| `codex/automatic-seven-segment` | still | 1 | 18.09.2026 |
| `docs/oq22-rp2040-wedge` | still | 3 | 24.09.2026 |
| `docs/zensical-prototyp` | still | 1 | 24.09.2026 |
| `codex/MEM-6-c2-scripts-pi-housekeeping-py-bericht-und-freigegebenes-aufr-umen` | still | 1 | 14.10.2026 |
| `wip/haupt-checkout-2026-10-21` | still | 1 | 21.10.2026 |
| `exp/r13-fenster-tracker` | still | 1 | 22.10.2026 |
| `feat/messpfad-live` | still | 1 | 22.10.2026 |
| `worktree-feat-messpfad-live` | still | 1 | 22.10.2026 |
| `feat/installer-p0` | offen | 9 | 14.11.2026 |
| `feat/integration` | offen | 14 | 14.11.2026 |
| `feat/wiki-lebendig` | offen | 4 | 14.11.2026 |
| `fix/kleine-backend` | offen | 2 | 13.11.2026 |
| `wip/bruecke-ux3` | offen | 6 | 14.11.2026 |
| `docs/workbench-critical-2026-11-11` | offen | 2 | 11.11.2026 |
| `feat/gsvmulti-bridge` | offen | 1 | 11.11.2026 |
| `fix/wiki-export-master` | offen | 2 | 11.11.2026 |
| `fix/session-explorer-test-wackelt` | offen | 1 | 04.11.2026 |
| `exp/r13-randpruefung-grob` | gemergt | 0 | 22.10.2026 |
| `codex/session-explorer` | gemergt | 0 | 28.10.2026 |
| `docs/gsvmulti-userdefined` | gemergt | 0 | 28.10.2026 |
| `feat/session-explorer` | gemergt | 0 | 30.10.2026 |
| `fix/hinweis-test-ohne-scroll` | gemergt | 0 | 30.10.2026 |
| `feat/r13-display-haertung` | gemergt | 0 | 30.10.2026 |
| `fix/r13-24-aehnlichkeit-kleiner-versatz` | gemergt | 0 | 30.10.2026 |
| `merge/r13-nach-master` | gemergt | 0 | 30.10.2026 |
| `fix/kamera-neustart-protokoll` | gemergt | 0 | 31.10.2026 |
| `feat/r13-25-stabile-rahmenregionen` | gemergt | 0 | 04.11.2026 |
| `feat/session-laufmatrix` | gemergt | 0 | 04.11.2026 |
| `fix/devdata-diagnose-pfad` | gemergt | 0 | 04.11.2026 |
| `integration/2026-11-04` | gemergt | 0 | 04.11.2026 |
| `codex/windows-bridge-core` | gemergt | 0 | 06.11.2026 |
| `feat/werkbank-redesign` | gemergt | 0 | 06.11.2026 |
| `feat/bruecke-merge` | gemergt | 0 | 11.11.2026 |
| `feat/bruecke-takt` | gemergt | 0 | 11.11.2026 |
| `feat/bruecke-ux` | gemergt | 0 | 11.11.2026 |
| `fix/blocker-oq70` | gemergt | 0 | 12.11.2026 |
| `fix/blocker-oq71` | gemergt | 0 | 12.11.2026 |
| `fix/blocker-oq74` | gemergt | 0 | 12.11.2026 |
| `tmp/bruecke-merge` | gemergt | 0 | 11.11.2026 |
| `feat/bruecke-ui` | gemergt | 0 | 12.11.2026 |
| `fix/blocker-oq69` | gemergt | 0 | 12.11.2026 |
| `fix/blocker-oq72` | gemergt | 0 | 12.11.2026 |
| `fix/rahmen-raster` | gemergt | 0 | 13.11.2026 |

## Rhythmus {#rhythmus}

Freitag ist mit 222 von 677 Commits (33 %) der stärkste Tag, die Spitzenstunde liegt bei 14 Uhr (91 Commits). An 39 von 69 Tagen gab es Commits (Zeiten in Berlin).

<div class="wiki-chart" data-chart="bar" data-title="Commits je Wochentag" data-unit="Commits" markdown="1">

| Wochentag | Commits | Anteil |
| --- | --- | --- |
| Montag | 77 | 11 % |
| Dienstag | 67 | 10 % |
| Mittwoch | 189 | 28 % |
| Donnerstag | 93 | 14 % |
| Freitag | 222 | 33 % |
| Samstag | 24 | 4 % |
| Sonntag | 5 | 1 % |

</div>

## Struktur {#struktur}

Die 792 Dateien verteilen sich auf sieben Bereiche; am größten ist „Doku“ mit 80.871 Zeilen. Auf Tests kommen 1,02 Zeilen je Codezeile.

<div class="wiki-chart" data-chart="bar" data-title="Zeilen je Bereich" data-unit="Zeilen" markdown="1">

| Bereich | Zeilen | Dateien | größte Datei (Zeilen) |
| --- | --- | --- | --- |
| Kern | 13.335 | 64 | `src/dispread/benchmark.py` (954) |
| Werkbank & Live | 23.288 | 79 | `src/dispread/live/frame_tracking.py` (1.720) |
| Windows-Brücke | 13.288 | 53 | `windows/bridge/src/dispread_bridge_app/app_controller.py` (1.278) |
| Skripte | 15.758 | 54 | `scripts/sync-record.py` (1.619) |
| Tests | 67.100 | 181 | `tests/test_live_service.py` (3.628) |
| Doku | 80.871 | 203 | `docs/VALIDATION.md` (6.764) |
| Infrastruktur | 820 | 20 | `zensical.toml` (183) |

</div>

## Komplexität {#komplexitaet}

Von 2.350 Python-Funktionen außerhalb der Tests haben 278 (11,8 %) eine Komplexität über 10 und 26 über 40. Die komplexeste ist `Controller.command` mit 91.

<div class="wiki-chart" data-chart="bar" data-title="Die zwölf komplexesten Funktionen" data-unit="Komplexität" markdown="1">

| Funktion | Komplexität | Ort | Zeilen |
| --- | --- | --- | --- |
| `Controller.command` | 91 | `src/dispread/workbench/controller.py:480` | 319 |
| `BridgeSession.exchange` | 78 | `src/dispread/gsv_bridge.py:129` | 181 |
| `chips` | 76 | `windows/bridge/src/dispread_bridge_app/ui/texts.py:507` | 149 |
| `_auto_fit` | 75 | `src/dispread/dotlattice.py:545` | 202 |
| `LiveSession.step` | 69 | `src/dispread/live/session.py:504` | 150 |
| `run` | 67 | `scripts/import-harvest.py:385` | 376 |
| `validate` | 63 | `src/dispread/workbench/profiles.py:67` | 98 |
| `compare` | 61 | `scripts/r13-coarse-eval.py:106` | 82 |
| `FrameTrackingConfig.__post_init__` | 56 | `src/dispread/live/frame_tracking.py:338` | 46 |
| `evaluate_records` | 54 | `src/dispread/live/reference_eval.py:41` | 112 |
| `LiveService.status` | 52 | `src/dispread/live/service.py:268` | 132 |
| `AppController._load_state` | 52 | `windows/bridge/src/dispread_bridge_app/app_controller.py:357` | 66 |

</div>

## Zustand {#zustand}

Die Suche findet 8 ungenutzte Definitionen (43 Zeilen), 0 verwaiste Skripte, 9 stille Branches und 15 Quelldateien über 800 Zeilen. Das sind Hinweise zum Aufräumen, keine geprüften Fehler.

| Befund | Anzahl | Methode |
| --- | --- | --- |
| Ungenutzte Definitionen | 8 | Top-Level-Funktionen und -Klassen (per ast, ohne Decorator, ohne test_*, main und dunder) in Kern, Werkbank, Brücke und Skripten, deren Name im gesamten getrackten Repo-Text nur an der Definition vorkommt. |
| Verwaiste Skripte | 0 | Dateien direkt unter scripts/, deren Dateiname (bei Python-Modulen auch der Modulname) in keiner anderen getrackten Textdatei vorkommt. |
| Stille Branches | 9 | Lokale und Remote-Refs außer Haupt- und Fokus-Branch. still: Commits, die nicht im Fokus-Branch sind, und seit mindestens 14 Tagen kein neuer Commit (gemessen am Commit-Datum der Fokus-Spitze); offen: dasselbe, aber jünger; gemergt: Ref liegt vollständig im Fokus-Branch. |
| Gemergte Refs | 26 | Lokale und Remote-Refs außer Haupt- und Fokus-Branch. still: Commits, die nicht im Fokus-Branch sind, und seit mindestens 14 Tagen kein neuer Commit (gemessen am Commit-Datum der Fokus-Spitze); offen: dasselbe, aber jünger; gemergt: Ref liegt vollständig im Fokus-Branch. |
| Riesen (> 800 Zeilen) | 15 | Quelldateien (py, js, mjs, ts, css) in Kern, Werkbank, Brücke und Skripten mit mehr als 800 Zeilen. |
| TODO-Marker | 5 | Vorkommen der Marker TODO, FIXME und XXX in den Quelldateien dieser vier Bereiche. |

## Maschine {#maschine}

Die Kette hat 7 Stufen mit zusammen 4.311 Zeilen; die Stufen stammen aus `kette.json`. 3 Workflows und 6 Systemd-Units halten den Betrieb auf dem Pi.

<div class="wiki-chart" data-chart="bar" data-title="Stufen der Kette" data-unit="Zeilen" markdown="1">

| Stufe | Zeilen | übergibt | höchste Komplexität |
| --- | --- | --- | --- |
| Bildquelle | 1.045 | Frame | 19 |
| Anzeige finden | 452 | DisplayCandidate | 19 |
| Nachführen | 129 | TrackResult | 5 |
| Entzerren | 103 | DisplayCrop | 4 |
| Wert lesen | 1.559 | ReadResult | 26 |
| Freigabe | 268 | GateDecision | 22 |
| Ausgabe | 755 | TxReceipt | 11 |

</div>

| Name | Auslöser | Datei | Schritte |
| --- | --- | --- | --- |
| Zensical-Doku pflegen | Zeitplan (0 6 * * *, Europe/Berlin), manuell | `docs-maintenance.yml` | 8 |
| Doku-Seite | Push auf master, manuell | `docs.yml` | 8 |
| Playwright Tests | Push auf main,master, Pull Request auf main,master, manuell | `playwright.yml` | 6 |

| Unit | Aufgabe |
| --- | --- |
| `forgejo-codex-runner.service` | Forgejo Runner (picam-codex-docs) |
| `forgejo-runner.service` | Forgejo Runner (picam-docs) |
| `picam-codex-auth-sync.path` | Codex-Anmeldungen des Doku-Runners beobachten |
| `picam-codex-auth-sync.service` | Codex-Anmeldung fuer den Doku-Runner abgleichen |
| `picam-wiki-export.path` | Feste Exportanfrage des Wiki-Deployments beobachten |
| `picam-wiki-export.service` | Abgeschlossene Messpfad-Sessions für das Wiki vorbereiten |
<!-- CODEBASE-FACTS:END -->

## Wie die Zahlen entstehen {#methode}

* **Zeilen** sind Textzeilen je Datei, ohne Daten- und Fremdbibliotheken
  (`data`, `vendor`).
* **Komplexität** ist die zyklomatische Komplexität nach McCabe: eins plus
  die Zahl der Verzweigungen einer Funktion, statisch aus dem Python-Syntaxbaum
  gezählt. Ab 10 gilt eine Funktion als schwer zu überblicken, ab 40 als
  kaum noch vollständig zu testen.
* **Befunde** unter „Zustand“ nennen ihre Suchmethode in der Tabelle. Sie
  sind Hinweise zum Aufräumen, keine geprüften Fehler.
* **Branches** stammen aus den lokalen und den Remote-Refs zum Zeitpunkt der
  Erzeugung; „still“ heißt: Commits, die nicht im Fokus-Branch angekommen
  sind, und seit mindestens 14 Tagen keine neuen.
