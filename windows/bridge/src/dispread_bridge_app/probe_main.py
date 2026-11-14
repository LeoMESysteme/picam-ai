"""Exercise the bundled interpreter, light bridge and hidden Qt application."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
from pathlib import Path


def self_test() -> dict:
    frozen = bool(getattr(sys, "frozen", False))
    bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)).resolve()
    report = {
        "runtime_version": platform.python_version(), "qt_platform": None,
        "bridge_import_ok": False, "system_python_used": not frozen,
        "frozen": frozen, "qt_plugin_path": None, "qt_plugin_bundled": False,
        "loaded_modules": [], "provisional": True, "time_claim": False, "errors": [],
    }
    errors = report["errors"]
    if not frozen:
        errors.append("probe is not a frozen package")
    if sys.version_info < (3, 13):  # noqa: UP036 -- runtime assertion for frozen artifacts
        errors.append("Python >=3.13 runtime required")
    if sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        errors.append("Windows x64 runtime required")
    elif sys.getwindowsversion().build < 22000:
        errors.append("Windows 11 runtime required")
    try:
        bridge = importlib.import_module("dispread.gsv_bridge")
        report["bridge_import_ok"] = True
        if frozen and not Path(bridge.__file__).resolve().is_relative_to(bundle):
            errors.append("bridge was imported outside bundle")
        # Serial import is dynamic in the bridge; exercise it explicitly.
        importlib.import_module("serial")
    except Exception as exc:
        errors.append(f"bridge/serial import: {type(exc).__name__}: {exc}")
    try:
        core = importlib.import_module("PySide6.QtCore")
        widgets = importlib.import_module("PySide6.QtWidgets")
        plugins = Path(core.QLibraryInfo.path(core.QLibraryInfo.LibraryPath.PluginsPath)).resolve()
        report["qt_plugin_path"] = str(plugins)
        report["qt_plugin_bundled"] = (
            frozen and plugins.is_relative_to(bundle) and (plugins / "platforms/qwindows.dll").is_file()
        )
        if frozen and not report["qt_plugin_bundled"]:
            raise RuntimeError("Qt Windows platform plugin missing from bundle")
        if sys.platform != "win32":
            raise RuntimeError("Qt Windows platform probe requires a Windows host")
        # Ignore global Qt configuration. Qt's loader must use this package.
        if frozen:
            core.QCoreApplication.setLibraryPaths([str(plugins)])
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins / "platforms")
            os.environ["QT_QPA_PLATFORM"] = "windows"
        app = widgets.QApplication.instance() or widgets.QApplication([])
        report["qt_platform"] = app.platformName()
        app.processEvents()  # Never create/show a widget or start an event loop.
        if report["qt_platform"] != "windows":
            errors.append("Qt Windows platform is not active")
    except Exception as exc:
        errors.append(f"Qt runtime: {type(exc).__name__}: {exc}")
    report["loaded_modules"] = sorted(sys.modules)
    forbidden = {"cv2", "numpy", "PAM", "pam", "picamera2", "libcamera"}
    loaded_forbidden = sorted(forbidden & {name.split(".")[0] for name in sys.modules})
    if loaded_forbidden:
        errors.append("forbidden runtime imports: " + ", ".join(loaded_forbidden))
    report["ok"] = not errors
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args(argv)
    report = self_test()
    print(json.dumps(report, ensure_ascii=True, allow_nan=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
