# Anleitung — selbst programmieren

Diese Anleitung ist für **dich als Programmierer**, nicht für Claude. Sie
beschreibt, was als Nächstes gebaut wird, warum in dieser Reihenfolge, welchen
Vertrag jedes neue Modul erfüllen muss und woran du merkst, dass es fertig ist.
Der fertige Code steht absichtlich **nicht** darin — statt Lösungen gibt es
Gerüst, Test und Fallenliste.

Fachlich autoritativ bleibt [../../Konzept.md](../../Konzept.md). Die
Daueranweisungen in [../../AGENTS.md](../../AGENTS.md) gelten für jede Zeile,
die du schreibst.

**Direkt ausprobieren:** [Kamera-Livevorschau über SSH](10-kamera-livevorschau.md)
zeigt das echte Kamerabild mit unbestätigten Display-Kandidaten im
Windows-Browser. Dieser kleine Prototyp läuft unabhängig vom Lernpfad.

## So ist jedes Kapitel aufgebaut

| Abschnitt | Bedeutung |
| --- | --- |
| **Ziel** | Was danach läuft, in einem Satz |
| **Warum jetzt** | Was es freischaltet, welche ROADMAP-Zeile es abhakt |
| **Vorbedingungen** | Kapitel, Pakete, Hardware |
| **Der Vertrag** | Welches `Protocol` bzw. welche Datenklasse zu erfüllen ist |
| **Schritt für Schritt** | Kleine Schritte, jeder einzeln prüfbar |
| **Fallen** | Was in *diesem* Projekt konkret schiefgeht |
| **Fertig, wenn** | Checkliste, inklusive Doku-Pflicht |

## Lernpfad

Reihenfolge ist Absicht: jedes Kapitel benutzt, was das vorige gebaut hat, und
die ersten fünf brauchen **keine Hardware**.

| # | Kapitel | Danach kannst du | Hardware | Aufwand | ROADMAP |
| --- | --- | --- | --- | --- | --- |
| 0 | [Werkzeuge und Arbeitsrhythmus](00-werkzeuge.md) | venv, Tests, `ruff`, Commit-Regeln, Fehler lesen | – | 1 h | – |
| 1 | [Die Kette verstehen](01-kette-verstehen.md) | einen Frame von Hand durch alle sechs Stufen schieben | – | 2 h | – |
| 2 | [Die Verträge](02-vertraege.md) | *Nachschlagewerk:* alle Trennstellen und Datenklassen auf einer Seite | – | – | – |
| 3 | [Erste eigene Bildquelle: `folder://`](03-erste-bildquelle-folder.md) | ein `FrameSource`-Modul selbst schreiben und testen | – | 3–4 h | P0 |
| 4 | [Geräteprofile](04-geraeteprofile.md) | ROI, Layout, Einheit aus JSON laden statt hart im Beispiel | – | 4–6 h | P0 |
| 5 | [Die CLI](05-cli.md) | `dispread run --source … --profile …` statt Beispielskripte | – | 4–6 h | P0 |
| 6 | [Kamera, Aufnahme, `replay://`](06-kamera-aufnahme-replay.md) | echte Frames aufnehmen und reproduzierbar abspielen | Kamera | 1–2 Tage | P1/P2 |
| 7 | [Lokalisierung ohne Bediener](07-lokalisierung.md) | Anzeige im Bild finden und verfolgen | Kamera (Test: nein) | 1–2 Tage | P0/P3 |
| 8 | [Weitere OCR-Backends](08-ocr-backends.md) | zweites Backend gegen das Segmentverfahren messen | – (Daten: ja) | 2–3 Tage | P3 |
| 9 | [Betrieb: Installation, Dienst, Dauerlauf](09-betrieb.md) | Dienst starten, 72 h laufen lassen, Doku-Test | Kamera + UART | 2–3 Tage | P6 |

**Nachschlagen statt lesen:**
[Rezepte](rezepte.md) — Codeschnipsel zum Kopieren ·
[Glossar](glossar.md) — jeder Fachbegriff des Projekts in zwei Sätzen.

## Wenn du nur eine Stunde hast

1. [Kapitel 0](00-werkzeuge.md), Abschnitt „Die vier Befehle".
2. `./.venv/bin/python examples/16_end_to_end_headless.py` starten und die
   Ausgabe mit [Kapitel 1](01-kette-verstehen.md) nebeneinander lesen.
3. Rezept 4 aus den [Rezepten](rezepte.md): einen Frame zu Fuß durch die Kette.

## Fünf Regeln, die in jedem Kapitel gelten

Vollständig in [../../AGENTS.md](../../AGENTS.md), hier nur als Merkzettel:

1. **Ein veralteter Wert läuft nie unmarkiert weiter.** Kein Modul darf den
   letzten guten Wert „vorsichtshalber" wiederholen.
2. **Der Referenzwert der Kalibriermaschine erreicht die Erkennung nicht.**
   Wenn eine Signatur ihn bräuchte, ist die Signatur falsch.
3. **Unlesbares wird abgelehnt, nicht geraten.** Eine Falschablehnung ist
   erlaubt, eine stille Fehlablesung nicht.
4. **Konfidenz ist keine Fehlerwahrscheinlichkeit.**
   `declares_confidence_calibrated` bleibt `False`, bis eine Kalibriermessung
   in [../VALIDATION.md](../VALIDATION.md) steht.
5. **Kein Protokoll erfinden.** Das GSVmulti-Telegramm ist unbekannt
   ([OQ-07](../open-questions.md)); alles Neue geht über einen
   `TelegramFormatter` mit `provisional=True`.

Dazu die Zeitregel: **jeder Zeitstempel trägt seine Zeitbasis.** Aus
`SYNTHETIC` und `FILE_MTIME` darf keine Latenzaussage werden.

## Was du dabei nicht brauchst

Kein Cloud-Dienst, kein Sprachmodell, kein Trainingscluster. Der laufende
Messpfad ist eine klassische CV-/OCR-Kette mit Regelprüfung — bewusst so,
siehe [../../CLAUDE.md](../../CLAUDE.md), Abschnitt „Was dieses Projekt ist".
Alles in den Kapiteln 0–5 läuft auf dem Pi ohne angeschlossene Kamera.

## Fortschritt festhalten

Nach jedem Kapitel, das Code erzeugt hat (Pflicht laut
[../../AGENTS.md](../../AGENTS.md)):

* `CHANGELOG.md` — obenauf: Problem, Änderung, Konsequenz. **Kein Commit an
  `src/` ohne diesen Eintrag.**
* `docs/ROADMAP.md` — die zugehörige `- [ ]`-Zeile unter P0 abhaken.
* `docs/status.md` — vor Sessionende neu schreiben, nicht anhängen.
* Neue Unbekannte entdeckt? Sofort ein `OQ-nn` in
  [../open-questions.md](../open-questions.md), auch ohne Codeänderung.
