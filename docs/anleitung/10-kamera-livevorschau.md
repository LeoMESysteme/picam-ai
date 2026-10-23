---
weg: bedienen
---

# Kamera-Workbench: HTTPS, Einstelltabelle und Shell

> **Kamerastand beachten:** Der Abschnitt „Kamera einstellen“ zeigt die
> StreamCam-Regler als Karten; die eingeklappten historischen Blöcke betreffen
> die Picamera2-Controls und den mechanischen Fokus der früheren IMX500. Die aktive
> Kamera ist seit 2026-09-25 die Logitech StreamCam mit UVC-Reglern
> ([Hardwareprofil](../HARDWARE_PROFILE.md),
> [Kamera-Inbetriebnahme](../CAMERA_COMMISSIONING.md)). Vor dem Einstellen
> die in der laufenden Workbench tatsächlich angebotenen Regler prüfen;
> die historischen Control-Namen gelten für die frühere IMX500.

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
überschrieben. Wenn `cert.pem` und `key.pem` bereits unter
`var/workbench/tls/` vorhanden sind, kannst du direkt
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
./.venv/bin/python examples/17_camera_display_preview.py --port 8081
```

Die gesamte Oberfläche verlangt das normale Linux-/SSH-Passwort von
`me-systeme`, nicht das separate root-Passwort. Passwörter werden weder
protokolliert noch gespeichert. Nach acht Stunden ist eine erneute Anmeldung
nötig. Fünf Anmeldeversuche pro Minute und Client sind möglich.

## Live-Seite `/live`

Stand 2026-10-21: gebaut; Einrichtung und mehrere Bedienerläufe mit
serieller Referenz sind dokumentiert. Eine allgemeine Live-Freigabe folgt
daraus nicht. Der beendete Werteplan-Versuch zeigt bei großen Wertwechseln
`tracking_lost:low_score` und später selbstständige Erholung. Bei Faktor 2
und 5 fehlt VALID in stabilen Referenzfenstern; die Rückstellung ist geprüft.
Eine unabhängige Ursachenabsicherung steht aus
([Auswertung](../VALIDATION.md#messpfad-live-werteplan-2026-10-21),
[OQ-26](../open-questions.md#oq-26)).
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
   acht Zeichen für Vorzeichen und Zahlenzellen eingeben, etwa
   `+0.60972`; die neunte, leere Zelle wird ergänzt. Neun Zeichen mit
   abschließendem Leerzeichen sind ebenfalls zulässig. Bei schwankenden
   Zellen `?` verwenden. Es ist kein Textfeld für alle 16 Zellen.
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
waren jeweils OK. Damals standen Bestätigung und Messlauf noch aus;
seitdem gibt es die Bedienerläufe vom 2026-10-21. Die Einrichtungen vom
2026-10-14 waren kein formaler Abnahme-Lauf.

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
Die Vermutungsanzeige ist kein freigegebener Messwert. **Die technische
Sperre im Audit ist jedoch unvollständig:** `LiveSession.step()` schreibt
den Pipeline-Record unverändert, auch wenn ein späteres Bild `VALID` ergibt
([OQ-44](../open-questions.md#oq-44)). Deshalb sind alle Records dieses
Laufordners als Testdaten von Messungen auszuschließen; ein einzelnes
`status=valid` hebt die Testmarkierung des Laufs nicht auf. Das rote Banner
kennzeichnet auch den beendeten Testlauf.
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
| TRANSITION | Noch nicht über die erforderlichen Bilder bestätigt (`awaiting_confirmation`), oder die Anzeige wechselt gerade („Wert wechselt“, `anzeige_wechselt`): höchstens 3 Zellen sind Mischziffern, alle lesbaren Zellen gleichen dem letzten freigegebenen Wert, und dieser ist höchstens 0,5 s alt. Kein Wert wird freigegeben; echte Sprünge werden nicht geglättet. Ein Finger über 1–3 Zellen kann kurz ebenfalls als „Wert wechselt“ erscheinen, danach STALE. |
| UNREADABLE | Bild, Tracking oder Ablesung abgelehnt; Ablehnungsgrund prüfen. |
| STALE | Kein aktueller gültiger Wert: Ablesung älter als 0,5 s, Lauf beendet oder Verbindung/Anmeldung verloren. |

Verbindungsfehler oder abgelaufene Anmeldung setzen die Anzeige auf STALE;
auch wenn länger als 1,5 s kein erfolgreicher Statusabruf kam. Polling und
Verbindungsfenster können die sichtbare Umschaltung verzögern (schlimmstenfalls
etwa 2 s). Ein stillstehender Kamerastream beendet den Lauf erst nach dem
OpenCV-Select-Timeout (etwa 10–20 s), nicht nach 2 s. Die Vorschau kann auf
dem letzten Bild stehen bleiben; sie allein beweist keine aktuelle Messung.
**Lauf stoppen** beendet den Lauf, die Kamera läuft für Vorschau weiter.

### Referenzaufzeichnung und Abgleich

Vor **Lauf starten** ist „Referenz vom GSV-2AS mitschreiben“ eingeschaltet.
Der Lauf hält den Port nur während der Aufzeichnung. Fehlt das Gerät oder
antwortet es innerhalb von zwei Sekunden nicht mit lesbaren Telegrammen,
startet die Bildlesung **ohne Referenz**; Seite und `session.json` nennen den
Grund. Einrichtung und Lauf dürfen den Port nicht gleichzeitig verwenden.
Die Referenz schreibt ausschließlich ein separates Audit und korrigiert
niemals Leser, Freigabe oder Messwertdatensätze.

Optional erzeugt „Werteplan (set norm)“ Sprünge, etwa `1:20,2:20,0.5:20`
(Faktor:Sekunden; Faktoren 0,15 bis 1 580 000, positive endliche Haltezeit).
Erst die zusätzliche Bestätigungsfrage erlaubt den Plan. Dieser
schreibt in den RAM des GSV-2AS (laut Messung 2026-10 EEnow = 0 an diesem Gerät, kein EEPROM-Verschleiss; nicht live geprüft).
Ohne Werteplan werden **keine** Befehle an den Port geschrieben.

Ein Plan verwendet denselben gespeicherten Rückstellpunkt wie
`sync-record.py`: `var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json`.
Normierung und Dezimalpunkt müssen vor dem ersten Schreibschritt passen;
eine Abweichung verhindert den Plan. Die Referenzaufzeichnung läuft dabei
rein lesend weiter; `schedule_aborted` nennt den Grund in Status und
`session.json`. Ein fehlender oder ungültiger Rückstellpunkt verweigert den
Laufstart. Es gibt auf der Seite keine Übersteuerung.
Beim Stoppen werden zuerst weitere Planschritte gesperrt und dann die
Ausgangswerte zurückgeschrieben und gelesen. Währenddessen steht
„Werte werden zurückgestellt …“ auf der Seite. Gerät verbunden lassen.
Die bewährten Wartezeiten bleiben erhalten; der Abschluss wartet bis zu
20 Sekunden. Bei Zeitüberschreitung oder fehlender Bestätigung steht in
Status und `session.json`: „Rückstellung nicht bestätigt – Gerät prüfen (gsv-registers.py)“.
Die reine Leseaufzeichnung beendet sich innerhalb von zwei Sekunden.
Auch das reguläre Herunterfahren des Servers stellt einen aktiven Plan zurück.

**Nach `kill -9` oder Stromausfall findet keine Rückstellung statt.** Vor dem
nächsten Lauf den Server beenden und das Gerät manuell auf die gespeicherten
Norm-/Dezimalpunktbytes zurückstellen. Den ursprünglichen Rückstellpunkt aus
`scripts/gsv-registers.py` verwenden und nicht mit dem veränderten Zustand
überschreiben. Im Projektverzeichnis mit verbundenem Gerät:

```bash
PYTHONPATH=src ./.venv/bin/python - <<'PY_RESTORE'
import json
from pathlib import Path
import serial
from dispread.gsv2as_serial import DEFAULT_RESTORE_POINT, _apply_norm_dpoint, _check_restore_point

point = json.loads(DEFAULT_RESTORE_POINT.read_text(encoding="utf-8"))
# Anschluss aus dem gespeicherten Rueckstellpunkt, nicht aus einem Default.
serial_port = point["port"]
serial_baudrate = int(point["baudrate"])
reg = point["register"]
# Protokoll in eine neue Datei schreiben; vorhandene Aufzeichnungen behalten.
with Path("var/diagnostics/manuelle-rueckstellung.jsonl").open("x") as log:
    with serial.Serial(serial_port, serial_baudrate, timeout=0.2) as port:
        ok = _apply_norm_dpoint(port, reg["norm"]["daten"], reg["dpoint"]["daten"][0],
                                log, {}, label="manual_restore")
        matches, detail = _check_restore_point(port, point, log, {}, label="manual_verify")
        if not ok or not matches:
            raise SystemExit(f"Rueckstellung nicht bestaetigt: {detail}")
print("Normierung und Dezimalpunkt zurueckgestellt und geprueft.")
PY_RESTORE
```

Den Protokolldateinamen bei wiederholter Rückstellung neu wählen. Anschließend
mit `PYTHONPATH=src ./.venv/bin/python scripts/gsv-registers.py
--port PORT_AUS_RUECKSTELLPUNKT --baudrate BAUDRATE_AUS_RUECKSTELLPUNKT
--out var/diagnostics/gsv-register-nach-rueckstellung.json` einen separaten
Iststand sichern und mit dem ursprünglichen Rückstellpunkt vergleichen.
Die Platzhalter durch `port` und `baudrate` aus dem Rückstellpunkt ersetzen.
Dieses Skript liest Register; es stellt sie selbst nicht zurück. Es sendet
STOP/CLEAR/START und unterbricht dabei den Messwertstrom; nur außerhalb
einer laufenden Referenzaufzeichnung verwenden.

Pro Lauf entstehen `reference.jsonl` mit BOOTTIME-Zeit, Rohtelegramm,
Zellentext und Zahlenwert (abgelehnte Zeilen mit `cell_text: null`,
`value: null` und `error`) sowie bei einem Plan `commands.jsonl` mit jedem
Befehlsbyte und seiner BOOTTIME-Zeit. `session.json` enthält den Plan,
Zeilenzahl, Parsefehler, Lücken über einer Sekunde, verworfene Queue-Einträge
und die Rückstellprüfung. Ein Leserthread und ein Dateischreiber mit
begrenzter Warteschlange verhindern, dass eine langsame Platte den Portleser
aufhält; bei Überlauf wird der älteste Eintrag verworfen und gezählt.

Nach dem Stoppen im Projektverzeichnis:

```bash
PYTHONPATH=src ./.venv/bin/python scripts/live-reference-eval.py PFAD/ZUM/run-01
PYTHONPATH=src ./.venv/bin/python scripts/live-reference-eval.py PFAD/ZUM/run-01 --json
```

Der Abgleich rechnet Aufnahmezeiten mit `to_boottime_ns` und dem gemessenen
BOOTTIME–MONOTONIC-Versatz aus `session.json` um. Fehlender Versatz,
Suspend oder eine künstliche Zeitbasis werden abgelehnt (Exit 2). Auch
Queue-Verluste oder eine unvollständige Referenzdatei verhindern einen
Referenznachweis. Ein Parsefehler sperrt das Fenster vom vorherigen Telegramm
bis zum nächsten gültigen Telegramm plus 695 ms, nicht den gesamten Lauf.
Die 695 ms aus `gate-label.py` schützen nach jedem Telegrammwechsel;
VALID darin zählt als **unentschieden**. Der Anzeigeversatz wird nicht ein
zweites Mal abgezogen. Vor dem ersten und nach dem letzten Telegramm sowie
an Lücken über einer Sekunde wird kein Referenzwert extrapoliert. VALID im
Schutzintervall (`undecided_valid`) und VALID ohne Referenzdeckung
(`uncovered_valid`) werden getrennt gezählt.
Ein Wechsel, dessen erstes neues Telegramm eine solche Lücke beendet, zählt
als `changes_after_gap`: „Wechsel nach Telegrammluecke (Werteplan):
Verzoegerung nicht messbar“. Er geht weder in die Wechselanteile noch in die
Verzögerung ein. Die nach einer Pause gebündelt gelesenen Telegramme sind zu
spät gestempelt, um den Wechselzeitpunkt festzulegen. Nur Wechsel innerhalb
kontinuierlicher Telegrammdeckung liefern Wechselanteile und Verzögerungen.

Die Ausgabe zeigt Fehllesungen (Exit 1, Ziel 0), VALID-Anteile je
Anzeigezustand und getrennt nach stabil/Wechsel, Median und p90 bis zum
ersten VALID des neuen Wertes sowie TRANSITION-/UNREADABLE-Anteile während
Wechseln. `tolerance_frames` kommt aus der Sitzungszusammenfassung;
Fehllesungen in Läufen mit angepasster Toleranz werden separat ausgewiesen.
Das bisherige Recordformat markiert einzelne Bilder oberhalb der alten
Schwelle nicht: Diese Fehlerzahl gilt für den **gesamten Toleranzlauf**.
Unentschiedene Bilder sind kein Nachweis korrekter Werte. Ein Testlauf mit
übergangener Lesesperre wird als Referenznachweis abgelehnt.

Der Freigabehinweis bleibt sichtbar:

> Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V — andere Lichtquellen und Geräte nicht geprüft.

Es gibt noch keine serielle Ausgabe an GSVmulti ([OQ-07](../open-questions.md#oq-07)).
Die Bedienerläufe vom 2026-10-21 liefern erste Trackingbefunde bei
Wertwechseln ([Validierung](../VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21)).
Im inzwischen beendeten strengen Werteplan-Versuch wurde nach dem Wechsel auf
Faktor 2 dauerhaft `tracking_lost:low_score` beobachtet; bei Faktor 0,5
kehrte VALID ohne Eingriff zurück. Der Einfluss des Zifferninhalts ist
plausibel, aber noch nicht abschließend abgesichert (R13,
[OQ-26](../open-questions.md#oq-26)). Die
[Abschlussauswertung](../VALIDATION.md#messpfad-live-werteplan-2026-10-21)
und bestätigte Rückstellung sind dokumentiert; die Nachführung muss vor
weiteren Freigabeläufen überarbeitet und erneut geprüft werden.
Ein Toleranzlauf ≥ 10 min mit Werteplan bleibt separat offen
([TODO](../../TODO.md)).

### Dateien und lokale Bedienung

| Ablage | Inhalt |
| --- | --- |
| `var/live/<sitzung>/setup/` | Einrichtungsbilder, Bericht und Overlays; `cell-text.json` mit ursprünglichem/maskiertem Text und Quelle, `failure.json` mit Abbruchschritt, Grund und UTC-Zeit bei Fehlern. |
| `var/live/<sitzung>/profile.json` und `confirmation.json` | Bestätigtes Profil und namentliche Bedienbestätigung. |
| `var/live/<sitzung>/run-NN/records.jsonl` | ValueRecords des einzelnen Laufs; `raw_text` enthält die geparste Zahl, nicht 16 Zellen. |
| `var/live/<sitzung>/run-NN/session.json` | Laufmetadaten, Zeitbasis/Versatz BOOTTIME−MONOTONIC, aufgezeichnete Timing-Kalibrierung, Freigabehinweis, Bedienbestätigung, Zusammenfassung und Endgrund. |

Die Timing-Kalibrierung wird aufgezeichnet, nicht auf den Live-Wert angewandt.
Zeitstempel tragen ihre Zeitbasis; unbekannte Unsicherheit ist `None`.
Die `JsonlSink` rotiert standardmäßig bei 64 MiB und behält fünf
Generationen zusätzlich zur aktuellen Datei. Wie lange das reicht, hängt
von Bildrate und Recordgröße ab; dauerhafte Aufbewahrung ist ein Folgeschritt.

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

Die folgenden Karten zeigen die StreamCam-Regler, die Profil und Code beim
Öffnen der Kamera setzen ([Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag"),
`src/dispread/camera_settings.py`). Welche Regler die laufende
Werkbank-Oberfläche tatsächlich anbietet, steht in ihrer Einstelltabelle.

Die StreamCam hat dagegen
`focus_automatic_continuous` und `focus_absolute`; für reproduzierbare
Aufnahmen setzt [CameraSettings](../../api/frames.md) die Automatik aus und
liest den festen Fokuswert zurück.

### Fokus-Automatik

<div class="wiki-setting" markdown="1">

| Einstellung | Fokus-Automatik |
| --- | --- |
| Wozu | Hält den Fokus für reproduzierbare Aufnahmen fest. |
| Im Hintergrund | `focus_automatic_continuous` wird vor dem festen Fokuswert ausgeschaltet. |
| Standard | aus (`0`) |
| Ändern? | **Nein** — für reproduzierbare Aufnahmen bleibt sie aus. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Fester Fokus

<div class="wiki-setting" markdown="1">

| Einstellung | Fester Fokus |
| --- | --- |
| Wozu | Stellt die Anzeige am konkreten Arbeitsabstand scharf. |
| Im Hintergrund | `focus_absolute` kommt aus dem bestätigten Profil und wird zurückgelesen. Automatik zuerst aus, dann Absolutwert: In einem gemeinsamen Aufruf schlägt `focus_absolute` bei noch aktivem Autofokus mit EIO fehl. |
| Standard | — |
| Ändern? | **Nur wenn** — Arbeitsabstand oder Aufbau sich ändern; den Fokus anschließend neu bestätigen. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag"); [Reihenfolgeregel](../../CLAUDE.md#hardware-fakten-die-man-leicht-falsch-annimmt) |

</div>

### Belichtungsautomatik

<div class="wiki-setting" markdown="1">

| Einstellung | Belichtungsautomatik |
| --- | --- |
| Wozu | Übernimmt nach dem Einrichten eine feste Belichtung für die Aufnahme. |
| Im Hintergrund | `auto_exposure` wird auf `1` gesetzt; die Belichtungszeit kommt aus dem Profil. |
| Standard | aus (`1`) |
| Ändern? | **Nein** — im bestätigten Aufnahmeprofil bleibt die Automatik ausgeschaltet. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Belichtungszeit

<div class="wiki-setting" markdown="1">

| Einstellung | Belichtungszeit |
| --- | --- |
| Wozu | Passt die Belichtung an Anzeige und Licht des Aufbaus an. |
| Im Hintergrund | `exposure_time_absolute` ist ein Pflichtwert des Profils; es gibt keinen stillschweigenden Ersatzwert. |
| Standard | — |
| Ändern? | **Nur wenn** — Anzeige oder Beleuchtung eine neue Einrichtung erfordern; Wert im Profil bestätigen. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Verstärkung

<div class="wiki-setting" markdown="1">

| Einstellung | Verstärkung |
| --- | --- |
| Wozu | Passt die Verstärkung an die Beleuchtung des Aufbaus an. |
| Im Hintergrund | `gain` ist ein Pflichtwert des Profils; es gibt keinen stillschweigenden Ersatzwert. |
| Standard | — |
| Ändern? | **Nur wenn** — die Beleuchtung eine neue Einrichtung erfordert; Wert im Profil bestätigen. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Weißabgleichsautomatik

<div class="wiki-setting" markdown="1">

| Einstellung | Weißabgleichsautomatik |
| --- | --- |
| Wozu | Hält den Weißabgleich während reproduzierbarer Aufnahmen fest. |
| Im Hintergrund | `white_balance_automatic` wird vor den Profilwerten auf `0` gesetzt. |
| Standard | aus (`0`) |
| Ändern? | **Nein** — im bestätigten Aufnahmeprofil bleibt die Automatik ausgeschaltet. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Weißabgleich

<div class="wiki-setting" markdown="1">

| Einstellung | Weißabgleich |
| --- | --- |
| Wozu | Passt den festen Weißabgleich an die Beleuchtung an. |
| Im Hintergrund | `white_balance_temperature` ist ein Pflichtwert des Profils; es gibt keinen stillschweigenden Ersatzwert. |
| Standard | — |
| Ändern? | **Nur wenn** — die Beleuchtung eine neue Einrichtung erfordert; Wert im Profil bestätigen. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Netzfrequenz

<div class="wiki-setting" markdown="1">

| Einstellung | Netzfrequenz |
| --- | --- |
| Wozu | Hält die Netzfrequenzeinstellung für den Aufbau fest. |
| Im Hintergrund | `power_line_frequency` wird vor den Profilwerten fest gesetzt. |
| Standard | `1` |
| Ändern? | **Nein** — die Einstellung ist im Code festgelegt und kommt nicht aus dem Profil. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Zoom

<div class="wiki-setting" markdown="1">

| Einstellung | Zoom |
| --- | --- |
| Wozu | Hält den Bildausschnitt zwischen den Sitzungen reproduzierbar. |
| Im Hintergrund | `zoom_absolute` ist fest gesetzt, damit keine Zoom-Drift zwischen Sitzungen entsteht. |
| Standard | `100` |
| Ändern? | **Nein** — der Wert ist im Code festgelegt und kommt nicht aus dem Profil. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Schwenken

<div class="wiki-setting" markdown="1">

| Einstellung | Schwenken |
| --- | --- |
| Wozu | Hält die horizontale Ausrichtung zwischen den Sitzungen reproduzierbar. |
| Im Hintergrund | `pan_absolute` ist fest gesetzt, damit keine Schwenk-Drift zwischen Sitzungen entsteht. |
| Standard | `0` |
| Ändern? | **Nein** — der Wert ist im Code festgelegt und kommt nicht aus dem Profil. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Neigen

<div class="wiki-setting" markdown="1">

| Einstellung | Neigen |
| --- | --- |
| Wozu | Hält die vertikale Ausrichtung zwischen den Sitzungen reproduzierbar. |
| Im Hintergrund | `tilt_absolute` ist fest gesetzt, damit keine Neige-Drift zwischen Sitzungen entsteht. |
| Standard | `0` |
| Ändern? | **Nein** — der Wert ist im Code festgelegt und kommt nicht aus dem Profil. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag") |

</div>

### Auflösung/Bildrate

<div class="wiki-setting" markdown="1">

| Einstellung | Auflösung/Bildrate |
| --- | --- |
| Wozu | Legt Bildgröße und angeforderte Bildrate für die StreamCam fest. |
| Im Hintergrund | `size`, `fourcc` und `fps` kommen aus dem bestätigten Profil. Die Vorschau vor dem Fokus-Sweep verwendet 1920×1080 YUYV bei 30 Bildern/s ohne Reglerwerte. |
| Standard | Vorschau: 1920×1080 YUYV, 30 Bilder/s; Aufnahme: bestätigtes Profil |
| Ändern? | **Nur wenn** — ein neu bestätigtes Profil es erfordert; volle Auflösung braucht USB3. |
| Quelle | [Kameraeinstellungen](../../api/frames.md#aktuelle-uvc-kameraeinstellungen "UVC-Regler und Profilvertrag"); [Hardwareprofil](../HARDWARE_PROFILE.md#aktuelle-streamcam-sitzung-2026-10-21) |

</div>

Reflexionen zuerst durch Position, Abschirmung und kontrolliertes Licht
verringern: [Optischer Aufbau](../OPTICAL_SETUP.md).

<details class="wiki-layer wiki-layer--historisch" markdown="1">
<summary>Historisch: AI Camera (IMX500)</summary>

Es werden nur unterstützte Controls angeboten. Belichtungsautomatik `an`
regelt selbst. Auf `aus` umstellen übernimmt die aktuellen Ist-Werte als
Startpunkt und entsperrt `ExposureTime` (µs) und `AnalogueGain`. `Contrast` beeinflusst die
Bildaufbereitung. Auflösung oder Bildrate starten den Stream neu.

**Historischer IMX500-Stand:** Die AI Camera hat mechanischen Fokus.
Fokusassistenz `an` vergrößert die
bestätigte ROI im Vorschaufenster; die Tabelle zeigt daneben einen relativen
Schärfewert. Am kleinen Objektiv mit dem Fokuswerkzeug einstellen; keine
motorische Autofokusfunktion vortäuschen.

</details>

<figure class="tour-figure" data-scene="bedienung-kamera" markdown="1">
<figcaption markdown="span">Die StreamCam am GSV-Aufbau: USB3-Anschluss, YUYV in voller Auflösung, Autofokus aus und ein fester Fokuswert.</figcaption>
</figure>

<details class="wiki-layer wiki-layer--historisch" markdown="1">
<summary>Historisch: AI Camera (IMX500)</summary>

Tabelle und CLI melden Sollwerte und die beobachtete Belichtung getrennt. Die interne
Revision `applied_revision` bedeutet gesetzte Controls mit eingeschwungener
manueller Belichtung (Toleranzen: 3 % ExposureTime, 8 % Gain); Kontrast wird von
Picamera2 nicht als gemessener Istwert zurückgemeldet. Bei nicht bestätigbarer
Übernahme wird ein Fehler angezeigt.

</details>

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
Bereiche. Die ROI ist an den bestätigten Aufbau gebunden; der
`QuadTracker` führt sie begrenzt gegen das Bestätigungsbild nach. Auf
`/live` passiert das bei jedem gelesenen Bild. Bei überschrittenen Grenzen
oder verlorenem Tracking muss die Einrichtung geprüft und gegebenenfalls
neu bestätigt werden ([OQ-26](../open-questions.md#oq-26)). Kein Modell wird
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

Die alte Werkbankvorschau verwendet `SevenSegmentReader`; er unterstützt
`bright_on_dark` und `dark_on_bright`. Der Fall „alle Stellen zeigen 8“
bleibt [OQ-13](../open-questions.md#oq-13), die optische Punktprüfung dieses
Segmentlesers und das Lesen der Einheit [OQ-17](../open-questions.md#oq-17).
Auf `/live` liest dagegen `DotMatrixReader` den Punkt als Zeichen und
übernimmt die bestätigte Einheit mV/V aus dem Profil.
Statusanzeigen wie `DC` werden in diesem Schritt ebenfalls nicht gelesen.
Vorschauänderungen werden nicht automatisch gespeichert. Gültige externe
Dateiänderungen werden nach kurzem Entprellen übernommen. Bei ungültigem JSON
bleibt die letzte Konfiguration aktiv; bei gleichzeitig ungespeicherten lokalen
Änderungen erscheint ein Konflikt. `resolve local` behält die Vorschau, ein
anschließendes `save` überschreibt die Datei bewusst.

Der folgende Block dokumentiert den älteren Controller. Im laufenden
Server mit `CameraOwner` werden `camera.set`, Fokus und Auto-Setup dort
abgewiesen und auf `/live` verwiesen. `mode run` ist weiterhin lediglich
der alte Vorschauzustand, kein Live-Laufstart.

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
Reale StreamCam-Bilder tragen `V4L2_MONOTONIC`, unbekannte Semantik und
Unsicherheit `None`; `SENSOR_BOOTTIME` gehört zum historischen IMX500-Pfad.

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

**Historischer Prüfstand vom 2026-09-08:** 63 automatische Tests einschließlich
TLS-Login mit Testauthentifizierung,
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
[OQ-21](../open-questions.md). Diese historische lokale Headless-Störung ist
kein pauschaler Befund für heutige Playwright-Läufe; der Live-Pfad besitzt
inzwischen `tests/live-ui.spec.ts` mit simuliertem Dienst.
Windows-Zertifikatsvertrauen, Anmeldung mit deinem
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

* [ ] Ein fehlgeschlagenes Gegenlesen sperrt den normalen Lauf; ein
  ausdrücklich gestarteter Testlauf trägt Banner und `TESTLAUF.json`.
  Der Schutz gegen `VALID` im Test-Audit bleibt [OQ-44](../open-questions.md#oq-44).
* [ ] `/live` führt ohne Anmeldung zum Login und danach zurück; bei Portkonflikt
  startet die Werkbank mit `--port 8081`.
* [ ] Einrichtung zeigt Schritte, Sekunden, Overlays und Prüfungen;
  FEHLER sperrt, WARNUNG verlangt Kenntnisnahme, Bestätigung einen Namen.
* [ ] Ein bestätigter Lauf zeigt VALID/TRANSITION/UNREADABLE/STALE;
  Altwerte und Verbindungsverlust erscheinen nie als aktuelle gültige Ziffern.
* [ ] Optionale Referenzaufzeichnung schreibt `reference.jsonl`; Status und
  `session.json` zeigen Parsefehler, Verluste und gegebenenfalls den abgebrochenen
  Werteplan. Plan-Stop und reguläres Serverende bestätigen die Rückstellung.
* [ ] `scripts/live-reference-eval.py` wertet den Lauf aus: Fehllesungen,
  unentschiedene/ungedeckte VALID und Wechsel nach Telegrammlücken prüfen;
  Latenz und Wechselanteile nur bei kontinuierlicher Referenzdeckung bewerten.
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
