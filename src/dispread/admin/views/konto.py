"""Tab Konto: Anmeldung an der Werkbank, Gruppen und Benutzerdienst."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from .. import probes
from ..ui import ACCENT, MUTED, TONE, Action, Segment, fact_title, hint_block, symbol
from .base import FactView, actions_segment

GROUP_WHY = (('video', 'Kamera (/dev/video…)'), ('dialout', 'serielle Schnittstelle (/dev/ttyAMA0)'))


class KontoView(FactView):
    TAB_ID, TITLE, KEY = 'konto', 'Konto', '0'
    FACTS = ('konto', 'linger')
    INFO_TITLE = 'Konto und Anmeldung'
    INFO = ('An der Werkbank im Browser meldet man sich mit dem Linux-Konto des Dienstes an, mit dessen '
            'Linux-Passwort. Es gibt kein eigenes Werkbank-Passwort.',
            'Passwort ändern: im Terminal passwd eingeben. Das gilt dann auch für die SSH-Anmeldung. '
            'Die Konsole speichert und ändert keine Passwörter.',
            'Das Konto braucht die Gruppen video (Kamera) und dialout (UART).')

    DEFAULT_CSS = """
    KontoView #kt-login { margin: 1 0 0 0; padding: 0 1; border-left: wide $primary; background: $picam-tint-info;
                          max-width: 110; }
    """

    def compose(self):
        yield Static(Text(self.TITLE, style='bold'), classes='title')
        yield Static(id='kt-login')
        yield Segment('Gruppen', Static(id='kt-groups'), Static(id='f-konto-hint', classes='hint'))
        yield Segment(None, *self.fact_widgets('linger'))
        yield Segment('Passwort ändern', Static(id='kt-passwd'))
        yield actions_segment()

    def actions(self) -> list[Action]:
        return super().actions() + [Action('p', 'Passwort ändern', lambda: None,
                                           blocked='im Terminal mit passwd, nicht in der Konsole')]

    def _user(self) -> str | None:
        user = self.app.instance.pam_user
        if user:
            return user
        fact = self.app.fact('konto')
        return dict(fact.detail).get('Konto') if fact is not None else None

    def update_view(self) -> None:
        user = self._user()
        login = Text()
        login.append('Anmeldung an der Werkbank\n', style='bold')
        login.append('Benutzer ', style=MUTED)
        login.append(user or '–', style=f'bold {ACCENT}')
        login.append(' mit dem Linux-Passwort dieses Kontos', style='bold')
        login.append('\nEin eigenes Werkbank-Passwort gibt es nicht.', style=MUTED)
        self.query_one('#kt-login', Static).update(login)
        fact = self.app.fact('konto')
        groups = self.query_one('#kt-groups', Static)
        hint = self.query_one('#f-konto-hint', Static)
        if fact is None:
            groups.update(Text('Wird geprüft …', style=MUTED))
            hint.display = False
        else:
            have = {g.strip() for g in dict(fact.detail).get('Gruppen', '').split(',')}
            table = Table.grid(padding=(0, 2))
            table.add_column(no_wrap=True)
            table.add_column(overflow='fold')
            for name, why in GROUP_WHY:
                level = probes.OK if name in have else probes.FAIL
                cell = Text()
                cell.append(f'{symbol(level)} ', style=TONE[level])
                cell.append(name, style='bold')
                table.add_row(cell, Text(why + ('' if level == probes.OK else '  fehlt'), style=MUTED))
            groups.update(table)
            block = hint_block(fact)
            hint.display = block is not None and fact.level in (probes.WARN, probes.FAIL)
            if hint.display:
                hint.update(block)
                hint.set_class(fact.level == probes.FAIL, 'fail')
        linger = self.app.fact('linger')
        title = self.query_one('#f-linger-title', Static)
        lhint = self.query_one('#f-linger-hint', Static)
        detail = self.query_one('#f-linger-detail', Static)
        for widget in (title, lhint, detail):
            widget.display = linger is not None
        if linger is not None:
            title.update(fact_title(linger))
            block = hint_block(linger)
            lhint.display = block is not None
            if block is not None:
                lhint.update(block)
            detail.update(Text('Benutzerdienst: läuft nach dem Abmelden weiter und startet beim Booten.',
                               style=MUTED))
        passwd = Text()
        passwd.append('passwd', style=f'bold {ACCENT}')
        passwd.append(' im Terminal eingeben. Das ändert auch die SSH-Anmeldung dieses Kontos. '
                      'Die Konsole ändert keine Passwörter.', style='')
        self.query_one('#kt-passwd', Static).update(passwd)
        self.sync_buttons()
