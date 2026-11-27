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

`scripts/codebase-facts.py` erzeugt die Zahlen aus den versionierten
Dateien am unten genannten Commit. Der Git-Verlauf umfasst die beim
Abgleich vorhandenen lokalen Branches und Remote-Tracking-Refs. Die
interaktive Bühne und die Tabellen verwenden denselben Stand.

<div id="codebase-stage" class="wiki-codebase-stage"></div>

<!-- CODEBASE-FACTS:BEGIN -->
Stand: Commit `197959a` auf `master`, erzeugt am 26.11.2026.

## Wachstum {#wachstum}

Der Bestand wuchs von 2.322 Zeilen am 07.09.2026 auf 271.190 Zeilen in 1.048 Dateien; davon sind 84.163 Code (Kern, Werkbank, Brücke, Skripte), 81.504 Tests und 104.494 Doku. Daten- und Fremddateien zählen nicht mit.

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
| KW 46 (ab 09.11.) | 216.891 |
| KW 47 (ab 16.11.) | 251.063 |
| KW 48 (ab 23.11.) | 271.190 |

</div>

## Branches {#branches}

Neben dem Fokus `master` gibt es 10 Refs: 10 still, 0 offen und 0 gemergt. Insgesamt enthält die Historie 760 Commits und 53 Merges.

| Branch | Zustand | Commits (nicht im Fokus) | letzter Commit |
| --- | --- | --- | --- |
| `test/clahe-ocr-accuracy` | still | 4 | 10.09.2026 |
| `codex/automatic-seven-segment` | still | 1 | 18.09.2026 |
| `docs/oq22-rp2040-wedge` | still | 3 | 24.09.2026 |
| `docs/zensical-prototyp` | still | 1 | 24.09.2026 |
| `codex/MEM-6-c2-scripts-pi-housekeeping-py-bericht-und-freigegebenes-aufr-umen` | still | 1 | 14.10.2026 |
| `exp/r13-fenster-tracker` | still | 1 | 22.10.2026 |
| `feat/messpfad-live` | still | 1 | 22.10.2026 |
| `fix/session-explorer-test-wackelt` | still | 1 | 04.11.2026 |
| `docs/workbench-critical-2026-11-11` | still | 2 | 11.11.2026 |
| `feat/gsvmulti-bridge` | still | 1 | 11.11.2026 |

## Rhythmus {#rhythmus}

Freitag ist mit 263 von 760 Commits (35 %) der stärkste Tag, die Spitzenstunde liegt bei 14 Uhr (96 Commits). An 47 von 81 Tagen gab es Commits (Zeiten in Berlin).

<div class="wiki-chart" data-chart="bar" data-title="Commits je Wochentag" data-unit="Commits" markdown="1">

| Wochentag | Commits | Anteil |
| --- | --- | --- |
| Montag | 78 | 10 % |
| Dienstag | 69 | 9 % |
| Mittwoch | 220 | 29 % |
| Donnerstag | 98 | 13 % |
| Freitag | 263 | 35 % |
| Samstag | 26 | 3 % |
| Sonntag | 6 | 1 % |

</div>

## Struktur {#struktur}

Die 1.048 Dateien verteilen sich auf sieben Bereiche; am größten ist „Doku“ mit 104.494 Zeilen. Auf Tests kommen 0,97 Zeilen je Codezeile.

<div class="wiki-chart" data-chart="bar" data-title="Zeilen je Bereich" data-unit="Zeilen" markdown="1">

| Bereich | Zeilen | Dateien | größte Datei (Zeilen) |
| --- | --- | --- | --- |
| Kern | 29.575 | 108 | `src/dispread/calibration/record.py` (1.734) |
| Werkbank & Live | 24.595 | 81 | `src/dispread/live/frame_tracking.py` (1.720) |
| Windows-Brücke | 15.206 | 57 | `windows/bridge/src/dispread_bridge_app/app_controller.py` (1.511) |
| Skripte | 14.787 | 63 | `scripts/codebase-facts.py` (1.177) |
| Tests | 81.504 | 231 | `tests/test_live_service.py` (3.912) |
| Doku | 104.494 | 302 | `docs/VALIDATION.md` (7.066) |
| Infrastruktur | 1.029 | 24 | `zensical.toml` (184) |

</div>

## Komplexität {#komplexitaet}

Von 3.402 Python-Funktionen außerhalb der Tests haben 392 (11,5 %) eine Komplexität über 10 und 33 über 40. Die komplexeste ist `Controller.command` mit 91.

<div class="wiki-chart" data-chart="bar" data-title="Die zwölf komplexesten Funktionen" data-unit="Komplexität" markdown="1">

| Funktion | Komplexität | Ort | Zeilen |
| --- | --- | --- | --- |
| `Controller.command` | 91 | `src/dispread/workbench/controller.py:480` | 319 |
| `BridgeSession.exchange` | 84 | `src/dispread/gsv_bridge.py:139` | 191 |
| `chips` | 83 | `windows/bridge/src/dispread_bridge_app/ui/texts.py:676` | 160 |
| `collect` | 82 | `scripts/codebase-facts.py:547` | 183 |
| `_auto_fit` | 75 | `src/dispread/dotlattice.py:545` | 202 |
| `LiveSession.step` | 69 | `src/dispread/live/session.py:516` | 151 |
| `run` | 67 | `scripts/import-harvest.py:385` | 376 |
| `_calibrate` | 63 | `src/dispread/admin/calibrate.py:1043` | 241 |
| `validate` | 63 | `src/dispread/workbench/profiles.py:67` | 98 |
| `LiveService.start_run` | 62 | `src/dispread/live/service.py:1166` | 188 |
| `compare` | 61 | `scripts/r13-coarse-eval.py:106` | 82 |
| `setup_spec` | 61 | `windows/bridge/src/dispread_bridge_app/ui/texts.py:1283` | 98 |

</div>

## Zustand {#zustand}

Die Suche findet 4 ungenutzte Definitionen (33 Zeilen), 1 verwaiste Skripte, 10 stille Branches und 22 Quelldateien über 800 Zeilen. Das sind Hinweise zum Aufräumen, keine geprüften Fehler.

| Befund | Anzahl | Methode |
| --- | --- | --- |
| Ungenutzte Definitionen | 4 | Top-Level-Funktionen und -Klassen (per ast, ohne Decorator, ohne test_*, main und dunder) in Kern, Werkbank, Brücke und Skripten, deren Name im gesamten getrackten Repo-Text nur an der Definition vorkommt. |
| Verwaiste Skripte | 1 | Dateien direkt unter scripts/, deren Dateiname (bei Python-Modulen auch der Modulname) in keiner anderen getrackten Textdatei vorkommt. |
| Stille Branches | 10 | Lokale und Remote-Refs außer Haupt- und Fokus-Branch. still: Commits, die nicht im Fokus-Branch sind, und seit mindestens 14 Tagen kein neuer Commit (gemessen am Commit-Datum der Fokus-Spitze); offen: dasselbe, aber jünger; gemergt: Ref liegt vollständig im Fokus-Branch. |
| Gemergte Refs | 0 | Lokale und Remote-Refs außer Haupt- und Fokus-Branch. still: Commits, die nicht im Fokus-Branch sind, und seit mindestens 14 Tagen kein neuer Commit (gemessen am Commit-Datum der Fokus-Spitze); offen: dasselbe, aber jünger; gemergt: Ref liegt vollständig im Fokus-Branch. |
| Riesen (> 800 Zeilen) | 22 | Quelldateien (py, js, mjs, ts, css) in Kern, Werkbank, Brücke und Skripten mit mehr als 800 Zeilen. |
| TODO-Marker | 9 | Vorkommen der Marker TODO, FIXME und XXX in den Quelldateien dieser vier Bereiche. |

## Maschine {#maschine}

Die Kette hat 7 Stufen mit zusammen 4.314 Zeilen; die Stufen stammen aus `kette.json`. 3 Workflows und 8 Systemd-Units halten den Betrieb auf dem Pi.

<div class="wiki-chart" data-chart="bar" data-title="Stufen der Kette" data-unit="Zeilen" markdown="1">

| Stufe | Zeilen | übergibt | höchste Komplexität |
| --- | --- | --- | --- |
| Bildquelle | 1.045 | Frame | 19 |
| Anzeige finden | 452 | DisplayCandidate | 19 |
| Nachführen | 129 | TrackResult | 5 |
| Entzerren | 103 | DisplayCrop | 4 |
| Wert lesen | 1.559 | ReadResult | 26 |
| Freigabe | 268 | GateDecision | 22 |
| Ausgabe | 758 | TxReceipt | 11 |

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
| `picam-wlan-watchdog.service` | WLAN-Waechter: haengende NetworkManager-WLAN-Verbindung zurueckholen |
| `picam-wlan-watchdog.timer` | WLAN-Waechter jede Minute pruefen |
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
