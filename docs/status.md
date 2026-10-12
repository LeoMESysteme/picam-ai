# Status — Stand 2026-10-12 (Sessionende)

Dieser Snapshot wird zum Sessionende überschrieben. Verlauf:
[Changelog](../CHANGELOG.md) und
[Projektgeschichte](project_history.md); Aufgaben:
[TODO.md](../TODO.md).

## Aktuelle Session — Projektcockpit Version 3 mit Forgejo

Das private [Projektcockpit](https://picam-ai-cockpit.me-me-system-9148.chatgpt.site)
ist als Version 3 veröffentlicht. Der Nutzer hat Forgejo als maßgebliches
Repository bestätigt: [l.hentschke/picam-ai](https://ds1515.me-systeme.de/l.hentschke/picam-ai).
GitHub ist ein Mirror und liefert keine Prüfaussagen mehr für das Cockpit.
Die Seite liest ausschließlich per GET aus der festen Forgejo-API. Der
Read-only-Token ist als geschütztes Sites-Runtime-Geheimnis
`FORGEJO_ACCESS_TOKEN` hinterlegt. Er fehlt in Quell- und Build-Dateien;
private Site-Zielgruppe unverändert, ein zugelassener Nutzer.

Neue Statistiken: Commit-Aktivität für 7/30/90 Tage, aktive Tage,
Merge-Commits und jüngste verlinkte Änderungen. Dateivolumen am Commit
und Forgejo-Repository-Größe werden getrennt ausgewiesen. Die bei Bedarf
geladene Zeilenanalyse prüft alle eigenen Code-Dateien gegen ihre Git-Blobs,
zählt physische und nichtleere Quelltextzeilen einschließlich Kommentaren
und trennt Produktionscode, Tests und Hilfscode. Fremdbibliotheken und
generierte Verzeichnisse zählen nicht mit. Die acht größten eigenen
Quelldateien und direkter Handlungsbedarf ergänzen die Übersicht.

Paginierung, Gesamtzeitlimit, Speichergrenzen und Veralterung bleiben
sichtbar abgesichert. Unvollständige Historien ergeben Mindeststände;
fehlende oder unlesbare Quelldateien verhindern vollständige Zeilenwerte.
Alte Ergebnisse behalten ihre ursprüngliche SHA und die Veraltet-Markierung.
Die bestehende kontrastreiche Gestaltung und reduzierte Bewegung bleiben
wirksam. Direkte Sprunglinks führen von der Übersicht zu den Prüfungen.

**Verifikation:** 51 Website-Node-Tests und TypeScript bestanden;
Sites-Build erfolgreich. Browser-QA mit echten privaten Forgejo-Daten
bestand für Erstabruf, Zeiträume, Zeilenwerte, Commit-Cache, Desktop/Mobil,
reduzierte Bewegung, Origin-/SHA-Prüfung, initialen Abruffehler und alte
Ergebnisse nach Quellenfehler. Unabhängige Prüfung ohne blockierende
Restbefunde. Strenger Doku-Build sowie 27 Doku-Browsertests bestanden.
Keine Python-Suite oder Betriebsmessung für diesen Cockpit-Auftrag gestartet.

**Gehosteter Abruf:** Mit bestehendem technischen Zugriff auf die private
Site bestanden Projekt-, Aktivitäts- und Zeilen-Endpunkte, ohne Quellenfehler.
Besucher-Anmeldung wurde nicht separat nachgestellt. GitHub-Einwilligung
ist für die neue Datenquelle nicht nötig (`requires_byop=false`).
Abgerufen am 2026-10-12: Forgejo-Commit
`f06f7b46856d3708c85e74816e3d4b589e5233e0`, 270 versionierte Dateien,
262 vollständig geladene Commits, 173 eigene Code-Dateien,
51.760 Quelltextzeilen, 44.569 nichtleer, 7.191 Leerzeilen.
Aktuelle Playwright- und Doku-Läufe bestanden; älterer Wartungslauf veraltet,
pytest-/ruff-CI-Nachweise fehlend. Diese Beobachtung bleibt ein Snapshot.

**Site-Quelle:** Separates Repository `sites/picam-ai-cockpit`,
Quellcommit `c8449c22b5bc710f75d2d7c44e38e82ed7480e25`;
Site-ID `appgprj_6accdd4468948191be0d5301888c835f`.
[Spezifikation](superpowers/specs/2026-10-12-projektcockpit-design.md) und
[Plan](superpowers/plans/2026-10-12-projektcockpit.md) sind im Repo und
unter ihren bisherigen Library-Identitäten auf Forgejo korrigiert.
Keine Hardware bedient und keine neue Abhängigkeit eingeführt.
Die parallelen Sessionergebnisse darunter bleiben erhalten.

## Übergabeprüfung für 2026-10-13

Die Playwright-Korrektur ist als `881b411` committet. Der lokale
Cockpit-Doku-Commit `9d6994a` und Remote-Commit `ef76811` (Tour-Fakten aus
dem Code) sind im zusammengeführten Stand enthalten. Der einzige Konflikt lag in
den neuen Changelog-Abschnitten; beide Änderungen bleiben erhalten.
Auftrag dieser Abschlusssession ist Commit und Push nach `origin/master`.
Die übrigen lokalen Arbeiten bleiben separat offen.

Noch offen im Hauptcheckout: die neue Fokuswarnungs-Idee in
`PLANNED_FEATURES.md` sowie Konzeptillustration und Prompt
unter `docs/illustrations/`. Im separaten Worktree
`.claude/worktrees/feat-messpfad-live` steht Branch
`worktree-feat-messpfad-live` auf `71320bf`; die Spezifikation ist geändert
und `docs/superpowers/plans/2026-10-12-messpfad-live.md` liegt unversioniert
vor. Dort beginnt der nächste Implementierungsschritt mit Task 1 des Plans.
Spezifikation und Plan vor der Umsetzung gemeinsam prüfen und sichern.
Meilenstein 1 umfasst Browser-Einrichtung, Live-Lesen und JSONL-Audit;
serielle Ausgabe an GSVmulti folgt separat (OQ-07).

Die Playwright-CI ist korrigiert: `playwright.yml` verlangt nun `picam-docs` statt
`ubuntu-latest`, lädt nur Chromium ohne Systempaketinstallation und nutzt
den Forgejo-Artefaktupload. `playwright.config.ts` grenzt Browsertests auf
`.spec.ts` ein; Node-Harnische mit Pytest-Fixtures werden nicht mehr von
Playwright geladen. Changelog, Hosting-Doku, Projektgeschichte und der
Runner-Kommentar in `docs.yml` sind angepasst. Runner-Label und YAML/
Shell-Schritte sind geprüft; 2 Chromium-Beispieltests und 5 Python-Tests
für die Node-Harnische bestehen. Strikter Doku-Build bestanden, neue
Doku-Browserprüfung mit allen 26 Tests bestanden, vor dem Merge.
Auch der zusammengeführte Stand ist geprüft: strikter Doku-Build,
**27 Doku-Browsertests** und **53 betroffene Python-Tests** bestanden.
Ruff für Tour-Fakten-Skript und zugehörige Tests, Runner-Label, YAML/
Shell-Schritte sowie Diff-Prüfung bestanden. Die vollständige Python-Suite
wurde nach dem Merge nicht erneut ausgeführt; ihr Lauf unten gehört zur
vorherigen Übergabeprüfung. Ein echter Forgejo-Lauf ist in dieser Sitzung
nicht abgenommen; alte wartende Läufe behalten die alte Workflow-Version.

Weitere ungesicherte Arbeit liegt im alten Worktree
`/home/me-systeme/picam-ai-assist`: vorgemerkte Änderungen an README,
Bedien-/Glossar-/Rezept-Doku und Status, ein geänderter Cursor-Test sowie
unversionierte `.venv`-, `node_modules`- und `var`-Verknüpfungen zum
Hauptcheckout. Auch `var` im Worktree `/home/me-systeme/picam-ai-ernte`
ist eine solche Verknüpfung, keine zusätzliche Datenkopie.
Bei der Nachprüfung waren Livevorschau-, Glossar- und Rezept-Doku bereits
identisch mit dem Hauptcheckout; README und Cursor-Test wichen noch ab.
Diese Worktrees vor einer Bereinigung auf benötigte Änderungen prüfen.
Das eigenständige Cockpit-Repository `sites/picam-ai-cockpit` war bei der
ersten Prüfung auf `126c59e` sauber. Bei der Nachprüfung läuft dort
inzwischen die parallele Erweiterung: `lib/codebase-model.mjs` ist
geändert; `lib/activity-model.mjs`, `lib/code-analysis.mjs` sowie
`tests/activity-model.test.mjs` und `tests/code-analysis.test.mjs` sind
neu und unversioniert. Diese laufende Arbeit ist von den oben genannten
Prüfergebnissen nicht abgedeckt.

Frische Prüfungen: Ruff für `src`, `tests`, `scripts`, `examples` bestanden;
OQ-Index aktuell; `git diff --check` bestanden. Der Workbench-Browsertest
mit seiner von Pytest erzeugten Fixture besteht (3 Python-Tests).
Der strikte Doku-Build besteht, ebenso alle 26 Doku-Browsertests.
Die vollständige Mock-Testsuite (`./.venv/bin/pytest --mode=mock -q`)
besteht: **1007 bestanden, 3 übersprungen, 1 erwarteter Fehlschlag**,
Laufzeit 440,37 s. Die Workbench-Browserregressionen brauchen die von
Pytest erzeugte Fixture.

Die Projekt-venv nutzt `include-system-site-packages = true`. Kein
`var/RECORDING_IN_PROGRESS`-Marker lag bei der Prüfung vor; keine Kamera
oder serielle Hardware wurde bedient. Auf `/` waren 4,4 GB frei bei
91 % Belegung, `/dev/shm` hatte 4,0 GB frei. Vor neuen Aufnahmen Platz und
Arbeitsspeicher erneut prüfen; eine externe Sicherung von `var/` bleibt offen.

## Projektcockpit — angefragte Erweiterung vom 2026-10-12

Der Nutzer wünscht Commit-Statistiken und weitere Größenkennzahlen,
insbesondere Codezeilen, sowie begründete Verbesserungsvorschläge.
Die vorhandenen Datenpfade und GitHub-Ressourcen wurden lesend geprüft.
Ein kurzer Entwurf mit Commit-Aktivität, getrennten Größenangaben,
Commit-bezogener Quelltextzeilenanalyse, größten Quelldateien und direktem
Handlungsbedarf liegt zur Freigabe vor. Die neue Umsetzung hat noch nicht
begonnen; private Sites-Version 2 bleibt der veröffentlichte Stand.
Andere parallele Sessionergebnisse bleiben unten erhalten.

## Projektcockpit Version 2 — bisheriger Stand vom 2026-10-12

Das private [picam-ai Projektcockpit](https://picam-ai-cockpit.me-me-system-9148.chatgpt.site)
ist aktualisiert und als Version 2 veröffentlicht. Die Roadmap zeigt P0–P8
als verbundene grafische Phasenfolge, mobil vertikal. Meilensteine öffnen
Exit-Kriterien, Voraussetzungen und Originalbelege. Es werden keine
unbelegten Terminpläne eingeführt.

„Codebase & Prüfungen“ ergänzt Dateizahlen, Quellcode- und Testdateien,
eigenes Codevolumen, Sprachanteile und die neun größten Repository-Bereiche.
Der vollständige GitHub-Dateibaum wird an denselben Commit wie die übrigen
Daten gebunden. Fremdbibliotheken zählen nicht zum eigenen Code;
Daten-Fixtures zählen zum Gesamtvolumen, aber nicht zum Sprachvolumen.
Dateigröße wird ausdrücklich von Codezeilen, Coverage und ausgeführten
Tests unterschieden. Unvollständige Dateibäume werden abgelehnt; bei
Abruffehlern bleibt ein alter Datensatz mit seinem Commit als veraltet sichtbar.

Dunkelgrüne Navigation, satterer Hintergrund und stärkere Beschriftungen
verbessern den Kontrast. Ansichtswechsel, Karten, Diagrammbalken und
Meilensteine sind animiert; reduzierte Bewegung wird berücksichtigt.
Zahlen bleiben auch während Übergängen exakt.

**Prüfungen der Website:** 33 fachliche Node-Tests, TypeScript und
Sites-Build bestanden. Lokale Browserprüfung mit echten nativen GitHub-Daten
bestand für Statistik, Timeline-Details und Filter, Desktop/Mobilbreite,
reduzierte Bewegung sowie veraltete Statistiken. Keine Browserfehler.
Nach unabhängiger Prüfung wurden Textkontrast, Screenreader-Status und
Diagramm-Erläuterungen verbessert. Gemessener Mindestkontrast der geprüften
kleinen Statistiktexte: 5,99:1; Belegdatum auf Timeline-Karten: 5,41:1.

**Veröffentlichung:** Sites meldet Erfolg. Site-ID:
`appgprj_6accdd4468948191be0d5301888c835f`; Quellcommit im eigenständigen
Site-Repository `sites/picam-ai-cockpit`:
`126c59edc4b315505fe294dbc62a50a1c271bf3d`.
Die freigegebene [Spezifikation](superpowers/specs/2026-10-12-projektcockpit-design.md)
und der [Plan](superpowers/plans/2026-10-12-projektcockpit.md) bleiben gültig.
Die Besucheranmeldung und GitHub-Einwilligung im Hosting wurden weiterhin
nicht unabhängig verifiziert; die Live-Vorschau nutzt echte native Lesezugriffe.

Beim Browserabruf am 2026-10-12: Commit
`6868d858a1d843f79b470dbefc752912e99715fe`, 263 versionierte Dateien,
64 Code-Dateien unter src/, 59 Testdateien, 2.075.962 Byte eigener Code.
Dies ist ein Abrufsnapshot; das Cockpit aktualisiert den Stand weiter.
Keine picam-ai-Python-Tests oder Betriebsmessungen wurden ausgeführt und
keine Hardware bedient. Die Betriebsangaben unten bleiben frühere Belege.

## Projekt-Tour — alle sechs Kapitel vorhanden

Die [Projekt-Tour](uebersicht/projekt-tour.md) steht seit `812bb59` mit
allen sechs Kapiteln in `master`: Überblick, Erkennung, Zeit, Training,
Bedienung und Regeln. Sie zeigt eine animierte SVG-Bühne mit lokalen
anime.js-Dateien, Kapitelwahl und Links in die Doku. Der frühere
Zwischenstand „nur Überblick und Erkennung fertig“ ist überholt.
Der integrierte Remote-Commit `ef76811` bezieht die Tour-Fakten aus dem
Code. Änderungen am gezeigten Verhalten brauchen
weiterhin Text und Szene zusammen (AGENTS.md).

## Betrieb und Messstand

Die aktive Kamera ist die Logitech StreamCam über UVC (046d:0893). Die
IMX500 ist seit 2026-09-25 außer Betrieb
([Hardwareprofil](HARDWARE_PROFILE.md)). Die echte Anbindung an GSVmulti
bleibt wegen der fehlenden Telegrammspezifikation offen
([OQ-07](open-questions.md#oq-07)).

**Dot-Matrix-Leser: Abnahme 3 bestanden (2026-09-30).**
* Stufe 2 ist eingefroren als `templates-stufe2c-2026-09-30.json`
  (`6f20dec4…`), Lesercode wie `ef5cedf`, Normierung `bg_closing_v1`.
* Neue Aufstellungen `ab5` (frontal, gedreht) und `ab6` (schräg von links):
  215/215 richtig, 0 falsch, 0 abgelehnt, Obergrenze der Fehlerrate 3,5 %.
* Einschränkungen:
  * nur Raumlicht, ein Gerät, eine Einheit,
  * bei `ab6` verwarf der Import 42 % als `zellen_inkonsistent`.
* Abnahme 2 war zuvor an **falsch sitzenden Punktrastern** gescheitert,
  nicht am Leser. Seitdem wird der Rasterversatz vor jeder Ernte gemessen
  (`scripts/profile-regrid.py still`, Grenze 0,15 Punktspalten).
* **2026-10-01, Lesetest `sc7`:** frontal und nah, bisher größte
  Abbildung mit etwa 900 px Glasbreite, nicht in den Vorlagen.
  111/111 richtig, 0 falsch, 0 abgelehnt. Kein formaler Abnahme-Lauf.
* **Entscheidung 2026-10-01 (Variante B):** Der Leser gilt für den
  GSV-Sensor als ausreichend validiert. Als Nächstes kommt die Anbindung an
  den Messpfad (TODO.md Punkt 2). Andere Lichtquellen und weitere Geräte
  bleiben als Einschränkung genannt.
* Zahlen: [VALIDATION.md](VALIDATION.md), [Fortschritt](FORTSCHRITT.md),
  [Laborjournal](lab_journal.md). Entscheidung:
  [project_history.md](project_history.md).

**Aufnahme:** Ernten laufen mit RAM-Zwischenablage; 0 Bildverluste in allen
Ernten seit `sc6b`. Das Kopieren auf die SD-Karte dauert inzwischen etwa
435 s. Eine Ernte braucht etwa 3,7 GB `MemAvailable`. Parallel laufende
Importe oder Tests können zur Ablehnung vor dem Start führen. Dabei geht
nichts verloren.

**SD-Karte:** knapp.
* Das Codex-Leck (`~/.codex/.tmp/marketplaces/.staging`, etwa 1 GB/h)
  füllt sie, solange Codex läuft.
* Volle tar-Sicherungen je Aufstellung liegen in `~/var-backups`.
* `var/` hat keine Sicherung auf einem anderen Medium.

**Einrichtungsassistent:** Nacharbeit 1–4 ist seit 2026-10-01 in `master`,
Nacharbeit 5 seit dem Merge am 2026-10-12. Der erste echte Kameralauf mit
seriellem Text richtete `sc7` ohne Hilfe ein: 2j 0,04/0,07 Punktabstände,
unabhängig mit `profile-regrid.py still` bestätigt, Gegenlesen 2/2,
Gesamturteil WARNUNG nur wegen des Bias-Ersatzmaßes. Das Profil wurde nach
Sichtprüfung bestätigt.

**Nacharbeit 5:** Der Versuch davor
(`sc7a`, Kamera leicht von oben) wurde durch schwache Punktschatten in der
Cursorzeile abgelehnt. Die Cursorprüfung verlangt nun eine Kandidatentiefe
von mindestens 60 % des Medians der zugeordneten Glyphenpunkte. Mit dem
gespeicherten Quad bestehen alle 32 `sc7a`-Stillframes offline; ein
synthetisch belegter Cursor bleibt abgelehnt. `propose --quad` auf Frame 16
liefert 2j OK (0,041/0,057) und Gesamt-WARNUNG. Die unveränderte
Startsuche findet auf den Assist-Bildern `sc7` und `sc7a` eine Lage
(196 und 318 zugeordnete Punkte). Das `sc7a`-Startquad liegt bis zu
6,46 px vom Referenzquad entfernt; 2j und Bedienerprüfung bleiben nötig.
Es gab keinen weiteren Kamera- oder seriellen Lauf; ein neuer echter Lauf
mit schräger Aufstellung steht aus. Schräge Aufstellungen wie `ab4`/`ab6`
richtet man weiter von Hand mit `profile-regrid.py still` ein.

## Software und Anleitung

Die Baukapitel 3–9 beschreiben teils noch geplante Komponenten:
folder:// ist registriert, aber FolderSource fehlt; automatische
contour_heuristic-Lokalisierung und RegionTracker aus Kapitel 7 fehlen
(vorhanden sind ManualRoiLocator und QuadTracker). Kapitel 8 ist ein
Bauentwurf: SevenSegmentReader, DotMatrixReader und TesseractReader sind
implementiert, der beschriebene Vergleichsharnisch bleibt offen.
Geräteprofile und die Pipeline-CLI für dispread run fehlen ebenfalls. Der bestehende
dispread-Einsprungpunkt führt zur separaten Workbench-CLI
([Lernpfad](anleitung/README.md), [Roadmap](ROADMAP.md)).
Livevorschau und Datensatz-Sammelmodus haben eigene
[Bedienseiten](anleitung/10-kamera-livevorschau.md) und
[Dokumentation zum Sammeln](anleitung/11-datensatz-sammeln.md).
Die Kameravorschau in der Workbench ist derzeit nur mit `--simulate` nutzbar;
die StreamCam ist dort noch nicht angebunden. Die separate UVC-Bildquelle und
das Kamera-Inbetriebnahmeskript unterstützen die StreamCam bereits.

## Zensical-Dokumentation und Runner

Die [Startseite](../index.md) nennt jetzt die StreamCam und verlinkt
alle Navigationsziele direkt. Die Vertiefungen zu
[Messpfad](uebersicht/messpfad.md),
[Zeitstempeln](uebersicht/zeitstempel.md) und
[Daten/Abnahme](uebersicht/daten-und-abnahme.md) verbinden Anforderungen,
API und Nachweise. Frühere IMX500-Baukapitel und Kameramesswerte sind als
historisch gekennzeichnet; das [Kamerarezept](anleitung/rezepte.md)
verwendet `v4l2://`, die aktiven UVC-Profile stehen in der
[Bildquellen-API](../api/frames.md).

Der Forgejo-Runner nahm am 2026-09-30 um 06:00 einen Auftrag an und
veröffentlichte um 06:04 einen Doku-Commit. Sein rotierender Audit hatte
die Startseite nicht als festen Prüfschritt. Der Audit-Auftrag enthält sie
nun bei jedem Lauf. Ein lokaler Codex-Probelauf mit der installierten CLI
zeigte: Mit --ephemeral scheiterte der Spawn an „no thread with id“;
ohne diesen Schalter wurde ein Kind-Thread angelegt. Das aktualisierte
Startkommando enthält die explizite `docs_reader`-Rollenangabe, nachdem die CLI sie
mit `--ignore-user-config` nicht automatisch geladen hatte. Der lokale
Rollen-Probelauf war erfolgreich. Der Dienst-Runner selbst war bei der
Prüfung aktiv; seine geschützte Anmeldung und
Sessionlogs waren für diese Sitzung nicht lesbar
([Hosting und Pflege](HOSTING.md)).

## Nächste Schritte

1. Den aktuellen Stand von Nacharbeit 5 mit einer Aufstellung leicht von
   oben, wie bei `sc7a`, mit `assist` gegenprüfen.
2. **Anbindung an den Messpfad** (Variante B, TODO.md Punkt 2).
   * Im Worktree `.claude/worktrees/feat-messpfad-live` liegen die
     abgestimmte Spezifikation und ein neuer Implementierungsplan.
     Den uncommitteten Stand prüfen und sichern, dann mit Task 1 beginnen.
   * Meilenstein 1: StreamCam, Browser-Einrichtung, Dot-Matrix-Leser und
     JSONL-Audit in der Werkbank bzw. `dispread serve` verbinden.
   * Serielle Ausgabe an GSVmulti ist ein eigener Folgeschritt;
     das GSV-Protokoll bleibt offen (OQ-07).
3. Die Importprüfung `zellen_inkonsistent` für schrägen Blick verbessern.
   Die Einzelbilder von `ab6-run` dafür behalten.
4. **SD-Karte:**
   * Die Löschung von `vor-ab6.tar`, der Einzelbilder `sc6-run` und der
     Einzelbilder `sc7-run` (etwa 4,8 GB) ist vorgeschlagen; die Freigabe
     durch den Nutzer steht aus.
   * Das Codex-Leck dauerhaft abstellen.
   * `var/` auf ein anderes Medium sichern.
