#!/usr/bin/env python3
"""Die gesamte Kette ohne jede Hardware.

Zweck:    Nachweis, dass die Verarbeitungskette aus Konzept.md §3 vollstaendig
          ist: Bildquelle -> Lokalisierung -> Entzerrung -> Werterkennung ->
          Freigabe -> ValueRecord -> JSONL + serielles Telegramm.
Hardware: nein. Bildquelle ist der synthetische Generator, die serielle
          Gegenstelle ein pty-Paar aus os.openpty() - kein socat noetig.
Ausgabe:  var/examples/16_end_to_end/values.jsonl, telegrams.txt, report.json
Referenz: Konzept.md §3 (Kette), §7 (Freigabe), §8 (Datensatz)

Dies ist das Abnahmeartefakt fuer Phase P0 (docs/ROADMAP.md).

Wichtig zur Deutung: die Bildquelle ist synthetisch, die Zeitbasis also
SYNTHETIC. Aus den hier gemessenen Zeiten darf KEINE Aussage ueber reale
Latenzen abgeleitet werden - Frame.is_time_bearing ist False. Der Bericht
weist das explizit aus.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dispread import paths
from dispread.detect.manual_roi import ManualRoiLocator, quad_from_box
from dispread.frames import open_source
from dispread.layout import DisplayLayout
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.records import InvalidValuePolicy, ValueStatus
from dispread.sink.jsonl import JsonlSink
from dispread.sink.protocol.ascii_csv import AsciiCsvFormatter
from dispread.sink.serial_out import SerialSink


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=40, help="Anzahl Frames")
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--blur", type=float, default=0.0)
    parser.add_argument("--glare", type=float, default=0.0)
    parser.add_argument("--confirm-frames", type=int, default=1, help="Mehrbildbestaetigung")
    parser.add_argument("--out", type=Path, default=paths.EXAMPLES_OUT / "16_end_to_end")
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    # --- Bildquelle -------------------------------------------------------
    uri = (
        f"synthetic://seven-seg?digits=5&decimals=2&unit=N"
        f"&count={args.count}&noise={args.noise}&blur={args.blur}&glare={args.glare}"
    )
    source = open_source(uri)
    layout: DisplayLayout = source.layout  # type: ignore[attr-defined]

    # --- Bestaetigte ROI --------------------------------------------------
    # Im Betrieb kommt sie aus dem Profil, das der Bediener nach Konzept.md §4
    # einmalig bestaetigt. Hier nimmt sie der Generator vom ersten Frame.
    source.open()
    probe = next(iter(source.frames()))
    x, y, w, h = probe.raw_metadata["digit_area"]
    source.close()
    locator = ManualRoiLocator(quad_from_box(x, y, w, h), role_hint="main", confirmed_by="example-16")

    # --- Serielle Gegenstelle: pty-Paar aus der stdlib --------------------
    master_fd, slave_fd = os.openpty()
    slave_name = os.ttyname(slave_fd)
    formatter = AsciiCsvFormatter(invalid_policy=InvalidValuePolicy.STATUS_FLAG)

    from dispread.validate import GateConfig, ReleaseGate

    pipeline = Pipeline(
        source=source,
        locator=locator,
        reader=SevenSegmentReader(),
        gate=ReleaseGate(GateConfig(confirm_frames=args.confirm_frames, expected_unit=layout.unit)),
        sinks=[
            JsonlSink(out / "values.jsonl"),
            SerialSink(slave_name, formatter, baudrate=115200),
        ],
        config=PipelineConfig(profile_id="synthetic-demo", layout=layout),
    )

    # values.jsonl frisch aufbauen, damit Wiederholungen nicht anwachsen.
    (out / "values.jsonl").unlink(missing_ok=True)

    correct = wrong = rejected = 0
    ground_truth: dict[int, float] = {}
    records = []
    for frame_value in _run_with_truth(pipeline, ground_truth):
        record, truth = frame_value
        records.append(record)
        if record.status is ValueStatus.VALID:
            if record.value == truth:
                correct += 1
            else:
                # Der gefaehrliche Fall: als gueltig ausgegeben, aber falsch.
                wrong += 1
        else:
            rejected += 1

    # --- Telegramme von der Gegenstelle lesen -----------------------------
    os.set_blocking(master_fd, False)
    try:
        wire = os.read(master_fd, 1 << 20)
    except BlockingIOError:
        wire = b""
    (out / "telegrams.txt").write_bytes(wire)
    os.close(master_fd)
    os.close(slave_fd)

    telegram_lines = [line for line in wire.decode("ascii", "replace").splitlines() if line]

    # --- Latenzen ---------------------------------------------------------
    durations = [r.trace.stage_durations_us() for r in records if r.trace]
    stages = sorted({k for d in durations for k in d})
    latency = {}
    for stage in stages:
        values = sorted(d[stage] for d in durations if stage in d)
        if values:
            latency[stage] = {
                "p50_us": round(values[len(values) // 2], 1),
                "p95_us": round(values[int(len(values) * 0.95)], 1),
                "max_us": round(values[-1], 1),
            }

    report = {
        "source": source.describe(),
        # Der entscheidende Vorbehalt, maschinenlesbar im Bericht:
        "timing_is_meaningful": bool(records and records[0].capture_timestamp.base.carries_time_information),
        "formatter": {
            "format_id": formatter.capabilities.format_id,
            "provisional": formatter.capabilities.provisional,
            "carries_capture_timestamp": formatter.capabilities.carries_capture_timestamp,
        },
        "counts": {
            "frames": pipeline.stats.frames,
            "by_status": pipeline.stats.by_status,
            "correct": correct,
            "silently_wrong": wrong,
            "rejected": rejected,
            "telegrams_on_wire": len(telegram_lines),
        },
        # Sink-Gesundheit gehoert in den Bericht: ein Schreibfehler oder ein
        # bewusst ausgelassener Datensatz darf nicht stillschweigend als
        # "uebertragen" gelten.
        "sinks": [
            {
                "type": type(sink).__name__,
                "sent": sink.health().sent,
                "omitted": sink.health().omitted,
                "errors": sink.health().errors,
                "last_error": sink.health().last_error,
            }
            for sink in pipeline.sinks
        ],
        "processing_latency": latency,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Ausgabe ----------------------------------------------------------
    print(f"Quelle:      {uri}")
    print(f"Zeitbasis:   {source.describe()['timebase']}  "
          f"(traegt Zeitaussage: {report['timing_is_meaningful']})")
    print(f"Frames:      {pipeline.stats.frames}")
    print(f"Status:      {pipeline.stats.by_status}")
    print(f"korrekt:     {correct}")
    print(f"abgelehnt:   {rejected}")
    print(f"STILL FALSCH:{wrong}   <- als gueltig ausgegeben, aber falsch")
    print(f"Telegramme:  {len(telegram_lines)} auf der Leitung"
          f"  (Format {formatter.capabilities.format_id}, provisorisch)")
    for entry in report["sinks"]:
        note = f"  FEHLER: {entry['last_error']}" if entry["errors"] else ""
        print(f"  {entry['type']:12s} gesendet={entry['sent']:>4} "
              f"ausgelassen={entry['omitted']:>3} Fehler={entry['errors']:>3}{note}")
    if telegram_lines:
        print(f"  erstes: {telegram_lines[0]}")
        print(f"  letztes: {telegram_lines[-1]}")
    print()
    print("Verarbeitungsdauer je Stufe (Mikrosekunden):")
    for stage, stats in latency.items():
        print(f"  {stage:8s} p50={stats['p50_us']:>9.1f}  p95={stats['p95_us']:>9.1f}  max={stats['max_us']:>9.1f}")
    print()
    print(f"Artefakte in {out}")

    # Stille Fehlablesungen sind der einzige Fall, der diesen Lauf
    # fehlschlagen laesst. Ablehnungen sind kein Fehler.
    return 1 if wrong else 0


def _run_with_truth(pipeline: Pipeline, truth_out: dict[int, float]):
    """Datensaetze samt Sollwert liefern.

    Der Sollwert wird ausserhalb der Pipeline gefuehrt. Die Pipeline selbst
    sieht ihn nie - genau das verlangt Konzept.md §7.
    """
    source = pipeline.source
    source.open()
    for sink in pipeline.sinks:
        sink.open()
    try:
        for frame in source.frames():
            truth = frame.raw_metadata["ground_truth"]["value"]
            truth_out[frame.frame_sequence] = truth
            record = pipeline.process(frame)
            pipeline.stats.frames += 1
            pipeline.stats.note(record.status)
            for sink in pipeline.sinks:
                pipeline.stats.receipts.append(sink.emit(record))
            yield record, truth
    finally:
        for sink in pipeline.sinks:
            sink.close()
        source.close()


if __name__ == "__main__":
    sys.exit(main())
