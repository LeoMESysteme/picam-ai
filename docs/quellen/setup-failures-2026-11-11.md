# Einrichtungsfehler vom 2026-11-11: Bilder und Offline-Reproduktion

Spätere Abbrüche, verzögerte Oberfläche und Worktree-/Fokusprüfung stehen im
[Zusatzpaket nach Neustart](setup-followup-2026-11-11.md). Das hier
beschriebene erste Archiv bleibt unverändert.

Das [Belegpaket](setup-failures-2026-11-11.zip) sichert die vorhandenen
Originaldateien der fehlgeschlagenen Einrichtungen einschließlich der späteren,
vom Nutzer geänderten Aufstellung. [SHA-256](setup-failures-2026-11-11.sha256).
Es enthält außerdem den damaligen Quellcode, die Laufzeitversionen, einen
Status-Schnappschuss und ein ausführbares Offline-Rezept. Die ursprüngliche
Kameraposition wird zur Untersuchung der gespeicherten Bilder nicht benötigt.
Die Fehler sind weiterhin offen: [OQ-69](../open-questions.md#oq-69) und
[OQ-70](../open-questions.md#oq-70). Der zusätzlich gemeldete Bedienfehler
[OQ-71](../open-questions.md#oq-71) hat hohe Priorität. Dieses Paket belegt
keine Fehlerbehebung.

## Welche Fälle gesichert sind

Zeiten in den IDs sind UTC-Kennzeichnungen der Host-Wanduhr. Sie sind keine
Bildaufnahmezeitstempel. Die aktuelle lokale Zeitzone war MEZ (UTC+1).

| Sitzung | Gesicherter Zustand | Bildbelege | Einordnung |
| --- | --- | --- | --- |
| `live-20261111T095341Z` | Abbruch beim Fokus | kein Standbild vorhanden | Kontext; kein Rasterfehler belegt |
| `live-20261111T154403Z` | `startlage_mehrdeutig` in drei Versuchen | letztes Standbild | konkurrierende Rasterlagen; OQ-69 |
| `live-20261111T154459Z` | `keine_startlage` in drei Versuchen | letztes Standbild | erster ausführlich untersuchter Rasterfehler; OQ-69 |
| `live-20261111T155404Z` | `Einrichtung abgebrochen`; erster Fit `keine_startlage` | ein Standbild | kein vollständig ausgeschöpfter Drei-Versuche-Lauf |
| `live-20261111T155557Z` | Vorschlag vorhanden; Raster `OK`, Nachführung `FEHLER` | Standbild, zweites Mittelbild, drei Überlagerungen | andere Aufstellung; gesicherter Zustand nach manuellen Bereichsänderungen, OQ-70 |

Die Rasterfehler und der spätere Nachführfehler sind unterschiedliche
Fehlerstellen. Eine gemeinsame Ursache ist nicht nachgewiesen.

## Inhalt und Herkunft

Das ZIP enthält einen Ordner `setup-failures-20261111/`:

* `sessions/<ID>/setup/`: sämtliche zum Sicherungszeitpunkt vorhandenen
  Setup-Dateien, unverändert kopiert. Darunter `failure.json`,
  `camera-settings.json`, `cell-text.json`, PNG-Bilder und beim letzten Fall
  `proposal.json` mit Quad, Raster, Prüfkennzahlen, Nachführkonfiguration,
  Bereichen, Änderungsliste und Vorschlagsrevision.
* `source-08ac9b9.tar.gz`: versionierte Quellen, Tests, Skripte,
  `pyproject.toml`, Konzept, Abhängigkeiten und Hardwareprofil aus
  `08ac9b9cc818c013de10e6cee6579d372607d59e`. Der relevante laufende Quellbaum
  war unverändert. Die Kopie bleibt auch nutzbar, wenn der Branch entfällt.
* `environment.json`: Python-, OpenCV-, NumPy- und weitere Paketversionen,
  Plattform, Architektur und Konfiguration der Projekt-venv.
* `reference-assets/var/`: eingefrorene Dot-Matrix-Vorlagen Stufe 2c
  (SHA-256 gegen den Quellcode geprüft) und damalige Timing-Kalibrierdatei.
  Für spätere Gegenleseanalysen erhalten; die historische Timing-Datei
  verleiht einem anderen Rechner oder Aufbau keine Kalibrierung.
* `live-status.json`: lesend abgefragter Zustand mit Kamera-Reglerrückmeldungen,
  Prüfergebnissen und manueller Bereichsauswahl. Der Erfassungszeitpunkt
  steht mit Zeitbasis und unbekannter Unsicherheit darin.
* `cases.json`, `provenance.json`: Fallzuordnung, ursprüngliche Pfade,
  Dateigrößen und SHA-256. Die Originale entsprachen bei der nachfolgenden
  Kopierprüfung noch den gesicherten Bytes.
* `previous-analysis.json`: Eingrenzung des ersten Rasterfehlers aus der
  vorherigen Diagnose. Falscher Plus-Anker am Gehäuserand ist ein Teilbefund,
  keine abschließend bewiesene alleinige Ursache.
* `replay.py`, `replay-results.jsonl`: Offline-Rezept und tatsächlich
  ausgeführte Wiederholung auf dem archivierten Quellstand.
* `ui-dead-end-report.json`, `ui-dead-end-results.jsonl`: Bedienermeldung,
  hohe Priorität, Korrekturanforderungen und ausgeführte Wiederholung der
  fehlenden Auswege bei einem fehlerhaften Vorschlag.
* `MANIFEST.json`: Größe und SHA-256 aller übrigen Paketdateien. Das Manifest
  selbst wird über den äußeren ZIP-Hash gebunden; kein Signaturnachweis.

Absolute Pfade in Original-JSON bleiben absichtlich erhalten. Das
Offline-Rezept löst seine Bilder relativ zum entpackten Paket auf. Das Paket
nicht als bestätigtes Produktionsprofil in eine laufende Werkbank übernehmen.

## Ohne Kamera wiederholen

Im Repositorywurzelverzeichnis, mit der Projekt-venv und ihren Debian-Paketen:

```bash
sha256sum -c docs/quellen/setup-failures-2026-11-11.sha256
./.venv/bin/python -m zipfile -e docs/quellen/setup-failures-2026-11-11.zip var/replay
./.venv/bin/python var/replay/setup-failures-20261111/replay.py
./.venv/bin/python var/replay/setup-failures-20261111/replay.py --raster --tracking
```

In einen neuen, leeren Zielordner entpacken. Der erste Rezeptaufruf prüft nur
Dateiliste und Hashes. Die Rasterwiederholung kann auf dem Pi mehrere Minuten
dauern. Sie verwendet automatisch die eingefrorenen Quellen in einem
temporären Verzeichnis. Kamera, serielle Schnittstelle und laufender Dienst
werden nicht angesprochen. Es werden keine Pakete nachinstalliert.

Für einen einzelnen Fall:

```bash
./.venv/bin/python var/replay/setup-failures-20261111/replay.py --raster --case live-20261111T154459Z
```

Für den Vergleich mit einer späteren Korrektur:

```bash
./.venv/bin/python var/replay/setup-failures-20261111/replay.py --raster --tracking --source /pfad/zum/korrigierten/checkout
```

Die Ausgabe nennt jeweils beobachtetes und historisch erwartetes Ergebnis.
Mit `--source` sind Abweichungen Vergleichsergebnisse; ein erfolgreicher Fit
allein beweist weder ein korrektes Quad noch eine sichere Messfreigabe.
Die spätere Korrektur braucht zusätzlich überprüfte Geometrie, Gegenlesen,
negative Fälle und passende Regressionstests.

## Bedienfehler mit hoher Priorität: Vorschlag ohne Ausweg

Der Nutzer meldet zur letzten Einrichtung: Bestätigen wird angeboten, dann
wegen des Fehlerurteils abgelehnt; Abbrechen und Neu einrichten fehlen.
Gesicherter Zustand ist `setup_ready + setup.overall=FEHLER`. Die korrekte
Sperre fehlerhafter Bestätigungen bleibt erforderlich; der Bug ist der
fehlende Ausweg und das fälschlich aktivierbare Bestätigen.

Ohne Kamera wiederholen (zusätzlich vorhandenes Node.js erforderlich):

```bash
./.venv/bin/python var/replay/setup-failures-20261111/replay.py --ui
```

Dieser Aufruf verwendet die tatsächlichen reinen UI-Funktionen aus
`setup/confirm.js` und `shell.js` sowie die tatsächlichen Vorbedingungsprüfungen
von `LiveService.confirm` und `cancel_setup`. Er öffnet keinen Browser und
erzeugt kein Bildschirmfoto. Die Servicemethoden werden an einem isolierten
Objekt mit dem gesicherten Vorschlag geprüft; kein Kameraobjekt,
Einrichtungsworker, HTTP-Aufruf oder Messlauf wird gestartet.

Auf dem historischen Quellstand nachgewiesen:

* Name und Format-Haken machen `fieldsReady=true`, obwohl `FEHLER` vorliegt.
* Kontextaktionen enthalten allein den aktiven Knopf „Bestätigen“.
* Bestätigen wirft „Einrichtung meldet FEHLER - nicht bestaetigbar“.
* Abbruch wirft „Keine Einrichtung laeuft“, weil nur `setup_running` zulässig ist.
* Nach beiden abgelehnten Aktionen bleibt `setup_ready` erhalten.

Korrektur zuerst als eigenen Bedienfehler bearbeiten: Bestätigen bei
`FEHLER` sperren und verständlich erklären; Vorschlag verwerfen sowie
Neueinrichtung ermöglichen; Diagnosebelege dabei erhalten. Nur einen
Abbrechen-Knopf hinzuzufügen reicht angesichts der Backend-Vorbedingung
nicht. Regressionen müssen beide Bestätigungswege (Knopf/Tastatur),
abgelehnte Bestätigung, erreichbare Auswege, `OK`/`WARNUNG`, laufende
Einrichtung und laufenden Messlauf abdecken. [OQ-71](../open-questions.md#oq-71)
und [TODO](../../TODO.md) führen diesen Fehler mit hoher Priorität.

## Was vollständig wiederholbar ist und was fehlt

Die Rasterstartsuche kann auf den vier erhaltenen Standbildern mit denselben
Codeeingaben wiederholt werden. Zellentexte sind historische Prüfevidenz;
`fit_lattice` erhält sie nicht zur Korrektur eines DUT-Werts.

Beim letzten Fall berechnet `--tracking` die räumliche Verteilung und Reserve
aus dem gesicherten Quad, den Bereichen und der Konfiguration erneut:
16 Bereiche, Achsenseiten `[[2, 6], [11, 7]]`, mindestens drei pro Seite
erforderlich, mit Reserve fünf. Das ist eine Wiederholung dieses
Geometrie-Gates, keine neue Stabilitätsprüfung. Die 20 protokollierten
manuellen Änderungen enthalten auch abgelehnte Ergänzungen; daraus darf
keine Serie von 20 angenommenen Bereichen abgeleitet werden.

Die damalige Anwendung hat die acht Rohbilder eines Mittelbildstapels und
die acht Stabilitäts-Einzelbilder nicht auf Platte geschrieben. Bei mehreren
Startversuchen wurde außerdem `still.png` überschrieben: von den ersten
beiden Versuchen bleiben die Texte und Fehlergründe, aber keine eigenen
Bilder. Beim letzten Fall fehlt eine getrennt gespeicherte ursprüngliche
automatische Vorschlagsrevision. Diese Daten lassen sich nachträglich nicht
aus dem Mittelbild oder den Kennzahlen zurückgewinnen. Insbesondere sind
zeitliche Stabilität, Multiplexing und die vollständige Folge automatischer
und manueller Vorschlagsprüfungen damit nicht exakt wiederholbar.

Für künftige Aufnahmen bei einer Korrektur alle Rohbilder je Versuch,
Original-Zeitbasen und Unsicherheiten, Stabilitätsproben und jede
Vorschlagsrevision mit deren Eingaben und Ausgaben sichern. Fehlende
Einzelbilder niemals durch Kopien desselben Mittelbilds ersetzen und dann
als unabhängigen Stabilitätsnachweis ausgeben.

Datei-Mtime und Sicherungszeitpunkt dienen nur der Herkunftszuordnung. Aus
diesem Paket folgt keine Aufnahmezeit-, Framealter- oder Latenzaussage.
