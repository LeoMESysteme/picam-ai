# Status — Stand 2026-10-23

Dieser Snapshot wird zum Sessionende neu geschrieben. Arbeitsliste:
[TODO.md](../TODO.md); Verlauf: [Changelog](../CHANGELOG.md),
[Projektgeschichte](project_history.md) und [Laborjournal](lab_journal.md).

## Aktuelle Arbeit: interaktive Wiki-Roadmap

Die Roadmap ist im isolierten Arbeitsstand als frei verschiebbare Karte
mit P0–P8 und einer eigenen inneren Ebene für die Arbeitsschritte gebaut.
Kartenminiaturen zeigen die enthaltene Ebene. Beim Eintritt verblassen
Inhalt und Füllung, der Umriss erreicht den Bühnenrand; Randlicht und eine
statische Punktwolke kennzeichnen die innere Karte. Klick, Tastatur,
Mausrad und Touch-Pinch nutzen denselben Ebenenwechsel.

Die Hauptkarten zeigen gemäß Bildvorlage zwei verbundene Checkpoints mit
Häkchen und Status rechts. Bei laufenden Phasen bleibt der nächste offene
Schritt sichtbar. Schrittstatus und belegte Daten kommen aus der neuen
Tabelle in [ROADMAP.md](ROADMAP.md#roadmap-schritte); die erste
Phasentabelle bleibt unverändert. Quelltabellen und Nutzung ohne
JavaScript bleiben erhalten. Die vorhandene lokale Anime.js-Kopie wird
wiederverwendet, es gibt keine neue Abhängigkeit.

Arbeitsstand: `/home/me-systeme/.codex/worktrees/bbce/picam-ai`. Die Roadmap
wird auf ausdrücklichen Wunsch in einem eigenen lokalen Commit gesichert;
eine Veröffentlichung erfolgt dabei nicht. Vorbestehende TODO-Änderungen
und der R13-Plan bleiben außerhalb dieses Commits erhalten.
[Entwurf](superpowers/specs/2026-10-23-roadmap-spatial-zoom-design.md)
und [Umsetzungsplan](superpowers/plans/2026-10-23-roadmap-spatial-zoom.md)
halten Entscheidungen und Abnahme fest. Eine unabhängige Codeprüfung
fand einen inzwischen korrigierten Verlust unbesuchter Kartenpositionen
nach Neuladen; ein Regressionstest deckt beide betroffenen Ebenen ab.
Abschluss: **45/45 Doku-Browsertests bestanden**, strenger Website-Build
ohne Befunde, JavaScript-Syntax- und Diff-Prüfung sauber. Desktop und
375-Pixel-Ansicht in beiden Themes gesichtet; der Schlussreview bestätigt
die Speicherkorrektur und hat keine offenen wichtigen Befunde.

In dieser Session keine Hardwareänderung, kein Messlauf und keine
Änderung am Messpfad. Die folgenden Lauf- und Messangaben sind der
dokumentierte Projektstand vom 2026-10-21, keine neue Live-Abfrage.

## Wiki-Abgleich vom 2026-10-21

Alle 52 Zensical-Navigationsseiten und die 34 Tour-Schritte sind geprüft.
Drei Subagents bearbeiteten Anleitungen, Projekt/Betrieb und Tour/API;
ein weiterer Agent prüfte die Änderungen unabhängig. Das
[Seitenprotokoll](wiki-audit-2026-10-21.md) nennt Ergebnisse und offene
Befunde. Veraltete Live-/IMX500-Aussagen, Installationsblocker, Freigabe-
und Zeitversprechen sind korrigiert. Anime.js-Timelines und Szenentexte
sind gemeinsam aktualisiert; 32 Tour-Fakten werden aus Code/Belegen erzeugt.

Neu erkannt und sofort erfasst:

* [OQ-44](open-questions.md#oq-44): Testlaufmarkierung und Banner verhindern
  technisch weder VALID im Audit noch dessen Anzeige. Solche Daten bleiben
  für Messungen gesperrt; eine erzwungene Freigabesicherung fehlt.
* [OQ-45](open-questions.md#oq-45): MONOTONIC-Verarbeitungsmarken werden
  teilweise mit einer unpassenden Zeitbasis bezeichnet. Der aktuelle
  V4L2-Livepfad passt; andere Aufnahmezeitbasen brauchen eine Korrektur.

Produktionscode wurde bei diesem Abgleich nicht geändert. Vorbestehende
Messdokumente und deren neue Abschlussbelege sind erhalten. Der damalige
Messlauf ist beendet und die Rückstellung bestätigt.
OQ-/Tour-Faktentests: **13 erfolgreich**, Browserprüfung: **29 erfolgreich**.
Strenger Website-Build, Lint, Generator- und Diff-Prüfungen bestanden.
Alle 52 Navigationsseiten laden mit HTTP 200 ohne JavaScript-Fehler;
geänderte Tour-Szenen und 375-Pixel-Ansicht gesichtet. Eine vom Kopierknopf
verdeckte Code-Anmerkung ist durch eine mehrzeilige Signatur behoben.

## Gebauter Messpfad

Auf `master` hält `dispread serve` die Logitech StreamCam über
`CameraOwner` für seine gesamte Laufzeit. `/live` führt durch Einrichtung,
namentliche Bestätigung und Messlauf mit Dot-Matrix-Leser. Die alte
Werkbank erhält gedrosselte Bilder desselben Owners. Kamerabedienung nur
über `/live`; andere Aufnahmeprozesse bekommen währenddessen „belegt“.

Profile und Bestätigung: `var/live/<sitzung>/profile.json` und
`confirmation.json`. Je Lauf: `run-NN/records.jsonl`, `session.json` und
optional getrennt `reference.jsonl`. Lokale Kommandos:
`dispread live status|setup|stop|camera`; Bestätigung und Laufstart bleiben
auf der angemeldeten Seite.

Am 2026-10-21 gebaut und in `master`: Lesesperre bei nicht erfolgreichem
Gegenlesen, markierter Testlauf, maskierte schwankende Zellen,
Schattenhinweis, ausdrücklich zu bestätigende und **nicht validierte**
erhöhte Lesetoleranz mit serieller Einrichtungsgegenprobe, vektorisierter
Leser, TRANSITION bei Mischziffern sowie getrennte Referenzaufzeichnung
mit optionalem Werteplan und Rückstellung. Die Referenz korrigiert keine
DUT-Werte und wird Leser/Gate nicht als Parameter übergeben.
Der [Plan Tempo und Abschluss](superpowers/plans/2026-10-21-messpfad-live-tempo-und-abschluss.md)
ist erledigt. Testlauf-Vermutungen bleiben Diagnosen; OQ-44 begrenzt die
bisherige Behauptung einer vollständigen technischen Freigabesicherung.

## Reale Belege und Grenzen

Die Leser-Abnahme 3 vom 2026-09-30 ergab 215/215 richtige Proben, der
Einrichtungslesetest `sc7` 111/111. Sie betreffen denselben begrenzten
GSV-2AS-/Displaytech-161A-Pfad in mV/V unter Raumlicht, keine allgemeine
Gerätefreigabe und keine vollständige Systemabnahme.

Bedienerläufe vom 2026-10-21: streng 0/715 Fehllesungen; Toleranz ×1,8
über 5,6 min 0/6630; streng über 12 min 0/8979 bei 29,8 gelesenen
Bildern/s. Die Toleranz ist damit weiterhin nicht validiert. Frühere
Schatten-, Handabdeckungs- und Laufzeitbefunde bleiben in
[VALIDATION](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21) und im
Laborjournal erhalten.

Der **strenge Werteplan-Lauf** `live-20261021T151835Z/run-01` ist seit
17:36 MESZ beendet (Start 17:22 MESZ, 806 s einschließlich Rückstellung).
Die parallel dokumentierte
[Abschlussauswertung](VALIDATION.md#messpfad-live-werteplan-2026-10-21)
ergibt 0/11 137 Fehllesungen bei prüfbaren VALID, 2563 VALID im
Schutzintervall und 232 ohne Referenzdeckung. 8074 Trackingverluste;
bei Faktor 2 und 5 **kein VALID in stabilen Referenzfenstern**, bei
Faktor 1, 0,5 und 10 nahezu durchgehend VALID. Kamera ohne Bildlücke,
Audit ohne Fehler, Referenz ohne Queue-Verlust. Normierung und
Dezimalpunkt durch Schreiben und Rücklesen erfolgreich zurückgestellt.

Die systematischen Ausfälle lösen R13 aus
([OQ-26](open-questions.md#oq-26)). Der Tracker berücksichtigt den
Zifferninhalt; ein unabhängiger Bildnachweis der Ursache fehlt, weil keine
Live-Bilder der Ausfallphasen gespeichert wurden. Die Person bestätigt
unveränderten Aufbau und etwa 2 s Abdeckung nach ungefähr 6 min; deren
Zeitfenster ist im Audit nicht eindeutig isolierbar. Kein gesonderter
Abdecknachweis, kein Robustheits-/Toleranznachweis und keine formale Abnahme.
Verzögerungen der großen Plansprünge sind wegen Referenzlücken während
der Befehlspausen nicht messbar.

## Laufumgebung und nächste Schritte

Werkbank in tmux `picam-messlauf-20261021`,
`https://100.122.154.35:8081/live`; zuletzt `stopped`, Kamera für Vorschau
aktiv. Port 8080 ist auf diesem Pi durch MEhub belegt. Vorbereitung und
Register-Sicherung: `var/diagnostics/messlauf-vorbereitung-20261021/`.
Aufstellung: Fokus 42, Belichtung 300, Gain 14, Weißabgleich 4717 K;
sitzungsbezogene Einstellungen in `setup/camera-settings.json`.
Keine Hardwareänderung oder neuer Messlauf durch den Wiki-Abgleich oder
die Roadmap-Gestaltung; der aktuelle Laufzustand wurde nicht abgefragt.

Nächste Aufgaben gemäß TODO:

1. Nachführung unabhängig vom Zifferninhalt untersuchen und große
   Wertwechsel erneut prüfen (R13/OQ-26).
2. Testlauf-Sicherung und Zeitbasis-Bezeichnung klären (OQ-44/OQ-45).
3. Toleranzlauf ≥ 10 min mit Werteplan und weitere Aufstellung erst nach
   Bearbeitung der Trackinggrenze; andere Lichtquellen/Geräte bleiben offen.
4. GSVmulti-Anbindung wartet auf [OQ-07](open-questions.md#oq-07).
   Danach Bedienoberfläche und Aufräumarbeiten gemäß TODO.

Weiter offen: `raw_text` enthält die geparste Zahl statt 16 Displayzellen;
Streamstillstand beendet erst nach OpenCV-Timeout (etwa 10–20 s), die
Oberfläche markiert zuvor STALE; Auditrotation kann nach etwa 7 h alte
Generationen verwerfen. Import bei schrägem Blick und Aufräumen des alten
7-Segment-Pfads bleiben Aufgaben. `var/` braucht eine Sicherung auf anderem
Medium. Das frühere Codex-Staging-Leck wurde am 2026-10-21 abgestellt
(Details/Sicherung in TODO). Nachtpflegefehler seit 2026-10-19 ungeklärt.

Forgejo-CI und Messpfad teilen denselben Pi. Während Messläufen keine
Builds, Browsertests oder Pushes nach `master`: früher bis 44 s Stillstand.
Die Website-Prüfung dieser Runde wurde erst nach dem Laufende begonnen.

## Weitere gepflegte Teile

Projekt-Tour mit allen sechs Kapiteln und eingebetteten Abbildungen;
Fakten aus `scripts/tour-facts.py`. Forgejo ist das maßgebliche Repository,
GitHub ein Mirror. Der geschützte Doku-Runner und Hostingablauf sind in
[HOSTING.md](HOSTING.md) dokumentiert.

Das private [Projektcockpit](https://picam-ai-cockpit.me-me-system-9148.chatgpt.site)
(Version 4, eigenes Repository `sites/picam-ai-cockpit`) liest Forgejo mit
Read-only-Zugriff. Automatische Zeilenanalyse und historisches Wachstum
bleiben offen; Details im [Plan](superpowers/plans/2026-10-12-projektcockpit.md).
