# Prüfung UX2 der Windows-Brücke (Anleitung für eine lokale Claude-Sitzung)

Diese Datei ist der Auftrag für eine Claude-Code-Sitzung auf Leonhards
Windows-11-PC. Sie prüft die überarbeitete Oberfläche der App
„GSVmulti-Brücke“ (Branch `feat/bruecke-ux`) unter echten Bedingungen und
schreibt einen Bericht. Der Bericht geht zurück an die Pi-Sitzung, die die App
umbaut.

**Regeln für die prüfende Sitzung**

* Nichts am Code ändern, nichts committen oder pushen. Nur ausführen,
  beobachten, berichten.
* Die Oberfläche kann Claude nicht selbst bedienen. Teil A (Bildschirmfotos)
  läuft per Skript. Für die Teile B und C führt Leonhard die Handgriffe aus;
  die Sitzung nennt je Prüfpunkt den Handgriff und das erwartete Verhalten,
  fragt nach dem Ergebnis und trägt es ein. Höchstens drei Prüfpunkte auf
  einmal abfragen.
* Jede Beobachtung mit Prüfpunkt-ID (z. B. `B-07`) festhalten. Bei einem
  Problem: was zu sehen war, was erwartet war, Bild oder Datei dazu.
* Ein Häkchen oder „belegt“ gibt es nur für Dinge, die wirklich geprüft
  wurden. „Nicht geprüft“ ist ein gültiges Ergebnis.

## 0. Vorbereitung

1. Quelle holen: Mit Git
   `git clone -b feat/bruecke-ux https://ds1515.me-systeme.de/l.hentschke/picam-ai.git picam-ai-ux`.
   Die Zugangsdaten gibt Leonhard selbst ein. Ohne Git den Branch in Forgejo als
   ZIP laden und entpacken. Im Ordner `picam-ai-ux` weiterarbeiten.
2. Python 3.13 x64 finden: `py -3.13 -c "import sys; print(sys.executable)"`.
3. Eigene Umgebung anlegen (ändert nichts am System-Python):

   ```powershell
   py -3.13 -m venv .venv-ux
   .\.venv-ux\Scripts\python.exe -m pip install PySide6 pyserial cryptography==50.0.1 zeroconf aiohttp==3.14.3
   $env:PYTHONPATH = "$PWD\windows\bridge\src;$PWD\src"
   ```

4. Versionen notieren: Windows-Build (`winver`), Python, PySide6
   (`.\.venv-ux\Scripts\python.exe -c "import PySide6; print(PySide6.__version__)"`),
   Anzeigeskalierung, hell oder dunkel, Akzentfarbe, GSVmulti-Version.
5. **Wichtig:** Läuft eine ältere „GSVmulti-Brücke“ (EXE), sie vorher über
   das Tray-Menü beenden. Die App lässt nur eine Instanz zu.

## Teil A – Bildschirmfoto-Tour (automatisch)

Die Tour startet die App nacheinander mit Demo-Zuständen (ohne Pi, ohne
COM-Port), öffnet die Fenster und fotografiert sie samt Windows-Rahmen.
Während der Tour Maus und Tastatur nicht benutzen und keine anderen Fenster
in den Vordergrund holen.

```powershell
$py = ".\.venv-ux\Scripts\python.exe"
& $py windows\bridge\probes\ux_tour.py ux2-bilder\100-hell   --theme light
& $py windows\bridge\probes\ux_tour.py ux2-bilder\100-dunkel --theme dark
$env:QT_SCALE_FACTOR = "1.5"; & $py windows\bridge\probes\ux_tour.py ux2-bilder\150-system --theme system
$env:QT_SCALE_FACTOR = "2";   & $py windows\bridge\probes\ux_tour.py ux2-bilder\200-system --theme system
Remove-Item Env:QT_SCALE_FACTOR
```

Jeder Ordner enthält `tour.tsv`, in der jede Szene `ok` tragen muss, sonst
die Fehlermeldung. Danach jedes Bild ansehen (Read-Werkzeug) und prüfen:

| ID | Prüfung | Erwartung |
| --- | --- | --- |
| A-01 | Schrift | Segoe UI Variable (nicht Times/Arial); Daten wie Pi-ID in Cascadia Mono oder Consolas |
| A-02 | Abgeschnitten | Kein Text, Knopf oder Symbol abgeschnitten oder überlappend, auch bei 150 % und 200 % und in `07-betrieb-minimal-380` |
| A-03 | Symbole | Alle Symbole scharf, gleiche Strichstärke, in hell und dunkel sichtbar; keine leeren Kästchen |
| A-04 | Kontrast | Sekundärtext, Hinweise und deaktivierte Knöpfe lesbar, besonders im Dunkelmodus |
| A-05 | Rahmen | Werkzeugfenster (`10`–`22`) haben einen normalen Windows-Rahmen mit Titel und Schließen-Knopf |
| A-06 | Grün | Grün nur bei belegten Zuständen („Installiert“, „Verbunden“, „steckt“); „Session-Datei erzeugt“, „Aktiv“ und „Übernahme bestätigt“ sind **nicht** grün |
| A-07 | DUT-Zeile | Die Sperrzeile steht in jedem Hauptfenster-Bild |
| A-08 | Gesamteindruck | Je Bild ein Satz: aufgeräumt? klar gegliedert? Was stört? |

## Teil B – Bedienung im Demo-Modus (Leonhard bedient)

Start (jeder Zustand eine eigene Instanz, vorher die alte schließen):

```powershell
& $py -m dispread_bridge_app.main --demo-ui --state=B1
```

Andere Zustände per `--state=`: `B3` (Pi antwortet nicht), `Bnone` (nicht
eingerichtet), `first_run` (erster Start), `E3` (Einrichtung Adresse),
`E1manual` (Portpaar), `E2b` (Kopplungscode), `D1` (UART direkt),
`E4session` (Session), `Bdirect` (Betrieb UART direkt).

| ID | Zustand | Handgriff | Erwartung |
| --- | --- | --- | --- |
| B-01 | B1 | Über die Info-Symbole (ⓘ) der sechs Kacheln fahren | Tooltip erklärt kurz, was der Prüfpunkt bedeutet und was nicht |
| B-02 | B1 | Eine Kachel anklicken | Eigenes Fenster mit Windows-Rahmen öffnet sich, lässt sich ziehen, bleibt vor dem Hauptfenster; Esc schließt; zweiter Klick holt dasselbe Fenster nach vorn |
| B-03 | B1 | Im Pi-Fenster Kopierknöpfe für Pi-ID, Endpunkt und Fingerabdruck drücken, jeweils in den Editor einfügen | Wert vollständig in der Zwischenablage; Symbol wird kurz zum Häkchen |
| B-04 | B1 | Symbolleiste unten: alle Symbole überfahren | Jedes hat einen Tooltip; Einstellungen, Protokolle exportieren, Info, Beenden |
| B-05 | B1 | „Protokolle exportieren“ → Speichern | Fenster nennt den Inhalt vor dem Speichern; danach Häkchen, Pfad, „Ordner öffnen“ öffnet den Explorer |
| B-06 | B1 | Herzschlag-Punkt vor dem Zustandssatz beobachten (ca. 30 s) | Pulsiert ruhig etwa alle 1,5 s; wirkt aktiv, nicht hektisch |
| B-07 | B1 | Moduswahl-Knopf im Kopf („Netzwerk ⌄“) | Fenster mit drei Karten; während der Übertragung gesperrt mit Grund |
| B-08 | first_run | App starten | Moduswahl öffnet sich von selbst; Pfeiltasten wechseln die Karte; „Wechseln“ erst nach Auswahl aktiv |
| B-09 | B10 | Einstellungen öffnen | Abschnitte Weg, Pi, Ports, GSVmulti-Session, Protokolle, Über; Fenster scrollt; Werte kopierbar |
| B-10 | B1 | Einstellungen öffnen | Weg, Pi und Ports schreibgeschützt mit Schloss und Grund |
| B-11 | E3 | In „Adresse oder Name“ `pi.local` tippen, dann `gibtsnicht.example` | Nach kurzer Pause Ring, dann Häkchen „Pi erreichbar, Zertifikat passt“, bzw. rotes Symbol mit Meldung und nächster Aktion |
| B-12 | E3 | „Suche wiederholen“ (Pfeilkreis-Symbol) | Dreht oder zeigt einen Ring während der Suche |
| B-13 | E3 | Schließen-Symbol (×) rechts neben dem Schritttitel | Einrichtung wird verlassen, Betrieb erscheint |
| B-14 | E1manual | Zwei Ports wählen | Prüfung läuft; Ergebnis ok oder Warnung mit Text |
| B-15 | E2b | Kopplungscode `12345` tippen | Sofort Formatfehler; Weiter bleibt gesperrt |
| B-16 | E4session | „Session-Datei erzeugen …“ | Speichern-Dialog mit Vorschlag `GSVmulti_<Pi>_<COMx>.ucf`; danach neutraler Haken, Pfad, Hinweise (Autoscale; bei ausgeblendeten Kanälen Pflichtschritt „Record Hidden Channels“) |
| B-17 | E-Schritte | „Weiter“/„Zurück“ durch die Einrichtung | Kurze Überblendung in Laufrichtung; „Gespeichert“-Zeile erscheint und verschwindet |
| B-18 | D1 | Adapter wählen | Prüfung, dann „bereit“; Kopf zeigt „UART direkt – Adapter noch offen“ bzw. den Port |
| B-19 | Bdirect | Betrieb ansehen | Keine Pi-Verbindungsaussagen; Adapter steckt/fehlt; Pi, Ausgabe und Weitergabe „nicht benutzt“ |
| B-20 | beliebig | Windows: Einstellungen → Barrierefreiheit → Visuelle Effekte → Animationseffekte **aus**, App neu starten | Keine Bewegung (kein Puls, keine Überblendung), alle Zustände und Häkchen trotzdem sichtbar. Danach wieder einschalten |
| B-21 | beliebig | Windows auf dunkel umstellen, App neu starten | Folgt dem Farbschema; Akzentfarbe = Windows-Akzent |
| B-22 | B1 | Nur Tastatur: Tab, Shift+Tab, Enter, Esc, Pfeiltasten | Sichtbarer Fokusrahmen; alles erreichbar; Esc schließt Fenster |
| B-23 | B1 | Hauptfenster schließen (×) | App geht in den Infobereich; Hinweis nur beim ersten Mal; Tray-Menü „Öffnen“ holt sie zurück |
| B-24 | gesamt | Leonhards Eindruck | Wirkt die Bedienung bestätigend, ruhig, aktiv? Zu viel oder zu wenig Bewegung? Was fehlt? Freitext übernehmen |

## Teil C – Echte App gegen den Pi (Leonhard bedient)

Voraussetzung: Der Pi-Dienst `dispread-werkbank-bruecke` läuft, und das
com0com-Paar COM7 ↔ COM8 ist vorhanden. Start ohne `--demo-ui`:
`& $py -m dispread_bridge_app.main`. Die App verwendet ihren normalen
Datenordner. Die Kopplung von heute bleibt erhalten.

Der Weg „UART über Brücke“ ist **nicht** Teil dieser Prüfung. Die App spricht
dort jetzt mit 460 800 Baud, der Pi ist noch nicht umgestellt.

| ID | Handgriff | Erwartung / was festhalten |
| --- | --- | --- |
| C-01 | App starten, Einstellungen → Pi → Endpunkt: echte Adresse prüfen lassen, dann eine falsche (z. B. Tippfehler im Namen) | ok mit „Zertifikat passt“; Fehler nennt die Stufe (Name, Verbindung, Zertifikat). Dauer bis zum Ergebnis notieren (soll < 3 s) |
| C-02 | Einstellungen → Ports: COM7/COM8 wählen, dann COM7/COM1 (oder ein anderes Nicht-Paar) | ok bzw. Warnung „nicht als com0com-Paar erkannt“; COM-Liste vollständig mit Bezeichnungen |
| C-03 | Verbinden (Netzwerk) | Herzschlag pulsiert bei Pi-Kontakt; Kachel Pi „Verbunden“ |
| C-04 | Pi-Dienst kurz unerreichbar (z. B. LAN-Kabel ziehen oder WLAN aus, 20 s) | Ring statt Puls, Infobar mit Zähler; **keine** aufblitzenden Konsolenfenster (früherer Fehler); danach automatisch wieder verbunden |
| C-05 | „Session-Datei erzeugen …“ für COM8, als `ux2-COM8.ucf` speichern; dann `fc /b ux2-COM8.ucf docs\quellen\bruecke-testlauf-2026-11-06\Session-COM8.ucf` | Ausgabe „keine Unterschiede“ (byte-identisch zur belegten Session) |
| C-06 | Session für einen anderen Port erzeugen (z. B. COM6) und mit `fc` gegen die COM8-Datei vergleichen | Unterschiede nur in `ComNr`, `Name` („Chan. 6_1“) und `ComNo` |
| C-07 | Die in C-05 erzeugte Datei in GSVmulti als Session öffnen, Demo-Empfangstest der App starten (600 Werte), in GSVmulti aufzeichnen | Session lädt ohne Rückfrage; Werte kommen an. TDMS/TXT sichern: das ist der Roundtrip-Beleg für die erzeugte Session (N3) |
| C-08 | Protokolle exportieren; ZIP öffnen | Genau `summary.json` und `details.jsonl`; darin kein Token, Kopplungscode oder Passwort (Suche nach `token`, `offer`, `password`, `credential`) |
| C-09 | Moduswahl während der Verbindung öffnen | Wechsel gesperrt mit Grund; nach Trennen wählbar |
| C-10 | Nur falls der FTDI-USB-Adapter da ist: Moduswahl → „UART direkt“ → D1–D4 durchgehen, Adapter einmal abziehen | Adapter erkannt und geprüft; Session für dessen Port; im Betrieb „steckt“ bzw. „fehlt“ innerhalb weniger Sekunden; danach wieder auf „Netzwerk“ zurückstellen |

## Teil D – EXE bauen und Kurztest

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\bridge\build-test.ps1 -Python (& py -3.13 -c "import sys; print(sys.executable)")
```

| ID | Prüfung | Erwartung |
| --- | --- | --- |
| D-01 | Build | Läuft durch; Pfad und SHA-256 der EXE notieren |
| D-02 | EXE starten | Symbole sichtbar (keine leeren Kästchen; prüft, dass QtSvg mitgepackt ist) |
| D-03 | Session in der EXE erzeugen (wie C-05) | Funktioniert (prüft, dass die Vorlage mitgepackt ist); `fc /b` wie C-05 |
| D-04 | 2 min laufen lassen, Pi einmal unerreichbar machen | Keine aufblitzenden Konsolenfenster |

## Bericht

Datei `ux2-bericht.md` im Ordner `picam-ai-ux` anlegen:

```markdown
# Bericht Prüfung UX2 – <Datum>
Umgebung: Windows <Build>, Python <…>, PySide6 <…>, Skalierung <…>, Thema <…>, GSVmulti <…>, Branch-Commit <git rev-parse HEAD oder ZIP>

| ID | Ergebnis (OK / Problem / Nicht geprüft) | Beobachtung | Bild/Datei |
| --- | --- | --- | --- |
| A-01 | … | … | … |
…

## Die fünf wichtigsten Probleme (nach Schwere)
1. …

## Eindruck Leonhard (wörtlich)
…
```

Dann alles zusammenpacken:

```powershell
Compress-Archive -Path ux2-bericht.md, ux2-bilder, ux2-COM8.ucf, <GSVmulti-Aufnahme aus C-07> -DestinationPath ux2-pruefung.zip
```

Leonhard lädt `ux2-pruefung.zip` in die Pi-Sitzung hoch.
