# Bericht Prüfung UX2 – 2026-11-11 bis 2026-11-13

Umgebung: Windows 11 Pro 24H2 (Build 26100.9711), Python 3.13.17 x64, PySide6 6.12.0,
4K-Anzeige mit 150 % Systemskalierung, Thema hell (B-21 auch dunkel), Akzent #0078D4,
GSVmulti 2.01 Pro (Leonhards PC) bzw. 2.03 Pro (zweiter PC), com0com 3.0.0.0.

Geprüfte Stände:

| Teil | Stand | Nachweis |
| --- | --- | --- |
| A, B | `feat/bruecke-ux` als ZIP (vor `2c5be9b`), Demo-Modus | „Quelle unbekannt“ |
| C-01 … C-03, C-05, C-06 | `feat/bruecke-ux` @ `2c5be9bc94b627baa87444228becb9bceeb1f2ab` (Git-Clone) | `git log` |
| C-07 ff., D | EXE-Builds von Leonhard aus ZIPs von `feat/integration`: 12:08, 12:32, 12:50, 13:16, **14:50** (letzter Stand, vermutlich `c643f30`) | SHA-256 siehe D-01 |
| Werkbank | ab 13.11. 12:00 `fe87998`, später `5a31b41` (Angabe der Pi-Sitzung) | – |

Alle Einzelheiten, Zitate, Messwerte und Zwischenstände stehen chronologisch in
**[ux2-bericht-details.md](ux2-bericht-details.md)**. Diese Datei fasst den Endstand zusammen.

**Abweichung Teil A:** Weil das System schon auf 150 % steht, wurde `QT_SCALE_FACTOR`
auf 0,6667 / leer / 1,3333 gesetzt. So ergeben sich wirklich 100/150/200 % (DPR nachgemessen).
Die Werte aus der Anleitung hätten 150/225/300 % ergeben.

## Ergebnisse

| ID | Ergebnis | Kurzbeobachtung (Details in ux2-bericht-details.md) | Bild/Datei |
| --- | --- | --- | --- |
| A-01 | OK | Segoe UI Variable Text / Cascadia Mono nachgewiesen; einzige Ausnahme Pi-ID in E2b in Segoe | `ux2-bilder\*\32-*` |
| A-02 | Problem | Bei 380 × 560 kein Journaleintrag sichtbar; Einrichtungsfuß bricht zweizeilig um; sonst bis 200 % nichts abgeschnitten | `07-*`, `30`–`44` |
| A-03 | Problem | Schachbrett-Bildlaufleiste im Dunkelmodus (auch echtes Windows-Dunkel); ⓘ und (i) zu ähnlich | `100-dunkel\*`, `150-windows-dunkel\01` |
| A-04 | Problem | Comboboxen unlesbar bei erzwungenem Dunkel auf hellem Windows (im echten Dunkel ok) | `100-dunkel\13`, `31` |
| A-05 | OK | Alle Werkzeugfenster mit nativem Rahmen; „Gekoppelte Pi“ ohne Titelzusatz | `10`–`22` |
| A-06 | OK (behoben) | „Adapter steckt“ war im Betrieb grau; in EXE 13:16 grün | `06`, Foto 13.11. |
| A-07 | OK | Ersatzzeilen bei Testfreigabe/UART direkt laut Pi-Sitzung gewollt | `02`, `06` |
| A-08 | siehe Details | Je Bild ein Satz; Hauptpunkte: zu viel Text, InfoBar doppelt Sperre, „Wechseln zu Pi“ während Übertragung aktiv | alle |
| B-01 | Problem | Tooltips spät und als überlange Einzelzeile | – |
| B-02 … B-06 | OK | Kachel-Fenster, Kopieren, Symbolleiste, Protokoll-Export, Herzschlag | – |
| B-07 | Problem | Moduswahl gesperrt ohne Trennen-Möglichkeit, Sperre auch ohne Lauf | `12` |
| B-08 | Problem | Pfeiltasten in der Moduswahl ohne Wirkung | – |
| B-09 | Problem (hoch) | Mausrad verstellt Ports (Datenverlust), Neuaufbau beim Scrollen, Weg doppelt, Endpunkt-Bedienung unklar, Session-Abschnitt textlastig | `13`, `15` |
| B-10 | Problem (hoch) | Einstellungen/Info zu hoch für den Bildschirm | `13`, `14`, `19` |
| B-11 | OK | Ring nur kurz sichtbar → Mindestdauer empfohlen | `33` |
| B-12 | Problem (hoch) | „Suche wiederholen“ löscht getippte Adresse, Fenster flackert | – |
| B-13 | OK (Gestaltung) | × zum Verlassen der Einrichtung nicht als solches erkennbar | `31`–`37` |
| B-14 | OK | Portpaar-Prüfung | `31` |
| B-15 | OK (Gestaltung) | Wunsch: Auge im Feld, farbiger Feldrand, Symbol an der Meldung | `32` |
| B-16 | OK mit Mängeln | Zu viel Text, Werte nicht als Werte erkennbar | `36` |
| B-17 | Nicht prüfbar | Demo wechselt keine Schritte; aktives „Weiter“ ohne Wirkung | `30` |
| B-18 | Problem | Nur Radio-Punkt klickbar, Punkt/Haken versetzt, Flackern statt Animation | `40` |
| B-19 | OK (Gestaltung) | UART direkt: Strecke Adapter → GSVmulti soll als Bild sichtbar sein | `06` |
| B-20 | OK | Bewegung aus wirkt; Kopier-Animation nie sichtbar; Wunsch farbiger Punkt (umgesetzt laut Pi-Sitzung) | – |
| B-21 | OK | Folgt Windows-Dunkel; Kontrollkästchen-Rand unsauber; Wunsch Thema-Umschalter ganz oben | `150-windows-dunkel\*` |
| B-22 | Problem | Enter löst nichts aus (Tab, Pfeile, Esc ok) | – |
| B-23 | OK | Tray-Verhalten | – |
| B-24 | siehe unten | Leonhards Eindruck; Kontrastanalyse hell/dunkel | – |
| Zusatz | Problem (hoch), Ursache belegt | 19 Blitzfenster je Öffnen der Einstellungen: `CopyField` schaltet Knopf sichtbar vor `addWidget` (`ui/widgets.py:475`) | `ux2-probe-blitzfenster.py` |
| C-01 | OK | Endpunktprüfung echt/falsch | – |
| C-02 | Problem | Portwechsel flackert/verschwindet, Mausrad (Stand 2c5be9b) | – |
| C-03 | OK | Herzschlag; Wunsch ruhiger | – |
| C-04 | **OK (nach Fix)** | EXE 12:08: harter Stopp ohne Wiederverbinden (`unknown_delivery` sperrte dauerhaft); EXE 14:50: verbindet sich nach LAN-Ziehen selbst wieder | `ux2-C04-neue-exe\` |
| C-05 | Teilweise | UI-Weg blockiert (Port gesperrt); Generator `generate_session('COM8')` byte-identisch zu `Session-COM8.ucf` | `ux2-COM8-generator.ucf` |
| C-06 | Teilweise | Generator COM6 ↔ COM8: nur `ComNr`, `Name`, `ComNo` verschieden | `ux2-COM6-generator.ucf` |
| C-07 | **OK (nach Fixes)** | Netzwerk, Vierkanal: 600/600 lückenlos, Demo-Rampe exakt, sichtbares Ende (EXE 12:08 und 14:50). Vorher: Vierkanal-Session gegen Einkanal-Sender (0 Werte), Demo-Werte überschrieben (588/600, 596/600) – behoben | `ux2-C07-neue-exe\`, `ux2-netzwerk-final\` |
| C-08 | OK mit Anmerkungen | Genau `summary.json` + `details.jsonl`, keine Zugangsdaten; Zeit je Zeile seit `42dae1c`; Datei kumulativ (≈ 10 MB) | alle Protokoll-ZIPs |
| C-09 | OK (über B-07/C-05 belegt) | Wechsel bei Verbindung gesperrt mit Grund; Trennen fehlte im Betrieb (in Gestaltungsrunde) | – |
| C-10 | OK mit Hinweis | UART direkt: 1392 Takte lückenlos, Kanal 1 hält 325/325; Adapter steckt grün; nach Abziehen muss GSVmulti neu starten; Komponenten-Kachel zeigt fälschlich Portpaar | `ux2-C10-uart-direkt-2\` |
| D-01 | OK | Letzter Build: `Downloads\picam-ai-feat-integration(5)\…\GSVmulti-Bruecke.exe`, 13.11. 14:50:10, SHA-256 `CC605C672B1BD49F0E4FE44C2D9B323CB30A450EE5E046CEE0D939B343128442`; davor 13:16: `BAF785789BCCA180160FCA42963D66E3A2C24B0B3E459277D32F1B8D624BB252` | – |
| D-02 | OK | Symbole in der EXE sichtbar (Leonhards Bildschirmfotos) | Fotos 13.11. |
| D-03 | OK (funktional) | EXE erzeugt Vierkanal-Sessions; Roundtrip 600/600 belegt. Byte-Vergleich mit der Einkanal-Referenz entfällt, weil die Vorlage jetzt Vierkanal ist | `ux2-C10-GSVmulti_DispreadPi_COM6.ucf` |
| D-04 | OK | Prozess-Wächter 13:18–14:18 (EXE 13:16): 0 Kindprozesse; vorher nur eine PowerShell-Adaptersuche mit `CREATE_NO_WINDOW`, kein Fenster sichtbar | `ux2-*-kindprozesse.txt` |

### Echte Läufe (Vierkanal-Takt, „Kanal 1 hält“)

| Weg | Lauf | Takt | Ungültig | Halten | Bemerkung |
| --- | --- | --- | --- | --- | --- |
| Netzwerk | 13.11. 14:54 | 1 … 854 lückenlos | 27 % | 226/226 | keine Abbrüche |
| UART über Brücke | 13.11. 15:10 | 1 … 1181 lückenlos | 21 % | 239/239 | 2× `uart_frame_invalid`, je ≈ 2,5 s Neuanmeldung |
| UART über Brücke (unter Last) | 13.11. 14:38 | 1 … 2695 lückenlos | 23 % | – | 5 Abbrüche, 44 Takte gefüllt |
| UART direkt | 13.11. 15:03 | 1 … 1392 lückenlos | 24 % | 325/325 | – |
| Netzwerk (12:18, alte Werkbank) | 13.11. 12:18 | 1 … 2546 lückenlos | 60 % | 1509/1509 | lange Lücken bis 9,8 s durch `tracking_lost:rahmen_unstimmig` (Pi) |

## Die fünf wichtigsten Probleme (nach Schwere)

1. **UART über Brücke: unlesbare Rahmen.** `uart_frame_invalid` im Lauf, dazu 3× `uart_timeout` bei der Anmeldung. Kernel-Zähler `ttyAMA0`: 232 Rahmenfehler, 105 Breaks. Der Empfangstest scheitert (3/600, 124/600); im Lauf überbrückt die Brücke Abbrüche mit Füllzeilen. Ursache Signalqualität; Abhilfe Prüfsumme je Zeile mit Wiederholung oder elektrisch (in TODO).
2. **Einstellungen verlieren Daten und flackern.** Das Mausrad verstellt die Ports, das Fenster baut sich bei jeder Änderung neu auf, es ist höher als der Bildschirm, und beim Öffnen blitzen 19 Mini-Fenster auf (Ursache belegt). Fixes laut Pi-Sitzung auf Zwischenzweig bzw. in der Gestaltungsrunde, in den getesteten EXEs **nicht nachgeprüft**.
3. **Gestaltung: zu viel Text, Bewegung nur als Flackern** (Leonhards Gesamturteil). Werte sind nicht als Werte erkennbar, Hell wirkt stumpf, Auswahlkarten sind nur am Punkt klickbar, Enter wirkt nicht. Gestaltungsrunde der Pi-Sitzung (Wertfelder, Textbudget, Checklisten, Kontrast hell) **nicht nachgeprüft**.
4. **Viele ungültige Takte (20–60 %) mit langen Lücken** durch die Nachführung auf dem Pi (≈ 30 % `tracking_lost:rahmen_unstimmig`, Abschnitte bis 9,8 s). Das betrifft die Werkbank, nicht die EXE, prägt aber den Eindruck in GSVmulti.
5. **Bedienfallen zwischen Werkbank und Brücke:** UART-Kopplung als Sackgasse (Schritt 2 ohne Codefeld), fehlendes „Erneut prüfen“, belegter Port beim Moduswechsel (englische Meldung), Session gegen Port ohne Warnung, Port-Rollen COM4/COM5 unklar. Teilweise behoben (Port-Freigabe in Werkbank `5a31b41`, Kopplung `eef2991`), Rest in TODO.

Behoben und nachgeprüft: C-04 (Wiederverbinden), C-07 (600/600, sichtbares Ende), Demo-Verluste,
Vierkanal-Format, „Kanal 1 hält“ auf allen drei Wegen, A-06 (Adapter steckt grün), Laufdialog-Hinweis der Werkbank.

## Eindruck Leonhard (wörtlich)

Nach B-16:

> Generell bin ich nicht wirklich mit dem design zufrieden. Die animationen funktionieren nicht und sind bloß ein flackern. Es wird viel text verwendet der das ui unübersichtlich macht. infos wie com port, datei locations, frequenz usw... könnte man in graue felder packen so das erkennbar ist das diese werte sich ändern können und keine standard infos/texte sind). bitte reduziere den text, und lasse das ui für sich sprechen (funktionen, bedeutung, usw... soll durch das design kommuniziert werden)

B-21: „sieht alles gut aus (dunkel finde ich deutlich besser als design)“

B-24: „Wie gesagt finde ich das dunkle design deutlich besser, vielleicht könnte man versuchen das was das dunkle design "besser" wirken lässt auf das helle design zu übertragen (natürlich schwierig das die farbe ja eigentlich das design ausmacht und sich am ui eigentlich nichts ändert, aber vielleicht könnte man am kontrast oder so drehen)“

C-10: „die uart bridge sollte beendet werden wenn man den modus wechselt bzw. mit einem neuen modus den lauf starten will (es sollte automatisch alles auf den neuen modus eingestellt werden, damit später der user nicht auf fehlersuche gehen muss)“

Entscheidungen Leonhards während der Prüfung: Herzschlag-Punkt farbig (über die Pi-Sitzung); Kanal 1 hält den letzten gültigen Wert („Kanal 1 hält“; die frühere Antwort „Anzeigekanal, gehalten“ ist damit überholt).
