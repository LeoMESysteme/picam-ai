# Status — Stand 2026-09-30 (Sessionende)

Dieser Snapshot wird zum Sessionende überschrieben. Verlauf:
[Changelog](../CHANGELOG.md) und
[Projektgeschichte](project_history.md); Aufgaben:
[TODO.md](../TODO.md).

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

**Einrichtungsassistent (Branch `feat/einrichtungsassistent`):**
Nacharbeit 1–4 sind umgesetzt. Bei festen oder nachgeführten Quads
entscheiden der bekannte Zellentext, die unabhängige 2j-Prüfung und
`check_setup` über den Vorschlag. RMS, Bias und Zuordnungsquote bleiben
bei bestandenem 2j als WARNUNG sichtbar; die automatische Startsuche
behält ihre strengeren Grenzen. Wird ein am zweiten Standbild besseres
Quad aus anderem Grund abgelehnt, bricht `assist` mit dem Grund ab.
`confirm` speichert fehlende Prüfungen als `NICHT_GEPRUEFT` und verlangt
eine neue Begründung.

Die vier bestätigten Profil-Quads von `ab4`, `ab5`, `ab6` und `sc6`
bestehen den textgestützten Offline-Befehl `propose --quad` mit OK oder
WARNUNG; 2j ist in allen vier Fällen OK. `ab4` und `ab6` haben noch
keine sichere automatische Startlage. Die Einheitszeichen rechts werden
geometrisch extrapoliert. Es gab keinen echten Assist-Kamera- oder
seriellen Lauf; `var/` wurde nur gelesen. Zahlen und Grenzen stehen in
[VALIDATION.md](VALIDATION.md) und im
[Plan](superpowers/plans/2026-09-29-einrichtungsassistent.md).

**Branch-Prüfung:** 997 Python-Tests bestanden, 3 übersprungen,
1 erwarteter Fehlschlag; 155 gezielte Tests bestanden. Ruff und
`git diff --check` waren sauber. Der Zensical-Build meldete keine
Probleme, alle 21 Playwright-Dokutests bestanden. Eine abschließende
Code-Review fand keinen blockierenden Befund.

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

1. Den Feature-Branch nach Review durch Claude integrieren. Der erste
   echte Assist-Lauf und die Einrichtungsdauer gehören zum gemeinsamen
   Kameratermin. Die optionale Nacharbeit N1–N3 und die Startsuche für
   schräge Aufstellungen stehen im Plan.
2. Die Importprüfung `zellen_inkonsistent` für schrägen Blick verbessern
   (Vergleich je Position), danach `ab6` gegebenenfalls neu importieren.
   Dafür die Einzelbilder von `ab6-run` behalten.
3. Das Codex-Leck dauerhaft abstellen (repowise-Plugin in Codex) und `var/`
   auf ein anderes Medium sichern. Alte tar-Sicherungen erst nach
   Rückfrage löschen.
4. Weitere Abnahmebedingungen: anderes Licht, weitere Geräte und Einheiten.
