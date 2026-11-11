"""Gestaltungs-Tokens (DESIGN.md) als QPalette + QSS, hell/dunkel."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import icons

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
# QSS-Schriftlisten: jede mit generischem Fallback, damit Qt unter Windows nie auf Serif (Times) fällt
FONT_QSS = ', '.join(f'"{n}"' for n in FONT_FAMILIES) + ', sans-serif'
MONO_QSS = '"Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace'

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
    f.setStyleHint(QFont.StyleHint.Monospace if mono else QFont.StyleHint.SansSerif)
    f.setPointSizeF(pt)
    f.setWeight(weight)
    if tabular:
        try:
            f.setFeature(QFont.Tag('tnum'), 1)
        except Exception:
            pass
    return f


# ---------------------------------------------------------------- Typografie (Spec UX2)
# Rolle -> (Punkt, Gewicht, Mono, sekundär). Als QSS-Property ``typo`` und für gezeichnete Texte.
TYPO = {
    'title': (15, QFont.Weight.DemiBold, False, False),          # Pi-Name im Kopf, Titel im Fensterinhalt
    'section': (11, QFont.Weight.DemiBold, False, False),        # Überschriften in Fenstern
    'body_strong': (10.5, QFont.Weight.DemiBold, False, False),  # Zustandssatz, Kartentitel
    'body': (10.5, QFont.Weight.Normal, False, False),
    'caption': (9, QFont.Weight.Normal, False, True),            # Feldnamen, Zweitzeilen (text2)
    'caption_strong': (9, QFont.Weight.DemiBold, False, False),  # Statuswörter
    'data': (9, QFont.Weight.Normal, True, False),               # Pi-ID, Endpunkt, Fingerabdruck, Ports
}


def typo_font(role: str) -> QFont:
    pt, weight, mono, _ = TYPO[role]
    return make_font(pt, weight, mono=mono, tabular=role in ('caption', 'caption_strong', 'data'))


def set_typo(widget, role: str):
    """Typostufe setzen (QSS-Property ``typo``; Mono zusätzlich über ``mono``/Schrift)."""
    widget.setProperty('typo', role)
    if TYPO[role][2]:
        widget.setProperty('mono', True)
        widget.setFont(typo_font(role))
    return widget


# ---------------------------------------------------------------- Bewegung
MOTION_ENV = 'DISPREAD_UI_MOTION'      # "0" schaltet Bewegung ab (Tests: deterministisch)
SPI_GETCLIENTAREAANIMATION = 0x1042


def motion_enabled() -> bool:
    """Zentraler Schalter für alle Animationen. Windows: folgt „Animationseffekte“."""
    env = os.environ.get(MOTION_ENV)
    if env is not None:
        return env.strip().lower() not in ('0', 'off', 'false', 'no', '')
    if sys.platform == 'win32':
        try:
            import ctypes
            from ctypes import wintypes
            on = wintypes.BOOL(True)
            if ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(on), 0):
                return bool(on.value)
        except Exception:
            return True
    return True


def _chevron_url(t: dict) -> str:
    """Combo-Pfeil als PNG im Temp-Ordner (QSS kann nur Dateien), in Textfarbe; Pfad mit Schrägstrichen."""
    import tempfile
    try:
        d = os.path.join(tempfile.gettempdir(), 'dispread-bridge-ui')
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"chevron-{t['text'].lstrip('#')}.png")
        if not os.path.exists(path):
            icon_pixmap('chevron_down', t['text'], 12, 2.0).save(path, 'PNG')
        return path.replace('\\', '/')
    except Exception:
        return ''


def qss(t: dict) -> str:
    return f"""
* {{ outline: 0; }}
QWidget {{ color: {t['text']}; font-family: {FONT_QSS}; font-size: 10.5pt; }}
QWidget[mono="true"] {{ font-family: {MONO_QSS}; }}
QWidget#root, QDialog {{ background: {t['mica']}; }}
QLabel {{ background: transparent; }}
QLabel[secondary="true"] {{ color: {t['text2']}; }}
QLabel[caption="true"] {{ font-size: 9pt; }}
QLabel[strong="true"] {{ font-weight: 600; }}
QLabel[subtitle="true"] {{ font-size: 15pt; font-weight: 600; }}
QLabel[typo="title"] {{ font-size: 15pt; font-weight: 600; }}
QLabel[typo="section"] {{ font-size: 11pt; font-weight: 600; }}
QLabel[typo="body_strong"] {{ font-size: 10.5pt; font-weight: 600; }}
QLabel[typo="body"] {{ font-size: 10.5pt; font-weight: 400; }}
QLabel[typo="caption"] {{ font-size: 9pt; font-weight: 400; color: {t['text2']}; }}
QLabel[typo="caption_strong"] {{ font-size: 9pt; font-weight: 600; }}
QLabel[typo="data"] {{ font-family: {MONO_QSS}; font-size: 9pt; }}
QFrame.Card, QFrame[card="true"] {{ background: {t['card']}; border: 1px solid {t['stroke']}; border-radius: 8px; }}
QFrame[card="true"] QLabel {{ background: transparent; border: none; }}
QFrame[card="true"][selected="true"] {{ border: 1px solid {t['accent']}; }}
QFrame[card="true"][dimmed="true"] QLabel[typo="body_strong"] {{ color: {t['text2']}; }}
QFrame[card="true"] QLabel[badge="true"] {{ border: 1px solid {t['stroke_strong']}; }}
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
QToolButton[flat="true"] {{ background: transparent; border: 1px solid transparent; padding: 4px; }}
QToolButton[flat="true"]:hover {{ background: {t['ctrl_hover']}; }}
QToolButton[flat="true"]:pressed {{ background: {t['ctrl_press']}; }}
QToolButton[flat="true"]:disabled {{ background: transparent; }}
QToolButton[mode="true"] {{ background: transparent; border: 1px solid transparent; padding: 2px 6px; }}
QToolButton[mode="true"]:hover {{ background: {t['ctrl_hover']}; border: 1px solid {t['stroke']}; }}
QToolButton[mode="true"]:pressed {{ background: {t['ctrl_press']}; }}
QFrame#toolbar {{ background: {t['mica2']}; border-top: 1px solid {t['stroke']}; }}
QFrame[section="true"] {{ background: {t['card']}; border: 1px solid {t['stroke']}; border-radius: 8px; }}
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
QRadioButton::indicator {{ width: 12px; height: 12px; border-radius: 7px; border: 1px solid {t['stroke_strong']};
  background: {t['ctrl']}; }}
QRadioButton::indicator:hover {{ background: {t['ctrl_hover']}; }}
QRadioButton::indicator:checked {{ width: 6px; height: 6px; border: 4px solid {t['accent']}; background: {t['on_accent']}; }}
QRadioButton::indicator:disabled {{ border-color: {t['text_dis']}; background: {t['mica2']}; }}
QRadioButton::indicator:checked:disabled {{ border-color: {t['text_dis']}; background: {t['mica2']}; }}
QWidget:disabled {{ color: {t['text_dis']}; }}
QLineEdit:disabled {{ background: {t['mica2']}; color: {t['text_dis']}; border: 1px solid {t['stroke']}; }}
QProgressBar {{ background: {t['stroke']}; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
QListView {{ background: {t['card']}; border: 1px solid {t['stroke']}; border-radius: 8px;
  selection-background-color: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; border: none; width: 10px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; border: none; height: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['stroke_strong']}; border-radius: 3px; min-height: 24px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['stroke_strong']}; border-radius: 3px; min-width: 24px; margin: 2px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; background: none; border: none; }}
QComboBox {{ background: {t['ctrl']}; color: {t['text']}; border: 1px solid {t['ctrl_stroke']};
  border-bottom: 1px solid {t['stroke_strong']}; border-radius: 4px; padding: 4px 8px; min-height: 22px;
  selection-background-color: {t['accent']}; selection-color: {t['on_accent']}; }}
QComboBox:hover {{ background: {t['ctrl_hover']}; }}
QComboBox:focus, QComboBox:on {{ border-bottom: 2px solid {t['accent']}; }}
QComboBox:disabled {{ background: {t['mica2']}; color: {t['text_dis']}; border: 1px solid {t['stroke']}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none;
  background: transparent; }}
QComboBox::down-arrow {{ image: url({_chevron_url(t)}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {t['ctrl']}; color: {t['text']}; border: 1px solid {t['ctrl_stroke']};
  outline: 0; padding: 2px; selection-background-color: {t['accent']}; selection-color: {t['on_accent']}; }}
QComboBox QAbstractItemView::item {{ min-height: 24px; padding: 2px 6px; background: transparent; color: {t['text']}; }}
QComboBox QAbstractItemView::item:selected, QComboBox QAbstractItemView::item:hover {{
  background: {t['accent']}; color: {t['on_accent']}; }}
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


# ---------------------------------------------------------------- Symbole (Fluent, icons.py)
_STATUS_ICON = {'ok': 'status_ok', 'warn': 'status_warn', 'err': 'status_err', 'info': 'status_info',
                'unclear': 'status_unclear', 'unused': 'status_unused'}
_STATUS_COLOR = {'ok': 'ok', 'warn': 'warn', 'err': 'err', 'info': 'info', 'unclear': 'warn', 'unused': 'text2'}
_pix_cache: dict[tuple, QPixmap] = {}


def _color(color_key: str) -> str:
    """Token-Name oder direkt ein Farbwert (#rrggbb)."""
    return color_key if color_key.startswith('#') else _current.get(color_key, _current['text'])


def screen_dpr() -> float:
    try:
        scr = QGuiApplication.primaryScreen()
        return max(1.0, float(scr.devicePixelRatio())) if scr is not None else 1.0
    except Exception:
        return 1.0


def _svg_for(name: str, size: int) -> str:
    if size <= 16 and f'{name}@16' in icons.SVG:
        return icons.SVG[f'{name}@16']
    try:
        return icons.SVG[name]
    except KeyError:
        raise KeyError(f'Symbol {name!r} ist nicht eingebettet (ui/icons.py)') from None


def icon_pixmap(name: str, color_key: str = 'text2', size: int = 16, dpr: float | None = None) -> QPixmap:
    """Symbol als Pixmap, eingefärbt aus den Tokens; gecacht je (Name, Farbe, Größe, DPR)."""
    dpr = dpr or screen_dpr()
    color = _color(color_key)
    key = (name, color, size, dpr)
    pm = _pix_cache.get(key)
    if pm is not None:
        return pm
    svg = _svg_for(name, size).replace('<svg ', f'<svg fill="{color}" ', 1)
    px = max(1, round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode('ascii'))).render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(dpr)
    _pix_cache[key] = pm
    return pm


def icon(name: str, color_key: str = 'text2', size: int = 16) -> QIcon:
    """QIcon mit Pixmaps für 100 %, 150 % und 200 % (Qt wählt je Bildschirm)."""
    ic = QIcon()
    for dpr in sorted({1.0, 1.5, 2.0, screen_dpr()}):
        ic.addPixmap(icon_pixmap(name, color_key, size, dpr))
    return ic


def status_pixmap(tone: str, size: int = 16, dpr: float | None = None) -> QPixmap:
    """Statussymbol (ok/warn/err/info/unclear/unused) aus demselben Symbolsatz, in der Statusfarbe."""
    return icon_pixmap(_STATUS_ICON.get(tone, 'status_info'), _STATUS_COLOR.get(tone, 'info'), size, dpr)


def glyph_icon(kind: str, size: int = 16) -> QIcon:
    """Altname: ``lock`` / ``chevron`` aus dem Fluent-Satz."""
    return icon({'lock': 'lock_closed', 'chevron': 'chevron_down'}.get(kind, kind), 'text2', size)


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
