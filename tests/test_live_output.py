"""Live output lifecycle: audit remains authoritative before any publication."""

import json

import pytest
from dotmatrix_helpers import embed
from test_live_service import FakeOwner
from test_live_session import _session

from dispread.live.service import LiveError, LiveService


class Publisher:
    def __init__(self, config, out_dir):
        self.config, self.out_dir = config, out_dir
        self.started = self.stopped = False
        self.records = []

    def start(self):
        self.started = True

    def publish(self, record):
        # This fails if publication precedes the mandatory audit.
        lines = (self.out_dir / "records.jsonl").read_text().splitlines()
        assert json.loads(lines[-1]) == record.to_dict()
        self.records.append(record)

    def stop(self):
        self.stopped = True

    def status(self):
        return {"transport": self.config.transport, "state": "disconnected", "release_block": "Windows-Abnahme fehlt"}

    def metadata(self):
        return {"config": self.config.to_dict(), "provisional": True}


def test_publish_follows_audit_and_stop_closes_output(tmp_path):
    from dispread.gsv_transport import OutputConfig

    session = _session(tmp_path, [embed("+ 1.2345 "), embed("+ 1.2345 ")],
                       output=OutputConfig.from_dict({"transport": "tcp"}), output_factory=Publisher)
    session.start()
    assert session._output.started
    session.step()
    session.step()
    assert len(session._output.records) == 2
    assert session.output_status()["state"] == "disconnected"
    assert session.end_reason is None
    assert session._sink.max_bytes == 0
    session.stop()
    assert session._output.stopped
    data = json.loads(session.session_path.read_text())
    assert data["output"]["provisional"] is True
    assert data["output"]["status"]["state"] == "disconnected"


def test_failed_audit_does_not_publish_record(tmp_path, monkeypatch):
    from dispread.gsv_transport import OutputConfig
    from dispread.live.session import AuditFailed
    from dispread.records import TxReceipt

    session = _session(tmp_path, [embed("+ 1.2345 ")],
                       output=OutputConfig.from_dict({"transport": "tcp"}), output_factory=Publisher)
    session.start()
    monkeypatch.setattr(session._sink, "emit", lambda record: TxReceipt(record.frame_sequence, 1, "jsonl", None, 0, None))
    with pytest.raises(AuditFailed):
        session.step()
    assert session._output.records == []
    session.stop()
    assert session._output.stopped


def test_test_override_refuses_external_output_before_creating_run(tmp_path):
    service = LiveService(FakeOwner(), tmp_path)
    service._state = "confirmed"
    service._profile_path = tmp_path / "profile.json"
    service._run_block = "Gegenlesen fehlt"
    with pytest.raises(LiveError, match="Testlauf"):
        service.start_run(test_override=True, reference=False, output={"transport": "tcp"})
    assert not list(tmp_path.glob("run-*"))


def test_invalid_output_is_live_error_before_creating_run(tmp_path):
    service = LiveService(FakeOwner(), tmp_path)
    with pytest.raises(LiveError):
        service.start_run(output={"transport": "unknown"})
    assert not list(tmp_path.glob("run-*"))


def test_late_start_metadata_failure_closes_audit_and_output(tmp_path, monkeypatch):
    from dispread.gsv_transport import OutputConfig

    session = _session(tmp_path, [], output=OutputConfig.from_dict({"transport": "tcp"}),
                       output_factory=Publisher)
    write = session._write_session
    calls = []

    def fail_second_write(*, ended):
        calls.append(ended)
        if len(calls) == 2:
            raise OSError("Metadaten voll")
        return write(ended=ended)

    monkeypatch.setattr(session, "_write_session", fail_second_write)
    with pytest.raises(OSError, match="Metadaten voll"):
        session.start()
    assert session._output.stopped
    assert session._sink._fh is None
