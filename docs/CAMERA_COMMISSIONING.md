---
weg: bedienen
---

# Kamera-Inbetriebnahme

Prüfe die StreamCam, bevor du mit ihr misst. Die Inbetriebnahme gehört in ein
Wartungsfenster mit freier Kamera: `dispread serve`, Harvest und andere
Aufnahmen dürfen währenddessen nicht laufen.

## Aktuell: Logitech StreamCam (UVC)

1. Vorher den aktuellen Aufbau und die Kamerabelegung anhand von
   [Status](status.md) und [Hardwareprofil](HARDWARE_PROFILE.md) prüfen.
2. Bei freier Kamera aus der Projektwurzel ausführen:
   ```bash
   ./scripts/camera-commissioning.sh
   ```
3. Exit 0 bedeutet: keine FEHLER in den geprüften Schritten. WARNUNGEN
   können verbleiben, insbesondere bei USB2; sie sind gesondert zu bewerten.
   Das Testbild liegt unter
   `var/diagnostics/camera-commissioning/test.png` (1920×1080).
4. Fokus, Bildausschnitt und Licht am konkreten Gerät einrichten und
   bestätigen. Für den Live-Pfad dient die Seite unter `/live` im vorhandenen
   Server auf Port 8081.
5. Aufbau und Diagnose nach [lab_journal.md](lab_journal.md) übernehmen;
   bei Konfigurationsänderungen [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)
   aktualisieren. Ein Diagnose-Exit 0 ist keine Leser- oder Systemabnahme.

Wenn etwas nicht klappt:

* Gerät fehlt: USB-ID und Videoindex prüfen.
* Reduzierte Auflösung: USB3-Verbindung prüfen.
* „Belegt“: den vorhandenen Kamerabesitzer klären.

<details class="wiki-layer wiki-layer--hintergrund" markdown="1">
<summary>Was passiert im Hintergrund</summary>

Seit 2026-09-25 ist die StreamCam die aktive Kamera. Die Diagnose prüft
`v4l2-ctl`, USB-ID `046d:0893` mit `index == 0`, USB-Geschwindigkeit,
YUYV 1920×1080, Fokusregler und ein Testbild.

Sie setzt `focus_automatic_continuous` und `focus_absolute` testweise und
versucht die vorher gelesenen Werte wiederherzustellen. Sie schreibt ein
Testbild und öffnet die Kamera direkt. Der Server hält die Kamera während
der gesamten Serverlaufzeit, auch ohne aktiven Messlauf; deshalb darf die
Diagnose nicht parallel zu `dispread serve`, Harvest oder einer anderen
Aufnahme laufen.

Port 8080 ist auf diesem Pi durch MEhub belegt, verwendet wird 8081.
Zeitstempel stammen aus V4L2/CLOCK_MONOTONIC. Die Umrechnung und die noch
offene physikalische Semantik stehen in [TIMING.md](TIMING.md).

</details>

<details class="wiki-layer wiki-layer--entwickler" markdown="1">
<summary>Für Entwickler</summary>

Das Skript für die Diagnose:
[`scripts/camera-commissioning.sh`](../scripts/camera-commissioning.sh).
`CameraOwner` hält die StreamCam während der gesamten Serverlaufzeit.
`find_uvc_device()` sucht über USB-ID und `index == 0`; die Knotennummer
wechselt mit der Steckreihenfolge und wird nicht fest eingetragen
([gemeinsamer Kamera-Besitzer](../api/frames.md#gemeinsamer-kamera-besitzer-im-live-betrieb "Kamerabesitz im Live-Betrieb")
und [Projektanweisungen](../CLAUDE.md#erwartete-zustande-die-keine-bugs-sind)).

</details>

<details class="wiki-layer wiki-layer--historisch" markdown="1">
<summary>Historisch: IMX500-Aufbau (außer Betrieb)</summary>

## Historischer IMX500-Aufbau (außer Betrieb)

Die folgenden Beobachtungen und FPC-/Boot-Schritte betreffen ausschließlich
die IMX500. Das heutige `camera-commissioning.sh` prüft diese Kamera nicht.
Die historischen Schritte sind kein Ablauf für die USB-StreamCam.

## Der Fall, der am 2026-09-07 zutraf

Die Kamera war an CAM/DISP0 angeschlossen und wurde trotzdem nicht erkannt.
Ursache: **`camera_auto_detect` prüft die Anschlüsse ausschließlich beim
Booten.** Die Kamera war nach dem letzten Boot angesteckt worden. Ein Reboot
hat es behoben.

Merksatz: **Kamera angesteckt ⇒ Reboot.** Erst danach Fehlersuche.

## Historische Checkliste

1. Vorher-Zustand mit Kameraliste und Kernelmeldungen festhalten. Das
   damalige IMX500-Diagnoseskript ist durch die UVC-Fassung ersetzt.
2. `sudo shutdown -h now`, **Netzteil abziehen**. Die Kamera nie unter Spannung
   an- oder abstecken.
3. Anschluss festlegen: CAM/DISP0 oder CAM/DISP1. Die Wahl gehört nach
   [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md), damit die Diagnose gegen den
   erwarteten Anschluss prüft und nicht gegen „irgendeine Kamera".
4. Kabel: Der Pi 5 hat den **schmalen 22-poligen** FPC-Anschluss, die AI Camera
   einen 15-poligen. Es braucht das mitgelieferte 15↔22-Kabel — ein
   Pi-4-Kabel passt nicht. Riegel an **beiden** Enden öffnen, Kabel gerade bis
   zum Anschlag einschieben, Riegel schließen. Kontaktrichtung gegen das Foto
   der offiziellen Doku prüfen:
   <https://www.raspberrypi.com/documentation/accessories/ai-camera.html>
5. Objektivdeckel abnehmen. Die AI Camera hat **manuellen Fokus** mit
   Fokuswerkzeug — das ist erfahrungsgemäß verstellt und muss auf den
   Arbeitsabstand eingestellt werden.
6. Booten, dann in dieser Reihenfolge:
   ```bash
   rpicam-hello --list-cameras          # muss imx500 listen
   ls /dev/v4l-subdev*                  # muss existieren
   sudo dmesg | grep -iE 'imx500|rp1-cfe'
   ```
7. Testaufnahme:
   ```bash
   rpicam-still -o /tmp/first-light.jpg
   ```
8. Optischen Aufbau herstellen (siehe [OPTICAL_SETUP.md](OPTICAL_SETUP.md)),
   danach Belichtung und Verstärkung fixieren und ins Geräteprofil schreiben.
9. Erste `replay://`-Session aufzeichnen. Ab da ist die Kette gegen reales
   Material regressionsfähig, auch ohne Gerät am Platz.
10. [lab_journal.md](lab_journal.md) und
    [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) nachziehen.

## Was ein Nachweis ist und was nicht

| Signal | Bedeutung |
| --- | --- |
| Sensorknoten im Device-Tree (`imx500@1a`) | **Nachweis**: die Kamera wurde beim Booten erkannt |
| `rpicam-hello --list-cameras` listet den Sensor | **Nachweis** |
| `Picamera2.global_camera_info()` nicht leer | **Nachweis** |
| `cam0_reg`/`cam1_reg` im Device-Tree | nur der **Anschluss** — auf dem Pi 5 immer vorhanden, auch ohne Kamera |
| `dtoverlay -l` | **kein Kriterium.** `camera_auto_detect` wird von der Firmware angewandt und erscheint dort nicht |
| CAM-I2C-Busnummer | nur informativ, die Nummern sind nicht stabil (hier 6 und 10, nicht 4 und 6) |
| `pispbe-*`, `rpi-hevc-dec` unter V4L2 | ISP und Video-Decoder, existieren auch ohne Kamera |

## Historischer Fehlerbaum

```
rpicam-hello --list-cameras leer?
├─ dmesg ohne imx500-Zeile
│  └─ Kabel verdreht, nicht gesteckt oder falscher Typ  -> Schritt 4
├─ dmesg zeigt imx500, aber Probe-Fehler
│  └─ Stromversorgung oder Kabelqualitaet
└─ Kamera gelistet, aber IMX500() scheitert
   └─ Rechte auf /dev/v4l-subdev*, Gruppe video pruefen
```

Hält der Zustand nach dem Reboot an, in dieser Reihenfolge weiter:

1. Explizites Overlay statt Auto-Detect, Backup zuerst:
   ```bash
   sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak
   # Zeile ergänzen:  dtoverlay=imx500,cam0
   sudo reboot
   ```
2. Kabel prüfen (Schritt 4 oben).
3. Gegenprobe am zweiten Port CAM/DISP1, dann `dtoverlay=imx500,cam1`. Das
   trennt einen Port- oder Kabeldefekt von einem Moduldefekt.

## Historische IMX500-Messgrößen

Beides ist ohne Hardware nicht bestimmbar und gehört nach
[TIMING.md](TIMING.md):

* Warmlaufzeit des ersten `.rpk`-Uploads (gemessen: **6,8 s**).
* `CnnKpiInfo` mit `dnn_runtime` und `dsp_runtime`, sowie die tatsächlich
  erreichte Inferenzrate. Achtung: `network_intrinsics` behauptet eine Rate,
  die gemessen nicht erreicht wird (26 behauptet, 15,0 gemessen).

</details>

**Weiter mit:** [Kameraregler einstellen](anleitung/10-kamera-livevorschau.md#kamera-einstellen)
