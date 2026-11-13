# Prüfung UX3 der Windows-Brücke (Gestaltungsrunde 3)

Prüfanleitung für Leonhard am Windows-PC (geplant Mittwoch, 2026-11-18).
Sie gilt für den Branch `wip/bruecke-ux3`. Dieser Stand ist **nicht** nach
`feat/integration` gemergt. Erst nach dieser Sichtprüfung wird gemergt.

Grundlage: Spec `docs/superpowers/specs/2026-11-11-windows-bruecke-ux2.md`,
Abschnitt „Runde 3“ (R3-1 … R3-6), Gestaltungsregeln in `windows/bridge/DESIGN.md`
und die offenen Oberflächenpunkte aus `TODO.md` („Befunde Smoketest 13.11.“).

## Was sich in Runde 3 geändert hat

Leitsatz: **Werte sind Felder, Zustände sind Formen, Text ist die Ausnahme.**

| Thema | Änderung |
| --- | --- |
| R3-1 Wertfeld | Ports, Pfade, Baudraten, Pi-ID, Endpunkt, Fingerabdruck und Zähler stehen in grauen Wertfeldern. Ein Klick auf das Feld kopiert den Wert, danach erscheint kurz ein Häkchen. |
| R3-2 Textbudget | Kurze Titel ohne „Schritt x von 5“. Erklärungen stehen im ⓘ. Einschränkungen erscheinen als Abzeichen: „Demo“, „Testfreigabe“, „nicht abgenommen“, „kein Empfangsnachweis“, „Einkanal“. Im Normalbetrieb erscheint keine Infobar. Die Zweitzeilen der Kacheln sind kürzer, z. B. „kein Nachweis“, „1342 Takte“ oder „COM4 ↔ COM5“. |
| R3-3 Session | Unter „Datei“ steht der Dateiname, daneben der Knopf „Neu erzeugen“. Darunter stehen „Ordner“ und ein beschrifteter Knopf **„Ordner öffnen“**. Es folgt die Checkliste „In GSVmulti einstellen“. „Record Hidden Channels“ ist Pflicht bei Vierkanal und gilt auch nach einem Neustart der App. |
| R3-4 Zustand über Form | Der Feldrand zeigt den Prüfzustand. Das Statussymbol steht vor der Meldung. Das Augen-Symbol zeigt oder verbirgt den Kopplungscode. Der Grund für eine gesperrte Aktion steht unter dem Knopf. „Verlassen“ steht rechts neben dem Schritttitel. |
| R3-5 Bewegung | Überblendung, Schrittübergang und Kachel-Farbblitz sind entfernt. Der Herzschlag pulst **langsamer**: 900 ms, höchstens alle 2 s. Eingaben, Haken, Auswahl und Fokus bleiben beim Neuaufbau erhalten. |
| R3-6 Fehler aus Teil B | Tooltips erscheinen als Box. Die Moduswahl lässt sich ohne laufende Übertragung wechseln und mit Pfeiltasten bedienen. Werkzeugfenster bleiben auf dem Bildschirm. Die Suche löscht keine Eingabe mehr. Die Demo-Einrichtung lässt sich mit Weiter und Zurück ganz durchlaufen. Enter löst den fokussierten Knopf aus. Der Beenden-Dialog aus dem Tray kommt nach vorn. |
| Schritt 5 | Bei Erfolg neutral: „600 von 600 Werten an COM5 übergeben“, ohne Warnfarbe. Ob GSVmulti die Werte aufgezeichnet hat, prüft die Brücke weiterhin nicht. Bei Verlust erscheint rot „Unvollständig: 588 von 600, 12 fehlen“ mit „Protokolle exportieren“ und „Test wiederholen“. |
| Strecke als Bild | Auf Brückenwegen steht unter den Kacheln „Brücke → COM4 ⇄ COM5 → GSVmulti“. |
| Taktzähler, Format | Bei einem Vierkanal-Takt zeigt die Weitergabe-Kachel „n Takte“. Das Detailfenster nennt Takte an COM, ungültige und aufgefüllte Takte. Die GSVmulti-Kachel nennt das Format von Session und Lauf. |
| Session passt nicht | Meldet der Pi ein anderes Format als die erzeugte Session (z. B. Lauf Vierkanal, Session Einkanal), zeigt die GSVmulti-Kachel „Session passt nicht“. Die Infobar bietet „Session neu erzeugen …“ im Format des Laufs an. |
| Journal | Neue Einträge: „Empfangstest beendet: n von 600 übergeben“, „Empfangstest unterbrochen: n von 600 übergeben“ mit Grund, „Übertragung gestoppt“, „Verbindung unterbrochen“, „Takt gestört“, „Verbindung wird aufgebaut“ und Ausgabewechsel des Pi. UART-Fehlercodes erscheinen mit kurzer Abhilfe. |
| Kopplung je Weg | Das Pi-Detailfenster nennt „Kopplung Netzwerk“ und „Kopplung UART“. Schritt 2 zeigt „Kopplung je Weg“, wenn die Wege verschieden gekoppelt sind. |
| Erneut prüfen | Nach einer Warnung oder einem Fehler einer Prüfung (Adapter, Portpaar, Adresse) steht neben der Meldung der Knopf „Erneut prüfen“. Der Umweg COM6 → COM0 → COM6 entfällt. |
| Testsession merken | Der Haken „Getrennte GSVmulti-Testsession verwendet“ bleibt gesetzt, solange die App läuft. |
| Portpaar-Prüfung | Die Meldung ist in beiden Reihenfolgen gleich: „Ports vorhanden und frei; Paar nicht geprüft“. Ein Seitentausch sieht nicht mehr wie ein Fehler aus. |
| UART direkt | Die Kachel „Komponenten“ nennt nur den USB-Adapter, kein altes Portpaar. |
| Beenden-Dialog | Bei Testfreigabe oder Demo sagt er „Die Übertragung an GSVmulti endet“. Vorher stand dort fälschlich „es werden keine Werte übertragen“. |

## 0. Bauen

1. Branch holen: `git fetch` und `git checkout wip/bruecke-ux3`. Ohne Git den
   Branch in Forgejo als ZIP laden.
2. Eine laufende ältere „GSVmulti-Brücke“ über das Tray-Menü beenden.
3. `windows\bridge\build-test.cmd` doppelklicken. Nach dem Build öffnet sich
   `dist-test`. Pfad und SHA-256 der EXE notieren.
4. Für die Demo-Zustände in Teil 2 die Quell-App mit der Umgebung aus
   `PRUEFUNG-UX2.md` Abschnitt 0 starten:
   `& $py -m dispread_bridge_app.main --demo-ui --state=<Zustand>`.

## 1. Bildschirmfotos (automatisch)

```powershell
& $py windows\bridge\probes\ux_tour.py ux3-bilder\100-hell   --theme light
& $py windows\bridge\probes\ux_tour.py ux3-bilder\100-dunkel --theme dark
$env:QT_SCALE_FACTOR = "1.5"; & $py windows\bridge\probes\ux_tour.py ux3-bilder\150-system --theme system
Remove-Item Env:QT_SCALE_FACTOR
```

In `tour.tsv` muss jede Szene `ok` tragen. Die Offscreen-Fotos vom Pi liegen
zum Vergleich in `docs/quellen/ux3-tour-2026-11/`.

## 2. Prüfliste (Leonhard bedient)

Die Spalte „Zustand“ nennt den Demo-Zustand (`--state=`) oder „EXE“ für die
echte App gegen den Pi.

| Nr. | Zustand | Handgriff | Erwartung |
| --- | --- | --- | --- |
| 1 | B1 | Hauptfenster ansehen | Kacheln mit höchstens drei Wörtern in der Zweitzeile. Darunter „Brücke → COM4 ⇄ COM5 → GSVmulti“. Keine Infobar. Abzeichen „kein Empfangsnachweis“ und „Einkanal“ unter der Sperrzeile. |
| 2 | B1 | Herzschlag-Punkt etwa 30 s beobachten (Demo pulst je Austausch) | Ruhiger Puls, höchstens etwa alle 2 s, kein Flackern |
| 3 | B1 | Auf ein Portfeld der Strecke klicken | Port in der Zwischenablage, kurz ein Häkchen |
| 4 | B1tick | Kachel „Weitergabe“ ansehen und anklicken | Zweitzeile „1342 Takte“. Das Detailfenster nennt Takte an COM 1342, davon ungültig 17, aufgefüllt 0 |
| 5 | B1tick | Kachel „GSVmulti“ anklicken | Format der Session: Vierkanal, Format des Laufs: Vierkanal |
| 6 | B1mismatch | Hauptfenster ansehen | GSVmulti-Kachel gelb „Session passt nicht / Lauf Vierkanal“. Infobar „Session passt nicht“ mit „Session neu erzeugen …“. Ein Klick öffnet den Speichern-Dialog. |
| 7 | B1tr | Kachel „Pi“ anklicken | Zeilen „Kopplung Netzwerk: gekoppelt“ und „Kopplung UART: nicht gekoppelt“ |
| 8 | E2b_route | Schritt 2 ansehen | Oben „Kopplung je Weg“ mit Netzwerk gekoppelt, UART nicht gekoppelt |
| 9 | E1manual | Zwei Ports wählen (COM4/COM5), dann tauschen (COM5/COM4) | Beide Male dieselbe Meldung. Neben einer Warnung steht „Erneut prüfen“; ein Klick prüft erneut |
| 10 | D1 | Adapter wählen, Ergebnis abwarten, „Erneut prüfen“ (nur bei Warnung oder Fehler sichtbar) | Prüfung läuft erneut, ohne dass die Auswahl gewechselt werden muss |
| 11 | E4session | „Session-Datei erzeugen …“, speichern | Neutrales Häkchen. „Datei“ mit Dateinamen und Symbol „Neu erzeugen“. Darunter „Ordner“ mit Pfad und beschriftetem Knopf **„Ordner öffnen“**, der den Explorer öffnet. Darunter die Checkliste. |
| 12 | E5 | Haken „Getrennte GSVmulti-Testsession verwendet“ setzen, mit „Zurück“ zu Schritt 4 und mit „Weiter“ wieder zu Schritt 5 | Der Haken ist noch gesetzt, „Test starten“ ist aktiv |
| 13 | E5done | Schritt 5 ansehen | Neutrale Infobar (blau, nicht gelb) „600 von 600 Werten an COM5 übergeben“. Kurzer Satz: in der Testsession nachsehen |
| 14 | E5short | Schritt 5 ansehen | Rot „Unvollständig: 588 von 600, 12 fehlen“, „Protokolle exportieren“ und „Test wiederholen“ |
| 15 | Bdirect | Hauptfenster ansehen | Strecke Adapter → COM9 → GSVmulti liest direkt. Keine Kacheln, kein Portpaar |
| 16 | E3 | Adresse tippen, dann „Suche wiederholen“ | Text bleibt stehen; während der Suche erscheint ein Ring |
| 17 | E1 bis E5 | „Weiter“/„Zurück“ durch die Demo-Einrichtung | Keine Überblendung, kein Flackern. Jeder Schritt erscheint; ein aktives „Weiter“ tut immer etwas |
| 18 | B1 | Nur Tastatur: Tab, Enter auf Kachel und Symbolknopf, Esc im Werkzeugfenster | Fokusrahmen sichtbar. Enter löst aus. Esc schließt das Fenster |
| 19 | B1 | Tray → „Brücke beenden …“ bei minimiertem Fenster | Hauptfenster und Dialog kommen nach vorn |
| 20 | EXE | Netzwerk verbinden, Empfangstest 600 Werte | Ende neutral „600 von 600 Werten an COM… übergeben“. Das Journal zeigt „Empfangstest beendet: 600 von 600 übergeben“ |
| 21 | EXE | Während eines Empfangstests das LAN kurz ziehen | Journal: „Empfangstest unterbrochen: n von 600 übergeben“ mit Grund. Schritt 5 endet spätestens nach etwa 70 s mit „Unvollständig“ |
| 22 | EXE | Echten Vierkanal-Lauf auf dem Pi starten (Testfreigabe) | Weitergabe-Kachel „n Takte“, der Zähler steigt. Passt die Session nicht zum Format, erscheint die Warnung aus Nr. 6 |
| 23 | EXE | Brücke beenden, während die Testfreigabe überträgt | Dialog: „Die Übertragung an GSVmulti endet …“ mit „Weiter übertragen“ |
| 24 | alle | Gesamteindruck hell und dunkel | Weniger Text? Ruhiger? Was stört noch? Freitext |

## Bekannt offen (nicht Teil dieser Runde)

* **Welche Session GSVmulti wirklich geöffnet hat, sieht die Brücke nicht.**
  Die Warnung „Session passt nicht“ vergleicht nur das Format des Laufs
  (vom Pi) mit dem Format der zuletzt erzeugten Session für diesen Weg und
  Port. Sessions werden je Port geführt; einen Portkonflikt mit der Datei
  kann es im Zustand der App nicht geben. Eine Session, die GSVmulti von Hand
  geöffnet hat, erkennt sie nicht.
* **Paarprüfung com0com:** Ohne verifiziertes Treiber-Inventar
  (`vcom` „driver_provider_unverified“) bleibt jedes Paar „nicht geprüft“.
  Die Meldung ist jetzt in beiden Reihenfolgen gleich, belegt aber nicht, dass
  die Ports ein Paar sind.
* **Testsession merken** gilt nur, solange die App läuft. Das ist Absicht:
  Ob die Testsession nach einem Neustart noch offen ist, weiß die App nicht.
* **Taktzähler** zählen nur die lokale COM-Annahme (WorkerStatus), nicht den
  Empfang in GSVmulti.
* **Neuaufbau der Einrichtung:** Die Einrichtung baut bei einem Datenwechsel
  weiterhin Widgets neu auf. Eingabe, Haken, Auswahl, Fokus und Bildlauf
  werden wiederhergestellt; flimmerfrei ist das nur nachgewiesen, wenn
  Nr. 16 und 17 ohne Befund bleiben.
* **Freigabetexte nach der Abnahme** („Testfreigabe – nicht abgenommen“)
  bleiben unverändert. Das ist eine Messpfad-Entscheidung, siehe `TODO.md`.
* **Ein Abbruch durch Zeitablauf** (keine Pi-Meldung) erscheint nicht als
  eigener Journaleintrag, nur als „Unvollständig“ in Schritt 5.

## Bericht

Wie bei UX2: `ux3-bericht.md` mit Nr., Ergebnis (OK / Problem / Nicht
geprüft), Beobachtung und Bild. Dazu die Bildordner und Protokollexporte als
`ux3-pruefung.zip`.
