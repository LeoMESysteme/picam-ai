"""Tab Dienst: Zustand der Werkbank-Unit, Version und die Dienstaktionen."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

from .. import probes
from ..ui import MUTED, TONE, Action, fact_title, hint_block, kv_table, section, symbol
from .base import FactView

DASH = '–'


class DienstView(FactView):
    TAB_ID, TITLE, KEY = 'dienst', 'Dienst', '3'
    FACTS = ()
    INFO_TITLE = 'Was ist der Dienst?'
    INFO = ('Der Dienst ist die Werkbank selbst: ein Hintergrundprogramm (systemd), das die Kamera hält, '
            'die Weboberfläche ausliefert und die Werte an GSVmulti weitergibt. Er startet beim Hochfahren '
            'des Pi von selbst, wenn „Autostart“ auf „ja“ steht.',
            'Stoppen oder Neustarten unterbricht verbundene Browser und die Windows-Brücke kurz; Stoppen '
            'lässt die Werkbank aus, bis jemand sie wieder startet. Während eines Laufs, einer Einrichtung '
            'oder einer Diagnosekopie ist beides gesperrt, damit keine Messung verloren geht.',
            'Update installiert eine neue Version neben der laufenden und schaltet erst nach einem '
            'Selbsttest um. „Zurück“ schaltet auf die vorige Version zurück.')
    SCOPED_CSS = False
    DEFAULT_CSS = """
    DienstView .blocked { border-left: wide $warning; padding: 0 1; margin: 1 0 0 0; background: #16140f;
                          max-width: 110; }
    Screen.stacked DienstView .buttons { layout: grid; grid-size: 2; grid-gutter: 0 1; grid-rows: 1; }
    Screen.stacked DienstView .buttons Button { width: 100%; margin: 0; }
    """

    def compose(self):
        yield Static(id='dienst-state', classes='fact-title first')
        yield Static(id='dienst-hint', classes='hint')
        yield Static(id='dienst-blocked', classes='blocked')
        yield Static(id='dienst-rows')
        yield section('Version')
        yield Static(id='dienst-version')
        yield Horizontal(id='buttons', classes='buttons')

    def update_view(self) -> None:
        app = self.app
        service = app.fact('dienst')
        state, hint = self.query_one('#dienst-state', Static), self.query_one('#dienst-hint', Static)
        if service is None:
            state.update(Text('Dienst', style='bold'))
            hint.display = False
            self.query_one('#dienst-rows', Static).update(Text('Wird geprüft …', style=MUTED))
        else:
            state.update(fact_title(service))
            block = hint_block(service)
            hint.display = block is not None
            if block is not None:
                hint.update(block)
                hint.set_class(service.level == probes.FAIL, 'fail')
            detail = dict(service.detail)
            rows = [(key, detail.get(key) or DASH) for key in ('Unit', 'Art', 'Autostart', 'Seit', 'PID')]
            rows += [(k, v) for k, v in service.detail if k not in dict(rows) and k not in ('Steuerung',)]
            self.query_one('#dienst-rows', Static).update(kv_table(rows))
        blocked = self.query_one('#dienst-blocked', Static)
        reason = self._stop_reason()
        blocked.display = reason is not None
        if reason is not None:
            text = Text()
            text.append(f'{symbol(probes.WARN)} Stoppen und Neustarten gesperrt: ', style=f'bold {TONE[probes.WARN]}')
            text.append(reason)
            blocked.update(text)
        version = app.fact('version')
        info = dict(version.detail) if version is not None else {}
        rows = [('Version', version.value if version is not None else DASH),
                ('Commit', info.get('Commit') or DASH), ('Vorige', info.get('Vorige') or DASH),
                ('Ort', info.get('Ort') or app.instance.root or DASH)]
        self.query_one('#dienst-version', Static).update(kv_table(rows))
        self.sync_buttons()

    def _service_running(self) -> bool:
        service = self.app.fact('dienst')
        return service is not None and service.level in (probes.OK, probes.WARN)

    def _stop_reason(self) -> str | None:
        return self.app.blocker if self._service_running() and self.app.instance.unit is not None else None

    def actions(self) -> list[Action]:
        app = self.app
        running = self._service_running()
        blocked = self._stop_reason()
        if app.snapshot is None:
            blocked = 'Laufstatus noch nicht geprüft'
        if app.instance.unit is None:
            blocked = 'kein Dienst eingerichtet (portabel)'
        actions = [
            Action('s', 'Stoppen' if running else 'Starten',
                   lambda: app.service_action('stop' if running else 'start'),
                   blocked=blocked, danger=running),
            Action('r', 'Neu starten', lambda: app.service_action('restart'), blocked=blocked),
        ]
        if app.installed():
            actions.append(Action('u', 'Update', app.start_update, blocked=app.blocker))
            version = app.fact('version')
            has_previous = version is not None and any(k == 'Vorige' and v for k, v in version.detail)
            actions.append(Action('z', 'Zurück', app.start_rollback,
                                  blocked=app.blocker or (None if has_previous else 'keine vorige Version')))
        actions.append(Action('l', 'Protokoll', lambda: app.open_tab('protokoll')))
        return actions
