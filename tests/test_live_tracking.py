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


def _interrupted_pipeline(lost_sequences):
    from dispread.detect.manual_roi import ManualRoiLocator

    class Locator(ManualRoiLocator):
        last_reason = "tracking_lost:test"

        def locate(self, frame):
            if frame.frame_sequence in lost_sequences:
                return ()
            return super().locate(frame)

    pipeline = _pipeline(Locator(QUAD))
    pipeline.gate = ReleaseGate(default_gate_config("dotmatrix", confirm_frames=2, expected_unit="mV/V"))
    return pipeline


def _second_frame(seq, image):
    return Frame(frame_sequence=seq, image=image, source_id="test",
                 capture_timestamp=Timestamp(value_ns=seq * 1_000_000_000,
                                             base=TimeBaseKind.V4L2_MONOTONIC))


def test_tracking_loss_interrupts_confirmation():
    pipeline = _interrupted_pipeline({2, 3, 4})
    image = embed("+ 1.2345 ")
    assert pipeline.process(_second_frame(1, image)).status is ValueStatus.TRANSITION
    for seq in (2, 3, 4):
        assert pipeline.process(_second_frame(seq, image)).status is ValueStatus.UNREADABLE
    resumed = pipeline.process(_second_frame(5, image))
    assert resumed.status is ValueStatus.TRANSITION
    assert resumed.frames_confirmed == 1 and resumed.confirmation_span_ns == 0
    confirmed = pipeline.process(_second_frame(6, image))
    assert confirmed.status is ValueStatus.VALID
    assert confirmed.frames_confirmed == 2 and confirmed.confirmation_span_ns == 1_000_000_000


def test_tracking_loss_preserves_last_valid_time_for_stale_rejection():
    pipeline = _interrupted_pipeline({3, 4, 5})
    image = embed("+ 1.2345 ")
    pipeline.process(_second_frame(1, image))
    assert pipeline.process(_second_frame(2, image)).status is ValueStatus.VALID
    for seq in (3, 4, 5):
        assert pipeline.process(_second_frame(seq, image)).status is ValueStatus.UNREADABLE
    rejected = pipeline.process(_second_frame(6, image * 0 + 200))
    assert rejected.status is ValueStatus.STALE and rejected.value is None


def test_confirmed_locator_uses_stored_regions_without_proposing(tmp_path, monkeypatch):
    import cv2
    from frame_tracking_helpers import reference_scene, tracking_block

    from dispread.live import frame_tracking
    from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, RegionProposal
    from dispread.live.tracking import ConfirmedRegionLocator

    image, quad = reference_scene()
    path = tmp_path / "still.png"
    cv2.imwrite(str(path), image)
    block = tracking_block(image, quad, path)
    block["proposal"]["regions"].reverse()
    proposal = RegionProposal.from_dict(block["proposal"])
    expected = FrameTracker(image, quad, proposal, FrameTrackingConfig())

    def forbidden(*args, **kwargs):
        raise AssertionError("Kein neuer Vorschlag beim Laufstart")

    monkeypatch.setattr(frame_tracking, "propose_regions", forbidden)
    locator = ConfirmedRegionLocator(image, quad, block)
    assert locator.locator_id == "rahmenbereiche_confirmed_quad"
    for seq, current in enumerate((image, image * 0, image), 1):
        candidates = locator.locate(_frame(seq, current))
        result = expected.update(current)
        assert locator.last_track == result
        if result.quad is None:
            assert candidates == ()
            assert locator.last_reason == f"tracking_lost:{result.reason}"
        else:
            assert candidates[0].quad == result.quad
            assert candidates[0].locator_id == locator.locator_id
            assert locator.last_reason is None
