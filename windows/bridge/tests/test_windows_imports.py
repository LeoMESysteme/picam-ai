"""Die EXE-Module müssen ohne Unix-Uhren und Unix-Module importierbar sein.

Unter Windows fehlen ``time.clock_gettime(_ns)`` und die ``CLOCK_*``-Konstanten. Ein Zugriff
darauf beim Import (z. B. als Standardargument) lässt den Selbsttest der EXE scheitern
(13.11.2026: ``dispread.live.clock`` über ``live.tick`` → ``gsv_bridge``). Der Test stellt
das in einem eigenen Prozess nach, damit die übrigen Tests das echte ``time`` behalten.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1]
REPO = BRIDGE.parents[1]

SCRIPT = r'''
import sys, time
for name in [n for n in dir(time) if n.startswith(("clock_get", "clock_set", "CLOCK_", "pthread_getcpuclockid"))]:
    delattr(time, name)
for name in ("fcntl", "termios", "pwd", "grp", "resource"):   # unter Windows nicht vorhanden
    sys.modules[name] = None
failed = []
for mod in sys.argv[1:]:
    try:
        __import__(mod)
    except Exception as exc:
        failed.append(f"{mod}: {type(exc).__name__}: {exc}")
print("\n".join(failed))
sys.exit(1 if failed else 0)
'''

# Dieselben Module, die der Selbsttest der EXE (packaging/app_launcher.py) prüft, soweit Windows-unabhängig.
MODULES = ("dispread.bridge", "dispread.gsv_bridge", "dispread_bridge_app.main", "dispread_bridge_app.ui.window")


def test_exe_modules_import_without_unix_clocks():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": os.pathsep.join([str(BRIDGE / "src"), str(REPO / "src")])}
    proc = subprocess.run([sys.executable, "-c", SCRIPT, *MODULES], env=env, capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
