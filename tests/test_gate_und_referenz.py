"""Freigabelogik und die drei "stillen" Fehlermodi aus Konzept.md §7.

Diese Fehlermodi werden nicht "vermieden", sondern jeder bekommt einen Test,
der fehlschlaegt, wenn das System sie zeigt.
"""

from __future__ import annotations

import os

from dispread.detect.manual_roi import ManualRoiLocator, quad_from_box
from dispread.frames import open_source
from dispread.layout import DisplayLayout
from dispread.ocr import GlyphEvidence, ReadResult
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.records import ValueStatus
from dispread.sink.jsonl import JsonlSink
from dispread.validate import GateConfig, ReleaseGate

SECOND = 1_000_000_000


def _read_result(value: float | None, **overrides) -> ReadResult:
    base = dict(
        raw_text="-012.50" if value is not None else "?????",
        value=value,
        sign_detected=True,
        sign_region_readable=True,
        decimal_point_detected=True,
        decimal_point_index=2,
        unit_text="N",
        status_flags=frozenset(),
        glyphs=(GlyphEvidence(text="0", confidence=0.9, margin=0.9),),
        backend_id="fake",
        backend_version="1",
        diagnostics={"contrast": 0.4, "min_margin": 0.9, "unreadable_cells": 0},
    )
    base.update(overrides)
    return ReadResult(**base)  # type: ignore[arg-type]


# --- Fehlermodus 1: Altwert laeuft unmarkiert weiter ----------------------


def test_nach_verlust_wird_der_wert_veraltet_nicht_weitergefuehrt():
    """Konzept.md §7: alte Werte duerfen nicht unmarkiert weiterlaufen."""
    gate = ReleaseGate(GateConfig(stale_after_ns=SECOND // 2))

    first = gate.evaluate(_read_result(-12.5), capture_ns=0)
    assert first.status is ValueStatus.VALID

    # Anzeige wird unlesbar: zunaechst UNREADABLE ...
    soon = gate.evaluate(_read_result(None, diagnostics={"contrast": 0.0}), capture_ns=SECOND // 10)
    assert soon.status is ValueStatus.UNREADABLE

    # ... und nach Ablauf der Frist zwingend STALE.
    later = gate.evaluate(_read_result(None, diagnostics={"contrast": 0.0}), capture_ns=2 * SECOND)
    assert later.status is ValueStatus.STALE
    assert later.reject_reasons


def test_verdeckte_anzeige_liefert_keinen_gueltigen_datensatz(tmp_path):
    """Ende-zu-Ende: Anzeige nicht lokalisierbar -> nie VALID."""

    class LostLocator:
        locator_id = "lost"

        def locate(self, frame):
            del frame
            return ()

    src = open_source("synthetic://seven-seg?count=5")
    pipeline = Pipeline(
        source=src,
        locator=LostLocator(),
        reader=SevenSegmentReader(),
        gate=ReleaseGate(),
        sinks=[JsonlSink(tmp_path / "v.jsonl")],
        config=PipelineConfig(profile_id="t", layout=DisplayLayout()),
    )
    statuses = [r.status for r in pipeline.run()]
    assert statuses
    assert ValueStatus.VALID not in statuses
    assert all(s in (ValueStatus.UNREADABLE, ValueStatus.STALE) for s in statuses)


# --- Fehlermodus 2: Plausibilitaetsregeln glaetten echte Spruenge ---------


def test_echte_spruenge_werden_nicht_geglaettet():
    """Konzept.md §7: reale Messwertspruenge duerfen nicht verschwinden.

    Der Sprung von 1.0 auf 500.0 muss unveraendert durchkommen - keine
    Mittelung, keine Begrenzung, keine Verzoegerung ausser der dokumentierten
    Mehrbildbestaetigung.
    """
    gate = ReleaseGate(GateConfig(confirm_frames=1))
    values = [1.0, 1.0, 500.0, 500.0, -500.0, 0.0]
    out = []
    for i, v in enumerate(values):
        decision = gate.evaluate(_read_result(v), capture_ns=i * SECOND // 10)
        assert decision.status is ValueStatus.VALID
        out.append(v)
    assert out == values


def test_mehrbildbestaetigung_meldet_ihre_zeitspanne():
    """Die Verzoegerung der Bestaetigung muss messbar im Datensatz stehen."""
    gate = ReleaseGate(GateConfig(confirm_frames=3))
    gate.evaluate(_read_result(5.0), capture_ns=0)
    gate.evaluate(_read_result(5.0), capture_ns=SECOND // 10)
    final = gate.evaluate(_read_result(5.0), capture_ns=2 * SECOND // 10)
    assert final.status is ValueStatus.VALID
    assert final.frames_confirmed == 3
    assert final.confirmation_span_ns == 2 * SECOND // 10


# --- Fehlermodus 3: Referenzwert korrigiert den DUT-Wert ------------------


def test_referenzwert_kann_die_erkennung_nicht_beeinflussen(tmp_path):
    """Konzept.md §7: die Erkennung darf den Referenzwert nicht benutzen.

    Derselbe Lauf zweimal, einmal mit einem absichtlich um 20 % verfaelschten
    "Referenzwert" in den Frame-Metadaten. Die erzeugten Datensaetze muessen
    identisch sein - bis auf die Verarbeitungszeiten, die naturgemaess
    schwanken.
    """

    def run(reference_factor: float) -> list[tuple]:
        src = open_source("synthetic://seven-seg?count=12")
        src.open()
        probe = next(iter(src.frames()))
        x, y, w, h = probe.raw_metadata["digit_area"]
        src.close()

        pipeline = Pipeline(
            source=src,
            locator=ManualRoiLocator(quad_from_box(x, y, w, h)),
            reader=SevenSegmentReader(),
            gate=ReleaseGate(GateConfig(expected_unit="N")),
            sinks=[JsonlSink(tmp_path / f"v{reference_factor}.jsonl")],
            config=PipelineConfig(profile_id="t", layout=src.layout),
        )
        out = []
        src.open()
        for sink in pipeline.sinks:
            sink.open()
        try:
            for frame in src.frames():
                # Der "Referenzwert" liegt in den Metadaten und ist verfaelscht.
                truth = frame.raw_metadata["ground_truth"]["value"]
                frame.raw_metadata["reference_value"] = truth * reference_factor
                record = pipeline.process(frame)
                out.append((record.frame_sequence, record.value, record.unit, record.status, record.raw_text))
        finally:
            for sink in pipeline.sinks:
                sink.close()
            src.close()
        return out

    assert run(1.0) == run(1.2)


def test_leser_bekommt_den_referenzwert_nicht_als_parameter():
    """Strukturelle Sperre: die Signatur laesst ihn nicht zu."""
    import inspect

    params = set(inspect.signature(SevenSegmentReader.read).parameters)
    assert params == {"self", "crop", "layout"}

    gate_params = set(inspect.signature(ReleaseGate.evaluate).parameters)
    assert gate_params == {"self", "read", "capture_ns"}


# --- Eigenstaendige Kriterien fuer Vorzeichen, Dezimalpunkt, Einheit ------


def test_unlesbarer_vorzeichenbereich_fuehrt_zur_ablehnung():
    """Nicht sichtbares Vorzeichen darf nicht als "positiv" gelten."""
    gate = ReleaseGate()
    decision = gate.evaluate(_read_result(12.5, sign_region_readable=False), capture_ns=0)
    assert decision.status is not ValueStatus.VALID
    assert "sign_region_unreadable" in decision.reject_reasons


def test_unbekannter_dezimalpunkt_fuehrt_zur_ablehnung():
    gate = ReleaseGate()
    decision = gate.evaluate(_read_result(12.5, decimal_point_detected=False), capture_ns=0)
    assert "decimal_point_unknown" in decision.reject_reasons


def test_falsche_einheit_fuehrt_zur_ablehnung():
    gate = ReleaseGate(GateConfig(expected_unit="N"))
    decision = gate.evaluate(_read_result(12.5, unit_text="mV/V"), capture_ns=0)
    assert any(r.startswith("unit_mismatch") for r in decision.reject_reasons)


def test_betriebszustand_blockiert_den_zahlenwert():
    gate = ReleaseGate()
    decision = gate.evaluate(_read_result(None, status_flags=frozenset({"overflow"})), capture_ns=0)
    assert decision.status is ValueStatus.UNREADABLE
    assert "state:overflow" in decision.reject_reasons


# --- Serielle Ausgabe ueber ein pty --------------------------------------


def test_telegramme_erreichen_die_gegenstelle():
    """Ohne socat: os.openpty() aus der stdlib genuegt fuer den Nachweis."""
    from dispread.records import InvalidValuePolicy, TimeBaseKind, Timestamp, ValueRecord
    from dispread.sink.protocol.ascii_csv import AsciiCsvFormatter
    from dispread.sink.serial_out import SerialSink

    master, slave = os.openpty()
    try:
        formatter = AsciiCsvFormatter(invalid_policy=InvalidValuePolicy.STATUS_FLAG)
        sink = SerialSink(os.ttyname(slave), formatter)
        sink.open()
        record = ValueRecord(
            frame_sequence=1,
            capture_timestamp=Timestamp(value_ns=42, base=TimeBaseKind.SENSOR_BOOTTIME),
            value=-12.5,
            unit="N",
            status=ValueStatus.VALID,
            confidence=0.9,
            profile_id="p",
            trigger_sequence=None,
            result_timestamp=None,
        )
        receipt = sink.emit(record)
        sink.close()

        assert receipt.wire_bytes is not None
        assert not receipt.omitted
        os.set_blocking(master, False)
        wire = os.read(master, 4096).decode("ascii")
        assert "-12.500" in wire
        assert "valid" in wire
        # Die Zeitbasis muss mitgehen: ein Zeitstempel ohne Zeitbasis ist
        # nach Konzept.md §6 keine verwertbare Angabe.
        assert "sensor_boottime" in wire
    finally:
        os.close(master)
        os.close(slave)


def test_ausgelassener_datensatz_wird_als_ausgelassen_belegt():
    """Eine Luecke im Datenstrom darf nicht als Uebertragungsfehler gelten."""
    from dispread.records import InvalidValuePolicy, TimeBaseKind, Timestamp, ValueRecord
    from dispread.sink.protocol.ascii_csv import AsciiCsvFormatter
    from dispread.sink.serial_out import SerialSink

    master, slave = os.openpty()
    try:
        sink = SerialSink(os.ttyname(slave), AsciiCsvFormatter(invalid_policy=InvalidValuePolicy.OMIT_RECORD))
        sink.open()
        receipt = sink.emit(
            ValueRecord(
                frame_sequence=1,
                capture_timestamp=Timestamp(value_ns=1, base=TimeBaseKind.SENSOR_BOOTTIME),
                value=None,
                unit=None,
                status=ValueStatus.STALE,
                confidence=0.0,
                profile_id="p",
                trigger_sequence=None,
                result_timestamp=None,
                reject_reasons=("stale",),
            )
        )
        sink.close()
        assert receipt.omitted
        assert receipt.wire_bytes is None
        assert sink.health().omitted == 1
    finally:
        os.close(master)
        os.close(slave)
