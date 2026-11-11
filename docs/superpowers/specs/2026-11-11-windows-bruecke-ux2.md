# Windows-Brücke UX2: Überarbeitung von Bedienung und Oberfläche

Stand 2026-11-11, Branch `feat/bruecke-ux` (von `feat/bruecke-ui` 7223a61).
Auftrag von Leonhard am 2026-11-11 nach dem ersten Lauf mit echten Werten.
Gilt zusätzlich zu `windows/bridge/PRODUCT.md`, `windows/bridge/DESIGN.md` und
der Spec `2026-11-06-windows-bruecke-design.md`. Wo dieses Dokument etwas
ändert, gilt es; alle Wahrheitsregeln aus DESIGN.md bleiben (Proven-Green,
One-Accent, Word-Beside-Color, DUT-Sperrzeile, „Weitergabe ist nicht Empfang“).

Modus der Oberfläche: **Operate**. Windows 11 nativ bleibt die Welt
(Segoe UI Variable, Mica, Karten mit 1-px-Rand, Systemakzent). Es ist eine
Verfeinerung der bestehenden Welt, kein Stilwechsel.

## Entscheidungen des Nutzers (2026-11-11)

1. **Session-Datei** wird aus der belegten Vorlage erzeugt: Kopie von
   `docs/quellen/bruecke-testlauf-2026-11-06/Session-COM8.ucf`
   (SHA-256 `6e553a1e…5992`, identisch mit der in den Tests vom 06.11. und
   11.11. benutzten Session). Geändert werden **nur** `[ch1] ComNr`,
   `[ch1] Name` („Chan. N_1“) und `[UserDevice] ComNo`. Alles andere bleibt
   byte-gleich (Zeilenenden, Kodierung, `[CopyPaste]`). Die Datei gilt als
   „nicht abgenommen“, bis der Windows-Testlauf das Öffnen in GSVmulti und
   den Empfang bestätigt (N3/OQ-53 bleiben bis dahin offen).
2. **UART direkt** ist in der EXE ein Einrichtungshelfer: Adapter erkennen,
   COM-Port prüfen, Verdrahtung zeigen, Session für genau diesen Port
   erzeugen. Danach zeigt die App nur, ob der Adapter steckt. Werte laufen an
   der App vorbei; sie startet dafür keinen Worker und braucht keine Kopplung.
3. **Moduswahl** über einen Knopf im Kopf (Symbol + Name des Wegs + Chevron).
   Er öffnet ein eigenes Fenster mit drei Karten untereinander. Beim ersten
   Start ohne gewählten Weg öffnet es sich von selbst.
4. **UART-Baudrate** Pi↔Brücke bekommt eine einzige Quelle (Nutzerregel
   „eine Quelle für veränderliche Werte“) und wird auf 460 800 Baud
   angehoben, sobald beide Seiten sie aus derselben Quelle beziehen. Die
   GSVmulti-Seite (com0com, Session-Vorlage) bleibt bei 115 200; das ist ein
   eigener, aus der Vorlage gelesener Wert.

## Gestaltung

### Symbole statt Text

* Symbolsatz: **Fluent UI System Icons** (Microsoft, MIT), Variante
  „Regular“, 20 px, als SVG im Paket unter `ui/icons/` mit `LICENSE`.
  Gerendert mit `QSvgRenderer`, eingefärbt aus den Tokens (`text`, `text2`,
  Status- oder Akzentfarbe), gecacht je (Name, Farbe, Größe, DPR). Keine
  Unicode-Zeichen oder Emoji als Symbole; das bestehende „×“ im Flyout
  verschwindet.
* Jeder reine Symbolknopf hat **Tooltip und Screenreader-Namen**, 32 × 32,
  flach (`flat`), Hover `ctrl_hover`. Tastaturfokus wie bisher.
* Konkret: Suche/Neu suchen → Symbol `arrow_sync`; Kopieren → `copy`;
  Fenster schließen → nativer Rahmen; Fußleiste → Symbolleiste (s. u.).

### Typografie und Gliederung

Stufen (Qt-Punkte; DESIGN.md ergänzt):

| Rolle | Größe/Gewicht | Einsatz |
| --- | --- | --- |
| Titel | 15 pt / 600 | Pi-Name im Kopf, Fenstertitel im Inhalt |
| Abschnitt | 11 pt / 600 | Überschriften in Fenstern (Einstellungen, Moduswahl) |
| Text stark | 10,5 pt / 600 | Zustandssatz, Kartentitel, Infobar-Titel |
| Text | 10,5 pt / 400 | Fließtext, Knöpfe |
| Beschriftung | 9 pt / 400, `text2` | Feldnamen, Zweitzeilen, Zeiten |
| Beschriftung stark | 9 pt / 600 | Statuswörter |
| Daten | Cascadia Mono 9 pt | Pi-ID, Endpunkt, Fingerabdruck, Ports, Dateinamen |

Feldname über Wert (Beschriftung über Daten) ist das Muster für alle
technischen Angaben. Keine Kicker/Eyebrows über Überschriften.

### Kopf

Zeile 1: Pi-Name (Titel) · rechts Moduswahl-Knopf (Symbol des Wegs,
Kurzname „Netzwerk“ / „UART · Brücke“ / „UART direkt“, Chevron), Schloss
wie bisher. Zeile 2: Herzschlag-Punkt + Zustandssatz. Zeile 3: DUT-Sperrzeile
(unverändert, Pflicht).

**Herzschlag:** 8-px-Punkt links neben dem Zustandssatz. Bei jedem neuen
`activity_seq` ein kurzer Puls (Deckkraft/Größe 250 ms, ease-out). Farbe
`text2` (neutral, kein Grün: der Puls belegt nur Kontakt zum Pi, keine
Weitergabe). Ohne Verbindung ruht der Punkt hohl (`stroke_strong`). Bei
Verbindungsaufbau/Backoff läuft stattdessen ein kleiner Ring (ProgressRing).

### Prüfpunkt-Kacheln (bisher Chips)

* Raster 3 × 2 bleibt. Jede Kachel: oben links **Komponenten-Symbol**
  (`cube` Komponenten, `usb_stick`/`serial_port` UART, `developer_board` Pi,
  `arrow_export_ltr` Ausgabe, `arrow_forward` Weitergabe, `data_line`
  GSVmulti; Namen gegen das Paket prüfen), daneben Name (Beschriftung,
  `text2`); oben rechts **Info-Symbol** (`info`, 16 px, `text2`), dessen
  Tooltip in 1–3 Sätzen erklärt, was der Prüfpunkt bedeutet und was er
  **nicht** bedeutet (Texte in `texts.CHIP_HELP`). Darunter Statussymbol +
  Statuswort (Beschriftung stark), optionale Zweitzeile.
* Hover über der Kachel: Kurz-Tooltip mit der Zweitzeile in voller Länge.
* Klick öffnet das **Detailfenster** (s. u.), nicht mehr ein Popup.
* Zustandswechsel einer Kachel: 200 ms Farbübergang des Hintergrunds
  (kurzer Ton der neuen Stufe, dann zurück zu `card`). Nur bei echter
  Änderung, nie beim Neuzeichnen.

### Fenster statt Popups

* Neue Basis `ToolWindow(QDialog)`: **nicht modal**, nativer Windows-Rahmen
  mit Titelleiste (beweglich, Schließen-Knopf), Besitzer = Hauptfenster
  (bleibt darüber, eigener Taskleisteneintrag nein), Esc schließt, Position
  je Fensterart für die Laufzeit gemerkt, höchstens eine Instanz je Art
  (erneutes Öffnen holt das vorhandene nach vorn). Inhalt scrollt, wenn er
  nicht passt; Mindestbreite 360.
* Ersetzt `Flyout` (Kachel-Details, „Gekoppelte Pi“, Schloss-Erklärung,
  „Details“). `Qt.Popup` wird nirgends mehr benutzt.
* Hover-Erklärungen sind Tooltips (QToolTip, gestylt), keine Fenster.
* Bestätigungen, die die Übertragung beenden (Beenden, Trennen), bleiben
  modale Dialoge.

### Kopierbare Werte

Baustein `CopyField`: Feldname (Beschriftung) über Wert (Daten, auswählbar,
bricht um) mit Kopierknopf rechts (`copy`). Klick kopiert in die
Zwischenablage, das Symbol wechselt für 1,5 s zu `checkmark` in `ok`-Farbe,
Tooltip „Kopiert“. Einsatz: Pi-ID, Endpunkt, Fingerabdruck (vollständig, nie
gekürzt), Ports, Session-Pfad, Version, Protokoll, Lauf-ID.

### Fußleiste → Symbolleiste

Links: **Einstellungen** (`settings`), **Protokolle exportieren**
(`document_arrow_down` o. ä.), **Info** (`info`, bisher „Details“).
Rechts: Version (Beschriftung), **Beenden** (`power`, Tooltip
„Brücke beenden …“). „Einrichtung ändern …“ wandert in die Einstellungen und
in die Moduswahl.

### Protokolle exportieren (bisher „Diagnose“)

Der Knopf heißt jetzt „Protokolle exportieren“ und öffnet ein Fenster, das
vor dem Speichern sagt, **was drin ist** (aus `diagnostics_contents()`):
`summary.json` (Version, Bereitschaft, Worker-Zustand, Weg, Portpaar, Zähler
der Übergaben je Ergebnis) und `details.jsonl` (Ereignisprotokoll der App,
Zugangsdaten redigiert, keine Messwerte). Knopf „Speichern unter …“.
Danach im selben Fenster: Häkchen, Pfad als CopyField, „Ordner öffnen“.
Es ist ausdrücklich **kein** Gesundheitscheck.

### Moduswahl-Fenster

Drei Karten untereinander (`MODES`), je: Symbol, Name, ein Satz
Erklärung, Statuszeile aus `ModeInfo` (Symbol + Wort, Proven-Green), rechts
Abzeichen „Aktiv“ (Rand + Text, nicht grün) beim aktiven Weg. Karte ist ein
Auswahlknopf (Radio-Semantik, Pfeiltasten). Fuß: „Abbrechen“ / „Wechseln“
(Akzent). Nicht wählbare Karten sind gedimmt mit Grund. Wechsel auf einen
nicht eingerichteten Weg startet dessen Einrichtung.

Erklärungen (Entwurf, in `texts.MODE_TEXT`):
* **UART direkt** – „Das Pi-Kabel steckt am GSVmulti-PC, GSVmulti liest
  den Adapter direkt. Die Brücke hilft nur beim Einrichten.“
* **UART über Brücke** – „Das Pi-Kabel steckt an diesem PC, die Brücke
  gibt die Werte an GSVmulti weiter.“ (Rate aus `uart_baud` ableiten, nicht
  fest hinschreiben.)
* **Netzwerk über Brücke** – „Der Pi ist über LAN oder Tailscale
  verbunden, verschlüsselt. Die Brücke gibt die Werte an GSVmulti weiter.“

### Einstellungen-Fenster

Abschnitte (Abschnitt-Überschrift, Karten darunter):
1. **Weg** – aktiver Weg (Knopf öffnet Moduswahl), „Einrichtung erneut
   durchlaufen“.
2. **Pi** – Name, Pi-ID, Endpunkt (editierbar mit Prüfung), Fingerabdruck
   (CopyFields), „Beim Start automatisch verbinden“ (Schalter, sofort
   gespeichert, mit Häkchen bestätigt), gekoppelte Pi.
3. **Ports** – Brückenseite / GSVmulti-Seite (Auswahl mit Prüfung),
   USB-Adapter (Auswahl mit Prüfung), Baudraten als reine Anzeige.
4. **GSVmulti-Session** – „Session-Datei erzeugen …“ (Speichern-Dialog,
   Standardname `GSVmulti_<Pi>_<COMx>.ucf`), Ergebnis mit Pfad, Hinweis
   „nicht abgenommen“, Kurzanleitung „in GSVmulti öffnen“.
5. **Protokolle** – Export (wie oben).
6. **Über** – Version, Kanal, Protokoll (CopyFields).

Während einer aktiven Übertragung sind Weg, Pi und Ports schreibgeschützt
(Schloss-Symbol + Grund), Anzeige und Kopieren bleiben möglich.

### Einrichtung

* **Verlassen:** Im Schrittkopf rechts ein Symbolknopf `dismiss`
  („Einrichtung verlassen“), sichtbar wenn `setup_leavable`. Ruft
  `leave_setup()`. Ohne gespeicherte Konfiguration landet man im Betrieb mit
  Infobar „Nicht eingerichtet“ und Knopf „Einrichtung starten“.
* **Bestätigende Eingaben:** Baustein `ValidatedField` (Eingabefeld oder
  Auswahl) mit Statusfläche rechts und Meldungszeile darunter:
  leer → nichts; tippt/ändert → nach 500 ms Ruhe läuft die Prüfung
  (ProgressRing 16 px), Ergebnis `ok` (Häkchen in `ok` + Meldung),
  `warn`, `err` (Symbol + Meldung + nächste Aktion). Nur echte Prüfungen aus
  dem Controller (`check_*`), keine Attrappen. Ein `ok` darf erst nach
  bestandener Prüfung erscheinen.
* Übernommene Schritte bekommen im Schrittkopf das Häkchen (wie bisher) und
  zusätzlich eine kurze Bestätigungszeile „Gespeichert“ mit Häkchen, die
  nach 2 s ausblendet.
* „Suche wiederholen“ → Symbolknopf `arrow_sync` neben der Liste; während
  der Suche dreht das Symbol (oder ProgressRing an seiner Stelle).
* Schrittwechsel: 200 ms Überblendung mit 12 px Versatz in Laufrichtung.

### Bewegung

Nur wo sie Zustand erklärt. Dauer 150–250 ms, ease-out, Ausgang schneller
als Eingang. Alles über einen zentralen Schalter `theme.motion_enabled()`;
unter Windows folgt er „Animationseffekte“ (SPI_GETCLIENTAREAANIMATION),
sonst an. Aus = Endzustand sofort, Bedeutung bleibt (Häkchen erscheint
trotzdem).

| Ort | Bewegung |
| --- | --- |
| Herzschlag | Puls je Pi-Kontakt |
| Verbindungsaufbau, Backoff, Prüfungen, Suche | ProgressRing (unbestimmt) |
| Laufende Aufgabe ohne eigenen Platz (Export, Session) | 2-px-Ladebalken unbestimmt unter dem Kopf |
| Kachel-Zustandswechsel | Farbübergang 200 ms |
| Wechsel Betrieb ↔ Einrichtung, Schrittwechsel | Überblendung + Versatz 200 ms |
| Kopieren, Prüfung ok, gespeichert | Symbolwechsel mit 150 ms Skalierung |
| Fenster öffnen | Systemanimation, keine eigene |

Keine Dauerschleifen außer ProgressRing/Ladebalken während echter Arbeit.
Versteckte Fenster stoppen ihre Animationen.

## Backend-Vertrag (Codex)

Die Oberfläche hängt nur an `ui/port.py`. Neu (dort definiert):
`CheckResult`, `ModeInfo`, `PortChoice`, `SessionExport`, neue
`UiContext`-Felder und die Methoden `modes`, `select_mode`, `leave_setup`,
`list_ports`, `list_adapters`, `check_endpoint`, `check_port_pair`,
`check_adapter`, `check_pairing_code`, `export_session_file`,
`diagnostics_contents`. Der `AppController` erfüllt sie; `ui/fake.py` spielt
sie für Tests und `--demo-ui` nach.

Prüfungen (alle mit Zeitgrenze ≤ 3 s gesamt, ohne Zugangsdaten in Texten,
thread-sicher, blockieren nie den GUI-Thread):
* `check_endpoint`: Syntax → Namensauflösung → TCP-Verbindung zum Port →
  TLS-Handshake und Vergleich des Zertifikat-Fingerabdrucks mit dem Profil.
  Ergebnis nennt die Stufe, an der es scheitert.
* `check_port_pair`: beide vorhanden, verschieden, als com0com-Paar
  erkennbar (sonst `warn`), nicht belegt (exklusiv öffnen und sofort
  schließen; während eigener Übertragung nicht prüfen, sondern `ok` aus dem
  Zustand).
* `check_adapter`: vorhanden, USB-Seriell, exklusiv zu öffnen mit der
  UART-Baudrate, wieder freigegeben.
* `check_pairing_code`: nur Format.

Weitere Backend-Punkte: `uart_direct` als dritter Weg im Controller (kein
Worker, keine Kopplung, Adapterpräsenz per `serial.tools.list_ports` ohne
Konsolenfenster, höchstens alle 2 s); Session-Generator aus der Vorlage
(eigenes Modul, Tests mit byte-genauem Vergleich gegen COM4/COM8-Belege);
Baudrate als eine Quelle (Pi-Konstante im gemeinsamen Paket
`dispread.bridge`, im Profil mitgegeben, Windows nimmt den Profilwert, sonst
die Konstante; alle festen `115200` der Pi↔Brücke-Strecke ersetzt; die
GSVmulti-Seite liest ihre Baudrate aus der Vorlage); `activity_seq`;
`setup_leavable`; `CREATE_NO_WINDOW` für jeden Subprozess (TODO-Punkt).

## Nachweis

* Linux offscreen: Tests unter `windows/bridge/tests` mit
  `/mnt/ssd/picam-dev/qt-venv/bin/python -m pytest`, Bildschirmfotos aller
  Zustände hell/dunkel bei 380 × 560 und 440 × 720.
* Windows: Prüfanleitung `windows/bridge/PRUEFUNG-UX2.md` für eine lokale
  Claude-Sitzung auf Leonhards PC; deren Bericht fließt in die nächste Runde.

## Runde 3: Gestaltung nach Leonhards Rückmeldung (2026-11-11)

Leonhard nach Teil B der Windows-Prüfung, wörtlich: „Generell bin ich nicht
wirklich mit dem design zufrieden. Die animationen funktionieren nicht und
sind bloß ein flackern. Es wird viel text verwendet der das ui unübersichtlich
macht. infos wie com port, datei locations, frequenz usw... könnte man in
graue felder packen so das erkennbar ist das diese werte sich ändern können
und keine standard infos/texte sind). bitte reduziere den text, und lasse das
ui für sich sprechen (funktionen, bedeutung, usw... soll durch das design
kommuniziert werden)“

Leitsatz: **Werte sind Felder, Zustände sind Formen, Text ist die Ausnahme.**

### R3-1 Wertfeld
Jeder veränderliche Wert (COM-Port, Pfad, Baudrate, Frequenz, Pi-ID,
Endpunkt, Fingerabdruck, Lauf-ID, Version, Zähler, Zeiten in Details) steht
in einem **Wertfeld**: Grund `mica2` (dunkel `ctrl`), Radius 4, Polster 3/8,
Cascadia Mono 9 pt, Textfarbe `text`. Bezeichner davor oder darüber in
Beschriftung `text2`. Kopieren: Klick auf das Feld oder ein Kopiersymbol,
das bei Hover/Fokus im Feld rechts erscheint; danach Häkchen 1,2 s. Sätze
enthalten **keine** Werte mehr („Die Session verweist auf COM5“ →
Bezeichner „Port“ + Wertfeld `COM5`). Ersetzt den bisherigen CopyField-Look.

### R3-2 Textbudget
* Karte, Infobar, Kachel: höchstens **ein** kurzer Satz (Richtwert ≤ 70
  Zeichen); Kachel-Zweitzeile höchstens drei Wörter oder ein Wertfeld.
* Erklärungen gehen ins ⓘ-Tooltip oder ins Detailfenster, nie als Absatz in
  die Hauptansicht.
* Wiederkehrende Einschränkungen werden **Abzeichen** (Umriss
  `stroke_strong`, Beschriftung 9 pt, Radius 4, kein Grün): „nicht
  abgenommen“, „Demo“, „Testfreigabe“, „kein Empfangsnachweis“,
  „Einkanal“. Ein Abzeichen trägt ein ⓘ-Tooltip mit der Erklärung (z. B. der
  F3-Wortlaut bei „Einkanal“).
* Keine Dopplung: Was die DUT-Sperrzeile sagt, sagt keine Infobar noch
  einmal. Infobar nur bei Handlungsbedarf oder Störung; im Normalbetrieb
  (Lauf läuft, Ausgabe gesperrt) **keine** Infobar.
* Moduswahl-Karten: Name + ein Satz + Status; Baudraten nur im Detail.

### R3-3 Session (Einrichtung E4/D3 und Einstellungen)
Eine Ergebniszeile: neutrales Häkchen, Wertfeld mit Pfad, Symbolknöpfe
„Ordner öffnen“ und „Neu erzeugen“. Darunter Checkliste „In GSVmulti
einstellen“: je Punkt ein Kontrollkästchen mit kurzem Text + ⓘ
(„Record Hidden Channels einschalten“ – Pflicht, nur bei ausgeblendeten
Kanälen, hält „Weiter“ zurück; „Autoscale Y für Kanal 8_1 aus“ – Empfehlung;
„Session in GSVmulti öffnen“). Einkanal-Warnung als Abzeichen „Einkanal“ mit
ⓘ, nicht als Block. Keine Anleitungsprosa.

### R3-4 Zustand über Form
* ValidatedField: Rand des Feldes in `ok`/`warn`/`err` (2 px unten, 1 px
  rundum), Statussymbol **vor** der einzeiligen Meldung unter dem Feld,
  nicht rechts in einer Spalte.
* Kopplungscode: Augen-Symbolknopf im Feld (`eye`/`eye_off`) statt Text.
* Gesperrte Hauptaktion: Grund im Tooltip und als eine kurze Zeile direkt
  links neben/unter dem Knopf, in `text2`.
* Einrichtung verlassen: beschrifteter Knopf „Verlassen“ mit Symbol rechts in
  der Zeile des Schritttitels (Tooltip „Einrichtung verlassen – Gespeichertes
  bleibt erhalten“).

### R3-5 Bewegung – nur was sauber läuft
Flackern ist schlechter als keine Bewegung. Erlaubt bleiben nur:
ProgressRing (mit **Mindestanzeigedauer 400 ms**), Herzschlag-Puls,
Kopier-/Prüf-Häkchen, Ladebalken. **Entfernt**: Überblendung
Betrieb↔Einrichtung, Schrittübergang (`slide_in`, `fade_in`), Kachel-
Farbblitz – es sei denn, sie laufen nachweislich ohne Neuaufbau der Widgets
flimmerfrei. Grundregel: Kein Widget wird bei einem bloßen Datenwechsel neu
aufgebaut; die Einrichtung aktualisiert vorhandene Widgets und behält
Eingabetext und Fokus (B-12: „Suche wiederholen“ löschte die Adresse).

### R3-6 Fehler aus Teil B
B-01 Tooltips als Box (Rich Text, Höchstbreite 320 px, Verzögerung ≈ 300 ms,
überall gleich). B-07 Moduswahl: ohne laufende Übertragung (kein Lauf mit
Weitergabe) ist der Wechsel erlaubt und trennt nach Bestätigung; während
Übertragung steht in der Sperrzeile der Karte ein Knopf „Trennen …“ mit dem
bestehenden Dialog. B-08 Pfeiltasten in der Moduswahl. B-10 Werkzeugfenster
höchstens verfügbare Bildschirmhöhe − 48 px, Position in die verfügbare
Fläche geklemmt, Inhalt scrollt. B-12 Suche: kein Neuaufbau, Text bleibt,
Ergebnis „Nichts gefunden“ sichtbar. B-17 Demo (`ui/fake.py`): „Weiter“/
„Zurück“ schalten E1→E2b→E3→E4session→E5 bzw. D1→D4 durch; ein aktives
„Weiter“ tut nie wortlos nichts. B-22 Enter/Return löst fokussierte Knöpfe,
Symbolknöpfe und Kacheln aus, auch in Werkzeugfenstern (QDialog-Standard-
knopf-Logik beachten). Tray → „Brücke beenden …“: Dialog kommt nach vorn
(`raise_`/`activateWindow`, Hauptfenster vorher wiederherstellen).
