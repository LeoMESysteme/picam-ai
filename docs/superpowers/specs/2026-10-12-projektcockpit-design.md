# picam-ai Projektcockpit

Stand: 2026-10-12. Der Nutzer hat den beschriebenen Live-Cockpit-Entwurf bestätigt. Diese Spezifikation konkretisiert ihn zur schriftlichen Prüfung.

## Zweck und Erfolgskriterien

Eine neue, zunächst private Sites-Website zeigt auf einen Blick, welche Arbeit belegt ist, welche Aufgaben als Nächstes folgen und wie belastbar der aktuelle Projektstand ist. Details bleiben auf derselben Website zugänglich. Die Oberfläche ist deutsch, für Desktop und Mobilgeräte nutzbar und verlinkt jeden fachlichen Befund mit seiner Quelle.

Der Stand stammt aus dem GitHub-Repository [LeoMESysteme/picam-ai](https://github.com/LeoMESysteme/picam-ai). Lokale, unveröffentlichte Dateien und laufende Codex-Chats sind über diese Quelle nicht sichtbar. Ein aktiver Pull Request oder eine ausdrücklich als laufend bezeichnete Aufgabe belegt Arbeit; eine offene Aufgabe allein belegt keine laufende Bearbeitung.

## Übersicht und Vertiefung

Oben stehen drei Hauptbereiche:

- **In Arbeit:** aktive Pull Requests und im Status ausdrücklich laufende Aufgaben, einschließlich Herkunft und Aktualität.
- **Als Nächstes:** die aktive Aufgabenliste in ihrer dokumentierten Reihenfolge, Voraussetzungen und Blocker. Historische Aufgabenabschnitte werden nicht als aktuelles Backlog ausgegeben.
- **Projektzustand:** Prüfungen am aktuellen Standardbranch-Commit, offene Integrations- und Abnahmegrenzen sowie Alter der Belege.

Darunter folgen durchsuchbare und aufklappbare Ansichten für Prüfdetails, Roadmap P0–P8 mit Exit-Kriterien, offene Fragen, Validierung und jüngste Änderungen. Filter unterscheiden offen, in Arbeit, blockiert und erledigt. Ein Klick führt zum jeweiligen Originalbeleg oder Prüflauf.

Die Gestaltung verwendet einen hellen Hintergrund, klare Typografie, gut lesbare Karten und sparsame Statusfarben. Farben werden immer durch Text ergänzt. Navigation, Filter und Details funktionieren per Tastatur; schmale Displays ordnen die Hauptbereiche untereinander an.

## Datenquellen und Bedeutung

| Quelle | Zweck |
| --- | --- |
| Repository-Metadaten und Standardbranch | Branch und aktueller Commit |
| GitHub Check Runs und Actions-Läufe | Prüfstatus, Laufzeitpunkt, Ergebnis und Link |
| Offene Pull Requests | belegte Entwicklungsarbeit und Reviews |
| TODO.md | aktive Arbeitsreihenfolge und Voraussetzungen |
| docs/status.md | Betriebsstand und dokumentierte nächste Schritte |
| docs/ROADMAP.md | Phasen, Stand und harte Exit-Kriterien |
| docs/open-questions.md | OQ-Titel, Status und offene Entscheidungen |
| docs/VALIDATION.md | Messbelege mit Datum und Einschränkungen |
| CHANGELOG.md | letzte dokumentierte Änderungen |

Dokumente werden an den zuvor ermittelten Commit gebunden gelesen. Prüfergebnisse beziehen sich ausdrücklich auf ihren eigenen Commit. Der Zeitpunkt des Abrufs ist getrennt vom Datum des fachlichen Belegs. Eine jüngere Dokumentüberschrift verjüngt keine älteren Tests oder Messungen.

Die Normalisierung erhält Quelltext, Quelle und Datum. Bei unbekannter Dokumentstruktur zeigt die Seite einen Hinweis und den Originalabschnitt; sie erfindet keine Aufgabe. Bei widersprüchlichen Quellen bleiben beide Aussagen sichtbar. Die Seite entscheidet nicht automatisch, dass eine Aufgabe erledigt ist.

## Prüfstatus und Codequalität

Jede Prüfung zeigt bestanden, fehlgeschlagen, läuft, wartet, übersprungen, nicht nachgewiesen oder veraltet. Ein historischer grüner Lauf wird nicht als Prüfung des aktuellen Commits angezeigt. Fehlende pytest-, Lint-, Coverage- oder Typprüfungsdaten bleiben als fehlend sichtbar. Ein fehlgeschlagener Sammelworkflow beweist nicht, dass sämtliche Teilschritte fehlgeschlagen sind; Job- und Schrittinformationen werden getrennt dargestellt, soweit verfügbar.

Codequalität wird über nachvollziehbare Einzelbefunde beschrieben: aktuelle Prüfungen, Prüfabdeckung, Reviews, dokumentierte Schnittstellen, offene Fehler und Validierungsgrenzen. Eine numerische Gesamtnote und eine Behauptung wie „produktionsreif“ werden daraus nicht automatisch erzeugt. Tests zur Software und Messabnahmen an Hardware bleiben getrennt.

## Architektur und Aktualisierung

Die Website besitzt eine Sites-Anwendung mit einer Oberfläche, serverseitigen Lesezugriffen und einer getrennten Normalisierungsschicht. Sie nutzt den für Sites zugelassenen GitHub-Connector ausschließlich lesend, mit der Verbindung des angemeldeten Besuchers. Repository und erlaubte Leseaktionen sind serverseitig festgelegt; ein beliebiger Proxy und Schreibaktionen sind nicht vorgesehen.

Die Seite lädt beim Öffnen, nach einer ausdrücklich ausgelösten Aktualisierung und alle fünf Minuten während sichtbarer Nutzung. Sie pausiert automatische Abrufe im Hintergrund. Ein sichtbarer Hinweis nennt den letzten erfolgreichen Abruf und den ausgewählten Commit. GitHub-Änderungen erscheinen nach erfolgreichem nächsten Abruf, ohne die Website neu zu veröffentlichen.

Daten werden nicht zwischen Besuchern zwischengespeichert. Nach einem fehlgeschlagenen Abruf dürfen vorherige Daten in der aktuellen Sitzung sichtbar bleiben, erhalten aber unmittelbar den Hinweis „veraltet“ und den Fehler. Teilquellen scheitern unabhängig: Eine nicht erreichbare Validierungsdatei entfernt nicht die verfügbaren Prüfungen. Zeitlimits, begrenzte Ergebnismengen und vom Anbieter vorgegebene Wartezeiten verhindern unbegrenzte Abrufe.

Die neue Website wird nach der Prüfung privat veröffentlicht. Eine öffentliche Freigabe ist eine gesonderte Änderung der Zielgruppe.

## Beobachteter Ausgangsstand

Am 2026-10-12 wurde GitHub-Commit a8376d7fc67ad8bfc4de583be6576632814f87bf geprüft:

- Der [Playwright-Lauf](https://github.com/LeoMESysteme/picam-ai/actions/runs/38245332243) ist fehlgeschlagen; der Schritt „Run Playwright tests“ scheiterte, die anschließenden Doku-Prüfungen wurden übersprungen.
- Der [Doku-Lauf](https://github.com/LeoMESysteme/picam-ai/actions/runs/38245332413) wartet.
- Die offenen Pull Requests waren beim Abruf leer. Das beweist keine Inaktivität außerhalb von GitHub.
- TODO.md bezeichnet Nacharbeit 5 als offen. Der Status desselben Commits beschreibt den Code als vorhanden und den erneuten realen Gegencheck als nicht dokumentiert.
- Die Aussage „997 Tests grün, ruff sauber“ ist ein historischer Dokumentationsbeleg und kein aktueller CI-Nachweis.

Diese Ausgangsdaten werden nicht als unveränderliche Dashboard-Inhalte eingebaut.

## Prüfung vor Veröffentlichung

Sinnvolle automatisierte Tests prüfen die Normalisierung aktiver und historischer Aufgaben, Roadmap- und OQ-Status, widersprüchliche Dokumente, Commit-Zuordnung, fehlende Checks und veraltete Daten nach Abruffehlern. Die Oberfläche wird mit echten GitHub-Lesezugriffen auf Erstladen und Aktualisierung geprüft. Login-Rückkehr und der gehostete Connector-Zugriff werden getrennt von lokalen Tests bewertet.

Build und Paket müssen erfolgreich erstellt werden. Responsive Darstellung, Tastaturbedienung und die wichtigsten Filter werden geprüft, soweit die verfügbare Vorschau dies zulässt. Jede verbleibende Prüfgrenze wird bei der Übergabe genannt.

## Abgrenzung

Das Cockpit führt keine Projekt-Tests auf dem Raspberry Pi aus, bedient keine Hardware, ändert keine Aufgaben und schreibt nicht nach GitHub. Laufende Codex-Chats, lokale Ressourcen und Forgejo-Prüfungen benötigen eigene Datenquellen; sie werden ohne solche Belege nicht als Livezustand dargestellt.
