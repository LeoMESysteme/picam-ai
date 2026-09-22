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
"""

from __future__ import annotations

import argparse
import json
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

DEFAULT_OUTPUT_ROOT = Path("var/diagnostics")
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 38400
DEFAULT_SYNTHETIC_URI = "synthetic://seven-seg"
SERIAL_READ_TIMEOUT_S = 0.5
JOIN_TIMEOUT_S = 5.0


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
    args = parser.parse_args(argv)
    _check_camera_size(parser, args)
    return args


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


# --- Serieller Strom, eigener Thread, nur lesen -----------------------------


def _serial_worker(
    port: str,
    baudrate: int,
    out_path: Path,
    stop_event: threading.Event,
    ready_event: threading.Event,
    state: dict[str, Any],
) -> None:
    """Liest zeilenweise, sendet nichts. Signalisiert `ready_event`, sobald
    der Port entweder offen ist oder das Oeffnen endgueltig fehlgeschlagen
    ist - der Aufrufer wartet darauf, bevor er die Bildaufnahme startet."""
    import serial

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
    ready_event.set()
    count = 0
    try:
        with open(out_path, "a", encoding="utf-8") as f:
            while not stop_event.is_set():
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
                f.write(json.dumps({"t_boot": t_boot, "text": text}, ensure_ascii=False) + "\n")
                f.flush()
                count += 1
    finally:
        try:
            ser.close()
        except Exception:  # noqa: BLE001 - Aufraeumen, kein neuer Fehler beim Beenden
            pass
        state["count"] = count


# --- Bildstrom ---------------------------------------------------------------


def _synthetic_frames(uri: str):
    """`Frame`-Objekte aus `dispread.frames.open_source`, roh durchgereicht."""
    source = open_source(uri)
    source.open()
    try:
        for frame in source.frames():
            yield frame.image, frame.capture_timestamp.to_dict()
    finally:
        source.close()


def _camera_frames(size: tuple[int, int], fps: float):
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
    """
    from picamera2 import Picamera2

    camera = Picamera2()
    try:
        config = camera.create_video_configuration(
            main={"size": size, "format": "RGB888"},
            controls={"FrameRate": fps} if fps > 0 else {},
            queue=False,
        )
        camera.configure(config)
        camera.start(show_preview=False)
        while True:
            request = camera.capture_request(wait=2.0)
            try:
                image = request.make_array("main").copy()
                raw_metadata = request.get_metadata()
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
            yield image, timestamp.to_dict()
    finally:
        camera.stop()


def _frame_generator(args: argparse.Namespace):
    if args.source == "synthetic":
        yield from _synthetic_frames(args.synthetic_uri)
    else:
        w, _, h = args.camera_size.partition("x")
        yield from _camera_frames((int(w), int(h)), args.frame_rate)


# --- Hauptablauf --------------------------------------------------------------


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"nicht serialisierbar: {type(value)!r}")


def run(args: argparse.Namespace) -> int:
    output_dir = args.output or (DEFAULT_OUTPUT_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S"))
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    serial_jsonl = output_dir / "serial.jsonl"
    frames_jsonl = output_dir / "frames.jsonl"
    session_json = output_dir / "session.json"

    started_at_utc = datetime.now(UTC).isoformat()
    started_at_boottime_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)

    stop_event = threading.Event()
    ready_event = threading.Event()
    serial_state: dict[str, Any] = {"count": 0, "open_error": None}

    serial_thread = threading.Thread(
        target=_serial_worker,
        args=(args.port, args.baudrate, serial_jsonl, stop_event, ready_event, serial_state),
        name="serial-reader",
        daemon=True,
    )
    serial_thread.start()

    if not ready_event.wait(timeout=JOIN_TIMEOUT_S):
        print(
            f"Fehler: serieller Lesethread meldete sich nicht innerhalb {JOIN_TIMEOUT_S}s",
            file=sys.stderr,
        )
        stop_event.set()
        return 1
    if serial_state["open_error"]:
        print(
            f"Fehler: serieller Port {args.port!r} konnte nicht geoeffnet werden: "
            f"{serial_state['open_error']}",
            file=sys.stderr,
        )
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        return 1

    frame_period_s = 1.0 / args.frame_rate if args.frame_rate > 0 else 0.0
    ext = "png" if args.image_format == "png" else "jpg"

    frames_recorded = 0
    aborted = False
    abort_reason: str | None = None
    start_mono = time.monotonic()
    next_due = start_mono

    try:
        with open(frames_jsonl, "a", encoding="utf-8") as f_frames:
            for image, timestamp_dict in _frame_generator(args):
                now = time.monotonic()
                if now - start_mono >= args.duration:
                    break
                frames_recorded += 1
                filename = f"frame_{frames_recorded:06d}.{ext}"
                cv2.imwrite(str(frames_dir / filename), image)
                entry = {
                    "file": filename,
                    "frame_sequence": frames_recorded,
                    "capture_timestamp": timestamp_dict,
                }
                f_frames.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f_frames.flush()

                if frame_period_s > 0:
                    next_due += frame_period_s
                    sleep_for = next_due - time.monotonic()
                    if sleep_for > 0:
                        time.sleep(sleep_for)
    except KeyboardInterrupt:
        aborted = True
        abort_reason = "KeyboardInterrupt (Ctrl-C)"
        print("\nAbbruch (Ctrl-C) - schreibe bereits aufgezeichnete Daten vollstaendig ab.", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - Sitzung trotzdem sauber abschliessen
        aborted = True
        abort_reason = f"{type(exc).__name__}: {exc}"
        traceback.print_exc(file=sys.stderr)
    finally:
        elapsed_s = time.monotonic() - start_mono
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)

        serial_lines_recorded = serial_state.get("count", 0)
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
        }
        session_json.write_text(json.dumps(session, indent=2, ensure_ascii=False, default=_json_default))

    if serial_state.get("read_error"):
        print(f"Warnung: serielles Lesen beendet mit Fehler: {serial_state['read_error']}", file=sys.stderr)

    if serial_state.get("count", 0) == 0:
        print(
            "WARNUNG: In der gesamten Aufzeichnung wurde kein einziges Telegramm "
            f"empfangen (Dauer={args.duration}s, Port={args.port!r}, Baudrate={args.baudrate}). "
            "serial.jsonl ist leer - das ist eine Meldung, kein stiller Erfolg.",
            file=sys.stderr,
        )

    print(
        f"Fertig: {frames_recorded} Bilder, {serial_state.get('count', 0)} Telegrammzeilen, "
        f"{'ABGEBROCHEN' if aborted else 'vollstaendig'} -> {output_dir}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
