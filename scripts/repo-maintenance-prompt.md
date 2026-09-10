# Automatisierte Doku-Pflege (geplante Routine, unbeaufsichtigt)

Du läufst unbeaufsichtigt per Cron, kurz nach dem morgendlichen Boot des
Raspberry Pi, bevor jemand mit der Arbeit beginnt. **Niemand liest oder
beantwortet Rückfragen** — `AskUserQuestion`, `ExitPlanMode` oder ein
Zwischenstopp zur Bestätigung funktionieren hier nicht. Wenn ein geladener
Skill (z. B. `brainstorming`, `writing-plans`, `executing-plans`,
`subagent-driven-development`, `using-git-worktrees`,
`requesting-code-review`/`receiving-code-review`) normalerweise eine
Rückfrage stellen oder auf Bestätigung warten würde: überspringe genau
diesen interaktiven Schritt, triff die konservativste vertretbare
Entscheidung selbst, und vermerke das übersprungene Vorgehen kurz in deiner
Abschlusszusammenfassung. Bash, Subagenten (`Agent`) und Web-Zugriff
(`WebFetch`/`WebSearch`) stehen technisch nicht zur Verfügung — versuch es
gar nicht erst, das ist beabsichtigt.

Nützlich könnten sein: `claude-md-management` (Methodik zur
Strukturprüfung von Markdown-Doku, auch wenn `CLAUDE.md` selbst tabu ist —
sieh unten) und `superpowers:verification-before-completion` (eigene
Änderungen vor Abschluss nochmal gegenlesen, bevor du sie als erledigt
zusammenfasst). Setz sie ein, wenn sie den Auftrag unten unterstützen —
erfinde aber keinen zusätzlichen Umfang daraus.

## Auftrag

Halte die Projektdokumentation unter `docs/` sowie `CHANGELOG.md` aktuell,
aufgeräumt und knapp:

1. **Veraltetes/Falsches korrigieren** — nur wenn du die Abweichung im
   aktuellen Code (`src/`, `tests/`, `examples/`) mit `Read`/`Grep`/`Glob`
   nachweisen kannst. Ohne Beleg: nichts ändern, stattdessen als neue OQ in
   `docs/open-questions.md` vermerken (Format siehe bestehende Einträge).
2. **Redundanz und Länge reduzieren** — besonders in `docs/lab_journal.md`,
   `docs/project_history.md`, `docs/VALIDATION.md`,
   `docs/open-questions.md`: sich wiederholende oder ausufernde Abschnitte
   knapper zusammenfassen, ohne technischen Gehalt (Zahlen, Messwerte,
   Datumsangaben, Ursache-Wirkungs-Ketten) zu verlieren.
3. **Querverweise und Formatierung reparieren** — kaputte Markdown-Links,
   falsche Dateipfade, inkonsistente Kopfzeilen.

## Harte Grenzen (nicht verhandelbar)

- **Nur Dokumentation anfassen.** Erlaubt: Dateien unter `docs/` sowie
  `CHANGELOG.md`. Verboten, unter keinen Umständen: `src/`, `tests/`,
  `examples/`, `scripts/`, `systemd/`, `udev/`, `Konzept.md`, `AGENTS.md`,
  `CLAUDE.md`, alles unter `.claude/`, `pyproject.toml`. Diese nie
  bearbeiten, auch nicht bei vermeintlichen Fehlern — stattdessen als OQ
  vermerken.
- `docs/anleitung/` nur bei offensichtlichen Tippfehlern oder toten Links
  anfassen, keine inhaltliche Umstrukturierung — die Kapitel sind an
  laufende P0-Arbeit gekoppelt.
- **`docs/open-questions.md`: OQ-Einträge werden nie gelöscht.** Ein
  geklärter Punkt wird auf „geklärt" + Datum + Antwort + Verweis gesetzt,
  niemals entfernt (siehe `AGENTS.md`-Tabelle). Im Zweifel: Eintrag stehen
  lassen.
- **`docs/status.md`** nicht inhaltlich umschreiben (das ist Aufgabe der
  jeweiligen Arbeits-Session, die den aktuellen Stand kennt) — nur
  offensichtliche Formatierungsfehler oder tote Links fixen.
- `docs/PLAN_*.md` sind aktive Arbeitspläne — nur Tippfehler/Formatierung,
  keine inhaltliche Kürzung oder Umstrukturierung.
- Nichts löschen, wenn unsicher, ob es noch gebraucht wird — lieber
  kürzen/zusammenfassen als entfernen.
- Committe nicht selbst und nutze kein `git` — das übernimmt der
  aufrufende Wrapper anhand deiner Dateiänderungen und der von dir
  gelieferten Commit-Message (siehe unten).

## Vorgehen

1. Lies `docs/status.md` und `docs/open-questions.md` zuerst (Einstiegs-
   reihenfolge aus `CLAUDE.md`).
2. Geh die übrigen `docs/*.md` durch, identifiziere konkrete, belegbare
   Probleme (siehe oben).
3. Nimm nur Änderungen vor, die du klar begründen kannst. Bei Unsicherheit:
   nichts tun.
4. Gib zum Schluss eine kurze Zusammenfassung der vorgenommenen Änderungen
   aus (fürs Log dieser Routine) — falls ein interaktiver Skill-Schritt
   übersprungen wurde, erwähne das hier ebenfalls kurz.

## Commit-Message

Falls du mindestens eine Datei geändert hast, schreib **ganz am Ende**
deiner Antwort zusätzlich einen Commit-Message-Block in exakt diesem
Format (Marker wortwörtlich, sonst kann der Wrapper ihn nicht parsen):

```
===COMMIT-MESSAGE-START===
<eine knappe, konkrete Subject-Zeile auf Deutsch, die tatsächlich benennt
was sich inhaltlich geändert hat (nicht "Doku aktualisiert"), endend mit
"(automatisierte Doku-Pflege)">

<optional: 1-3 knappe Zeilen mit weiteren Einzelheiten, nur falls die
Subject-Zeile allein die Änderungen nicht abdeckt>
===COMMIT-MESSAGE-END===
```

Schreib diesen Block nur, wenn tatsächlich Dateien geändert wurden — hast
du nichts geändert, lass ihn ganz weg. Der Wrapper hängt automatisch die
`Co-Authored-By`-Zeile an, die musst du nicht selbst ergänzen.
