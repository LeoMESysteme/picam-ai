# AGENTS.md — verbindliche Daueranweisungen

## Python immer über die Projekt-.venv

```bash
./.venv/bin/python   ./.venv/bin/pytest   ./.venv/bin/ruff
```

Die venv **muss** mit `--system-site-packages` erzeugt werden, das Paket mit
`--no-deps` installiert werden. Grund: `picamera2`, `libcamera`, `cv2`, `numpy`
und `pyserial` sind Debian-Systempakete. PyPI-Kopien im venv überschatten sie
und brechen die ABI. Siehe [docs/dependencies.md](docs/dependencies.md).

## MEhubs /opt-Hotfix-Regel gilt hier NICHT

Das Schwesterprojekt MEhub liegt unter `/opt/mehub/current` und hat deshalb die
Regel „nicht direkt dorthin schreiben, erst nach `$HOME` hochladen, dann mit
`sudo install` deployen". **Dieses Repo liegt im Home** und wird direkt
bearbeitet. Die Regel nicht übernehmen.

## Dokumentationspflicht

| Auslöser | Pflicht-Update | Wann |
| --- | --- | --- |
| Änderung unter `src/`, `examples/`, `scripts/`, `systemd/`, `udev/` | `CHANGELOG.md`, oberster Abschnitt | **im selben Commit** |
| Strukturelle Entscheidung mit verworfenen Alternativen | `docs/project_history.md` | im selben Commit |
| Neue Unbekannte erkannt | neuer `OQ-nn` in `docs/open-questions.md` | sofort, auch ohne Code-Änderung |
| Unbekannte geklärt | OQ-Eintrag auf `geklärt` + Datum + Antwort + Verweis. **Nicht löschen.** Zielort füllen | im selben Commit |
| Messung gelaufen | `docs/VALIDATION.md` (Zahlen) **und** `docs/lab_journal.md` (Aufbau, Deutung) | am selben Tag |
| Hardware angefasst | `docs/lab_journal.md`; bei Konfigwirkung `docs/HARDWARE_PROFILE.md`; Diagnose-Schnappschuss ablegen | direkt danach |
| Neue Abhängigkeit | `docs/dependencies.md` + `pyproject.toml`/`install.sh` | im selben Commit |
| **Sessionende, jede Session** | `docs/status.md` neu schreiben (überschreiben, nicht anhängen) | vor dem letzten Commit |

Zwei harte Sätze:

* **Kein Commit an `src/` ohne CHANGELOG-Eintrag.**
* **Vor Sessionende `docs/status.md` aktualisieren.**

## Nicht verhandelbar (Konzept.md §7)

* Ein veralteter Wert läuft **nie** unmarkiert als aktueller gültiger Wert
  weiter. Erzwungen im `ValueRecord`-Konstruktor und in der Freigabe.
* Die Erkennung benutzt den Referenzwert **nicht**, um den DUT-Wert zu
  korrigieren. `ValueReader.read` und `ReleaseGate.evaluate` bekommen ihn
  strukturell nicht als Parameter — das ist getestet, nicht nur beabsichtigt.
* Echte Messwertsprünge werden **nicht** geglättet. Keine Mittelung, keine
  Begrenzung.
* Modell-Konfidenz ist **keine** Fehlerwahrscheinlichkeit.
  `declares_confidence_calibrated` bleibt `False`, solange keine
  Kalibriermessung in `docs/VALIDATION.md` steht.
* Unlesbare oder unbekannte Eingaben werden **abgelehnt**, nicht geraten.

## Kein Erfinden von Protokollen

Das GSVmulti-Telegramm ist unbekannt ([OQ-07](docs/open-questions.md)). Jede
Formatänderung geht über `TelegramFormatter`, niemals hart in die Pipeline. Der
`AsciiCsvFormatter` ist als `provisional=True` gekennzeichnet, und dieses Flag
gehört in jedes Runartefakt. `gsv_ascii.py` wirft absichtlich.

## Zeitangaben immer mit Zeitbasis

Ein Zeitstempel ohne `TimeBaseKind` ist keine verwertbare Angabe. Aus
`SYNTHETIC` und `FILE_MTIME` darf **keine** Latenz- oder Zeitaussage abgeleitet
werden — `Frame.is_time_bearing` und
`TimeBaseKind.carries_time_information` sagen, ob es zulässig ist. Eine
unbekannte Unsicherheit ist `None`, nicht `0`.

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->
