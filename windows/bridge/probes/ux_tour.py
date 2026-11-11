"""Bildschirmfoto-Tour der Brücken-Oberfläche auf einem echten Desktop (UX2-Prüfung).

Startet die App nacheinander mit den Fake-Zuständen aus ``ui/fake.py``, öffnet die
Werkzeugfenster und fotografiert jedes Fenster samt nativem Rahmen vom Bildschirm.
Kein Pi, kein COM-Port, keine Netzwerkverbindung nötig.

    python windows/bridge/probes/ux_tour.py AUSGABEORDNER [--theme light|dark|system] [--only TEIL]

Skalierung prüfen: vorher ``set QT_SCALE_FACTOR=1.5`` (bzw. 2) setzen und einen
eigenen Ausgabeordner wählen. Bewegung bleibt an, damit sie sich ansehen lässt; die
Fotos warten, bis Übergänge fertig sind.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path[:0] = [str(HERE.parents[1] / 'src'), str(HERE.parents[3] / 'src')]
os.environ.setdefault('DISPREAD_UI_FIRST_RUN_MODES', '0')

from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# Szene: (Dateiname, Fake-Zustand, Größe, Fenster/Aktion)
SCENES = [
    ('01-betrieb-verbunden', 'B1', (440, 720), None),
    ('02-betrieb-testfreigabe', 'B1tr', (440, 720), None),
    ('03-betrieb-pi-antwortet-nicht', 'B3', (440, 720), None),
    ('04-betrieb-verbindungsaufbau', 'B3c', (440, 720), None),
    ('05-betrieb-nicht-eingerichtet', 'Bnone', (440, 720), None),
    ('06-betrieb-uart-direkt', 'Bdirect', (440, 720), None),
    ('07-betrieb-minimal-380', 'B1', (380, 560), None),
    ('10-fenster-moduswahl-erster-start', 'first_run', (440, 720), 'modes'),
    ('11-fenster-moduswahl', 'B10', (440, 720), 'modes'),
    ('12-fenster-moduswahl-gesperrt', 'B1', (440, 720), 'modes'),
    ('13-fenster-einstellungen', 'B10', (440, 720), 'settings'),
    ('14-fenster-einstellungen-gesperrt', 'B1', (440, 720), 'settings'),
    ('15-fenster-einstellungen-session', 'B10', (440, 720), 'settings+session'),
    ('16-fenster-einstellungen-uart-direkt', 'Bdirect', (440, 720), 'settings'),
    ('17-fenster-kachel-pi', 'B1', (440, 720), 'chip2'),
    ('18-fenster-kachel-gsvmulti', 'B1', (440, 720), 'chip5'),
    ('19-fenster-info', 'B1', (440, 720), 'info'),
    ('20-fenster-protokolle', 'B1', (440, 720), 'export'),
    ('21-fenster-protokolle-gespeichert', 'B1', (440, 720), 'export_done'),
    ('22-fenster-gekoppelte-pi', 'B1', (440, 720), 'paired'),
    ('30-einrichtung-komponenten', 'E1', (440, 720), None),
    ('31-einrichtung-portpaar', 'E1manual', (440, 720), None),
    ('32-einrichtung-koppeln', 'E2b', (440, 720), None),
    ('33-einrichtung-adresse-ok', 'E3', (440, 720), 'endpoint_ok'),
    ('34-einrichtung-adresse-fehler', 'E3', (440, 720), 'endpoint_err'),
    ('35-einrichtung-uart-bruecke', 'E3uart', (440, 720), None),
    ('36-einrichtung-session', 'E4session', (440, 720), 'session'),
    ('37-einrichtung-empfangstest', 'E5', (440, 720), None),
    ('40-direkt-adapter', 'D1', (440, 720), None),
    ('41-direkt-verdrahtung', 'D2', (440, 720), None),
    ('42-direkt-adapter-fehlt', 'D2missing', (440, 720), None),
    ('43-direkt-session', 'D3', (440, 720), 'session_hidden'),
    ('44-direkt-fertig', 'D4', (440, 720), None),
]


def settle(w, ms=300):
    QTest.qWait(ms)
    end = time.monotonic() + 8
    while w.pool.activeThreadCount() and time.monotonic() < end:
        QTest.qWait(20)
    QTest.qWait(ms)


def grab(widget, path: Path) -> None:
    """Fenster samt Rahmen vom Bildschirm (nicht widget.grab(), das zeigt keinen Rahmen)."""
    widget.raise_()
    widget.activateWindow()
    QTest.qWait(400)
    fg = widget.frameGeometry()
    screen = widget.screen() or QGuiApplication.primaryScreen()
    screen.grabWindow(0, fg.x(), fg.y(), fg.width(), fg.height()).save(str(path))


def run_scene(name, state, size, action, out: Path, dark, tmp: str) -> str:
    from dispread_bridge_app.ui.fake import FakeController
    from dispread_bridge_app.ui.window import MainWindow
    c = FakeController(state)
    w = MainWindow(c, dark=dark, first_run_modes=(state == 'first_run'))
    w.move(60, 60)
    w.resize(*size)
    w.show()
    w.refresh()
    settle(w)
    target = w
    try:
        sv = w.setup_view
        if action in ('endpoint_ok', 'endpoint_err'):
            sv.endpoint_edit.setText('pi.local' if action == 'endpoint_ok' else 'gibtsnicht.example')
            QTest.qWait(800)
            settle(w)
        elif action in ('session', 'session_hidden'):
            c.record_hidden = action == 'session_hidden'
            w.pick_session = lambda n: os.path.join(tmp, n)
            w.do_action('make_session')
            settle(w, 400)
        elif action and action.startswith(('modes', 'settings')):
            kind = action.split('+')[0]
            if kind not in w.tool_windows:
                w.do_action('open_' + kind)
            settle(w, 400)
            if action.endswith('+session'):
                w.pick_session = lambda n: os.path.join(tmp, n)
                w.do_action('make_session')
                settle(w, 400)
            target = w.tool_windows[kind]
        elif action and action.startswith('chip'):
            w.status_view.chips[int(action[4:])].click()
            settle(w)
            target = w.tool_windows['chip']
        elif action == 'info':
            w.do_action('details')
            settle(w)
            target = w.tool_windows['info']
        elif action in ('export', 'export_done'):
            w.do_action('export_diagnostics')
            settle(w)
            target = w.tool_windows['export']
            if action == 'export_done':
                w.pick_save = lambda: os.path.join(tmp, 'GSVmulti-Bruecke-Protokolle.zip')
                target.save_button.click()
                settle(w)
        elif action == 'paired':
            w._show_switch()
            settle(w)
            target = w.tool_windows['paired']
        grab(target, out / f'{name}.png')
        return 'ok'
    except Exception as exc:          # Szene überspringen, Tour fortsetzen
        return f'FEHLER {type(exc).__name__}: {exc}'
    finally:
        settle(w, 10)
        w.force_close()
        w.deleteLater()
        QApplication.processEvents()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Bildschirmfoto-Tour der Brücken-Oberfläche (UX2)')
    ap.add_argument('out', type=Path)
    ap.add_argument('--theme', choices=('light', 'dark', 'system'), default='system')
    ap.add_argument('--only', help='nur Szenen, deren Name diesen Text enthält')
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    QApplication.instance() or QApplication(sys.argv[:1])
    dark = {'light': False, 'dark': True, 'system': None}[args.theme]
    tmp = tempfile.mkdtemp(prefix='ux-tour-')
    lines = []
    for name, state, size, action in SCENES:
        if args.only and args.only not in name:
            continue
        result = run_scene(name, state, size, action, args.out, dark, tmp)
        lines.append(f'{name}\t{state}\t{action or "-"}\t{result}')
        print(lines[-1], flush=True)
    (args.out / 'tour.tsv').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 0 if all(line.endswith('ok') for line in lines) else 1


if __name__ == '__main__':
    raise SystemExit(main())
