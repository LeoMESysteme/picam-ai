"""Der interne Datensatz und seine Invarianten (Konzept.md §7, §8)."""

from __future__ import annotations

import pytest

from dispread.records import (
    PipelineTrace,
    TimeBaseKind,
    Timestamp,
    TimestampSemantics,
    ValueRecord,
    ValueStatus,
)


def _record(**overrides) -> ValueRecord:
    base = dict(
        frame_sequence=7,
        capture_timestamp=Timestamp(
            value_ns=123_456_789,
            base=TimeBaseKind.SENSOR_BOOTTIME,
            semantics=TimestampSemantics.UNKNOWN,
            uncertainty_ns=None,
        ),
        value=-12.5,
        unit="N",
        status=ValueStatus.VALID,
        confidence=0.8,
        profile_id="gsv-2asd",
        trigger_sequence=None,
        result_timestamp=Timestamp(value_ns=123_500_000, base=TimeBaseKind.SENSOR_BOOTTIME),
        raw_text="-012.50",
        trace=PipelineTrace(t_dequeue_ns=1, t_record_built_ns=2000),
        component_versions={"dispread": "0.1.0.dev0"},
    )
    base.update(overrides)
    return ValueRecord(**base)  # type: ignore[arg-type]


def test_roundtrip_ist_verlustfrei():
    """Abnahmekriterium P0: to_dict/from_dict verliert nichts."""
    original = _record()
    assert ValueRecord.from_dict(original.to_dict()) == original


def test_stale_darf_keinen_zahlenwert_fuehren():
    """Konzept.md §7: alte Werte laufen nicht unmarkiert weiter.

    Ein STALE-Datensatz mit Zahlenwert waere genau der verbotene Fall - der
    Konstruktor laesst ihn nicht entstehen.
    """
    with pytest.raises(ValueError, match="veralteter oder"):
        _record(status=ValueStatus.STALE, value=-12.5, reject_reasons=("stale",))


def test_unreadable_darf_keinen_zahlenwert_fuehren():
    with pytest.raises(ValueError, match="veralteter oder"):
        _record(status=ValueStatus.UNREADABLE, value=1.0, reject_reasons=("low_contrast",))


def test_ablehnung_braucht_einen_grund():
    """Ohne Begruendung ist eine Ablehnung nicht nachvollziehbar."""
    with pytest.raises(ValueError, match="ohne reject_reasons"):
        _record(status=ValueStatus.UNREADABLE, value=None, reject_reasons=())


def test_stale_ohne_wert_ist_erlaubt():
    record = _record(status=ValueStatus.STALE, value=None, unit=None, reject_reasons=("stale",))
    assert record.status is ValueStatus.STALE
    assert record.value is None


def test_zeitbasis_sagt_ob_zeitaussage_moeglich_ist():
    """Synthetische und Datei-Zeitstempel tragen keine Zeitaussage."""
    assert TimeBaseKind.SENSOR_BOOTTIME.carries_time_information
    assert TimeBaseKind.REPLAY_RECORDED.carries_time_information
    assert not TimeBaseKind.SYNTHETIC.carries_time_information
    assert not TimeBaseKind.FILE_MTIME.carries_time_information


def test_unbekannte_unsicherheit_ist_none_nicht_null():
    """Eine unbekannte Unsicherheit als 0 auszugeben waere eine Falschaussage."""
    ts = Timestamp(value_ns=1, base=TimeBaseKind.SENSOR_BOOTTIME)
    assert ts.uncertainty_ns is None
    assert ts.semantics is TimestampSemantics.UNKNOWN


def test_stufendauern_werden_berechnet():
    trace = PipelineTrace(
        t_dequeue_ns=0,
        t_locate_done_ns=1_000,
        t_rectify_done_ns=3_000,
        t_read_done_ns=8_000,
        t_gate_done_ns=9_000,
        t_record_built_ns=10_000,
    )
    d = trace.stage_durations_us()
    assert d["locate"] == 1.0
    assert d["read"] == 5.0
    assert d["total"] == 10.0
