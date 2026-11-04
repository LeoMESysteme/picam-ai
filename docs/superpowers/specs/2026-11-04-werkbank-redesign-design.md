# Werkbank `/live` neu gestaltet — Entwurf

**Stand:** 2026-11-04. Am 2026-10-30 bis 2026-11-04 mit Leonhard Hentschke
schrittweise abgestimmt, über Skizzen und einen animierten Mock.
**Freigegebene Gestaltungsreferenz:** [Mock](2026-11-04-werkbank-redesign-mock/README.md).
Bauen mit `./build.sh`, die Sprungmarken stehen im README. Der Mock ist
**Gesetz für Aussehen und Verhalten**. Die Spec ist Gesetz für Daten,
Wahrheitsregeln und Schnittstellen. Widersprechen sich beide, gewinnt die
Spec, und der Widerspruch kommt in die offenen Punkte.
**Bezug:** Konzept.md §4, §6, §7, §8. Spec Messpfad live 2026-10-12. Die
frühere Seite: `src/dispread/workbench/static/live.html` + `live.js`
(mit Aufgabe 12 entfernt).
Die Bestandsaufnahme der Server-Schnittstelle steht im Anhang A.

## Ziel und Erfolg

Die Werkbank-Seite `/live` soll so werden, dass Bediener im
Kalibrierlabor sie ohne Einweisung durch den Entwickler bedienen können.
Der Entwickler behält dabei alle Diagnosen.

Erfolg heißt:

1. Während der Einrichtung zeigt ein Fortschrittsverlauf jeden Schritt
   live mit Teilfortschritt: Fokus mit live gezeichneter Fokuskurve,
   Kamera, Belichtung mit Pegel, Standbilder mit Stabilitäts-Countdown
   und Vorschlag. Die Prüfungen erscheinen, sobald sie gerechnet sind.
2. Das Kamerabild ist das größte Element. Es läuft mit **bis zu 15 fps**
   statt ≈ 2 fps. Ein HUD zeigt darauf Anzeige, Raster, Zellen,
   Rahmenbereiche und den gelesenen Wert, deckungsgleich zum
   angezeigten Bild.
3. Jeder Störzustand ist auf einen Blick erkennbar, ohne zu lesen. Das
   sind Wechsel, Unlesbar, Nachführung verloren, Korrektur läuft,
   Streamstillstand und Verbindung verloren. Wo der Bediener handeln
   muss, erscheint ein Dialog.
4. Die Bilder aus der Einrichtung (Standbild, Abtastbild, Entzerrt) sind
   in den Viewer eingebaut. Sie sind zoombar, jede Markierung lässt sich
   per Zeigen erklären, und Rahmenbereiche lassen sich im Bild bearbeiten.
5. Ein neuer Nutzer lernt die Oberfläche auf drei Wegen: in einem
   Rundgang, in einem Übungslauf ohne Hardware und über das Hilfe-Dock.
6. Keine Wahrheitsregel der heutigen Seite wird schwächer (siehe
   „Wahrheitsregeln“).

## Entscheidungen

| Datum | Frage | Entscheidung |
|---|---|---|
| 10-30 | Bildschirm | Desktop-Monitor im Labor, Maus und Tastatur. Zielbreite 1440 px, muss von 1280×800 bis 1920×1080 tragen |
| 10-30 | Nutzer | Laborbediener ohne CV-Wissen und der Entwickler. Diagnosen bleiben einen Klick tiefer erreichbar |
| 10-30 | Technik | Entscheidung Claude: ohne Build, ES-Module, Canvas 2D und SVG (siehe „Technik“) |
| 10-31 | Richtung | **D, Branchenstandard Machine-Vision-HMI**. Gewählt aus A Signalbuch, B Kalibrierschein, C Liniennetz und D |
| 10-31 | Maßstab | Cognex In-Sight/VisionPro und MVTec MERLIC/HALCON. Kein „generischer Dark-Panel-Look“ |
| 11-04 | Mock | Freigegeben: „everything looks great“. Effekte, Dialogregel und Wertanzeige wie im Mock |
| 11-04 | Einarbeitung | Rundgang + Übungslauf + Hilfe-Dock mit Glossar. **Keine** einmaligen Erst-Hinweise |
| 11-04 | Bildrate | Adaptiv, **höchstens 15 fps**, fällt unter Last auf 5 fps. Der Messpfad hat immer Vorrang |
| 10-30 | Arbeitsteilung | Codex setzt das Backend um, Claude-Subagenten setzen die Oberfläche um, Claude prüft |

## Nutzer und Szene

Ein Laborbediener steht im hell beleuchteten Kalibrierlabor am Aufbau.
Dazu gehören GSV-2AS, StreamCam auf Stativ und der Pi. Er schaut auf
einen Desktop-Monitor daneben, oft im Wechsel mit GSVmulti. Er richtet
ein, prüft und bestätigt mit Namen und startet dann einen Lauf, der
Stunden dauern kann. Danach schaut er nur noch gelegentlich hin. Der
Entwickler bedient dieselbe Seite, auch über Tailscale, und will Gründe,
Kennzahlen und Rohbilder sehen.

## Visuelle Welt

Die Werte sind aus dem Mock übernommen (`mock.src.html`, `:root`). Die
Seite ist **nur dunkel**. Das ist bewusst gewählt: Der Viewer ist ein
Grafikfenster, und eine helle Hülle würde das Kamerabild überstrahlen.

| Token | Wert | Rolle |
|---|---|---|
| `--bg0` | `#0d0c0b` | Viewer-Grund (Grafikfenster) |
| `--bg1` | `#161513` | Seitengrund |
| `--dock` | `#1c1b19` | Docks |
| `--title` | `#24231f` | Dock-Titelleisten |
| `--ctl` / `--ctl-h` | `#2c2a26` / `#363430` | Bedienelemente / Hover |
| `--line` / `--line2` / `--stripe` | `#3a3833` / `#292724` / `#201f1c` | Trennlinien, Zebrastreifen |
| `--tx` / `--tx2` / `--tx3` | `#ebe7e0` / `#bab4aa` / `#958f85` | Text, Sekundärtext, Tertiärtext |
| `--sel` / `--sel-hi` / `--sel-bg` / `--sel-line` | `#3f6fb8` / `#86aee8` / `#212d40` / `#36507a` | Auswahl, Primäraktion, Fokus |
| `--ok` `--warn` `--err` `--stale` | `#55c46e` `#e5a535` `#ee5b4d` `#8f8a82` | Freigegeben, Wechselt/WARNUNG, Unlesbar/FEHLER, Veraltet/ausstehend |
| `--teal` | `#30c6b7` | **nur** „Korrektur läuft“ (Nachregistrierung) |
| `--mag` | `#d65ccf` | **nur** Rahmenbereiche |

Regeln für Typografie und Formen:

* Schriften: `--sans: "Segoe UI","Noto Sans",system-ui,sans-serif` und
  `--mono: "Noto Sans Mono",ui-monospace,monospace`. Noto Sans und Noto
  Sans Mono (OFL) liegen als woff2 lokal unter `static/vendor/fonts/`,
  ohne CDN.
* Monospace gilt **nur** für Werte, Koordinaten und Kennungen. Zahlen
  stehen immer mit `tabular-nums`. Grundgröße 13 px.
* Docks haben schmale Titelleisten. Zwischen den Docks stehen 1-px-Linien.
  Es gibt **keine** gerundeten Karten und **keine** Schatten außer an
  Pop-ups, Menüs und Dialogen. Radien betragen höchstens 2 px.
* Ein Zustand erscheint als kleines Quadrat plus Wort, nicht als Pille
  oder Häkchen-Kreis. Icons gibt es nur an Werkzeugleisten-Knöpfen, als
  1,5-px-Linien-SVG.
* Statusfarben tragen nur Bedeutung. Teal und Magenta sind reserviert
  (siehe oben).

## Aufbau der Oberfläche

```
┌ Titelleiste: picam-ai Werkbank · Einrichtung › Lauf · GSV-2AS · Displaytech 161A ·· [Hilfe] [Kontextaktionen] ┐
├ Dock links (248 px) ┬ Viewer-Werkzeugleiste ──────────────────────────┬ Ergebnis (nur Lauf) ───────┤
│ Ablauf (Einrichtung)│ Grafikfenster (Kamerabild + HUD + Effekte)     │ Inspektor-Tabs (368 px)    │
│ bzw. Lauf (Statistik)│                                                │ Schritt·Fokus·Prüfungen    │
│ … Fußfelder          ├ Zeitleiste (Einrichtung: Schritte; Lauf: 40 s) │ bzw. Wert·Ursachen·Nachf.·Ref. │
├ Statusleiste: Kamera · Vorschau fps · Bilder · Lücken · Latenz · CPU · SD · Referenz ·· Sitzung ──────────┤
```

* **Kontextaktionen** in der Titelleiste, abhängig vom Zustand:
  * `idle`: Einrichtung starten (mit optionalem Zellentext im Popover)
  * `setup_running`: Einrichtung abbrechen
  * `setup_ready`: Bestätigen, gesperrt bis zur Bestätigung im Inspektor
  * `confirmed`: Lauf starten (Optionen im Popover: Referenz, Diagnosebilder, Werteplan)
  * `running`: Ereignis markieren und Lauf stoppen
  * `stopped`: Neu einrichten
  * Kamera neu verbinden steht im Statusleisten-Menü der Kamera
* **Testmodus** (Lesesperre übergehen) bleibt ein ausdrücklicher Schritt
  im Lauf-Popover. Er hat einen eigenen Bestätigungsdialog im Seitenstil;
  `window.confirm` wird abgelöst. Im Testlauf trägt die Titelleiste ein
  unübersehbares Band „TESTLAUF – Werte nicht freigegeben“ (`--err`-Grund).
* **Dock links**:
  * Einrichtung: Schrittliste mit Teilfortschritt wie im Mock.
  * Lauf: Laufdaten, Statusanteile, Referenz und Werteplan.
  * Fuß: Sitzung sowie Fokus-, Belichtungs- und Weißabgleich-Regler.
* **Ergebnisanzeige** (Lauf, oben rechts) ist das schwerste Element:
  * Statuswort mit Codewort klein daneben, also „Freigegeben VALID“,
    „Wechselt TRANSITION“, „Unlesbar UNREADABLE“, „Veraltet STALE“.
  * Großer Wert mit Einheit, Grund in Klartext, Referenzwert, Spurgüte
    und Alter.
  * Kopfband in der Statusfarbe.
  * Ein veralteter Wert erscheint grau und durchgestrichen. Bei Unlesbar
    steht „Kein Wert“.
* **Inspektor-Tabs**:
  * Einrichtung: Schritt, Fokus, Prüfungen.
  * Lauf: Wert (Tabelle der letzten Datensätze), Ursachen (10-s-Fenster
    aus `rejection_causes`), Nachführung (Rahmenbereiche mit Treffer),
    Referenz.
  * Diagnoseinfos (Diagnosebilder, RAM-Ablage, Kopie) stehen im Tab
    Referenz unter „Ablage“, nicht in der Hauptansicht.
* **Hinweise ohne Aktion**: Freigabehinweis (`release_notice`),
  Toleranzband und Speicherwarnung erscheinen als Zeile in der
  Statusleiste mit Menü, nicht als Banner. Ausnahmen: Speicher `error`
  und Testlauf werden Banner.

## Viewer

* **Bildquellen** über einen Umschalter: Live | Standbild | Abtastbild |
  Entzerrt. Die Quellen kommen aus `setup.overlays`. Nicht vorhandene
  Quellen sind deaktiviert und tragen einen Tooltip mit dem Grund.
* **Navigation**:
  * Mausrad zoomt um den Zeiger, Ziehen verschiebt.
  * Werkzeugleiste: −/+, Prozent, 1:1 und Einpassen.
  * Ebenen-Menü: Anzeige, Raster, Zellen, Rahmenbereiche, Fokus-ROI und
    Wert-Etikett, jede Ebene einzeln schaltbar.
  * Legende, die jedes Markierungs-Symbol erklärt.
* **HUD** wird auf dem Client mit 1-px-Linien gezeichnet. Es ist bei
  jedem Zoom scharf. Die Geometrie stammt immer aus dem Bild, das gerade
  angezeigt wird (siehe Backend-Vertrag, `X-Hud`):
  * Quad der Anzeige
  * Punktraster mit 16 Zellen
  * Zellkästen; unsichere Zelle `--warn` getönt
  * Rahmenbereiche in Magenta mit Suchfenster; `kein Treffer` in `--err`
  * Fokus-ROI, nur in der Einrichtung
  * Wert-Etikett am Quad mit Führungslinie: Wert, Status und Spur
* **Markierungs-Info**:
  * Zeigen öffnet ein Popover, Klicken heftet es an. Beispiele:
    „Rahmenbereich 3 · Mitte 812, 410 · Treffer 0,93 · Suchfenster
    ±12 px“, „Zelle 8 · Bestwert 7 · Abstand 0,41 · unsicher“.
  * Die Zahlen kommen nur aus dem Status, nichts wird erfunden.
  * Konfidenz wird nie als Fehlerwahrscheinlichkeit beschriftet.
* **Rahmenbereiche bearbeiten** (nur `setup_ready`, Bildquelle Standbild
  oder Live):
  * Klick auf freien Rahmen fügt einen Bereich hinzu, Klick auf einen
    Bereich entfernt ihn.
  * Es gilt derselbe Vertrag wie heute: `POST /live/setup/regions`
    mit `proposal_revision`.
  * Die Rückmeldung je Klick kommt aus `centre_results` als Etikett am
    Klickpunkt, zum Beispiel „im Zeichenbereich – nicht geeignet“.
  * Während eine Anfrage läuft, sind Bestätigen und weitere Klicks
    gesperrt.
  * Die Koordinateneingabe x,y bleibt als Tastaturweg im Inspektor.

## Zustandseffekte

Die Effekte liegen auf einer eigenen Canvas-Ebene über dem Bild. Sie
zeigen **wo** das Problem ist, nicht nur dass es eins gibt.

| Zustand | Auslöser (Status) | Effekt | Reduzierte Bewegung |
|---|---|---|---|
| Wechselt | `run.latest.status == transition` | kurzer `--warn`-Puls am Quad-Rand, Tönung nur der wechselnden Zelle, kein Leuchten am Rahmen | Tönung ohne Puls |
| Unlesbar / Rahmen verdeckt / Nachführung verloren | `unreadable`, `tracking_hint.kind`, `reject_reasons` mit `tracking_lost:` | `--err`-Innenleuchten am Viewer. Treibende Punktwolke an den **betroffenen** Quad-Ecken und Rahmenbereichen (Partikel mit Rauschen, niedriges Alpha), schwach an den Viewer-Ecken | statisches Leuchten + markierte Ecken |
| Korrektur läuft | `X-Hud.track.correcting` (neu; wahr, wenn `last_coarse.used` in diesem Bild) | `--teal`-Partikel fließen entlang der Quad-Kanten vom alten zum neuen Quad, Geisterbild des alten Quads blendet aus | Geisterbild ohne Partikel |
| Streamstillstand | `camera.stalled` oder kein neues Bild > 1,5 s | letztes Bild eingefroren, zunehmend unscharf und entsättigt. Mittiges Feld „Kein neues Kamerabild seit 3,4 s“ mit laufendem Alter. Ergebnis auf Veraltet | Unschärfe ohne Verlauf |
| Verbindung zur Werkbank verloren | Statusabruf scheitert > 1,5 s (heutige `connectionView`) | ganze Oberfläche gedimmt, Band oben „Verbindung zur Werkbank verloren – Werte veraltet“ mit Sekunden | gleich |
| Kamera neu gestartet | `setup.step == kamera` | Bild 0,6 s dunkel, Hinweis „Kamera wird mit festen Reglern neu gestartet“ | gleich |

Vorrang bei gleichzeitigen Zuständen: Verbindung verloren >
Streamstillstand > Unlesbar/verloren > Korrektur > Wechselt. Es läuft
immer nur der Effekt mit dem höchsten Vorrang. Die Effekte bleiben unter
4 ms Zeichenzeit je Bild bei 1440 px. Fällt die Bildrate des Clients
unter 20 fps, halbiert sich die Partikelzahl.

## Meldungen

| Ereignis | Form | Text (Produkttexte, wörtlich) |
|---|---|---|
| Rahmen verdeckt | Hinweis unten rechts im Viewer, bleibt bis zur Erholung | „Rahmenbereiche verdeckt oder verschoben – Kamera und Sicht prüfen“ / „Rahmen verdeckt? Hand oder Gegenstand vom Rahmen nehmen. Werte werden nicht freigegeben.“ |
| Streamstillstand | Hinweis | „Streamstillstand: kein neues Kamerabild“ |
| Werteplan-Schritt, Lauf gestartet/gestoppt, Marke gesetzt | Hinweis, schließt nach 4 s | — |
| Vorschlag mit WARNUNG | Hinweis | „Vorschlag mit WARNUNG“ + Grund |
| **Anzeige hat sich bewegt** (`tracking_hint.kind == anzeige_bewegt`) | **Dialog**, blockierend | „Anzeige hat sich bewegt (ca. N px (Ecken), X Grad) – Werte werden nicht freigegeben. Bitte neu einrichten.“ Knöpfe: Neu einrichten · Lauf stoppen · Weiter beobachten |
| Testlauf starten, Werteplan anwenden | **Dialog** (ersetzt `window.confirm`) | heutige Texte aus `live.js` |
| Fehler einer Aktion (HTTP 409/400) | Hinweis `--err`, bleibt | Servertext |

Hinweise stapeln sich mit höchstens 3 sichtbaren und sind per Tastatur
schließbar. Ein Dialog hält den Fokus fest und schließt mit Esc als
„Weiter beobachten“, nie als Stopp. Ein gleicher Hinweis wird nicht
doppelt gestapelt.

## Einrichtungs-Fortschritt und Fokuskurve

* **Schrittliste**: fokus → kamera → belichtung → standbilder →
  vorschlag, danach „Prüfen & Bestätigen“. Jeder Schritt zeigt seinen
  Zustand (erledigt/läuft/ausstehend/fehlgeschlagen), die Dauer und eine
  Zeile Ergebnis. Der laufende Schritt zeigt Teilschritte:
  * Fokus: „Probe 6/9“
  * Belichtung: „Runde 1/4“
  * Standbilder: Versuch n/3, Mitteln, Zellentext, Raster, Stabilität
    mit Countdown, zweites Standbild, Gegenlesen
* **Fokuskurve** (Inspektor-Tab Fokus):
  * Punkte erscheinen live in Messreihenfolge.
  * Bestwert markiert, Schwellenlinie bei 85 % des Bestwerts.
  * Danach die Gegenprüfung, zum Beispiel „624 ≥ 536 (99 %)“.
  * Im Viewer zeigt die Fokus-ROI die aktuelle Schärfe.
* **Belichtung**: Pegel p80 als Balken im Band 115–150 mit Ziel 130,
  Runden mit Belichtung, Gain und Weißabgleich.
* **Prüfungen**: Raster mit Spalten Prüfung | Status | Hinweis.
  Prüfungen erscheinen, sobald `assist_measure` sie meldet, nicht erst
  mit dem Vorschlag. Die Spalte Hinweis zeigt `check_reasons`.
* **Bestätigen** (Inspektor, Tab Schritt, bei `setup_ready`), Felder wie
  heute:
  * Name
  * „Einheit mV/V und Format geprüft“
  * bei WARNUNG „WARNUNG zur Kenntnis genommen“
  * wenn möglich „Angepasste Toleranz ×f verwenden …“
  * `proposal-block`-Hinweis bei Lesesperre

  Die Felder setzen sich bei neuer `proposal_revision` oder
  `session_id` zurück.

## Lauf

* **Zeitleiste** (40 s, scrollend):
  * Statusband je Bild in den Farben Freigegeben/Wechselt/Unlesbar/Veraltet.
  * Darüber die Wertspur **nur aus freigegebenen Werten**, als Stufen,
    nie geglättet.
  * Ereignismarken: Werteplan, Bedienermarke, Störungen.
* **Abgleich gegen Referenz**:
  * Während des Laufs zeigt die Ergebnisanzeige den neuesten
    Referenztext (`reference.latest`).
  * Die Zahl der Fehllesungen erscheint **erst nach Laufende** aus der
    bestehenden Auswertung (`reference_eval`).
  * Während des Laufs steht dort „Abgleich nach Laufende“. Ein vorläufiger
    Live-Abgleich ist ein offener Punkt (OP-1).
* **Laufende**: Zusammenfassung im linken Dock mit Dauer, Bildern,
  Statusanteilen, Fehllesungen gegen Referenz, Ablage und Endgrund.

## Einarbeitung

1. **Rundgang**
   * 8 Stationen: Titelleiste und Aktionen, Ablauf-Dock, Viewer mit
     Werkzeugleiste, HUD-Legende, Inspektor, Ergebnisanzeige,
     Zeitleiste, Statusleiste.
   * Je Station ein hervorgehobener Bereich plus 1–3 Sätze; überspringbar.
   * Startet beim ersten Besuch über ein Angebot („Rundgang starten /
     Später“), sonst über Hilfe › Rundgang. Der Merker liegt in
     `localStorage`, mit try/catch geschützt.
   * Läuft nie automatisch über einen laufenden Lauf.
2. **Übungslauf** (Hilfe › Übungslauf)
   * Die echte Oberfläche läuft auf einem **clientseitigen Szenario**.
     Es ist das Zeitachsen-Modell des Mocks, erzeugt Status-Objekte im
     Format von `/live/status` und Bild plus HUD aus `still.jpg`.
   * Der Bediener klickt selbst: Einrichtung starten, Rahmenbereich
     bearbeiten, Bestätigen mit Namen, Lauf starten, auf den Dialog
     reagieren, Lauf stoppen.
   * An jeder Station steht ein kurzer Auftrag im Rundgang-Stil
     („Klicke auf Bestätigen …“).
   * Im Übungsmodus geht **keine Anfrage** an `/live/*` mit POST. Die
     Kamera-Vorschau ist ersetzt, und Titelleiste und Statusleiste tragen
     das Band „Übungslauf – keine Messung“.
   * Nur möglich bei Zustand `idle`, `stopped` oder `setup_failed`.
     Ein laufender Lauf oder eine laufende Einrichtung sperrt ihn.
3. **Hilfe-Dock** (rechts, ersetzt den Inspektor bis zum Schließen)
   * Glossar: Statuswörter, alle 12 Prüfungen, alle Markierungen, alle
     Nachführungs- und Lesegründe aus `REASONS` / `LIVE_CAUSE_TEXT`.
   * Suche.
   * Je Begriff ein Link ins Wiki („Bedienen“).
   * Die Texte liegen in `static/live/help/glossar-de.json`. Gründe
     werden zur Laufzeit aus dem Status ergänzt, nicht doppelt gepflegt.

## Vorschau-Bildrate

* Neuer Strom `GET /live/preview.mjpg`, Teile als
  `multipart/x-mixed-replace`, 960×540, JPEG-Qualität 80.
* Ziel 15 fps. Der Server **fällt auf 5 fps**, solange eine der beiden
  Bedingungen gilt:
  1. Der Leser-Thread hat in den letzten 2 s mehr als 10 % der neuen
     Kamerabilder übersprungen (`skipped_recent > 0.10`).
  2. Die eigene Kodierzeit liegt im Mittel über 25 ms.

  Zurück auf 15 fps geht es nach 5 s ohne beide Bedingungen.
* Je Bildsequenz wird höchstens einmal kodiert (Cache nach Sequenz).
  Mehrere Betrachter teilen sich die Kodierung.
* Die Statusleiste zeigt die tatsächliche Rate und den Grund der
  Drosselung („Vorschau 5 fps – Messung hat Vorrang“).
* `GET /live/preview.jpg` bleibt für Werkzeuge erhalten, zeichnet das
  Quad aber nicht mehr ins Bild.

## Backend-Vertrag (neu)

Nur Erweiterungen; bestehende Felder bleiben unverändert.

**`status.setup.progress`** (solange eine Einrichtung läuft oder lief):

```json
{"steps": [{"key": "fokus", "state": "done", "elapsed_s": 21.3},
           {"key": "kamera", "state": "done", "elapsed_s": 2.0},
           {"key": "belichtung", "state": "done", "elapsed_s": 4.1},
           {"key": "standbilder", "state": "running", "elapsed_s": 9.0},
           {"key": "vorschlag", "state": "pending", "elapsed_s": null}],
 "attempt": 1, "attempts_max": 3,
 "phase": "stabilitaet",
 "wait": {"elapsed_s": 9.0, "total_s": 15.0}}
```

`state` ∈ `pending|running|done|failed`. `phase` ∈ `mitteln|zelltext|raster|stabilitaet|zweites_standbild|gegenlesen|null`.

**`status.setup.focus`**:
`{"method": "climb|sweep", "samples": [[48, 630.36], …], "verify": {"score": 624.47, "threshold": 535.80} | null}`.
Die Samples erscheinen live in Messreihenfolge.

**`status.setup.exposure`**:
`{"target": 130, "band": [115, 150], "rounds": [{"level": 124.0, "controls": {…}}]}`.

**`status.setup.checks_live`**: `{name: {"status": "OK|WARNUNG|FEHLER|NICHT_GEPRUEFT", "reason": str|null}}`.
Kommt aus dem `report`-Haken von `assist_measure`, solange noch kein
Vorschlag existiert.

**`status.run.counts`**: `{"valid": n, "transition": n, "unreadable": n, "stale": n}`,
je Bild gezählt (nicht der 60-s-`summary`).

**`status.run.recent`**: `[[t_ms, "v|t|u|s", value|null], …]` über die
letzten 60 s in 250-ms-Eimern. Je Eimer zählt der schlechteste Status
(s > u > t > v) und der letzte freigegebene Wert. Damit füllt der Client
die Zeitleiste nach einem Neuladen.

**`X-Hud`-Kopf je MJPEG-Teil** (kompaktes JSON, ≤ 2 KB; Koordinaten im
Kamerabild 1920×1080):

```json
{"seq": 51234, "cap_ns": 1730000000000, "w": 1920, "h": 1080,
 "rec": {"seq": 51233, "status": "valid", "text": "+0.62427", "unit": "mV/V",
         "reasons": [], "age_s": 0.04},
 "track": {"quad": [[810.2,510.7], …], "score": 0.93, "shift_px": 0.4,
           "rotation_deg": 0.0, "reason": null, "correcting": false,
           "regions": [{"c": [528, 292], "s": 15, "peak": 0.92, "ok": true}, …]},
 "cells": [{"i": 8, "best": "7", "margin": 0.41, "uncertain": true}, …],
 "proc": {"fps": 14.8, "latency_ms": 46, "skipped_recent": 0.02},
 "preview": {"fps": 15, "throttled": null}}
```

`track` und `cells` gibt es nur während eines Laufs, außerhalb ist das
Feld `null`. `cells` enthält jede Zelle, nicht nur Testläufe. Weitere
Kopfzeilen sind `X-Frame-Sequence` und `X-Capture-Ns`.

## Technik

* **Ohne Build.** Native ES-Module unter
  `src/dispread/workbench/static/live/`, Canvas 2D und SVG. Keine
  Bibliothek, außer den lokal abgelegten Schriften. Der Mock beweist,
  dass das reicht.
* Der Client liest den MJPEG-Strom per `fetch()` und `ReadableStream`,
  zerlegt die Teile, dekodiert per `createImageBitmap` und zeichnet Bild
  und HUD aus demselben Teil. So ist das HUD immer deckungsgleich. CSP
  bleibt `connect-src 'self'; img-src 'self' blob:`.
* Statusabruf bleibt `/live/status` alle 500 ms. Er liefert Zustand,
  Docks und Inspektor; der Strom liefert Bild und HUD.
* `live.js` wird zu `live/app.js`. Die reinen Funktionen `statusView`
  und `connectionView` ziehen unverändert nach `live/model.js` um. Ihr
  bestehender Testsatz (`tests/live_client.test.mjs`) zieht mit.

## Wahrheitsregeln (unverändert, für jede Aufgabe bindend)

1. Ein Wert älter als 0,5 s (`latest_age_s`) oder ohne gültige Antwort
   seit 1,5 s ist **Veraltet**, nie Freigegeben.
2. Im Testlauf wird nichts freigegeben. Die Ergebnisanzeige zeigt
   „UNREADABLE“ statt eines Werts. Eine Leser-Vermutung erscheint nur
   bei Wechselt oder Unlesbar, nie neben Freigegeben oder Veraltet.
3. Die Wertspur zeigt nur freigegebene Werte und glättet Sprünge nie.
4. Konfidenz und Spurgüte heißen „Spur“ oder „Treffer“, nie
   „Wahrscheinlichkeit“ oder „Sicherheit %“.
5. Bestätigen und Lauf starten gehen nur über HTTPS mit CSRF (Konzept
   §4). Der Übungslauf sendet nie.
6. Rückmeldungen des Servers (409/400) erscheinen wörtlich.

## Tests und Abnahme

* `node --test`: `model.js` (der bisherige Testsatz plus neue Fälle),
  `mjpeg.js` (Zerlegen von Teilen über Chunk-Grenzen), `scenario.js`
  (Status-Objekte bestehen dieselbe Formprüfung wie der Fake-Server),
  `effects.js`-Vorrang.
* `pytest`: Fortschritt, Fokus-Samples, `checks_live`, `counts`/`recent`,
  `X-Hud`, Bildraten-Drosselung (Zeit injiziert), Kodier-Cache.
* Playwright (`playwright.live.config.ts`): Ablauf Einrichtung →
  Bestätigen → Lauf → Stopp gegen `tests/live_ui_server.py` mit neuen
  Feldern und MJPEG-Attrappe. Dazu Verbindungsverlust, Streamstillstand,
  Dialog „Anzeige bewegt“, Rahmenbereich bearbeiten, Rundgang und
  Übungslauf. Screenshots bei 1280×800, 1440×900 und 1920×1080 gegen den
  Mock prüfen (Augenschein).
* **Hardware-Abnahme**:
  1. Eine echte Einrichtung und ein Lauf von mindestens 30 min am Aufbau.
  2. Die Vorschau hält im Lauf ≥ 12 fps.
  3. Der Leser überspringt nicht mehr Bilder als ohne Vorschau (Vergleich
     mit dem Lauf vom 2026-10-30).
  4. Die CPU-Zahl kommt in VALIDATION.md.

## Nicht-Ziele

Die alte Seite `/` (Controller, Datensätze, Terminals) bleibt
unverändert. Ebenfalls außerhalb liegen eine helle Ansicht, eine
Handy-Ansicht, Mehrsprachigkeit, Änderungen am Messpfad und eine
GSVmulti-Ausgabe (OQ-07).

## Offene Punkte

* **OP-1:** Soll es einen vorläufigen Live-Abgleich gegen die Referenz
  geben? Er könnte die Fehllesungen schon während des Laufs zählen, mit
  ≥ 0,8 s Verzug wegen `GUARD_NS`. Bis zur Entscheidung gilt
  „Abgleich nach Laufende“.
* **OP-2:** Der alte Controller verbraucht dauerhaft 5 Hz
  (`controller.py`, Publish alle 0,2 s). Er soll pausieren, solange
  `/live` aktiv ist. Das wird erst gemessen (Aufgabe 13) und nur bei
  Bedarf umgesetzt.
* **OP-3:** Wie sollen Tablets bedient werden (Berührung statt
  Mausrad)? Es gibt keinen Bedarf, nicht geplant.

## Anhang A: heutige Schnittstelle (Bestandsaufnahme 2026-10-30, `origin/master` 41dfafe, seither unverändert)

* aiohttp über TLS, Handler per `asyncio.to_thread`.
  Routen in `workbench/live_api.py:101-111`. MJPEG-Muster vorhanden in
  `workbench/server.py:154-184` (alter Controller).
* `preview_jpeg` (`live/service.py:307`) skaliert je Abruf neu auf
  960 px, zeichnet das Quad ein und kodiert mit Qualität 80, ohne Cache.
* Einrichtung (`live/service.py:428-538`): Die Schritte heißen
  `fokus|kamera|belichtung|standbilder|vorschlag`. Fokus-Paare entstehen
  in `climb_focus.sample` (`focus_sweep.py:58`) und werden erst nach dem
  Schritt geschrieben. `assist_measure(report=…)` hat einen Haken, den
  der Dienst nicht übergibt. Die 15-s-Stabilität ist ein einzelnes
  `sleep(stability_s)` (`live/setup.py:501`).
* Daten je Bild im Lauf: `locator.last_track` (Quad, Verschiebung,
  Drehung, Score, Grund), `_tracker.last_coarse`, Zelldaten in
  `pipeline.last_read.diagnostics["cells"]` und Zeiten in `trace`. Davon
  steht heute nichts im Status. Die Treffer der Rahmenbereiche sind nur
  lokale Variablen in `FrameTracker.update`.
* `run.summary` wird nur alle 60 s neu gebaut (`session.py:74`,
  `:439-442`).
