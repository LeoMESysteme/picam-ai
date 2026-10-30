"""Der interne Datensatz und seine Invarianten (Konzept.md §7, §8)."""

from __future__ import annotations

from dataclasses import MISSING, fields

import pytest

from dispread.records import (
    PipelineTrace,
    TimeBaseKind,
    Timestamp,
    TimestampSemantics,
    ValueRecord,
    ValueStatus,
    to_boottime_ns,
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


@pytest.mark.parametrize("base", [
    "sensor_boottime", "v4l2_monotonic", "synthetic", "file_mtime", "replay_recorded", "host_monotonic",
])
def test_ergebniszeitbasis_bleibt_beim_audit_roundtrip_erhalten(base):
    data = _record().to_dict()
    data["result_timestamp"]["base"] = base
    assert ValueRecord.from_dict(data).to_dict() == data


def test_genau_die_neun_konzeptfelder_bleiben_pflicht():
    required = {f.name for f in fields(ValueRecord) if f.default is MISSING and f.default_factory is MISSING}
    assert required == {
        "frame_sequence", "capture_timestamp", "value", "unit", "status", "confidence",
        "profile_id", "trigger_sequence", "result_timestamp",
    }


def test_now_monotonic_bezeichnet_die_host_uhr(monkeypatch):
    monkeypatch.setattr("dispread.records.time.monotonic_ns", lambda: 987_654_321)
    timestamp = Timestamp.now_monotonic()
    assert timestamp.value_ns == 987_654_321
    assert timestamp.base.value == "host_monotonic"
    assert timestamp.semantics is TimestampSemantics.HOST_DEQUEUE
    assert timestamp.uncertainty_ns is None


def test_host_monotonic_traegt_zeitaussage():
    assert TimeBaseKind("host_monotonic").carries_time_information


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


def _ts(value_ns, base):
    return {"value_ns": value_ns, "base": base, "semantics": "unknown", "uncertainty_ns": None}


def test_v4l2_monotonic_zaehlt_als_zeitbehaftet():
    assert TimeBaseKind("v4l2_monotonic") is TimeBaseKind.V4L2_MONOTONIC
    assert TimeBaseKind.V4L2_MONOTONIC.carries_time_information


def test_sensor_boottime_bleibt_unveraendert_auch_ohne_session():
    assert to_boottime_ns(_ts(123, "sensor_boottime"), None) == 123


@pytest.mark.parametrize("base", ["v4l2_monotonic", "host_monotonic"])
def test_monotonic_wird_mit_startversatz_umgerechnet(base):
    session = {"clock_offset_boottime_minus_monotonic_ns": {"start": 5_000, "end": 5_400}}
    assert to_boottime_ns(_ts(1_000_000, base), session) == 1_005_000


@pytest.mark.parametrize("base", ["v4l2_monotonic", "host_monotonic"])
@pytest.mark.parametrize("session", [
    None, {}, {"clock_offset_boottime_minus_monotonic_ns": {"start": 0}},
    {"clock_offset_boottime_minus_monotonic_ns": {"end": 0}},
])
def test_monotonic_ohne_versatz_wird_abgelehnt(base, session):
    with pytest.raises(ValueError, match="clock_offset"):
        to_boottime_ns(_ts(1, base), session)


@pytest.mark.parametrize("base", ["v4l2_monotonic", "host_monotonic"])
def test_suspend_zwischen_start_und_ende_wird_abgelehnt(base):
    session = {"clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 1_000_001}}
    with pytest.raises(ValueError, match="Suspend"):
        to_boottime_ns(_ts(1, base), session)


@pytest.mark.parametrize("base", ["synthetic", "file_mtime", "replay_recorded", "quatsch"])
def test_andere_basen_werden_abgelehnt(base):
    with pytest.raises(ValueError, match="Zeitbasis"):
        to_boottime_ns(_ts(1, base), {"clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 0}})


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
