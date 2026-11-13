# TODO — Stand 2026-11-13 abends

> **KRITISCHER NUTZERAUFTRAG 2026-11-11:** Vor Bridge-/EXE-Features den Workbench-Blocker bearbeiten.
> Einstieg: [/home/me-systeme/picam-ai/docs/WORKBENCH_BLOCKER.md](/home/me-systeme/picam-ai/docs/WORKBENCH_BLOCKER.md).
> Originale, Quellstände, Logs und Regressionen sind im Hauptcheckout gesichert.
> Ziel Freitag 2026-11-13; keine Hardwarefreigabe ohne Beleg.

Diese Datei ist der Wiedereinstieg. Sie soll genug Kontext tragen, dass man
weitermachen kann, **ohne erst zu recherchieren**. Tiefe Begründungen stehen
in den verlinkten Dateien; hier steht, was zu tun ist und warum.

Die verbindliche Einstiegsreihenfolge (`CLAUDE.md`) gilt weiter —
Diese Arbeitsliste kommt zuerst, danach `docs/status.md`.

## Zuerst: Reihenfolge nach der Abnahme vom 13.11.

**Abnahme:** Herr Kaulitz hat am 2026-11-13 die Werkbank und die Ausgabewege (Netzwerk über Brücke, UART über Brücke, UART direkt) offiziell abgenommen (Stand `feat/integration`, Pi-Dienst `5a31b41`, EXE gebaut 14:50 aus `c643f30`). Smoketest: [windows/bridge/SMOKETEST-2026-11-13.md](windows/bridge/SMOKETEST-2026-11-13.md); Prüfbericht: [docs/quellen/ux2-pruefung-2026-11-13](docs/quellen/ux2-pruefung-2026-11-13/ux2-bericht.md).

1. ~~**Fix Rahmenprüfung / Rasterbestimmung**~~ erledigt 13.11. abends (Codex, von Claude reviewt, auf `feat/integration`): Fokusband 0,95–1,05 am Laufstart mit Ablehnung, Raster A1+B1 63/65 statt 58/65 Fits. [Bericht](docs/quellen/rahmen-raster-2026-11-13/REPORT-codex.md). **Offen:** Fokusband am Aufbau kalibrieren (OQ-74); Leonhard prüft am Mittwoch, ob die Ablehnung im Alltag zu oft greift (ein guter Lauf lag bei 1,418).
2. **Überarbeitung der EXE (UI, Claude):** Gestaltungsrunde 3 auf `wip/bruecke-ux3` fertigstellen und nach `feat/integration` mergen, offene Punkte aus dem Prüfbericht (unten), Bildschirmfoto-Tour mit Leonhard.
3. **Installer und TUI:** One-Line-Installer; TUI/CLI, die den Nutzer visuell durch das Setup des picam-Projekts im Terminal führt und von der aus man Status und Logs sieht sowie die Werkbank startet, stoppt, konfiguriert, Fehler sucht und aktualisiert. Ersetzt auch den umständlichen Windows-Testbau (siehe „Auslieferung der Windows-App vereinfachen“ unten).

## Befunde Smoketest 13.11. (offen)

**Vollständiger Prüfbericht (Windows-Prüfung UX2, 13.11.):** `docs/quellen/ux2-pruefung-2026-11-13/ux2-pruefung.zip` mit `ux2-bericht.md` (Zusammenfassung, alle Prüf-IDs, Läufe-Tabelle) und `ux2-bericht-details.md` (chronologisch, Zitate, Messwerte), dazu Bilder, TDMS, Sessions, Protokollexporte. Reports entpackt daneben ([ux2-bericht.md](docs/quellen/ux2-pruefung-2026-11-13/ux2-bericht.md)). Top 5 laut Bericht:
1. UART über Brücke: `uart_frame_invalid` (Signalqualität), siehe unten.
2. EXE-Einstellungen: Mausrad verstellt Ports, Neuaufbau, Fensterhöhe, Blitzfenster.
3. EXE-Gestaltung: zu viel Text, Flackern.
4. 20–60 % ungültige Takte durch die Nachführung, siehe unten.
5. Bedienfallen zwischen Werkbank und Brücke (Kopplung je Weg, Port-Belegung, Moduswechsel).

Punkte 2 und 3 sind auf `wip/bruecke-ux3` (Gestaltungsrunde 3, mit `feat/integration` zusammengeführt, Windows-Testsuite grün) umgesetzt, aber nicht gemergt und unter Windows **nicht** nachgeprüft. Nächster Schritt: Sichtprüfung nach [windows/bridge/PRUEFUNG-UX3.md](windows/bridge/PRUEFUNG-UX3.md) (Mittwoch 18.11.), Offscreen-Bilder unter `docs/quellen/ux3-tour-2026-11/`; erst danach Merge nach `feat/integration`.

**Wiki:** Vergleich und Erklärung der drei Ausgabewege (Netzwerk über Brücke, UART über Brücke, UART direkt: Strecke, Hardware, Rate, Störverhalten, Rückmeldung, Einrichtung, Abnahmestand) als eigene Wiki-Seite eintragen. Vorlage: [docs/quellen/ausgabewege-vergleich-2026-11-13.md](docs/quellen/ausgabewege-vergleich-2026-11-13.md). Passt zur offenen Idee „UART-Anschluss als Grafik im Wiki“. **Entwurf liegt vor (13.11. abends):** [docs/superpowers/specs/2026-11-13-wiki-ausgabewege-entwurf.md](docs/superpowers/specs/2026-11-13-wiki-ausgabewege-entwurf.md), Einhängen nach dem Merge der Wiki-Session (`feat/wiki-lebendig`).

**Risiko UART über Brücke (13.11. abends, Code-Befund, nicht gemessen):** Die JSON-Zeilen haben keine Prüfsumme. Kippt ein Bit so, dass gültiges JSON bleibt (z. B. eine Ziffer im Wertfeld), schreibt die App einen falschen Wert als gültig an GSVmulti. Empfehlung: bis zur Prüfsumme diesen Weg nicht für Messungen verwenden. Spec-Entwurf mit CRC-32, Wiederholung und Gegentest mit 115 200 Baud: [docs/superpowers/specs/2026-11-13-uart-pruefsumme-design.md](docs/superpowers/specs/2026-11-13-uart-pruefsumme-design.md).

**Entscheidung Leonhard: Freigabetexte nach der Abnahme.** Trotz Abnahme vom 13.11. zeigt die Oberfläche weiter „Testfreigabe – nicht abgenommen, keine Messfreigabe“, und `release_block` („DUT-Ausgabe gesperrt: Windows-Abnahme … fehlt“) sperrt die echte Ausgabe ohne Haken. Ob die Abnahme die Messfreigabe einschließt und welche Texte/Sperren fallen, ist eine Messpfad-Entscheidung; nicht autonom geändert.

Heute nachgeprüft und bestanden: Netzwerk (Empfangstest 600/600, Lauf lückenlos), UART direkt (Kanal 1 hält, Laufstart gibt UART-Empfang frei), „Kanal 1 hält“ auf allen Wegen. C-04 (LAN ziehen ohne Lauf) mit EXE 14:50 bestanden.

- **Nachführung: Zweitdurchgang mit Münzwurf-Bereich (kritisch, Werkbank-Blocker).** Lauf `var/live/live-20261113T111848Z/run-01`: 60 % ungültige Takte, Abschnitte bis 10 s, 2297/7524 Bilder `tracking_lost:rahmen_unstimmig`. Gegenversuch `live-20261113T113119Z/run-01` (Diagnosebilder, Marken):
  - Hand neben dem Display bewegt: bis 41 % Nachführungsverlust je Sekunde.
  - Simulator drehen: höchstens 7 %; Hand ruhig: 0 %.
  - **Ursache laut Recherche (13.11., Fable-Teammate), nicht Licht/Schatten:** Fokuszustand zwischen Einrichtungsbild und Lauf verschieden (Fokus am Laufstart neu gesetzt; Laufbild 140 % bzw. 65 % der Einrichtungsschärfe). Folge: Maßstab 1,0018 gegen die Referenz, der starre Erstdurchgang scheitert in fast jedem Bild; im Zweitdurchgang hat ein schärfeempfindlicher Fasenbereich (Lauf B: Nr. 6) einen festen Versatz von 0,62 px bei Grenze 0,65 px, also Münzwurf. Mit einem Laufbild als Referenz bestehen alle 216 Diagnosebilder den Erstdurchgang. Helligkeitsunterschied abgelehnt/angenommen < 0,5 Graustufen.
  - Belege: `session.json` (`summary.tracking_region_hint`), `run-01/diagnose/images.jsonl`; Bericht [docs/quellen/nachfuehrung-recherche-2026-11-13](docs/quellen/nachfuehrung-recherche-2026-11-13/README.md).
  - Stilllegung von Bereich 6 in Lauf A hat die Schutzprobe zu Recht abgelehnt (sonst 2,19 px falsche Lage möglich).
  - Empfehlung: (1) Fokuszustand von Referenz und Lauf angleichen und sichtbar machen (Schärfeprüfung am Laufstart zweiseitig, heute nur Untergrenze 0,6; Maßstab und Anteil Zweitversuche als Hinweis), 1–2 Tage, keine Messpfadgrenze ändert sich. (2) Schärfeprobe bei der Bereichsauswahl, Bedienhinweis auf maßstabsbereinigte Residuen umstellen, 1–2 Tage plus Neukalibrierung. Nicht: k Ausreißer ausschließen, letztes Quad halten.
  - Vorher nötig: Versuch mit Schärfeverhältnis nahe 100 % und bewegter Hand; Replay der Läufe vom 11.11. auf Maßstab; Messreihe Fokuswert gegen Maßstab.
- **Einrichtung scheitert an der Rasterbestimmung (`keine_startlage`, 13.11. 14:02, `live-20261113T130253Z`; kritisch, Werkbank-Blocker).** Recherche (Fable-Teammate, [Bericht](docs/quellen/raster-recherche-2026-11-13/README.md)): zwei Verfahrensfehler, beide lehnen nur ab, keiner erzeugt einen falschen Fit. (A) Leerzellenregel zählt Randminima am linken Stamm des Nachbarzeichens (Lückenspalte, < 0,3 px vor der Zellgrenze) zur Leerzelle 8 (`dotlattice.py` 407–413); hängt von Schärfe/Subpixellage ab, nicht vom Anzeigewert; 5 von 12 heutigen Standbildern betroffen. (B) nur still.png: eine schräge Hough-Linie durch die Ziffern gibt der Startsuche eine falsche Unterkanten-Neigung (0,0467 statt 0,0015), alle Startlagen ≥ 13 px daneben. Vorschlag: A1 Randabstand ~0,25 Spalten an der Zellgrenze (65 Standbilder: +5 Fits, kein bisheriger Fit wandert > 1 px); B1 Unterkante nur bei Plausibilität bzw. beide Annahmen durchsuchen (pauschal Unterkante = Oberkante bricht zwei Einrichtungen vom 26.10.). Etwa 1 Tag mit Tests; vorher volle Suite mit Entwicklungsdaten, OQ-69-Fehlraster mit A1 allein, 65 Bilder je Änderung getrennt. Ausweg am Aufbau: Einrichtung wiederholen (anderer Anzeigewert oder Hinweisbox hilft laut Recherche nicht).
- **Leser:** 975 Bilder unlesbar (Zellen unlesbar, geringer Segmentabstand) im Lauf 1; eigenes Thema nach der Nachführung.
- **EXE, Altlasten im Zustellprotokoll:** Ein alter `unknown`-Eintrag bleibt für immer stehen; die App kann ihn weder erklären noch auflösen. Seit 53fbbd6 sperrt er das Wiederverbinden nicht mehr.
- **EXE, `details.jsonl`:** Zeit je Zeile und bekannte Codes seit 13.11. drin; offen: Port je Zeile, kumulativ über alle Starts (10 MB), Leerlauf nicht zusammengefasst.
- **UART über Brücke: unlesbare Rahmen belegt (13.11. 15:10).** Export mit neuen Codes: Abbrüche im Lauf sind `uart_frame_invalid`, Neuverbindung nach ~2,5 s, Takt bleibt lückenlos (Auffüllung). Pi-Kernelzähler `ttyAMA0`: fe 232, brk 105, kein Überlauf (seit Boot, nicht je Test getrennt). Ursache Signalqualität, nicht CPU-Last. Vorschlag: Prüfsumme je UART-Zeile plus gezielte Wiederholung statt Neuanmeldung (Protokolleingriff, Review); elektrisch: Kabel/Masse prüfen, ggf. niedrigere Rate. Außerdem beim Verbinden dreimal `uart_timeout` (2 s), bevor die Anmeldung klappt: klären, ob der Pi-Empfang noch nicht bereit ist.
- **UART direkt:** Halten belegt (325/325). Nach Abziehen des USB-Adapters am PC schrieb der Pi bis zum Bedienerstopp weiter (er kann es über TX allein nicht merken); GSVmulti muss nach erneutem Einstecken die Messung neu starten (in Anleitung/Checkliste). App: Adapter-Wechsel (fehlt/steckt) ins Journal.
- **UART über Brücke, Empfangstest bricht ab (13.11.: 3/600 um 12:58, 124/600 um 14:35):** Pi-Audit: alle Werte quittiert, danach keine Abfrage; Abbruch 0,17 s nach dem letzten Wert (kein Zeitlimit). Seit 13.11. nennt der Export den UART-Code (`uart_frame_invalid` usw.); bei `uart_frame_invalid` wäre ein Rahmenschutz (Prüfsumme, Wiederholung) oder eine niedrigere Rate zu prüfen. Zähler der App 123 statt 124 (Off-by-one klären). Alt:  Wert 4 ohne Quittung, Neuverbindung mit neuer Lease beendete die Demo. Ursache des gescheiterten UART-Austauschs (Bitfehler bei 460 800? Zeitlimit 2 s?) offen; mit neuer EXE wiederholen, dann zeigt `details.jsonl` den Code. Frage: Soll eine Demo eine Neuverbindung überleben? Werkbank zeigt Abbruch und Grund nicht an (UX).
- **EXE, Bedienung Kopplung/Verbindung (auf `wip/bruecke-ux3` umgesetzt, Sichtprüfung offen):** „Erneut prüfen“ nach Kopplungs-/Verbindungsfehler (heute nur über Portwechsel 6→0→6), Kopplungsstatus je Weg sichtbar, Haken „getrennte Testsession“ merken.
- **EXE, Gestaltung (Runde 3, `wip/bruecke-ux3`), umgesetzt am 13.11. abends, Sichtprüfung offen (PRUEFUNG-UX3.md):**
  - Schritt 5 bei Erfolg neutral („600 von 600 an COM8 übergeben“).
  - Pair-Check unabhängig von der Reihenfolge der Ports.
  - Strecke als Bild (Brücke → COM4 ⇄ COM5 → GSVmulti).
  - Schritt 4 mit Ordner und „Ordner öffnen“.
  - Kachel-Zweitzeilen kürzen.
  - Journal zeigt Abbruch und Stopp.
  - Warnung, wenn die Session nicht zum Port passt.
  - Puls langsamer.
  - Taktzähler und Format-Hinweis sichtbar.
  - UART direkt: Kachel „Komponenten“ zeigt ein altes Portpaar (COM7 ↔ COM6); dort gehört nur der Adapter hin.
- **Nachprüfen unter Windows:** C-04 (LAN ziehen ohne Lauf, 53fbbd6) und „UART über Brücke“ koppeln (eef2991).

## Danach offen (Brücke)

- **Merge:** `feat/bruecke-ui` nach `master`, erst mit Leonhards OK nach dem Test.
- **UART kompakter kodieren:** Für 10 Hz über UART muss das Protokoll kompakter werden. Das ist ein Eingriff ins Protokoll mit Review.
- **Tracking-Tests:** 15 Tests in `tests/test_frame_tracking.py` (R19b, R19c, R25) schlagen fehl, sobald `var/` vorhanden ist. Das gilt auch auf `master`; ohne `var/` werden sie übersprungen, ihr Fehlschlag blieb deshalb bisher unbemerkt. Ursache klären.
- **Wackelnde Integrationstests:** `windows/bridge/tests/test_app_controller_integration.py` wackelt unter starker CPU-Last.
- **Statuswörter:** Die ergänzten Wörter („Unbekannt“, „Keine Weitergabe“, „nicht verbunden“, „Testfreigabe“) in die Spec §10 übernehmen.
- **Alter Controller (OQ-61):** S1, S2 und S4 sind umgesetzt; S3 und S5–S9 folgen erst nach dem Test. Der Datensatz-Sammelmodus bleibt, weil er für die invertierten GSV-Anzeigen gebraucht wird. Siehe Audit in `.superpowers/sdd/2026-11-06-bruecke-ui/oq61-audit.md`.
- **Abnahmegates:** N1, N2 und N3 auf Windows (Paket, Treiber, Sessionexport) bleiben offen.
- **Auslieferung der Windows-App vereinfachen (Leonhard, 2026-11-11):** Der Testbau ist zu umständlich und hat zu viele Bruchstellen (Branch in Forgejo wählen, ZIP laden und entpacken, Skriptordner suchen, ExecutionPolicy umgehen, 3–4 min Build, EXE suchen). Für Prod soll der Bediener nur noch einen Installer herunterladen. Ziel:
  1. Ein Windows-Runner (Forgejo-Runner auf einem Labor-PC) baut `Setup.exe` bei Tag/Merge und legt sie als Release-Anhang ab.
  2. Die Werkbank bietet im Brücken-Dialog Schritt 1 genau diesen zum Pi-Stand passenden Installer zum Download an.
  3. Die App prüft beim Verbinden die Protokoll-/Versionspassung und sagt, wenn sie veraltet ist.
  - Übergangslösung erledigt (13.11.): `windows/bridge/build-test.cmd` als Doppelklick-Starter (ruft PowerShell mit `-ExecutionPolicy Bypass`, findet Python 3.13 über `py -3.13` und öffnet am Ende den Ausgabeordner). Unter Windows noch nicht gelaufen.
- **Keine aufblitzenden Konsolenfenster in der Windows-App (Leonhard, 2026-11-11):** Läuft die Werkbank nicht, öffnet sich bei jedem Verbindungsversuch (alle paar Sekunden) kurz ein Kommandozeilenfenster. Ursache: `windows/bridge/src/dispread_bridge_app/devices.py` `_execute()` startet für die PnP-Inventur `powershell.exe` per `subprocess.run` ohne `creationflags=subprocess.CREATE_NO_WINDOW`, und das bei jedem Versuch.
  - Fix: Flag setzen (Backend, Codex).
  - Inventur nicht bei jedem Wiederholversuch neu abfragen.
  - Test, dass jeder Subprozess der App ohne Fenster startet.
  - Gehört zum späteren Design-Polish der EXE: Leonhard will das evtl. an seinem Windows-PC machen, damit die EXE unter echten Bedingungen mit /impeccable geprüft wird.

---

## 2026-11-06: Nutzerentscheidungen und Fahrplan

Leonhard hat am 2026-11-06 festgelegt, was nach dem Werkbank-Redesign
kommt. Arbeitszweig ist `feat/werkbank-redesign` (Plan
[2026-11-04 Werkbank-Redesign](docs/superpowers/plans/2026-11-04-werkbank-redesign.md),
[Spec](docs/superpowers/specs/2026-11-04-werkbank-redesign-design.md)).
In dieser Reihenfolge:

1. **Werkbank-Redesign softwareseitig fertiggestellt (2026-11-06), einschließlich
   GSVmulti-Ausgabewahl in der neuen `/live`-Oberfläche.** Pro Lauf genau ein Weg: Aus | UART
   direkt (P4-3) | UART über Brücke | Netzwerk über Brücke. Backend steht
   (Commit `7bb4898`): „UART direkt“ gibt echte Werte aus, ist aber dauerhaft
   als „Prototyp – nicht am Windows-PC abgenommen, keine Messfreigabe“
   markiert und startet nur nach ausdrücklicher Bestätigung
   (`acknowledge_unaccepted`). Die Brückenwege bleiben bis zur
   Windows-Abnahme strukturell DUT-gesperrt
   ([GSVmulti-Stand](docs/GSVMULTI_PROTOCOL.md#stand-das-format-ist-unbekannt)).
2. **Hardware-Abnahme Aufgabe 13 (T13) mit Leonhard:** echte Einrichtung,
   Lauf ≥ 30 min mit Referenz, Vorschau-fps, übersprungene Bilder mit und
   ohne Seite, CPU-Last, Verbrauch des alten Controllers. Erster Lauf vom
   06.11. dauerte 22:38 min und enthielt absichtliche Bewegungen: keine
   vollständige T13-Abnahme. [Auswertung](docs/quellen/werkbank-t13-2026-11-06.md),
   dauerhafter zweiter Fit und missverständlicher Korrekturhinweis:
   [OQ-63](docs/open-questions.md#oq-63). Nur mit Leonhards
   Freigabe im Chat; Merge nach `master` nur mit seinem ausdrücklichen OK.
3. **Spec Laufablage, Export und Aufbewahrung**
   ([OQ-60](docs/open-questions.md#oq-60)). Vorgaben: immer ein gesetzter
   Standard-Speicherort, überschreibbar (z. B. Logs und Diagnosebilder auf
   SSD/USB); Download aus der Werkbank als txt, csv, json, GSVmulti-Format
   und frei definierbar; Aufzeichnungsoptionen (Diagnosebilder gibt es schon
   beim Laufstart). Zu klären: wird jeder Lauf gespeichert, wie läuft der
   lokale Speicher nicht langsam voll (Produktion: 64-GB-SD ohne SSD), wie
   finden unerfahrene Nutzer ihre Daten und löschen sie. Laufende nach nicht
   korrigierbarer Verschiebung: **„Neu einrichten“** verwirft die bisherige
   Aufzeichnung, **„Lauf stoppen“** behält sie zum Speichern, Export und
   Ansehen. Heute bietet der Dialog „Anzeige hat sich bewegt“ Weiter
   beobachten · Lauf stoppen · Neu einrichten, und „Neu einrichten“ lässt die
   Dateien liegen; das Verwerfen kommt erst mit der Speicherverwaltung.
   Grundlage: Platzprüfung und `dispread live aufraeumen` (R13-16).
4. **Spec Nachberechnungsmodus plus Messungen**
   ([OQ-59](docs/open-questions.md#oq-59)). Machbar als begrenzter
   Lückenschluss: RAM-Ringpuffer (10–30 s) eines Ausschnitts um das
   bestätigte Quad, bei Trackingverlust sichern und weiter aufzeichnen,
   nach Neueinrichtung nachlesen. Vollbild dauerhaft scheidet aus (JPEG
   25–40 GB/h, kein H.264-Hardware-Encoder am Pi 5). Vor der Entscheidung
   messen: CPU und übersprungene Bilder mit Ringpuffer, Bytes/h, gleiche
   Leseergebnisse auf gespeicherten Bildern, wie oft die Anzeige aus dem
   Ausschnitt rutscht. Nachberechnete Werte nie live an GSVmulti, Herkunft
   im Audit; ein Herkunftsfeld im `ValueRecord` bräuchte eine
   Konzeptänderung (§8, neun Felder).
5. **Bessere automatische Korrektur** bei Kamerastoß und Anzeigeverschiebung
   (später). Heute: Grobverschiebung plus begrenzte ECC-Nachregistrierung
   („Korrektur läuft“). Ziel: ein wichtiger Lauf geht nicht verloren und muss
   nicht wiederholt werden ([OQ-26](docs/open-questions.md#oq-26)).
6. **Alten Controller und alte Startseite entfernen** (OP-2 der Spec,
   entschieden 2026-11-06), sobald die neue Werkbank produktionsreif ist.
   Vorher Bestandsaufnahme, was nur dort lebt (Datensatz-Sammelmodus,
   Profilbearbeitung, Terminals, Anmeldung …;
   [OQ-61](docs/open-questions.md#oq-61)).
7. **Fahrplan danach** ([Roadmap P9](docs/ROADMAP.md#p9-betrieb-und-ausbau)),
   sobald neue Werkbank und GSVmulti-Anbindung fertig sind:
   1. Codebasis polieren.
   2. Wiki polieren (Doku und Zensical-Seite).
   3. TUI für Einrichtung, Verwaltung, Konfiguration und Fehlersuche; soll
      möglichst viel abdecken und wird entsprechend umfangreich.
   4. Test auf frisch installiertem bzw. neuem Pi: Einrichtung,
      Konfiguration und Betrieb laufen glatt. Einrichtung sehr
      benutzerfreundlich, am besten ein Befehl, der alles installiert
      ([OQ-49](docs/open-questions.md#oq-49)).
   5. Produktionsabnahme, eventuell durch Abteilungsleiter Holger Kabelitz.
   6. Danach Anlernen eines neuen Sensors: GSV-2TSD-DI.

**Windows-Einrichtung der GSVmulti-Brücke vereinfachen** (Nutzervorgabe
2026-11-06, nun zur Umsetzung freigegeben; [OQ-62](docs/open-questions.md#oq-62)): Die Wahl einer
GSVmulti-Ausgabe in der Werkbank führt zu einer passenden Verbindungsanleitung.
Bevorzugt lädt die Person eine fertige Windows-EXE herunter, die benötigte
Komponenten installiert und einrichtet. Eine einfache GUI bietet UART oder
Netzwerk an, erkennt Geräte/Ports und zeigt verständlich „bereit“ oder die
konkrete fehlende Aktion, etwa „USB-Adapter anschließen“. Als mögliche
Alternative ein einziger Befehl zum Herunterladen und Ausführen eines
Einrichtungsskripts. Werkbank oder EXE erzeugt möglichst eine passende
GSVmulti-Sessiondatei zum Öffnen/Importieren in GSVmulti. Normale Benutzer
sollen Python-Umgebung, COM-Paar und Portzuordnung nicht selbst zusammensetzen.
Die EXE muss ohne vorinstalliertes Python und neben alten Installationen
(z. B. Visual-Studio-Python 3.7) funktionieren; sie darf nicht zufällig den
Systeminterpreter wählen. Eine Skriptalternative prüft die Version vorab und
richtet automatisch eine geeignete isolierte Laufzeit ein. Bestehende
Python-/Visual-Studio-Installationen erhalten. Frisch-PC-Tests decken sowohl
„kein Python“ als auch „nur Python 3.7“ ab.
Netzerkennung und überprüfte Kopplung mehrerer Pi sowie Verhalten bei
Netzwechseln in [OQ-64](docs/open-questions.md#oq-64) klären. Nutzer erlaubt
Downloads während der Ersteinrichtung; Offline-Installationspaket derzeit
keine Pflicht. Architektur und [Spezifikation](docs/superpowers/specs/2026-11-06-windows-bruecke-design.md)
sind am 06.11. freigegeben: bestehender Python-Kern + Qt-GUI + Windows-Installer.
[Umsetzungsplan](docs/superpowers/plans/2026-11-06-windows-bruecke.md) mit drei
Teilplänen und zwölf Aufgaben liegt vor. Nachweise vor GUI-Ausbau;
Ausführung durch Codex mit Subagents freigegeben; EXE-GUI und sichtbare
Workbench-Anbindung bleiben Claude vorbehalten.
Sessionformat und unterstützte GSVmulti-Versionen vorher nachweisen
([OQ-53](docs/open-questions.md#oq-53)); Installation und einfacher Verbindungsstatus
ersetzen keine Messfreigabe oder Empfänger-Abnahme. Umsetzung nach den
laufenden Abnahmearbeiten spezifizieren; heute nur Anforderung erfasst.

---

## Stand 2026-09-30 nachmittags: Abnahme 3 bestanden

Der Dot-Matrix-Leser, Stufe 2 `templates-stufe2c-2026-09-30.json`
(`6f20dec4…`), hat Abnahme 3 über die neuen Aufstellungen `ab5` (frontal,
gedreht) und `ab6` (schräg von links) **bestanden**:
* 215/215 Proben richtig, 0 falsch, 0 abgelehnt,
* Obergrenze der Fehlerrate 3,5 % (85 Plateaus).

Details und Einschränkungen: VALIDATION.md 2026-09-30.

**2026-10-01:** Der Einrichtungsassistent ist gemergt und lief bei `sc7`
(frontal, nah) im ersten echten Kameralauf ohne Hilfe durch.
* `stufe2c` liest `sc7` mit 111/111 richtig, 0 falsch, 0 abgelehnt.
* Das ist kein formaler Abnahme-Lauf (VALIDATION.md 2026-10-01).
* Der erste Versuch `sc7a` (von oben) scheiterte an zwei falschen
  Ablehnungen. Nacharbeit 5 behebt sie und ist seit 2026-10-12 in
  `master`.

Offen:
1. **Einrichtungsassistent:** am 2026-10-01 gemergt; der erste echte
   Kameralauf (`sc7`) bestand. **Nacharbeit 5** ist am
   2026-10-12 nach `master` gemergt (offline geprüft): `sc7a`
   findet eine Startlage, schwache Punktschatten zählen nicht mehr als
   Cursor. Offen: eine Aufstellung leicht von oben
   mit `assist` gegenprüfen. Schräge Aufstellungen (wie `ab4`/`ab6`)
   lehnt `assist` noch ab (`startlage_mehrdeutig`/`keine_startlage`), die
   richtet man weiter von Hand mit `profile-regrid.py still` ein.
   Spätere Kleinigkeiten N1–N3 stehen im Plan unter Nacharbeit 4.
2. **Anbindung an den Messpfad** (Variante B): gebaut und am 2026-10-21 am
   Aufbau gelaufen (StreamCam über `CameraOwner`, Einrichtung, Bestätigung
   und Lauf auf `/live`, JSONL-Audit je Lauf, optionale serielle Referenz).
   Stand und nächste Schritte unter „Messpfad live (aktiv)“ unten; Zahlen
   in [VALIDATION](docs/VALIDATION.md#messpfad-live-langlauf-2026-10-21).
   Kein formaler Abnahme-Lauf. Weiter offen:
   * **Folgeschritte:** serielle Ausgabe an GSVmulti (OQ-07), alten
     7-Segment-Lesepfad samt ungenutzter Geometriehelfer entfernen und
     dessen CPU-Last im Messlauf erfassen. Der Werteplan-Lauf vom
     2026-10-21 zeigt nun Trackingverlust bei großen Wertwechseln (R13,
     [OQ-26](docs/open-questions.md#oq-26)); Abschlussdiagnose und eine
     vom Zifferninhalt unabhängige Trackerregion sind damit zu bearbeiten.
   * **Gebaut R13-16:** Live-Audits ohne Generationenrotation je Lauf;
     Platzprüfung und manuelles Aufräumen mit Vorschau (Kapitel 10).
     SD-Dauerbetrieb und Platzplanung vor längeren Läufen praktisch prüfen.
   * **Zurückgestellte Bedienpunkte:** Vorschau kann auf dem letzten Bild
     einfrieren; Streamstillstand beendet erst nach OpenCV-Select-Timeout
     (etwa 10–20 s) statt 2 s. Kamera-Neuverbindung nach Einrichtung behält
     Setup-Regler; Laufstopp lässt die Kamera für Vorschau an. Ein
     `tracking_lost`-Hinweis kann den Endfehler auf der Seite verdecken
     (in `session.json` erhalten). Bei tatsächlich hängendem Leser kann
     Laufstopp blockieren; dann Serverneustart nötig. Kamerastatus kann
     nach einem fehlgeschlagenen Neustart noch alte Quelldaten zeigen.
     Fehler beim Schreiben von `confirmation.json` lassen den Vorschlag
     zur erneuten Bestätigung stehen; diese Rückmeldung verbessern.
   * Freigabe bleibt auf GSV-2AS / Displaytech 161A, Raumlicht und mV/V
     begrenzt. `raw_text` enthält die geparste Zahl, nicht 16 Zellen.
     `serve` hält die StreamCam bis zum Serverende (Harvest meldet „belegt“).
3. **Import bei schrägem Blick:** `zellen_inkonsistent` verwirft viel
   (`ab6` 42 %). Die Importprüfung vergleicht über alle Positionen hinweg.
   Prüfen, ob ein Vergleich je Position oder Halbzeile die Ausbeute hebt,
   ohne falsche Labels durchzulassen.
4. **Punktraster-Anpassung `latfit.py`:** lag bei jeder neuen Aufstellung
   0,2–0,4 Punktspalten daneben, `profile-regrid.py still` korrigiert das.
   Der Einrichtungsassistent (seit 2026-10-01 gemergt) prüft das mit 2j.
5. **Andere Lichtquelle** und weitere Geräte bzw. Einheiten sind nicht
   geprüft.
6. `auf3`: Das korrigierte Profil ist nicht bestätigt, niedrige Priorität.
7. **SD-Karte:** Das Codex-Leck in `~/.codex/.tmp/marketplaces/.staging`
   (etwa 200 MB alle 15 min, dazu I/O-Stillstände) ist seit 2026-10-21
   abgestellt: Ursache war der Block `[marketplaces.repowise]` in
   `~/.codex/config.toml` (entfernt, Sicherung `config.toml.bak-2026-10-21`).
   Tauchen wieder Kopien auf, prüfen, ob der Block zurück ist. `var/` hat
   weiterhin keine Sicherung auf einem anderen Medium.
8. Die Einzelbilder von `ab5-run`/`ab6-run` (je 1,6 GB) erst nach Rückfrage
   löschen.
9. **Projekt-Tour** (Doku): seit 2026-10-12 alle sechs Kapitel fertig.
   Pflege: Ändert sich gezeigtes Verhalten, Text und Szene
   (`docs-site/assets/tour*.js`) zusammen anpassen (AGENTS.md).
   Seit 2026-10-13 stehen 21 Szenen auch als Abbildung in Doku-Seiten:
   Verträge, Messpfad, Zeitstempel, Daten und Abnahme sowie die
   Anleitungskapitel 01, 02, 04, 07, 08 und 10. Das Glossar bleibt ohne,
   weil seine Einträge als kurze Vorschau auf anderen Seiten erscheinen.

---

## Erledigt 2026-09-30: Abnahme 2 abgeschlossen (`ab4` geerntet, einmal ausgewertet)

Stand 2026-09-29 abends: Stufe 2 ist mit `bg_closing_v1` eingefroren
(Vorlagen `var/dotmatrix/templates-stufe2b-2026-09-29.json`, sha256
`fc3b44bdc880372a600168218560a3926fa307fe533b2592f7c4c244a89aa75e`).
`ab3` (frontal, nah) ist geerntet und importiert und steht in der
Profilzuordnung. **`ab4` fehlt.**

1. **`ab4` aufbauen:** Kamera schräg von rechts (30–40° seitlich, leicht von
   oben), anderes Licht als `ab3` (z. B. Lampe seitlich oder Decke aus). Nichts
   Helles hinter der Kamera, Anzeige mittig, grüner Rand neben dem Text frei,
   normal scharf.
2. **Einrichten wie `ab3`**, Ablauf in VALIDATION.md:
   * `harvest-setup.py focus` erst ohne, dann mit `--hint-box`,
   * Standbild 3 s PNG (`sync-record.py … --duration 3`),
   * Punktraster mit 4 Stützpunkten: `python var/diagnostics/latfit.py
     FRAME OUT.json x,y:spalte,zeile …` (Punktmitten, Spalte 0–95 über alle
     Zellen, Zeile 0–6). Wird mit dem Einrichtungsassistenten überflüssig.
     **Danach prüfen:** Leerzellen 8/13–15 ohne zugeordnete Punkte. Ein
     kleiner Restfehler allein beweist nichts (Befund `sc6`).
   * `propose --grid 0,25,17.78,160`,
   * Leerzellen 8/13–15 leer? Rand frei? Stabilität?
   * **Keinen Lesertest** (Abnahme-Aufstellung).
   * Bestätigen mit `--confirmed-by "Leonhard Hentschke"`.
3. **Ernten:** `touch var/RECORDING_IN_PROGRESS`, dann
   `harvest.py --profile var/diagnostics/ab4-profile --out-dir var/diagnostics/ab4-run --n-steps 30 --hold-s 6 --seed 2026093001`,
   danach `rm var/RECORDING_IN_PROGRESS`. Vorher `grep MemAvailable
   /proc/meminfo` (≥ 3,6 GB).
4. **Sichern und importieren:** tar nach `var-backups`, dann
   `import-harvest.py --harvest var/diagnostics/ab4-run --profile var/diagnostics/ab4-profile --dataset-root var/workbench/datasets`,
   `ab4` mit sha256 in `var/diagnostics/dotmatrix-profile-map.json`
   eintragen (Vorstand sichern als `.vN.json`).
5. **Einmal auswerten:**
   `dotmatrix-eval.py abnahme --dataset-root var/workbench/datasets --profile-map var/diagnostics/dotmatrix-profile-map.json --templates var/dotmatrix/templates-stufe2b-2026-09-29.json --templates-sha256 fc3b44bdc880372a600168218560a3926fa307fe533b2592f7c4c244a89aa75e --groups ab3,ab4 --out var/dotmatrix/abnahme-stufe2b-<datum>.json`.
   Bestanden bei 0 falsch und ≤ 20 % abgelehnt. **Keine Nachbesserung an
   `ab3`/`ab4`**, bei Nichtbestehen gehen sie ins Training.
6. Einzelbilder von `ab3-run` (und `ab4-run`) erst nach Rückfrage löschen.
7. Nach Import und Abnahme die Fortschrittsseite aktualisieren:
   `./.venv/bin/python scripts/docs-progress-data.py`, dann
   `docs-site/assets/data/fortschritt.json` mitcommitten
   ([FORTSCHRITT.md](docs/FORTSCHRITT.md)).

Der [Plan Einrichtungsassistent](docs/superpowers/plans/2026-09-29-einrichtungsassistent.md)
ist mit dem Merge am 2026-10-01 abgeschlossen.

---

## Verlauf 2026-09-28/29 (erledigt, zum Nachlesen)


Stand: Kamerawechsel fertig und nach `master` gemergt. Aufstellung `sc3`
(Kamera fest auf dem Tisch) ist geerntet und importiert: 46 Proben, ROM-
Gegenprobe je Zeichen 0 Abweichungen. Dot-Matrix 942 Proben in 9
Gruppen (`sc6` 219 mit `sc6b`, `ernte1` 152, `sc5` 114, `ab1` 99, `ab2` 83, `sc4` 79, `auf2` 76, `auf3` 73, `sc3` 47 mit Profil `sc3b`). Die Aufnahmen `sc1`/`sc2`
waren durch Kamerabewegung verschoben und sind verworfen (VALIDATION.md
2026-09-28/29).

1. ~~Kalibrieraufnahme C~~ erledigt am 2026-09-29. Die neue
   `var/calibration/timing-streamcam.json` hat M = 325,9 ms und einen
   Anzeigeversatz von 89,6 ms, aus `sc3-cal-a/b/c` (VALIDATION.md
   2026-09-28/29). Die alte Datei (M = 1225,8 ms) liegt daneben als
   `.v-sc1-20260928.json`.
2. Optional `gate-label` für `sc3-run` mit dem neuen M neu laufen lassen und
   neu importieren. Das bringt mehr Ausbeute. Die jetzigen Labels (mit altem,
   größerem M) bleiben gültig.
3. ~~Zweite feste Aufstellung~~ `sc4` erledigt am 2026-09-29 (79 Proben, 0
   Abweichungen vom ROM). ~~OQ-42~~ ist entschieden (`--train-eligibility
   rom_per_group`), `loo` ist gelaufen. Ergebnis: nie ein falscher Wert,
   `sc4` 79/79 richtig, `ernte1` 91/152, `sc3` 0/46 (Zellen 5–7 über d_max),
   `auf2`/`auf3` alle abgelehnt (VALIDATION.md 2026-09-29).
4. `sc5` erledigt am 2026-09-29 (114 Proben, ROM 0), `sc3` mit korrigiertem
   Profil `sc3b` neu importiert (47). `loo` (c): nie falsch, `sc4` 79/79,
   `sc5` 114/114, `ernte1` 133/152, `sc3` 0/47 (VALIDATION.md 2026-09-29).
5. ~~Kontrastgefälle `sc3`~~: Normierung `ink_per_cell_v1` (Commits
   `021f8ab`, `8908fe4` nach Review). `loo` (e): nie falsch, `ernte1` 152/152, `sc3` 47/47, `sc4`
   79/79, `sc5` 114/114, `auf3` 61/73 (Rest mehrdeutig), `auf2` abgelehnt
   (VALIDATION.md 2026-09-29).
6. ~~Stufe 2 einfrieren~~ erledigt am 2026-09-29 (Code `47b8902`, Vorlagen
   sha256 `4524d6a1…`, VALIDATION.md „Stufe 2 eingefroren“).
7. ~~Abnahme `ab1`/`ab2`~~ am 2026-09-29: **nicht bestanden**, 0 falsch.
   `ab1` 99/99 richtig, `ab2` 0/83 (alle Ablehnungen in Zelle 8: Kante
   einer Glasspiegelung läuft durch die Leerzelle), gesamt 45,6 % abgelehnt
   (VALIDATION.md). `ab1`/`ab2` gehen ins Training.
8. ~~Entwicklungsrunde Spiegelkante~~ erledigt am 2026-09-29: Normierung
   `bg_closing_v1` (Commit `50d68d6`), Hintergrund je Punkt per
   Grauwert-Schließung. `loo` mit 942 Proben: 0 falsch, `ab2` 83/83, alle
   scharfen Gruppen vollständig richtig. `auf2` (unscharf) wird jetzt
   vollständig abgelehnt (vorher 63/76), VALIDATION.md.
   Stufe 2 neu eingefroren (Vorlagen `templates-stufe2b-2026-09-29.json`,
   sha256 `fc3b44bd…`, VALIDATION.md). **Nächster Schritt:** zwei **neue**
   Abnahme-Aufstellungen ernten (`ab3`, `ab4`), dann einmal `abnahme`.
9. ~~Einzelbilder `ab1-run`/`ab2-run`~~ gelöscht am 2026-09-29 (Nutzer-OK).
10. **Einrichtungsassistent** baut Codex parallel nach
    [Plan](docs/superpowers/plans/2026-09-29-einrichtungsassistent.md) im
    Worktree `/home/me-systeme/picam-ai-assist`, Branch
    `feat/einrichtungsassistent`, ohne Kamerazugriff und ohne in `var/` zu
    schreiben. Während jeder Aufnahme liegt
    `var/RECORDING_IN_PROGRESS` (von Claude angelegt und entfernt), dann
    lässt Codex die volle Testsuite ruhen. Claude reviewt und merged.
11. `sc6` erledigt am 2026-09-29 (88 Proben, ROM 0, Stufe 2 liest 88/88).
    `loo` mit 9 Gruppen: 0 falsch in 811 Proben, alle scharfen Gruppen
    vollständig richtig, `ab2` weiter 0/83 (VALIDATION.md „Aufstellung
    `sc6`“). Weitere Trainingsaufstellungen sind möglich, der Engpass
    bleibt aber Punkt 8.

Offene Befunde:
* **SD-Karte:** Eine Aufnahme mit 15 fps belegt 1,3–1,8 GB. Vor jeder
  Sitzung `df -h /` prüfen; alte Einzelbilder nach dem Import löschen oder
  auslagern. Keine Schreiblast (git worktree, Tests, tar) während Aufnahmen.
* **Verworfene Bilder (analysiert 2026-09-29):** Ursache sind Schreibhänger
  der SD-Karte (in `sc6` 14 Stillstände > 0,5 s, bis ~42 s; auch 200-Byte-
  Zeilen in `commands.jsonl` hingen 12–23 s), nicht die Kodierung (JPEG q95
  13 ms/Bild, GIL frei). Karte 7,1 MB/s mit fsync gegen 5,9 MB/s Bedarf.
  Nebenwirkung: `_log_event` im seriellen Thread verlängert GSV-Sendepausen
  → lange `telegrammluecke`. Vorschlag: (A) Aufnahme nach `/dev/shm`, danach
  kopieren; (C) `_log_event` über Writer-Queue; optional (B) Ernte mit 5 fps.
  Mitursache vermutlich Codex: 31 liegen gebliebene Kopien des
  repowise-Marketplace (je ~185 MB) in `~/.codex/.tmp/marketplaces/.staging`,
  am 2026-09-29 gelöscht (dazu Caches, 14 GB frei). Karte ist No-Name
  (`SD16G`, meldet 50 GiB) → Kapazität unklar, `var/` dringend auf ein
  anderes Medium sichern. Danach `sudo fstrim -v /`.
  **Umgesetzt 2026-09-29:** (A) `sync-record.py --staging-root`, von
  `harvest.py` mit `/dev/shm` genutzt, und (C) `commands.jsonl` über einen
  eigenen Schreiber (CHANGELOG). `fstrim` gelaufen, 14 GB frei.
  **Offen:** Probeernte an der Kamera. Prüfen: `frames_dropped_queue_full` = 0,
  weniger `telegrammluecke`, Kopierdauer. Ist der RAM knapp: Ernte mit 5 fps.
* **Glasdetektor (`propose`)** trifft an der StreamCam oft nicht das Glas
  (Blende, Drehung); das Quad kam aus einer Punktgitter-Homographie (Skript-
  Schnipsel im Sitzungsverlauf). Werkzeug dafür in `harvest-setup` einbauen,
  dazu ein Overlay der Abtastpunkte und eine Prüfung der 8-Zeilen-Konvention.
* **M-9 bestätigt:** Fokus-Sweep misst nach großen Sprüngen ein veraltetes
  Pufferbild; Nachmessung (1 s warten, 10 Bilder verwerfen) war jedes Mal
  nötig. Fix in `focus_sweep`.
* M-10 (eingefrorene Belichtung bei anderem Licht) ist ungeprüft.

Zurückgestellt: Werkbank-Kamera an die StreamCam anbinden (heute außer
Betrieb), Replay verliert die Zeitbasis (M-6).

## Sicherung für `var/` einrichten

`var/` gibt es nur einmal (gitignored, Worktree per Symlink). Nach der
Löschung vom 2026-09-25 ist wiederhergestellt, was ging (alle 389 Proben,
Profile, `devices.json`, Rückstellpunkt; `var/rescue-20260925/NOTES.md`).
Verloren: Einzelbilder der Ernte-Aufnahmen, die meisten Diagnosebilder.
`/home/me-systeme/picam-ai/.var_recovered` ist ausgewertet und kann weg.
Lokale Sicherungen (gleiche SD-Karte, nur gegen versehentliches Löschen):
`/home/me-systeme/var-backups/var-20260929-vor-sc3.tar` (Datensatz 389,
Profile, Kalibrierung) und `var-20260928-vor-import.tar`. Zu tun: regelmäßige Sicherung von mindestens
`var/workbench/datasets`, `var/diagnostics/*-profile*`, `var/calibration`
auf ein **anderes Medium**.

---

## Hintergrund Dot-Matrix-Leser

Leser fertig und geprüft (`rom_check_v2`, `auf3` neu bestätigt). Die vorab
festgelegte Messung brach bisher im Durchgang „nur weiche Aufstellungen im
Training" an der Gegenprobe ab; nie ein falscher Wert (VALIDATION.md
2026-09-25, OQ-42). Seit 2026-09-28 gibt es zwei scharfe StreamCam-
Aufstellungen dazu, siehe oben.

---

## Historisch (IMX500 außer Betrieb): Streamstarts sparen (OQ-22)

Am 2026-09-24 blockierte die Brücke beim 8. Start eines Boots; nach Neustart
liefen zwei Starts fehlerfrei. Jede Sitzung so planen, dass sie mit wenigen
Starts auskommt: Kamera nicht verstellen, ScalerCrop aus **einem** Vollbild,
Ernte direkt anschliessen.

---

## Wo wir standen (2026-09-25)

Dieser Abschnitt hält den früheren Übergang zur StreamCam fest. Der
aktuelle Stand folgt unter „Messpfad live“; die StreamCam-Kalibrierung
vom 2026-09-29 ist inzwischen dokumentiert.

* Sollwertkanal (RS232 ASCII vom GSV-2AS) steht seit 2026-09-22.
* Kamera seit 2026-09-25: Logitech StreamCam (IMX500 außer Betrieb).
  Aufnahme, Profil v3, Fokus per Software und Pflicht-Kalibrierung sind
  gebaut und an der Hardware geprüft.
* Task B (Versatz Telegramm ↔ Glas) hatte mit der IMX500 δ zwischen +80 und
  +116 ms und M 499–695 ms. Für die StreamCam wird beides neu gemessen.
* Führende Null (OQ-41) und SD-Schreibstau (OQ-40) sind behandelt; die
  endgültigen Gap-Schwellen bleiben offen, blockieren die erste Ernte aber
  nicht.

Details: [docs/status.md](docs/status.md), alle Zahlen in
[docs/VALIDATION.md](docs/VALIDATION.md) (2026-09-23), Herleitung in
[docs/lab_journal.md](docs/lab_journal.md) (letzter Eintrag).

---

## Die Aufgaben, in Reihenfolge

### Windows-Brücke v2 (aktiv, Nutzerfreigabe 2026-11-06)

Backend und testbare Paketierung im isolierten Zweig `codex/windows-bridge-core`
fortführen. [OQ-62](docs/open-questions.md#oq-62),
[OQ-64](docs/open-questions.md#oq-64),
[OQ-65](docs/open-questions.md#oq-65) und
[Umsetzungsplan](docs/superpowers/plans/2026-11-06-windows-bruecke.md) führen
Technik und offene echte Windows-Gates. P1/N1/N2/N3/P2 als technische
Grundlagen geprüft; laufende Schritte und nächste Aufgaben in
[Status](docs/status.md). UI/Anleitung/Bereitschaftsdarstellung für Claude
vorbereiten, keine Veröffentlichung oder DUT-Entsperrung daraus ableiten.

### Messpfad live (aktiv)

**Stand 2026-10-30:** Auf `feat/r13-display-haertung` (nicht in `master`)
sind R13-1 bis R13-23 und der P4-Prototyp gebaut.

* **Langlauf** `live-20261030T082502Z/run-01`: 42,8 min, Werteplan mit
  280 Schritten, **0 / 45 702** Fehllesungen, 100 % VALID in stabilen
  Fenstern, kein Trackingverlust
  ([Laborjournal](docs/lab_journal.md#langlauf-2026-10-30)).
* **Offen für Leonhard:**
  * Merge R13 → `master` anhand der
    [Entscheidungsvorlage](docs/superpowers/plans/2026-10-28-r13-merge-entscheidung.md).
  * Zweite Aufstellung für die Abnahme.
  * GSVmulti-Test am Windows-PC
    ([Anleitung](docs/GSVMULTI_PROTOCOL.md#windows-test)).
  * Belichtungsnachregelung (R13-20) am Gerät zeigen; dafür braucht es
    dunkleres Licht.
  * Stillstandserkennung (R13-22) mit echtem Abziehen der Kamera prüfen.
* **Werkbank:** läuft als Unit `dispread-werkbank-r13` aus einem Export
  (`PYTHONPATH`), nicht aus dem Worktree.

**Stand 2026-10-21 abends:** Der Messpfad läuft am Aufbau. Lesesperre,
schwankende Ziffern, Licht-Hinweis/Toleranz, Leser mit ~30 Bildern/s,
TRANSITION bei Wertwechseln und Referenzaufzeichnung sind gebaut und in
`master` (Plan
[2026-10-21 Tempo und Abschluss](docs/superpowers/plans/2026-10-21-messpfad-live-tempo-und-abschluss.md)
erledigt). Drei Läufe mit serieller Referenz, alle **0 Fehllesungen**:
streng 45 s (0/715), Toleranz ×1,8 5,6 min (0/6630), streng 12 min (0/8979,
29,8 Bilder/s, Wechsel im Median nach 232 ms); siehe
[VALIDATION](docs/VALIDATION.md#messpfad-live-langlauf-2026-10-21).

**Nächste Schritte, in Reihenfolge:**

1. **Nachführung bei großen Wertwechseln bearbeiten (R13)**
   — [freigegebener Plan](docs/superpowers/plans/2026-10-21-r13-strukturstabile-nachfuehrung.md),
   **gebaut auf `feat/r13-display-haertung`** (R13-1…R13-18, nicht in
   `master`); Merge entscheidet die Person am 2026-10-28 anhand der
   [Entscheidungsvorlage](docs/superpowers/plans/2026-10-28-r13-merge-entscheidung.md).
   Live 23.10.: 0 Fehllesungen, ruhiger Lauf 99,98 % VALID.
   ([OQ-26](docs/open-questions.md#oq-26)): Strenger Werteplan-Lauf
   `live-20261021T151835Z/run-01` abgeschlossen: 806 s, 0/11 137 Fehllesungen,
   aber 8074 Trackingverluste; bei Faktor 2 und 5 in stabilen
   Referenzfenstern kein VALID. Rückstellung bestätigt. Nachführung
   unabhängig vom Zifferninhalt untersuchen und große Sprünge erneut
   prüfen. Die berichtete Abdeckung ist zeitlich nicht eindeutig
   zuordenbar. [Zahlen](docs/VALIDATION.md#messpfad-live-werteplan-2026-10-21).
   **Befund 2026-10-28** (`live-20261028T110248Z/run-01`, 328 s, 0/6437
   Fehllesungen): um 12:17:51 verschob sich die Anzeige im Bild um 11,8 px
   (dx +11, dy −4,2) und blieb dort; knapp unter dem Suchradius 12 px
   flackerte die Nachführung zwischen Wiederkehr und `rahmen_unstimmig`
   (Strecken bis 28 s), VALID fiel von 83 % auf 49 %.
   * **Später (Leonhard, zurückgestellt):** richtiger Hinweis bei dauerhafter
     Verschiebung. Die Werkbank meldete „Rahmen verdeckt“ statt „Anzeige hat
     sich bewegt – neu einrichten“ (`tracking_hints.max_shift_px` blieb
     leer). Verschiebung grob über den ganzen Rahmen schätzen (z. B.
     Phasenkorrelation mit ausgeblendetem LCD-Inhalt) und den Hinweis danach
     wählen.
   * **In Arbeit:** automatische Nachführung über größere Bewegungen
     (Grobschätzung der Gesamtverschiebung, dann unveränderte Feinprüfung).
   * **Später (Leonhard 2026-10-28):** solche Fehler grundsätzlich vermeiden —
     automatische Korrekturen und Rückfallstufen, im Extremfall manuelle
     Belichtung durch die Person. R13-20 ergänzt vorerst Displaybelichtung
     und die warnende Vorprüfung; reale Regelungsabnahme steht aus.
   * **Hinweistext Gegenlesen (klein, später):** Einrichtung
     `live-20261028T133037Z` mit absichtlichem Fleck auf dem Glas: „668“
     (Zellen 5–7) blasser, Kontrasttiefe 0,36 statt 0,63–0,70; Lauf korrekt
     gesperrt, Toleranz korrekt verweigert (`beste_vermutung_widerspricht_referenz`).
     Der Hinweis nennt aber nur „Schatten“; besser „Schatten oder
     Verschmutzung auf dem Glas: reinigen bzw. abschatten“.
   * Raster am rechten Rand leicht versetzt (Zellversatz bis 0,15 Spalten
     in den Einheitszellen, 6 von 157 Punkten im „mV/V“ nicht zugeordnet);
     ohne Einfluss auf den Wert, die Einheit wird nicht gelesen.
2. **~~Testlauf-Sicherung und Zeitbasis-Bezeichnung klären~~ (erledigt 2026-10-23):**
   [OQ-44](docs/open-questions.md#oq-44) ist umgesetzt: Gate-Freigaben werden
   vor dem Test-Audit als `UNREADABLE` ohne `value` unterdrückt;
   [OQ-45](docs/open-questions.md#oq-45) ist erledigt 2026-10-23:
   Ergebniszeiten aus `time.monotonic_ns()` tragen für jede Quelle
   `HOST_MONOTONIC`, Aufnahmezeitbasen bleiben unverändert. BOOTTIME nur
   über `to_boottime_ns` mit Sessionversatz und Suspend-Prüfung;
   alte Auditdateien behalten ihre Labels. Testlaufdaten bleiben für
   Messungen gesperrt.
3. **Toleranzlauf ≥ 10 min mit Werteplan** (siehe unten), mit der
   bedienenden Person; der Werteplan schreibt `set norm` und stellt danach
   zurück. Danach entscheiden, ob die Toleranz als validiert gilt (für
   diese Aufstellung).
4. **Serielle Ausgabe an GSVmulti** ([OQ-07](docs/open-questions.md#oq-07)):
   **2026-11-04:** Software-Prototyp mit UserDefined-Formatter,
   TCP-/UART-Brücke gebaut; echte DUT-Ausgabe über die Brücke gesperrt.

   - [ ] Ausgabewahl (Aus | UART direkt | UART über Brücke | Netzwerk über Brücke) in der neuen /live-Oberfläche — in Arbeit (Werkbank-Redesign G2)

   **2026-11-06 (Nutzerentscheidung):** „UART direkt“ gibt weiter echte
   Werte aus, ist aber dauerhaft als „Prototyp – nicht am Windows-PC
   abgenommen, keine Messfreigabe“ markiert und startet nur nach
   ausdrücklicher Bestätigung (`acknowledge_unaccepted`). Brückenwege bleiben
   bis zur Windows-Abnahme strukturell DUT-gesperrt.

   Direkte UART-Demowerte unter Windows 11/GSVmulti 2.03 Pro gespeichert:
   Rampen und acht Sprünge korrekt, Timeout und Fortsetzung belegt.
   Ungültige Zeiträume fehlen aber im Export, auch bei NaN und bestätigtem
   Replace Missing Values ([OQ-06](docs/open-questions.md#oq-06),
   [OQ-50](docs/open-questions.md#oq-50), [OQ-51](docs/open-questions.md#oq-51)).
   Reproduktionsfall mit GSVmulti-Entwicklung klären; Belegpaket lokal vorhanden,
   kein Kontakt versandt. Lauf 11 belegt 510 korrekte Zahlen, mV/V und
   Skalierung 1 in TDMS sowie Unit=mV/V in gespeicherter Session; TXT ohne
   eigene Einheit. Gültiges Zahlenprofil der 2.03-Pro-Konfiguration geklärt
   ([OQ-01](docs/open-questions.md#oq-01)). Als Nächstes getrennt
   Altwert-/Puffernachlauf und Port-/Prozesswiederanlauf prüfen. Lauf 12:
   Wiederöffnen nach Close scheitert mit 805306614; zuerst Portbelegung gegen
   DLL-Zustand trennen ([OQ-52](docs/open-questions.md#oq-52)). Filter-aus-
   Vergleich 14 mit abgeglichener10Hz/mV/V-Session bleibt auf Timeout;
   positive Gegenprobe15 liest gültige Zahlen wieder. A-Präfix ohne Filter
   bleibt in16 durchgehend auf Timeout ([OQ-53](docs/open-questions.md#oq-53)).
   Geladene Windows-GSV-Versionen erfasst, OQ-54 geklärt
   ([Inventar](docs/GSVMULTI_PROTOCOL.md#geladene-gsv-bibliotheken)).
   LogLevel2 wirksam: Close-/Open-Fehler zweimal protokolliert; initial
   zusätzlich Clear-Buffer-Fehler. Gegenprobe über Add Channel reproduziert
   beide Signaturen bei1 statt10 Hz ([OQ-55](docs/open-questions.md#oq-55));
   Zusammenhang offen. Vergleichspaket für direkten Entwicklungskontakt
   lokal vorbereitet, kein Versand; OQ-52/OQ-53 bleiben teilweise geklärt.
   Nutzer akzeptiert vollständigen GSVmulti-Neustart als Workaround;
   Fehlerbehebung vorerst zurückgestellt. Nutzer wählt wieder com0com als
   nächsten Weg: Nach angeleitetem Vovsoft-Buildwechsel alle sechs Geräte
   Code0, COM5/COM6 bidirektional geprüft; Hash passt, SecureBoot/HVCI aktiv.
   Lokale Windows-Demo COM5→COM6/GSVmulti mit600/600 exakten Zahlen samt
   mV/V/Scaling1 vollständig gespeichert. Gemeinsamer Pi-TCP-/JSONL-/ACK-
   Demolauf:600/600 Werte exakt in TXT/TDMS, passende ACKs/Payloads und Einheiten
   belegt. Brückenprozess-Wiederanlauf:510/510 geschriebene Werte exakt gespeichert,
   ohne Zwischenhistorie fortgesetzt; Exportpause weiter unmarkiert. Zusatzersatz
   Frame356 unter [OQ-58](docs/open-questions.md#oq-58) isolieren; gemeinsamer UART
   und übrige Abbruch-/Altwertfälle noch prüfen
   ([OQ-47](docs/open-questions.md#oq-47)). Echte DUT-Ausgabe bleibt gesperrt.
   [Arbeitsplan](docs/superpowers/plans/2026-11-04-gsvmulti-anbindung.md),
   [Messbelege](docs/VALIDATION.md#uart-demo-20261104-10).
   `protocol/gsv_ascii` wirft weiterhin absichtlich; Format provisorisch.
   Kein Protokoll erfinden; Messfreigabe erst nach erfüllten Abnahmeschranken.

   **Historischer Planungsstand (2026-10-28 bis 2026-10-30, P4-3 direkt):**
   **2026-10-30:** P4-1 bis P4-3 sind als Prototyp gebaut:
   `UserDefinedFormatter`, Demo-Sender und Opt-in-Ausgabe im Live-Lauf.
   Geprüft ist das nur mit pty; der Windows-Test steht aus
   ([Plan](docs/superpowers/plans/2026-10-29-p4-gsvmulti-userdefined.md)).
   **2026-10-28:** UserDefined laut Herstelleranleitung v2.6 belegt;
   ein Prototyp für die im PDF dokumentierte Windows-Version 2.01 Pro
   kann gebaut werden. [Bewertung und Prüfplan](docs/GSVMULTI_PROTOCOL.md).
   Eigenen einkanaligen `TelegramFormatter` und Transport wählen
   ([OQ-47](docs/open-questions.md#oq-47)); die optionale ZIP-Bridge vor
   Übernahme bei COM-Fehlern und Größen-/Zahlenprüfung korrigieren
   ([Codeprüfung](docs/GSVMULTI_PROTOCOL.md#beispielcode)). Danach in den bisher nur
   JSONL schreibenden Live-Pfad integrieren. Empfang in 2.01 Pro
   ([OQ-01](docs/open-questions.md#oq-01)), sichere Ungültigbehandlung
   ([OQ-06](docs/open-questions.md#oq-06)) und Zeitachse (M8) vor
   Messfreigabe belegen. `protocol/gsv_ascii` wirft weiterhin absichtlich;
   AsciiCsv bleibt provisorisch. Kein Protokoll erfinden.
5. **UI/UX-Überarbeitung der Werkbank** (nicht prod-ready), einschließlich
   schnellerer Vorschau (Seite holt Bild und Status nur alle 0,5 s) und der
   zurückgestellten Bedienpunkte unter „Offen“ Punkt 2.
   Seit 2026-11-04 als Werkbank-Redesign in Arbeit. Folgearbeiten laut
   Entscheidung 2026-11-06 (oben, „Nutzerentscheidungen und Fahrplan“):
   Laufablage/Export ([OQ-60](docs/open-questions.md#oq-60)),
   Nachberechnungsmodus ([OQ-59](docs/open-questions.md#oq-59)), alten
   Controller und alte Startseite nach Bestandsaufnahme entfernen
   ([OQ-61](docs/open-questions.md#oq-61)).
6. **Aufräumen im Messpfad:** alten 7-Segment-Lesepfad entfernen.
   Live-Audit ohne verlustbehaftete Rotation ist seit R13-16 gebaut.
7. **Rest aus Review Task 5** (nicht blockierend): `DEFAULT_RESTORE_POINT`
   wird relativ zum Arbeitsverzeichnis aufgelöst. Das Snippet in Anleitung
   Kapitel 10 liest Port/Baud seit dem Wiki-Abgleich aus dem Rückstellpunkt.

**Speicherbudget für den Betrieb (neu 2026-10-23):** Im Unternehmen läuft das
Werkzeug voraussichtlich auf einem Pi 5 mit 64-GB-SD-Karte, ohne SSD.
Messläufe deshalb weiter auf der SD-Karte testen. **Gebaut R13-16:**
Platzprüfung vor Einrichtung und Laufstart (2 GB Reserve, mit Diagnose
zusätzlich 0,6 GB), Status/Seite mit freiem Platz und Warnung unter 5 GB,
Diagnosebilder standardmäßig aus in Seite und API, vollständige Auditdatei
je Lauf ohne Generationenverlust und opt-in
`dispread live aufraeumen --aelter-als <tage> [--nur-diagnose] [--ausfuehren]`
mit Größen und Vorschau als Vorgabe. Keine automatische Löschung;
Profile/Setup und laufende Läufe bleiben geschützt. Ein 10-min-Lauf braucht
etwa 10 MB Audit, mit Diagnosebildern bis zu 0,6 GB zusätzlich.
**Offen:** längeren Betrieb auf der Produktions-SD praktisch validieren
und benötigte Daten vor manuellem Aufräumen sichern.
Für die Entwicklung kann eine NVMe-SSD (500 GB, vorhanden) Aufnahmen,
Datensätze und die fehlende `var/`-Sicherung aufnehmen, aber nicht die
Messläufe selbst.

**Pi-Betrieb (für ruhige Messläufe):**

* Die Forgejo-CI läuft auf demselben Pi. Jeder Push nach `master` startet
  Build und Playwright mit headless Chrome; am 2026-10-21 16:13–16:22 gab
  das 20–44 s Stillstand, SSH-Abbrüche, kurzes STALE auf `/live` und zwei
  Playwright-Zeitüberschreitungen (lokal danach 29/29 grün). **Nicht während
  eines Messlaufs nach `master` pushen.** Mittelfristig CI auf einen anderen
  Rechner oder während Läufen pausieren (Entscheidung der Person).
* Nächtlicher Lauf `maintain`: scheiterte 2026-10-19 bis 2026-10-21 früh,
  seit 2026-10-21 15:12 wieder grün (22. und 23.10. erfolgreich, letzter
  Codex-Lauf ohne Befund, Doku-Build ok; `sudo picam-codex-logs`). Ursache der
  drei Fehlschläge nicht mehr nachvollziehbar (keine Schritt-Logs per Token).
* Playwright-CI für `master` `109d360` (Roadmap-Karte, 2026-10-23) fehlgeschlagen,
  Build ok. Laut Wiki-Sitzung wahrscheinlich Last (Roadmap-Rad- und
  Tour-Abbildungstests wackeln unter Last); ihr Branch `feat/wiki-geruest`
  ersetzt Roadmap-Code und -Tests, daher nicht separat angefasst.
* Kein persistentes Journal; der Hänger 2026-10-21 14:08 ist deshalb nicht
  belegbar. Aktivieren:
  `sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald`.
* Haupt-Checkout `~/picam-ai`: beim Wiki-Abgleich auf `master`
  (`339703d`). Der zuvor dokumentierte WIP liegt auf
  `wip/haupt-checkout-2026-10-21` (`a55ab1f`); dessen Integration gesondert
  prüfen. Uncommittierte Messdokumente der Person erhalten.
* Vier gemergte Remote-Branches können weg (`feat/einrichtungsassistent`,
  `feat/task-b-versatz-normierung`, `fix/docs-pin-pymdown`,
  `ocr-selbstkalibrierung`); MEM-6 (Pi-Hauswart, auf origin, nicht gemergt)
  entscheiden.

**Offen seit 2026-10-21: angepasste Lesetoleranz validieren.** Die Werkbank
bietet bei Gegenlesen WARNUNG eine Toleranz bis ×2,0 an (1,25 × gemessener
Abstand, nur mit seriellem Referenzwert, Werte als „nicht validiert“
markiert). Belegt: Einrichtungsstandbilder stimmen mit der Referenz,
synthetischer Sweep mit ×2,0 ohne falschen Wert, und ein erster Live-Lauf
×1,8 mit Referenz (`live-20261021T143419Z`, 5,6 min, 0 Fehllesungen bei 6630
entschiedenen VALID, 8978 Toleranzbilder; [VALIDATION](docs/VALIDATION.md#messpfad-live-toleranzlauf-2026-10-21)).
Ein strenger Lauf über 12 min (`live-20261021T144605Z`, 0/8979) belegt den
Dauerbetrieb, zählt aber nicht für die Toleranz.
Es fehlen ein Toleranzlauf ≥ 10 min mit bestätigtem Werteplan, eine zweite
Aufstellung und jeweils ein Abgleich mit
`PYTHONPATH=src ./.venv/bin/python scripts/live-reference-eval.py <run-dir>`
(Fehllesungen, Wechselanteile, Verzögerung und `tolerance_frames` in
`session.json`; siehe [Anleitung Kapitel 10](docs/anleitung/10-kamera-livevorschau.md#referenzaufzeichnung-und-abgleich)). Bis dahin keine Toleranz-Läufe für echte Kalibrierungen.

### Zensical-Wiki umbauen (Gerüst gebaut, weitere Seiten offen)

Gerüst und Beispielseiten sind auf Branch `feat/wiki-geruest` gebaut,
noch nicht gemergt. Leser und Leitlinien stehen in `PRODUCT.md`,
Umfang und Konventionen im bestätigten Brief
[2026-10-23 Wiki-Gerüst](docs/superpowers/specs/2026-10-23-wiki-geruest-design.md).
Startseite, Seitenkopf, Hinweise und Statuschips, Schichten und Muster,
Verarbeitungskette und Tabellendiagramme sind gebaut. Das Glossar umfasst
263 Begriffe; Vorkommen kommen zur Laufzeit aus `search.json`.
Beispielseiten: `docs/CAMERA_COMMISSIONING.md`, Kameraregler in
`docs/anleitung/10-kamera-livevorschau.md`, Anbindung in
`docs/GSVMULTI_PROTOCOL.md`. Linke Navigation und URLs bleiben.

Noch nicht auf Wege/Schichten umgestellt (ohne `weg:` im Front Matter):

* Projektseiten: `docs/CodeWiki-2.0-Umsetzungsplan.md`,
  `docs/DISPLAYBUS_TAP.md`,
  `docs/FORTSCHRITT.md`,
  `docs/HARDWARE_PROFILE.md`,
  `docs/HOSTING.md`,
  `docs/OPTICAL_SETUP.md`,
  `docs/README.md`,
  `docs/ROADMAP.md`,
  `docs/TIMING.md`,
  `docs/dependencies.md`,
  `docs/open-questions.md`,
  `docs/status.md`.
* Anleitung: `docs/anleitung/00-werkzeuge.md`,
  `docs/anleitung/01-kette-verstehen.md`,
  `docs/anleitung/02-vertraege.md`,
  `docs/anleitung/03-erste-bildquelle-folder.md`,
  `docs/anleitung/04-geraeteprofile.md`,
  `docs/anleitung/05-cli.md`,
  `docs/anleitung/06-kamera-aufnahme-replay.md`,
  `docs/anleitung/07-lokalisierung.md`,
  `docs/anleitung/08-ocr-backends.md`,
  `docs/anleitung/09-betrieb.md`,
  `docs/anleitung/11-datensatz-sammeln.md`,
  `docs/anleitung/rezepte.md`.
* Übersichten: `docs/uebersicht/daten-und-abnahme.md`,
  `docs/uebersicht/projekt-tour.md`,
  `docs/uebersicht/zeitstempel.md`.

Messjournale (`docs/VALIDATION.md`, `docs/lab_journal.md`), Historie
(`docs/project_history.md`, `docs/tool_review_2026-09-08.md`,
`docs/wiki-audit-2026-10-21.md`), `docs/PLAN_*` und `docs/superpowers/`
bleiben wie sie sind. Die übrigen Seiten seitenweise mit vollständigem
Faktenerhalt umstellen; höchstens eine Seite pro Pflegelauf.
Der tägliche Pflegelauf (`scripts/docs-maintenance-prompt.md`, Codex)
kennt die Bausteine seit 2026-10-23 und hält ihre Konventionen ein.

### 1.–2. Erledigt 2026-09-23: M und führende Null

* **M = 695 ms**, der grösste Wert über die Populationen. Das hat der Nutzer
  entschieden, festgeschrieben im Plan unter Festlegung 3.
* **Führende Null:** Sie wird vor dem Vergleich aus dem Telegramm entfernt,
  wie vom Nutzer entschieden. Das macht `telegram_to_display_text()` in
  `scripts/gate-label.py`, im Plan steht es unter Festlegung 1. Offen aus
  [OQ-41](docs/open-questions.md) bleiben (b), die leere Zelle im Zellenraster
  des Lesers, und (c), negative Werte (ungeprüft).

### 3. Erledigt 2026-09-24: Task 6, Fokus, ScalerCrop, Schwelle

* Fokus nachgestellt, ScalerCrop 1920×1440 um die Anzeige → `native_scale = 1,0`.
* Gemessen: frontal 3,36, „30°" (≈ 20°) 3,34, „45°" (≈ 23°) 2,68 native px
  je Punktspalte. **`resolution_threshold_px = 2,6`**, vom Nutzer festgelegt
  (Plan, Entscheidung 7).
* Profile und Bilder: `var/diagnostics/task6-{frontal,30deg,45deg}-setup/`.
  Der Ausschnitt gilt nur für die jeweilige Kameralage; nach jedem
  Verstellen neu bestimmen (10-s-Vollbild, dann Ausschnitt).

### 4. Erledigt 2026-09-24: Task 7, Ernte 1

81 Proben importiert (VALIDATION.md, „Ernte 1"). Profil und Lauf:
`var/diagnostics/ernte1-profile/`, `var/diagnostics/ernte1-run/`; Sicherung
des Datensatzes davor: `var/backup-datasets-vor-ernte1-20260924T1159/`.

**Nächste Schritte:**
* **Stand Abend 2026-09-24:** 389 Proben, 301 geerntet aus 98 Zeichenketten
  in 3 Aufstellungen, **Ziffernabdeckung vollständig** (VALIDATION.md,
  „Aufstellung 3"). Vor jeder Ernte die Stichprobe ansehen — so wurde der
  Zwei-Nullen-Fehler gefunden (OQ-41).
* **Schärfe vor jeder Ernte prüfen:** die Schwelle 2,6 px lässt unscharfe
  Aufstellungen durch. Fokus in einer eigenen Sitzung mit Ausschnitt und
  Schärfemesser, Kamera dabei nicht bewegen.
* Weitere Aufstellungen (Winkel, Abstand, Licht) für unabhängige Testgruppen;
  ≤ 7 Starts je Boot, danach Neustart.
* Weitere Ernten mit anderen `--seed`, um die Ziffernlücken je Zelle zu
  schliessen (OQ-39-Nachtrag). Solange die Kamera nicht bewegt wird, gilt
  `ernte1-profile/profile.json` weiter — dann ist jede Ernte **ein** Start.
* Prüfen, warum nur ≈ 28 statt ≈ 39 Bilder je Schritt gelabelt werden
  (`telegrammluecke` 1497): nur die Schreibpause oder auch zu knappe 800 ms?
* Phase 2: Zellen-Klassifikator ist auf dem Feature-Zweig in Tasks 1–7
  implementiert; echte Stufe-1-Messung und Freigabe stehen noch aus.

### 5. OQ-40: Gap-Schwellen nachmessen (kein Ernte-Blocker)

**Erledigt 2026-09-23:**
* Ursache gemessen: Beim Zurückschreiben auf die SD-Karte blockieren die
  Dateischreibvorgänge.
* `sync-record.py` schreibt jetzt in eigenen Threads.
* `sensor_sequence` wird je Bild mitgeschrieben, verlorene Bilder sind
  gezählt.
* `gate-label.py` lehnt Stösse über `--min-gap-ms` ab.

Zahlen: `docs/VALIDATION.md`, Eintrag „Stillstand beim Aufzeichnen".

**Offen:** Endgültige Werte für `--min-gap-ms` und `--max-gap-ms`. Laut
Ernte-Phase-1-Plan wird die Stundenaufzeichnung bewusst nicht vorgezogen:
die erste Ernte benutzt 300/800 ms und markiert
`gap_thresholds_provisional: true`. Die Stundenmessung folgt separat.

**2026-10-30:** 13 Live-Läufe (≈ 74 min, Kamera laufend) bestätigen
800 ms. Der ungestörte Strom hat höchstens 561 ms Abstand; ein einzelner
Ausfall ergäbe ≥ ≈ 1 039 ms. Die Referenzauswertung und der Rekorder nutzen
jetzt 800 ms statt 1 000 ms; die Auswertung aller Läufe ist bytegleich.
Offen bleiben die Stundenmessung und ein absichtlich erzeugter Ausfall.

→ [OQ-40](docs/open-questions.md#oq-40).

### 6. Externer Loader lehnt Export-Schema 2 ab

`picam-ai-auto-seven-segment/src/dispread/experimental/evaluation.py:50`
akzeptiert nur `schema_version` 1. Ein einzeiliger Relax auf `{1, 2}` würde
reichen. **Der Nutzer ist unentschieden (2026-09-23), deshalb bleibt es
unverändert**, weil es ein anderes Repo ist. Bis dahin ist
`test_real_export_is_accepted_by_the_actual_experiment_loader` `xfail(strict=True)`.

### 7. Kleinere offene Punkte

* **Vorzeichenstelle unverifiziert** (Firmware 1.3.07, negative Normierung
  erst ab 1.5.06) — muss bei jeder Benchmarkzahl mitgenannt werden.

---

## Was nicht vergessen werden darf

Vorab festgelegt, damit nichts nachträglich an ein Ergebnis angepasst wird
(Plan, Abschnitt „Vorab-Festlegungen"):

1. **Exakte Zeichenkettengleichheit** zwischen Label und Anzeige — keine
   Toleranz, kein Runden. (Die OQ-41-Abbildung ist eine Vorschrift, keine
   Toleranz — Festlegung bleibt bestehen.)
2. **Bilder im Schutzfenster bekommen keinen geratenen Wert.**
3. **M fällt aus der Formel**, es wird nicht ausgesucht. Die vorab
   entschiedene konservative Kombination ergibt **695 ms**.
4. **`independence_group` je Aufnahmesitzung**, nicht je Bild.
5. **Jede Benchmarkzahl nennt die Herkunftsmischung** (`manual` vs.
   `serial_ascii`) und die unbelegte Vorzeichenstelle.

---

## Fallstricke

* **`0x3B`-Präfix** bei GSV-Registerantworten — `scripts/gsv-registers.py`
  macht es richtig.
* **`capture_request(wait=2.0)`** ist ein Timeout in Sekunden, kein Flag.
* **`create_video_configuration`**, nicht `create_still_configuration` — mit
  `RGB888`, gesetzter `FrameRate`, `queue=False`.
* **Ein Normierungsschreibzyklus pausiert den Strom ~1,8 s** (STOP/CLEAR →
  schreiben → START) — sichtbar in `commands.jsonl` als `non_telegram`.
* **`frame_sequence` in `sync-record.py` ist ein Skriptzähler**; für
  Sensorlücken das zusätzlich aufgezeichnete `sensor_sequence` verwenden
  (siehe OQ-40).
* **Das Telegramm hat eine führende Null, das Glas nicht** — Rohübernahme
  des Telegramms als Label ist ab Wert ≥ 1 falsch (OQ-41).

---

## Landkarte — wo steht was

| Frage | Datei |
| --- | --- |
| Aktueller Stand, Blocker | `docs/status.md` |
| Plan mit Tasks A–H, Vorab-Festlegungen | `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md` |
| Alle Messzahlen | `docs/VALIDATION.md` (Einträge 2026-09-23 am Ende) |
| Aufbau, Deutung, Irrwege | `docs/lab_journal.md` (letzter Eintrag) |
| Offene Fragen | `docs/open-questions.md` — OQ-22 (Kamerabrücke, seit 2026-09-24 wieder funktionsfähig), OQ-38 (Zeitkopplung), OQ-40 (Gap-Schwellen), OQ-41 (führende Null) |
| Dot-Matrix-Leser, nicht bestandenes Gate | `docs/superpowers/plans/2026-09-22-dotmatrix-backend.md` |

### Werkzeuge

| Skript | Zweck | Stand |
| --- | --- | --- |
| `scripts/gsv-registers.py` | Registerstand als Rückstellpunkt, nur Lesebefehle | läuft, verifiziert |
| `scripts/sync-record.py` | Kamera + serieller Strom, `--norm-schedule` | **läuft gegen Hardware**, verifiziert |
| `scripts/display-offset.py` (neu) | Photometrischer Versatz Telegramm↔Glas, Vorlagen-Projektion | läuft, erste Zahlen liegen vor |
| `scripts/gate-label.py` | Offline-Gate, rein über Zeitstempel | Normalisierung der führenden Null gebaut (OQ-41), M = 695 ms festgelegt; nie auf echten Daten gelaufen |
| `scripts/migrate-samples-v1-to-v2.py` | Schemamigration | gelaufen, erledigt |
