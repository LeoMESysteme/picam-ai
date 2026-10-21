# Bildquellen (`frames/`)

Austauschbare Bildquellen hinter `open_source()`. Die aktuelle Kamera wird
über `v4l2://` mit bestätigten Einstellungen geöffnet; `synthetic://` und
Dateizeitquellen erlauben keine realen Latenzaussagen. Die derzeit
fehlerhafte Basenkennzeichnung von <code>Timestamp.now_monotonic()</code>
und Ergebniszeiten außerhalb des V4L2-Pfads ist in
[OQ-45](../docs/open-questions.md#oq-45) erfasst; Zeitdifferenzen nur nach
Prüfung von Uhr und Ereignis auswerten. Die historischen
Schemata `picamera2://` und `imx500://` werden gezielt abgelehnt.

::: dispread.frames

## Aktuelle UVC-Kameraeinstellungen

Das Profil der StreamCam verlangt Bildformat, Bildrate, USB-ID und die
bestätigten Fokus-, Belichtungs-, Weißabgleich- und Verstärkungsregler.
Die frühere Picamera2-Quelle ist außer Betrieb
([Hardwareprofil](../docs/HARDWARE_PROFILE.md)).

::: dispread.camera_settings

## Gemeinsamer Kamera-Besitzer im Live-Betrieb

`CameraOwner` hält die Kamera während `dispread serve` und versorgt
Live-Lesen und gedrosselte Werkbank-Vorschau aus derselben Quelle. Andere
Kameraprozesse erhalten „belegt“. Eine Live-Sitzung verarbeitet jeweils das
neueste Bild und zählt übersprungene Bilder getrennt.

::: dispread.live.camera
