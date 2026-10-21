# picam-ai Projektcockpit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Eine private Sites-Website zeigt den aktuellen Projektstand aus Forgejo übersichtlich und mit vertiefenden Belegen. GitHub ist ausschließlich Mirror.

**Architecture:** Eine Vinext-Sites-Anwendung liest die feste Forgejo-Repository-API per GET mit einem geschützten serverseitigen Read-only-Token. Eine reine Normalisierungsschicht ordnet Aufgaben, Prüfungen und Dokumente ein. Die Oberfläche hält einen sitzungsbezogenen Stand und kennzeichnet Abruffehler unmittelbar.

**Tech Stack:** Sites-Vinext-Starter, React, TypeScript, Node-Testläufer, Forgejo-REST-API und geschütztes Sites-Geheimnis FORGEJO_ACCESS_TOKEN.

**Spec:** [Projektcockpit](../specs/2026-10-12-projektcockpit-design.md)

## Global Constraints

- Neue Website zunächst privat; deutsche, responsive und per Tastatur bedienbare Oberfläche.

- Beim Öffnen, auf Wunsch und alle fünf Minuten bei sichtbarer Nutzung aktualisieren.

- Jede Aussage mit Quelle, Belegdatum und gegebenenfalls geprüftem Commit.

- Historische Prüfungen nicht als aktuellen Nachweis und fehlende Daten nicht als bestanden ausgeben.

- Widersprüche sichtbar lassen; keine pauschale Codequalitätsnote.

- Forgejo-Zugriff serverseitig lesend, mit geschütztem Token, ohne gemeinsame Datenablage; bisheriger privater Sites-Empfängerkreis bleibt erhalten.

- Keine Änderungen am Messpfad, kein Hardwarezugriff und keine Repository-Schreibaktionen.

- Site-Quelle in einem separaten Checkout unter sites/picam-ai-cockpit; vorhandene Repo-Änderungen erhalten.

## Review Focus

- Geänderte oder fehlende Markdown-Abschnitte: Originalquelle und Hinweis statt erfundener Aufgaben.

- Ein neuer Commit bei alten grünen Prüfungen: kein aktueller grüner Gesamtzustand.

- Erfolg einzelner Quellen und Fehler anderer: verfügbare Bereiche bleiben nutzbar.

- Login-, Netzwerk- oder Anbieterfehler: alte Daten sofort als veraltet markieren und Wartezeit beachten.

- Historische nummerierte Listen und erledigte OQs: nicht als aktuelle Arbeit ausgeben.

## Dateiverantwortung

Site-Pfade beziehen sich auf sites/picam-ai-cockpit:

| Datei | Verantwortung |
| --- | --- |
| .openai/hosting.json | Site-ID und Hosting; Forgejo-Token separat als Runtime-Geheimnis |
| lib/project-model.mjs | reine Auswertung der Dokumente und Prüfungen |
| lib/forgejo-data.mjs und lib/forgejo-runtime.ts | feste Repository-API, geschützter Token und begrenzter Abruf |
| lib/activity-model.mjs und lib/code-analysis.mjs | Commit-Aktivität und geprüfte Quelltextzeilen |
| app/api/project/route.ts | validierter, gleichursprünglicher POST-Endpunkt |
| components/project-dashboard.tsx | Übersicht, Details, Suche und Aktualisierung |
| app/page.tsx und app/layout.tsx | Einstieg und Metadaten |
| app/globals.css | responsives Layout und sichtbare Statuszustände |
| tests/project-model.test.mjs | fachliche Grenzfälle der Auswertung |
| tests/project-refresh.test.mjs | Fehler, Veralterung und Teilergebnisse |

### Task 1: Normalisierter Projektstand

**Interfaces:** normalizeProject(input) liefert head, tasks, checks, roadmap, questions, evidence, changes und warnings; jedes Element behält source und evidenceDate. reconcileRefresh(previous, incoming) erhält nur ausdrücklich veraltete Restdaten.

- [ ] Node-Tests schreiben: historische TODO-Abschnitte ausgeschlossen; P0–P8 erhalten; erledigte OQs korrekt gefiltert; fehlendes pytest/ruff als nicht nachgewiesen; alte grüne Checks bei neuer SHA veraltet; Nacharbeit-Widerspruch sichtbar; unbekannte Struktur mit Quellhinweis.

- [ ] node --test tests/project-model.test.mjs ausführen und erwartetes Scheitern ohne Implementierung prüfen.

- [ ] lib/project-model.mjs mit diesen Schnittstellen implementieren.

- [ ] Tests ausführen und grünes Ergebnis prüfen; Änderung im Site-Checkout sichern.

### Task 2: Live-Daten und Aktualisierung

**Interfaces:** loadForgejoProject(client) liefert den Eingabetyp von normalizeProject und separate Quellenfehler. Die POST-Endpunkte für Projekt, Aktivität und Zeilenanalyse validieren Origin und SHA und liefern private No-Store-Antworten.

- [ ] Tests schreiben: abgelehnte Forgejo-Antwort; Teilfehler; fehlender Branch; veraltete Daten nach Fehler; Wiederholung erst nach retryAfterMs; keine Übernahme von Providertext als HTML.

- [ ] node --test tests/project-refresh.test.mjs ausführen und den roten Ausgang bestätigen.

- [ ] Starter im separaten Checkout einrichten, Site einmal registrieren, ID sofort persistieren und nötige Starter-Abhängigkeiten installieren.

- [ ] Forgejo-Token als geschütztes Sites-Runtime-Geheimnis setzen; GET-Leser und POST-Endpunkte mit festem Repo, vollständiger Paginierung, Origin-Prüfung, gemeinsamen Zeitlimits und privaten No-Store-Antworten implementieren.

- [ ] Erstladen und Refresh mit echter Forgejo-API prüfen; Tests ausführen und Änderungen sichern.

### Task 3: Cockpit und Vertiefung

**Interfaces:** ProjectDashboard nutzt den normalisierten Projektstand und die POST-Endpunkte; keine API-Token oder direkten Provider-Aufrufe im Browser.

- [ ] Hauptbereiche „In Arbeit“, „Als Nächstes“, „Projektzustand“ und Vertiefungen zu Checks, Roadmap, OQs, Validierung und Änderungen bauen.

- [ ] Suche, Statusfilter, aufklappbare Originalbelege und Quellenlinks hinzufügen; Live-Aktualisierung alle 300000 ms nur bei sichtbarer Seite.

- [ ] Kontrastreichere responsive Gestaltung, P0–P8-Timeline, Codebase-/Commit-Statistiken, reduzierte Bewegung und Tastaturbedienung umsetzen.

- [ ] In der verfügbaren Vorschau Desktop, Mobilansicht, leere Listen, Quellfehler, Suche und Filter prüfen; keine Testabdeckung oder Codequalitätsnote erfinden.

### Task 4: Prüfen und privat veröffentlichen

- [ ] Node-Tests, TypeScript-Prüfung und den Sites-Build ausführen; nur bei Erfolg weitergehen.

- [ ] Abschließenden Quellstand unabhängig prüfen; relevante Befunde beheben und betroffene Checks wiederholen.

- [ ] Runtime-Geheimnis und bisherigen privaten Empfängerkreis prüfen; Sites-Quellcredential ausschließlich im Sitzungsspeicher und über stdin verwenden.

- [ ] Site-Workflow mit dem exakten Quellstand ausführen, pushen und Paket erzeugen.

- [ ] Exakten Commit und Paket mit save_version_and_deploy_private veröffentlichen; nichtterminales Deployment bis zum Ergebnis verfolgen.

- [ ] Gehostetes Erstladen, Refresh und Login-Rückkehr prüfen, soweit die verfügbare Browserunterstützung erlaubt; unbestätigte Bereiche ausdrücklich benennen.

- [ ] Spezifikation und diesen Plan in der Library erhalten; Repo-Status vor dem letzten Commit aktualisieren und Site-URL übergeben.

## Vorgeschlagene Ausführung

Native: Der Hauptagent setzt die vier eng verbundenen Aufgaben in diesem Chat um. Eine unabhängige Abschlussprüfung beurteilt Datenwahrheit, Fehlerzustände und den Quellstand vor Veröffentlichung. Dies vermeidet mehrfaches Übergeben der gemeinsamen Datenschnittstellen.
