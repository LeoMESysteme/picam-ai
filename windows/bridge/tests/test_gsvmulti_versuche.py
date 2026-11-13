import importlib.util
import io
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "gsvmulti_versuche", Path(__file__).resolve().parents[1] / "tools" / "gsvmulti_versuche.py")
assert _SPEC is not None and _SPEC.loader is not None
gv = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = gv  # dataclass braucht den Moduleintrag
_SPEC.loader.exec_module(gv)


class FakePort:
    def __init__(self):
        self.data = bytearray()

    def write(self, b):
        self.data += b
        return len(b)


def run(nummer):
    port, log, now = FakePort(), io.StringIO(), [0.0]
    gv.senden(gv.versuch(nummer), port, log=log,
              monotonic=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s), wall=lambda: 1789000000.0)
    return port.data.decode("ascii").split("\r\n")[:-1], [json.loads(z) for z in log.getvalue().splitlines()]


def test_versuch_2_layout_and_gap_position():
    lines, _ = run(2)
    assert len(lines) == 250
    assert all(z.startswith("%") and z.count(";") == 3 for z in lines)
    flags = [z.split(";")[1] for z in lines]
    assert flags == ["1"] * 100 + ["0"] * 50 + ["1"] * 100
    assert [int(z.split(";")[2]) for z in lines] == list(range(1, 251))
    assert lines[0] == "%0.50001;1;1;1789000000.000000"


def test_fixed_rate_without_catch_up():
    _, log = run(1)
    assert [e["soll_s"] for e in log[:3]] == [0.0, 0.1, 0.2]
    assert all(e["spaet_ms"] == 0 for e in log)


def test_versuch_5_pauses_send_nothing():
    lines, log = run(5)
    assert len(lines) == 500
    assert sum("telegramm" not in e for e in log) == (2 + 4 + 8 + 30) * 10


def test_versuch_3_markers_four_channels_flagged_invalid():
    lines, _ = run(3)
    assert len(lines) == len(gv.MARKER) * 100 + 50
    assert all(z.count(";") == 3 for z in lines)
    marker = [z for z in lines if z.split(";")[1] == "0"]
    assert len(marker) == len(gv.MARKER) * 50
    assert {z[1:].split(";")[0] for z in marker} == set(gv.MARKER)
    assert [int(z.split(";")[2]) for z in lines] == list(range(1, len(lines) + 1))
