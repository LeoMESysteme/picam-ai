import importlib.util
from pathlib import Path

import pytest

from dispread import gsv2as_serial


@pytest.mark.parametrize('raw,valid', [(b';\x01', True), (b'\x01', False), (b'x\x01', False)])
def test_shared_register_reader_checks_prefix_and_data_count(raw, valid):
    from test_live_reference import FakePort
    class Port(FakePort):
        def read(self, count):
            return raw
    entry = gsv2as_serial.read_register(Port(), 'dpoint', 0x1c, 1)
    assert ('daten' in entry) is valid
    if valid:
        assert entry['daten'] == [1]
    else:
        assert 'fehler' in entry


def test_register_script_imports_shared_protocol():
    path = Path(__file__).parents[1] / 'scripts/gsv-registers.py'
    spec = importlib.util.spec_from_file_location('register_script', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.read_register is gsv2as_serial.read_register
    assert module._read_exact is gsv2as_serial._read_exact
    assert module.READ_COMMANDS is gsv2as_serial.READ_COMMANDS
