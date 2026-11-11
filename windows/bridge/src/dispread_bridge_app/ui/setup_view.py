"""Einrichtung: Schrittkopf (5 Schritte Brückenwege, 4 Schritte UART direkt) und die Zustände E1–E5, D1–D4."""
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
from .tool_windows import note_line
from .widgets import (
    CopyField,
    Header,
    IconButton,
    InfoBar,
    ProgressRing,
    SavedNote,
    StateIcon,
    ValidatedField,
    button,
    footer_frame,
    repolish,
    slide_in,
)


class StepHeader(QWidget):
    """Schritte: erledigt / aktuell / offen; als Ganzes ein Screenreader-Satz."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = 1
        self.steps = texts.STEPS
        self.setFixedHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_step(1)

    def set_step(self, n: int, steps: tuple[str, ...] | None = None) -> None:
        if steps is not None and tuple(steps) != tuple(self.steps):
            self.steps = tuple(steps)
            self.setFixedHeight(54 if self.labels_visible() else 30)
        self.current = n
        self.setAccessibleName(f'Schritt {n} von {len(self.steps)}: {self.steps[n - 1]}')
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.setFixedHeight(54 if self.labels_visible() else 30)    # ohne Labels nur die Kreise

    LABEL_PT = 9.0          # 12 px: Lesbarkeitsgrenze, nie kleiner

    def _label_boxes(self) -> list[tuple[float, float]]:
        """Je Label (x0, x1), erstes/letztes an der Kante ausgerichtet."""
        w = self.width() / len(self.steps)
        boxes = []
        for i, label in enumerate(self.steps, 1):
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
        return QRectF((i - .5) * self.width() / len(self.steps) - 11, 3, 22, 22)

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            for i, name in enumerate(self.steps, 1):
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
        n = len(self.steps)
        w = self.width() / n
        show = self.labels_visible()
        boxes = self._label_boxes()
        for i, label in enumerate(self.steps, 1):
            cx = (i - .5) * w
            done, cur = i < self.current, i == self.current
            if i < n:
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
    CONTENT_MARGINS = (16, 4, 16, 12)

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
        self.header.mode_clicked.connect(lambda: self.action.emit('open_modes'))
        self.step_header = StepHeader()
        self.leave_button = IconButton('dismiss', texts.LEAVE_SETUP, name='leave_setup')
        self.leave_button.clicked.connect(lambda: self.action.emit('leave_setup'))
        self.leave_button.hide()
        self.saved_note = SavedNote()
        self.saved_note.setObjectName('step_saved')
        self.lead = _label('', strong=True)
        top.addWidget(self.header)
        top.addWidget(self.step_header)
        top.addWidget(self.saved_note)
        self.overview_button = button('Zur Übersicht', name='btn_overview')
        self.overview_button.hide()
        lead_row = QHBoxLayout()
        lead_row.addWidget(self.lead, 1)
        lead_row.addWidget(self.overview_button, 0, Qt.AlignmentFlag.AlignTop)
        lead_row.addWidget(self.leave_button, 0, Qt.AlignmentFlag.AlignTop)   # Schrittkopf rechts: verlassen
        top.addLayout(lead_row)
        root.addLayout(top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName('setup_content')
        self.cl = QVBoxLayout(self.content)
        self.cl.setContentsMargins(*self.CONTENT_MARGINS)
        self.cl.setSpacing(12)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)
        self.next_reason = _label('', secondary=True, caption=True)
        self.next_reason.setContentsMargins(16, 4, 16, 0)
        self.next_reason.hide()
        root.addWidget(self.next_reason)
        foot, fl = footer_frame()
        self.export_button = IconButton('document_arrow_down', texts.EXPORT_LOGS, name='export')
        self.exit_button = IconButton('power', texts.EXIT_TIP, name='exit_bridge')
        self.back_button = button('Zurück', name='back')
        self.next_button = button('Weiter', name='next')
        fl.addWidget(self.export_button)
        fl.addStretch(1)
        fl.addWidget(self.back_button)
        fl.addWidget(self.next_button)
        fl.addSpacing(4)
        fl.addWidget(self.exit_button)
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
        self.fields: dict[str, ValidatedField] = {}
        self.live_bars: list[InfoBar] = []
        self.gate_hints: dict[str, QLabel] = {}
        self.error_bar: InfoBar | None = None
        self._next_action, self._gate, self._freeze, self._last_step = 'next', None, False, 0
        self._locked, self._step = False, 1
        self._steps = texts.STEPS
        self._last_variant = ''
        # Anbindung an den Controller (setzt das Hauptfenster): echte Prüfungen und Thread-Pool
        self.check_fns: dict = {}
        self.runner = None
        self.port_labels: dict[str, str] = {}
        self.session_export = None                 # letzte SessionExport dieser Laufzeit (Pfad, Record Hidden)
        self.session_busy = False
        self.record_hidden_confirmed: set[str] = set()
        self.searching = False
        self._ports_requested_for = None
        self._ctx = None
        self._search_buttons: list = []
        self._record_hidden_gate = False

    def bind(self, check_fns: dict, runner) -> None:
        self.check_fns, self.runner = dict(check_fns), runner

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

    def _session_key(self) -> tuple:
        e = self.session_export
        return (None if e is None else (str(e.path), e.record_hidden_required), self.session_busy,
                tuple(sorted(self.port_labels.items())))

    def update_from(self, readiness, worker, ctx, locked: bool) -> None:
        self._ctx = ctx
        self.header.update_from(ctx, texts.headline(readiness, worker, ctx), locked, allow_switch=False,
                                peer=readiness.peer)
        self.header.headline.setVisible(False)
        self.header.head_icon.setVisible(False)
        self.header.pulse_slot.setVisible(False)
        self.leave_button.setVisible(bool(ctx.setup_leavable))
        st = ctx.setup
        self.overview_button.setVisible(readiness.peer == 'authenticated')
        spec = texts.setup_spec(ctx, locked)
        masked = dict(spec, blocks=tuple(('livebar', b[1], b[3], b[4]) if b[0] == 'livebar' else b
                                         for b in spec['blocks']))
        key = (st.variant, repr(masked), locked, self._session_key())
        if key != self.variant:
            self.variant = key
            prev_step, prev_variant, prev_steps = self._last_step, self._last_variant, self._steps
            self._locked, self._step, self._steps = locked, spec['step'], spec['steps']
            self.step_header.set_step(spec['step'], spec['steps'])
            self.lead.setText(spec['lead'])
            self._build(spec)
            if spec['step'] == 3 and self._last_step == 2 and self.next_button.isVisibleTo(self):
                QTimer.singleShot(0, self.next_button.setFocus)      # nach „Code übernehmen“ weiter mit „Verbinden“
            same_flow = prev_steps == spec['steps'] and prev_step > 0
            if st.variant != prev_variant and same_flow:
                if spec['step'] > prev_step or (spec['step'] == prev_step and st.variant.endswith('ok')
                                                 and not prev_variant.endswith('ok')):
                    self.saved_note.flash()                           # übernommener Schritt
                if spec['step'] != prev_step:
                    slide_in(self.content, self.cl, spec['step'] - prev_step, self.CONTENT_MARGINS)
            self._last_step, self._last_variant = spec['step'], st.variant
        for bar, blk in zip(self.live_bars, [b for b in spec['blocks'] if b[0] == 'livebar'], strict=False):
            bar.set_bar(texts.ActionBar(blk[1], blk[2], blk[3], tuple(blk[4])))
        self._apply_searching()

    def set_searching(self, on: bool) -> None:
        self.searching = on
        self._apply_searching()

    def _apply_searching(self) -> None:
        for b, ring in list(self._search_buttons):
            try:
                b.setVisible(not self.searching)
                ring.setVisible(self.searching)
            except RuntimeError:
                pass

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
        self.fields = {}
        self._search_buttons = []
        self._record_hidden_gate = False
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
        if self.code_edit is not None:
            self.code_edit.textChanged.connect(self._update_gates)
        for c in self.checks.values():
            c.toggled.connect(self._update_gates)
        for cb in self.combos.values():
            cb.currentIndexChanged.connect(self._update_gates)
        for f in self.fields.values():
            f.result_changed.connect(self._update_gates)

    def selected_ports(self) -> tuple[str | None, str | None]:
        def val(name):
            cb = self.combos.get(name)
            if cb is None or cb.currentIndex() <= 0:
                return None
            data = cb.currentData()
            return data if data is not None else cb.currentText()
        return val('bridge_port'), val('gsv_port')

    def _gate_ok(self, gate, a, c) -> bool:
        kind = gate[0]
        if kind == 'ports':
            return bool(a and c and a != c)
        if kind == 'blocked':
            return False
        if kind == 'pair':
            f = self.fields.get('pairing_code')
            return bool(self.checked('fp_ok') and self.code_text()
                        and not (f is not None and f.state == 'err'))          # formal falscher Code
        if kind.startswith('clear:'):            # Prüfung darf weder fehlgeschlagen sein noch laufen
            f = self.fields.get(kind[6:])
            return not (f is not None and f.state in ('pending', 'checking', 'err'))
        if kind.startswith('check:'):
            f = self.fields.get(kind[6:])
            return bool(f is not None and f.ok)
        return self.checked(kind)

    def _update_gates(self, *_a) -> None:
        """Knopfsperren neu bewerten: Koppeln-Knopf, Test starten, Portpaar, „Weiter“ mit Grund."""
        try:
            b = self.buttons.get('pair')
            if b is not None and not (self._locked and self._step <= 3):
                b.setEnabled(self._gate_ok(('pair',), None, None))
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
            ok = True
            if gate is not None:
                ok = self._gate_ok(gate, a, c)
                if not ok:
                    reason = gate[1]
                    if gate[0].startswith('clear:'):
                        f = self.fields.get(gate[0][6:])
                        reason = (texts.GATE_CHECK_RUNNING if f is not None and f.state in ('pending', 'checking')
                                  else gate[1])
            if ok and self._record_hidden_gate and not self.checked('record_hidden_ok'):
                ok, reason = False, texts.RECORD_HIDDEN_GATE
            if gate is not None or self._record_hidden_gate:
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
                port = cb.itemData(i) if cb.itemData(i) is not None else cb.itemText(i)
                cb.model().item(i).setEnabled(port != other)

    def _field(self, editor, check_name: str, value=None, label: str = '', debounce_ms=None,
               name: str = '') -> ValidatedField | None:
        fn = self.check_fns.get(check_name)
        if fn is None:
            return None
        f = ValidatedField(editor, fn, value=value, runner=self.runner, label=label, debounce_ms=debounce_ms,
                           name=name or f'field_{check_name}')
        return f

    def _search_button(self, aid: str = 'rescan', tip: str = texts.RESCAN_TIP) -> QWidget:
        """Symbolknopf „Suche wiederholen“; während der Suche steht ein Ring an seiner Stelle."""
        w = QWidget()
        w.setFixedSize(32, 32)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        b = IconButton('arrow_sync', tip, name=f'icon_{aid}')
        b.clicked.connect(lambda: self.action.emit(aid))
        ring = ProgressRing(16)
        ring.setAccessibleName(texts.CHECKING)
        ring.hide()
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ring, 0, Qt.AlignmentFlag.AlignCenter)
        self.buttons[aid] = b
        self._search_buttons.append((b, ring))
        return w

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

    def _make_combo(self, name, heading, ports, current) -> QComboBox:
        cb = QComboBox()
        cb.setObjectName(f'combo_{name}')
        cb.setAccessibleName(heading)
        cb.addItem(texts.PORT_CHOOSE)
        for port in ports:
            cb.addItem(self.port_labels.get(port, port), port)
        if current:
            idx = cb.findData(current)
            if idx > 0:
                cb.setCurrentIndex(idx)
        self.combos[name] = cb
        return cb

    def _b_combo(self, name, heading, ports, current):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(_label(heading, strong=True))
        lay.addWidget(self._make_combo(name, heading, ports, current))
        return w

    def _b_portpair(self, ports, cur_b, cur_g):
        """Brückenseite und GSVmulti-Seite als ein Prüffeld (check_port_pair)."""
        if not ports:
            box = QWidget()
            lay = QHBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(_label(texts.NO_PORTS, secondary=True), 1)
            lay.addWidget(self._search_button('list_ports', texts.RESCAN_PORTS_TIP), 0, Qt.AlignmentFlag.AlignTop)
            if self._ports_requested_for != self._last_variant_key():
                self._ports_requested_for = self._last_variant_key()
                QTimer.singleShot(0, lambda: self.action.emit('list_ports'))   # Liste einmal selbst einlesen
            return box
        if not self.port_labels and self._ports_requested_for != self._last_variant_key():
            self._ports_requested_for = self._last_variant_key()
            QTimer.singleShot(0, lambda: self.action.emit('list_ports'))   # Bezeichnungen (com0com, USB) nachladen
        editor = QWidget()
        el = QVBoxLayout(editor)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(4)
        for name, heading, cur in (('bridge_port', texts.PORT_BRIDGE, cur_b), ('gsv_port', texts.PORT_GSV, cur_g)):
            el.addWidget(_label(heading, strong=True))
            el.addWidget(self._make_combo(name, heading, ports, cur))

        def value():
            a, c = self.selected_ports()
            return (a, c) if a and c and a != c else None
        f = self._field(editor, 'port_pair', value=value, name='field_port_pair')
        if f is None:
            return editor
        self.fields['port_pair'] = f
        for cb in self.combos.values():
            cb.currentIndexChanged.connect(lambda _i, f=f: f.schedule(immediate=True))
        if value() is not None:
            QTimer.singleShot(0, lambda f=f: f.recheck() if f.state == 'idle' else None)
        return f

    def _last_variant_key(self):
        return self._ctx.setup.variant if self._ctx is not None and self._ctx.setup is not None else None

    def _b_card(self, heading, rows):
        f, lay = _card()
        if heading:
            lay.addWidget(_label(heading, strong=True))
        for k, v in rows:
            if k:
                lay.addWidget(_label(k, secondary=True, caption=True))
            lab = _label(v)
            if k == 'Pi-ID':                       # Kennung: Mono, damit sie sich zeichengenau vergleichen lässt
                lab.setProperty('mono', True)
                lab.setFont(theme.make_font(10.5, mono=True))
            lay.addWidget(lab)
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
        c.setObjectName(f'check_{aid}')
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
        e = QLineEdit()
        e.setObjectName('pairing_code')
        e.setAccessibleName(label)
        e.setFont(theme.make_font(10.5, mono=True))
        e.setProperty('mono', True)
        e.setMaxLength(64)
        e.setEchoMode(QLineEdit.EchoMode.Password)      # Code nicht mitlesbar am Bildschirm
        f = self._field(e, 'pairing_code', label=label, debounce_ms=0, name='field_pairing_code')
        if f is None:
            lay.addWidget(_label(label, strong=True))
            lay.addWidget(e)
        else:
            self.fields['pairing_code'] = f
            lay.addWidget(f)
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
        e = QLineEdit()
        e.setObjectName('manual_endpoint')
        e.setAccessibleName(label)
        e.editingFinished.connect(lambda: self.action.emit('entry:manual_endpoint'))
        self.endpoint_edit = e
        f = self._field(e, 'endpoint', label=label, name='field_endpoint')
        if f is None:
            lay.addWidget(_label(label, strong=True))
            lay.addWidget(e)
        else:
            self.fields['endpoint'] = f
            lay.addWidget(f)
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
        try:
            pb.setValue(int(value))
        except (TypeError, ValueError):            # unbekannter Fortschritt: leer, nie geraten
            pb.setValue(0)
        pb.setAccessibleName(title)
        lay.addWidget(pb)
        lay.addWidget(_label(text, secondary=True, caption=True))
        return w

    def _b_radios(self, name, items, heading=None):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if heading or name in texts.RESCAN_LISTS:
            head = QHBoxLayout()
            head.setSpacing(4)
            head.addWidget(_label(heading or '', strong=True), 1)
            if name in texts.RESCAN_LISTS:
                head.addWidget(self._search_button(), 0, Qt.AlignmentFlag.AlignVCenter)
            lay.addLayout(head)
        if not items:
            lay.addWidget(_label(texts.EMPTY_CHOICE.get(name, 'Keine Einträge gefunden.'), secondary=True))
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
            rb.setAccessibleName(f'{title}. {desc}' if desc else title)
            rb.toggled.connect(lambda on, n=name, i=idx: on and self.action.emit(f'radio:{n}:{i}'))
            group.addButton(rb)
            rl.addWidget(rb, 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(_label(title, strong=True))
            if desc:
                col.addWidget(_label(desc, secondary=True, caption=True))
            rl.addLayout(col, 1)
            if badge:
                bd = QLabel(badge[0])
                bd.setProperty('badge', True)
                rl.addWidget(bd, 0, Qt.AlignmentFlag.AlignTop)
            lay.addWidget(row)
        if name == 'adapter' and items and not self._locked and self._ctx is not None and self._ctx.adapter_port:
            return self._adapter_field(w)
        return w

    def _adapter_field(self, editor) -> QWidget:
        """Gewählter Adapter wird sofort echt geprüft (check_adapter); ok nur nach bestandener Prüfung."""
        port = self._ctx.adapter_port if self._ctx is not None else None
        f = self._field(editor, 'adapter', value=port, name='field_adapter')
        if f is None:
            return editor
        self.fields['adapter'] = f
        if port:
            QTimer.singleShot(0, lambda f=f: f.recheck() if f.state == 'idle' else None)
        return f

    def _b_adapter_pick(self, heading, items, port):
        """D1: USB-Seriell-Adapter wählen (Liste mit „Suche wiederholen“) und echt prüfen."""
        w = self._b_radios('adapter', items, heading)
        if 'adapter' not in self.fields and items and port and not self._locked:
            return self._adapter_field(w)
        return w

    def _b_session(self, port, name, path):
        """Session-Datei erzeugen (Kopie der geprüften Vorlage, nur Port geändert) oder das Ergebnis zeigen."""
        f, lay = _card()
        f.setObjectName('session_card')
        lay.setSpacing(8)
        exp = self.session_export
        warn = texts.single_channel_warning(self._ctx) if self._ctx is not None else ''
        full = path or (str(exp.path) if exp is not None and name and exp.path.name == name else None)
        if self.session_busy:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(ProgressRing(16))
            row.addWidget(_label(texts.SESSION_SAVING, secondary=True), 1)
            lay.addLayout(row)
            return f
        if name:
            row = QHBoxLayout()
            row.setSpacing(8)
            ic = QLabel()
            ic.setObjectName('session_done_icon')
            ic.setPixmap(theme.icon_pixmap('checkmark', 'text', 16))     # erzeugt ≠ abgenommen: nie grün
            ic.setAccessibleName(texts.SCREEN_READER['info'])
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(_label(texts.SESSION_DONE, strong=True), 1)
            lay.addLayout(row)
            lay.addWidget(CopyField(texts.SESSION_PATH, full or name))
            if port:
                lay.addWidget(CopyField(texts.SESSION_PORT, port))
            lay.addWidget(_label(texts.SESSION_NOT_ACCEPTED, secondary=True, caption=True))
            if exp is not None and full and str(exp.path) == full and exp.record_hidden_required:
                lay.addWidget(self._record_hidden_block(full))
            if warn:
                lay.addWidget(note_line('warn', warn, 'single_channel_warning'))
            hint = texts.autoscale_hint(port)
            if hint:
                    lay.addWidget(note_line('info', hint, 'autoscale_hint'))
            lay.addWidget(_label(texts.SESSION_HOWTO.format(port=port or '–'), secondary=True, caption=True))
            brow = QHBoxLayout()
            brow.setSpacing(8)
            if full:
                ob = button(texts.OPEN_FOLDER, name='btn_open_session_folder')
                ob.setIcon(theme.icon('folder_open', 'text', 16))
                ob.clicked.connect(lambda: self.action.emit('open_session_folder:' + full))
                self.buttons['open_session_folder'] = ob
                brow.addWidget(ob)
            again = button(texts.SESSION_AGAIN, name='btn_make_session')
            again.clicked.connect(lambda: self.action.emit('make_session'))
            again.setEnabled(bool(port))
            self.buttons['make_session'] = again
            brow.addWidget(again)
            brow.addStretch(1)
            lay.addLayout(brow)
            return f
        lay.addWidget(_label(texts.SESSION_WHAT))
        if warn:
            lay.addWidget(note_line('warn', warn, 'single_channel_warning'))
        if port:
            lay.addWidget(CopyField(texts.SESSION_PORT, port))
        b = button(texts.SESSION_MAKE, True, name='btn_make_session')
        b.clicked.connect(lambda: self.action.emit('make_session'))
        b.setEnabled(bool(port))
        self.buttons['make_session'] = b
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        if not port:
            lay.addWidget(_label(texts.SESSION_NO_PORT, secondary=True, caption=True))
        return f

    def _record_hidden_block(self, path: str) -> QWidget:
        """Pflichtschritt in GSVmulti, der nicht in der Session steht: Achtung, nicht wegklickbar, nie grün."""
        w = QFrame()
        w.setProperty('bar', True)
        w.setProperty('kind', 'warn')
        w.setObjectName('record_hidden')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(StateIcon('warn', 16), 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(_label(texts.RECORD_HIDDEN), 1)
        lay.addLayout(row)
        chk = self._b_check(texts.RECORD_HIDDEN_OK, 'record_hidden_ok', path in self.record_hidden_confirmed)
        chk.layout().setContentsMargins(26, 0, 0, 0)
        c = self.checks['record_hidden_ok']
        c.toggled.connect(lambda on, p=path: (self.record_hidden_confirmed.add(p) if on
                                              else self.record_hidden_confirmed.discard(p)))
        lay.addWidget(chk)
        self._record_hidden_gate = True
        return w
