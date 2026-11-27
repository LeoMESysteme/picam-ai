# Sensorpakete

Ein Sensorpaket beschreibt ein Gerät und seine Anzeige mit JSON-Daten und
eingefrorenen Zeichenvorlagen. Das erste Paket `gsv2as-161a@1` beschreibt den
GSV-2AS mit Displaytech 161A. Der Assistent kann vorläufige Pakete für
ähnliche Anzeigen erzeugen. KI kommt nur bei der Einrichtung zum Einsatz.

## Paketformat (Schema 1)

| Datei | Inhalt |
| --- | --- |
| `sensor.json` | `schema: 1`, `id` (gleich dem Verzeichnisnamen), positive `version`, `status`, Anzeigename `display_name`, `manufacturer`, `aliases` für die Suche, `device_id` für das Sitzungsprofil, `unit`, `release_notice` zum geprüften Einsatz sowie `templates.file` und `templates.sha256`. |
| `display.json` | `schema: 1`, `family`, `polarity`, `cells` und `rows`. `lattice` beschreibt Start (`left`), Zellabstand (`pitch`), obere und untere Rastergrenze (`top`, `bottom`) und Zielgröße (`target_size`) in Pixeln des entzerrten Bilds. Die Zielbreite entspricht `cells × pitch`. |
| `templates.json` | Eingefrorene Zeichenvorlagen im bestehenden Vorlagenformat v3. Der Leser prüft die Dateibytes gegen SHA-256. `templates.file` ist ein einfacher Dateiname im Paketverzeichnis. |
| `README.md` | Platz für Herkunft, Aufbau und Prüfbelege. Beim mitgelieferten Paket enthalten, bei lokal erzeugten Paketen optional. |

`display.json` ordnet unter `roles` den bei 0 beginnenden Zellenindizes
die Rollen `sign`, `number`, `separator`, `unit` und `blank` zu. `anchor`
benennt mit `char` und `cell` das Zeichen für den Rasterstart. `format`
enthält die Regel (`rule`), die Ziffernzahl (`digits`), erlaubte Vorzeichen
(`sign_chars`) und die Regel für führende Nullen (`leading_zero_rule`).
Unbekannte Schlüssel und Schemaversionen werden abgelehnt.

P0 unterstützt einzeiliges Punktraster 16×1 (`hd44780_5x8`), dunkle Zeichen
auf hellem Grund (`dark_on_light`) und für die Live-Rastersuche ein festes
`+` in Zelle 0. Der GSV-2AS behält `gsv2as_v1` und
`gsv2as_leading_zero_v2`. Der Assistent leitet für lokale Pakete
`char_number_v1` aus dem Zellbeispiel ab. Dafür gilt `leading_spaces`.
`decimal` erlaubt `point` oder `none`. Das optionale `min_digits` legt die
Untergrenze fest, `digits` die Obergrenze. Fehlt `min_digits`, gilt `digits`
auch als Untergrenze. [Rastergrenze (OQ-81)](open-questions.md#oq-81)

| Status | Bedeutung |
| --- | --- |
| `verified` | Verifiziert für den dokumentierten Einsatz. P0 liefert `gsv2as-161a` für den geprüften Raumlicht-Aufbau mit `mV/V`. Die Registry weist lokale Pakete mit diesem Status ab. |
| `provisional` | Vorläufig. Der Assistent vergibt diesen Status, und die Aktivierung verlangt eine Bestätigung. Neue Pakete bleiben bis zur Klärung der Hochstufung vorläufig. [OQ-82](open-questions.md#oq-82) |
| `draft` | Entwurf. Die Aktivierung über den Assistenten oder `picam sensor activate` wird abgelehnt. |

## Ablage und Auswahl

Die mitgelieferten Pakete liegen unter `src/dispread/data/sensors/<id>/`
und sind in Wheel und Releasearchiv enthalten. Lokale Pakete speichert
der Assistent schon in P0 unter dem Datenstamm der Instanz, bei regulärer
Systeminstallation unter `/var/lib/picam/sensors/<id>/`, im
Entwicklungscheckout normalerweise unter `var/sensors/<id>/`. Später ist
der lokale Paketordner auch für aus dem Katalog bezogene Pakete vorgesehen.

`live.sensor` wählt die Paketkennung. Ohne Einstellung gilt `gsv2as-161a`.
Die Werkbank übernimmt die Wahl beim Neustart. `session.json` hält den
Sensorbezug als `<id>@<version>` fest. Für den Standardsensor bleiben
vorhandene `live.templates`-Pfade mit passender SHA-256 nutzbar. Fehlt die
Datei an einem erkannten alten Stufe-2c-Pfad, verwendet die Werkbank die
Paketvorlage und meldet den Wechsel. Andere Sensoren laden die eigene
Paketvorlage.

## Neuen Sensor hinzufügen (Konsole) { #neuen-sensor-hinzufuegen }

1. In der Verwaltungskonsole mit **o** den Tab **Sensoren** öffnen und
   **Neuen Sensor hinzufügen** wählen.
2. Name, Hersteller, Anzeigeart, Einheit und Anschluss angeben. Das
   Zellbeispiel genau wie auf dem Display eingeben, mit Leerzeichen für
   leere Zellen, etwa `+ 0.4678 mV/V`. **Claude**, **Codex** oder **Ohne KI**
   wählen.
3. Checkliste verfolgen und Rückfragen beantworten. Anzeigeformat und
   Einheit vor der Paketerzeugung bestätigen. Ohne Standbild mit passendem
   bestätigtem Raster prüft die Probelesung Paket und Vorlagen statisch.
4. Auf Rückfrage oder im Tab **Sensoren** das Paket **als aktiv setzen**,
   den vorläufigen Status bestätigen und `picam restart` ausführen.
5. In der Werkbank unter `/live` die Anzeige einrichten, bestätigen und
   einen Lauf starten. Für Zellformate, die der Browserdialog nicht
   annimmt, kann `dispread live setup --cell-text` die Zellenfolge
   übergeben. [Anzeige einrichten](anleitung/10-kamera-livevorschau.md#anzeige-einrichten)

Der Assistent braucht einen festen Plus-Anker in Zelle 0 und verwendet die
GSV-2AS-Vorlagen. Die benötigten OCR-Zeichen müssen darin vorkommen. Die
Einheit bestätigt der Bediener anhand der Anzeige. Live-Status und
Laufaudit kennzeichnen Werte des vorläufigen Pakets mit
`sensor_status: provisional`. Die Ausgabe an GSVmulti unterstützt nur
`mV/V`. Wie der Paketstatus dort kenntlich wird, bleibt offen.
[OQ-83](open-questions.md#oq-83)

Am 27.11.2026 wurden auf raspi06 ohne Kamera je ein Paket ohne KI und mit
Claude-Agent erzeugt, statisch geprüft und aktiviert. Der erste Lauf am
Kameraaufbau steht aus. [Laborjournal](lab_journal.md#sensor-p0-onboarding-2026-11-27)

## Golden-Vergleich

`scripts/sensor-golden.py --out <datei>` schreibt die vollständigen
Leserantworten und ausgewählte Raster- und Einrichtungsbefunde auf
denselben Entwicklungsdaten. Mit `PYTHONPATH` zur jeweiligen Quelle und
demselben `DISPREAD_DEV_DATA` einmal vor und einmal nach der Änderung
ausführen, anschließend beide JSON-Dateien mit `cmp` vergleichen. Für
P0 waren alle **2.781 GSV-2AS-Proben** vor der Umstellung, nach ihr und
nach dem Onboarding byte-identisch. Die Stufe-2c-Vorlagen behalten ihre
SHA-256 `6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a`.

## Ausblick P1–P6 des Sensorplans { #ausblick }

- **P1:** `charset.json` für Zeichensätze und `protocol.json` für dokumentierte Schnittstellen ergänzen.
- **P2:** Werkzeug-CLI `picam sensor` um Ernte, Training und Abnahme erweitern.
- **P3:** Den TUI-Assistenten ausbauen und einen Marktplatz-Tab für Suche und Installation ergänzen.
- **P4:** Die Assistenten-Anbindung für Claude und Codex ausbauen.
- **P5:** Pakete per Forgejo-Issue mit Token im Firmennetz oder über Tailscale einreichen.
  Den öffentlichen Katalog und die Pakete ohne Token über den GitHub-Mirror abrufen.
- **P6:** GSV-2TSD-DI als ersten neuen Sensor einrichten und am Aufbau abnehmen.
