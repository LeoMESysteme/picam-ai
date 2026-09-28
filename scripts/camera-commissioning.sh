#!/usr/bin/env bash
# Diagnose der Kamera-Inbetriebnahme (Logitech StreamCam, USB/UVC 046d:0893).
#
# Ersetzt die IMX500-/Picamera2-Fassung (ausser Betrieb seit 2026-09-25,
# siehe docs/project_history.md). Rein lesend bis auf Schritt 5 (setzt zwei
# Controls testweise und liest sie sofort zurueck, stellt am Ende den vorher
# gelesenen Stand wieder her) und Schritt 6 (ein Testbild nach
# var/diagnostics/, ruehrt die Live-Controls nicht an). `v4l2-ctl --set-ctrl`
# wird ausschliesslich hier in Schritt 5 aufgerufen, nirgends sonst in diesem
# Skript.
#
# Ausgabe: je Pruefzeile OK/FEHLER/WARNUNG. Exit 0 nur ohne FEHLER.
#
# Bezug: docs/superpowers/sdd/2026-09-25-streamcam-switch/task-6-brief.md.

set -uo pipefail

USB_ID="046d:0893"
SYSFS_ROOT=/sys/class/video4linux
FOCUS_ABSOLUTE_TEST=48
DIAG_DIR="var/diagnostics/camera-commissioning"
TEST_IMAGE="$DIAG_DIR/test.png"

fail_count=0
warn_count=0

sec()  { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()   { printf '  \033[32m[ OK ]\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m[WARN]\033[0m %s\n' "$1"; warn_count=$((warn_count + 1)); }
bad()  { printf '  \033[31m[FAIL]\033[0m %s\n' "$1"; fail_count=$((fail_count + 1)); }
info() { printf '         %s\n' "$1"; }

# --------------------------------------------------------- 1. v4l2-ctl da? ---
sec "1. v4l2-ctl vorhanden"
if command -v v4l2-ctl >/dev/null 2>&1; then
    ok "v4l2-ctl: $(command -v v4l2-ctl)"
else
    bad "v4l2-ctl nicht installiert (Paket v4l-utils)"
    printf '\n  \033[31mKamera NICHT einsatzbereit\033[0m (%s Fehler, %s Warnungen).\n' \
           "$fail_count" "$warn_count"
    exit 1
fi

# --------------------------------------- 2. Geraet mit USB-ID, index == 0 ---
sec "2. Geraet ${USB_ID}, index==0 (${SYSFS_ROOT})"
DEVICE=""
if [ -d "$SYSFS_ROOT" ]; then
    for entry in "$SYSFS_ROOT"/video*; do
        [ -e "$entry/index" ] || continue
        index=$(cat "$entry/index" 2>/dev/null) || continue
        [ "$index" = "0" ] || continue
        iface=$(readlink -f "$entry/device" 2>/dev/null) || continue
        usb_dir="$iface/.."
        vendor=$(cat "$usb_dir/idVendor" 2>/dev/null) || continue
        product=$(cat "$usb_dir/idProduct" 2>/dev/null) || continue
        if [ "$vendor:$product" = "$USB_ID" ]; then
            DEVICE="/dev/$(basename "$entry")"
            break
        fi
    done
fi
if [ -n "$DEVICE" ]; then
    ok "Knoten: $DEVICE"
else
    bad "kein Video-Knoten mit USB-ID ${USB_ID} und index==0 unter ${SYSFS_ROOT} gefunden"
fi

# ------------------------------------------------- 3. USB-Geschwindigkeit ---
sec "3. USB-Geschwindigkeit"
if [ -n "$DEVICE" ]; then
    iface=$(readlink -f "$SYSFS_ROOT/$(basename "$DEVICE")/device" 2>/dev/null)
    speed=""
    [ -n "$iface" ] && speed=$(cat "$iface/../speed" 2>/dev/null)
    if [ "${speed:-}" = "5000" ]; then
        ok "speed == 5000 (USB3)"
    elif [ -n "${speed:-}" ]; then
        warn "USB2 - Kamera an einen blauen USB3-Port (gemessen: speed=${speed})"
    else
        warn "USB-Geschwindigkeit nicht lesbar (${iface:-Geraetepfad unbekannt}/../speed)"
    fi
else
    info "uebersprungen - kein Geraet aus Schritt 2"
fi

# ------------------------------------------------- 4. Format YUYV 1920x1080 ---
sec "4. Format YUYV 1920x1080"
if [ -n "$DEVICE" ]; then
    formats=$(v4l2-ctl -d "$DEVICE" --list-formats-ext 2>&1)
    # Diagnostischer Blockscan, kein autoritativer Parser: alle Zeilen ab dem
    # 'YUYV'-Eintrag bis zu (max.) 40 Folgezeilen, darin nach 1920x1080 suchen.
    if printf '%s\n' "$formats" | grep -A 40 "'YUYV'" | grep -q '1920x1080'; then
        ok "YUYV 1920x1080 in --list-formats-ext vorhanden"
    else
        bad "YUYV 1920x1080 nicht in --list-formats-ext gefunden"
    fi
else
    info "uebersprungen - kein Geraet aus Schritt 2"
fi

# ------------------------- 5. focus_automatic_continuous, focus_absolute ---
sec "5. Controls setzen und zurueck lesen (unveraendert am Ende)"
if [ -n "$DEVICE" ]; then
    original_focus_auto=$(v4l2-ctl -d "$DEVICE" --get-ctrl=focus_automatic_continuous 2>/dev/null \
        | grep -oE '[0-9]+' | head -1)
    original_focus_abs=$(v4l2-ctl -d "$DEVICE" --get-ctrl=focus_absolute 2>/dev/null \
        | grep -oE '[0-9]+' | head -1)

    set_err=$(v4l2-ctl -d "$DEVICE" \
        --set-ctrl=focus_automatic_continuous=0 \
        --set-ctrl=focus_absolute=${FOCUS_ABSOLUTE_TEST} 2>&1)
    set_rc=$?
    if [ "$set_rc" -ne 0 ]; then
        bad "v4l2-ctl --set-ctrl fehlgeschlagen: $(echo "$set_err" | tr '\n' ' ')"
    else
        readback_auto=$(v4l2-ctl -d "$DEVICE" --get-ctrl=focus_automatic_continuous 2>/dev/null \
            | grep -oE '[0-9]+' | head -1)
        readback_abs=$(v4l2-ctl -d "$DEVICE" --get-ctrl=focus_absolute 2>/dev/null \
            | grep -oE '[0-9]+' | head -1)
        if [ "${readback_auto:-}" = "0" ] && [ "${readback_abs:-}" = "${FOCUS_ABSOLUTE_TEST}" ]; then
            ok "focus_automatic_continuous=0, focus_absolute=${FOCUS_ABSOLUTE_TEST} gesetzt und bestaetigt"
        else
            bad "Ruecklesen weicht ab: focus_automatic_continuous=${readback_auto:-?}, focus_absolute=${readback_abs:-?}"
        fi
    fi

    # Unveraendert lassen: auf den vor diesem Lauf gelesenen Stand zurueck-
    # setzen. Ohne bekannten Ausgangswert wird nichts geraten (nur gewarnt).
    if [ -n "${original_focus_auto:-}" ] && [ -n "${original_focus_abs:-}" ]; then
        v4l2-ctl -d "$DEVICE" \
            --set-ctrl=focus_absolute="$original_focus_abs" \
            --set-ctrl=focus_automatic_continuous="$original_focus_auto" >/dev/null 2>&1
        info "Ausgangswerte wiederhergestellt (focus_automatic_continuous=${original_focus_auto}, focus_absolute=${original_focus_abs})"
    else
        warn "Ausgangswerte vor dem Test nicht lesbar - keine Wiederherstellung moeglich"
    fi
else
    info "uebersprungen - kein Geraet aus Schritt 2"
fi

# --------------------------------------------------------- 6. Testbild ---
sec "6. Testbild (cv2.VideoCapture, YUYV 1920x1080)"
PYTHON_BIN=""
if [ -x /home/me-systeme/picam-ai/.venv/bin/python ]; then
    PYTHON_BIN=/home/me-systeme/picam-ai/.venv/bin/python
elif [ -x ./.venv/bin/python ]; then
    PYTHON_BIN=./.venv/bin/python
fi

if [ -z "$DEVICE" ]; then
    info "uebersprungen - kein Geraet aus Schritt 2"
elif [ -z "$PYTHON_BIN" ]; then
    bad "kein Python mit cv2 gefunden (/home/me-systeme/picam-ai/.venv/bin/python oder ./.venv/bin/python)"
else
    mkdir -p "$DIAG_DIR"
    capture_err=$("$PYTHON_BIN" - "$DEVICE" "$TEST_IMAGE" <<'PYEOF' 2>&1
import sys

import cv2

device, out_path = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
try:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    ok, image = cap.read()
    if not ok:
        print("read() lieferte False", file=sys.stderr)
        sys.exit(1)
    if not cv2.imwrite(out_path, image):
        print(f"imwrite({out_path!r}) fehlgeschlagen", file=sys.stderr)
        sys.exit(1)
finally:
    cap.release()
PYEOF
)
    capture_rc=$?
    if [ "$capture_rc" -eq 0 ] && [ -s "$TEST_IMAGE" ]; then
        ok "Testbild gespeichert: $TEST_IMAGE ($(stat -c%s "$TEST_IMAGE") Bytes)"
    else
        bad "Testbild fehlgeschlagen (rc=$capture_rc): $(echo "$capture_err" | tail -3 | tr '\n' ' ')"
    fi
fi

# ------------------------------------------------------------------- Urteil ---
sec "Urteil"
if [ "$fail_count" -eq 0 ]; then
    printf '  \033[32mKamera einsatzbereit.\033[0m %s Warnung(en).\n' "$warn_count"
    exit 0
fi
printf '  \033[31mKamera NICHT einsatzbereit\033[0m (%s Fehler, %s Warnungen).\n' \
       "$fail_count" "$warn_count"
exit 1
