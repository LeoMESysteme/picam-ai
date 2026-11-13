"""Zentrale Vorgaben bleiben fuer alle Verbraucher wirksam und CWD-relativ."""

import ast
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_default_modules_exist():
    assert (ROOT / 'src/dispread/hardware_ports.py').exists()
    assert (ROOT / 'src/dispread/defaults.py').exists()


def test_cli_paths_stay_relative_to_working_directory(tmp_path, monkeypatch):
    from dispread import defaults
    from dispread.live import LIVE_DATA_DIR
    from dispread.workbench.cli import parser

    monkeypatch.chdir(tmp_path)
    cli = parser()
    args = cli.parse_args(['serve'])
    assert args.port == defaults.SERVE_PORT == 8080
    assert args.data == str(defaults.WORKBENCH_DATA_DIR) == 'var/workbench'
    assert args.live_data == str(LIVE_DATA_DIR) == str(defaults.LIVE_DATA_DIR) == 'var/live'
    assert args.cert == str(defaults.TLS_CERT) == 'var/workbench/tls/cert.pem'
    assert args.key == str(defaults.TLS_KEY) == 'var/workbench/tls/key.pem'
    assert Path(args.data).resolve() == tmp_path / 'var/workbench'
    assert cli.parse_args(['init-tls']).directory == str(defaults.TLS_DIR)
    for command in (['identity'], ['export-profile', '--name', 'Pi', '--output', 'profile.json'], ['revoke', 'client']):
        assert cli.parse_args(['bridge', *command]).directory == str(defaults.BRIDGE_DIR)


def test_direct_baud_and_uart_port_reach_consumers():
    from dispread.gsv_transport import OutputConfig
    from dispread.hardware_ports import DIRECT_UART_BAUD, GSV_UART_PORT
    from dispread.live.output import validate_output
    from dispread.sink.serial_out import SerialSink

    assert OutputConfig().serial_port == GSV_UART_PORT == '/dev/ttyAMA0'
    with pytest.raises(ValueError, match='Referenzport'):
        OutputConfig(serial_port='/dev/serial0')
    assert validate_output({'port': '/dev/ttyAMA0'})['baudrate'] == DIRECT_UART_BAUD == 115200
    assert inspect.signature(SerialSink).parameters['baudrate'].default == DIRECT_UART_BAUD


@pytest.mark.parametrize(('path', 'names'), [
    ('src/dispread/gsv_transport.py', {'GSV_UART_PORT'}),
    ('src/dispread/bridge/uart.py', {'GSV_UART_PORT'}),
    ('src/dispread/live/output.py', {'DIRECT_UART_BAUD'}),
    ('src/dispread/sink/serial_out.py', {'DIRECT_UART_BAUD'}),
    ('src/dispread/gsv_bridge.py', {'DIRECT_UART_BAUD'}),
    ('scripts/gsv-publisher-demo.py', {'GSV_UART_PORT'}),
    ('scripts/gsvmulti-demo-sender.py', {'DIRECT_UART_BAUD'}),
    ('src/dispread/workbench/cli.py', {'SERVE_PORT', 'WORKBENCH_DATA_DIR', 'LIVE_DATA_DIR',
                                    'TLS_DIR', 'TLS_CERT', 'TLS_KEY', 'BRIDGE_DIR'}),
    ('src/dispread/live/__init__.py', {'LIVE_DATA_DIR'}),
])
def test_consumers_import_shared_defaults(path, names):
    # Architekturvertrag aus P0a: kein neuer lokaler Default bei Refactorings.
    tree = ast.parse((ROOT / path).read_text())
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                and node.module in {'dispread.hardware_ports', 'dispread.defaults'} for alias in node.names}
    assert names <= imported
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert names <= used | ({'LIVE_DATA_DIR'} if path.endswith('__init__.py') else set())
