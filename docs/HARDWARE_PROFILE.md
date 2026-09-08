# Hardware-Profil

Stand 2026-09-07, Gerät `raspi06`.

## Rechner

| Größe | Wert |
| --- | --- |
| Modell | Raspberry Pi 5 Model B Rev 1.1 |
| RAM | 8 GB |
| Speicher | 49 GB, davon **34 GB frei** |
| OS | Debian GNU/Linux 13 (trixie) |
| Kernel | 6.12.34+rpt-rpi-2712 |
| Python | 3.13.5 |
| Bootloader | aktuell (Stand 2026-05-26) |

**Konsequenz aus 34 GB frei:** Datensätze und Diagnosebilder gehören auf
externen Speicher. Im Betrieb Ringpuffer mit harter Obergrenze — der
`JsonlSink` rotiert bei 64 MB und behält 5 Generationen.

## Kamera

| Größe | Wert |
| --- | --- |
| Modul | Raspberry Pi AI Camera (Sony IMX500) |
| Anschluss | **CAM/DISP0** |
| Device-Tree-Knoten | `/axi/pcie@1000120000/rp1/i2c@88000/imx500@1a` |
| CAM-I2C-Busse | 6 und 10 (Grundausstattung ohne Kamera: 1, 13, 14) |
| Erkennung | über `camera_auto_detect=1`, **kein** explizites Overlay nötig |
| Sensor | 4056×3040, 10 bit, RGGB |
| Modi | 2028×1520 @ 30,02 fps · 4056×3040 @ 10,00 fps |
| Fokus | **manuell**, mit Fokuswerkzeug |
| Fokus-Controls in libcamera | **keine** — kein `AfMode`, `LensPosition`, `AfState` (gemessen 2026-09-08) |
| Fokusstellung | am 2026-09-08 eingestellt, Schärfe 216,6; Objektiv **nicht** gegen Verdrehen gesichert |
| Herstellerangabe Optik | f = 4,74 mm, F1.79, Fokusbereich ca. 20 cm – ∞ |

Gemessene Kenngrößen siehe [TIMING.md](TIMING.md): 6,8 s `.rpk`-Warmlauf,
15,0 Inferenzen/s mit SSD MobileNetV2 320×320, `SensorTimestamp` in
CLOCK_BOOTTIME.

## Serielle Schnittstellen

| Gerät | Rolle |
| --- | --- |
| **`/dev/ttyAMA0`** | **Datenport für GSVmulti.** Aktiv durch `dtparam=uart0=on` |
| `/dev/ttyAMA10` = `/dev/serial0` | **3-Pin-Debug-Header** — ausdrücklich NICHT der Nutzdatenport |
| `/dev/ttyUSB*`, `/dev/ttyACM*` | nicht vorhanden, kein USB-Seriell-Adapter angeschlossen |

`serial-getty@ttyAMA10` ist disabled, beide Ports sind also frei.

**Elektrisch offen ([OQ-09](open-questions.md)):** Pi-GPIO-Pegel dürfen nicht
direkt mit RS-232 verbunden werden. Es braucht einen RS-232-/RS-485-Transceiver,
und die galvanische Trennung ist für den Laboraufbau zu bewerten. Ein virtueller
USB-COM-Port am Pi 5 darf nicht pauschal vorausgesetzt werden.

## Bootkonfiguration

Relevante Zeilen in `/boot/firmware/config.txt`:

```
camera_auto_detect=1      # greift NUR beim Booten
display_auto_detect=1
dtparam=uart0=on          # aktiviert /dev/ttyAMA0
dtparam=i2c_arm=on
dtparam=pciex1
dtoverlay=vc4-kms-v3d
```

Nebenbefund: `auto_initramfs` ist auskommentiert, mit dem Hinweis auf einen
früheren Waveshare-Kernel 6.6.23. Für die Kamera unkritisch.

## Benutzer und Gruppen

`me-systeme` ist in `dialout`, `video`, `i2c`, `gpio`, `spi`, `render`, `sudo`.
Zugriff auf Kamera- und Serienports ist damit gegeben.

**`sudo` verlangt seit dem Reboot am 2026-09-07 ein Passwort.** Automatisierte
Paketinstallationen sind dadurch nicht möglich — siehe
[OQ-15](open-questions.md).

## Zeitsynchronisation

Aktuell `systemd-timesyncd`. Das liefert **keine protokollierbare Offset- und
Drift-Historie**. Für Messung M1 wird `chrony` gebraucht
([OQ-15](open-questions.md)) — ohne `chronyc tracking`-Log ist die Aussage
„Pi-Zeit gegen Referenz" nicht belegbar.

## Konfigurationsschlüssel

Betriebliche Werte gehören nach `/etc/dispread/hardware.conf`. Regel wie bei
MEhub: **fehlende Datei oder fehlender Schlüssel ⇒ dokumentierter Default**,
kein Fehler.

| Schlüssel | Bedeutung | Default |
| --- | --- | --- |
| `CAM_PORT` | erwarteter CAM-Anschluss (0 oder 1) | 0 |
| `CAMERA_MODEL` | erwartetes Modul | `imx500` |
| `SERIAL_PORT` | Datenport | `/dev/ttyAMA0` |
| `SERIAL_BAUD` | Baudrate | offen ([OQ-01](open-questions.md)) |
| `SERIAL_TRANSCEIVER` | Typ des Pegelwandlers | offen ([OQ-09](open-questions.md)) |
| `HAS_ISOLATION` | galvanische Trennung vorhanden? | offen |
| `OCR_BACKEND` | `sevenseg` oder `tesseract_cli` | `sevenseg` |
| `IMX500_RPK` | Modell für die Detektion | keines (manual_roi ist Primärpfad) |

## Temporäre Vorschaukonfiguration (2026-09-08)

`examples/17_camera_display_preview.py`: Kameraindex 0, 960×720 RGB888,
15 Bilder/s angefordert, automatische Belichtung, kein IMX500-Inferenzmodell.
Diese Einstellungen gelten nur für den laufenden Prozess; keine Boot- oder
Hardwarekonfiguration geändert. Fokus und Aufbau unverändert.
Technischer Kurztest: [Laborjournal](lab_journal.md), 2026-09-08.

## Workbench-Controls (2026-09-08)

Nach Modularisierung gleicher temporärer Vorschauaufbau. Neue Liveabfrage:
ExposureTime 101..105904066 µs, AnalogueGain 1..22,26087, Contrast 0..32,
AeEnable unterstützt. Diese Treibergrenzen sind keine empfohlenen Messparameter;
insbesondere können sehr lange Belichtungen mit Vorschau-/Timeoutgrenzen
kollidieren. Tatsächlicher Kurztest und Metadaten: [Laborjournal](lab_journal.md).
Keine physische oder persistente Systemkonfiguration geändert.

## Fokus- und Kamera-Controls (2026-09-08 gemessen)

Vollständige Controlliste der laufenden Kamera: `AeConstraintMode`, `AeEnable`,
`AeExposureMode`, `AeFlickerMode`, `AeFlickerPeriod`, `AeMeteringMode`,
`AnalogueGain`, `AnalogueGainMode`, `AwbEnable`, `AwbMode`, `Brightness`,
`CnnEnableInputTensor`, `ColourCorrectionMatrix`, `ColourGains`,
`ColourTemperature`, `Contrast`, `ExposureTime`, `ExposureTimeMode`,
`ExposureValue`, `FrameDurationLimits`, `HdrMode`, `NoiseReductionMode`,
`Saturation`, `ScalerCrop`, `ScalerCrops`, `Sharpness`, `StatsOutputEnable`,
`SyncFrames`, `SyncMode`.

**Kein Fokus-Control.** `Sharpness` ist ISP-Nachschärfung und verstellt das
Objektiv nicht. Fokussiert wird ausschließlich mechanisch am Objektiv. Die
Fokusassistenz der Workbench vergrößert nur die bestätigte ROI und zeigt einen
relativen Schärfewert; sie bewegt nichts.

Ebenfalls sichtbar: `ExposureTimeMode`/`AnalogueGainMode` sind die neueren
libcamera-Controls neben dem älteren `AeEnable`. Die Workbench benutzt weiter
`AeEnable`; ob ein Wechsel nötig ist, ist nicht geprüft.
