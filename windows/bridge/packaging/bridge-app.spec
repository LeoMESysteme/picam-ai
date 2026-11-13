# INTERNER, UNQUALIFIZIERTER Testbuild der GUI "GSVmulti-Bruecke".
# Nur ueber build-test.ps1 (Windows 11 x64). Kein freigegebener Bauweg:
# der qualifizierte Weg bleibt build.ps1 + bridge.spec.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

bridge_root = Path(SPECPATH).parent
repo_root = bridge_root.parents[1]

a = Analysis(
    [str(bridge_root / "packaging/app_launcher.py")],
    pathex=[str(bridge_root / "src"), str(repo_root / "src")],
    binaries=[],
    datas=[(str(bridge_root / "src/dispread_bridge_app/templates/Session-COM8.ucf"),
            "dispread_bridge_app/templates"),
           (str(bridge_root / "src/dispread_bridge_app/templates/vorlage-4kanal-mvv.ucf"),
            "dispread_bridge_app/templates")],
    hiddenimports=[
        "dispread.gsv_bridge", "serial", "serial.tools.list_ports",
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
        "cryptography", "aiohttp", "zeroconf",
        *collect_submodules("dispread.bridge"),
        *collect_submodules("dispread_bridge_app"),
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
    pyz, a.scripts, [], exclude_binaries=True, name="GSVmulti-Bruecke",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="GSVmulti-Bruecke")
