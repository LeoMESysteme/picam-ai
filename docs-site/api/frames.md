# Bildquellen (`frames/`)

Austauschbare Bildquellen hinter `open_source()`. Die aktuelle Kamera wird
über `v4l2://` mit bestätigten Einstellungen geöffnet; `synthetic://` und
Dateizeitquellen erlauben keine realen Latenzaussagen.
<code>capture_timestamp</code> behält seine Quellbasis;
<code>result_timestamp</code> und <code>Timestamp.now_monotonic()</code>
verwenden für jede Quelle <code>time.monotonic_ns()</code> mit
<code>HOST_MONOTONIC</code>
([OQ-45, geklärt 2026-10-23](../docs/open-questions.md#oq-45)). Nach BOOTTIME
führt nur <code>to_boottime_ns</code> mit Sessionversatz und Suspend-Prüfung.
Alte Auditdateien behalten ihre bisherigen Labels. Zeitdifferenzen nur nach
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
