"""Tab Dienst: Zustand der Werkbank-Unit, Version und die Dienstaktionen."""

from __future__ import annotations

from .. import probes
from ..ui import Action
from ..widgets import (
    ActionBar,
    SectionCard,
    TabBody,
    badge,
    fact_badge,
    fact_help,
    fields,
    header,
    help_line,
    join,
    value,
)
from .base import FactView

DASH = '–'
#: Zeilen des Dienstes in dieser Reihenfolge (paarweise, wenn die Breite reicht).
ROWS = ('Unit', 'Art', 'Autostart', 'PID', 'Seit')
WIDE = ('Ergebnis', 'Grund')


class DienstView(FactView):
    TAB_ID, TITLE, KEY = 'dienst', 'Dienst', '3'
    FACTS = ()
    INFO_TITLE = 'Was ist der Dienst?'
    ABOUT = ('Der Dienst ist die Werkbank selbst: ein Hintergrundprogramm (systemd), das die Kamera hält, '
             'die Weboberfläche ausliefert und die Werte an GSVmulti weitergibt. Er startet beim Hochfahren '
             'des Pi von selbst, wenn „Autostart“ auf „ja“ steht.',
             'Stoppen oder Neustarten unterbricht verbundene Browser und die Windows-Brücke kurz; Stoppen '
             'lässt die Werkbank aus, bis jemand sie wieder startet. Während eines Laufs, einer Einrichtung '
             'oder einer Diagnosekopie ist beides gesperrt, damit keine Messung verloren geht.',
             'Update installiert eine neue Version neben der laufenden und schaltet erst nach einem '
             'Selbsttest um. „Zurück“ schaltet auf die vorige Version zurück.')
    INFO_FACTS = ('dienst',)

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='dienst-card')
            yield SectionCard(id='dienst-version')
        yield ActionBar()

    def update_view(self) -> None:
        app = self.app
        card = self.query_one('#dienst-card', SectionCard)
        width = self.card_width(card)
        columns = 2 if width >= 60 else 1
        service = app.fact('dienst')
        rows: list = []
        if service is not None:
            detail = dict(service.detail)
            for key in ROWS:
                if key == 'Autostart' and detail.get(key):
                    on = detail[key] == 'ja'
                    rows.append((key, badge(probes.OK if on else probes.OFF, detail[key], 'on' if on else 'off')))
                else:
                    rows.append((key, value(detail.get(key)), key in WIDE))
            rows += [(k, value(v), k in WIDE) for k, v in service.detail if k not in ROWS and k != 'Steuerung']
        reason = self._stop_reason()
        if reason is not None:
            rows.append(('Stoppen', join(badge(probes.WARN, 'gesperrt'), f'  auch Neustart · {reason}'), True))
        if service is not None and service.hint:
            hint = fact_help(service)
        else:
            hint = help_line('Der Dienst ist die Werkbank selbst.', 'i', 'mehr')
        card.show(header('service', 'Werkbank-Dienst', fact_badge(service), width),
                  fields(rows, width, label_w=12, columns=columns), hint)

        version = app.fact('version')
        info = dict(version.detail) if version is not None else {}
        rows = [('Version', value(version.value if version is not None else None)),
                ('Commit', value(info.get('Commit'))), ('Vorige', value(info.get('Vorige'))),
                ('Ort', value(info.get('Ort') or app.instance.root), True)]
        right = None if version is None else badge(probes.OFF, 'installiert' if app.installed() else 'Entwicklung',
                                                   'version')
        self.query_one('#dienst-version', SectionCard).show(
            header('version', 'Version', right, width), fields(rows, width, label_w=12, columns=columns),
            help_line('Update schaltet erst nach einem Selbsttest um.') if app.installed() else None)
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
                   blocked=blocked, danger=running, icon='stop' if running else 'start'),
            Action('r', 'Neu starten', lambda: app.service_action('restart'), blocked=blocked, icon='restart'),
        ]
        if app.installed():
            actions.append(Action('u', 'Update', app.start_update, blocked=app.blocker, icon='update'))
            version = app.fact('version')
            has_previous = version is not None and any(k == 'Vorige' and v for k, v in version.detail)
            actions.append(Action('z', 'Zurück', app.start_rollback, icon='back',
                                  blocked=app.blocker or (None if has_previous else 'keine vorige Version')))
        actions.append(Action('l', 'Protokoll', lambda: app.open_tab('protokoll'), icon='log'))
        return actions
