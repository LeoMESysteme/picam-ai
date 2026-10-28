"""Small Node harness; no browser, hardware or session-directory access."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_session_transport_and_explorer_time_contracts():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node fehlt")
    result = subprocess.run([node, "--test", str(Path(__file__).with_name("session_transport.test.mjs"))],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
