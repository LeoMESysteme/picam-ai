import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).with_name("live_client.test.mjs")


def test_live_page_status_view():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node fehlt")
    result = subprocess.run([node, "--test", str(HARNESS)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
