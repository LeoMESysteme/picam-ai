"""Einrichtung: Schrittkopf 1-5 und die Zustände E1-E5 aus dem Mock."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QRadioButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from . import texts, theme
from .widgets import Header, InfoBar, StateIcon, button, footer_frame


class StepHeader(QWidget):
    """Fünf Schritte: erledigt / aktuell / offen; als Ganzes ein Screenreader-Satz."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = 1
        self.setFixedHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_step(1)

    def set_step(self, n: int) -> None:
        self.current = n
        self.setAccessibleName(f'Schritt {n} von 5: {texts.STEPS[n - 1]}')
        self.setToolTip(' · '.join(f'{i}. {s}' for i, s in enumerate(texts.STEPS, 1)))
        self.update()

    def _label_size(self, w: float) -> float:
        """Größte Schrift (9 bis 7 pt), bei der keine zwei Labels sich berühren oder abgeschnitten werden."""
        size = 9.0
        while size > 7:
            rects = []
            for i, label in enumerate(texts.STEPS, 1):
                font = theme.make_font(size, QFont.Weight.DemiBold if i == self.current else QFont.Weight.Normal)
                tw = QFontMetricsF(font).horizontalAdvance(label) + 2
                x = min(max((i - .5) * w - tw / 2, 0), self.width() - tw)
                rects.append((x, x + tw))
            if all(b[0] - a[1] >= 4 for a, b in zip(rects, rects[1:])):
                break
            size -= .5
        return size

    def paintEvent(self, e):
        t = theme.tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() / 5
        size = self._label_size(w)
        for i, label in enumerate(texts.STEPS, 1):
            cx = (i - .5) * w
            done, cur = i < self.current, i == self.current
            if i < 5:
                p.setPen(QPen(QColor(t['accent'] if done else t['stroke_strong']), 1.5))
                p.drawLine(QPointF(cx + 14, 14), QPointF(cx + w - 14, 14))
            r = QRectF(cx - 11, 3, 22, 22)
            p.setPen(QPen(QColor(t['accent'] if (done or cur) else t['stroke_strong']), 1.5))
            p.setBrush(QColor(t['accent']) if (done or cur) else QColor(t['mica']))
            p.drawEllipse(r)
            p.setPen(QColor(t['on_accent'] if (done or cur) else t['text2']))
            p.setFont(theme.make_font(9, QFont.Weight.DemiBold))
            if done:
                p.setPen(QPen(QColor(t['on_accent']), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawPolyline([QPointF(cx - 5, 14), QPointF(cx - 1.5, 17.5), QPointF(cx + 5, 10)])
            else:
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(i))
            font = theme.make_font(size, QFont.Weight.DemiBold if cur else QFont.Weight.Normal)
            tw = QFontMetricsF(font).horizontalAdvance(label) + 2
            p.setFont(font)
            p.setPen(QColor(t['text'] if cur else t['text2']))
            x = min(max(cx - tw / 2, 0), self.width() - tw)      # erstes/letztes Label bleibt im Fenster
            p.drawText(QRectF(x, 28, tw, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label)
        p.end()


def _card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setProperty('card', True)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(6)
    return f, lay


def _label(text, secondary=False, caption=False, strong=False, wrap=True) -> QLabel:
    l = QLabel(text)
    l.setWordWrap(wrap)
    l.setProperty('secondary', secondary)
    l.setProperty('caption', caption)
    l.setProperty('strong', strong)
    return l


def fingerprint_label(fp: str, other: str | None = None) -> QLabel:
    """Kleinbuchstaben-Hex, 4 Gruppen je Zeile in 4 Zeilen, Mono, nie gekürzt."""
    groups = fp.lower().split()
    ref = other.lower().split() if other else None
    lines = []
    for r in range(0, len(groups), 4):
        parts = []
        for i, g in enumerate(groups[r:r + 4], r):
            g = escape(g)
            if ref is not None and ref[i] != groups[i]:
                g = f'<b><u>{g}</u></b>'
            parts.append(g)
        lines.append('&nbsp;'.join(parts))
    l = QLabel('<br>'.join(lines))
    l.setTextFormat(Qt.TextFormat.RichText)
    l.setFont(theme.make_font(9, mono=True))
    l.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    l.setAccessibleName('Fingerabdruck ' + ' '.join(groups))
    l.setWordWrap(False)
    return l


class SetupView(QWidget):
    action = Signal(str)
    lock_clicked = Signal()
    switch_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        top = QVBoxLayout()
        top.setContentsMargins(16, 12, 16, 8)
        top.setSpacing(10)
        self.header = Header()
        self.header.lock_clicked.connect(self.lock_clicked)
        self.header.switch_clicked.connect(self.switch_clicked)
        self.step_header = StepHeader()
        self.lead = _label('', strong=True)
        top.addWidget(self.header)
        top.addWidget(self.step_header)
        top.addWidget(self.lead)
        root.addLayout(top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName('setup_content')
        self.cl = QVBoxLayout(self.content)
        self.cl.setContentsMargins(16, 4, 16, 12)
        self.cl.setSpacing(12)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)
        foot, fl = footer_frame()
        self.export_button = button('Diagnose exportieren', name='export')
        self.back_button = button('Zurück', name='back')
        self.next_button = button('Weiter', name='next')
        fl.addWidget(self.export_button)
        fl.addStretch(1)
        fl.addWidget(self.back_button)
        fl.addWidget(self.next_button)
        root.addWidget(foot)
        self.export_button.clicked.connect(lambda: self.action.emit('export_diagnostics'))
        self.back_button.clicked.connect(lambda: self.action.emit('back'))
        self.next_button.clicked.connect(lambda: self.action.emit('next'))
        self.dut_label = self.header.dut
        self.headline_label = self.header.headline
        self.lock_button = self.header.lock_button
        self.variant = ''
        self._graveyard: list = []
        self.checks: dict[str, QCheckBox] = {}
        self.buttons: dict[str, QWidget] = {}

    def code_text(self) -> str:
        e = getattr(self, 'code_edit', None)
        try:
            return e.text().strip() if e is not None else ''
        except RuntimeError:           # Widget wurde beim Neuaufbau zerstört
            return ''

    def endpoint_text(self) -> str:
        e = getattr(self, 'endpoint_edit', None)
        try:
            return e.text().strip() if e is not None else ''
        except RuntimeError:
            return ''

    def checked(self, aid: str) -> bool:
        c = self.checks.get(aid)
        return bool(c and c.isChecked())

    def update_from(self, readiness, worker, ctx, locked: bool) -> None:
        self.header.update_from(ctx, texts.headline(readiness, worker, ctx), locked, allow_switch=False)
        self.header.headline.setVisible(False)
        self.header.head_icon.setVisible(False)
        st = ctx.setup
        spec = texts.setup_spec(ctx)
        key = (st.variant, repr(spec))
        if key == self.variant:
            return
        self.variant = key
        self.step_header.set_step(spec['step'])
        self.lead.setText(spec['lead'])
        self._build(spec)

    def _clear(self) -> None:
        while self.cl.count():
            it = self.cl.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                self._graveyard.append(w)      # Python-Wrapper leben, bis Qt aufgeräumt hat
                w.deleteLater()
        QTimer.singleShot(500, self._graveyard.clear)
        self.checks, self.buttons = {}, {}

    def _build(self, spec) -> None:
        self._clear()
        for blk in spec['blocks']:
            w = getattr(self, '_b_' + blk[0])(*blk[1:])
            if w is not None:
                self.cl.addWidget(w)
        self.cl.addStretch(1)
        self.back_button.setVisible(spec['back'])
        self.next_button.setText(spec['next'])
        self.next_button.setProperty('accent', spec['ready'])
        self.next_button.setEnabled(True)
        from .widgets import repolish
        repolish(self.next_button)
        self._wire_gates()

    def _wire_gates(self) -> None:
        """Knöpfe, die eine Bestätigung brauchen, bleiben bis dahin aus."""
        for gate, target in (('test_session_ok', 'start_demo_check'), ('fp_ok', 'pair')):
            c, b = self.checks.get(gate), self.buttons.get(target)
            if c is not None and b is not None:
                b.setEnabled(c.isChecked())
                c.toggled.connect(b.setEnabled)

    # --- Blockbauer
    def _b_info(self, kind, title, text, buttons):
        bar = InfoBar()
        bar.set_bar(texts.ActionBar(kind, title, text, tuple(buttons)))
        bar.action.connect(self.action)
        for b, (_, aid, _p) in zip(bar.buttons, buttons):
            self.buttons[aid] = b
        return bar

    def _b_card(self, heading, rows):
        f, lay = _card()
        if heading:
            lay.addWidget(_label(heading, strong=True))
        for k, v in rows:
            if k:
                lay.addWidget(_label(k, secondary=True, caption=True))
            lay.addWidget(_label(v))
        return f

    def _b_text(self, text):
        return _label(text, secondary=True)

    def _b_bullets(self, items):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        for i in items:
            lay.addWidget(_label('•  ' + i))
        return w

    def _b_button(self, label, aid, primary):
        b = button(label, primary, name=f'btn_{aid}')
        b.clicked.connect(lambda: self.action.emit(aid))
        self.buttons[aid] = b
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(b)
        lay.addStretch(1)
        return w

    def _b_check(self, text, aid, checked=False):
        c = QCheckBox(text)
        c.setChecked(checked)
        self.checks[aid] = c
        c.toggled.connect(lambda on, a=aid: self.action.emit(a + (':on' if on else ':off')))
        return c

    def _b_drop(self, title, sub, label, aid):
        f, lay = _card()
        f.setObjectName('drop')
        f.setMinimumHeight(120)
        t = _label(title, strong=True, wrap=False)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s = _label(sub, secondary=True, caption=True, wrap=False)
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        lay.addWidget(t)
        lay.addWidget(s)
        b = button(label, True, name='btn_open_profile')
        b.clicked.connect(lambda: self.action.emit(aid))
        self.buttons[aid] = b
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        return f

    def _b_fp(self, label, fp):
        f, lay = _card()
        lay.addWidget(_label(label, secondary=True, caption=True))
        lay.addWidget(fingerprint_label(fp))
        return f

    def _b_fpdiff(self, label, fp, ref):
        f, lay = _card()
        lay.addWidget(_label(label, secondary=True, caption=True))
        lay.addWidget(fingerprint_label(fp, ref))
        return f

    def _b_code(self, label, note):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(_label(label, strong=True))
        e = QLineEdit()
        e.setObjectName('pairing_code')
        e.setAccessibleName(label)
        e.setFont(theme.make_font(10.5, mono=True))
        e.setMaxLength(64)
        e.setEchoMode(QLineEdit.EchoMode.Password)      # Code nicht mitlesbar am Bildschirm
        lay.addWidget(e)
        lay.addWidget(_label(note, secondary=True, caption=True))
        self.code_edit = e
        return w

    def _b_entry(self, label, note):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(_label(label, strong=True))
        e = QLineEdit()
        e.setObjectName('manual_endpoint')
        e.setAccessibleName(label)
        e.editingFinished.connect(lambda: self.action.emit('entry:manual_endpoint'))
        self.endpoint_edit = e
        lay.addWidget(e)
        lay.addWidget(_label(note, secondary=True, caption=True))
        return w

    def _b_progress(self, title, text, value):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(_label(title, strong=True))
        pb = QProgressBar()
        pb.setTextVisible(False)
        pb.setValue(int(value))
        pb.setAccessibleName(title)
        lay.addWidget(pb)
        lay.addWidget(_label(text, secondary=True, caption=True))
        return w

    def _b_radios(self, name, items, heading=None):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if heading:
            lay.addWidget(_label(heading, strong=True))
        group = QButtonGroup(w)
        for idx, it in enumerate(items):
            title, desc, checked, *badge = it
            row = QFrame()
            row.setProperty('card', True)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 8, 12, 8)
            rb = QRadioButton()
            rb.setChecked(checked)
            rb.setAccessibleName(f'{title}. {desc}')
            rb.toggled.connect(lambda on, n=name, i=idx: on and self.action.emit(f'radio:{n}:{i}'))
            group.addButton(rb)
            rl.addWidget(rb, 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(_label(title, strong=True))
            col.addWidget(_label(desc, secondary=True, caption=True))
            rl.addLayout(col, 1)
            if badge:
                bd = QLabel(badge[0])
                bd.setProperty('badge', True)
                rl.addWidget(bd, 0, Qt.AlignmentFlag.AlignTop)
            lay.addWidget(row)
        return w
