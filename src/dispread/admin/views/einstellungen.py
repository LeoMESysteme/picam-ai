"""Einstellungen: änderbare Werte mit Risiko, Orte von Daten und Protokoll."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys

from rich.text import Text
from textual import on, work
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Static

from .. import probes
from ..ui import MUTED, TONE, Action, Confirmation, ConfirmScreen, kv_table, section
from .base import TabView

#: Änderbare Felder: Beschriftung, Risiko (Stufe, Erklärung).
FIELDS = {
    'port': ('Port der Werkbank (1–65535)',
             (probes.WARN, 'mittel – Lesezeichen, gekoppelte Brücken und Firewall-Regeln brauchen danach '
                           'die neue Adresse')),
    'bridge_name': ('Name des Pi in der Windows-Brücke',
                    (probes.OK, 'gering – nur die Anzeige in der Windows-App ändert sich')),
    'bridge_discovery': ('Im Netzwerk ankündigen (Windows-App findet den Pi selbst)',
                         (probes.OK, 'gering – aus: die Brücke muss die Adresse von Hand kennen')),
}
RISK_WORD = {probes.OK: 'Risiko', probes.WARN: 'Risiko'}


class EinstellungenView(TabView):
    TAB_ID, TITLE, KEY = 'einstellungen', 'Einstellungen', 'c'
    INFO_TITLE = 'Einstellungen'
    INFO = ('Nur wenige Werte sind hier änderbar; alles andere legt die Installation fest. Jede Änderung '
            'wird vor dem Speichern geprüft und wirkt nach einem Neustart des Dienstes.',
            'Die Adresse steht im Zertifikat und in den Kopplungen und wird nur bei einer Neuinstallation '
            'gewählt.')

    def compose(self):
        yield Static(Text('Einstellungen', style='bold'), classes='title')
        yield Static(id='cfg-intro', classes='hint info')
        yield Vertical(id='cfg-fields')
        yield section('Orte')
        yield Static(id='cfg-paths')
        yield Horizontal(id='buttons', classes='buttons')

    def on_mount(self) -> None:
        self._build_fields()
        bar = self.query_one('#buttons', Horizontal)
        for action in self.actions():
            bar.mount(self.action_button(action))

    def _build_fields(self) -> None:
        from .. import configedit

        inst = self.app.instance
        box = self.query_one('#cfg-fields', Vertical)
        box.remove_children()
        intro = self.query_one('#cfg-intro', Static)
        if inst.config is None:
            intro.update(Text('Entwicklungsbetrieb: Die Werte stammen aus dem Startbefehl des Dienstes '
                              '(scripts/werkbank-dienst.sh). Eine installierte Werkbank hat dafür eine '
                              'config.toml, die hier änderbar ist.'))
            return
        intro.update(Text(f'Datei {inst.config}. Wirksam nach einem Neustart des Dienstes.'))
        for key in configedit.EDITABLE:
            label, (level, risk) = FIELDS[key]
            current = getattr(inst, key)
            field = Vertical(classes='field')
            field.compose_add_child(Static(label, classes='field-label'))
            if key == 'bridge_discovery':
                field.compose_add_child(Checkbox('angekündigt', value=bool(current), id=f'cfg-{key}'))
            else:
                field.compose_add_child(Input(value='' if current is None else str(current), id=f'cfg-{key}',
                                              placeholder='nicht gesetzt'))
            field.compose_add_child(Static(Text(risk, style=TONE[level] if level != probes.OK else MUTED),
                                           classes='field-risk'))
            box.mount(field)

    def update_view(self) -> None:
        inst = self.app.instance
        rows = [('Konfiguration', inst.config or '– (Startbefehl des Dienstes)'),
                ('Adresse', inst.url or '–'),
                ('Anmeldung', f'{inst.pam_user or "Konto des Dienstes"} mit dessen Linux-Passwort'),
                ('Daten', inst.data or '–'), ('Laufdaten', inst.live_data or '–'),
                ('Brücke', inst.bridge_directory or '–'), ('Steuerung', inst.socket or '–'),
                ('Protokoll', f'journald, Unit {inst.unit or "–"} (picam logs)'),
                ('Programm', inst.root or '–')]
        self.query_one('#cfg-paths', Static).update(kv_table(rows))
        self.sync_buttons()

    def focus_first(self) -> None:
        for widget in self.query('#cfg-port'):
            widget.focus()

    def actions(self) -> list[Action]:
        inst = self.app.instance
        actions = [Action('p', 'Änderung prüfen …', self.check,
                          blocked=None if inst.config else 'keine config.toml (Entwicklungsbetrieb)')]
        actions.append(Action('x', 'Deinstallieren …', self.app.start_uninstall,
                              blocked=self.app.uninstall_blocker()))
        return actions

    @on(Input.Submitted)
    def _submitted(self) -> None:
        self.check()

    def check(self) -> None:
        self._config_flow()

    @work(exclusive=True, group='config')
    async def _config_flow(self) -> None:
        from .. import configedit

        app = self.app
        inst = app.instance
        if inst.config is None:
            return
        proposals = []
        for key in configedit.EDITABLE:
            widget = self.query_one(f'#cfg-{key}')
            raw = ('true' if widget.value else 'false') if isinstance(widget, Checkbox) else widget.value
            current = getattr(inst, key)
            if key != 'bridge_discovery' and raw.strip() == ('' if current is None else str(current)):
                continue
            if key == 'bridge_discovery' and bool(widget.value) == bool(current):
                continue
            proposals.append((key, raw))
        if not proposals:
            app.message(probes.OFF, 'Keine Änderung.')
            return
        if len(proposals) > 1:
            app.message(probes.WARN, 'Bitte ein Feld nach dem anderen ändern.')
            return
        key, raw = proposals[0]
        try:
            new_text, changes = configedit.propose(inst.config, key, raw)
        except (ValueError, OSError) as error:
            app.message(probes.FAIL, str(error))
            return
        level, risk = FIELDS[key][1]
        writable = os.access(inst.config, os.W_OK)
        lines = [c.text for c in changes] + [f'Risiko: {risk}.', 'Wirksam nach einem Neustart des Dienstes (r).']
        if not writable:
            lines.append('Die Datei gehört root: picam führt die Änderung mit sudo aus.')
        command = f'picam config set {key} {shlex.quote(raw)}'
        ok = await app.push_screen_wait(ConfirmScreen(Confirmation(
            'Einstellung ändern', lines, [command] if not writable else [], 'Übernehmen',
            danger=level != probes.OK)))
        if not ok:
            return
        if writable:
            try:
                configedit.apply(inst.config, new_text)
            except OSError as error:
                app.message(probes.FAIL, str(error))
                return
            code = 0
        else:
            sudo = ['sudo', sys.executable, '-m', 'dispread.admin.cli', '--config', inst.config,
                    'config', 'set', key, raw, '--yes']
            with app.suspend():
                code = subprocess.call(sudo)
        if code == 0:
            from ..instance import discover

            app.instance = discover(inst.config)
            self._build_fields()
            self.update_view()
            app.message(probes.OK, 'Gespeichert. Mit r neu starten, damit es wirkt.')
        else:
            app.message(probes.FAIL, f'Nicht gespeichert (Exit {code}).')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        super().on_button_pressed(event)
