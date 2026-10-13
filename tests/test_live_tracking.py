import numpy as np
from dotmatrix_helpers import LAYOUT, QUAD, embed, synthetic_reader

from dispread.frames import Frame
from dispread.live.tracking import TrackedQuadLocator
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.records import TimeBaseKind, Timestamp, ValueStatus
from dispread.validate import ReleaseGate, default_gate_config


class _Source:
    source_id = "test"


def _frame(seq, image):
    ts = Timestamp(value_ns=seq * 33_333_333, base=TimeBaseKind.V4L2_MONOTONIC)
    return Frame(frame_sequence=seq, image=image, capture_timestamp=ts, source_id="test")


def _pipeline(locator):
    gate = ReleaseGate(default_gate_config("dotmatrix", confirm_frames=1, expected_unit="mV/V"))
    config = PipelineConfig(profile_id="t", layout=LAYOUT, locate_every=0)
    return Pipeline(_Source(), locator, synthetic_reader(), gate, [], config)


def test_tracked_locator_reads_value_through_pipeline():
    reference = embed("+ 1.2345 ")
    record = _pipeline(TrackedQuadLocator(reference, QUAD)).process(_frame(1, embed("+ 1.2345 ")))
    assert record.status is ValueStatus.VALID
    assert record.value == 1.2345 and record.unit == "mV/V"


def test_lost_tracking_is_unreadable_with_reason():
    reference = embed("+ 1.2345 ")
    record = _pipeline(TrackedQuadLocator(reference, QUAD)).process(_frame(1, np.zeros_like(reference)))
    assert record.status is ValueStatus.UNREADABLE and record.value is None
    assert record.reject_reasons[0].startswith("tracking_lost:")


def test_dropped_frames_reach_the_trace():
    pipeline = _pipeline(TrackedQuadLocator(embed("+ 1.2345 "), QUAD))
    record = pipeline.process(_frame(1, embed("+ 1.2345 ")), dropped_frames=3)
    assert record.trace.dropped_frames == 3
