# Internal console probe only. No GUI layout, installer, driver or Pi configuration.
from pathlib import Path

bridge_root = Path(SPECPATH).parent
repo_root = bridge_root.parents[1]

a = Analysis(
    [str(bridge_root / "src/dispread_bridge_app/probe_main.py")],
    pathex=[str(bridge_root / "src"), str(repo_root / "src")],
    binaries=[],
    datas=[(str(bridge_root / "src/dispread_bridge_app/templates/Session-COM8.ucf"),
            "dispread_bridge_app/templates"),
           (str(bridge_root / "src/dispread_bridge_app/templates/vorlage-4kanal-mvv.ucf"),
            "dispread_bridge_app/templates")],
    hiddenimports=[
        "dispread.gsv_bridge", "serial", "serial.tools.list_ports",
        "PySide6.QtCore", "PySide6.QtWidgets",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "cv2", "numpy", "PAM", "pam", "picamera2", "libcamera",
        "dispread.workbench", "PyQt5", "PyQt6", "PySide2",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="dispread-bridge-probe",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="dispread-bridge-probe")
