# Kamera-Workbench: HTTPS, Einstelltabelle und Shell

> **Kamerastand beachten:** Der Abschnitt „Kamera einstellen“ dokumentiert
> Picamera2-Controls und mechanischen Fokus der früheren IMX500. Die aktive
> Kamera ist seit 2026-09-25 die Logitech StreamCam mit UVC-Reglern
> ([Hardwareprofil](../HARDWARE_PROFILE.md),
> [Kamera-Inbetriebnahme](../CAMERA_COMMISSIONING.md)). Vor dem Einstellen
> die in der laufenden Workbench tatsächlich angebotenen Regler prüfen;
> die alten Control-Namen unten sind keine StreamCam-Anleitung.

Die Werkbank bietet Kamerabild, Log und echte Bash-Tabs. Alle Zugriffe
sind mit dem Linux-Passwort von `me-systeme` geschützt. Seit dem Messpfad live
richtet `/live` die StreamCam ein und liest mit dem Dot-Matrix-Leser.
Die alte Werkbankseite bekommt gedrosselte Bilder vom `CameraOwner`;
Kamerabedienung erfolgt nur auf `/live`. Das alte `run` bezeichnet dort
weiterhin den Betrieb mit festen Einstellungen, ohne Messwertfreigabe.
Die nachfolgenden alten Einstelltabellen und Kamerakommandos beschreiben
den früheren Ablauf; für die StreamCam gilt der Abschnitt „Live-Seite `/live`“.

## Start

Im Projektverzeichnis:

```bash
bash scripts/install-workbench.sh
./.venv/bin/dispread init-tls
./.venv/bin/dispread serve --port 8081
```

`init-tls` nur einmal ausführen. Bereits vorhandene Schlüssel werden nicht
überschrieben. In dieser Implementierungssession wurde das Zertifikat bereits
unter `var/workbench/tls/` erzeugt; du kannst direkt
`./.venv/bin/dispread serve --port 8081` starten.

Mit diesem Startbefehl ist die Werkbank unter der zuvor vom Nutzer
eingestellten internen Adresse und Port 8081 erreichbar:

```text
https://100.122.154.35:8081
```

Auf diesem Pi belegt MEhub den Port 8080, deshalb `--port 8081`.
Dafür `https://100.122.154.35:8081/live` öffnen.

**Es ist jetzt HTTPS, nicht mehr HTTP.** Alten Vorschauprozess vorher mit
`Ctrl+C` beenden. Der kompatible Einstieg bleibt:

```bash
./.venv/bin/python examples/17_camera_display_preview.py
```

Die gesamte Oberfläche verlangt das normale Linux-/SSH-Passwort von
`me-systeme`, nicht das separate root-Passwort. Passwörter werden weder
protokolliert noch gespeichert. Nach acht Stunden ist eine erneute Anmeldung
nötig. Fünf Anmeldeversuche pro Minute und Client sind möglich.

## Live-Seite `/live`

Stand 2026-10-14: gebaut und Einrichtung am Aufbau geprüft, Messlauf offen.
Im Projektverzeichnis starten:

```bash
./.venv/bin/dispread serve --port 8081
```

Beim Start aus einem Git-Worktree `PYTHONPATH=src` vor den Befehl setzen,
damit dessen Quellen statt eines anderen editierbar installierten Checkouts
geladen werden.

`https://<host>:8081/live` öffnen. Ohne Anmeldung führt die Seite zu
`/login?next=/live`; nach Anmeldung mit dem Linux-Passwort von `me-systeme`
geht es zurück auf `/live`. API-Aufrufe bleiben ohne Anmeldung bei 401.
`CameraOwner` hält die StreamCam für die gesamte Serverlaufzeit; ein
Harvest-Skript erhält währenddessen „belegt“. Ein Laufstopp gibt die
Kamera nicht frei, damit die Vorschau weiterlaufen kann.

### Einrichten, prüfen und bestätigen

1. StreamCam an USB3, GSV-2AS seriell angeschlossen, Kamera senkrecht auf
   Displaymitte stellen. Reflexionen vermeiden. Vorlagen und gültige
   Timing-Kalibrierung müssen vorhanden sein; fehlende oder veränderte
   Dateien sperren den Laufstart.
2. Zellentext leer lassen, um ihn seriell vom GSV-2AS zu lesen. Alternativ
   die neun Zeichen der Zellen 0–8 einschließlich Leerzeichen eingeben,
   etwa `+0.60972 `. Es ist kein Textfeld für alle 16 Zellen.
3. **Einrichtung starten**. Die Seite zeigt Schritt und vergangene
   Sekunden: Fokus, Kamera, Standbilder, Vorschlag. Fokus per Bergsteigen,
   acht Bilder je gemitteltem Standbild und bis zu drei Suchversuche;
   Stabilitätsprüfung in der Werkbank 15 s, Harvest-CLI weiterhin 30 s.
   Nach einem Abbruch bleiben Grund und Einrichtungshinweis sichtbar.
4. Overlays und Prüfungen ansehen: Lage der Anzeige, Zellenraster,
   Rasterversatz und Gegenlesen. **FEHLER** sperrt die Bestätigung.
   Bei **WARNUNG** muss die bedienende Person den Befund prüfen und
   ausdrücklich „WARNUNG zur Kenntnis genommen“ abhaken.
5. Namen eintragen, „Einheit mV/V und Format geprüft“ abhaken und
   **Bestätigen** drücken. Erst diese namentliche Bestätigung speichert
   das Profil und die Bedienbestätigung (Konzept §4).

Am 2026-10-14 lieferten nach N7 vier Einrichtungen Vorschläge mit
Gesamt-WARNUNG wegen einer Proxy-Prüfung: zunächst `raster` WARNUNG wie
bei `sc7`, beim vierten Versuch `kanten` WARNUNG und `raster` OK.
Die Einrichtungen dauerten 47/55/49/45 s; Rasterversatz und Gegenlesen
waren jeweils OK. Bestätigung und Messlauf stehen noch aus;
das war kein formaler Abnahme-Lauf.

### Schwankende letzte Ziffer

Das Zellentextfeld am besten leer lassen: Dann liest die Werkbank den
Referenztext vom GSV-2AS vor und nach jedem Standbild. Ändert er sich
während der Aufnahme, wiederholt sie diese bis zu fünfmal; bleibt die
Anzeige unruhig, maskiert sie die wechselnden Zellen mit `?`. Bei manueller
Eingabe schwankende Ziffern selbst mit `?` markieren, etwa `+0.4678?`;
acht Zeichen werden um die leere neunte Zelle ergänzt. Passt der Text nur
zum ersten Standbild, weist die Einrichtung gezielt darauf hin.

Gegenlesen bedeutet jetzt: Alle unmaskierten Zellen müssen in jedem
Standbild lesbar sein und mit dessen Referenztext übereinstimmen,
darunter mindestens fünf der sieben Zahlenzellen. Maskierte Zellen
bleiben beim Vergleich außen vor; Belichtungs-, Kontrast- und
Leerzellenfehler bleiben wirksam. Ein gelesenes Zeichen, das dem
Referenztext widerspricht, ist **FEHLER** und sperrt Bestätigung und Lauf.
Fehlt Lesbarkeit ohne Widerspruch, lautet das Urteil **WARNUNG**;
der normale Lauf bleibt gesperrt. Der Referenztext korrigiert niemals
die Messwerte des Lesers.

### Lauf gesperrt / Testlauf

„Lauf gesperrt“ bedeutet: Der Leser konnte die Einrichtungsbilder beim
Gegenlesen nicht erfolgreich vergleichen oder das Gegenlesen fehlt. Bei
**WARNUNG** ist Bestätigen weiter möglich, ein normaler Lauf bleibt gesperrt.
Ein Widerspruch zur Referenz ist **FEHLER** und sperrt auch die Bestätigung.
Kamera senkrecht auf die Displaymitte ausrichten und neu einrichten; das Zellentextfeld dabei leer
lassen, damit der Text vom GSV-2AS kommt. Andere Warnungen, etwa zu Raster
oder Kanten, werden wie bisher bei der Bestätigung quittiert.

Unter „Testmodus (nur zu Testzwecken)“ lässt sich die Lesesperre ausdrücklich
übergehen. Haken setzen und den zusätzlichen Dialog bestätigen. Der Testlauf
zeigt, welche Zeichen der Leser vermutet hätte; unsichere Zellen sind benannt.
Diese Vermutungen sind verworfen und erscheinen nie als Messwert im JSONL-Audit.
Alle Werte des Testlaufs sind nicht freigegeben und dürfen nicht für Messungen
verwendet werden. Das rote Banner kennzeichnet auch den beendeten Testlauf.
`var/live/<sitzung>/run-NN/TESTLAUF.json` hält Sperrgrund, Bedienperson und
Startzeit fest; `session.json` enthält die Testmarkierung und die zehn
häufigsten Vermutungen. Die einzelnen Records in `records.jsonl` tragen keine
eigene Testmarkierung: Ein Laufordner mit `TESTLAUF.json` wird nicht geerntet
und nicht ausgewertet wie ein regulärer Lauf. Für einen regulären Lauf neu und
erfolgreich einrichten.

### Lauf und Wertstatus

Nach Bestätigung **Lauf starten**. Ein frischer freigegebener Wert erscheint
grün mit Einheit und Bildnummer. Andere Zustände zeigen den Status und
Ablehnungsgrund statt gültiger Ziffern:

| Status | Bedeutung |
| --- | --- |
| VALID | Frischer, freigegebener Wert; Live-Freigabe verlangt zwei bestätigende Bilder. |
| TRANSITION | Noch nicht über die erforderlichen Bilder bestätigt. Echte Sprünge werden nicht geglättet. |
| UNREADABLE | Bild, Tracking oder Ablesung abgelehnt; Ablehnungsgrund prüfen. |
| STALE | Kein aktueller gültiger Wert: Ablesung älter als 0,5 s, Lauf beendet oder Verbindung/Anmeldung verloren. |

Verbindungsfehler oder abgelaufene Anmeldung setzen die Anzeige auf STALE;
auch wenn länger als 1,5 s kein erfolgreicher Statusabruf kam. Polling und
Verbindungsfenster können die sichtbare Umschaltung verzögern (schlimmstenfalls
etwa 2 s). Ein stillstehender Kamerastream beendet den Lauf erst nach dem
OpenCV-Select-Timeout (etwa 10–20 s), nicht nach 2 s. Die Vorschau kann auf
dem letzten Bild stehen bleiben; sie allein beweist keine aktuelle Messung.
**Lauf stoppen** beendet den Lauf, die Kamera läuft für Vorschau weiter.

Der Freigabehinweis bleibt sichtbar:

> Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V — andere Lichtquellen und Geräte nicht geprüft.

Es gibt noch keine serielle Ausgabe an GSVmulti (OQ-07). ECC-Tracking bei
Wertwechseln ist noch ungemessen. Der geplante Bedienerlauf umfasst ≥ 10 min,
fünf Werte über `set norm` und einmal 2 s Displayabdeckung; danach
`tracking_lost` und `track_score` auswerten (R13, siehe [TODO](../../TODO.md)).

### Dateien und lokale Bedienung

| Ablage | Inhalt |
| --- | --- |
| `var/live/<sitzung>/setup/` | Einrichtungsbilder, Bericht und Overlays; `cell-text.json` mit ursprünglichem/maskiertem Text und Quelle, `failure.json` mit Abbruchschritt, Grund und UTC-Zeit bei Fehlern. |
| `var/live/<sitzung>/profile.json` und `confirmation.json` | Bestätigtes Profil und namentliche Bedienbestätigung. |
| `var/live/<sitzung>/run-NN/records.jsonl` | ValueRecords des einzelnen Laufs; `raw_text` enthält die geparste Zahl, nicht 16 Zellen. |
| `var/live/<sitzung>/run-NN/session.json` | Laufmetadaten, Zeitbasis/Versatz BOOTTIME−MONOTONIC, aufgezeichnete Timing-Kalibrierung, Freigabehinweis, Bedienbestätigung, Zusammenfassung und Endgrund. |

Die Timing-Kalibrierung wird aufgezeichnet, nicht auf den Live-Wert angewandt.
Zeitstempel tragen ihre Zeitbasis; unbekannte Unsicherheit ist `None`.
Die derzeitige `JsonlSink`-Rotation würde nach etwa 7 h alte
Auditgenerationen verwerfen; dauerhafte Aufbewahrung ist ein Folgeschritt.

Lokale Befehle über den privaten Steuer-Socket:

```bash
dispread live status
dispread live setup
dispread live setup --cell-text '+0.60972 '
dispread live camera
dispread live stop
```

`status` zeigt den Zustand, `setup` startet die Einrichtung, `camera`
verbindet die Kamera neu, `stop` stoppt den Messlauf. Kameraneuverbindung
nach Einrichtung behält die Setup-Regler. Über den Socket gibt es weder
Bestätigung noch Laufstart; beides verlangt die angemeldete Oberfläche.
`dispread stop` beendet dagegen den Werkbankserver.

### Typische Fehler

| Meldung / Befund | Nächster Schritt |
| --- | --- |
| `keine_startlage`, `startlage_mehrdeutig`, Rasterversatz 2j FEHLER | „Kamera senkrecht auf Displaymitte stellen und neu einrichten“; Lage, Schärfe und Reflexionen prüfen. FEHLER nicht bestätigen. |
| Auflösung unter der Schwelle | Kamera näher stellen und neu einrichten. |
| `tracking_lost:…` / „Anzeige verloren — Kamera bewegt? Neu einrichten“ | Kameralage prüfen und neu einrichten; bei Wertwechseln Trackingbefunde für die Auswertung sichern. |
| „Erst einrichten und bestaetigen“ | Vorschlag prüfen und mit Namen bestätigen, dann Lauf starten. |
| „Einrichtung meldet WARNUNG“ | Warnbefund prüfen und ausdrücklich zur Kenntnis nehmen. |
| Timing-Kalibrierung fehlt/ungültig, Vorlagenprüfsumme falsch, Referenzbild verändert | Richtige Dateien bereitstellen; bei verändertem Referenzbild neu einrichten. |
| Kamera nicht gestartet / „belegt“ | Anderen Kameraprozess beenden; gegebenenfalls Kamera neu verbinden. |
| „Anmeldung abgelaufen“ / „Verbindung zur Werkbank verloren“ | Neu anmelden bzw. Serververbindung prüfen; angezeigtes STALE bleibt ungültig. |

Ein `tracking_lost`-Hinweis kann einen Endfehler auf der Seite verdecken;
bei auffälligem Stopp `session.json` prüfen. Ein tatsächlich hängender
Leser kann Laufstopp blockieren und einen Serverneustart erfordern.

## Zertifikat auf Windows

Ein Firmenzertifikat kann über `--cert` und `--key` verwendet werden. Für das
lokal erzeugte Zertifikat:

1. Nur `var/workbench/tls/cert.pem` über deine bekannte SSH-Verbindung nach
   Windows kopieren. **Den privaten Schlüssel `key.pem` auf dem Pi lassen.**
2. Fingerabdruck auf dem Pi mit dem bei `init-tls` ausgegebenen Wert vergleichen:

   ```bash
   openssl x509 -in var/workbench/tls/cert.pem -noout -fingerprint -sha256
   ```

3. Die Zertifikatdatei gegebenenfalls in `picam.crt` umbenennen, öffnen und für
   den aktuellen Windows-Benutzer als vertrauenswürdiges Zertifikat installieren
   (bei verwalteten Geräten nach Firmenvorgabe durch die IT).
4. Erst danach über die zum Zertifikat passende Adresse anmelden.

Die Standardeinstellungen nehmen die interne IP sowie localhost/127.0.0.1 in
das Zertifikat auf. Für eine andere Adresse `init-tls --host ADRESSE` in einem
neuen Zertifikatverzeichnis verwenden. SSH-Tunnel bleiben mit
`serve --host 127.0.0.1` möglich, ebenfalls mit HTTPS und Anmeldung.

## Oberfläche: Kamera, setup-Tab und echte Shell

Kamera oben links, darunter die Tab-Leiste, Log rechts; auf schmalen
Bildschirmen werden die Bereiche gestapelt. Der erste Tab heißt `setup` und ist
nach der Anmeldung **sofort aktiv** — die Einrichtung braucht kein Kommando
mehr. `+` öffnet eine weitere Shell, `×` schließt sie samt laufenden Prozessen.
Maximal acht Shell-Tabs. Browser schließen, Verbindung verlieren oder abmelden
lässt die Shells weiterlaufen; erneutes Anmelden verbindet wieder. Serverende
schließt alle Shells. Die Sessions überleben keinen Serverneustart.

Jede Shell läuft als `me-systeme` im Startverzeichnis der Workbench. Der PATH
verwendet die Projekt-venv. `sudo`, Editoren, `Ctrl+C` und Größenänderungen sind
normal nutzbar. Bis zu 2 MiB Terminalausgabe pro Tab bleiben für Wiederverbindung
im Speicher; bei Überschreitung erscheint ein Hinweis auf gekürzte Historie.

### Einstelltabelle bedienen

Jede Zeile zeigt Parameter, Sollwert und daneben Istwert oder Hinweis. Werte mit
endlicher Auswahl stehen als Auswahlfeld bereit; **`true`/`false` oder JSON
tippt niemand mehr**. Belichtungszeit, Verstärkung und Kontrast sind Zahlenfelder
mit den Grenzen der laufenden Kamera und einer Schnellwahl (Minimum,
Kameradefault, aktueller Istwert, Maximum). Freitext gibt es nur noch für einen
neuen Profilnamen.

Gesperrte Zeilen und Aktionen nennen ihren Grund, statt erst beim Absenden zu
scheitern: `ExposureTime` bleibt gesperrt, solange die Belichtungsautomatik an
ist, und `run` ist erst wählbar, wenn bestätigte ROI, Livebild, übernommene
Kameraeinstellung und feste Belichtung zusammenkommen. Anzeigebereich und
Erkennungsfilter sind reine Anzeigezeilen — die ROI wird im Kamerabild
bearbeitet, die Filter über `serve`-Optionen oder die Profildatei.

| Taste | Wirkung |
| --- | --- |
| Pfeile | Zeile wählen |
| Enter | Auswahlfeld der Zeile öffnen |
| `a` | Automatische Einstellhilfe starten |
| `y` | Fertigen Vorschlag übernehmen |
| `c` | Einstellhilfe abbrechen |
| `s`, `n` | Speichern / speichern unter neuem Profilnamen |
| `o`, `r` | Profil laden / ungespeicherte Werte verwerfen |
| `d`, `l` | Profilkonflikt zugunsten Datei / lokaler Vorschau auflösen |

Dieselben Tasten stehen in der Aktionsleiste unter der Tabelle als Schaltflächen
mit dem Buchstaben in Klammern.

### Dieselbe Tabelle im Terminal

Ohne Browser — etwa direkt über SSH — zeigt

```bash
dispread tui
```

genau dieselben Zeilen, Optionen und Aktionen; sie kommen aus einer gemeinsamen
Quelle (`src/dispread/workbench/fields.py`). Enter öffnet dort eine Auswahlliste
statt eines Eingabefelds, bei Zahlen eine Liste mit Schnellwahl und ein
Zahlenfeld (Tab wechselt dazwischen). `q` kehrt zur Shell zurück, ohne die
Kamera zu beenden. Direkt über SSH gehen dieselben Befehle mit
`./.venv/bin/dispread`.

## Kamera einstellen

Es werden nur unterstützte Controls angeboten. Belichtungsautomatik `an`
regelt selbst. Auf `aus` umstellen übernimmt die aktuellen Ist-Werte als
Startpunkt und entsperrt `ExposureTime` (µs) und `AnalogueGain`. `Contrast` beeinflusst die
Bildaufbereitung. Auflösung oder Bildrate starten den Stream neu.

**Historischer IMX500-Stand:** Die AI Camera hat mechanischen Fokus.
Fokusassistenz `an` vergrößert die
bestätigte ROI im Vorschaufenster; die Tabelle zeigt daneben einen relativen
Schärfewert. Am kleinen Objektiv mit dem Fokuswerkzeug einstellen; keine
motorische Autofokusfunktion vortäuschen. Die StreamCam hat dagegen
`focus_automatic_continuous` und `focus_absolute`; für reproduzierbare
Aufnahmen setzt [CameraSettings](../../api/frames.md) die Automatik aus und
liest den festen Fokuswert zurück. Reflexionen zuerst durch Position,
Abschirmung und kontrolliertes Licht verringern: [Optischer Aufbau](../OPTICAL_SETUP.md).

<figure class="tour-figure" data-scene="bedienung-kamera" markdown="1">
<figcaption markdown="span">Die StreamCam am GSV-Aufbau: USB3-Anschluss, YUYV in voller Auflösung, Autofokus aus und ein fester Fokuswert.</figcaption>
</figure>

Tabelle und CLI melden Sollwerte und die beobachtete Belichtung getrennt. Die interne
Revision `applied_revision` bedeutet gesetzte Controls mit eingeschwungener
manueller Belichtung (Toleranzen: 3 % ExposureTime, 8 % Gain); Kontrast wird von
Picamera2 nicht als gemessener Istwert zurückgemeldet. Bei nicht bestätigbarer
Übernahme wird ein Fehler angezeigt.

Auto-Setup verlangt im Modus `setup` einen bestätigten Displaybereich. Es lässt
zuerst die Belichtungsautomatik einregeln und prüft neun Kombinationen um diese
Werte. Jede Kombination wird über mehrere Bilder bewertet. Originaleinstellungen
werden anschließend wiederhergestellt; erst `y` übernimmt den Vorschlag.
Bei ungeeignetem Bild gibt es keinen Vorschlag. Die Suche beweist keine
vollständige Abbildung multiplexender Segmente ([OQ-20](../open-questions.md)).

### Ernte-Aufstellung mit `harvest-setup.py`

Für ein Ernteprofil gibt es zusätzlich einen geführten Kommandozeilenlauf;
er ist unabhängig vom Auto-Setup dieser Workbench. `assist` führt den
Fokus-Sweep aus, nimmt zwei Standbilder mit mindestens 30 Sekunden Abstand,
passt das Punktraster an und prüft unter anderem dessen Versatz. Dazu braucht
er standardmäßig den seriellen GSV-2AS-Eingang (`/dev/ttyUSB0`, 38400 Baud).
Offline lassen sich die ersten neun Anzeigezellen mit `--cell-text` oder
`--cell-text-file` vorgeben:

```bash
./.venv/bin/python scripts/harvest-setup.py assist \
    --out var/diagnostics/setup-lauf1 --device-id gsv2as-01 --session-id lauf1
```

Ein erfolgreicher Lauf schreibt Standbilder, `proposal.json` und Overlays.
Sieh dir die Overlays und die Prüfungen an; erst danach bestätigt `confirm`
den Vorschlag als Profil. Ein Fehler bei der Rasterversatzprüfung erzeugt
keinen Vorschlag. Optionales Gegenlesen braucht eine Vorlagendatei samt
erwartetem SHA-256. Das Verfahren ist eine Einrichtungshilfe, kein Nachweis
für andere Geräte oder Lichtverhältnisse. Details zu Ernte und Prüfbildern:
[Datensatz-Sammelmodus](11-datensatz-sammeln.md).

<figure class="tour-figure" data-scene="bedienung-assistent" markdown="1">
<figcaption markdown="span">Der Ablauf von <code>harvest-setup.py assist</code>: Fokus, zwei Standbilder, Punktraster, Prüfungen und am Ende ein Vorschlag mit Kontrollbildern, den erst ein Mensch bestätigt.</figcaption>
</figure>

## Box bearbeiten und Annotationen sammeln

**Stand 2026-09-10, zweistufiger Ablauf** (löst den früheren, rein
tastaturgesteuerten Ablauf ab — Beweggründe und Bedienerbefund im
`CHANGELOG.md`, Eintrag "TUI-style two-stage confirm workflow"). Im Modus
`setup` oder `annotate`:

1. Kameraansicht fokussieren und `e` drücken oder doppelt klicken. Das
   Originalbild wird eingefroren; auch bei weiterlaufender Kamera bleibt
   dieses Bild maßgeblich. Solange keine Geometrie in dieser Sitzung
   bestätigt wurde, läuft die Kandidatensuche weiter und zeigt mehrere
   dünne, anklickbare Vorschlagsboxen.
2. **Stufe A — ROI:** den passenden Kandidaten anklicken, oder ✎ neben der
   aktiven Box drücken, um sie per Ziehen (Körper) oder Eckziehen
   (Perspektive) von Hand anzupassen. Während des Bearbeitens wird aus ✎ ein
   ✕, das die Bearbeitung abbricht und zur vorherigen Position zurückkehrt.
   ✓ übernimmt die aktuelle Position.
3. Nach ✓ sucht der Server automatisch im entzerrten Innenbereich nach
   Vorzeichen und Ziffern und schlägt eine OCR-Box vor (**Stufe B**). Dieselbe
   ✎/✓-Logik gilt jetzt für die gelbe OCR-Box — Vorzeichenbox, Ziffernzellen
   und Punkte sind genau das Raster, das der Segmentleser verwendet.
4. **Stufe B, optional — 🎯 kalibrieren:** statt Ziffernabstand,
   Vorzeichenbreite und die übrigen Rasterverhältnisse einzeln mit den
   Reglern der Einstelltabelle zu justieren, einmal den auf der Anzeige
   abgelesenen Wert eintippen (dasselbe Eingabefeld wie bei `annotate`). Der
   Server sucht daraus (`layout.autofit`) das Rasterverhältnis, das genau
   diesen Wert dekodiert, und zeigt Ergebniszeile mit gelesenem Wert und
   Trennschärfe. Passen mehrere deutlich verschiedene Raster gleich gut,
   erscheint ein sichtbarer Hinweis auf ein flaches (mehrdeutiges) Optimum —
   dann im Bild prüfen, nicht blind übernehmen. Der Vorschlag ist bis hierher
   reine Vorschau; er verändert das aktive Profil **nicht**.
5. ✓ an der OCR-Box übernimmt einen offenen 🎯-Vorschlag zuerst
   (`layout.set_many`) und bestätigt danach beide Rahmen endgültig
   (entspricht dem früheren `Strg+Enter`). Das ist die **einzige** Stelle, an
   der überhaupt etwas bestätigt wird — auch mit 🎯 bleibt das so. Ein Klick
   in den (jetzt inaktiven) grünen ROI-Rahmen während Stufe B führt zurück zu
   Stufe A, ohne die Kandidatensuche erneut zu starten. `Esc` verwirft die
   gesamte Bearbeitung, jederzeit.

`setup` übernimmt das normierte Vierpunktpolygon ins aktive Profil und
entzerrt es für die OCR. Der innere `ocr_box` wird danach ausgeschnitten und
auf das 400×160-Leserformat skaliert; mit `s` dauerhaft speichern. Alte Profile
aus Schema 1 und 2 werden beim Laden automatisch auf Profilschema 3 migriert
und beginnen mit einem inneren Rahmen über die volle ROI. `annotate` speichert
das eingefrorene Original als PNG zusammen mit Quad, OCR-Rahmen, Anzeigenrolle,
Originalmetadaten, Bildnummer und Profil unter
`var/workbench/annotations/`. Ändert sich das Profil während des Editierens,
werden reine OCR-Layoutänderungen (`digits`, `decimals`, Vorzeichen,
Rasterverhältnisse und Ziffernabstand) sofort im Overlay übernommen und bleiben
über die OCR-Box-✓ bestätigbar. Der cyanfarbene Kreis markiert die profilfeste
Dezimalposition; er
ist noch keine optische Punktmessung (OQ-17). Kamera- oder andere
Profiländerungen machen das eingefrorene Bild weiterhin ungültig; dann erst ein
neues Bild einfrieren.

Diese Annotation ist zunächst ein **Geometriebeispiel**, noch kein vollständig
beschriftetes OCR-Trainingsbeispiel: Sie enthält weder den abgelesenen Text noch
einen Referenzwert als Label. Für die Weiterarbeit an OQ-23 müssen mehrere
solche Bilder anschließend mit der sichtbaren Wahrheit beschriftet und vor dem
Abstimmen in getrennte Entwicklungs- und Testsätze aufgeteilt werden. Die
Labels bleiben außerhalb von `ValueReader.read` und `ReleaseGate.evaluate`.

Gelbe Rechtecke sind automatische Vorschläge, grüne markieren bestätigte
Bereiche. Die ROI ist an den bestätigten Aufbau gebunden; es gibt noch keinen
Tracker. Ein verschobenes Gerät muss neu eingerichtet werden. Kein Modell wird
beim Verschieben oder Speichern trainiert.

Eine automatische Live-Ermittlung des Ziffernrahmens ist grundsätzlich
möglich, braucht aber bestätigte reale Beispiele und eine getrennte
Fehlerauswertung. Aus nur einem Frame können leuchtende Segmente, Blende,
Dezimalpunkte und Einheit nicht sicher als Rastergrenzen unterschieden werden.
Die Workbench übernimmt deshalb derzeit ausschließlich die sichtbare manuelle
Kalibrierung; sie rät keine Grenze, die später als bestätigt gelten würde.

## Profile und Befehle

Profile liegen unter `var/workbench/profiles/NAME.json` und enthalten
Kameraeinstellungen, Anzeigebereich, Rolle, Erkennungsfilter und den
`layout`-Block mit dem Zahlenformat (`digits`, `decimals`, `has_sign`, `unit`).
Das Zahlenformat ist die Grundlage der Ablesung: der Segmentleser tastet gegen
dieses Raster ab und rät nicht. Der `setup`-Tab und `dispread tui` bieten dafür
dieselben Auswahlzeilen: 3–8 Ziffernstellen, 0–4 Nachkommastellen oder
`unbestimmt`, Vorzeichenstelle ja/nein, eine kurze Liste bestätigter Einheiten
und die relative Breite der Vorzeichenstelle. Unmögliche Kombinationen sind
gesperrt. `unbestimmt` bedeutet ausdrücklich nicht automatische Erkennung: Weil
der Dezimalpunkt noch nicht optisch geprüft wird, lehnt die Freigabevorschau den
Wert mit `decimal_point_unknown` ab.

Unter den Einstellungen stehen drei reine Anzeigezeilen. `ablesung` zeigt
Rohtext, Zahlenwert und die aus dem Profil stammende Einheit;
`freigabepruefung` zeigt Status und Ablehnungsgründe; `evidenz` zeigt gelesene
Stellen, Segmentkontrast, kleinste Segmentmarge, unlesbare Stellen und
Ausschnittqualität. Auch ein Status `valid` ist hier nur eine Vorschau:
`released` bleibt `false`, es entsteht kein `ValueRecord` und es wird nichts
seriell ausgegeben. Die Modell-/Segmentkonfidenz ist nicht als
Fehlerwahrscheinlichkeit kalibriert.

Der aktuelle Leser unterstützt helle LED/VFD-Segmente auf dunklem Grund.
Inverse LCD-Anzeigen bleiben [OQ-13](../open-questions.md), die sichtbare
Prüfung des Dezimalpunkts und der Einheit [OQ-17](../open-questions.md).
Statusanzeigen wie `DC` werden in diesem Schritt ebenfalls nicht gelesen.
Vorschauänderungen werden nicht automatisch gespeichert. Gültige externe
Dateiänderungen werden nach kurzem Entprellen übernommen. Bei ungültigem JSON
bleibt die letzte Konfiguration aktiv; bei gleichzeitig ungespeicherten lokalen
Änderungen erscheint ein Konflikt. `resolve local` behält die Vorschau, ein
anschließendes `save` überschreibt die Datei bewusst.

```bash
dispread status
dispread stop
dispread mode setup
dispread camera get
dispread camera set AeEnable false
dispread camera set ExposureTime 20000
dispread camera set AnalogueGain 1.5
dispread camera auto-setup
dispread camera accept
dispread camera cancel
dispread camera focus on
dispread profile save mein-geraet
dispread profile load mein-geraet
dispread profile revert
dispread profile resolve disk
dispread mode annotate
dispread mode run
```

`run` verlangt Livebild, bestätigte ROI und übernommene feste Belichtung. Jede
Profiländerung verlässt `run` und führt nach `setup`. Es entsteht weiterhin kein
Messwertdatensatz. Die lokale Steuerung verwendet einen Unix-Socket in einem
privaten 0700-Verzeichnis, standardmäßig `/tmp/dispread-UID/control.sock`.
`DISPREAD_SOCKET` kann einen anderen Socket angeben.

`dispread stop` spricht ausschließlich den privaten lokalen Unix-Socket an; die
authentifizierte Web-API bietet keinen Fernabschaltbefehl. Beim Beenden haben
auch blockierende Kamera-`stop`/`close`-Aufrufe eine Zeitgrenze, damit ein
Treiberproblem den gesamten Prozess nicht endlos festhält.

Für Entwicklung ohne Kamera:

```bash
./.venv/bin/dispread serve --simulate
```

Simulierte Bilder tragen die Zeitbasis `synthetic`; daraus keine reale Latenz
ableiten. Statusalter/Verarbeitungsrate verwenden CLOCK_MONOTONIC, Logzeiten UTC.
Aufnahmezeitstempel realer Bilder bleiben in SENSOR_BOOTTIME mit unbekannter
Semantik und Unsicherheit `None` erhalten.

### Schatten und angepasste Toleranz

„Ungleichmaessige Beleuchtung“ weist auf einen Kontrastsprung zwischen
benachbarten Zellen hin, etwa durch den Kameraschatten. Entferne den Schatten
oder schatte das ganze Display gleichmäßig ab und richte neu ein. Der Hinweis
allein ändert das Urteil des Gegenlesens nicht.

Scheitert nur die strikte Zellschwelle, kann die Einrichtung mit einem seriell
vom GSV-2AS erfassten Referenzwert eine **angepasste Toleranz** anbieten. Sie
berechnet den Faktor aus beiden Standbildern und liest beide erneut gegen.
Manuell eingegebener Zellentext reicht hierfür nicht aus. Wähle den Haken
„Angepasste Toleranz ×… verwenden“ ausdrücklich und bestätige auch die WARNUNG.
Ohne Auswahl bleibt die Lesesperre bestehen; ein Testlauf ist weiterhin separat
möglich.

Die Gegenprobe belegt nur die Übereinstimmung in dieser Aufstellung und ist
**keine Validierung** gegen eine Referenzaufzeichnung. Die Referenz korrigiert
keine Lesung; Abstand zur zweitbesten Klasse, zwei bestätigende Bilder und
STALE-Regeln gelten weiter. Ein Toleranzlauf trägt ein gelbes Banner und bei
VALID den Detailtext „erweiterte Toleranz ×… – nicht validiert“.
`confirmation.json` und `session.json` halten den Faktor als `reader_tolerance`
fest; `summary.tolerance_frames` zählt gültige Datensätze, bei denen mindestens
eine Zelle die ursprüngliche Vorlagenschwelle überschritt.

## Prüfstand dieser Implementierung

63 automatische Tests einschließlich TLS-Login mit Testauthentifizierung,
WebSocket-Shell, Wiederverbindung/Logout, Profilkonflikten, exakter Bildzuordnung
von Annotationen, Tastaturbedienung der TUI sowie der Prüfung, dass **jede
angebotene Auswahl vom Controller auch angenommen wird**, sind erfolgreich. Echter Kamera-
Worker separat geprüft: 25 Bilder, 14,8 Bilder/s, sauberes Beenden.

Die Browseroberfläche wurde mit lokal simuliertem Transport in Chromium geprüft
(Bild, Terminaldarstellung, Einfrieren); der setup-Tab zusätzlich mit 21
Prüfpunkten über eine `file://`-Seite mit eingespielter echter `/status`-Antwort
(Auswahlfelder, gesperrte Zeilen mit Grund, Tastenkürzel, Namensabfrage). Ein vollständiger HTTPS-Durchlauf in
dieser lokalen Chromium-Headless-Umgebung bleibt bei der Navigation hängen;
Python/curl und der TLS/WSS-Integrationstest funktionieren. Dieser Befund ist
[OQ-21](../open-questions.md). Windows-Zertifikatsvertrauen, Anmeldung mit deinem
wirklichen Linux-Passwort und der gemeinsame Betrieb im Windows-Browser sind
noch manuell abzunehmen. Es gibt keinen Testpasswort-Modus im Produkt.

`layout.autofit`/`layout.set_many` sind mit synthetischen Anzeigen getestet
(`tests/test_workbench.py`, u. a. dass die Suche außerhalb des Controller-Locks
läuft und ein eingefrorenes Bild nach der Rasterübernahme weiter bestätigbar
bleibt); der 🎯-Knopf selbst ist noch nicht am Windows-Browser gegen ein
reales Gerät geprüft.

## Fertig, wenn

Dieser Prototyp folgt nicht dem Kapitelraster aus der
[Lernpfad-Übersicht](README.md) (kein `Vertrag`, keine `Fallen`-Liste) — diese
Liste prüft die gebauten Bedienwege und den noch offenen Lauf am Aufbau.

* [ ] Ein fehlgeschlagenes Gegenlesen sperrt den Lauf; ein ausdrücklich gestarteter Testlauf trägt Banner und `TESTLAUF.json`.
* [ ] `/live` führt ohne Anmeldung zum Login und danach zurück; bei Portkonflikt
  startet die Werkbank mit `--port 8081`.
* [ ] Einrichtung zeigt Schritte, Sekunden, Overlays und Prüfungen;
  FEHLER sperrt, WARNUNG verlangt Kenntnisnahme, Bestätigung einen Namen.
* [ ] Ein bestätigter Lauf zeigt VALID/TRANSITION/UNREADABLE/STALE;
  Altwerte und Verbindungsverlust erscheinen nie als aktuelle gültige Ziffern.
* [ ] Bedienerlauf ≥ 10 min mit `set norm`-Wertwechseln und 2 s Abdeckung
  ausgewertet, einschließlich `tracking_lost`/`track_score`; Zahlen in
  VALIDATION und Aufbau/Deutung im Laborjournal dokumentiert (noch offen).
* [ ] Profil und `confirmation.json` liegen im Sitzungsordner, Audit und
  Laufmetadaten je in `run-NN/`; Freigabehinweis bleibt sichtbar.
* [ ] `dispread live status|setup|stop|camera` funktioniert lokal;
  Bestätigung und Laufstart erfolgen in der Oberfläche.
* [ ] `npx playwright test -c playwright.live.config.ts` prüft Login,
  Einrichtung, Fehler, frischen Wert und STALE ohne reale Kamera.

Die folgenden Punkte betreffen die alte Werkbankseite:

* [ ] `./.venv/bin/pytest -q` und `./.venv/bin/ruff check src tests examples scripts`
  laufen beide fehlerfrei durch.
* [ ] Im Browser: Bild einfrieren (`E`/Doppelklick), Stufe A (ROI) und
  Stufe B (OCR-Box) je per ✎/✓ bestätigen — der bisherige Ablauf ist
  unverändert.
* [ ] In Stufe B 🎯 drücken, einen Wert eintippen, der zur angezeigten Anzahl
  Ziffernstellen passt: die Ergebniszeile zeigt gelesenen Wert und
  Trennschärfe, **ohne** dass die Einstelltabelle sich bereits ändert.
* [ ] Erst nach ✓ steht das vorgeschlagene Raster im aktiven Profil (`s`
  speichert es dauerhaft); `confirmed` wird ausschließlich durch diesen
  ✓-Klick wahr, nie durch 🎯 allein.
* [ ] Ein absichtlich unpassender Tippwert (z. B. eine Ziffer zu viel) liefert
  eine Ablehnung mit Begründung statt eines stillschweigend falschen Rasters.
* [ ] Dieses Kapitel ist aktuell (dieser Abschnitt und der Ablauf oben) und
  `CHANGELOG.md` trägt den zugehörigen Eintrag.
