#!/usr/bin/env python3
"""Symboltest fürs Terminal: welche Zeichen stellt die Schrift sauber und einspaltig dar?

Aufruf: python3 scripts/picam-glyphs.py
Jede Zeile: Nummer, Zeichen zwischen zwei senkrechten Strichen, Bedeutung.
Gut ist ein Zeichen, wenn es sichtbar ist (kein Kästchen/Fragezeichen) und der
rechte Strich genau eine Spalte nach dem linken steht (|x|, nicht |x | oder |x|<versetzt>).
"""

GROUPS = {
    'Zustand': [('●', 'läuft / aktiv'), ('○', 'aus'), ('◐', 'halb / Einrichtung'), ('◆', 'Markierung'),
                ('✓', 'in Ordnung'), ('✔', 'in Ordnung, kräftig'), ('✗', 'Fehler'), ('✘', 'Fehler, kräftig'),
                ('▲', 'Warnung'), ('■', 'Stopp'), ('◉', 'Aufnahme / Kamera'), ('⦿', 'Ziel / Kamera 2')],
    'Bewegung': [('→', 'nach'), ('↻', 'neu starten'), ('⟳', 'neu starten 2'), ('⇄', 'Verbindung'),
                 ('⇅', 'Datenfluss'), ('↯', 'Störung'), ('▸', 'weiter'), ('▾', 'aufgeklappt'), ('›', 'Unterpunkt')],
    'Dinge': [('⌂', 'Start / Dashboard'), ('☰', 'Liste / Protokoll'), ('⚙', 'Einstellungen'), ('⏻', 'Ein/Aus'),
              ('⏵', 'Start'), ('⏸', 'Pause'), ('⏹', 'Stopp'), ('⏚', 'Masse / GND'), ('⎓', 'Gleichspannung'),
              ('⌁', 'Signal'), ('≋', 'Netzwerk'), ('⚿', 'Schlüssel / Zertifikat'), ('▤', 'Speicher'),
              ('◷', 'Uhr / Zeit'), ('⌸', 'Datei'), ('⎘', 'Kopie'), ('⧉', 'Ordner'), ('ⓘ', 'Info'), ('ℹ', 'Info 2'),
              ('☺', 'Konto'), ('⚑', 'Fahne / Hinweis'), ('✎', 'bearbeiten'), ('⌕', 'suchen'), ('⚡', 'Strom (oft breit)')],
    'Balken': [('█', 'voll'), ('▓', 'dicht'), ('▒', 'mittel'), ('░', 'locker'), ('▁▂▃▄▅▆▇█', 'Verlauf'),
               ('▏▎▍▌▋▊▉', 'Achtel'), ('▀▄', 'Halbblöcke'), ('⠋⠙⠹⠸⠼⠴', 'Drehzeichen'), ('╭─╮│╰╯', 'runde Ecken')],
}


def main() -> None:
    number = 0
    for group, glyphs in GROUPS.items():
        print(f'\n{group}')
        for glyph, meaning in glyphs:
            number += 1
            print(f'  {number:>2}  |{glyph}|  {meaning}')
    print('\nBitte die Nummern nennen, die als Kästchen/Fragezeichen erscheinen oder deren rechter Strich verrutscht.')


if __name__ == '__main__':
    main()
