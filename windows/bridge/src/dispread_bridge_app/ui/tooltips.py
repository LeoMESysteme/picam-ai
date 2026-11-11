"""Tooltips als Box (R3-6, B-01): überall gleich, höchstens 320 px breit, Verzögerung ca. 300 ms.

Ein Ereignisfilter auf der Anwendung fängt jedes ``QEvent.ToolTip`` ab und zeigt den Text als Rich Text
in einer Tabelle mit begrenzter Breite. Die Verzögerung kommt aus einem ``QProxyStyle``.
"""
from __future__ import annotations

import math
import re
from html import escape

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QComboBox, QProxyStyle, QStyle, QToolTip, QWidget

MAX_WIDTH = 320
_TAG = re.compile(r'<(?:b|i|u|br|p|div|span|ul|li|table|code)\b[^>]*>', re.IGNORECASE)
DELAY_MS = 300


def box_html(text: str, max_width: int = MAX_WIDTH) -> str:
    """Tooltip-Text als Rich-Text-Box. Reiner Text wird maskiert; Rich Text bleibt, wie er ist."""
    inner = text if _TAG.search(text) else escape(text).replace('\n', '<br>')
    doc = QTextDocument()
    doc.setDefaultFont(QToolTip.font())
    doc.setHtml(inner)
    doc.setTextWidth(-1)
    width = min(max_width, math.ceil(doc.idealWidth()) + 2)
    return f'<table width="{width}" cellspacing="0" cellpadding="0"><tr><td>{inner}</td></tr></table>'


def show(text: str, global_pos, widget: QWidget | None = None) -> None:
    QToolTip.showText(global_pos, box_html(text), widget)


def hide() -> None:
    QToolTip.hideText()


class _TipFilter(QObject):
    def eventFilter(self, obj, e):
        # Comboboxen: Mausrad ändert nur mit Fokus die Auswahl (B-09a); sonst scrollt der Bereich darunter
        if isinstance(obj, QComboBox):
            if e.type() == QEvent.Type.Show and obj.focusPolicy() != Qt.FocusPolicy.StrongFocus:
                obj.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            elif e.type() == QEvent.Type.Wheel and not obj.hasFocus():
                w = obj.parentWidget()
                while w is not None and not isinstance(w, QAbstractScrollArea):
                    w = w.parentWidget()
                if w is not None:
                    QApplication.sendEvent(w.viewport(), e)
                return True
        if e.type() == QEvent.Type.ToolTip and isinstance(obj, QWidget):
            text = obj.toolTip()
            if not text:
                return False
            if text.startswith('<table width='):           # schon verpackt
                return False
            show(text, e.globalPos(), obj)
            return True
        return False


class _TipStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return DELAY_MS
        if hint == QStyle.StyleHint.SH_ToolTip_FallAsleepDelay:
            return 0
        return super().styleHint(hint, option, widget, returnData)


_filter: _TipFilter | None = None


def install(app: QApplication) -> None:
    """Einmal je Anwendung: Verzögerung und Box-Darstellung."""
    global _filter
    if _filter is None or _filter.parent() is not app:
        _filter = _TipFilter(app)
        app.installEventFilter(_filter)
    if not app.property('_tip_style'):
        app.setStyle(_TipStyle(app.style().objectName()))
        app.setProperty('_tip_style', True)


__all__ = ['DELAY_MS', 'MAX_WIDTH', 'box_html', 'hide', 'install', 'show']
