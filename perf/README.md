# Performance-Metriken

`scripts/perf-report.py` misst die Lesekette und vergleicht gegen `perf/baseline.json`.
Aufruf (immer `./.venv/bin/python`):

```bash
./.venv/bin/python scripts/perf-report.py                              # messen, perf/results/<commit>.json
./.venv/bin/python scripts/perf-report.py --compare perf/baseline.json # Gate
./.venv/bin/python scripts/perf-report.py --update-baseline            # Baseline neu schreiben
./.venv/bin/python scripts/perf-report.py --summary-file "$GITHUB_STEP_SUMMARY" --compare perf/baseline.json
```

Exit-Codes: 0 gut, 1 Regression, 2 Aufruf-/Umgebungsfehler (auch: Baseline von anderem Runner),
3 Lauf ungueltig (keine Regressionsaussage).

## Messquelle

Standard `synthetic`: gerenderte Dot-Matrix-Bilder und synthetisch angelernter Leser
(`tests/dotmatrix_helpers.py`, fester Seed), Pipeline mit `ManualRoiLocator` und `ReleaseGate`.
Das laeuft ohne Hardware und ohne Daten ausserhalb des Repos, ist also auf jedem Pi-5-Runner
reproduzierbar. `--source dev --still ... --proposal ...` misst Latenz/Durchsatz auf einem
echten gespeicherten Bild (nur lokal, `DISPREAD_DEV_DATA` wird beachtet) und hat keine
Qualitaetsmetrik, weil Wahrheitswerte fehlen. Jede Wiederholung ist ein frischer Prozess;
berichtet wird der Median je Metrik ueber die gueltigen Wiederholungen (Standard 3), die
Streuung steht als min/max in `spread`.

## Metriken

Verteilungen sind nie ein Einzelwert (docs/TIMING.md). Perzentile nach Nearest-Rank
(immer ein gemessener Wert).

| Schluessel | Bedeutung |
|---|---|
| `latency.<stufe>.p50/p95/p99/max_ms` | Stufen `locate, rectify, read, gate, build` aus dem `PipelineTrace` jedes `ValueRecord` (`stage_durations_us`), `total` = `t_dequeue` bis `t_record_built`. Reine Rechenzeit der Software, **nicht** Kamera-/Displaylatenz. |
| `throughput.max_fps` | Bilder/s der Lesekette (Entzerren + Leser) ohne Pacing (`--target-fps 0`, `measure_run`). |
| `throughput.fps30.achieved_fps`, `.dropped_percent` | gelesene Bilder/s bei 30 Bildern/s Angebot und Anteil nicht gelesener (verworfener) Bilder; die Live-Sitzung liest immer das neueste Bild. |
| `quality.recognition_percent` | Anteil richtig freigegebener Werte auf denselben Bildern; daneben `wrong_percent` (falsch freigegeben, schwerer wiegend) und `rejected_percent`. Geschwindigkeit ohne Genauigkeit sagt nichts. |
| `startup.first_valid_ms` | Pipeline bauen bis erster `VALID`-Record, Leser bereits geladen (Kaltstart des Prozesses). |
| `ops.cpu_percent_own` | CPU des Messprozesses in Prozent eines Kerns (100 = ein Kern). |
| `ops.cpu_percent_foreign` | System-CPU minus eigene CPU, aus `/proc/stat`: Konkurrenz durch andere Prozesse. |
| `ops.soc_c_max`, Drosselbits | SoC-Temperatur und `vcgencmd get_throttled`; fehlt ein Sensor, steht im Bericht "nicht verfuegbar". |
| `ops.rss_start_mb/_end_mb/_growth_mb` | Resident-Speicher vor und nach der Messung (nur Information, kein Gate). |

## Gate und Toleranzen

| Metrik | Grenze | Begruendung |
|---|---|---|
| p95 je Stufe und gesamt | Baseline +15 % und mindestens +0,05 ms | p95 statt Max: robust gegen Einzelausreisser. Der Boden verhindert Fehlalarme bei Stufen im Mikrosekundenbereich (gate, build). |
| `max_fps`, `fps30.achieved_fps` | Baseline -15 % | |
| `fps30.dropped_percent` | Baseline +1 Punkt | |
| `recognition_percent` | Baseline -0,5 Punkte | Quelle ist deterministisch, jede Abnahme ist echt. |

Die Defaults wurden an der gemessenen Streuung zwischen Laeufen auf dem Pi 5 geprueft (siehe
Abschnitt Streuung unten). Anpassbar mit `--tol-latency-pct`, `--tol-throughput-pct`,
`--tol-recognition-points`. Bei einer Regression nennt die Ausgabe die Stufe mit dem groessten
Zuwachs als wahrscheinliche Ursache.

## Streuung (gemessen, Pi 5 im Leerlauf)

Innerhalb einer Baseline (3 Wiederholungen) liegt der p95 je Stufe bei hoechstens 5 % Spanne
(read 5,48 bis 5,73 ms), Durchsatz 132,1 bis 134,7 Bilder/s. Zwischen drei aufeinanderfolgenden
Median-Laeufen wich der p95 der Stufe read um +9,8 %, +5,7 % ab (nie ueber +10 %), der Durchsatz um
hoechstens 2 %. 15 % bleibt deshalb als Grenze: knapp ueber der beobachteten Streuung, aber
klein genug, dass ein kuenstlicher `sleep(3 ms)` in `read` (+58 % p95, -28 % Durchsatz) klar bricht.
Unter Last durch andere Prozesse streuen die Werte um ein Vielfaches (max_fps 32 statt 134):
solche Laeufe sind ueber die Fremdlast-Pruefung ungueltig, nicht vergleichbar.

## Ungueltige Laeufe (Exit 3)

Ein Lauf zaehlt nicht, wenn ein aktives Drosselbit (Bit 0-3 von `get_throttled`) gesetzt ist, der
SoC >= 75 Grad erreicht oder fremde CPU-Last > 40 % eines Kerns herrscht. Die "seit Boot"-Bits
(16-19) bleiben bis zum Neustart gesetzt und gelten nur als Hinweis. Ungueltige Wiederholungen
fliessen nicht in den Median ein; sind alle ungueltig, gibt es Exit 3 statt einer Regression.
Auf einem Runner, der parallel Tests laufen laesst, ist das der Normalfall: Perf-Lauf allein auf
dem Geraet starten.

## Baseline aktualisieren

1. Pi 5 im Leerlauf, keine parallelen Tests oder Agenten.
2. `./.venv/bin/python scripts/perf-report.py --update-baseline` (schreibt nur bei lauter gueltigen Wiederholungen).
3. Zweiten Lauf mit `--compare perf/baseline.json` pruefen, Diff der `baseline.json` (Host-Kennung:
   Modell, Kerne, Python, OpenCV) in den Commit, mit Grund (bewusste Aenderung an Leser/Pipeline).

## Grenzen

* Nur Pi-5-Runner sind untereinander vergleichbar; bei anderem Modell, Kernzahl oder Quelle
  verweigert `--compare` mit Exit 2. Anderer Runner = eigene Baseline.
* Drosselbits: `vcgencmd get_throttled` braucht `/dev/vcio` (root); fuer den normalen Nutzer
  ist es "nicht verfuegbar" und Drosselung dann nur ueber SoC-Temperatur und Fremdlast erkennbar.
  Der CPU-Takt wird nur als Information berichtet (DVFS-Stufen machen ihn als Kriterium unzuverlaessig).
* Nicht gemessen (offen): echte Kamera-Latenz und Aufnahme-bis-Wert (M2/M5), Startzeit mit
  Vorlagenladen und Kamera, Erkennungsrate auf realen Geraeten/Licht, Speicherwachstum ueber
  Stunden. Das braucht Hardware oder Daten, die nicht im Repo liegen.
* Die Ergebnisse unter `perf/results/` sind nicht versioniert (`.gitignore`).
