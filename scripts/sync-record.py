#!/usr/bin/env python3
"""Kamerabilder und den seriellen GSV-Strom derselben Sitzung gemeinsam
aufzeichnen - Task E aus
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md.

Aufruf (ohne Hardware, vollstaendig testbar):

    ./.venv/bin/python scripts/sync-record.py --duration 30 \\
        --output var/diagnostics/lauf1

Aufruf mit echter Kamera + echtem Port (NICHT von hier aus ausgefuehrt -
siehe unten):

    ./.venv/bin/python scripts/sync-record.py --duration 60 --source camera \\
        --port /dev/ttyUSB0 --baudrate 38400

Zweck: um den Ende-zu-Ende-Versatz zwischen dem seriellen Telegramm des
GSV-2AS und dem, was die Kamera auf dem LC-Display sieht, zu messen (Task B
desselben Plans), braucht es eine gemeinsame Aufzeichnung beider Stroeme mit
Zeitstempeln in DERSELBEN Zeitdomaene (CLOCK_BOOTTIME). Aufzeichnen und
Auswerten sind bewusst getrennt: dieses Skript zeichnet nur auf, labelt
nichts und legt keine Datensatzproben an. Dieselbe Aufzeichnung laesst sich
so spaeter mit einem anderen Schutzintervall (M) erneut auswerten, ohne neu
messen zu muessen.

Reiner Diagnosecode, kein Produktionspfad - Stil und Argumentbehandlung an
`dataset-benchmark.py` angelehnt.

**Nur lesen.** An den seriellen Port wird kein einziges Byte gesendet -
weder ein Handshake-Signal (kein RTS/CTS, DSR/DTR, XON/XOFF) noch ein
Kommando. `SerialSink` (`src/dispread/sink/serial_out.py`) ist die einzige
Stelle im Repo, die auf diesen Port schreiben darf, und das ist nicht dieses
Skript.

Fuer die Bild-Zeitstempelfelder ist `Controller._capture`
(`src/dispread/workbench/controller.py`) der verbindliche Bezug: dieselben
Feldnamen, dieselbe Behandlung (`timestamp_semantics: "unknown"`,
`uncertainty_ns: None`, `TimeBaseKind.SENSOR_BOOTTIME`, `SensorTimestamp`
unveraendert). Ein Zeitstempel ohne benannte Zeitbasis ist nach AGENTS.md
keine verwertbare Angabe.

Betriebshinweis (`--source camera`): Die Kamera kann nur EIN Prozess halten.
Vor dem Start pruefen, ob ein `dispread serve` laeuft, und die
RP2040-Wedge-/Sperrgefahr aus OQ-22 (docs/open-questions.md) im Blick
behalten - dieser Zweig wird bewusst nicht von der Entwicklungsumgebung aus
ausgefuehrt, nur geschrieben und per `--source synthetic` getestet.

Robustheit:
  - Serielles Lesen laeuft in einem eigenen Thread, damit eine 66-ms-Bildauf-
    nahme kein Telegramm verschluckt.
  - Ctrl-C hinterlaesst vollstaendige, gueltige Dateien: beide JSONL-Dateien
    werden zeilenweise geflusht, und `session.json` wird auch im
    Abbruchfall geschrieben (mit `"aborted": true`).
  - Kommt ueber die ganze Dauer kein einziges Telegramm an, wird das am Ende
    laut gemeldet statt stillschweigend eine leere `serial.jsonl` zu
    hinterlassen.

## Erzeugen und Schreiben sind getrennte Threads (seit OQ-40-Nachtrag 2026-09-23)

Root-Cause-Messung vom 2026-09-23 (Aufzeichnung
`var/diagnostics/stall-105143` + ein unabhaengiger, I/O-loser Herzschlag-
prozess parallel): die Bildluecken (333/933/533/333 ms) UND der serielle
Burst fielen zeitlich mit Kernel-Dirty-Page-Writeback auf die SD-Karte
zusammen (bis 130 MB Writeback beobachtet). Der Herzschlagprozess selbst
zeigte KEINE Luecke - das System stand nicht still, nur die Dateischreiber
blockierten. Sowohl die Bildschleife (`cv2.imwrite`) als auch der serielle
Thread (`serial.jsonl`-Schreiben) blockierten im Dateisystemzugriff; der
serielle Thread rief dadurch `readline()` zu spaet auf und stempelte
laengst angekommene, gepufferte Zeilen zu spaet - das erzeugte den Burst.

Deshalb ist die Erzeugung (Kamera-`capture_request`/`synthetic`-Generator
bzw. `ser.readline()`) jetzt strikt von der Schreibseite (JPEG-Kodierung +
`frames.jsonl`, `serial.jsonl`) getrennt - je ein eigener Thread, verbunden
ueber `queue.Queue`:

  - `frame_queue` ist BEGRENZT (`--frame-queue-size`, Vorgabe 60 Bilder,
    bei 15 fps rund 4 s) - Bilder sind gross, ein unbegrenzter Puffer wuerde
    bei einem laengeren Schreibstau den Speicher aufbrauchen. Ist sie voll,
    wird das Bild verworfen und GEZAEHLT (`frames_dropped_queue_full` in
    `session.json`), nie still - dazu je ein `frames.jsonl`-Eintrag
    `{"dropped": true, "sensor_sequence": ..., "capture_timestamp": ...}`
    ueber eine eigene, unbegrenzte Meldungs-Warteschlange (Nutzdaten winzig).
    Die Aufnahmeseite blockiert dafuer NIE am `frame_queue.put(...)`.
  - `serial_queue` ist UNBEGRENZT wie die Drop-Meldungen - Telegrammzeilen
    sind winzig, ein Rueckstau kostet nur etwas RAM, nie eine verpasste
    Zeile.
  - Die Taktung (`--frame-rate`) bleibt im Erzeugerthread (regelt, wie
    schnell der naechste Frame angefordert wird), nicht im Schreiberthread -
    ein langsamer Schreiber darf die Aufnahmetaktung nie veraendern.
  - Bei Beendigung (Dauer erreicht, Ctrl-C, SIGTERM) werden beide
    Warteschlangen vollstaendig GELEERT, bevor `session.json` geschrieben
    wird - kein Bild/Telegramm, das schon in der Warteschlange steht, geht
    beim Abbruch verloren.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from dispread.frames import open_source
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUTPUT_ROOT = Path("var/diagnostics")
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 38400
DEFAULT_SYNTHETIC_URI = "synthetic://seven-seg"
SERIAL_READ_TIMEOUT_S = 0.5
#: Grosszuegig bemessen: mit --norm-schedule laeuft im finally-Block des
#: Lesethreads noch die Rueckstellung (Strom anhalten, zwei Register
#: schreiben+pruefen, wieder anhalten, zwei Register lesen, Strom neu starten -
#: mehrere Sleeps von 0,15-0,8 s), bevor der Thread sich beendet.
JOIN_TIMEOUT_S = 20.0
#: Registerlesen + Schreibsequenz kann vor dem ersten Telegramm laufen
#: (--norm-schedule) - grosszuegiger bemessen als das reine Portoeffnen.
READY_TIMEOUT_S = 15.0
#: Bilder sind gross (im Gegensatz zu Telegrammzeilen) - ein unbegrenzter
#: Puffer wuerde bei einem laengeren Schreibstau den Speicher aufbrauchen.
#: 60 bei 15 fps sind rund 4 s Reserve, siehe Moduldocstring.
DEFAULT_FRAME_QUEUE_SIZE = 60
#: Wie lange der Schreiberthread beim Leeren wartet, bevor er nach dem
#: Ende-Signal (`_QUEUE_DONE`) der Erzeugerseite selbst aufgibt.
WRITER_DRAIN_JOIN_TIMEOUT_S = 30.0

#: Bug 1 (Orchestrator, 2026-09-23): ein realer Lauf zeichnete 0 Bilder auf,
#: weil der Sensor blockiert war ("stream on failed" im Kernel-Log) und
#: `capture_request` unbegrenzt lange haengen blieb (kein TimeoutError, kein
#: Fehler ueberhaupt) - `sync-record.py` beendete sich trotzdem mit Exit 0
#: und "vollstaendig". Kommt im Kamerazweig innerhalb dieser Frist nach dem
#: Kamerastart kein einziges Bild an, gilt das als Befund (OQ-22,
#: docs/open-questions.md), nicht als stiller Leerlauf. Bewusst grosszuegiger
#: als der einzelne `capture_request(wait=2.0)`-Versuch in `_camera_frames` -
#: erst wiederholtes Ausbleiben nach dieser Frist zaehlt.
STARTUP_TIMEOUT_S = 5.0

#: Exitcode, wenn der Kamerazweig ohne ein einziges Bild endet (Timeout beim
#: ersten Bild oder frames_recorded == 0 am Ende) - ungleich 0, damit ein
#: Aufrufer (z.B. harvest.py) das nicht mit einem erfolgreichen Lauf
#: verwechselt.
EXIT_NO_FRAMES_ACQUIRED = 4

# --- Streamstart-Budget (Scope-Erweiterung, Orchestrator 2026-09-23) --------
#
# Root Cause der heutigen Blockade: OQ-22 (2026-09-09) haelt fest, dass die
# IMX500/RP2040-Bruecke nach rund 20-25 Streamstarts je Boot unerreichbar
# wird. Heute: 20 erfolgreiche Streamstarts, der 21. scheiterte mit
# `imx500_power_on: failed to get led gpio` gefolgt von `stream on failed`.
# Diese Konstanten und Funktionen pruefen das Budget VOR jedem
# `camera.start()` - lesend, oeffnen dabei selbst weder Kamera noch Port.

#: Sicherheitsmarge unterhalb der beobachteten 20-25 Starts (Vorgabe fuer
#: --stream-budget).
DEFAULT_STREAM_BUDGET = 15

#: Exitcode, wenn das Streamstart-Budget dieses Boots erschoepft ist ODER
#: das Kernel-Log bereits ein "stream on failed" dieses Boots zeigt - die
#: Kamera wird in diesem Fall gar nicht erst geoeffnet.
EXIT_STREAM_BUDGET_EXHAUSTED = 5

#: rp1-cfe (der CSI2-Frontend-Treiber) loggt diese Zeile bei jedem
#: erfolgreichen Streamstart - gemessen: normalerweise eine Zeile, im
#: beobachteten Fehlschlag ein Burst von 5 Zeilen innerhalb 1s. Deshalb wird
#: nach ZEITSTEMPELN gruppiert, nicht nach Zeilenzahl gezaehlt.
STREAM_START_LOG_MARKER = "Using a link rate of"

#: Markiert einen bereits fehlgeschlagenen Streamstart dieses Boots -
#: Oeffnen der Kamera wuerde auf einen vermutlich schon blockierten Sensor
#: treffen und nur weitere Fehler erzeugen (OQ-22).
STREAM_FAILED_LOG_MARKER = "stream on failed"

#: Zwei Log-Zeilen mit `STREAM_START_LOG_MARKER` innerhalb dieses Fensters
#: gehoeren zu EINEM Streamstart (siehe Burst-Beobachtung oben).
STREAM_START_GROUP_WINDOW_S = 2.0

#: `journalctl -o short-monotonic` UND `dmesg` beginnen beide eine Zeile mit
#: `[   12.345678]` (Sekunden seit Boot, CLOCK_MONOTONIC) - ein gemeinsamer
#: Parser reicht fuer beide Quellen.
_KERNEL_LOG_TIMESTAMP_RE = re.compile(r"^\[\s*(\d+\.\d+)\]")

#: Fallback, wenn das Kernel-Log nicht lesbar ist (z.B. eingeschraenkte
#: journalctl-Policy): zaehlt die eigenen Aufrufe dieses Skripts je Boot,
#: identifiziert ueber /proc/sys/kernel/random/boot_id. Eine Naeherung (kein
#: Kernel-Nachweis), aber besser als kein Budget zu pruefen.
DEFAULT_STREAM_BUDGET_COUNTER_PATH = REPO_ROOT / "var/diagnostics/camera-stream-budget.json"


def count_stream_starts(log_text: str) -> int:
    """Zaehlt Streamstarts (nicht Log-Zeilen) im Kerneltext: alle Zeilen mit
    `STREAM_START_LOG_MARKER`, gruppiert nach Zeitstempel - Zeilen innerhalb
    `STREAM_START_GROUP_WINDOW_S` zaehlen als EIN Start (siehe
    Moduldocstring-Abschnitt oben, Burst-Beobachtung).

    Reine Funktion, kein I/O - so mit eingebettetem Beispieltext testbar."""
    timestamps: list[float | None] = []
    for line in log_text.splitlines():
        if STREAM_START_LOG_MARKER not in line:
            continue
        match = _KERNEL_LOG_TIMESTAMP_RE.match(line)
        timestamps.append(float(match.group(1)) if match else None)
    if not timestamps:
        return 0
    if any(ts is None for ts in timestamps):
        # Zeitstempel nicht parsebar (unerwartetes Log-Format) - jede Zeile
        # einzeln zaehlen ist die sichere Richtung: eine Unterzaehlung wuerde
        # das Budget faelschlich als nicht erschoepft ausweisen.
        return len(timestamps)
    ordered = sorted(timestamps)
    count = 1
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if cur - prev >= STREAM_START_GROUP_WINDOW_S:
            count += 1
    return count


def has_stream_on_failed(log_text: str) -> bool:
    """Reine Funktion: enthaelt der Text bereits einen gescheiterten
    Streamstart dieses Boots?"""
    return STREAM_FAILED_LOG_MARKER in log_text


def _read_kernel_log() -> tuple[str | None, str]:
    """Liest das Kernel-Log des laufenden Boots: zuerst `journalctl -k -b`
    (ohne sudo lesbar, siehe Auftrag), sonst `dmesg`. `-o short-monotonic`
    liefert dieselbe `[   12.345678]`-Zeitstempelform wie `dmesg`, damit ein
    gemeinsamer Parser reicht. Liefert `(None, "unavailable")`, wenn beide
    scheitern - der Aufrufer faellt dann auf den Zaehlerdatei-Fallback
    zurueck."""
    try:
        result = subprocess.run(
            ["journalctl", "-k", "-b", "-o", "short-monotonic", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout, "journalctl"
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        result = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout, "dmesg"
    except (OSError, subprocess.SubprocessError):
        pass
    return None, "unavailable"


def _read_boot_id() -> str | None:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        return None


def _consult_counter_fallback(path: Path, boot_id: str | None) -> int:
    """Zaehlerdatei-Fallback (Kernel-Log unlesbar): gibt den Stand VOR
    diesem Aufruf zurueck (das ist `stream_starts_this_boot_before`) und
    schreibt den um 1 erhoehten Stand fuer den naechsten Aufruf zurueck -
    atomar wie `SessionProfile.save`. Alte `boot_id`-Eintraege werden dabei
    verworfen (nur die aktuelle Boot-ID ist noch aussagekraeftig)."""
    if boot_id is None:
        # Keine Boot-ID lesbar - kann den Stand keiner Sitzung zuordnen,
        # verhaelt sich wie "noch nichts gezaehlt" statt zu raten.
        return 0
    current = 0
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            stored = data.get(boot_id)
            if isinstance(stored, int):
                current = stored
        except (OSError, json.JSONDecodeError):
            current = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps({boot_id: current + 1}), encoding="utf-8")
    os.replace(tmp_path, path)
    return current


def check_stream_budget(
    *,
    stream_budget: int,
    override: bool,
    counter_path: Path = DEFAULT_STREAM_BUDGET_COUNTER_PATH,
) -> dict[str, Any]:
    """Prueft das Streamstart-Budget VOR jedem Kamerastart. Reine
    Entscheidungslogik (keine Kamera-/Port-Zugriffe) mit den I/O-Helfern
    oben - so mit gefaketem `subprocess.run`/Dateisystem testbar. Gibt ein
    dict fuer session.json UND die Abbruchentscheidung zurueck:

        stream_starts_this_boot_before, stream_budget, stream_budget_source,
        stream_on_failed_seen_before_start, refuse (bool), message (str|None),
        warn (bool), warn_message (str|None)
    """
    log_text, source = _read_kernel_log()
    if log_text is not None:
        count_before = count_stream_starts(log_text)
        failed_seen = has_stream_on_failed(log_text)
    else:
        count_before = _consult_counter_fallback(counter_path, _read_boot_id())
        failed_seen = False

    info: dict[str, Any] = {
        "stream_starts_this_boot_before": count_before,
        "stream_budget": stream_budget,
        "stream_budget_source": source,
        "stream_on_failed_seen_before_start": failed_seen,
        "refuse": False,
        "message": None,
        "warn": False,
        "warn_message": None,
    }

    if failed_seen and not override:
        info["refuse"] = True
        info["message"] = (
            "FEHLER: Im Kernel-Log dieses Boots steht bereits 'stream on failed' - "
            "der Sensor ist vermutlich blockiert. Reboot empfohlen (OQ-22, "
            "docs/open-questions.md). Die Kamera wird NICHT geoeffnet, das wuerde "
            "nur weitere Fehler erzeugen. Mit --override-stream-budget uebersteuerbar."
        )
        return info

    if count_before >= stream_budget and not override:
        info["refuse"] = True
        info["message"] = (
            f"FEHLER: Streamstart-Budget dieses Boots erschoepft "
            f"({count_before}/{stream_budget}), Reboot empfohlen, OQ-22 "
            "(docs/open-questions.md). Mit --override-stream-budget uebersteuerbar."
        )
        return info

    if count_before >= stream_budget - 3:
        info["warn"] = True
        info["warn_message"] = (
            f"WARNUNG: Streamstart-Budget dieses Boots fast erschoepft "
            f"({count_before}/{stream_budget}) - OQ-22, docs/open-questions.md."
        )
    return info


#: Sentinel: die Erzeugerseite (Kamera-/Serial-Thread) ist fertig, keine
#: weiteren Eintraege kommen mehr - der Schreiberthread leert die
#: Warteschlange bis hierher und beendet sich dann selbst. Eine eigene
#: Objektidentitaet statt z.B. `None`, damit sie sich nie mit einem echten
#: (leeren) Nutzlast-Eintrag verwechseln laesst.
_QUEUE_DONE = object()

DEFAULT_RESTORE_POINT = REPO_ROOT / "var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json"

#: Erlaubter Normierungsbereich des GSV-2AS, siehe CLAUDE.md ("Hardware-Fakten") -
#: 0,15...1 580 000. Nur zur Validierung von --norm-schedule, keine eigene Messung.
NORM_MIN, NORM_MAX = 0.15, 1_580_000.0


def _load_gsv_registers_module():
    """`scripts/gsv-registers.py` als Modul laden statt seine Byte-Kodierung
    neu zu schreiben (Registerkonstanten, Semikolon-Praefix-Pruefung,
    `read_register`). Reiner Funktions-/Konstantenimport - die Datei fuehrt
    beim Laden keinen I/O aus, nur unter `if __name__ == "__main__"`."""
    path = Path(__file__).resolve().with_name("gsv-registers.py")
    spec = importlib.util.spec_from_file_location("_dispread_gsv_registers", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_gsv_registers = _load_gsv_registers_module()

#: `set norm` (16) / `set dpoint` (17) aus der GSV-2-Anleitung, siehe
#: CLAUDE.md. `_gsv_registers` liefert nur die Lesebefehle; STOP/CLEAR/START
#: und LAST_ERR kommen von dort (identische Werte in norm_sweep.py).
SET_NORM_CMD = 0x10
SET_DPOINT_CMD = 0x11
LAST_ERR_CMD = _gsv_registers.READ_COMMANDS["last_error"][0]
OK_ERROR_CODE = 0xA0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zeichnet Kamerabilder und den seriellen GSV-Strom parallel auf, "
            "mit Zeitstempeln in CLOCK_BOOTTIME - fuer die photometrische "
            "Versatzmessung (Task B). Labelt nichts."
        )
    )
    parser.add_argument("--duration", type=float, required=True, help="Aufzeichnungsdauer in Sekunden")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Zielverzeichnis; Vorgabe: var/diagnostics/<Zeitstempel> (ausserhalb des Repos zu waehlen)",
    )
    parser.add_argument("--source", choices=["synthetic", "camera"], default="synthetic")
    parser.add_argument(
        "--synthetic-uri",
        default=DEFAULT_SYNTHETIC_URI,
        help="URI fuer --source synthetic, siehe dispread.frames.open_source",
    )
    parser.add_argument(
        "--frame-rate",
        type=float,
        default=15.0,
        help="Zieltakt der Bildaufnahme in Hz (0 = so schnell wie moeglich)",
    )
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serieller Port, nur gelesen")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--image-format", choices=["png", "jpg"], default="png")
    parser.add_argument(
        "--frame-queue-size",
        type=int,
        default=DEFAULT_FRAME_QUEUE_SIZE,
        help=(
            "Kapazitaet der Warteschlange zwischen Bildaufnahme und Schreiber "
            f"(JPEG-Kodierung + frames.jsonl); Vorgabe {DEFAULT_FRAME_QUEUE_SIZE} "
            "Bilder. Bei Ueberlauf wird das Bild verworfen und gezaehlt statt die "
            "Aufnahme zu blockieren, siehe Moduldocstring 'Erzeugen und Schreiben "
            "sind getrennte Threads'."
        ),
    )
    parser.add_argument(
        "--camera-size",
        # 960x720 ist NICHT beliebig gewaehlt, sondern die in OQ-22
        # festgehaltene Betriebsgroesse. Jede dort protokollierte Sitzung mit
        # einem grossen Sensormodus (2028x1520, 4056x3040) war die letzte des
        # Boots - danach setzt der Sensor keinen Stream mehr auf und nur ein
        # Reboot hilft. Am 2026-09-22 mit der Vorgabe 2028x1520 erneut
        # ausgeloest. 960x720 hebt das Problem nicht auf, verzoegert es aber
        # nachweislich; mehr Ziffernhoehe kommt ueber ScalerCrop, nicht ueber
        # den Sensormodus.
        default="960x720",
        help="Nur --source camera: Aufloesung BxH. Vorgabe 960x720 - "
             "groessere Sensormodi blockieren den Sensor bis zum Reboot (OQ-22)",
    )
    parser.add_argument(
        "--allow-large-sensor-mode",
        action="store_true",
        help="Sperre gegen grosse Sensormodi aufheben. Nur bewusst setzen - "
             "siehe OQ-22, Folge ist im Zweifel ein Reboot des Labor-Pi",
    )
    parser.add_argument(
        "--stream-budget",
        type=int,
        default=DEFAULT_STREAM_BUDGET,
        help=(
            f"Nur --source camera: Sicherheitsmarge fuer Streamstarts dieses Boots, "
            f"Vorgabe {DEFAULT_STREAM_BUDGET} (unter den beobachteten 20-25 Starts, "
            "nach denen die IMX500/RP2040-Bruecke unerreichbar wird, OQ-22). Ist das "
            "Budget erreicht, wird VOR dem Kamerastart abgebrochen (Exit 5)."
        ),
    )
    parser.add_argument(
        "--override-stream-budget",
        action="store_true",
        help=(
            "Streamstart-Budget-Abbruch bewusst uebersteuern (auch bei bereits "
            "geloggtem 'stream on failed') - nur bewusst setzen, siehe OQ-22."
        ),
    )
    parser.add_argument(
        "--scaler-crop",
        default=None,
        help=(
            "Sensor-Ausschnitt 'X,Y,W,H' in Sensorkoordinaten (ganzzahlig), nur "
            "--source camera. Mehr Ziffernhoehe ueber Zoom, nie ueber einen "
            "groesseren Sensormodus (OQ-22, CLAUDE.md-Entscheidung 4 aus "
            "docs/superpowers/plans/2026-09-23-ernte-phase1.md). Ohne diese "
            "Option wird kein ScalerCrop gesetzt (Sensor-Vorgabe bleibt aktiv)."
        ),
    )
    parser.add_argument(
        "--norm-schedule",
        default=None,
        help=(
            "Ablaufplan fuer den GSV-Normierungsfaktor, 'Faktor:Haltesekunden,...', "
            "z.B. '1.0:5,2.0:5,1.0:5'. Erzeugt waehrend der Aufzeichnung grosse "
            "Anzeigespruenge ueber Register 16 ('set norm')/17 ('set dpoint') - "
            "geschrieben INNERHALB der bereits offenen seriellen Sitzung dieses "
            "Skripts, siehe var/diagnostics/gsv-serial-2026-09-22/norm_sweep.py. "
            "Jeder Befehl inkl. Antwort landet in commands.jsonl. Ohne diese Option "
            "wird kein einziges Byte an den Port gesendet (Verhalten unveraendert)."
        ),
    )
    parser.add_argument(
        "--restore-point",
        type=Path,
        default=DEFAULT_RESTORE_POINT,
        help=(
            "Rueckstellpunkt-JSON (siehe scripts/gsv-registers.py --out), nur mit "
            f"--norm-schedule relevant. Vorgabe: {DEFAULT_RESTORE_POINT}"
        ),
    )
    parser.add_argument(
        "--ignore-restore-point-mismatch",
        action="store_true",
        help=(
            "Start trotz abweichendem Registerstand erzwingen (nur mit "
            "--norm-schedule). Ohne diese Option ist ein abweichender "
            "Ausgangszustand ein harter Abbruch vor jedem Schreibzugriff."
        ),
    )
    args = parser.parse_args(argv)
    _check_camera_size(parser, args)
    if args.frame_queue_size < 1:
        parser.error("--frame-queue-size muss mindestens 1 sein")
    if args.ignore_restore_point_mismatch and not args.norm_schedule:
        parser.error("--ignore-restore-point-mismatch ergibt nur mit --norm-schedule einen Sinn")
    if args.norm_schedule is not None:
        try:
            args.norm_schedule = _parse_norm_schedule(args.norm_schedule)
        except ValueError as exc:
            parser.error(str(exc))
    if args.scaler_crop is not None:
        try:
            args.scaler_crop = _parse_scaler_crop(args.scaler_crop)
        except ValueError as exc:
            parser.error(str(exc))
    return args


def _parse_norm_schedule(raw: str) -> list[tuple[float, float]]:
    """'1.0:5,2.0:5,1.0:5' -> [(1.0, 5.0), (2.0, 5.0), (1.0, 5.0)]."""
    schedule: list[tuple[float, float]] = []
    for segment in raw.split(","):
        segment = segment.strip()
        if not segment:
            continue
        factor_str, sep, hold_str = segment.partition(":")
        if not sep:
            raise ValueError(f"--norm-schedule-Segment {segment!r} hat nicht die Form Faktor:Sekunden")
        try:
            factor = float(factor_str)
            hold_s = float(hold_str)
        except ValueError as exc:
            raise ValueError(f"--norm-schedule-Segment {segment!r} ist nicht numerisch: {exc}") from exc
        if not (NORM_MIN <= factor <= NORM_MAX):
            raise ValueError(
                f"--norm-schedule-Segment {segment!r}: Normierungsfaktor {factor} ausserhalb des "
                f"dokumentierten Bereichs {NORM_MIN}..{NORM_MAX} (CLAUDE.md)"
            )
        if hold_s <= 0:
            raise ValueError(f"--norm-schedule-Segment {segment!r}: Haltezeit muss > 0 Sekunden sein")
        schedule.append((factor, hold_s))
    if not schedule:
        raise ValueError("--norm-schedule ergab keine Eintraege")
    return schedule


def _parse_scaler_crop(raw: str) -> tuple[int, int, int, int]:
    """'1000,800,1600,1200' -> (1000, 800, 1600, 1200) - X,Y,W,H in
    Sensorkoordinaten, wie picamera2 sie fuer das `ScalerCrop`-Control
    erwartet (siehe `_camera_frames`)."""
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError(f"--scaler-crop muss genau vier Werte X,Y,W,H haben, nicht {raw!r}")
    try:
        values = tuple(int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"--scaler-crop-Werte muessen ganzzahlig sein: {raw!r}") from exc
    if any(v <= 0 for v in values):
        raise ValueError(
            f"--scaler-crop-Werte muessen alle positiv sein (kein negativer oder Null-Wert): {raw!r}"
        )
    return values  # type: ignore[return-value]


def _encode_norm(norm: float) -> tuple[tuple[int, int, int], int]:
    """Portiert aus `norm_sweep.py::encode_norm` (Vorschrift aus der GSV-2-
    Anleitung, 'set norm', Befehl 16) - byteidentisch uebernommen, nicht neu
    hergeleitet."""
    dp = math.floor(math.log10(norm))
    scaled = norm / 10**dp
    if scaled > 1.6666 / 1.05:
        scaled /= 10
        dp += 1
    mant = round(scaled * 5250020)
    return (mant >> 16 & 0xFF, mant >> 8 & 0xFF, mant & 0xFF), dp + 1


def _send(ser, byte: int, sleep_s: float) -> None:
    """Ein einzelnes Kommandobyte schreiben, flushen, warten - wie die
    `ser.write(...); ser.flush(); time.sleep(...)`-Zeilen in norm_sweep.py,
    nur ohne die dort verwendeten Semikolon-Mehrfachanweisungen."""
    ser.write(bytes([byte]))
    ser.flush()
    time.sleep(sleep_s)


def _read_exact(ser, count: int, timeout_s: float = 1.0) -> bytes:
    """Wie `gsv-registers.py::_read_exact` / `norm_sweep.py::read_exact`."""
    deadline = time.monotonic() + timeout_s
    buf = b""
    while len(buf) < count and time.monotonic() < deadline:
        chunk = ser.read(count - len(buf))
        if chunk:
            buf += chunk
    return buf


#: Ab dieser Pixelzahl gilt ein Modus als "gross" im Sinne von OQ-22.
#: 960x720 = 691 200 liegt darunter, 2028x1520 = 3 082 560 darueber.
LARGE_SENSOR_MODE_PIXELS = 1_000_000


def _check_camera_size(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Grosse Sensormodi abweisen, solange OQ-22 offen ist.

    Das ist bewusst ein harter Abbruch und keine Warnung: die Folge eines
    grossen Modus ist ein Sensor, der bis zum Reboot keinen Stream mehr
    aufsetzt. Auf einem Laborrechner ist das teuer genug, um es nicht von
    einer uebersehenen Zeile auf stderr abhaengen zu lassen. Am 2026-09-22
    genau so passiert.
    """
    if args.source != "camera" or args.allow_large_sensor_mode:
        return
    width, _, height = args.camera_size.partition("x")
    try:
        pixels = int(width) * int(height)
    except ValueError:
        parser.error(f"--camera-size muss die Form BxH haben, nicht {args.camera_size!r}")
    if pixels > LARGE_SENSOR_MODE_PIXELS:
        parser.error(
            f"--camera-size {args.camera_size} ist ein grosser Sensormodus. Laut OQ-22 "
            "(docs/open-questions.md) war jede protokollierte Sitzung mit einem solchen "
            "Modus die letzte des Boots - danach setzt der Sensor keinen Stream mehr auf "
            "und nur ein Reboot hilft. Nimm 960x720 (mehr Ziffernhoehe ueber ScalerCrop) "
            "oder setze --allow-large-sensor-mode, wenn du das bewusst in Kauf nimmst."
        )


# --- Norm-Schedule: Schreiben INNERHALB der bereits offenen seriellen Sitzung --
#
# Alle Funktionen hier bekommen das offene `serial.Serial`-Objekt des
# Lesethreads gereicht und werden auch nur von dort aufgerufen - es gibt nie
# eine zweite Verbindung zum Port, und nie einen zweiten Thread, der
# gleichzeitig liest/schreibt.


def _log_event(f_cmd, state: dict[str, Any], event: dict[str, Any]) -> None:
    event.setdefault("t_boot", time.clock_gettime(time.CLOCK_BOOTTIME))
    f_cmd.write(json.dumps(event, ensure_ascii=False) + "\n")
    f_cmd.flush()
    state["command_event_count"] = state.get("command_event_count", 0) + 1


def _read_norm_dpoint(ser, f_cmd, state, *, label: str) -> tuple[dict, dict]:
    """Liest die Register `norm` (0x1A) und `dpoint` (0x1C) ueber
    `gsv-registers.py::read_register` (prueft das Semikolon-Praefix). Beide
    Antworten sind keine Telegramme und werden nur hier geloggt, nie nach
    serial.jsonl geschrieben."""
    norm_cmd, norm_len = _gsv_registers.READ_COMMANDS["norm"]
    dpoint_cmd, dpoint_len = _gsv_registers.READ_COMMANDS["dpoint"]
    norm_entry = _gsv_registers.read_register(ser, "norm", norm_cmd, norm_len)
    _log_event(f_cmd, state, {"event": "register_read", "label": label, "register": "norm",
                               "response_tag": "non_telegram", **norm_entry})
    dpoint_entry = _gsv_registers.read_register(ser, "dpoint", dpoint_cmd, dpoint_len)
    _log_event(f_cmd, state, {"event": "register_read", "label": label, "register": "dpoint",
                               "response_tag": "non_telegram", **dpoint_entry})
    return norm_entry, dpoint_entry


def _pause_read_registers_resume(ser, f_cmd, state, *, label: str) -> tuple[dict, dict]:
    """Strom anhalten (STOP+CLEAR, wie `gsv-registers.py`), Register lesen,
    Strom wieder anwerfen (START). Pause- und Resume-Zeitpunkt werden je als
    eigenes Ereignis geloggt - das ist die einzige Stelle, an der der Strom
    fuer eine reine Lesekontrolle (Precheck, Rueckstellungspruefung)
    angehalten wird."""
    t_pause = time.clock_gettime(time.CLOCK_BOOTTIME)
    _send(ser, _gsv_registers.CMD_STOP, 0.3)
    _send(ser, _gsv_registers.CMD_CLEAR, 0.2)
    ser.reset_input_buffer()
    _log_event(f_cmd, state, {"event": "pause_transmission", "label": label, "t_boot": t_pause})

    norm_entry, dpoint_entry = _read_norm_dpoint(ser, f_cmd, state, label=label)

    _send(ser, _gsv_registers.CMD_START, 0.8)
    t_resume = time.clock_gettime(time.CLOCK_BOOTTIME)
    _log_event(f_cmd, state, {"event": "resume_transmission", "label": label, "t_boot": t_resume})
    return norm_entry, dpoint_entry


def _check_restore_point(ser, restore_point: dict, f_cmd, state, *, label: str) -> tuple[bool, dict]:
    norm_entry, dpoint_entry = _pause_read_registers_resume(ser, f_cmd, state, label=label)
    expected_norm = restore_point.get("register", {}).get("norm", {}).get("daten")
    expected_dpoint = restore_point.get("register", {}).get("dpoint", {}).get("daten")
    actual_norm = norm_entry.get("daten")
    actual_dpoint = dpoint_entry.get("daten")
    matches = actual_norm == expected_norm and actual_dpoint == expected_dpoint
    detail = {
        "matches_restore_point": matches,
        "expected_norm": expected_norm,
        "actual_norm": actual_norm,
        "expected_dpoint": expected_dpoint,
        "actual_dpoint": actual_dpoint,
    }
    return matches, detail


def _apply_norm_dpoint(ser, norm_bytes, dpoint_byte: int, f_cmd, state, *, label: str) -> bool:
    """Setzt Normierung + Dezimalpunkt. Reihenfolge byteidentisch zu
    `apply_cfg` in norm_sweep.py: Strom anhalten+leeren, `set norm` (0x10)
    schreiben, per `last error` (0x42) pruefen, `set dpoint` (0x11)
    schreiben, wieder pruefen, Strom neu starten. Jede Kommandoantwort ist
    keine Telegrammzeile - sie kommt aus einem direkten `ser.read()`, nie aus
    der `readline()`-Schleife, und wird deshalb nur nach commands.jsonl
    geschrieben, mit `response_tag: non_telegram`."""
    t_pause = time.clock_gettime(time.CLOCK_BOOTTIME)
    _send(ser, _gsv_registers.CMD_STOP, 0.25)
    _send(ser, _gsv_registers.CMD_CLEAR, 0.15)
    ser.reset_input_buffer()
    _log_event(f_cmd, state, {"event": "pause_transmission", "label": label, "t_boot": t_pause})

    ser.write(bytes([SET_NORM_CMD, *norm_bytes]))
    ser.flush()
    time.sleep(0.35)
    ser.reset_input_buffer()
    ser.write(bytes([LAST_ERR_CMD]))
    ser.flush()
    resp_norm = _read_exact(ser, 2)
    _log_event(f_cmd, state, {
        "event": "command", "label": label, "command_name": "set_norm",
        "command_bytes": [SET_NORM_CMD, *norm_bytes],
        "response_bytes": list(resp_norm), "response_tag": "non_telegram",
    })

    ser.write(bytes([SET_DPOINT_CMD, dpoint_byte]))
    ser.flush()
    time.sleep(0.35)
    ser.reset_input_buffer()
    ser.write(bytes([LAST_ERR_CMD]))
    ser.flush()
    resp_dpoint = _read_exact(ser, 2)
    _log_event(f_cmd, state, {
        "event": "command", "label": label, "command_name": "set_dpoint",
        "command_bytes": [SET_DPOINT_CMD, dpoint_byte],
        "response_bytes": list(resp_dpoint), "response_tag": "non_telegram",
    })

    _send(ser, _gsv_registers.CMD_START, 0.7)
    t_resume = time.clock_gettime(time.CLOCK_BOOTTIME)
    _log_event(f_cmd, state, {"event": "resume_transmission", "label": label, "t_boot": t_resume})

    ok_norm = len(resp_norm) == 2 and resp_norm[1] == OK_ERROR_CODE
    ok_dpoint = len(resp_dpoint) == 2 and resp_dpoint[1] == OK_ERROR_CODE
    return ok_norm and ok_dpoint


# --- Serieller Strom, eigener Thread, nur lesen -----------------------------


def _serial_worker(
    port: str,
    baudrate: int,
    serial_queue: queue.Queue[Any],
    stop_event: threading.Event,
    ready_event: threading.Event,
    state: dict[str, Any],
    *,
    commands_path: Path | None = None,
    norm_schedule: list[tuple[float, float]] | None = None,
    restore_point: dict | None = None,
    ignore_restore_point_mismatch: bool = False,
) -> None:
    """Liest zeilenweise, sendet nichts (ausser den bewusst dokumentierten
    `--norm-schedule`-Schreibbefehlen, siehe unten). Signalisiert
    `ready_event`, sobald der Port entweder offen ist oder das Oeffnen
    endgueltig fehlgeschlagen ist - der Aufrufer wartet darauf, bevor er die
    Bildaufnahme startet.

    Schreibt NIE selbst nach `serial.jsonl` - jede gelesene Zeile geht sofort
    auf `serial_queue` (Erzeuger/Schreiber-Trennung, siehe Moduldocstring).
    Ein eigener Schreiberthread (`_serial_writer_worker`) leert die
    Warteschlange; nur so bleibt `ser.readline()` frei von Dateisystem-
    Wartezeit, die frueher (OQ-40-Nachtrag 2026-09-23) genau hier den
    beobachteten Burst erzeugt hat. Legt auf JEDEM Ausstiegspfad genau einmal
    `_QUEUE_DONE` auf `serial_queue`, damit der Schreiberthread sich sicher
    beenden kann, auch wenn der Port nie geoeffnet werden konnte."""
    import serial

    ser = None
    f_cmd = None
    try:
        try:
            ser = serial.Serial(
                port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=SERIAL_READ_TIMEOUT_S,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except Exception as exc:  # noqa: BLE001 - an den Aufrufer weiterreichen
            state["open_error"] = f"{type(exc).__name__}: {exc}"
            ready_event.set()
            return

        state["open_error"] = None

        if norm_schedule is not None:
            assert commands_path is not None and restore_point is not None
            f_cmd = open(commands_path, "a", encoding="utf-8")

            # Precheck: Registerstand mit dem Rueckstellpunkt vergleichen, BEVOR
            # auch nur ein Schreibbefehl geschickt wird. Der Strom wird dafuer
            # kurz angehalten und danach sofort wieder gestartet (eigenes
            # pause/resume-Ereignispaar, Label "precheck").
            matches, precheck_detail = _check_restore_point(ser, restore_point, f_cmd, state, label="precheck")
            state["precheck"] = precheck_detail
            if not matches and not ignore_restore_point_mismatch:
                state["schedule_error"] = (
                    "Geraet steht nicht am Rueckstellpunkt "
                    f"(erwartet norm={precheck_detail['expected_norm']} dpoint={precheck_detail['expected_dpoint']}, "
                    f"gelesen norm={precheck_detail['actual_norm']} dpoint={precheck_detail['actual_dpoint']}). "
                    "Kein Schreibbefehl wurde gesendet. Mit --ignore-restore-point-mismatch uebersteuerbar."
                )
                ready_event.set()
                return
            if not matches and ignore_restore_point_mismatch:
                precheck_detail["ignored"] = True

        ready_event.set()
        count = 0
        max_queue_depth = 0
        schedule_index = 0
        next_switch_mono: float | None = None
        if norm_schedule:
            factor, hold_s = norm_schedule[0]
            norm_bytes, dpoint_byte = _encode_norm(factor)
            ok = _apply_norm_dpoint(ser, norm_bytes, dpoint_byte, f_cmd, state, label=f"schedule[0] factor={factor}")
            state.setdefault("schedule_steps", []).append(
                {"index": 0, "factor": factor, "hold_s": hold_s, "last_error_ok": ok}
            )
            next_switch_mono = time.monotonic() + hold_s
            schedule_index = 1

        while not stop_event.is_set():
            if (
                norm_schedule
                and schedule_index < len(norm_schedule)
                and next_switch_mono is not None
                and time.monotonic() >= next_switch_mono
            ):
                factor, hold_s = norm_schedule[schedule_index]
                norm_bytes, dpoint_byte = _encode_norm(factor)
                ok = _apply_norm_dpoint(
                    ser, norm_bytes, dpoint_byte, f_cmd, state,
                    label=f"schedule[{schedule_index}] factor={factor}",
                )
                state.setdefault("schedule_steps", []).append(
                    {"index": schedule_index, "factor": factor, "hold_s": hold_s, "last_error_ok": ok}
                )
                next_switch_mono = time.monotonic() + hold_s
                schedule_index += 1
                continue
            try:
                raw = ser.readline()
            except Exception as exc:  # noqa: BLE001
                state["read_error"] = f"{type(exc).__name__}: {exc}"
                break
            if not raw:
                # Lesetimeout, kein Byte angekommen - weiter warten.
                continue
            t_boot = time.clock_gettime(time.CLOCK_BOOTTIME)
            text = raw.decode("ascii", errors="replace").rstrip("\r\n")
            serial_queue.put({"t_boot": t_boot, "text": text})
            count += 1
            max_queue_depth = max(max_queue_depth, serial_queue.qsize())
        state["count"] = count
        state["max_serial_queue_depth"] = max_queue_depth
    finally:
        # `not state.get("schedule_error")`: bei abweichendem Rueckstellpunkt
        # (Precheck-Mismatch ohne --ignore-restore-point-mismatch) wurde
        # bewusst NIE ein Schreibbefehl gesendet ("Kein Schreibbefehl wurde
        # gesendet." in der Fehlermeldung) - dieser `finally`-Block wird
        # jetzt (anders als vor der Erzeuger/Schreiber-Trennung) auch beim
        # fruehen Rueckkehrpfad des Precheck-Mismatch durchlaufen, darf die
        # Rueckstellung dort aber NICHT ausloesen, sonst wuerde genau dort
        # doch noch ein Schreibbefehl rausgehen.
        if norm_schedule is not None and f_cmd is not None and ser is not None and not state.get("schedule_error"):
            try:
                restore_norm_bytes = restore_point["register"]["norm"]["daten"]
                restore_dpoint_byte = restore_point["register"]["dpoint"]["daten"][0]
                write_ok = _apply_norm_dpoint(
                    ser, restore_norm_bytes, restore_dpoint_byte, f_cmd, state, label="restore"
                )
                verify_matches, verify_detail = _check_restore_point(
                    ser, restore_point, f_cmd, state, label="restore_verify"
                )
                state["restore_verification"] = {"write_ok": write_ok, **verify_detail}
            except Exception as exc:  # noqa: BLE001 - Sitzung trotzdem sauber abschliessen
                state["restore_verification"] = {"error": f"{type(exc).__name__}: {exc}"}
        if f_cmd is not None:
            f_cmd.close()
        if ser is not None:
            try:
                ser.close()
            except Exception:  # noqa: BLE001 - Aufraeumen, kein neuer Fehler beim Beenden
                pass
        serial_queue.put(_QUEUE_DONE)


def _serial_writer_worker(
    serial_queue: queue.Queue[Any],
    out_path: Path,
    state: dict[str, Any],
) -> None:
    """Entkoppelter Schreiber fuer `serial.jsonl`. Leert `serial_queue`
    zeilenweise geflusht, bis das `_QUEUE_DONE`-Sentinel des Lesethreads
    kommt - danach ist die Warteschlange per Konstruktion leer (FIFO, das
    Sentinel ist immer der letzte Eintrag des Lesethreads), es geht also
    nichts verloren. `state["count"]` ist die massgebliche Zahl tatsaechlich
    geschriebener Telegrammzeilen (ersetzt das frueher im Lesethread selbst
    gefuehrte `count`)."""
    count = 0
    with open(out_path, "a", encoding="utf-8") as f:
        while True:
            item = serial_queue.get()
            if item is _QUEUE_DONE:
                break
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            count += 1
    state["count"] = count


# --- Bildstrom ---------------------------------------------------------------


def _synthetic_frames(uri: str):
    """`Frame`-Objekte aus `dispread.frames.open_source`, roh durchgereicht.

    Liefert ein drittes Element `sensor_sequence=None` - es gibt bei
    `synthetic://` keine Sensor-/libcamera-Sequenznummer, das Feld existiert
    trotzdem in jedem Eintrag, nur eben leer (siehe OQ-40-Nachtrag). Die
    Elemente vier bis sechs (`scaler_crop_actual`, `sensor_mode_size`,
    `sensor_array_size`) sind aus demselben Grund immer `None` - das sind
    alles Kamera-Controls/-Eigenschaften, `synthetic://` hat keine Kamera
    (Task 2/Bug 2, docs/superpowers/plans/2026-09-23-ernte-phase1.md)."""
    source = open_source(uri)
    source.open()
    try:
        for frame in source.frames():
            yield frame.image, frame.capture_timestamp.to_dict(), None, None, None, None
    finally:
        source.close()


def _camera_frames(size: tuple[int, int], fps: float, scaler_crop: tuple[int, int, int, int] | None = None):
    """Echte Kamera - lazy Import, siehe CLAUDE.md.

    Feldbehandlung ist `Controller._capture` nachgebildet (controller.py
    ~Zeile 1515), **und die Konfiguration ebenfalls** (~Zeile 1638). Das ist
    kein Schoenheitsdetail:

    Die erste Fassung nahm `create_still_configuration`. Am echten IMX500
    liefert das ueber zwei Minuten **kein einziges Bild** - der Standbildpfad
    ist auf Einzelaufnahmen ausgelegt, nicht auf einen Dauerlauf, und der
    Sensor laeuft bei voller Aufloesung mit 10 fps. Gemessen am 2026-09-22:
    serieller Strom lief, `frames.jsonl` blieb leer.

    `create_video_configuration` ist der im Repo erprobte Streaming-Pfad; mit
    ihm sind die 88 Bestandsproben aufgenommen worden. `format="RGB888"` und
    die gesetzte `FrameRate` gehoeren dazu - ohne das Format liefert
    `make_array("main")` eine andere Kanalanordnung als der Rest der Kette
    erwartet. `queue=False` verhindert, dass ein gepuffertes altes Bild
    ausgeliefert wird; fuer eine Zeitversatzmessung waere genau das fatal.

    Zusaetzlich zur `SensorTimestamp`-basierten `Timestamp` liefert jedes
    Bild die Sensor-/libcamera-Sequenznummer (drittes Element im Tupel,
    `sensor_sequence`) - das eigentliche Gegenmittel zum OQ-40-Nachtrag: der
    Skript-eigene Zaehler `frame_sequence` in `run()` zaehlt nur, wie oft
    dieses Skript geschrieben hat, und haette die 2,60s-Luecke vom
    2026-09-23 NICHT gezeigt, weil `queue=False` das verpasste Bild
    stillschweigend ausliess. `request.request` ist das zugrundeliegende
    `libcamera.Request`-Objekt (siehe
    `/usr/lib/python3/dist-packages/picamera2/request.py:90`,
    `self.request = request` im `CompletedRequest.__init__`); dessen
    `.sequence`-Attribut stammt aus der kompilierten `_libcamera`-Erweiterung,
    reexportiert ueber `/usr/lib/python3/dist-packages/libcamera/__init__.py:4`
    (`from ._libcamera import *`) - `dir(libcamera.Request)` listet
    `sequence` dort auf. Muss VOR `request.release()` gelesen werden, wie
    `make_array`/`get_metadata` auch.

    `scaler_crop` (Task 2, docs/superpowers/plans/2026-09-23-ernte-phase1.md,
    Entscheidung 4 - mehr Pixel je Punkt ueber `ScalerCrop`, nie ueber einen
    groesseren Sensormodus, OQ-22) geht als `ScalerCrop`-Eintrag in die
    `controls`-Dict von `create_video_configuration`, NICHT ueber
    `camera.set_controls(...)` nach dem Start:
    `Picamera2.configure_()` uebernimmt `camera_config['controls']`
    unveraendert in `self.controls`
    (`/usr/lib/python3/dist-packages/picamera2/picamera2.py:1292`,
    `self.controls = Controls(self, controls=self.camera_config['controls'])`),
    und `Picamera2.start_()` wendet genau diese Controls beim eigentlichen
    Systemstart an (`picamera2.py:1338`, `self.camera.start(controls)`). Ein
    `set_controls` nach `camera.start()` wird laut Docstring dort "delivered
    with the next request that gets submitted" (`picamera2.py:1428`) - der
    allererste Request koennte den Crop also noch nicht sehen. Der
    Konfigurationsweg ist deshalb der einzige, der den Crop schon im ersten
    Bild garantiert.

    Der tatsaechlich wirksame Ausschnitt kommt aus den Metadaten des ersten
    Bildes zurueck (`request.get_metadata()["ScalerCrop"]`,
    `CompletedRequest.get_metadata` in
    `/usr/lib/python3/dist-packages/picamera2/request.py:161`) - dort wird
    jeder libcamera-`Rectangle`-Wert ueber `convert_from_libcamera_type`
    (`/usr/lib/python3/dist-packages/picamera2/utils.py:6-13`) zu einem
    reinen `(x, y, w, h)`-Tupel. Weil dieses Tupel kein `str`/`bool`/`int`/
    `float` ist, faellt es durch den bestehenden JSON-Metadatenfilter unten
    und wird deshalb VORHER separat ausgelesen.

    `sensor_mode_size`/`sensor_array_size` (Bug 2, Orchestrator 2026-09-23):
    das Aufloesungs-Gate (`source_dot_column_px`, `dispread.charcells`) misst
    im OUTPUT-Bild (hier `size`). Ist der `ScalerCrop` schmaler als der
    Output des gewaehlten Sensormodus, skaliert der ISP hoch - das Gate war
    damit zu optimistisch. Fuer die Ruecktransformation auf native
    Sensorpixel wird der tatsaechlich gewaehlte Sensormodus gebraucht:

    - `camera.camera_config["sensor"]["output_size"]` - erst NACH
      `camera.configure(...)` gueltig. Gesetzt in `_update_camera_config`
      (`/usr/lib/python3/dist-packages/picamera2/picamera2.py:1177-1178`,
      `sensor_config['output_size'] = ...; camera_config['sensor'] =
      sensor_config`), aufgerufen aus `configure_()` direkt nach
      `self.camera.configure(libcamera_config)`. Das ist der 2x2-gebinnte
      Sensormodus (z. B. 2028x1520 aus "Selected sensor format" im Log),
      NICHT die volle Sensorflaeche.
    - `camera.camera_properties["PixelArraySize"]` - die volle,
      unbeschnittene, unbinned Sensorflaeche (z. B. 4056x3040). Property-
      Getter bei `picamera2.py:451`, befuellt aus `self.camera.properties`
      in `configure_()` (`picamera2.py:1251`,
      `self.camera_properties_[k.name] = utils.convert_from_libcamera_type(v)`).
      Nach `camera.configure(...)` verlaesslich gesetzt, genau wie `sensor`.

    Beide werden wie `scaler_crop_actual` roh als Tupel durchgereicht (kein
    `str`/`bool`/`int`/`float`, faellt also ebenfalls durch den JSON-Filter).
    """
    from picamera2 import Picamera2

    camera = Picamera2()
    try:
        controls: dict[str, Any] = {"FrameRate": fps} if fps > 0 else {}
        if scaler_crop is not None:
            controls["ScalerCrop"] = scaler_crop
        config = camera.create_video_configuration(
            main={"size": size, "format": "RGB888"},
            controls=controls,
            queue=False,
        )
        camera.configure(config)
        sensor_mode_size = None
        sensor_config = camera.camera_config.get("sensor") if camera.camera_config else None
        if sensor_config is not None and sensor_config.get("output_size") is not None:
            sensor_mode_size = tuple(sensor_config["output_size"])
        sensor_array_size = None
        pixel_array_size = camera.camera_properties.get("PixelArraySize")
        if pixel_array_size is not None:
            sensor_array_size = tuple(pixel_array_size)
        camera.start(show_preview=False)
        while True:
            request = camera.capture_request(wait=2.0)
            try:
                image = request.make_array("main").copy()
                raw_metadata = request.get_metadata()
                try:
                    sensor_sequence = request.request.sequence
                except AttributeError:
                    sensor_sequence = None
                scaler_crop_actual = raw_metadata.get("ScalerCrop")
            finally:
                request.release()
            # Nur JSON-faehige echte Metadaten; SensorTimestamp unveraendert -
            # deckungsgleich mit Controller._capture.
            metadata = {k: v for k, v in raw_metadata.items() if isinstance(v, (str, bool, int, float))}
            timestamp = Timestamp(
                value_ns=int(metadata.get("SensorTimestamp", 0)),
                base=TimeBaseKind.SENSOR_BOOTTIME,
                semantics=TimestampSemantics.UNKNOWN,
                uncertainty_ns=None,
            )
            yield (
                image,
                timestamp.to_dict(),
                sensor_sequence,
                scaler_crop_actual,
                sensor_mode_size,
                sensor_array_size,
            )
    finally:
        camera.stop()


def _frame_generator(args: argparse.Namespace):
    if args.source == "synthetic":
        yield from _synthetic_frames(args.synthetic_uri)
    else:
        w, _, h = args.camera_size.partition("x")
        yield from _camera_frames((int(w), int(h)), args.frame_rate, scaler_crop=args.scaler_crop)


class _CameraStartupTimeout(Exception):
    """Kein Bild innerhalb von `STARTUP_TIMEOUT_S` nach Kamerastart (Bug 1)."""


def _no_frames_message(detail: str) -> str:
    """Einheitlicher Wortlaut fuer jeden Fall, in dem der Kamerazweig ohne
    Bild endet (Timeout, Ausnahme, oder frames_recorded == 0 am Ende) - immer
    mit Verweis auf OQ-22 und dem Hinweis, den Prozess nicht hart zu beenden
    (Bug 1, Auftrag)."""
    return (
        "Sensor liefert keine Bilder - moeglicherweise blockiert, Reboot noetig, "
        f"Prozess NICHT hart beenden (OQ-22, docs/open-questions.md). {detail}"
    )


def _camera_startup_guard(gen, timeout_s: float):
    """Wrapper-Generator: das ERSTE Element von `gen` wird mit einer
    Zeitschranke `timeout_s` geholt, alle weiteren unveraendert durchgereicht.

    Grund: eine haengende Kamera (z.B. nach OQ-22 blockiertem Sensor) laesst
    `camera.capture_request(...)` in `_camera_frames` unter Umstaenden
    unbegrenzt lange haengen - ohne TimeoutError, ohne jede Meldung. Das darf
    nicht als stiller Leerlauf enden (Bug 1, Orchestrator 2026-09-23).

    Das erste `next(gen)` laeuft dafuer in einem eigenen Daemon-Thread. Bei
    Zeitueberschreitung wird dieser Thread NICHT abgebrochen - Python kann
    einen blockierten Aufruf nicht sicher unterbrechen, und das Kamera-Objekt
    soll laut Auftrag nicht aggressiv beendet werden. Der Thread stirbt mit
    dem Prozess (daemon=True); der reguläre Abbruchpfad (`camera.stop()` im
    `finally` von `_camera_frames`) laeuft nur, wenn `capture_request`
    irgendwann doch noch zurueckkehrt oder wirft."""
    result: dict[str, Any] = {}
    done = threading.Event()

    def _fetch_first() -> None:
        try:
            result["item"] = next(gen)
        except StopIteration:
            result["stopped"] = True
        except Exception as exc:  # noqa: BLE001 - an den Aufrufer weiterreichen
            result["exception"] = exc
        finally:
            done.set()

    thread = threading.Thread(target=_fetch_first, daemon=True, name="camera-startup-guard")
    thread.start()
    if not done.wait(timeout=timeout_s):
        raise _CameraStartupTimeout(
            f"Kein Bild innerhalb von {timeout_s:.0f}s nach Kamerastart erhalten"
        )
    if "exception" in result:
        raise result["exception"]
    if not result.get("stopped"):
        yield result["item"]
    yield from gen


def _frame_acquisition_worker(
    args: argparse.Namespace,
    frame_queue: queue.Queue[Any],
    frame_drop_queue: queue.Queue[Any],
    stop_event: threading.Event,
    state: dict[str, Any],
) -> None:
    """Zieht Bilder aus `_frame_generator` und legt sie in `frame_queue` ab -
    kodiert und schreibt NICHTS (siehe Moduldocstring, Abschnitt "Erzeugen
    und Schreiben sind getrennte Threads"): genau die Dateisystemzugriffe,
    die dort frueher in dieser Schleife lagen, blockierten am 2026-09-23
    unter Kernel-Dirty-Page-Writeback (bis 130 MB) - ein I/O-loser
    Herzschlagprozess zeigte im selben Zeitraum KEINE Luecke.

    Die Taktung (`--frame-rate`) bleibt bewusst HIER, nicht im
    Schreiberthread: sie regelt, wie schnell dieser Thread den naechsten
    Generator-`next()` aufruft - fuer `synthetic://` ist das die einzige
    Bremse ueberhaupt (Erzeugung ist praktisch sofort), fuer `--source
    camera` taktet die Hardware selbst schon (`FrameRate`-Control) und diese
    Sleep bleibt zusaetzlich wirksam, exakt wie vor dieser Aufteilung -
    reines Verschieben der Zustaendigkeit, keine Verhaltensaenderung an der
    Taktung selbst.

    Ist `frame_queue` voll (Schreiber kommt nicht hinterher), wird das Bild
    NICHT geschrieben und NICHT still verworfen: es zaehlt in
    `state["frames_dropped_queue_full"]`, und eine kleine Meldung (ohne
    Bilddaten) geht auf die unbegrenzte `frame_drop_queue`, damit sie trotzdem
    als eigener `frames.jsonl`-Eintrag sichtbar wird. `frame_queue.put(...)`
    selbst blockiert dafuer NIE.

    `scaler_crop_actual` (Task 2) wird nur vom ERSTEN Bild in `state`
    uebernommen - `session.json["scaler_crop_actual"]" soll den Wert aus den
    Metadaten des ersten Bildes tragen, nicht den letzten gesehenen."""
    frame_period_s = 1.0 / args.frame_rate if args.frame_rate > 0 else 0.0
    start_mono = time.monotonic()
    next_due = start_mono
    max_loop_iteration_s = 0.0
    stall_iterations: list[dict[str, Any]] = []
    prev_loop_end_mono = start_mono
    prev_sensor_timestamp_ns: int | None = None
    max_frame_queue_depth = 0
    frames_acquired = 0
    frames_dropped = 0
    scaler_crop_actual_captured = False

    gen = _frame_generator(args)
    if args.source == "camera":
        # Bug 1: nur der Kamerazweig kann haengen bleiben - synthetic:// ist
        # ein reiner Generator ohne Hardware-I/O.
        gen = _camera_startup_guard(gen, STARTUP_TIMEOUT_S)
    try:
        for (
            image,
            timestamp_dict,
            sensor_sequence,
            scaler_crop_actual,
            sensor_mode_size,
            sensor_array_size,
        ) in gen:
            if stop_event.is_set():
                break
            if not scaler_crop_actual_captured:
                # Bug 2: sensor_mode_size/sensor_array_size sind je Sitzung
                # konstant (aus camera.configure(), nicht je Bild neu
                # gelesen) - werden hier wie scaler_crop_actual vom ERSTEN
                # Bild uebernommen.
                state["scaler_crop_actual"] = scaler_crop_actual
                state["sensor_mode_size"] = sensor_mode_size
                state["sensor_array_size"] = sensor_array_size
                scaler_crop_actual_captured = True
            now = time.monotonic()
            iter_duration_s = now - prev_loop_end_mono
            if iter_duration_s > max_loop_iteration_s:
                max_loop_iteration_s = iter_duration_s
            if frame_period_s > 0 and iter_duration_s > 3 * frame_period_s:
                stall_iterations.append({
                    "t_boot": time.clock_gettime(time.CLOCK_BOOTTIME),
                    "duration_s": iter_duration_s,
                })
            if now - start_mono >= args.duration:
                break
            frames_acquired += 1

            value_ns = timestamp_dict.get("value_ns")
            sensor_timestamp_interval_ns = None
            if prev_sensor_timestamp_ns is not None and value_ns is not None:
                sensor_timestamp_interval_ns = value_ns - prev_sensor_timestamp_ns
            if value_ns is not None:
                prev_sensor_timestamp_ns = value_ns

            try:
                frame_queue.put_nowait({
                    "sensor_sequence": sensor_sequence,
                    "sensor_timestamp_interval_ns": sensor_timestamp_interval_ns,
                    "capture_timestamp": timestamp_dict,
                    "image": image,
                })
            except queue.Full:
                frames_dropped += 1
                frame_drop_queue.put({
                    "dropped": True,
                    "sensor_sequence": sensor_sequence,
                    "capture_timestamp": timestamp_dict,
                    "t_boot": time.clock_gettime(time.CLOCK_BOOTTIME),
                })
            max_frame_queue_depth = max(max_frame_queue_depth, frame_queue.qsize())

            if frame_period_s > 0:
                next_due += frame_period_s
                sleep_for = next_due - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
            prev_loop_end_mono = time.monotonic()
    except _CameraStartupTimeout as exc:
        # Bug 1: laut ablehnen statt still 0 Bilder zu hinterlassen - Wortlaut
        # zeigt auf OQ-22 (docs/open-questions.md), inkl. Hinweis, den Prozess
        # NICHT hart zu beenden (siehe _camera_startup_guard-Docstring).
        state["acquisition_error"] = _no_frames_message(f"{exc}.")
    except Exception as exc:  # noqa: BLE001 - Sitzung trotzdem sauber abschliessen
        if args.source == "camera" and frames_acquired == 0:
            # Jede Ausnahme im Kamerazweig OHNE EIN EINZIGES BILD ist derselbe
            # Befund wie der Startup-Timeout (Bug 1) - z.B. ein TimeoutError,
            # den eine andere picamera2-Version statt eines Haengers wirft.
            # Kam schon mindestens ein Bild an, ist es ein anderer Fehler (die
            # Kamera lief ja) - dafuer waere "Sensor liefert keine Bilder"
            # falsch, siehe generischer Zweig unten.
            state["acquisition_error"] = _no_frames_message(f"{type(exc).__name__}: {exc}")
        else:
            state["acquisition_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        gen.close()
        state.setdefault("scaler_crop_actual", None)
        state.setdefault("sensor_mode_size", None)
        state.setdefault("sensor_array_size", None)
        state["frames_acquired"] = frames_acquired
        state["frames_dropped_queue_full"] = frames_dropped
        state["max_loop_iteration_s"] = max_loop_iteration_s
        state["stall_iterations"] = stall_iterations
        state["max_frame_queue_depth"] = max_frame_queue_depth
        frame_queue.put(_QUEUE_DONE)
        frame_drop_queue.put(_QUEUE_DONE)


def _frame_writer_worker(
    frame_queue: queue.Queue[Any],
    frame_drop_queue: queue.Queue[Any],
    frames_jsonl: Path,
    frames_dir: Path,
    ext: str,
    state: dict[str, Any],
) -> None:
    """Entkoppelter Schreiber: JPEG/PNG-Kodierung (`cv2.imwrite`) +
    `frames.jsonl` - siehe Moduldocstring. `frame_sequence` wird HIER
    vergeben (luecken-/abbruchfreie, aufsteigende Zaehlung der tatsaechlich
    geschriebenen Bilder, unveraendert gegenueber dem Verhalten vor dieser
    Aufteilung) - verworfene Bilder tragen keine `frame_sequence`, ihre
    `frames.jsonl`-Meldung traegt stattdessen `sensor_sequence`/
    `capture_timestamp` (das, was von ihnen bekannt ist).

    `cv2.imwrite` ist eine OpenCV-C++-Funktion; das Kodieren blockiert
    trotzdem bewusst NUR hier und nie den Aufnahmethread - unabhaengig
    davon, wie lange dabei der GIL gehalten wird, darf ein langsamer
    Schreibvorgang nie die naechste Bildaufnahme verzoegern. `cv2` ist am
    Modulanfang importiert (kein Hardwarebedarf, siehe dort) - kein
    zusaetzlicher lokaler Import noetig."""
    frames_written = 0
    frame_done = False
    drop_done = False
    with open(frames_jsonl, "a", encoding="utf-8") as f_frames:
        while not (frame_done and drop_done):
            try:
                item = frame_queue.get(timeout=0.1)
            except queue.Empty:
                item = None
            if item is not None:
                if item is _QUEUE_DONE:
                    frame_done = True
                else:
                    frames_written += 1
                    filename = f"frame_{frames_written:06d}.{ext}"
                    cv2.imwrite(str(frames_dir / filename), item["image"])
                    entry = {
                        "file": filename,
                        "frame_sequence": frames_written,
                        "sensor_sequence": item["sensor_sequence"],
                        "sensor_timestamp_interval_ns": item["sensor_timestamp_interval_ns"],
                        "capture_timestamp": item["capture_timestamp"],
                    }
                    f_frames.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f_frames.flush()
            while True:
                try:
                    drop_item = frame_drop_queue.get_nowait()
                except queue.Empty:
                    break
                if drop_item is _QUEUE_DONE:
                    drop_done = True
                else:
                    f_frames.write(json.dumps(drop_item, ensure_ascii=False) + "\n")
                    f_frames.flush()
    state["frames_recorded"] = frames_written


# --- Hauptablauf --------------------------------------------------------------


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"nicht serialisierbar: {type(value)!r}")


#: Vorher: SIGTERM hatte keinen Handler und beendete den Prozess sofort ohne
#: session.json - nur SIGINT (Ctrl-C, per Default-Handler eine
#: KeyboardInterrupt) lief durch den sauberen Abbruchpfad. SIGTERM wird hier
#: bewusst auf denselben Pfad umgelenkt statt einen eigenen zu bauen.
_SIGTERM_MARKER = "SIGTERM"


def _install_sigterm_handler() -> None:
    def _handle_sigterm(signum, frame):  # noqa: ARG001 - Signatur von signal.signal vorgegeben
        raise KeyboardInterrupt(_SIGTERM_MARKER)

    signal.signal(signal.SIGTERM, _handle_sigterm)


def run(args: argparse.Namespace) -> int:
    _install_sigterm_handler()

    # Streamstart-Budget (Scope-Erweiterung, Orchestrator 2026-09-23): rein
    # lesende Pruefung VOR jedem Kamerazugriff - Kamera/Port werden hier noch
    # nicht angefasst. Nur relevant fuer --source camera.
    stream_budget_info: dict[str, Any] | None = None
    if args.source == "camera":
        stream_budget_info = check_stream_budget(
            stream_budget=args.stream_budget,
            override=args.override_stream_budget,
        )
        if stream_budget_info["warn"]:
            print(stream_budget_info["warn_message"], file=sys.stderr)
        if stream_budget_info["refuse"]:
            print(stream_budget_info["message"], file=sys.stderr)
            return EXIT_STREAM_BUDGET_EXHAUSTED

    output_dir = args.output or (DEFAULT_OUTPUT_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S"))
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    serial_jsonl = output_dir / "serial.jsonl"
    frames_jsonl = output_dir / "frames.jsonl"
    session_json = output_dir / "session.json"

    commands_jsonl: Path | None = None
    restore_point: dict | None = None
    if args.norm_schedule is not None:
        if not args.restore_point.is_file():
            print(f"Fehler: Rueckstellpunkt-Datei nicht gefunden: {args.restore_point}", file=sys.stderr)
            return 1
        try:
            restore_point = json.loads(args.restore_point.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"Fehler: Rueckstellpunkt-Datei {args.restore_point} ist kein gueltiges JSON: {exc}", file=sys.stderr)
            return 1
        commands_jsonl = output_dir / "commands.jsonl"

    started_at_utc = datetime.now(UTC).isoformat()
    started_at_boottime_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)

    stop_event = threading.Event()
    ready_event = threading.Event()
    serial_state: dict[str, Any] = {"count": 0, "open_error": None}
    serial_writer_state: dict[str, Any] = {"count": 0}
    serial_queue: queue.Queue[Any] = queue.Queue()  # unbegrenzt, siehe Moduldocstring

    serial_thread = threading.Thread(
        target=_serial_worker,
        args=(args.port, args.baudrate, serial_queue, stop_event, ready_event, serial_state),
        kwargs={
            "commands_path": commands_jsonl,
            "norm_schedule": args.norm_schedule,
            "restore_point": restore_point,
            "ignore_restore_point_mismatch": args.ignore_restore_point_mismatch,
        },
        name="serial-reader",
        daemon=True,
    )
    serial_writer_thread = threading.Thread(
        target=_serial_writer_worker,
        args=(serial_queue, serial_jsonl, serial_writer_state),
        name="serial-writer",
        daemon=True,
    )
    # Schreiber zuerst starten: er soll sofort abholen koennen, sobald der
    # Lesethread die erste Zeile auf die Warteschlange legt.
    serial_writer_thread.start()
    serial_thread.start()

    if not ready_event.wait(timeout=READY_TIMEOUT_S):
        print(
            f"Fehler: serieller Lesethread meldete sich nicht innerhalb {READY_TIMEOUT_S}s",
            file=sys.stderr,
        )
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        return 1
    if serial_state["open_error"]:
        print(
            f"Fehler: serieller Port {args.port!r} konnte nicht geoeffnet werden: "
            f"{serial_state['open_error']}",
            file=sys.stderr,
        )
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        return 1
    if serial_state.get("schedule_error"):
        print(f"Fehler: {serial_state['schedule_error']}", file=sys.stderr)
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        return 1

    ext = "png" if args.image_format == "png" else "jpg"

    frame_acq_state: dict[str, Any] = {}
    frame_writer_state: dict[str, Any] = {}
    frame_queue: queue.Queue[Any] = queue.Queue(maxsize=args.frame_queue_size)  # begrenzt, siehe Moduldocstring
    frame_drop_queue: queue.Queue[Any] = queue.Queue()  # unbegrenzt, nur kleine Meldungen

    frame_acq_thread = threading.Thread(
        target=_frame_acquisition_worker,
        args=(args, frame_queue, frame_drop_queue, stop_event, frame_acq_state),
        name="frame-acquisition",
        daemon=True,
    )
    frame_writer_thread = threading.Thread(
        target=_frame_writer_worker,
        args=(frame_queue, frame_drop_queue, frames_jsonl, frames_dir, ext, frame_writer_state),
        name="frame-writer",
        daemon=True,
    )
    frame_writer_thread.start()
    frame_acq_thread.start()

    aborted = False
    abort_reason: str | None = None
    start_mono = time.monotonic()

    try:
        # Die eigentliche Aufnahme laeuft komplett in den beiden Threads
        # oben - dieser Hauptthread wartet nur auf das Dauerende oder ein
        # Signal (SIGINT/SIGTERM landen hier als KeyboardInterrupt, siehe
        # `_install_sigterm_handler`, genau wie zuvor bei der blockierenden
        # Bildschleife).
        stop_event.wait(timeout=args.duration)
    except KeyboardInterrupt as exc:
        aborted = True
        if exc.args and exc.args[0] == _SIGTERM_MARKER:
            abort_reason = "SIGTERM"
            print("\nAbbruch (SIGTERM) - schreibe bereits aufgezeichnete Daten vollstaendig ab.", file=sys.stderr)
        else:
            abort_reason = "KeyboardInterrupt (Ctrl-C)"
            print("\nAbbruch (Ctrl-C) - schreibe bereits aufgezeichnete Daten vollstaendig ab.", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - Sitzung trotzdem sauber abschliessen
        aborted = True
        abort_reason = f"{type(exc).__name__}: {exc}"
        traceback.print_exc(file=sys.stderr)
    finally:
        elapsed_s = time.monotonic() - start_mono
        stop_event.set()

        # Reihenfolge ist Teil der Abbruchgarantie (siehe Moduldocstring):
        # erst die Erzeugerseiten fertig werden lassen - ihr jeweils letzter
        # Schritt ist `_QUEUE_DONE` auf die eigene Warteschlange zu legen -,
        # dann die Schreiberseiten, die bis zu diesem Sentinel vollstaendig
        # leeren. Erst danach ist bekannt, was wirklich geschrieben wurde.
        # JOIN_TIMEOUT_S ist grosszuegig bemessen (--norm-schedule laesst im
        # finally-Block des Lesethreads noch die Rueckstellung laufen; die
        # Kamera kann bis zu `wait=2.0` in `capture_request` haengen).
        frame_acq_thread.join(timeout=JOIN_TIMEOUT_S)
        frame_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)

        frames_recorded = frame_writer_state.get("frames_recorded", 0)
        serial_lines_recorded = serial_writer_state.get("count", 0)

        acquisition_error = frame_acq_state.get("acquisition_error")
        if args.source == "camera" and frames_recorded == 0 and not acquisition_error:
            # Bug 1, zweiter Fall: der Kamerazweig lieferte zwar irgendwann
            # eine Antwort (kein Timeout, keine Ausnahme), aber am Ende steht
            # trotzdem 0 aufgezeichnete Bilder da - auch das ist ein Befund,
            # kein stiller Leerlauf.
            acquisition_error = _no_frames_message("Kamerazweig endete mit 0 aufgezeichneten Bildern.")

        session = {
            "started_at_utc": started_at_utc,
            "started_at_boottime_ns": started_at_boottime_ns,
            "duration_s": args.duration,
            "elapsed_s": elapsed_s,
            "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
            "port": args.port,
            "baudrate": args.baudrate,
            "source": args.source,
            "frames_recorded": frames_recorded,
            "serial_lines_recorded": serial_lines_recorded,
            "aborted": aborted,
            "abort_reason": abort_reason,
            "norm_schedule": (
                [{"factor": f, "hold_s": h} for f, h in args.norm_schedule]
                if args.norm_schedule is not None
                else None
            ),
            # Immer True, sobald --norm-schedule gesetzt ist: jeder Schreib-
            # zugriff (Precheck, jeder Schedule-Schritt, die Rueckstellung)
            # haelt den Messwertstrom vorher an (STOP+CLEAR) und startet ihn
            # danach neu (START) - siehe commands.jsonl fuer die genauen
            # pause_transmission/resume_transmission-Zeitpunkte je Schritt.
            "transmission_paused_during_writes": args.norm_schedule is not None,
            "commands_jsonl_event_count": serial_state.get("command_event_count"),
            "precheck": serial_state.get("precheck"),
            "schedule_steps": serial_state.get("schedule_steps"),
            "restore_verification": serial_state.get("restore_verification"),
            # Stall-Diagnostik OQ-40-Nachtrag 2026-09-23 - jetzt im
            # Aufnahmethread gemessen, unbeeinflusst von der Schreibseite
            # (siehe Moduldocstring "Erzeugen und Schreiben sind getrennte
            # Threads"): ein langsamer Schreiber darf hier nie mehr
            # faelschlich als Stall auftauchen.
            "max_loop_iteration_s": frame_acq_state.get("max_loop_iteration_s", 0.0),
            "stall_iteration_count": len(frame_acq_state.get("stall_iterations", [])),
            "stall_iterations": frame_acq_state.get("stall_iterations", []),
            "frames_dropped_queue_full": frame_acq_state.get("frames_dropped_queue_full", 0),
            "max_frame_queue_depth": frame_acq_state.get("max_frame_queue_depth", 0),
            "max_serial_queue_depth": serial_state.get("max_serial_queue_depth", 0),
            "acquisition_error": acquisition_error,
            # Task 2 (docs/superpowers/plans/2026-09-23-ernte-phase1.md):
            # angefordert = das geparste --scaler-crop-Argument, tatsaechlich =
            # der Wert aus den Metadaten des ersten Bildes ("ScalerCrop") -
            # nur im Kamerazweig ueberhaupt gesetzt, siehe _camera_frames.
            "scaler_crop_requested": list(args.scaler_crop) if args.scaler_crop is not None else None,
            "scaler_crop_actual": (
                list(frame_acq_state["scaler_crop_actual"])
                if frame_acq_state.get("scaler_crop_actual") is not None
                else None
            ),
            # Bug 2 (Orchestrator 2026-09-23): fuer das native Aufloesungs-
            # Gate in harvest-setup.py gebraucht (source_dot_column_px misst
            # im Output-Bild, ScalerCrop < Output-Groesse des Sensormodus
            # heisst der ISP skaliert hoch) - siehe _camera_frames-Docstring
            # fuer die picamera2-Fundstellen. Nur im Kamerazweig gesetzt.
            "sensor_mode_size": (
                list(frame_acq_state["sensor_mode_size"])
                if frame_acq_state.get("sensor_mode_size") is not None
                else None
            ),
            "sensor_array_size": (
                list(frame_acq_state["sensor_array_size"])
                if frame_acq_state.get("sensor_array_size") is not None
                else None
            ),
            # Streamstart-Budget (Scope-Erweiterung 2026-09-23): der Stand VOR
            # diesem Lauf (nicht danach) - nur im Kamerazweig gesetzt.
            "stream_starts_this_boot_before": (
                stream_budget_info["stream_starts_this_boot_before"] if stream_budget_info else None
            ),
            "stream_budget": stream_budget_info["stream_budget"] if stream_budget_info else None,
            "stream_budget_source": stream_budget_info["stream_budget_source"] if stream_budget_info else None,
        }
        session_json.write_text(json.dumps(session, indent=2, ensure_ascii=False, default=_json_default))

    if serial_state.get("read_error"):
        print(f"Warnung: serielles Lesen beendet mit Fehler: {serial_state['read_error']}", file=sys.stderr)
    if acquisition_error:
        print(f"FEHLER: Bildaufnahme: {acquisition_error}", file=sys.stderr)

    if serial_writer_state.get("count", 0) == 0:
        print(
            "WARNUNG: In der gesamten Aufzeichnung wurde kein einziges Telegramm "
            f"empfangen (Dauer={args.duration}s, Port={args.port!r}, Baudrate={args.baudrate}). "
            "serial.jsonl ist leer - das ist eine Meldung, kein stiller Erfolg.",
            file=sys.stderr,
        )
    if frame_acq_state.get("frames_dropped_queue_full", 0) > 0:
        print(
            f"WARNUNG: {frame_acq_state['frames_dropped_queue_full']} Bild(er) verworfen, weil die "
            f"Schreiber-Warteschlange voll war (--frame-queue-size {args.frame_queue_size}).",
            file=sys.stderr,
        )

    # Bug 1: Exit 4 (und das "FEHLER"-Wort statt "vollstaendig") ist speziell
    # der "keine Bilder"-Befund - ein Fehler NACH bereits aufgezeichneten
    # Bildern bleibt beim bisherigen Verhalten (Warnung, Exit 0), das ist ein
    # anderer Fall als der hier behandelte stille Leerlauf.
    no_frames_acquired = args.source == "camera" and frames_recorded == 0 and bool(acquisition_error)
    if aborted:
        status_word = "ABGEBROCHEN"
    elif no_frames_acquired:
        # Dieses Wort darf hier nie stehen, wenn keine Bilder angekommen
        # sind - "vollstaendig" hiesse stillschweigend erfolgreich.
        status_word = "FEHLER (keine Bilder, siehe acquisition_error)"
    else:
        status_word = "vollstaendig"
    print(
        f"Fertig: {frame_writer_state.get('frames_recorded', 0)} Bilder, "
        f"{serial_writer_state.get('count', 0)} Telegrammzeilen, "
        f"{status_word} -> {output_dir}"
    )
    if no_frames_acquired:
        return EXIT_NO_FRAMES_ACQUIRED
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
