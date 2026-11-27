"""Einstellungen: änderbare Werte mit Risiko, Orte von Daten und Protokoll."""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys

from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.containers import Vertical
from textual.widgets import Button, Checkbox, Input, Static

from .. import probes, sensor_client
from ..edit_input import EDIT_HINT, EditInput, NavCheckbox
from ..ui import MUTED, Action, Confirmation, ConfirmScreen
from ..widgets import (
    ActionBar,
    CardBox,
    SectionCard,
    TabBody,
    badge,
    fields,
    header,
    help_line,
    join,
    value,
)
from .base import TabView

#: Änderbare Felder: Beschriftung, Risiko (Stufe, Erklärung).
FIELDS = {
    'port': ('Port der Werkbank (1–65535)',
             (probes.WARN, 'mittel – Lesezeichen, gekoppelte Brücken und Firewall-Regeln brauchen danach '
                           'die neue Adresse')),
    'bridge_name': ('Name des Pi in der Windows-Brücke',
                    (probes.OK, 'gering – die Windows-Brücke (ab 1.1.0) zeigt den neuen Namen nach einem '
                                'Dienstneustart; UART über Brücke danach neu vorbereiten')),
    'bridge_discovery': ('Im Netzwerk ankündigen (Windows-App findet den Pi selbst)',
                         (probes.OK, 'gering – aus: die Brücke muss die Adresse von Hand kennen')),
}


def risk_text(level: str, risk: str) -> Table:
    """Risiko als Abzeichen („Risiko mittel“), die Begründung gedämpft daneben (bricht in ihrer Spalte um).

    Geringes Risiko bleibt grau: grün hieße „in Ordnung“, nicht „wenig Folgen“.
    """
    word, _, why = risk.partition(' – ')
    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True)
    table.add_column(ratio=1)
    table.add_row(badge(level if level != probes.OK else probes.OFF, f'Risiko {word}',
                        'warn' if level != probes.OK else 'off'), Text(why, style=MUTED))
    return table


FEATURE_RISK = ('schaltet den Tab „Sensoren“ mit KI-Assistent, Katalog und Einreichung frei; der Messpfad '
                'mit mitgelieferten Sensoren bleibt unverändert')


class EinstellungenView(TabView):
    TAB_ID, TITLE, KEY = 'einstellungen', 'Einstellungen', 'c'
    INFO_TITLE = 'Einstellungen'
    OWN_BAR = True
    ABOUT = ('Nur wenige Werte sind hier änderbar; alles andere legt die Installation fest. Jede Änderung '
            'wird vor dem Speichern geprüft und wirkt nach einem Neustart des Dienstes.',
            'Die Adresse steht im Zertifikat und in den Kopplungen und wird nur bei einer Neuinstallation '
            'gewählt.')

    DEFAULT_CSS = 'EinstellungenView #cfg-fields { height: auto; }'

    def compose(self):
        self._feature_state = sensor_client.feature_enabled(self.app.instance)
        with TabBody(classes='tab-body'):
            with CardBox(id='cfg-values'):
                yield Static(id='cfg-head')
                yield Static(id='cfg-intro')
                yield Vertical(id='cfg-fields')
                yield Static(id='cfg-help')
            with CardBox(id='cfg-experimental'):
                yield Static(id='cfg-exp-head')
                with Vertical(classes='field'):
                    yield Static('KI-Sensoreinrichtung und Marktplatz', classes='field-label')
                    yield NavCheckbox('eingeschaltet', value=self._feature_state, id='cfg-feature')
                    yield Static(risk_text(probes.WARN, 'mittel – ' + FEATURE_RISK), classes='field-risk')
            yield SectionCard(id='cfg-paths')
        yield ActionBar()

    def on_mount(self) -> None:
        self._build_fields()
        bar = self.query_one(ActionBar)
        for action in self.actions():
            bar.mount(self.action_button(action))

    def _build_fields(self) -> None:
        from .. import configedit

        inst = self.app.instance
        box = self.query_one('#cfg-fields', Vertical)
        box.remove_children()
        if inst.config is None:
            return
        for key in configedit.EDITABLE:
            label, (level, risk) = FIELDS[key]
            current = getattr(inst, key)
            field = Vertical(classes='field')
            field.compose_add_child(Static(label, classes='field-label'))
            if key == 'bridge_discovery':
                field.compose_add_child(NavCheckbox('angekündigt', value=bool(current), id=f'cfg-{key}'))
            else:
                field.compose_add_child(EditInput(value='' if current is None else str(current), id=f'cfg-{key}',
                                              placeholder='nicht gesetzt'))
            field.compose_add_child(Static(risk_text(level, risk), classes='field-risk'))
            box.mount(field)

    def update_view(self) -> None:
        inst = self.app.instance
        card = self.query_one('#cfg-paths', SectionCard)
        width = self.card_width(card)
        if inst.config is None:
            state = badge(probes.OFF, 'Entwicklungsbetrieb', 'off')
            hint = help_line('Eine installierte Werkbank hat dafür eine config.toml, die hier änderbar ist.')
        else:
            state = badge(probes.OFF, 'wirkt nach Neustart', 'restart')
            hint = help_line('Jede Änderung wird vor dem Speichern geprüft.', 'i', 'mehr')
        self.query_one('#cfg-head', Static).update(header('values', 'Änderbare Werte', state, width))
        if inst.config is None:
            intro = Text('Die Werte stammen aus dem Startbefehl des Dienstes (scripts/werkbank-dienst.sh).',
                         style=MUTED)
        else:
            intro = fields([('Datei', value(inst.config), True)], width, label_w=8)
        self.query_one('#cfg-intro', Static).update(intro)
        self.query_one('#cfg-exp-head', Static).update(
            header('values', 'Experimentell', badge(probes.OFF, 'jederzeit umschaltbar', 'off'), width))
        self._hint = hint
        self._show_hint(width)
        config = value(inst.config) if inst.config else join(value(None), '  Startbefehl des Dienstes')
        rows = [('Konfiguration', config, True),
                ('Adresse', value(inst.url), True),
                ('Anmeldung', join(value(inst.pam_user or 'Konto des Dienstes'), '  mit dessen Linux-Passwort'), True),
                ('Daten', value(inst.data), True), ('Laufdaten', value(inst.live_data), True),
                ('Brücke', value(inst.bridge_directory), True), ('Steuerung', value(inst.socket), True),
                ('Protokoll', join(value('journald'), f'  Unit {inst.unit or "–"} (picam logs)'), True),
                ('Programm', value(inst.root), True)]
        card.show(header('file', 'Orte', None, width), fields(rows, width, label_w=15),
                  help_line('Die Adresse wird nur bei einer Neuinstallation gewählt.'))
        self.sync_buttons()

    def _show_hint(self, width: int | None = None) -> None:
        """Hilfezeile: beim Bearbeiten eines Feldes der Tastenhinweis, sonst die Standardzeile."""
        card = self.query_one('#cfg-values')
        width = width or self.card_width(card)
        editing = any(f.editing for f in self.query(EditInput))
        text = help_line(EDIT_HINT) if editing else getattr(self, '_hint', None)
        if text is not None:
            self.query_one('#cfg-help', Static).update(text.fitted(width))

    @on(EditInput.EditingChanged)
    def _editing_changed(self, event: EditInput.EditingChanged) -> None:
        event.stop()
        self._show_hint()

    def focus_first(self) -> None:
        """Erster Fokus im Navigationszustand (Feld markiert, Tippen schreibt nichts)."""
        for widget in self.query('#cfg-port'):
            widget.focus()

    def actions(self) -> list[Action]:
        inst = self.app.instance
        actions = [Action('p', 'Änderung prüfen …', self.check, icon='check',
                          blocked=None if inst.config else 'keine config.toml (Entwicklungsbetrieb)')]
        actions.append(Action('e', 'Einrichtung erneut …', self.app.open_onboarding, icon='setup'))
        actions.append(Action('x', 'Deinstallieren …', self.app.start_uninstall, icon='remove',
                              blocked=self.app.uninstall_blocker()))
        return actions

    @on(Checkbox.Changed, '#cfg-feature')
    def _feature_changed(self, event: Checkbox.Changed) -> None:
        event.stop()
        if bool(event.value) == self._feature_state:   # zurückgestellt oder schon so
            return
        self._feature_flow(bool(event.value))

    @work(exclusive=True, group='feature')
    async def _feature_flow(self, want: bool) -> None:
        app = self.app
        box = self.query_one('#cfg-feature', Checkbox)

        def revert() -> None:
            box.value = self._feature_state

        lines = ['Experimentell: KI-Sensoreinrichtung und Marktplatz '
                 + ('einschalten.' if want else 'ausschalten.'),
                 'Der Tab „Sensoren“ erscheint.' if want else 'Der Tab „Sensoren“ verschwindet; '
                 'mitgelieferte Sensoren bleiben nutzbar.',
                 'Der Messpfad mit dem mitgelieferten Sensor gsv2as-161a ändert sich nicht.']
        if want:
            lines.append('Einreichen sendet Paketdateien (keine Bilder) an das Firmen-Forgejo.')
        ok = await app.push_screen_wait(ConfirmScreen(Confirmation(
            'Experimentellen Schalter ändern', lines, [], 'Einschalten' if want else 'Ausschalten')))
        if not ok:
            revert()
            return
        done, message, restart = await asyncio.to_thread(sensor_client.set_feature, app.instance, want)
        if not done:
            revert()
            app.message(probes.FAIL, message)
            return
        self._feature_state = want
        app.sync_feature_tabs()
        app.message(probes.OK, message + (' Wirksam nach Neustart der Konsole/Werkbank.' if restart else ''))

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
