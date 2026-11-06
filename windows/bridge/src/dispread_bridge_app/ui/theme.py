"""Gestaltungs-Tokens (DESIGN.md) als QPalette + QSS, hell/dunkel."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap, QPolygonF

LIGHT = dict(
    mica='#f3f3f3', mica2='#ededed', card='#fbfbfb', stroke='#e5e5e5', stroke_strong='#8a8a8a',
    text='#1a1a1a', text2='#5d5d5d', text_dis='#9a9a9a', ctrl='#fdfdfd', ctrl_hover='#f6f6f6',
    ctrl_press='#efefef', ctrl_stroke='#d1d1d1', accent='#005fb8', accent_hover='#196ebd',
    accent_press='#3a82c5', on_accent='#ffffff', ok='#0f7b0f', warn='#9d5d00', err='#c42b1c',
    info='#5d5d5d', bar_ok='#dff6dd', bar_warn='#fff4ce', bar_err='#fde7e9', bar_info='#f9f9f9',
    focus_outer='#1a1a1a', focus_inner='#ffffff', scrim='rgba(0,0,0,77)')
DARK = dict(
    mica='#202020', mica2='#1b1b1b', card='#2b2b2b', stroke='#3a3a3a', stroke_strong='#9a9a9a',
    text='#ffffff', text2='#cfcfcf', text_dis='#7a7a7a', ctrl='#323232', ctrl_hover='#3a3a3a',
    ctrl_press='#292929', ctrl_stroke='#464646', accent='#60cdff', accent_hover='#52b7e6',
    accent_press='#44a0cc', on_accent='#000000', ok='#6ccb5f', warn='#fce100', err='#ff99a4',
    info='#cfcfcf', bar_ok='#393d1b', bar_warn='#433519', bar_err='#442726', bar_info='#2f2f2f',
    focus_outer='#ffffff', focus_inner='#1a1a1a', scrim='rgba(0,0,0,128)')

FONT_FAMILIES = ['Segoe UI Variable Text', 'Segoe UI', 'Noto Sans', 'DejaVu Sans']
MONO_FAMILIES = ['Cascadia Mono', 'Consolas', 'DejaVu Sans Mono', 'monospace']

_current: dict = dict(LIGHT)
_dark = False


def tokens() -> dict:
    return _current


def is_dark() -> bool:
    return _dark


def _luminance(c: QColor) -> float:
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c.red()) + 0.7152 * f(c.green()) + 0.0722 * f(c.blue())


def contrast(a: str | QColor, b: str | QColor) -> float:
    la, lb = _luminance(QColor(a)), _luminance(QColor(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def system_dark() -> bool:
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def _accent(base: dict) -> dict:
    """Windows-Akzent übernehmen, sofern er genug Kontrast zum Grund hat."""
    t = dict(base)
    try:
        acc = QGuiApplication.styleHints().accentColor()
    except Exception:
        return t
    if not acc.isValid() or contrast(acc, t['mica']) < 4.5:
        return t
    t['accent'] = acc.name()
    t['accent_hover'] = acc.lighter(110).name() if not _dark else acc.darker(108).name()
    t['accent_press'] = acc.lighter(125).name() if not _dark else acc.darker(120).name()
    t['on_accent'] = '#ffffff' if contrast(acc, '#ffffff') >= contrast(acc, '#000000') else '#000000'
    return t


def make_font(pt: float = 10.5, weight=QFont.Weight.Normal, mono=False, tabular=False) -> QFont:
    f = QFont()
    f.setFamilies(MONO_FAMILIES if mono else FONT_FAMILIES)
    f.setPointSizeF(pt)
    f.setWeight(weight)
    if tabular:
        try:
            f.setFeature(QFont.Tag('tnum'), 1)
        except Exception:
            pass
    return f


def qss(t: dict) -> str:
    return f"""
* {{ outline: 0; }}
QWidget {{ color: {t['text']}; font-size: 10.5pt; }}
QWidget#root, QDialog {{ background: {t['mica']}; }}
QLabel {{ background: transparent; }}
QLabel[secondary="true"] {{ color: {t['text2']}; }}
QLabel[caption="true"] {{ font-size: 9pt; }}
QLabel[strong="true"] {{ font-weight: 600; }}
QLabel[subtitle="true"] {{ font-size: 15pt; font-weight: 600; }}
QFrame.Card, QFrame[card="true"] {{ background: {t['card']}; border: 1px solid {t['stroke']}; border-radius: 8px; }}
QFrame[card="true"] QLabel {{ background: transparent; border: none; }}
QFrame#footer {{ background: {t['mica2']}; border-top: 1px solid {t['stroke']}; }}
QFrame#segmented {{ background: {t['mica2']}; border-radius: 4px; }}
QPushButton, QToolButton {{ background: {t['ctrl']}; border: 1px solid {t['ctrl_stroke']}; border-radius: 4px;
  padding: 5px 12px; min-height: 20px; }}
QPushButton:hover, QToolButton:hover {{ background: {t['ctrl_hover']}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {t['ctrl_press']}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {t['text_dis']}; }}
QPushButton[accent="true"] {{ background: {t['accent']}; color: {t['on_accent']}; border: 1px solid {t['accent']}; }}
QPushButton[accent="true"]:hover {{ background: {t['accent_hover']}; }}
QPushButton[accent="true"]:pressed {{ background: {t['accent_press']}; }}
QPushButton[accent="true"]:disabled {{ background: {t['ctrl_press']}; color: {t['text_dis']}; border-color: {t['ctrl_stroke']}; }}
QPushButton[seg="true"] {{ background: transparent; border: none; border-bottom: 2px solid transparent; padding: 3px 16px; }}
QPushButton[seg="true"]:checked {{ background: {t['card']}; border-bottom: 2px solid {t['accent']}; font-weight: 600; }}
QToolButton[chip="true"] {{ background: {t['card']}; border: 1px solid {t['stroke']}; padding: 4px 6px; text-align: left; }}
QToolButton[chip="true"]:hover {{ background: {t['ctrl_hover']}; }}
QToolButton[chip="true"]:checked {{ border: 1px solid {t['accent']}; }}
QToolButton[flat="true"] {{ background: transparent; border: none; padding: 4px; }}
QFrame[bar="true"] {{ border-radius: 4px; border: 1px solid transparent; }}
QFrame[bar="true"][kind="ok"] {{ background: {t['bar_ok']}; }}
QFrame[bar="true"][kind="warn"] {{ background: {t['bar_warn']}; }}
QFrame[bar="true"][kind="err"] {{ background: {t['bar_err']}; }}
QFrame[bar="true"][kind="info"] {{ background: {t['bar_info']}; border: 1px solid {t['stroke']}; }}
QFrame[bar="true"] QLabel {{ border: none; }}
QLabel[badge="true"] {{ border: 1px solid {t['stroke_strong']}; border-radius: 4px; padding: 0 5px; font-size: 9pt; }}
QLineEdit {{ background: {t['ctrl']}; border: 1px solid {t['ctrl_stroke']}; border-bottom: 1px solid {t['stroke_strong']};
  border-radius: 4px; padding: 5px 8px; selection-background-color: {t['accent']}; selection-color: {t['on_accent']}; }}
QLineEdit:focus {{ border-bottom: 2px solid {t['accent']}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QProgressBar {{ background: {t['stroke']}; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
QListView {{ background: {t['card']}; border: 1px solid {t['stroke']}; border-radius: 8px;
  selection-background-color: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['stroke_strong']}; border-radius: 3px; min-height: 24px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['stroke']}; padding: 4px; }}
QFrame[popup="true"] {{ background: {t['card']}; border: 1px solid {t['stroke']}; border-radius: 8px; }}
"""


def palette(t: dict) -> QPalette:
    p = QPalette()
    for role, key in ((QPalette.Window, 'mica'), (QPalette.Base, 'card'), (QPalette.AlternateBase, 'mica2'),
                      (QPalette.WindowText, 'text'), (QPalette.Text, 'text'), (QPalette.ButtonText, 'text'),
                      (QPalette.Button, 'ctrl'), (QPalette.Highlight, 'accent'),
                      (QPalette.HighlightedText, 'on_accent'), (QPalette.PlaceholderText, 'text2'),
                      (QPalette.ToolTipBase, 'card'), (QPalette.ToolTipText, 'text')):
        p.setColor(role, QColor(t[key]))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        p.setColor(QPalette.Disabled, role, QColor(t['text_dis']))
    return p


def apply_theme(app, dark: bool | None = None) -> dict:
    """Folgt dem Windows-Farbschema; ``dark`` erzwingt (Tests, Mock-Vergleich)."""
    global _current, _dark
    _dark = system_dark() if dark is None else dark
    _current = _accent(DARK if _dark else LIGHT)
    app.setFont(make_font())
    app.setPalette(palette(_current))
    app.setStyleSheet(qss(_current))
    return _current


# ---------------------------------------------------------------- Symbole
def status_pixmap(tone: str, size: int = 16, dpr: float = 2.0) -> QPixmap:
    t = tokens()
    color = QColor(t.get({'ok': 'ok', 'warn': 'warn', 'err': 'err'}.get(tone, 'info'), t['info']))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(1, 1, size - 2, size - 2)
    pen = QPen(color, 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    inner = QColor(t['card'])
    s = size
    if tone == 'warn':
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(s / 2, 1), QPointF(s - 1, s - 2), QPointF(1, s - 2)]))
        p.setPen(QPen(QColor(t['on_accent'] if not _dark else '#000000') if False else QColor('#ffffff' if not _dark else '#000000'), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(s / 2, s * .42), QPointF(s / 2, s * .65))
        p.drawPoint(QPointF(s / 2, s * .8))
    elif tone == 'unused':
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(r)
        p.drawLine(QPointF(s * .3, s / 2), QPointF(s * .7, s / 2))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(r)
        on = QColor('#ffffff' if not _dark else '#000000')
        p.setPen(QPen(on, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if tone == 'ok':
            p.drawPolyline(QPolygonF([QPointF(s * .3, s * .52), QPointF(s * .45, s * .66), QPointF(s * .72, s * .36)]))
        elif tone == 'err':
            p.drawLine(QPointF(s * .34, s * .34), QPointF(s * .66, s * .66))
            p.drawLine(QPointF(s * .66, s * .34), QPointF(s * .34, s * .66))
        elif tone == 'unclear':
            f = make_font(s * 0.55 * 0.75, QFont.Weight.Bold)
            p.setFont(f)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, '?')
        else:  # info
            p.drawLine(QPointF(s / 2, s * .46), QPointF(s / 2, s * .72))
            p.drawPoint(QPointF(s / 2, s * .3))
    p.end()
    return pm


def tray_icon(state: str = 'normal') -> QIcon:
    """normal / warn / err: Brückensymbol, bei Achtung/Fehler Badge unten rechts."""
    t = tokens()
    size = 32
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    fg = QColor('#ffffff' if _dark else '#1a1a1a')
    p.setPen(QPen(fg, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(3, 11, 9, 9))
    p.drawEllipse(QRectF(20, 11, 9, 9))
    p.drawLine(QPointF(12, 15.5), QPointF(20, 15.5))
    if state in ('warn', 'err'):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t['warn' if state == 'warn' else 'err']))
        p.drawEllipse(QRectF(18, 18, 13, 13))
    p.end()
    return QIcon(pm)


def glyph_icon(kind: str, size: int = 16) -> QIcon:
    """lock / chevron als gezeichnete Symbole (keine Emoji-Schrift nötig)."""
    t = tokens()
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(t['text2'])
    p.setPen(QPen(col, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    s = size
    if kind == 'lock':
        p.setBrush(col)
        p.drawRoundedRect(QRectF(s * .2, s * .46, s * .6, s * .4), 2, 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(s * .32, s * .12, s * .36, s * .5), 0, 180 * 16)
    else:
        p.drawPolyline(QPolygonF([QPointF(s * .28, s * .4), QPointF(s * .5, s * .62), QPointF(s * .72, s * .4)]))
    p.end()
    return QIcon(pm)
