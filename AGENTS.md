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
| Neue Unbekannte erkannt | neuer `OQ-nn` in `docs/open-questions.md`, danach `scripts/oq-index.py` | sofort, auch ohne Code-Änderung |
| Unbekannte geklärt | OQ-Eintrag auf `geklärt` + Datum + Antwort + Verweis. **Nicht löschen.** Zielort füllen, danach `scripts/oq-index.py` | im selben Commit |
| OQ-Titel/Status oder aktive Aufgaben/OQ-Verweise in `TODO.md` geändert | `./.venv/bin/python scripts/oq-index.py`; erzeugte Übersicht mitcommitten | im selben Commit |
| Messung gelaufen | `docs/VALIDATION.md` (Zahlen) **und** `docs/lab_journal.md` (Aufbau, Deutung) | am selben Tag |
| Hardware angefasst | `docs/lab_journal.md`; bei Konfigwirkung `docs/HARDWARE_PROFILE.md`; Diagnose-Schnappschuss ablegen | direkt danach |
| Neue Abhängigkeit | `docs/dependencies.md` + `pyproject.toml`/`install.sh` | im selben Commit |
| **Sessionende, jede Session** | `docs/status.md` neu schreiben (überschreiben, nicht anhängen) | vor dem letzten Commit |

Zwei harte Sätze:

* **Kein Commit an `src/` ohne CHANGELOG-Eintrag.**
* **Vor Sessionende `docs/status.md` aktualisieren.**

## Zensical-Übersichten pflegen

* Den erzeugten Block in `docs/open-questions.md` zwischen `OQ-INDEX:START`
  und `OQ-INDEX:END` sowie die `#oq-nn`-Anker nicht von Hand bearbeiten.
  „Jetzt“ folgt den unerledigten Aufgaben in `TODO.md`.
* Die interaktive Roadmap liest die erste Tabelle in `docs/ROADMAP.md`: P0–P8,
  sechs Spalten (`Phase`, `Ziel`, `Kamera?`, `GSVmulti-Spec?`,
  `Hartes Exit-Kriterium`, `Stand`) und die Statuswörter `erreicht`,
  `teilweise`, `blockiert`, `offen`. Bei einer Strukturänderung
  `docs-site/assets/docs-interactive.js` und `tests/docs-site.spec.ts`
  zusammen anpassen. Status und Exit-Kriterien bei neuen Belegen in der
  Roadmap selbst aktualisieren.
* Vorschau-Links auf Glossarbegriffe und Dokumentabschnitte brauchen stabile
  Überschriften-IDs und kurze Zielabschnitte. Links ohne Abschnittsanker auf
  Glossar und Timing zeigen die jeweilige Seiteneinleitung; diese knapp
  halten. Bei Umbenennungen die Links in `docs/anleitung/` und die
  Vorschau-Ziele in `zensical.toml` prüfen.
  API-Links mit kurzem Markdown-Linktitel erklären; generierte API-Seiten
  nicht pauschal als Vorschau-Ziele aufnehmen.
* Die [Projekt-Tour](docs/uebersicht/projekt-tour.md) zeigt den Messpfad als
  Animation. Ihre Texte stehen im Markdown, die Szenen unter derselben
  h3-ID in `docs-site/assets/tour.js` (Überblick, Erkennung) bzw.
  `tour-<kapitel>.js`. Ändert sich Verhalten,
  das eine Szene zeigt (Kette, Freigaberegeln, Zeitbasis, Ausgabe, OQ-07),
  Text **und** Szene im selben Commit anpassen und das Stand-Datum der Seite
  setzen. Geplantes bleibt auf der Bühne bernsteinfarben und gestrichelt.
  Werte aus dem Code (Felder, Vorgaben, Grenzen, Zeichensatz, Testnamen)
  liest die Tour aus `docs-site/assets/data/tour-facts.json`, erzeugt von
  `scripts/tour-facts.py`. Ändert sich einer, schlagen `docs-site.sh build`
  und `tests/test_tour_facts.py` fehl und nennen die betroffenen Schritte:
  diese prüfen, dann `./scripts/tour-facts.py --write`. Zeigt eine Szene einen
  neuen Wert aus dem Code, ihn dort als Fakt aufnehmen statt ihn
  einzutragen.
  Einzelne Szenen stehen als Abbildung auch in anderen Seiten
  (`<figure class="tour-figure" data-scene="<h3-ID>">`, z. B. in
  `docs/uebersicht/` und `docs-site/api/vertraege.md`). Bildunterschriften
  beschreiben nur, Zahlen zeigt die Bühne aus den Fakten. Eine Szenenänderung
  wirkt deshalb auch dort; `grep -rn 'data-scene="<ID>"' docs docs-site/api`
  zeigt, wo. Der Docs-Test lässt nur IDs zu, die es als Tour-Schritt gibt.
* Vor dem Merge von Doku-Änderungen `./scripts/docs-site.sh build -s` und
  `npx playwright test -c playwright.docs.config.ts` ausführen. Der Build
  bricht bei einem veralteten OQ-Index ab; die Browsertests prüfen Filter,
  Suche, Roadmap, Vorschauen und Fallback ohne JavaScript.

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

## Arbeitsweise für Codex

* Lies Projektunterlagen passend zur Aufgabe. Für offene Punkte zuerst nur die
  Übersicht am Anfang von `docs/open-questions.md`, danach betroffene OQs.
  `Konzept.md` bei Änderungen am Messpfad lesen; im `CHANGELOG.md` nur den
  benötigten Abschnitt öffnen.
* Suche mit `rg` und lies gezielte Dateiausschnitte. Nutze den Repowise-Index
  für Architektur, Änderungsrisiken und Entscheidungshistorie, wenn diese
  Informationen gebraucht werden; `get_answer` ist kein Standardweg.
* Die Filter für Suche, Diff und Dateilisten sind in `.repowise/config.yaml`
  abgeschaltet. `repowise distill` nur für laute Test-, Build- und Logausgaben
  nutzen. Ausgelassene Ausgabe mit `repowise expand <ref>` wiederherstellen.

<!-- REPOWISE_DISTILL:START — Do not edit below this line. Auto-generated by Repowise. -->
### Output Distillation

- Prefer `repowise distill <cmd>` for noisy commands — test runs, builds, `git status`/`log`/`diff`, searches, file listings. It runs the command unchanged (exit code preserved) and prints a compact, errors-first rendering; every error line survives.
- Output may contain a marker like `[repowise#a1b2c3d4e5f6: 230 lines omitted (~6.1k tokens); restore: repowise expand a1b2c3d4e5f6]`. The omitted content is fully preserved — run `repowise expand <ref>` to retrieve it, or `repowise expand <ref> -q <regex>` for just the matching lines.
- Never re-run a command to see omitted output; expand the marker instead.
- For structure-level questions about a large indexed file ("what's in here", "which function handles X"), `get_context(["path"], include=["skeleton"])` returns the file with bodies elided — every signature plus the bodies of the most central symbols — at a fraction of the cost of a full Read.
<!-- REPOWISE_DISTILL:END -->
