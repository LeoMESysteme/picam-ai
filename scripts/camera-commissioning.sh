#!/usr/bin/env bash
# Diagnose der Kamera-Inbetriebnahme (Raspberry Pi 5 + AI Camera / IMX500).
#
# Rein lesend - aendert nichts am System. Ausgabe: Zustand jeder Pruefung plus
# ein Urteil mit der naechsten Massnahme.
#
# Exit 0 = Kamera einsatzbereit, Exit 1 = nicht einsatzbereit.
#
# Bezug: Konzept.md §5 (AI Camera), docs/CAMERA_COMMISSIONING.md (Checkliste).

set -uo pipefail

DT_BASE=/sys/firmware/devicetree/base   # /proc/device-tree ist ein Symlink hierauf;
                                        # find(1) folgt ihm ohne -L nicht.
BOOT_CFG=/boot/firmware/config.txt
IMX500_MODEL_DIR=/usr/share/imx500-models

fail_count=0
warn_count=0

sec()  { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()   { printf '  \033[32m[ OK ]\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m[WARN]\033[0m %s\n' "$1"; warn_count=$((warn_count + 1)); }
bad()  { printf '  \033[31m[FAIL]\033[0m %s\n' "$1"; fail_count=$((fail_count + 1)); }
info() { printf '         %s\n' "$1"; }

# ---------------------------------------------------------------- Plattform ---
sec "Plattform"
if [ -r "$DT_BASE/model" ]; then
    # Device-Tree-Strings sind NUL-terminiert.
    info "Modell:  $(tr -d '\0' < "$DT_BASE/model")"
fi
info "Kernel:  $(uname -r)"
info "OS:      $(. /etc/os-release && echo "$PRETTY_NAME")"
info "Python:  $(python3 --version 2>&1)"
info "Uptime:  seit $(uptime -s)  (Boot-Zeitpunkt ist relevant, s. unten)"

# --------------------------------------------------------- Bootkonfiguration ---
sec "Bootkonfiguration ($BOOT_CFG)"
if [ ! -r "$BOOT_CFG" ]; then
    bad "$BOOT_CFG nicht lesbar"
else
    if grep -qE '^\s*camera_auto_detect=1' "$BOOT_CFG"; then
        ok "camera_auto_detect=1 gesetzt"
        info "Achtung: greift NUR beim Booten. Nach dem Anstecken der Kamera ist ein"
        info "Reboot noetig, sonst wird kein Overlay geladen."
    else
        warn "camera_auto_detect=1 fehlt oder ist auskommentiert"
    fi

    if cam_ovl=$(grep -oE '^\s*dtoverlay=imx[0-9]+[^ ]*' "$BOOT_CFG"); then
        ok "explizites Kamera-Overlay: $(echo "$cam_ovl" | tr -d ' ')"
    else
        info "kein explizites dtoverlay=imx... (nur Auto-Detect)"
    fi

    if grep -qE '^\s*dtparam=uart0=on' "$BOOT_CFG"; then
        ok "dtparam=uart0=on gesetzt (Datenport /dev/ttyAMA0 aktiv)"
    else
        warn "dtparam=uart0=on fehlt - /dev/ttyAMA0 steht dann nicht bereit"
    fi
fi

# ------------------------------------------------------------------ Overlays ---
sec "Device-Tree-Overlays (nur informativ)"
overlays=$(dtoverlay -l 2>&1)
if echo "$overlays" | grep -qi "no overlays loaded"; then
    info "dtoverlay -l: keine Overlays geladen"
    info "Das ist KEIN Fehlerkriterium: camera_auto_detect wird von der Firmware"
    info "beim Booten angewandt und erscheint hier nicht - dtoverlay -l zeigt nur"
    info "zur Laufzeit nachgeladene Overlays. Beweis ist der Sensorknoten unten."
else
    echo "$overlays" | sed 's/^/         /'
fi

# --------------------------------------------------------------- Device-Tree ---
sec "Device-Tree: Anschluss vs. Sensor"
# cam0_reg/cam1_reg stammen aus dem Basis-Device-Tree und sind auf dem Pi 5
# immer vorhanden. Sie belegen den ANSCHLUSS, nicht die Kamera.
connectors=0
for n in cam0_reg cam1_reg cam0_clk cam1_clk; do
    [ -e "$DT_BASE/$n" ] && connectors=$((connectors + 1))
done
if [ "$connectors" -gt 0 ]; then
    ok "CAM-Anschluesse im Device-Tree vorhanden ($connectors Knoten)"
else
    warn "keine CAM-Anschlussknoten gefunden - unerwartet fuer einen Pi 5"
fi

# Ein Sensorknoten entsteht erst durch das Kamera-Overlay - das ist der
# eigentliche Nachweis, dass die Kamera beim Booten erkannt wurde.
sensor_nodes=$(find -L "$DT_BASE" -maxdepth 8 -iname 'imx[0-9]*@*' 2>/dev/null | head -5)
if [ -n "$sensor_nodes" ]; then
    ok "Sensorknoten im Device-Tree:"
    echo "$sensor_nodes" | sed "s|$DT_BASE|         DT:|"
    # Der I2C-Knoten im Pfad ist der CAM-Bus des belegten Anschlusses.
    sensor_i2c=$(echo "$sensor_nodes" | head -1 | grep -oE 'i2c@[0-9a-f]+' || true)
    [ -n "$sensor_i2c" ] && info "belegter CAM-I2C-Knoten: $sensor_i2c"
else
    bad "kein Sensorknoten im Device-Tree (Anschluss da, Kamera nicht erkannt)"
fi

# --------------------------------------------------------------------- V4L2 ---
sec "V4L2-Geraete"
cfe_found=0
for f in /sys/class/video4linux/*/name; do
    [ -r "$f" ] || continue
    name=$(cat "$f")
    case "$name" in
        *rp1-cfe*|*csi*)
            ok "CSI-Frontend: $(basename "$(dirname "$f")") -> $name"
            cfe_found=1
            ;;
    esac
done
if [ "$cfe_found" -eq 0 ]; then
    bad "kein rp1-cfe/CSI-Node vorhanden (nur ISP-/Decoder-Nodes)"
    info "Die pispbe-* und rpi-hevc-dec-Nodes sind ISP bzw. Video-Decoder und"
    info "existieren auch ohne Kamera - sie sind kein Nachweis."
fi

if compgen -G "/dev/v4l-subdev*" > /dev/null; then
    ok "v4l-subdev vorhanden: $(echo /dev/v4l-subdev* | tr ' ' ',')"
    info "picamera2.devices.IMX500 scannt genau diese Nodes."
else
    bad "keine /dev/v4l-subdev* - IMX500() wird 'dev-node not found' melden"
fi

# ---------------------------------------------------------------------- I2C ---
sec "I2C-Busse (nur informativ)"
buses=$(ls -1 /dev/i2c-* 2>/dev/null | sed 's|/dev/i2c-||' | sort -n | tr '\n' ' ')
info "vorhanden: ${buses:-keine}"
# Ohne Kamera sind auf diesem Pi nur 1, 13 und 14 da; die CAM-Busse kommen mit
# dem Overlay hinzu. Die Nummern sind nicht stabil, deshalb kein Fehlerkriterium
# - der Sensorknoten oben ist der belastbare Nachweis.
extra_buses=$(echo " $buses" | tr ' ' '\n' | grep -vxE '1|13|14|' | tr '\n' ' ')
if [ -n "${extra_buses// /}" ]; then
    info "zusaetzlich zur Grundausstattung: ${extra_buses}(CAM-Busse)"
fi

# ------------------------------------------------------------ libcamera/rpicam ---
sec "libcamera / rpicam"
if command -v rpicam-hello >/dev/null 2>&1; then
    listing=$(rpicam-hello --list-cameras 2>&1)
    if echo "$listing" | grep -qi "no cameras available"; then
        bad "rpicam-hello --list-cameras: 'No cameras available!'"
    else
        ok "rpicam-hello listet Kameras:"
        echo "$listing" | sed 's/^/         /'
    fi
else
    bad "rpicam-hello nicht installiert (Paket rpicam-apps)"
fi

if python3 -c "import picamera2" 2>/dev/null; then
    cams=$(python3 -c "from picamera2 import Picamera2; print(len(Picamera2.global_camera_info()))" 2>/dev/null)
    if [ "${cams:-0}" -gt 0 ] 2>/dev/null; then
        ok "Picamera2.global_camera_info(): $cams Kamera(s)"
    else
        bad "Picamera2.global_camera_info() liefert [] - kein Sensor"
        info "Der reine Import von picamera2/IMX500 funktioniert auch ohne Kamera."
        info "Erst die Instanziierung scheitert - das ist erwartet, kein Softwarefehler."
    fi
else
    bad "python3-picamera2 nicht importierbar"
fi

# ------------------------------------------------------------------- IMX500 ---
sec "IMX500-Firmware und Modelle"
for fw in /usr/lib/firmware/imx500_firmware.fpk /usr/lib/firmware/imx500_loader.fpk; do
    if [ -r "$fw" ]; then
        ok "$(basename "$fw") ($(stat -c%s "$fw") Bytes)"
    else
        bad "$fw fehlt (Paket imx500-firmware)"
    fi
done
if [ -d "$IMX500_MODEL_DIR" ]; then
    n_models=$(find "$IMX500_MODEL_DIR" -name '*.rpk' | wc -l)
    if [ "$n_models" -gt 0 ]; then
        ok "$n_models Fertigmodelle in $IMX500_MODEL_DIR"
        info "Hinweis: das sind COCO-/ImageNet-Modelle. Fuer Messverstaerker-Displays"
        info "ist die bestaetigte manuelle ROI der Primaerpfad (s. Konzept §10 Ph. 2)."
    else
        warn "$IMX500_MODEL_DIR ist leer"
    fi
else
    warn "$IMX500_MODEL_DIR fehlt (Paket imx500-models)"
fi

# -------------------------------------------------------------------- Serial ---
sec "Serielle Schnittstellen"
if [ -e /dev/ttyAMA0 ]; then
    ok "/dev/ttyAMA0 vorhanden - das ist der Datenport fuer GSVmulti"
else
    warn "/dev/ttyAMA0 fehlt (dtparam=uart0=on gesetzt und rebootet?)"
fi
if [ -L /dev/serial0 ]; then
    warn "/dev/serial0 -> $(readlink /dev/serial0) ist der 3-Pin-DEBUG-Header, nicht GPIO14/15"
    info "Fuer die Nutzdaten /dev/ttyAMA0 verwenden, nicht /dev/serial0."
fi
if compgen -G "/dev/ttyUSB*" > /dev/null || compgen -G "/dev/ttyACM*" > /dev/null; then
    ok "USB-Seriell-Adapter: $(echo /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | tr ' ' ',')"
else
    info "kein USB-Seriell-Adapter angeschlossen"
fi
if id -nG | tr ' ' '\n' | grep -qx dialout; then
    ok "Benutzer $(id -un) ist in der Gruppe dialout"
else
    warn "Benutzer $(id -un) ist NICHT in dialout - kein Zugriff auf /dev/ttyAMA*"
fi
if id -nG | tr ' ' '\n' | grep -qx video; then
    ok "Benutzer $(id -un) ist in der Gruppe video"
else
    warn "Benutzer $(id -un) ist NICHT in video - kein Zugriff auf die Kamera-Nodes"
fi

# ------------------------------------------------------------------- Urteil ---
sec "Urteil"
if [ "$fail_count" -eq 0 ]; then
    printf '  \033[32mKamera einsatzbereit.\033[0m %s Warnung(en).\n' "$warn_count"
    printf '\n  Naechster Schritt:\n'
    printf '    rpicam-still -o /tmp/first-light.jpg     # Testaufnahme\n'
    printf '    Objektivdeckel abnehmen, manuellen Fokus einstellen\n'
    exit 0
fi

printf '  \033[31mKamera NICHT einsatzbereit\033[0m (%s Fehler, %s Warnungen).\n' \
       "$fail_count" "$warn_count"

# Fehlt der Sensorknoten, wurde die Kamera beim Booten nicht erkannt. Das ist
# der Fall, fuer den die Eskalationsleiter gilt.
if [ -z "$sensor_nodes" ]; then
    cat <<'EOF'

  Wahrscheinlichste Ursache: die Kamera wurde nach dem letzten Boot angesteckt.
  camera_auto_detect prueft die Anschluesse ausschliesslich beim Booten.

  Naechste Massnahme, in dieser Reihenfolge:

    1. Reboot:  sudo reboot
       Danach dieses Skript erneut ausfuehren.

    2. Haelt der Zustand an, explizites Overlay setzen (Backup zuerst):
         sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak
         # Zeile ergaenzen:  dtoverlay=imx500,cam0
         sudo reboot

    3. Kabel pruefen. Der Pi 5 hat den schmalen 22-poligen FPC-Anschluss, die
       AI Camera einen 15-poligen - es ist das mitgelieferte 15<->22-Kabel
       noetig, ein Pi-4-Kabel passt nicht. Riegel an BEIDEN Enden oeffnen,
       Kabel gerade bis zum Anschlag einschieben, Riegel schliessen.
       Kontaktrichtung gegen das Foto der offiziellen Doku pruefen:
       https://www.raspberrypi.com/documentation/accessories/ai-camera.html
       Pi vorher herunterfahren UND Netzteil abziehen.

    4. Gegenprobe am zweiten Port CAM/DISP1 (dann dtoverlay=imx500,cam1).
       Das trennt einen Port-/Kabeldefekt von einem Moduldefekt.

  Zur Eingrenzung nach einem Reboot:
    sudo dmesg | grep -iE 'imx500|rp1-cfe'
      - keine Zeile          -> Kabel verdreht oder nicht gesteckt (Schritt 3)
      - Zeile, aber Probe-Fehler -> Stromversorgung/Kabelqualitaet
      - Kamera gelistet, IMX500() scheitert -> Rechte auf /dev/v4l-subdev*
EOF
fi

exit 1
