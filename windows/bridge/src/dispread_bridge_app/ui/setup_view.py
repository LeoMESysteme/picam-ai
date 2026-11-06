"""Einrichtung: Schrittkopf 1-5 und die Zustände E1-E5 aus dem Mock."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from . import texts, theme
from .widgets import Header, InfoBar, StateIcon, button, footer_frame2, repolish


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
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.setFixedHeight(54 if self.labels_visible() else 30)    # ohne Labels nur die Kreise

    LABEL_PT = 9.0          # 12 px: Lesbarkeitsgrenze, nie kleiner

    def _label_boxes(self) -> list[tuple[float, float]]:
        """Je Label (x0, x1), erstes/letztes an der Kante ausgerichtet."""
        w = self.width() / 5
        boxes = []
        for i, label in enumerate(texts.STEPS, 1):
            font = theme.make_font(self.LABEL_PT, QFont.Weight.Normal)      # gleiche Breite für alle Schritte
            tw = QFontMetricsF(font).horizontalAdvance(label) + 2
            x = min(max((i - .5) * w - tw / 2, 0), self.width() - tw)
            boxes.append((x, x + tw))
        return boxes

    def labels_visible(self) -> bool:
        """Labels nur, wenn alle ohne Berührung in die Breite passen; sonst nur die Kreise."""
        boxes = self._label_boxes()
        return all(b[0] - a[1] >= 4 for a, b in zip(boxes, boxes[1:], strict=False))

    def circle_rect(self, i: int) -> QRectF:
        return QRectF((i - .5) * self.width() / 5 - 11, 3, 22, 22)

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            for i, name in enumerate(texts.STEPS, 1):
                if self.circle_rect(i).contains(QPointF(e.pos())):
                    QToolTip.showText(e.globalPos(), f'Schritt {i}: {name}', self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(e)

    def paintEvent(self, e):
        t = theme.tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() / 5
        show = self.labels_visible()
        boxes = self._label_boxes()
        for i, label in enumerate(texts.STEPS, 1):
            cx = (i - .5) * w
            done, cur = i < self.current, i == self.current
            if i < 5:
                p.setPen(QPen(QColor(t['accent'] if done else t['stroke_strong']), 1.5))
                p.drawLine(QPointF(cx + 14, 14), QPointF(cx + w - 14, 14))
            r = self.circle_rect(i)
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
            if show:
                p.setFont(theme.make_font(self.LABEL_PT, QFont.Weight.Normal))
                p.setPen(QColor(t['text'] if cur else t['text2']))
                x0, x1 = boxes[i - 1]
                p.drawText(QRectF(x0, 28, x1 - x0, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label)
        p.end()


def _card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setProperty('card', True)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(6)
    return f, lay


def _label(text, secondary=False, caption=False, strong=False, wrap=True) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    lab.setProperty('secondary', secondary)
    lab.setProperty('caption', caption)
    lab.setProperty('strong', strong)
    return lab


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
    lab = QLabel('<br>'.join(lines))
    lab.setTextFormat(Qt.TextFormat.RichText)
    lab.setFont(theme.make_font(9, mono=True))
    lab.setProperty('mono', True)
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lab.setAccessibleName('Fingerabdruck ' + ' '.join(groups))
    lab.setWordWrap(False)
    return lab


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
        self.overview_button = button('Zur Übersicht', name='btn_overview')
        self.overview_button.hide()
        lead_row = QHBoxLayout()
        lead_row.addWidget(self.lead, 1)
        lead_row.addWidget(self.overview_button, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(lead_row)
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
        self.next_reason = _label('', secondary=True, caption=True)
        self.next_reason.setContentsMargins(16, 4, 16, 0)
        self.next_reason.hide()
        root.addWidget(self.next_reason)
        foot, fl, fl2 = footer_frame2()
        self.export_button = button('Diagnose', name='export')
        self.export_button.setAccessibleName('Diagnose exportieren')
        self.exit_button = button('Beenden …', name='exit_bridge')
        fl2.addStretch(1)
        fl2.addWidget(self.exit_button)
        self.back_button = button('Zurück', name='back')
        self.next_button = button('Weiter', name='next')
        fl.addWidget(self.export_button)
        fl.addStretch(1)
        fl.addWidget(self.back_button)
        fl.addWidget(self.next_button)
        root.addWidget(foot)
        self.export_button.clicked.connect(lambda: self.action.emit('export_diagnostics'))
        self.overview_button.clicked.connect(lambda: self.action.emit('overview'))
        self.back_button.clicked.connect(lambda: self.action.emit('back'))
        self.next_button.clicked.connect(lambda: self.action.emit(self._next_action))
        self.exit_button.clicked.connect(lambda: self.action.emit('exit_bridge'))
        self.dut_label = self.header.dut
        self.headline_label = self.header.headline
        self.lock_button = self.header.lock_button
        self.variant = ''
        self._graveyard: list = []
        self.checks: dict[str, QCheckBox] = {}
        self.buttons: dict[str, QWidget] = {}
        self.radio_buttons: list = []
        self.combos: dict[str, QComboBox] = {}
        self.live_bars: list[InfoBar] = []
        self.gate_hints: dict[str, QLabel] = {}
        self.error_bar: InfoBar | None = None
        self._next_action, self._gate, self._freeze, self._last_step = 'next', None, False, 0
        self._locked, self._step = False, 1

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
        self.overview_button.setVisible(readiness.peer == 'authenticated')
        spec = texts.setup_spec(ctx, locked)
        masked = dict(spec, blocks=tuple(('livebar', b[1], b[3], b[4]) if b[0] == 'livebar' else b
                                         for b in spec['blocks']))
        key = (st.variant, repr(masked), locked)
        if key != self.variant:
            self.variant = key
            self._locked, self._step = locked, spec['step']
            self.step_header.set_step(spec['step'])
            self.lead.setText(spec['lead'])
            self._build(spec)
            if spec['step'] == 3 and self._last_step == 2 and self.next_button.isVisibleTo(self):
                QTimer.singleShot(0, self.next_button.setFocus)      # nach „Code übernehmen“ weiter mit „Verbinden“
            self._last_step = spec['step']
        for bar, blk in zip(self.live_bars, [b for b in spec['blocks'] if b[0] == 'livebar'], strict=False):
            bar.set_bar(texts.ActionBar(blk[1], blk[2], blk[3], tuple(blk[4])))

    def focus_error(self) -> None:
        """Nach einer abgelehnten Aktion: zur Fehlerleiste scrollen und sie fokussieren."""
        bar = self.error_bar
        try:
            if bar is None:
                return
            self.scroll.verticalScrollBar().setValue(0)
            self.scroll.ensureWidgetVisible(bar)
            bar.setFocus(Qt.FocusReason.OtherFocusReason)
        except RuntimeError:
            pass

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
        self.radio_buttons = []
        self.combos, self.live_bars, self.gate_hints, self.error_bar = {}, [], {}, None
        self.endpoint_edit = self.code_edit = None

    def _build(self, spec) -> None:
        self._clear()
        for blk in spec['blocks']:
            w = getattr(self, '_b_' + blk[0])(*blk[1:])
            if w is not None:
                self.cl.addWidget(w)
        self.cl.addStretch(1)
        self.back_button.setVisible(True)
        self.next_button.setVisible(spec['next'] is not None)
        self.next_button.setText(spec['next'] or '')
        self.next_button.setProperty('accent', spec['ready'])
        self.next_button.setEnabled(True)
        self._next_action, self._gate, self._freeze = spec['next_action'], spec['gate'], spec['freeze']
        repolish(self.next_button)
        self._wire_gates()
        self._apply_lock()
        if spec['freeze']:
            self.back_button.setEnabled(False)
        elif not self._locked:
            self.back_button.setEnabled(spec['back'])
        self.back_button.setVisible(spec['back'])
        self._update_gates()
        if self.error_bar is not None and any(b[0] == 'info' and b[1] == 'err' for b in spec['blocks']):
            QTimer.singleShot(0, self.focus_error)

    CONFIG_BUTTONS = ('install', 'manual_pair', 'set_port_pair', 'rescan', 'pair', 'open_profile', 'change_pair')

    def _apply_lock(self) -> None:
        """Bei aktiver Verbindung nur Konfiguration sperren; Navigation vorwärts, Export, Übersicht bleiben."""
        frozen = getattr(self, '_freeze', False)
        if not (frozen or (getattr(self, '_locked', False) and getattr(self, '_step', 9) <= 3)):
            return
        for cb in self.combos.values():
            cb.setEnabled(False)
        for r in self.radio_buttons:
            r.setEnabled(False)
            if r.parentWidget() is not None:
                r.parentWidget().setEnabled(False)      # ganze Zeile dimmen, auch die Labels
        for aid in self.CONFIG_BUTTONS:
            b = self.buttons.get(aid)
            if b is not None:
                b.setEnabled(False)
                b.setToolTip(texts.REASON_DISCONNECT_FIRST)
                b.setAccessibleDescription(texts.REASON_DISCONNECT_FIRST)
        for w in (getattr(self, 'endpoint_edit', None), getattr(self, 'code_edit', None), self.checks.get('fp_ok')):
            try:
                if w is not None:
                    w.setEnabled(False)
            except RuntimeError:
                pass
        self.back_button.setEnabled(False)
        if self._step == 3 and not frozen:
            self.next_button.setText('Weiter')          # verbunden: weiter zu Schritt 4, nie erneut verbinden

    def _wire_gates(self) -> None:
        """Knöpfe, die eine Bestätigung brauchen, bleiben bis dahin aus."""
        for gate, target in (('test_session_ok', 'start_demo_check'), ('fp_ok', 'pair')):
            c, b = self.checks.get(gate), self.buttons.get(target)
            if c is not None and b is not None:
                c.toggled.connect(self._update_gates)
        if self.code_edit is not None:
            self.code_edit.textChanged.connect(self._update_gates)
        for c in self.checks.values():
            c.toggled.connect(self._update_gates)
        for cb in self.combos.values():
            cb.currentIndexChanged.connect(self._update_gates)

    def selected_ports(self) -> tuple[str | None, str | None]:
        def val(name):
            cb = self.combos.get(name)
            return cb.currentText() if cb is not None and cb.currentIndex() > 0 else None
        return val('bridge_port'), val('gsv_port')

    def _update_gates(self, *_a) -> None:
        """Knopfsperren neu bewerten: Koppeln-Knopf, Test starten, Portpaar, „Weiter“ mit Grund."""
        try:
            b = self.buttons.get('pair')
            if b is not None and not (self._locked and self._step <= 3):
                ok = self.checked('fp_ok') and bool(self.code_text())
                b.setEnabled(ok)
            h = self.gate_hints.get('pair')
            if h is not None:
                h.setVisible(b is not None and not b.isEnabled() and not self._locked)
            t, tb = self.checks.get('test_session_ok'), self.buttons.get('start_demo_check')
            if t is not None and tb is not None:
                tb.setEnabled(t.isChecked())
            self._sync_combos()
            a, c = self.selected_ports()
            pb = self.buttons.get('set_port_pair')
            if pb is not None and not self._locked:
                pb.setEnabled(bool(a and c and a != c))
            reason = ''
            gate = self._gate
            if gate is not None:
                if gate[0] == 'ports':
                    ok = bool(a and c and a != c)
                else:
                    ok = self.checked(gate[0])
                if not ok:
                    reason = gate[1]
                if not (self._freeze or (self._locked and self._step == 3)):
                    self.next_button.setEnabled(ok)
            self.next_reason.setText(reason)
            self.next_reason.setVisible(bool(reason))
            self.next_button.setToolTip(reason)
        except RuntimeError:
            pass                                    # Widgets beim Neuaufbau zerstört

    def _sync_combos(self) -> None:
        a, c = self.selected_ports()
        for name, other in (('bridge_port', c), ('gsv_port', a)):
            cb = self.combos.get(name)
            if cb is None:
                continue
            for i in range(1, cb.count()):
                cb.model().item(i).setEnabled(cb.itemText(i) != other)

    # --- Blockbauer
    def _b_info(self, kind, title, text, buttons):
        bar = InfoBar()
        bar.set_bar(texts.ActionBar(kind, title, text, tuple(buttons)))
        bar.action.connect(self.action)
        for b, (_, aid, _p) in zip(bar.buttons, buttons, strict=False):
            self.buttons[aid] = b
        if kind == 'err' and self.error_bar is None:
            self.error_bar = bar
            bar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            bar.setAccessibleName(f'Fehler: {title}')
        return bar

    def _b_livebar(self, kind, title, text, buttons):
        bar = self._b_info(kind, title, text, buttons)
        self.live_bars.append(bar)
        return bar

    def _b_progress_busy(self, title, text):
        w = self._b_progress(title, text, 0)
        pb = w.findChild(QProgressBar)
        pb.setRange(0, 0)                           # unbestimmt
        return w

    def _b_gate_hint(self, aid, text):
        lab = _label(text, secondary=True, caption=True)
        self.gate_hints[aid] = lab
        return lab

    def _b_combo(self, name, heading, ports, current):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(_label(heading, strong=True))
        cb = QComboBox()
        cb.setObjectName(f'combo_{name}')
        cb.setAccessibleName(heading)
        cb.addItem('Bitte wählen …')
        cb.addItems(list(ports))
        if current:
            cb.setCurrentText(current)
        self.combos[name] = cb
        lay.addWidget(cb)
        return w

    def _b_card(self, heading, rows):
        f, lay = _card()
        if heading:
            lay.addWidget(_label(heading, strong=True))
        for k, v in rows:
            if k:
                lay.addWidget(_label(k, secondary=True, caption=True))
            lay.addWidget(_label(v))
        return f

    def _b_statusrows(self, heading, rows):
        """Je Zeile: Label (Caption, grau) darüber, Wert (Body) mit Statussymbol."""
        f, lay = _card()
        lay.addWidget(_label(heading, strong=True))
        for key, value, tone in rows:
            lay.addWidget(_label(key, secondary=True, caption=True))
            row = QHBoxLayout()
            row.setSpacing(6)
            icon = StateIcon(tone, 16)
            row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(_label(value), 1)
            lay.addLayout(row)
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
        """Haken + umbrechendes Label (QCheckBox bricht nicht um); Klick auf den Text schaltet um."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        c = QCheckBox()
        c.setAccessibleName(text)
        c.setChecked(checked)
        lab = _label(text)
        lab.mousePressEvent = lambda e, c=c: c.toggle() if c.isEnabled() else None
        lay.addWidget(c, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(lab, 1)
        self.checks[aid] = c
        c.toggled.connect(lambda on, a=aid: self.action.emit(a + (':on' if on else ':off')))
        return w

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
        e.setProperty('mono', True)
        e.setMaxLength(64)
        e.setEchoMode(QLineEdit.EchoMode.Password)      # Code nicht mitlesbar am Bildschirm
        lay.addWidget(e)
        show = self._b_check('Code anzeigen', 'code_show')
        self.checks['code_show'].toggled.connect(
            lambda on: e.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        lay.addWidget(show)
        lay.addWidget(_label(note, secondary=True, caption=True))
        self.code_edit = e
        e.returnPressed.connect(self._enter_in_code)
        return w

    def _enter_in_code(self) -> None:
        b = self.buttons.get('pair')
        if b is not None and b.isEnabled():
            b.click()

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
            self.radio_buttons.append(rb)
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
