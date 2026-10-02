# Status — Stand 2026-10-02 (Dokumentationssnapshot)

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

**Einrichtungsassistent:** `harvest-setup.py assist` ist im aktuellen
`master`-Stand vorhanden. Der Lauf erstellt nach Fokus-Sweep und zwei
Standbildern ein Punktraster-Profil mit Prüfbericht und Overlays; ein
GSV-2AS-Zellentext kommt standardmäßig seriell oder kann offline vorgegeben
werden. Vorhandene Messungen:
* Der erste echte Kameralauf mit seriellem Text richtete `sc7` ohne
  Hilfe ein:
  * 2j mit 0,04 Spalten und 0,07 Zeilen, unabhängig mit
    `profile-regrid.py still` bestätigt,
  * Gegenlesen 2/2,
  * Gesamturteil WARNUNG nur wegen des Bias-Ersatzmaßes.
* Der Versuch davor (`sc7a`, Kamera leicht von oben) brachte zwei falsche
  Ablehnungen:
  * Die Startsuche fand aus der Nähe keine Startlage.
  * Punktschatten wurden als belegte Cursorzeile gezählt.
* Im Plan dokumentierte Nacharbeit 5 betrifft Startsuche aus der Nähe und
  Punktschatten in der Cursorzeile ([Plan](superpowers/plans/2026-09-29-einrichtungsassistent.md)).
  Der aktuelle Code enthält die Nacharbeit; ein neuer echter Lauf mit
  schräger Aufstellung ist in den vorliegenden Messbelegen nicht dokumentiert.
* Schräge Aufstellungen wie `ab4` oder `ab6` deshalb bis zu diesem Gegencheck
  weiter mit `profile-regrid.py still` einrichten.
* Nach dem Merge liefen in `master` 997 Tests grün, ruff ist sauber.

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

1. Den aktuellen Stand von Nacharbeit 5 mit einer Aufstellung leicht von
   oben, wie bei `sc7a`, mit `assist` gegenprüfen.
2. **Anbindung an den Messpfad** (Variante B, TODO.md Punkt 2).
   * Zuerst einen Plan schreiben.
   * Dann die StreamCam an der Werkbank bzw. in `dispread serve` in
     Betrieb nehmen.
   * Dann den Dot-Matrix-Leser im laufenden Pfad einsetzen, mit Ausgabe an
     GSVmulti (das GSV-Protokoll ist offen, OQ-07).
3. Die Importprüfung `zellen_inkonsistent` für schrägen Blick verbessern.
   Die Einzelbilder von `ab6-run` dafür behalten.
4. **SD-Karte:**
   * Die Löschung von `vor-ab6.tar`, der Einzelbilder `sc6-run` und der
     Einzelbilder `sc7-run` (etwa 4,8 GB) ist vorgeschlagen; die Freigabe
     durch den Nutzer steht aus.
   * Das Codex-Leck dauerhaft abstellen.
   * `var/` auf ein anderes Medium sichern.
