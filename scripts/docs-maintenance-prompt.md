# Unbeaufsichtigte Pflege der Zensical-Dokumentation

Du arbeitest in einem frischen Checkout von `master`. Der aufrufende Gate-Prozess
prüft jede Änderung, führt Build und Browsertests aus, committet und pusht erst
danach. **Nutze selbst weder `git commit` noch `git push`.** Frage niemanden;
wenn eine Aussage nicht belegbar ist, lass sie unverändert und melde die Lücke.

## Ziel

Halte die Zensical-Seite für neue Entwickler verständlich, knapp und aktuell.
Nutze die vollständige Dateiliste im JSON unten als Einstieg. Wenn `diff_base`
gesetzt ist, prüfe die Änderungen mit `git diff diff_base..base -- <pfad>`;
ohne `diff_base` ist die Liste ein vollständiges Datei-Inventar für den
Erstaudit oder einen nicht mehr erreichbaren früheren Stand. Berücksichtige
**alle** genannten Pfade, bündele zusammengehörige Änderungen und lies nur
die betroffenen Code- und Dokumentationsstellen. Die genannten `guide_pages`
werden auch ohne Codeänderung geprüft: anfangs in Dreierpaketen, danach
wöchentlich eine Seite. Beim ersten Paket: prüfe zusätzlich die Navigation
und finde die wichtigsten fehlenden Kontextverweise der Anleitung.
Bevorzuge eine gezielte Änderung an höchstens fünf Seiten pro Lauf.

1. Prüfe Fakten gegen `src/`, `examples/`, `scripts/`, `tests/` und die
   verbindlichen Projektdokumente. Schreibe Erklärtexte der Anleitung bei
   Bedarf für Einsteiger neu. Halte Beispiele ausführbar und benenne Grenzen.
2. Ergänze sinnvolle Querverweise nur dort, wo sie einen Begriff oder Schritt
   im **jeweiligen Kontext** erklären. Verlinke die erste hilfreiche Nennung
   pro Abschnitt statt jedes Vorkommens. Schaffe kurze Zielabschnitte mit
   stabilen Ankern. Erweitere `zensical.toml` um ein Vorschauziel nur, wenn
   dessen Einleitung oder Abschnitt als kurzer Popup-Text taugt. Für einzelne
   API-Symbole nutze knappe Linktitel oder Code-Anmerkungen; generierte
   API-Klassen sind keine Vorschauziele. Neue Übersichtsseiten nur bei einer
   belegten Navigationslücke anlegen und in der Navigation aufnehmen.
3. Roadmap-Status nur mit eindeutigen Belegen aus dem aktuellen Stand
   korrigieren. `docs/status.md` bei jeder tatsächlichen Änderung als
   aktuellen, belegten Snapshot neu schreiben, ohne Produktfakten zu raten.
4. Wenn eine **neue echte Projekt-Unbekannte** sichtbar wird, füge ein neues
   OQ in `docs/open-questions.md` hinzu. Bestehende OQ-Einträge nie ändern
   oder löschen. Der Gate-Prozess erzeugt die Übersicht danach neu.

## Grenzen

Nur `README.md`, `zensical.toml`, `docs/anleitung/*.md`,
`docs/uebersicht/*.md`, `docs/ROADMAP.md`, `docs/status.md` und für neue
Unbekannte `docs/open-questions.md` bearbeiten. Messdaten, Laborjournal,
Timing-Aussagen, Hardwareprofil, Protokolldaten und Projektgeschichte sind
Quellen zum Verlinken, keine automatisch umzuschreibenden Texte. Halte
`AGENTS.md` und `Konzept.md` ein: keine erfundenen GSVmulti-Telegramme,
keine unmarkierten veralteten Werte, keine aus synthetischer Zeit
abgeleiteten Latenzen, keine Konfidenz als Fehlerwahrscheinlichkeit.

Der Lauf ist absichtlich klein. Arbeite allein, wenn die Änderung überschaubar
ist. Nur bei mindestens vier voneinander unabhängigen betroffenen Bereichen
oder einem größeren Erst-Audit darfst du **höchstens zwei** Instanzen des
lesenden `docs_reader`-Subagents auf getrennte Bereiche ansetzen. Er nutzt
`gpt-6-luna` mit niedrigem Denkaufwand und liefert knappe Belege. Du selbst
integrierst und schreibst allein.
Kein paralleles Schreiben, kein Web-Suchen für lokale Projektfakten.

Am Ende: eine kurze deutsche Zusammenfassung mit den wichtigsten Belegen,
oder „Keine Änderung nötig“. Keine Rückfrage und kein Vorschlag für einen
separaten PR.
