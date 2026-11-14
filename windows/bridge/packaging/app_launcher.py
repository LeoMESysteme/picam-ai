"""Einstieg der eingefrorenen GUI (interner Testbuild).

freeze_support() zuerst; --self-test / --self-test-out werden vor jedem
GUI-Import abgefangen. Sonst übernimmt dispread_bridge_app.main.
"""
import multiprocessing
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if any(a in ('--self-test', '--self-test-out') for a in sys.argv[1:]):
        from dispread_bridge_app.selftest import main as _selftest
        raise SystemExit(_selftest())
    from dispread_bridge_app.main import main
    raise SystemExit(main())
