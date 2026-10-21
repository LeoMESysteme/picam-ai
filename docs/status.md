# Status — Stand 2026-10-21

Dieser Snapshot wird zum Sessionende überschrieben. Verlauf:
[Changelog](../CHANGELOG.md) und [Projektgeschichte](project_history.md);
Arbeitsliste: [TODO.md](../TODO.md).

## Messpfad live

Auf `worktree-feat-messpfad-live` ist der Messpfad gebaut: `dispread serve`
hält die Logitech StreamCam über `CameraOwner` für seine gesamte Laufzeit.
`/live` führt durch Einrichtung, namentliche Bestätigung und Messlauf mit
Dot-Matrix-Leser; der Wert trägt VALID, TRANSITION, UNREADABLE oder STALE.
Die alte Werkbank bekommt gedrosselte Bilder vom selben Owner;
Kamerabedienung erfolgt nur über `/live`. Andere Kameraprozesse, etwa
Harvest-Skripte, bekommen währenddessen „belegt“. Port 8080 ist auf diesem Pi
durch MEhub belegt; die Werkbank läuft mit `dispread serve --port 8081`.

Einrichtung und Profil liegen unter `var/live/<sitzung>/`, einschließlich
`profile.json` und `confirmation.json` nach Bestätigung. Jeder Lauf schreibt
`records.jsonl` und `session.json` unter `var/live/<sitzung>/run-NN/`.
Lokal stehen `dispread live status|setup|stop|camera` zur Verfügung;
Bestätigung und Laufstart bleiben in der angemeldeten Oberfläche (Konzept §4).

## Neu am 2026-10-21

* **Lesesperre und Testlauf (L1, `5620ff0`).** Der Laufstart wird mit
  Erklärung abgelehnt, solange die Einrichtungsprüfung `gegenlesen` nicht OK
  ist. Ein ausdrücklicher Testlauf (`TESTLAUF.json`, Banner) zeigt die
  Vermutungen des Lesers, gibt aber nie einen Wert frei.
* **Schwankende Ziffern (L2, `7f71422`).** Gegenlesen ignoriert maskierte
  Zellen und vergleicht den Rest mit der seriellen GSV-2AS-Referenz; ein
  Widerspruch ist FEHLER. Standbilder werden bis zu fünfmal neu
  aufgenommen, bis der serielle Wert ruhig ist. Der manuelle Zellentext
  nimmt 8 Zeichen und `?` an.
* **Licht-Hinweis und angepasste Toleranz (L3, `b0d6f1a`).** Ungleiches Licht
  (Schatten) wird als Kontrastsprung zwischen Zellen benannt. Eine angepasste
  Lesetoleranz gibt es nur mit serieller Referenz: Faktor = 1,25 × größter
  gemessener `d_best` / `d_max`, höchstens 2,0, durch erneutes Lesen geprüft,
  bei der Bestätigung anzukreuzen. Lauf und Werte tragen „nicht validiert“,
  `tolerance_frames` steht in `session.json`. Synthetischer Sweep mit
  `d_max` × 2,0: kein falscher Wert.

## Bedienerläufe am Aufbau, 2026-10-21

StreamCam am GSV-2AS, Raumlicht und Tageslicht. Das sind **keine formalen
Abnahme-Läufe**; die Toleranz ist **nicht validiert**.

* **Morgens:** Kamera schräg und mit Kameraschatten auf der Anzeige. Punkttiefe
  außerhalb des Schattens 0,39–0,41, im Schatten 0,67–0,69. Zellen an der
  Schattenkante überschritten `d_max` (`d_best` bis 2,30 × `d_max`), doch die
  beste Vermutung stimmte in allen 28 Einrichtungsstandbildern mit Vorschlag
  mit der Referenz überein (Abstand zur zweitbesten Klasse ≥ 1,27).
* **Manueller Zellentext** mit schwankender letzter Ziffer erzeugte ein
  irreführendes 2j FEHLER (mit L2 behoben).
* **Testlauf** `live-20261021T100128Z`: Vermutungen nach Angabe der Person
  richtig, `tracking_lost` 0, `track_score` mindestens 0,86 bei Wertwechseln.
* **Toleranzlauf ×1,41** `live-20261021T113859Z` (25 s): 304/318 VALID,
  11 TRANSITION, 3 UNREADABLE, Nachführung ohne Verlust.
* **Strenger Lauf** `live-20261021T114122Z` (79 s, viele Wertwechsel, kurz
  Hand vor der Anzeige): 911/1168 VALID, 188 UNREADABLE, 68 TRANSITION,
  1 STALE. Alle 67 Wertwechsel erfasst; je Wechsel 270–340 ms ohne VALID
  (LCD-Umschaltung etwa 200–300 ms plus 1 Bestätigungsbild). Die Hand
  bedingte 1,4 s UNREADABLE, `tracking_lost` 33.
* **Tempo:** 14,7 verarbeitete Bilder/s von 30; Leser median 53 ms/Bild,
  gesamt 64 ms. Jedes zweite Bild entfällt.

Zahlen und Deutung: [VALIDATION.md](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21),
[Laborjournal](lab_journal.md#messpfad-live-bedienerlaeufe-2026-10-21).
Laufdaten unter `var/live/<sitzung>/` (lokale Daten, nicht in Git).

## Grenzen und nächster Schritt

Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V — andere
Lichtquellen und Geräte nicht geprüft. Die Leser-Abnahme 3 vom 2026-09-30
(215/215 richtig) und der `sc7`-Lesetest (111/111 richtig) bleiben frühere
Belege; sie ersetzen den Live-Messlauf nicht.

Plan [Tempo, Übergangsstatus und Abschluss](superpowers/plans/2026-10-21-messpfad-live-tempo-und-abschluss.md):

1. Leser auf 30 Bilder/s mit Pi-Schutz (CPU, Temperatur, Drosselung).
2. TRANSITION statt UNREADABLE bei Wertwechseln; Hand vor der Anzeige bleibt
   UNREADABLE.
3. Merge nach `master` und Worktree-Aufräumen.

Später: Referenzaufzeichnung zur Validierung der Toleranz (serieller Strom
parallel, Abgleich der VALID-Werte), Referenzlauf, serielle Ausgabe an
GSVmulti ([OQ-07](open-questions.md#oq-07), Protokoll fehlt) und eine
UI/UX-Überarbeitung der Werkbank (nicht prod-ready; erst wenn der Messpfad
weitgehend fertig ist).

Weiterhin offen: `raw_text` enthält die geparste Zahl, nicht die 16
Displayzellen. Ein stillstehender Stream beendet die Sitzung erst nach dem
OpenCV-Select-Timeout (etwa 10–20 s), die Wertanzeige wird zuvor STALE. Die
`JsonlSink`-Rotation würde nach etwa 7 h alte Auditgenerationen verwerfen.
Außerdem die 7-Segment-Bereinigung der alten Seite, Audit-Aufbewahrung,
andere Lichtquellen/Geräte/Einheiten und die Importprüfung bei schrägem
Blick. `var/` braucht weiterhin eine Sicherung auf anderem Medium; ältere
Hinweise zur knappen SD-Karte stehen in TODO und Laborjournal.

## Aus `origin/master` übernommen (Stand 2026-10-12)

* **Projektcockpit** (privat, Sites):
  [picam-ai Projektcockpit](https://picam-ai-cockpit.me-me-system-9148.chatgpt.site),
  Version 4. Quelle: eigenes Repository `sites/picam-ai-cockpit`, Site-ID
  `appgprj_6accdd4468948191be0d5301888c835f`. Forgejo
  ([l.hentschke/picam-ai](https://ds1515.me-systeme.de/l.hentschke/picam-ai))
  ist das maßgebliche Repository, GitHub nur Mirror. Das Cockpit liest per GET
  mit einem Read-only-Token (`FORGEJO_ACCESS_TOKEN`, Sites-Runtime-Geheimnis).
  Es zeigt Roadmap P0–P8, Commit-Aktivität, Dateivolumen und eine
  Zeilenanalyse eigener Code-Dateien; Abrufstand 2026-10-12: 173 eigene
  Code-Dateien, 51.760 Quelltextzeilen. Offen: automatische Zeilenanalyse
  und Ansicht für historisches Wachstum (nur entworfen).
  [Spezifikation](superpowers/specs/2026-10-12-projektcockpit-design.md),
  [Plan](superpowers/plans/2026-10-12-projektcockpit.md).
* **Projekt-Tour:** alle sechs Kapitel vorhanden
  ([Tour](uebersicht/projekt-tour.md)), Tour-Fakten aus dem Code
  (`scripts/tour-facts.py`); Verhaltensänderungen brauchen Text und Szene
  zusammen (AGENTS.md).
* **Startseite:** [Startseite](../index.md) nennt die StreamCam und verlinkt
  alle Navigationsziele; Vertiefungen zu [Messpfad](uebersicht/messpfad.md),
  [Zeitstempeln](uebersicht/zeitstempel.md) und
  [Daten/Abnahme](uebersicht/daten-und-abnahme.md). IMX500-Baukapitel sind als
  historisch gekennzeichnet.
* **Forgejo-Runner (Docs/Codex):** Der Runner nahm am 2026-09-30 einen
  Auftrag an und veröffentlichte einen Doku-Commit. Der rotierende Audit
  prüft die Startseite bei jedem Lauf. Das Startkommando nennt die Rolle
  `docs_reader` ausdrücklich (`--ignore-user-config` lädt sie nicht
  selbst; `--ephemeral` scheiterte am Spawn). Die geschützte Anmeldung und
  Sessionlogs sind nicht lesbar ([Hosting und Pflege](HOSTING.md)).
  Playwright-CI: `playwright.yml` verlangt das Label `picam-docs`, lädt nur
  Chromium und nutzt den Forgejo-Artefaktupload.
