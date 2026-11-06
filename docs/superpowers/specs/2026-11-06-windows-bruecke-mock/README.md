# Mock der Windows-App „GSVmulti-Brücke“ (Gestaltungsvorlage)

Stand: 2026-11-06. Interaktiver HTML-Mock (`mock.html`, eine Datei, ohne externe
Ressourcen) als **Gestaltungsvorlage für die spätere Qt-Umsetzung** (PySide6,
Qt Widgets). Er zeigt Aussehen, Zustände und Texte; er enthält keine Funktion
und keine echten Daten (alle Werte sind synthetisch). Fachlich autoritativ sind
[die Spec](../2026-11-06-windows-bruecke-design.md) (§3, §4, §6–§11) und
`windows/bridge/PRODUCT.md`. Gestaltungsvertrag: Zustand oben, Ereignisjournal
darunter, Windows 11 nativ (Fluent), Fenster 440 × 720 logische px (min.
380 × 560).

Öffnen: `mock.html` im Browser. Links die **Mock-Steuerung** (Zustandswähler,
hell/dunkel, Skalierung 100/150/200 %, Mindestgröße 380 × 560), rechts das
Fenster. Direkt anspringen: `mock.html#B3`; optional `?theme=dark`, `?zoom=2`,
`?min=1`. Im Fenster bedienbar: Chips (Detail-Flyout), Segmented „Alle |
Störungen“, Schaltflächen der Einrichtung, Schließen (Dialog), Minimieren
(Tray). Tastatur: Tab, Enter/Leertaste, Esc (Dialog: „Weiter übertragen“).

## Zustände

Einrichtung (Schrittkopf 1–5):
[E1](mock.html#E1) Komponenten, Portpaar fehlt ·
[E1uac](mock.html#E1uac) UAC abgelehnt ·
[E1restart](mock.html#E1restart) Neustart nötig ·
[E1ok](mock.html#E1ok) Portpaar eingerichtet ·
[E2](mock.html#E2) Profil öffnen ·
[E2b](mock.html#E2b) Fingerabdruck und Kopplungscode ·
[E2exp](mock.html#E2exp) Code abgelaufen ·
[E2bad](mock.html#E2bad) Fingerabdruck stimmt nicht ·
[E2ok](mock.html#E2ok) Pi gekoppelt ·
[E3](mock.html#E3) Verbinden, Netzwerk ·
[E3uart](mock.html#E3uart) UART, ein Adapter ·
[E3uart2](mock.html#E3uart2) UART, zwei gleiche Adapter ·
[E3ok](mock.html#E3ok) Pi verbunden ·
[E3fail](mock.html#E3fail) Adapter erkannt, Pi antwortet nicht ·
[E4](mock.html#E4) Session erzeugen ·
[E4ok](mock.html#E4ok) Sessiondatei erzeugt ·
[E4unk](mock.html#E4unk) GSVmulti-Version unbekannt ·
[E5](mock.html#E5) Empfangstest ·
[E5run](mock.html#E5run) Test läuft (Klick auf „Test starten“ spielt den Verlauf ab) ·
[E5file](mock.html#E5file) Testdatei auswählen ·
[E5ok](mock.html#E5ok) Empfang belegt ·
[E5bad](mock.html#E5bad) Abweichung 598/600.

Betrieb:
[B1](mock.html#B1) normal, DUT gesperrt ·
[B1t](mock.html#B1t) normal, Empfang belegt (nach E5ok) ·
[B2](mock.html#B2) wartet auf Lauf ·
[B3](mock.html#B3) Pi antwortet nicht ·
[B4a](mock.html#B4a) COM-Port belegt ·
[B4b](mock.html#B4b) COM-Schreibfehler ·
[B4c](mock.html#B4c) COM-Ergebnis unklar ·
[B5](mock.html#B5) Demo (synthetisch) ·
[B6](mock.html#B6) Chip-Detail ·
[B7](mock.html#B7) Beenden bei aktiver Übertragung ·
[B8](mock.html#B8) Minimiert, Tray-Hinweis und Symbolvarianten ·
[B9](mock.html#B9) lange Namen bei 200 % ·
[B10](mock.html#B10) anderer Pi in Auswahl.

## Bewusste Festlegungen des Mocks

* **DUT-Sperre immer sichtbar:** In **allen** Zuständen, Einrichtung und
  Betrieb, steht unter dem Zustandssatz die feste Zeile „DUT-Ausgabe gesperrt –
  die Brücke gibt keine Messwerte frei“ (Achtung-Symbol). Im Produkt kommt der
  Sperrzustand vom Pi (Hello, §9), im Mock ist er fest gesetzt; geht der Pi
  verloren (B3), bleibt der zuletzt gemeldete Stand stehen. Der Zustandssatz
  wiederholt die Sperre deshalb nicht (B1: „Verbunden – Lauf 7 wird
  übertragen“).
* **Schloss rechts im Kopf = „Pi-Wechsel gesperrt“** (Tooltip und Name, bleibt
  fokussierbar, Klick nennt den Grund). Es hat nichts mit der DUT-Sperre zu tun.
* **Sechs Prüfpunkte als 3 × 2-Raster, bewusste Entscheidung:** Sechs Chips mit
  Statuswort und Unterzeile passen bei 440 px nicht in eine Zeile, ohne
  Statuswörter zu kürzen. Chips einer Reihe sind gleich hoch, auch wenn Wörter
  umbrechen. Reihenfolge: Komponenten, UART, Pi / Ausgabe, Weitergabe,
  GSVmulti. Nicht benutzte Prüfpunkte tragen ein Strich-Symbol.
* **Nie pauschal grün:** „Ausgabe“ bleibt Achtung. **GSVmulti** ist nach der
  Bedienerbestätigung nur neutral (Info) mit Unterzeile „Empfang nicht
  nachgewiesen“; erst nach dem Empfangstest (E5ok) zeigt B1t grün „Empfang
  belegt“ mit „Test 14:02, 600/600“, nur für genau diese Konfiguration. Der
  **Weitergabe**-Chip trägt die Unterzeile „vom Port angenommen“ (in B4:
  „COM4 (Brückenseite)“); Ports stehen konsistent als „COM4 (Brückenseite)“
  und „GSVmulti hört auf COM5“. In der Demo (B5) steht „Demo-Werte“ im
  Achtung-Ton.
* **Fingerabdruck wie in der Werkbank:** Kleinbuchstaben-Hex, Vierergruppen,
  4 Gruppen je Zeile in 4 Zeilen, Mono, nie gekürzt, kein Umbruch (B6, E2b,
  E2bad). In E2bad sind abweichende Gruppen fett und unterstrichen.
* **Wiederverbinden (B3):** Der Kopfsatz trägt Zustand und Countdown, die
  InfoBar nur Ursachen und Wiederholregel. „Nicht mehr versuchen“ stoppt das
  automatische Wiederverbinden, „Erneut versuchen“ ist die Primäraktion. Kein
  weiteres Pop-up.
* **Journal:** Titel nennt die Störung, die Dauer steht als Badge, die
  Unterzeile den Ausgang („wieder verbunden · …“ bzw. „läuft noch · …“),
  ohne Doppelung. Das Journal gehört zum ausgewählten Pi: B10 zeigt nur
  Einträge von „Prüfstand 3 – Halle A“, die Journalkopfzeile nennt den Pi.
* **Tray (B8, dazu Vorschau unter dem Fenster in allen Betriebszuständen):**
  Symbol in drei Varianten (normal, Achtung, Fehler als kleines Zeichen am
  Symbol), Tooltip = Kopfsatz. Zustandswechsel ändern nur Symbol und Tooltip;
  der einmalige Hinweis „Die Brücke läuft im Infobereich weiter.“ erscheint
  nur beim ersten Minimieren.
* **InfoBars:** E4ok ist info-getönt (Datei erzeugt, Übernahme offen), nicht
  grün. E5ok trägt im Kopf „Empfang belegt für diese Testdatei und
  Konfiguration“.
* **Ergänzte Statuswörter** (nicht in Spec §10 als Tabelle): Ausgabe
  „Unbekannt“ und Weitergabe „Keine Weitergabe“ bei getrenntem Pi (B3),
  UART/Pi/Ausgabe „nicht verbunden“ nach Pi-Wechsel (B10). Bei der
  Implementierung gegen §10 abgleichen.
* **Sessiondatei `.ucf` und ihr Name** sind nach den Fixtures
  (`tests/fixtures/gsvmulti/session-templates`) belegt; eine freigegebene
  Vorlage gibt es noch nicht (OQ-53). E4/E4ok zeigen die Gestaltung, keine
  Zusage, dass der Generator für die Version arbeitet. E4unk ist der Normalfall,
  solange keine Vorlage geprüft ist.
* **Menüpfade in GSVmulti:** nur „Datei › Öffnen …“.
* **Mock-Hilfen außerhalb der App:** Zustandsleiste, Fußzeile „Mock –
  synthetische Daten“, Hinweiszeile und Tray-Vorschau unter dem Fenster,
  Desktop/Taskleiste in B8.

## Qt-Umsetzungsnotiz

### Farb-Tokens

Systemakzent der Mocks (hell #005fb8, dunkel #60cdff) ersetzt die App zur
Laufzeit durch den Windows-Akzent (`QPalette.Highlight` aus der
Systempalette bzw. UISettings), mit den Kontrastregeln unten.

| Token | hell | dunkel | Qt-Rolle / Selektor |
| --- | --- | --- | --- |
| `--mica` Fensterfläche | #f3f3f3 | #202020 | `QPalette.Window` |
| `--mica2` Fußleiste, Segmentgrund | #ededed | #1b1b1b | QSS `#footer`, `#segmented` |
| `--card` Karte, Journal, Chip | #fbfbfb | #2b2b2b | `QPalette.Base` bzw. QSS `.Card` |
| `--stroke` Kartenrand 1 px | #e5e5e5 | #3a3a3a | QSS `border:1px solid` auf Karten, Journal |
| `--stroke-strong` Bedienelementrand | #8a8a8a | #9a9a9a | Radio/Checkbox/Eingabefeld-Rand |
| `--text` | #1a1a1a | #ffffff | `QPalette.WindowText`, `Text` |
| `--text2` sekundärer Text | #5d5d5d | #cfcfcf | `QPalette.PlaceholderText`; QSS `[secondary="true"]` |
| `--text-dis` deaktiviert | #9a9a9a | #7a7a7a | `QPalette.Disabled, Text/ButtonText` |
| `--ctrl` / `-hover` / `-press` Schaltfläche | #fdfdfd / #f6f6f6 / #efefef | #323232 / #3a3a3a / #292929 | `QPalette.Button`; QSS `QPushButton`, `:hover`, `:pressed` |
| `--ctrl-stroke` Schaltflächenrand | #d1d1d1 | #464646 | QSS `QPushButton{border}` |
| `--accent` Primäraktion, Auswahl, Fokus | #005fb8 | #60cdff | `QPalette.Highlight`; QSS `QPushButton[accent="true"]` |
| `--accent-hover` / `-press` | #196ebd / #3a82c5 | #52b7e6 / #44a0cc | QSS `:hover` / `:pressed` der Akzent-Schaltfläche |
| `--on-accent` | #ffffff | #000000 | `QPalette.HighlightedText` |
| `--ok` Erfolg | #0f7b0f | #6ccb5f | Symbolfarbe `Status.ok` |
| `--warn` Achtung | #9d5d00 | #fce100 | Symbolfarbe `Status.warn` |
| `--err` Fehler | #c42b1c | #ff99a4 | Symbolfarbe `Status.err` |
| `--info` Hinweis/neutral | #5d5d5d | #cfcfcf | Symbolfarbe `Status.info` (kein Akzent); auch GSVmulti-Chip „Übernahme bestätigt“ |
| InfoBar Erfolg | #dff6dd | #393d1b | QSS `InfoBar[kind="ok"]` Hintergrund |
| InfoBar Achtung | #fff4ce | #433519 | `InfoBar[kind="warn"]` |
| InfoBar Fehler | #fde7e9 | #442726 | `InfoBar[kind="err"]` |
| InfoBar Info | #f9f9f9 | #2f2f2f | `InfoBar[kind="info"]` (mit Rand `--stroke`) |
| Scrim hinter Dialog | 30 % Schwarz | 50 % Schwarz | halbtransparentes `QWidget` über dem Inhalt |
| Tray-Badge Achtung/Fehler | `--warn` / `--err` | `--warn` / `--err` | kleines Zeichen unten rechts am Tray-Symbol (10 px) |
| Fokus außen / innen | #1a1a1a / #ffffff | #ffffff / #1a1a1a | eigenes `paintEvent`/Style, siehe Fokusrahmen |

Das Symbol der Statusstufe trägt immer zusätzlich ein Wort („Erfolg:“,
„Achtung:“ …) als Screenreader-Text (`QAccessible`-Name); sichtbar steht das
Statuswort des Prüfpunkts. Zustand nie nur über Farbe.

### Bausteine und Widgets

| Baustein im Mock | Qt-Umsetzung |
| --- | --- |
| Titelleiste, _ □ × | native Windows-11-Titelleiste (Standardrahmen); kein eigener Rahmen. Titel „GSVmulti-Brücke“ |
| Kopf (Name · Weg, Zustandssatz) | `QWidget` mit `QLabel` (Name, Semibold 15 pt, `wordWrap`, Tooltip = voller Name) und `QLabel` für den Satz mit Statussymbol (`QLabel` mit `QPixmap`/SVG) |
| DUT-Sperrzeile | `QLabel` mit Achtung-Symbol unter dem Zustandssatz, in jedem Fenster-Zustand sichtbar; Text aus dem vom Pi gemeldeten Sperrzustand |
| Pi-Wechsel (Auswahl / gesperrt) | frei: `QToolButton` mit Chevron, öffnet Auswahl-Popup (`QWidget`, `Qt.Popup`); gesperrt: `QToolButton` mit Schloss, bleibt fokussierbar und öffnet ein Popup mit dem Grund |
| InfoBar | `QFrame` + `QLabel` (Symbol), `QLabel` (Titel/Text, `wordWrap`) + `QPushButton`(en); `kind` als Property für QSS. Genau eine nächste Aktion, höchstens zwei Knöpfe, Primäraktion rechts |
| Prüfpunkt-Chip | `QToolButton`, checkable, bis zu drei Zeilen (Name, Symbol + Statuswort, optionale Unterzeile), `QGridLayout` 3 × 2; Chips einer Reihe gleich hoch; geprüft = Detail-Flyout offen |
| Detail-Flyout | `QWidget` mit `Qt.Popup`, Karte mit Radius 8, schließt bei Klick außerhalb und Esc, Fokus kehrt zum Chip zurück |
| Segmented „Alle \| Störungen“ | `QButtonGroup` (exklusiv) aus zwei checkable `QPushButton`; Pfeiltasten wechseln |
| Ereignisjournal | `QListView` mit `QAbstractListModel` und eigenem `QStyledItemDelegate` (Zeit, Symbol, Text + Zweitzeile, Dauer rechts); Gruppenköpfe „Heute/Gestern“ als Sondereinträge oder `QSortFilterProxyModel`; Zeitspalte mit Tabellenziffern (`QFont.setFeature("tnum")` bzw. fester Breite) |
| Fuß | `QFrame` mit `QPushButton` „Diagnose exportieren“, „Details“, Version als `QLabel` |
| Schrittkopf 1–5 | eigenes Widget (`paintEvent`) aus fünf Schritten; Zustände erledigt / aktuell / offen, `aria-current` entspricht `QAccessible`-Zustand „fokussiert“ am aktuellen Schritt |
| Karte | `QFrame` mit QSS `border:1px solid; border-radius:8px` |
| RadioButtons Weg, Adapter, Kandidaten | `QRadioButton` mit Beschreibungs-`QLabel` (eigene Komposition) |
| Kontrollkästchen | `QCheckBox` |
| Eingabefeld | `QLineEdit`, Fokus = 2-px-Unterstrich Akzent |
| Fortschrittsbalken | `QProgressBar` (4 px hoch, ohne Text; Text in eigenem `QLabel`) |
| Abzeichen „Unbestätigt“, „Synthetisch“ | `QLabel` mit Rand, Radius 4 |
| ContentDialog „Brücke beenden?“ | `QDialog` (modal, Fensterrahmen ohne Titelleiste) über Scrim; Standard- und Esc-Taste = „Weiter übertragen“ |
| Tray | `QSystemTrayIcon` mit drei Symbolen (normal / Achtung / Fehler), Tooltip = Kopfsatz; `showMessage` nur einmalig beim ersten Minimieren, keine wiederholten Pop-ups; Symbolklick stellt das Fenster wieder her |
| Ziehen einer Profildatei | `dragEnterEvent`/`dropEvent` auf der Ablagefläche; „Profil öffnen …“ = `QFileDialog` |

### Typografie

Schrift: „Segoe UI Variable Text“, Rückfall „Segoe UI“. Alle Größen bei 96 dpi
(1 px = 0,75 pt); Qt skaliert über `QT_ENABLE_HIGHDPI_SCALING`.

| Stufe | CSS | Qt (pt) | Verwendung |
| --- | --- | --- | --- |
| Untertitel | 20/28, 600 | 15 pt | Pi-Name, Dialogtitel |
| Text | 14/20, 400 | 10,5 pt | Fließtext, Journaleintrag, Schaltflächen |
| Text stark | 14/20, 600 | 10,5 pt (Semibold) | Zustandssatz, InfoBar-Titel, Karten-Überschrift |
| Beschriftung | 12/16, 400 | 9 pt | Chip-Name, Zweitzeile, Zeit, Version |
| Beschriftung stark | 12/16, 600 | 9 pt (Semibold) | Chip-Statuswort, Dauer |
| Daten (mono) | 12/18 | 9 pt | Fingerabdruck, Pi-ID, Endpunkt (Cascadia Mono / Consolas) |

Zahlen (Zeiten, Dauern, Zähler) in Tabellenziffern. Kein Display-Schnitt in
Bedienelementen.

### Abstände, Radien, Rand

* 4-px-Raster: 4 / 8 / 12 / 16 / 20. Fensterrand außen 16, Karteninnenrand
  12–14, Abstand zwischen Karten 12, Chip-Lücke 8, Journalzeile 6 oben/unten, 12
  seitlich.
* Radius 4 (Schaltfläche, Chip, InfoBar, Eingabe, Segmente), 8 (Karte, Journal,
  Flyout, Dialog, Fenster).
* Kartenrand 1 px `--stroke`; keine Verläufe; Schatten nur bei Flyout und
  Dialog (Offset 8 px, Weichzeichnung 16 px, 14 % Schwarz).
* Mindestgröße 380 × 560: Journal schrumpft, Kopf und Chips bleiben; Inhalt der
  Einrichtung scrollt, der Fuß bleibt sichtbar.

### Fokusrahmen

Fluent doppelt: 2 px außen in `--focus-outer` (hell schwarz, dunkel weiß), innen
1 px in `--focus-inner`, jeweils innerhalb der Widget-Fläche gezeichnet, damit
Scrollbereiche nichts abschneiden. Bei Eingabefeldern stattdessen 2-px-Unterstrich
in Akzent. Tab-Reihenfolge Betrieb: Pi-Wechsel, sechs Chips, Segmented,
Journal (Bereich fokussierbar, scrollt mit Pfeiltasten), „Diagnose exportieren“,
„Details“. Einrichtung: Inhalt von oben nach unten, dann Fuß links nach rechts.
Dialog: Fokus bleibt im Dialog, Standard „Weiter übertragen“, Esc ebenso.

### Hochkontrast und Kontrast

* Kontrast Text ≥ 4,5 : 1 in hell und dunkel (Text 2 auf Mica: hell ≈ 6,0 : 1,
  dunkel ≈ 11 : 1); Randfarben für Bedienelemente ≥ 3 : 1.
* Hochkontrast: `QPalette` aus dem System übernehmen, keine festen Hex-Werte
  für Text und Rand; Karten behalten den 1-px-Rand in `WindowText`; Akzent-
  Schaltfläche in `Highlight`/`HighlightedText`; Status bleibt über Symbol und
  Wort erkennbar. Der Mock hat dafür eine `forced-colors`-Regel.
* Bewegung: nur 150 ms für Hover/Zustandswechsel; `prefers-reduced-motion`
  entspricht der Windows-Einstellung „Animationseffekte“, dann ohne Übergang.
* Skalierung: 100/150/200 % Systemskalierung ohne Abschneiden; lange Namen
  brechen um, der volle Name steht im Tooltip. Kein Aufbau mit festen Pixelhöhen
  für Text.

## Texte je Zustand

Wörtlich zu übernehmen (Deutsch). Reihenfolge entspricht dem Fenster von oben
nach unten. Gemeinsam in allen Einrichtungszuständen: Kopf („Kein Pi gekoppelt
· Weg noch offen“ bis zur Pi-Wahl, danach „Prüfstand 2 · Netzwerk (LAN)“ bzw.
„UART (USB-Adapter)“), Schrittkopf „Komponenten · Pi koppeln · Verbinden ·
Session · Empfangstest“, Fuß „Diagnose exportieren“ links, „Zurück“ und
„Weiter“ rechts (Beschriftung „Verbinden“ in E3, „Fertig“ in E5ok; „Weiter“ ist
erst Primäraktion, wenn der Schritt erfüllt ist). Gemeinsam in **allen**
Zuständen, unter dem Zustandssatz: „DUT-Ausgabe gesperrt – die Brücke gibt keine
Messwerte frei“. Gemeinsam in allen Betriebszuständen (siehe B1): Chips, Segmented, Journal, Fuß „Diagnose
exportieren“, „Details“, „Version 0.1.0.dev0“. In den Betriebszuständen B1t–B10
sind nur die **Abweichungen von B1** aufgeführt. Screenreader-Präfixe der
Statussymbole: „Erfolg:“, „Achtung:“, „Fehler:“, „Hinweis:“, „Unklar:“,
„Nicht benutzt:“.

### Einrichtung und Betrieb

#### E1 – Komponenten: Portpaar fehlt

- Kein Pi gekoppelt · Weg noch offen
- Schritt 1 von 5: Komponenten prüfen.
- Komponenten
- Pi koppeln
- Verbinden
- Session
- Empfangstest
- Bestandsaufnahme
- Windows 11, 64 Bit
- Unterstützte Windows-Version
- Brücke 0.1.0.dev0
- Installiert
- COM-Portpaar fehlt
- Für GSVmulti wird ein virtuelles Portpaar (com0com) mit freien COM-Namen benötigt.
- Die Brücke legt das Portpaar einmalig an. Windows fragt dafür nach der Administratorfreigabe. Es wird nichts verändert, was bereits vorhanden ist.
- Portpaar einrichten (Administratorfreigabe)
- Diagnose exportieren
- Weiter

#### E1uac – … UAC abgelehnt

- Kein Pi gekoppelt · Weg noch offen
- Schritt 1 von 5: Komponenten prüfen.
- IT-Freigabe erforderlich
- Windows hat die Administratorfreigabe nicht erteilt. Die Brücke ändert ohne Freigabe nichts. Bitten Sie Ihre IT, das Portpaar einzurichten; danach genügt „Erneut prüfen“.
- Erneut prüfen
- Bestandsaufnahme
- Windows 11, 64 Bit
- Unterstützte Windows-Version
- Brücke 0.1.0.dev0
- Installiert
- COM-Portpaar fehlt
- Einrichtung nicht möglich ohne Administratorfreigabe.
- Weiter

#### E1restart – … Neustart nötig

- Kein Pi gekoppelt · Weg noch offen
- Schritt 1 von 5: Komponenten prüfen.
- Neustart nötig
- Windows muss neu starten, damit das Portpaar nutzbar wird. Die Einrichtung wird danach bei Schritt 1 fortgesetzt. Speichern Sie vorher offene Arbeit in anderen Programmen.
- Später
- Jetzt neu starten
- Bestandsaufnahme
- Windows 11, 64 Bit
- Unterstützte Windows-Version
- Brücke 0.1.0.dev0
- Installiert
- COM-Portpaar eingerichtet
- Wird erst nach dem Neustart nutzbar.
- Weiter

#### E1ok – … Portpaar eingerichtet

- Kein Pi gekoppelt · Weg noch offen
- Schritt 1 von 5: Komponenten sind bereit.
- Bestandsaufnahme
- Windows 11, 64 Bit
- Unterstützte Windows-Version
- Brücke 0.1.0.dev0
- Installiert
- Portpaar eingerichtet
- Brückenseite COM4 · GSVmulti-Seite COM5. Selbsttest in beide Richtungen bestanden.
- Weiter

#### E2 – Pi koppeln: Profil öffnen

- Kein Pi gekoppelt · Weg noch offen
- Schritt 2 von 5: Pi-Profil öffnen.
- Profil hierher ziehen
- Datei „pi.dispread“
- Profil öffnen …
- Laden Sie das Profil in der Werkbank herunter (Brücke einrichten › Profil). Öffnen allein gibt noch nichts frei: Kopplung und Ausgabe folgen getrennt.
- Zurück
- Weiter

#### E2b – … Fingerabdruck und Code

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 2 von 5: Pi koppeln.
- Profil geladen
- Anzeigename
- Prüfstand 2
- Pi-ID
- pi-4b7e09c1
- Fingerabdruck
- SHA-256
- a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de
- Vergleichen Sie den Fingerabdruck mit der Werkbank (Brücke einrichten › Profil).
- Der Fingerabdruck stimmt mit der Werkbank überein.
- Kopplungscode
- Der Code ist 5 Minuten gültig und nur einmal verwendbar.
- Koppeln
- Zurück
- Weiter

#### E2exp – … Code abgelaufen

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 2 von 5: Pi koppeln.
- Code abgelaufen
- Der Kopplungscode war 5 Minuten gültig. Es wurde nichts gekoppelt. Erzeugen Sie in der Werkbank einen neuen Code und geben Sie ihn ein.
- Neuen Code eingeben
- Profil geladen
- Anzeigename
- Prüfstand 2
- Pi-ID
- pi-4b7e09c1
- Zurück
- Weiter

#### E2bad – … Fingerabdruck falsch

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 2 von 5: Pi koppeln.
- Fingerabdruck stimmt nicht – falsches Gerät
- Der Pi, der geantwortet hat, ist nicht der Pi aus dem Profil. Es wurde nichts gekoppelt und nichts gesendet. Prüfen Sie, ob Profil und Pi zusammengehören.
- Anderes Profil öffnen
- Fingerabdrücke im Vergleich
- Im Profil
- a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de
- Beim antwortenden Gerät (fett unterstrichen = abweichend)
- a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 55e0 1b6c 9a46 3f02
- Zurück
- Weiter

#### E2ok – … Pi gekoppelt

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 2 von 5: Pi ist gekoppelt.
- Pi gekoppelt
- Anzeigename
- Prüfstand 2
- Pi-ID
- pi-4b7e09c1
- Zugang
- Gilt nur für diesen PC und ist in der Werkbank widerrufbar.
- Weiter

#### E3 – Verbinden: Netzwerk

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 3 von 5: Weg zum Pi wählen.
- Netzwerk LAN oder Tailscale, verschlüsselt
- UART (USB-Adapter) Direktverbindung, unverschlüsselt
- Gefundene Pi im Netz
- prüfstand2.local Unbestätigt 192.168.10.24 · gefunden per mDNS
- pi-labor-b.local Unbestätigt 192.168.10.37 · gefunden per mDNS
- Ein gefundener Name ist kein Identitätsnachweis. Erst die Prüfung gegen das Profil bestätigt den Pi.
- Adresse oder Name manuell eintragen
- Tailscale wird nur benutzt, wenn Sie hier den Tailscale-Namen oder die Adresse eintragen. Ohne Tailscale braucht es ein gemeinsames Netz oder die VPN-Route Ihrer IT.
- Suche wiederholen
- Zurück

#### E3uart – … UART, ein Adapter

- Prüfstand 2 · UART (USB-Adapter)
- Schritt 3 von 5: Weg zum Pi wählen.
- Netzwerk LAN oder Tailscale, verschlüsselt
- UART (USB-Adapter) Direktverbindung, unverschlüsselt
- USB-Adapter
- USB-Seriell-Adapter · COM6 USB-Ort: Port 3
- Verdrahtung
- 115200 Baud, 8N1, kein Handshake. TX des Adapters an RX des Pi, RX des Adapters an TX des Pi, GND an GND. VCC, CTS und RTS bleiben frei.
- Zurück

#### E3uart2 – … UART, zwei gleiche Adapter

- Prüfstand 2 · UART (USB-Adapter)
- Schritt 3 von 5: Weg zum Pi wählen.
- Zwei gleiche Adapter – Auswahl nötig
- Die Adapter lassen sich nur am USB-Anschluss unterscheiden. Wählen Sie den Adapter, der am Pi hängt.
- Netzwerk LAN oder Tailscale, verschlüsselt
- UART (USB-Adapter) Direktverbindung, unverschlüsselt
- USB-Adapter
- USB-Seriell-Adapter · COM6 USB-Ort: Port 3 (Hub 1)
- USB-Seriell-Adapter · COM7 USB-Ort: Port 4 (Hub 1)
- Verdrahtung
- 115200 Baud, 8N1, kein Handshake. TX des Adapters an RX des Pi, RX des Adapters an TX des Pi, GND an GND. VCC, CTS und RTS bleiben frei.
- Zurück

#### E3ok – … Pi verbunden

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 3 von 5: Pi verbunden.
- Pi verbunden (Identität geprüft)
- Der Pi hat seine Identität belegt; der Fingerabdruck passt zum Profil. Das ist noch keine Messfreigabe.
- Weg
- Netzwerk (LAN)
- Endpunkt
- wss://192.168.10.24 (Beispiel)
- Protokoll
- Version 2
- Zurück
- Weiter

#### E3fail – … Adapter erkannt, Pi antwortet nicht

- Prüfstand 2 · UART (USB-Adapter)
- Schritt 3 von 5: Verbindung herstellen.
- Adapter erkannt, Pi antwortet nicht
- Der USB-Adapter ist da, aber der Pi hat nicht geantwortet. Mögliche Ursachen:
- Der Pi-Dienst läuft nicht.
- TX, RX oder GND sind nicht richtig verbunden.
- Die Parameter stimmen nicht (115200 Baud, 8N1).
- Erneut versuchen
- Adapter
- USB-Seriell-Adapter · COM6
- USB-Ort
- Port 3
- Parameter
- 115200 Baud, 8N1, kein Handshake
- Zurück
- Weiter

#### E4 – Session: erzeugen

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 4 von 5: GSVmulti-Session erzeugen.
- Portpaar
- Brückenseite
- COM4
- Gegenport für GSVmulti
- COM5
- Die Session verweist auf COM5. Vorhandene GSVmulti-Sessions bleiben unverändert.
- Session erzeugen
- Zurück
- Weiter

#### E4ok – … Sessiondatei erzeugt

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 4 von 5: Session in GSVmulti öffnen.
- Sessiondatei erzeugt: GSVmulti_Prüfstand2_COM5.ucf
- Die Datei allein belegt nicht, dass GSVmulti die Einstellungen übernommen hat.
- Ordner öffnen
- In GSVmulti öffnen
- In GSVmulti: Datei › Öffnen …
- Die erzeugte Datei auswählen.
- Hier bestätigen, dass die Session geöffnet ist.
- Ich habe die Session in GSVmulti geöffnet.
- Zurück
- Weiter

#### E4unk – … GSVmulti-Version unbekannt

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 4 von 5: GSVmulti manuell einrichten.
- GSVmulti-Version unbekannt – Automatik gesperrt
- Für diese Version gibt es keine geprüfte Vorlage. Es wird keine Sessiondatei erzeugt. Die manuelle Anleitung ist eingeschränkt.
- Manuelle Anleitung (eingeschränkt)
- Stellen Sie in GSVmulti selbst ein:
- Port
- COM5
- Baudrate
- 115200
- Format
- 8N1, kein Handshake
- Die Menüführung Ihrer GSVmulti-Version ist nicht geprüft. Ob GSVmulti die Einstellungen übernimmt, belegt erst der Empfangstest.
- Ich habe GSVmulti so eingestellt.
- Zurück
- Weiter

#### E5 – Empfangstest: Start

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 5 von 5: Empfang prüfen.
- Synthetischer Test – getrennte GSVmulti-Testsession verwenden
- Die Testwerte sind künstlich und dürfen nicht in einer Kalibriermessung landen.
- Die Brücke sendet 600 synthetische Werte mit 10 Hz (etwa 60 s). GSVmulti zeichnet sie in der Testsession auf.
- Ich verwende eine getrennte GSVmulti-Testsession.
- Test starten
- Zurück
- Weiter

#### E5run – … Test läuft (600 Werte, 10 Hz)

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 5 von 5: Empfang prüfen.
- Synthetischer Test – getrennte GSVmulti-Testsession verwenden
- Die Testwerte sind künstlich und dürfen nicht in einer Kalibriermessung landen.
- Test läuft
- 312 von 600 Werten gesendet (10 Hz, synthetisch)
- Abbrechen
- Zurück
- Weiter

#### E5file – … Testdatei auswählen

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 5 von 5: Empfang prüfen.
- Synthetischer Test – getrennte GSVmulti-Testsession verwenden
- Die Testwerte sind künstlich und dürfen nicht in einer Kalibriermessung landen.
- Testdatei auswählen
- Der Test ist gesendet. Speichern Sie die Aufzeichnung in GSVmulti und wählen Sie die originale Datei aus. Die Brücke vergleicht jeden Wert und die Reihenfolge.
- Testdatei auswählen …
- Zurück
- Weiter

#### E5ok – … Empfang belegt (600/600)

- Prüfstand 2 · Netzwerk (LAN)
- Empfang belegt für diese Testdatei und Konfiguration
- 600/600 Werte stimmen überein
- Der Vergleich gilt nur für die ausgewählte Testdatei und diese Konfiguration, nicht für spätere Läufe.
- Datei
- GSVmulti_Test_Prüfstand2.txt
- Test
- 14:02, synthetisch
- Werte
- 600 von 600
- SHA-256
- 9f2c 41ab 07d3 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de
- Im Betrieb zeigt die Brücke danach „Empfang belegt“ nur für diese Konfiguration; die COM-Weitergabe bleibt eine eigene Aussage.
- Zurück
- Fertig

#### E5bad – … Abweichung (598/600)

- Prüfstand 2 · Netzwerk (LAN)
- Schritt 5 von 5: Empfang nicht belegt.
- Abweichung: 598/600
- Zwei Werte der Testdatei stimmen nicht mit dem Test überein. Der Empfang ist für diese Datei nicht belegt.
- Test wiederholen
- Fehlende Werte
- Nr. 211
- fehlt in der Testdatei
- Nr. 212
- fehlt in der Testdatei
- Zurück
- Weiter

#### B1 – Normal, DUT gesperrt

- Prüfstand 2 · Netzwerk (LAN)
- Verbunden – Lauf 7 wird übertragen
- DUT-Ausgabe gesperrt – die Brücke gibt keine Messwerte frei
- Komponenten Installiert
- UART nicht benutzt
- Pi Verbunden
- Ausgabe DUT gesperrt
- Weitergabe Bestätigt vom Port angenommen
- GSVmulti Übernahme bestätigt Empfang nicht nachgewiesen
- Alle
- Störungen
- 10 Einträge
- Heute
- 14:32:07
- Neuer Lauf erkannt Lauf 7 · DUT-Ausgabe gesperrt
- 14:31:55
- Pi-Lauf beendet Lauf 6
- 14:12:40
- Verbindung unterbrochen wieder verbunden · Netzwerk (LAN), gleicher Pi 4 s
- 14:05:12
- Weitergabe bestätigt Erster Wert dieses Laufs · COM4 → COM5
- 13:58:30
- Pi verbunden (Identität geprüft) Prüfstand 2 · pi-4b7e09c1
- 13:58:29
- Brücke gestartet Version 0.1.0.dev0
- Gestern
- 17:02:11
- Brücke beendet Auf Wunsch des Bedieners
- 16:20:03
- COM4 (Brückenseite): Schreibfehler Wert nicht erneut gesendet · weiter mit dem nächsten Wert 1 Wert
- 15:44:51
- Pi antwortet nicht wieder verbunden · Versuche nach 1, 2, 4, 8 s 14 s
- 15:10:02
- Pi verbunden (Identität geprüft) Prüfstand 2 · pi-4b7e09c1
- Diagnose exportieren
- Details
- Version 0.1.0.dev0

#### B1t – Normal, Empfang belegt (nach E5ok)

- GSVmulti Empfang belegt Test 14:02, 600/600

#### B2 – Wartet auf Lauf

- Verbunden – wartet auf einen Lauf auf dem Pi
- Ausgabe Wartet auf Lauf
- Weitergabe Noch nichts übertragen
- 9 Einträge

#### B3 – Pi antwortet nicht

- Pi antwortet nicht – Versuch in 4 s
- Keine Antwort vom Pi seit 14:32:20
- Mögliche Ursachen: Pi-Dienst, Netzwerk oder Strom des Pi. Wiederholung nach 1, 2, 4, 8 s, dann alle 8 s. „Nicht mehr versuchen“ stoppt das automatische Wiederverbinden.
- Nicht mehr versuchen
- Erneut versuchen
- Pi Antwortet nicht
- Ausgabe Unbekannt
- Weitergabe Keine Weitergabe Pi antwortet nicht
- 11 Einträge
- 14:32:20
- Pi antwortet nicht läuft noch · Netzwerk (LAN), Versuch 3 12 s

#### B4a – COM-Port belegt

- Weitergabe gestört – COM4 belegt
- COM4 (Brückenseite) belegt – GSVmulti hört auf COM5
- Ein anderes Programm hält COM4. Es wurde nichts gesendet. Schließen Sie es und prüfen Sie erneut.
- Erneut prüfen
- Weitergabe Port belegt COM4 (Brückenseite)
- 11 Einträge
- 14:33:41
- COM4 (Brückenseite) belegt läuft noch · ein anderes Programm hält den Port 8 s

#### B4b – COM-Schreibfehler

- Weitergabe gestört – Schreibfehler
- Schreibfehler auf COM4 (Brückenseite)
- Der Port hat den Wert nicht vollständig angenommen. Er wird nicht erneut gesendet; es geht mit dem nächsten zulässigen Wert weiter.
- Weitergabe Schreibfehler COM4 (Brückenseite)
- 11 Einträge
- 14:33:41
- COM4 (Brückenseite): Schreibfehler Wert nicht erneut gesendet · Bild 18343 1 Wert

#### B4c – COM-Ergebnis unklar

- Weitergabe unklar – kein Nachweis
- Ergebnis unklar auf COM4 (Brückenseite)
- Keine Bestätigung vom Port nach dem Schreiben. Ob GSVmulti den Wert erhalten hat, ist offen. Nicht wiederholt, im Journal vermerkt.
- Weitergabe Ergebnis unklar COM4 (Brückenseite)
- 11 Einträge
- 14:33:41
- COM4 (Brückenseite): Ergebnis unklar keine Quittung · nicht wiederholt · Bild 18343 1 Wert

#### B5 – Demo läuft (synthetisch)

- Verbunden – Demo läuft Synthetisch
- Ausgabe Demo-Werte
- 11 Einträge
- 14:34:02
- Demo gestartet Werte sind synthetisch · vom Pi gemeldet

#### B6 – Chip-Detail (Flyout)

- Pi – technische Werte
- Pi-ID
- pi-4b7e09c1
- Endpunkt
- wss://192.168.10.24 (LAN, Beispiel)
- TLS-Fingerabdruck (SHA-256)
- a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de
- Protokoll
- Version 2
- Letzte Quittung
- COM-Weitergabe bestätigt (Bild 18342) – kein GSVmulti-Empfangsnachweis

#### B7 – Beenden bei aktiver Übertragung

- Brücke beenden?
- Die Übertragung an GSVmulti endet. Der Lauf auf dem Pi läuft weiter.
- Weiter übertragen
- Beenden

#### B8 – Minimiert: Tray-Hinweis und Symbole

- Mock – Tray-Symbol: Normal · Achtung · Fehler. Tooltip = Kopfsatz. Zustandswechsel ändern nur Symbol und Tooltip, kein neues Pop-up.
- Weitergabe gestört – COM4 belegt
- Pi antwortet nicht – Versuch in 4 s
- GSVmulti-Brücke
- Die Brücke läuft im Infobereich weiter. Dieser Hinweis erscheint nur einmal. Ein Klick auf das Symbol öffnet das Fenster.
- 14:35

#### B9 – Lange Namen, 200 %

- Prüfstand 2 – Kalibrierlabor Halle B, Platz 14 · Netzwerk (LAN)
- Neuer Lauf erkannt Prüfstand 2 – Kalibrierlabor Halle B, Platz 14 · Lauf 7

#### B10 – Anderer Pi in Auswahl (frei)

- Prüfstand 3 – Halle A · Netzwerk (LAN)
- Nicht verbunden – Pi ausgewählt
- Gekoppelte Pi
- Prüfstand 2 pi-4b7e09c1 · zuletzt vor 2 Stunden
- Prüfstand 3 – Halle A pi-d21a77e6 · zuletzt gestern
- Nach dem Wechsel muss neu verbunden werden. Ein Wechsel während der Übertragung ist nicht möglich.
- Es läuft keine Übertragung
- Ein Pi-Wechsel ist jetzt möglich. Verbinden Sie danach neu.
- Verbinden
- Pi nicht verbunden
- Ausgabe unbekannt
- Weitergabe Keine Übertragung
- GSVmulti Noch nicht gekoppelt Empfang nicht nachgewiesen
- 3 Einträge · Prüfstand 3 – Halle A
- 14:40:02
- Pi ausgewählt Prüfstand 3 – Halle A · pi-d21a77e6
- 16:02:44
- Brücke beendet Prüfstand 3 – Halle A · auf Wunsch des Bedieners
- 14:20:11
- Pi verbunden (Identität geprüft) Prüfstand 3 – Halle A · pi-d21a77e6
### Chip-Details (Flyout)

Aufbau: Titel, Schließen-Knopf „Details schließen“, Schlüssel/Wert-Liste, Hinweis.

- B1 · Komponenten: Windows: 11, 64 Bit · App-Version: 0.1.0.dev0 · Portpaar: COM4 ↔ COM5 (com0com) — Hinweis: Alle Systemkomponenten sind vorhanden. Das sagt nichts über Verbindung oder Empfang.
- B1 · UART: Weg: Netzwerk (LAN) · USB-Adapter: nicht benutzt — Hinweis: Ein USB-Adapter wird nur im Weg „UART“ gebraucht.
- B1 · Pi – technische Werte: Pi-ID: pi-4b7e09c1 · Endpunkt: wss://192.168.10.24 (LAN, Beispiel) · TLS-Fingerabdruck (SHA-256): a3f90c1d7b42e58a19d6f03c84ab2e715c0db8f463a9d1270e5bc3f89a4671de · Protokoll: Version 2 · Letzte Quittung: COM-Weitergabe bestätigt (Bild 18342) – kein GSVmulti-Empfangsnachweis
- B1 · Ausgabe: Ausgabe: DUT-Ausgabe gesperrt · Bedeutung: Der Pi gibt die Messwerte des Prüflings noch nicht frei. — Hinweis: Die Brücke gibt nichts frei und startet keine Messung.
- B1 · Weitergabe: Brückenseite: COM4 · GSVmulti-Seite: COM5 · Letzte Quittung: COM-Weitergabe bestätigt (Bild 18342) – kein GSVmulti-Empfangsnachweis — Hinweis: „Bestätigt“ heißt: der Windows-Port hat die Daten angenommen.
- B1 · GSVmulti: Session: GSVmulti_Prüfstand2_COM5.ucf · Übernahme: vom Bediener bestätigt (keine Prüfung durch die Brücke) · Empfangsnachweis: nicht nachgewiesen — Hinweis: Nur der Empfangstest belegt Empfang. Der laufende Betrieb zeigt nur die COM-Weitergabe.
- B1t · GSVmulti: Session: GSVmulti_Prüfstand2_COM5.ucf · Übernahme: vom Bediener bestätigt · Empfangsnachweis: Belegt für die Testdatei GSVmulti_Test_Prüfstand2.txt und diese Konfiguration (600/600) — Hinweis: Gilt nur für genau diese Konfiguration, nicht für spätere Läufe.
- B2 · Ausgabe: Ausgabe: Wartet auf Lauf · Bedeutung: Der Pi ist erreichbar, es läuft aber keine Messung. — Hinweis: Die Brücke startet keinen Lauf.
- B3 · Pi – technische Werte: Pi-ID: pi-4b7e09c1 · Endpunkt: wss://192.168.10.24 (LAN, Beispiel) · TLS-Fingerabdruck (SHA-256): a3f90c1d7b42e58a19d6f03c84ab2e715c0db8f463a9d1270e5bc3f89a4671de · Protokoll: Version 2 · Letzte Quittung: COM-Weitergabe bestätigt (Bild 18342) – kein GSVmulti-Empfangsnachweis
- B3 · Ausgabe: Ausgabe: Unbekannt, solange der Pi nicht antwortet · Letzter Stand: DUT-Ausgabe gesperrt (zuletzt vom Pi gemeldet) — Hinweis: Die Brücke gibt nichts frei und startet keine Messung.
- B3 · Weitergabe: Brückenseite: COM4 · GSVmulti-Seite: COM5 · Letzte Quittung: Vor 12 s
- B4b · Weitergabe: Brückenseite: COM4 · GSVmulti-Seite: COM5 · Status: Schreibfehler · Letzte Quittung: COM-Weitergabe bestätigt (Bild 18342) – kein GSVmulti-Empfangsnachweis — Hinweis: Ein Wert wird nach unklarem oder kurzem Schreiben nie blind wiederholt.
- B5 · Ausgabe: Ausgabe: Demo (synthetisch) · Bedeutung: Die Werte kommen aus einer Demo, nicht von einem Messgerät. — Hinweis: Nicht für Kalibrierungen verwenden.


### Weitere Texte

* Pi-Wechsel gesperrt (Schloss im Kopf, auch Tooltip und Name „Pi-Wechsel gesperrt“): „Pi-Wechsel gesperrt“ – „Solange die Brücke an GSVmulti überträgt, bleibt der Pi festgelegt. Beenden Sie die Übertragung, um einen anderen Pi zu wählen.“
* Pi-Auswahl (B10): „Gekoppelte Pi“; Einträge „Prüfstand 2 · pi-4b7e09c1 · zuletzt vor 2 Stunden“, „Prüfstand 3 – Halle A · pi-d21a77e6 · zuletzt gestern“; Hinweis „Nach dem Wechsel muss neu verbunden werden. Ein Wechsel während der Übertragung ist nicht möglich.“
* Filter „Störungen“ ohne Treffer: „Keine Störungen seit dem Start der Brücke.“
* Details-Flyout („Details“ im Fuß): App 0.1.0.dev0 · Brückenseite COM4 · Gegenport COM5 · Pi-ID · Protokoll Version 2 · Journal „Begrenzt, Zugangsdaten werden nicht protokolliert.“
* Titelleistenknöpfe (Tooltip/Name): „Minimieren“, „Maximieren“ (ausgeschaltet), „Schließen“. Schließen ohne aktive Übertragung beendet die Brücke ohne Rückfrage.
* Tray-Symbol-Tooltip = Kopfsatz (normal „Verbunden – Lauf 7 wird übertragen“, Achtung „Weitergabe gestört – COM4 belegt“, Fehler „Pi antwortet nicht – Versuch in 4 s“).
* Tray (B8): Titel „GSVmulti-Brücke“, „Die Brücke läuft im Infobereich weiter.“, Nebensatz „Dieser Hinweis erscheint nur einmal. Ein Klick auf das Symbol öffnet das Fenster.“; Symbol-Tooltip = Kopfsatz.
* Dialog Brücke beenden (B7): Titel „Brücke beenden?“, Text „Die Übertragung an GSVmulti endet. Der Lauf auf dem Pi läuft weiter.“, Primär „Weiter übertragen“ (Standard, Esc), sekundär „Beenden“.
