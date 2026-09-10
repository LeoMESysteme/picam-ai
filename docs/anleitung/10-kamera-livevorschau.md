# Kamera-Workbench: HTTPS, Einstelltabelle und Shell

Eine Terminaloberfläche mit Kamerabild, Log und echten Bash-Tabs. Alle Zugriffe
sind mit dem Linux-Passwort von `me-systeme` geschützt. Vorschau und geometrische
Display-Vorschläge starten mit dem Server. Es findet keine OCR oder
Messwertfreigabe statt; `run` bezeichnet hier den Betrieb mit festen Einstellungen.

## Start

Im Projektverzeichnis:

```bash
bash scripts/install-workbench.sh
./.venv/bin/dispread init-tls
./.venv/bin/dispread serve
```

`init-tls` nur einmal ausführen. Bereits vorhandene Schlüssel werden nicht
überschrieben. In dieser Implementierungssession wurde das Zertifikat bereits
unter `var/workbench/tls/` erzeugt; du kannst direkt `dispread serve` starten.

Default ist die zuvor vom Nutzer eingestellte interne Adresse:

```text
https://100.122.154.35:8080
```

**Es ist jetzt HTTPS, nicht mehr HTTP.** Alten Vorschauprozess vorher mit
`Ctrl+C` beenden. Der kompatible Einstieg bleibt:

```bash
./.venv/bin/python examples/17_camera_display_preview.py
```

Die gesamte Oberfläche verlangt das normale Linux-/SSH-Passwort von
`me-systeme`, nicht das separate root-Passwort. Passwörter werden weder
protokolliert noch gespeichert. Nach acht Stunden ist eine erneute Anmeldung
nötig. Fünf Anmeldeversuche pro Minute und Client sind möglich.

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

Die AI Camera hat **mechanischen Fokus**. Fokusassistenz `an` vergrößert die
bestätigte ROI im Vorschaufenster; die Tabelle zeigt daneben einen relativen
Schärfewert. Am kleinen Objektiv mit dem Fokuswerkzeug einstellen; keine
motorische Autofokusfunktion vortäuschen. Reflexionen zuerst durch Position,
Abschirmung und kontrolliertes Licht verringern: [Optischer Aufbau](../OPTICAL_SETUP.md).

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
4. ✓ an der OCR-Box bestätigt beide Rahmen endgültig (entspricht dem früheren
   `Strg+Enter`). Ein Klick in den (jetzt inaktiven) grünen ROI-Rahmen
   während Stufe B führt zurück zu Stufe A, ohne die Kandidatensuche erneut
   zu starten. `Esc` verwirft die gesamte Bearbeitung, jederzeit.

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
