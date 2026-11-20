"""Kamera-Neustart per Steuersocket und run.proc in live.status (nur Attrappen)."""

import asyncio
import json
import threading
from collections import deque
from types import SimpleNamespace

import pytest

from dispread.live.service import LiveService
from dispread.live.session import LiveSession
from dispread.workbench.server import handle_local_op


class FakeOwner:
    def __init__(self, fail=None):
        self.restarts, self.fail = [], fail

    def restart(self, source_factory=None, reason="neustart"):
        if self.fail:
            raise RuntimeError(self.fail)
        self.restarts.append(reason)

    def status(self):
        return {"running": True, "restarts": len(self.restarts)}


def _service(tmp_path, owner, state="idle"):
    service = LiveService(owner, tmp_path, diagnostic_staging_root=tmp_path / "staging")
    service._state = state
    return service


def _op(service):
    response = asyncio.run(handle_local_op("live.camera.restart", {}, None, service))
    return response.status, json.loads(response.text)


@pytest.mark.parametrize("state", ["idle", "setup_ready", "setup_failed", "confirmed", "stopped"])
def test_restart_in_safe_states(tmp_path, state):
    owner = FakeOwner()
    status, body = _op(_service(tmp_path, owner, state))
    assert status == 200
    assert body == {"ok": True, "camera": {"running": True, "restarts": 1}}
    assert owner.restarts == ["kamera_neustart"]


@pytest.mark.parametrize("state", ["running", "setup_running"])
def test_restart_refused_during_run_or_setup(tmp_path, state):
    owner = FakeOwner()
    status, body = _op(_service(tmp_path, owner, state))
    assert status == 409
    assert "nicht moeglich" in body["error"]
    assert owner.restarts == []


def test_restart_refused_with_pending_diagnostic_copy(tmp_path):
    owner = FakeOwner()
    service = _service(tmp_path, owner, "stopped")
    service._diagnostic_copies = [SimpleNamespace(diagnose_kopie=True)]
    status, body = _op(service)
    assert status == 409 and "Diagnosekopie" in body["error"]
    assert owner.restarts == []


def test_restart_blocked_reader_gives_german_409(tmp_path):
    owner = FakeOwner(fail="Kamera-Neustart abgelehnt: Leser blockiert")
    status, body = _op(_service(tmp_path, owner))
    assert status == 409 and "fehlgeschlagen" in body["error"] and "blockiert" in body["error"]


def _session(clock):
    session = LiveSession.__new__(LiveSession)
    session._monotonic = lambda: clock[0]
    session._proc_last = None
    session._latency_buckets = deque()
    session._proc_lock = threading.Lock()
    return session


def _info(latency, margins, fps=10.0, skipped=0.1):
    return {"proc": {"fps": fps, "latency_ms": latency, "skipped_recent": skipped},
            "cells": [{"i": i, "best": "1", "margin": m, "uncertain": m < 0} for i, m in enumerate(margins)]}


def test_proc_status_empty_is_unknown():
    proc = _session([5.0]).proc_status()
    assert proc["fps"] is None and proc["latency_ms"] is None and proc["age_s"] is None
    assert proc["latency_recent"] == [] and proc["cells"] == {"min_margin": None, "uncertain": 0}


def test_proc_status_buckets_max_age_and_margin():
    clock = [100.2]
    session = _session(clock)
    session._observe_proc(100.2, _info(12.0, [0.5, 0.2]))
    session._observe_proc(100.7, _info(30.0, [0.5, 0.2]))
    session._observe_proc(102.1, _info(8.0, [0.4, -0.1, 0.9]))
    clock[0] = 103.1
    proc = session.proc_status()
    assert proc["latency_recent"] == [[0.0, 30.0], [2000.0, 8.0]]
    assert proc["latency_ms"] == 8.0 and proc["fps"] == 10.0 and proc["skipped_recent"] == 0.1
    assert proc["cells"] == {"min_margin": -0.1, "uncertain": 1}
    assert proc["age_s"] == pytest.approx(1.0)
    assert proc["latency_now_ms"] == pytest.approx(3100.0)
    clock[0] = 170.0
    assert session.proc_status()["latency_recent"] == []


def test_status_run_proc_only_with_session(tmp_path):
    service = _service(tmp_path, FakeOwner())
    assert service.status()["run"] is None
    proc = {"fps": 9.5, "latency_ms": 20.0, "age_s": 0.2}
    service._session = SimpleNamespace(
        latest=None, summary={}, recent_snapshot=lambda: ([], 0.0), latest_age_s=lambda: None,
        tracking={}, proc_status=lambda: proc)
    service._run_dir = tmp_path
    assert service.status()["run"]["proc"] == proc
