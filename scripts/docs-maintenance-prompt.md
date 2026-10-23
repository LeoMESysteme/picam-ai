# Unbeaufsichtigte Pflege der Zensical-Dokumentation

Du arbeitest in einem frischen Checkout von `master`. Der aufrufende Gate-Prozess
prüft jede Änderung, führt Build und Browsertests aus, committet und pusht erst
danach. **Nutze selbst weder `git commit` noch `git push`.** Frage niemanden;
wenn eine Aussage nicht belegbar ist, lass sie unverändert und melde die Lücke.

## Ziel

Halte die Zensical-Seite für ihre drei Lesergruppen verständlich, knapp und
aktuell: Einsteiger und Bediener (einrichten, bedienen, ohne Code-Flut),
fortgeschrittene Bediener (Einstellungen verstehen) und Entwickler
(Trennstellen, Schnittstellen, Codebeispiele). Lies vor jeder Änderung
`PRODUCT.md` im Projektwurzelverzeichnis; Leser, Leitlinien und Grenzen dort
sind verbindlich. Der geplante Wiki-Umbau steht in
`docs/superpowers/specs/2026-10-23-wiki-geruest-design.md`: Solange er nicht
umgesetzt ist, lege keine eigenen Wegweiser-, Schicht- oder Glossarstrukturen
an, die ihm vorgreifen. Bestehende Navigationseinträge (`nav` in
`zensical.toml`) und Seiten-URLs bleiben unverändert.
Nutze die vollständige Dateiliste im JSON unten als Einstieg. Wenn `diff_base`
gesetzt ist, prüfe die Änderungen mit `git diff diff_base..base -- <pfad>`;
ohne `diff_base` ist die Liste ein vollständiges Datei-Inventar für den
Erstaudit oder einen nicht mehr erreichbaren früheren Stand. Berücksichtige
**alle** genannten Pfade, bündele zusammengehörige Änderungen und lies nur
die betroffenen Code- und Dokumentationsstellen. Die genannten `guide_pages`
werden auch ohne Codeänderung geprüft: anfangs in Dreierpaketen, danach
wöchentlich eine Seite. Beim ersten Paket: prüfe zusätzlich die Navigation
und finde die wichtigsten fehlenden Kontextverweise der Anleitung.
Prüfe die `review_pages` bei **jedem** Lauf: Die Startseite muss die aktive
Kamera und den aktuellen Integrationsstand korrekt nennen und einen Weg zu
allen Navigationszielen bieten. Gleiche dazu `README.md` mit
`docs/status.md`, `docs/HARDWARE_PROFILE.md`, `docs/project_history.md` und
`zensical.toml` ab. Veraltete Aussagen auf der Startseite haben Vorrang vor
stilistischen Änderungen in den Anleitungsseiten. `docs/README.md` dient als
Inhaltskontrolle, darf aber vom automatischen Lauf nicht geändert werden.
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
   Markdown-Links innerhalb eines umzaeunten Codeblocks erscheinen nur als
   Text. Setze anklickbare Verweise deshalb im Fliesstext oder in einer
   Markdown-Tabelle ausserhalb des Codeblocks. Rate Abschnittsanker nicht aus
   Ueberschriften: Zensical normalisiert Satzzeichen und Code-Formatierung.
   Wenn du die tatsaechliche Ziel-ID nicht geprueft hast, verlinke die Seite
   ohne `#`-Anker.
3. Roadmap-Status nur mit eindeutigen Belegen aus dem aktuellen Stand
   korrigieren. `docs/status.md` bei jeder tatsächlichen Änderung als
   aktuellen, belegten Snapshot neu schreiben, ohne Produktfakten zu raten.
4. Wenn eine **neue echte Projekt-Unbekannte** sichtbar wird, füge ein neues
   OQ in `docs/open-questions.md` hinzu. Bestehende OQ-Einträge nie ändern
   oder löschen. Der Gate-Prozess erzeugt die Übersicht danach neu.

Nach allen Doku-Aenderungen einmal selbst `./scripts/docs-site.sh build -s` ausfuehren.
Repariere dabei gemeldete Links und Anker anhand der tatsaechlichen IDs in
`site/`, bevor du den Lauf beendest. Der Gate wiederholt den Build unabhaengig
und fuehrt danach die Browsertests (`tests/docs-site.spec.ts`) aus; die laufen
nur im Gate, nicht in deiner Sandbox. Lehnt der Gate ab, setzt er diese
Session mit seiner Meldung fort (hoechstens zweimal). Dann nur diese Meldung
beheben, oder die betroffene eigene Aenderung zuruecknehmen.

## Grenzen

Nur `README.md`, `zensical.toml`, `docs/anleitung/*.md`,
`docs/uebersicht/*.md`, `docs/ROADMAP.md`, `docs/status.md` und für neue
Unbekannte `docs/open-questions.md` bearbeiten. Messdaten, Laborjournal,
Timing-Aussagen, Hardwareprofil, Protokolldaten und Projektgeschichte sind
Quellen zum Verlinken, keine automatisch umzuschreibenden Texte. Halte
`AGENTS.md` und `Konzept.md` ein: keine erfundenen GSVmulti-Telegramme,
keine unmarkierten veralteten Werte, keine aus synthetischer Zeit
abgeleiteten Latenzen, keine Konfidenz als Fehlerwahrscheinlichkeit.

`docs/uebersicht/projekt-tour.md` ist an animierte Szenen
(`docs-site/assets/tour*.js`) gebunden. Ändere dort nur Fließtext innerhalb
bestehender Schritte. Die h3-IDs, die Hüllen `<section class="tour-chapter"
data-chapter=… data-label=…>` und `<div class="tour-step" markdown="1">`
sowie Zahl und Reihenfolge der Kapitel und Schritte bleiben unverändert; die
Browsertests prüfen je Schritt eine Szene und die Schrittzahl. Zahlen im
Tourtext stammen aus `scripts/tour-facts.py`; der Gate prüft sie vor deinem
Start. Meldet der Build trotzdem eine Abweichung, ändere nichts dafür, denn
Szenen und `tour-facts.json` sind nicht freigegeben. Nenne die gemeldeten
Tour-Schritte in der Zusammenfassung.
Abbildungen der Form `<figure class="tour-figure" data-scene="...">` in
anderen Seiten zeigen dieselben Szenen: `data-scene` nicht ändern und keine
neuen Szenennamen erfinden. Die Bildunterschrift darfst du anpassen, schreibe
aber keine Zahlen hinein.

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
