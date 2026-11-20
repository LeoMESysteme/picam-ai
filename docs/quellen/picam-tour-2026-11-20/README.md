# picam-Konsole: Bildschirmfotos zur Sichtprüfung (20.11.2026)

Echte Textual-Ausgaben der Konsole (`picam`), gerendert mit Beispieldaten
in festen Terminalgrößen. Fensterrahmen und Titel gehören zur Bildhülle,
nicht zur App. Ein Statussymbol kann in diesen PNGs um eine halbe Zelle
verrutscht wirken (Schriftersatz beim Rendern); im Terminal steht es
spaltengenau.

| Bild                                    | Zeigt                                                         |
| --------------------------------------- | ------------------------------------------------------------- |
| [01](01-uebersicht-120x40.png)          | Übersicht 120×40: Punkte mit Handlungsbedarf, Instanz         |
| [02](02-uebersicht-80x24.png)           | Übersicht 80×24 (Standardgröße)                               |
| [03](03-dienst-80x24.png)               | Dienst mit Aktionen `s`/`r`/`l`                               |
| [04](04-neustart-bestaetigen-80x24.png) | Neustart bestätigen: genauer Befehl, Fokus auf „Abbrechen“    |
| [05](05-lauf-aktiv-gesperrt-80x24.png)  | Lauf aktiv: Dienstaktionen gesperrt, Grund in der Statuszeile |
| [06](06-dienst-ausgefallen-80x24.png)   | Dienst ausgefallen: abhängige Bereiche „–“, Abhilfe           |
| [07](07-kalibrierung-fehlt-80x24.png)   | Einrichtungsbefund mit Abhilfe                                |
| [08](08-version-update-80x24.png)       | Version mit Update (`u`) und Rückweg (`z`)                    |
| [09](09-update-dialog-80x24.png)        | Update: Archiv wählen                                         |
| [10](10-protokoll-80x24.png)            | Protokoll, mitlaufend, Warnungen/Fehler farbig                |
| [11](11-konfiguration-80x24.png)        | Konfiguration: Port, Brückenname, Discovery                   |
| [12](12-hilfe-80x24.png)                | Tastenhilfe `?`                                               |
| [13](13-schmal-liste-60x20.png)         | Schmal (60 Spalten): nur die Liste                            |
| [14](14-schmal-bereich-60x20.png)       | Schmal: Bereich geöffnet, `esc` zurück                        |
| [15](15-zu-klein-40x12.png)             | Unter 48×14: Hinweis statt kaputtem Layout                    |
| [16](16-start-80x24.png)                | Startbild 80×24: Objektiv, LCD kompakt, Prüfergebnisse        |
| [16 GIF](16-start-animation-100x30.gif) | Startbild in Bewegung (ruckeliger als im Terminal, s. u.)     |
| [17](17-start-160x45.png)               | Startbild 160×45: LCD als Punktraster                         |
| [18](18-hoch-120x40-meldungen-unten.png) | Ab 34 Zeilen: letzte Meldungen unter dem Bereich             |
| [19](19-breit-180x50-karten-meldungen.png) | Ab 150 Spalten: Meldungen rechts, Betriebskarten          |
| [20](20-breit-180x50-kalibrierung.png)  | Breit: Einrichtungsbefund neben den Meldungen                 |

Gestaltung nach dem `tui-design`-Skill: eine Trennlinie zwischen Liste und
Bereich, kein Außenrahmen; je Zustand ein Zeichen plus eine Farbe; Werte
in der Liste nur farbig, wenn sie Handlungsbedarf zeigen; Hinweise als
schmaler Balken links. Keine Messwerte, keine laufenden Zähler.

Neu erzeugen: `PYTHONPATH=src ./.venv/bin/python docs/quellen/picam-tour-2026-11-20/capture.py AUSGABEORDNER [FALL …]`
schreibt SVGs; PNGs daraus mit CairoSVG (eigene venv, nicht in der Projekt-venv).
`capture_intro.py AUSGABEORDNER` schreibt die Einzelbilder des Startbilds
mit ihrer Zeit im Namen; das GIF entsteht daraus mit Pillow. Jedes
Bildschirmfoto braucht rund 0,1 s, darum zeigt das GIF etwa 7 statt der
20 Bilder je Sekunde im Terminal.

Startbild und Bewegung (Nachtrag 20.11. mittags, Wunsch nach Startseite
und besserer Nutzung großer Fenster): Das Objektiv ist ein schattierter
Torus mit gewölbtem Glas und Glanzlicht (Donut-Prinzip), das LCD zeigt
„picam“ im 5×7-Zeichensatz des HD44780 wie das Displaytech 161A. Eine
Lesezeile läuft einmal darüber. Übergänge bleiben kurz: Startbild aus-,
Konsole einblenden (0,2–0,3 s), Bereichswechsel und Dialoge 0,15 s,
geänderte Werte in der Liste kurz hinterlegt, Drehzeichen nur während
einer Prüfung oder Dienstaktion.
