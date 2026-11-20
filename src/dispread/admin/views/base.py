"""Grundlage der Tabs der picam-Konsole.

Ein Tab ist ein ``TabView`` (scrollbarer Container). Die App ruft
``update_view()`` nach jeder Prüfung und beim Anzeigen auf; ``actions()``
liefert die Aktionen des Tabs (Taste, Beschriftung, Aufruf, Sperrgrund). Die
Tastenleiste zeigt sie, die App leitet die Tasten weiter, und Knöpfe im Tab
rufen dieselben Aktionen auf (``action_button``).

Was ein Tab von der App benutzen darf (``self.app``):

- Daten: ``snapshot`` (``probes.Snapshot`` oder None), ``fact(key)``,
  ``instance``, ``metrics`` (``probes.system_metrics``), ``storage``
  (``probes.storage_usage`` oder None, langsam), ``network``
  (``probes.network_info`` oder None), ``log_lines``, ``problems()``,
  ``blocker`` (Grund, warum Dienst-/Kameraaktionen gesperrt sind),
  ``installed()``.
- Aktionen (alle mit Bestätigung, sofern gefährlich): ``service_action``
  ('start'|'stop'|'restart'), ``socket_action(op, title, lines, label, …)``,
  ``run_fix(fact)``, ``start_update()``, ``start_rollback()``,
  ``show_info(title, lines)``, ``open_tab(tab_id)``, ``message(level, text)``,
  ``run_cli(argv, title)``.

Darstellung: stabile Widgets in ``compose`` anlegen und in ``update_view``
nur ihren Inhalt ersetzen (``Static.update``); kein Neuaufbau je Prüfung.
Farben und Bausteine aus ``dispread.admin.ui``. Nichts erfinden: unbekannt
wird „–“.
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static

from .. import probes
from ..ui import ACCENT, MUTED, Action, Segment, fact_title, hint_block, kv_table
from ..widgets import ActionBar, action_label


class TabView(VerticalScroll):
    TAB_ID = ''
    TITLE = ''
    KEY = ''          # Direkttaste (Ziffer) oder ''
    INFO_TITLE = ''
    INFO: tuple[str, ...] = ()
    #: Eigene Aktionsleiste mit Tastenfeldern (neue Bildsprache, ``widgets``); die
    #: Tastenzeile unten nennt dann nur noch die allgemeinen Tasten.
    OWN_BAR = False
    can_focus = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.OWN_BAR:  # Inhalt scrollt in ``.tab-body``, die Aktionsleiste bleibt unten stehen
            self.add_class('own-bar')

    def update_view(self) -> None:
        """Inhalt aus ``self.app`` neu zeichnen (billig, oft aufgerufen)."""

    def on_resize(self, event) -> None:
        # Neue Bildsprache misst Zeilen selbst aus (Abzeichen rechtsbündig, Pfade gekürzt)
        if self.OWN_BAR:
            self.call_after_refresh(self.update_view)

    def actions(self) -> list[Action]:
        return []

    # Knöpfe: id 'act-<taste>' ruft die gleichnamige Aktion auf
    def button_label(self, action: Action):
        return action_label(action) if self.OWN_BAR else action.label

    def action_button(self, action: Action) -> Button:
        button = Button(self.button_label(action), id=f'act-{action.key}',
                        variant='error' if action.danger else 'default', classes='act')
        button.disabled = action.blocked is not None
        button.tooltip = action.blocked
        return button

    def sync_buttons(self) -> None:
        for action in self.actions():
            for button in self.query(f'#act-{action.key}'):
                button.disabled = action.blocked is not None
                button.tooltip = action.blocked
                button.label = self.button_label(action)
        if self.OWN_BAR:
            for bar in self.query(ActionBar):
                bar.fit(self.size.width - 5)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not (event.button.id or '').startswith('act-'):
            return
        key = event.button.id[4:]
        for action in self.actions():
            if action.key == key and action.blocked is None:
                event.stop()
                action.run()
                return


def actions_segment(*children) -> Segment:
    """Abschnitt mit den Knöpfen eines Tabs (ohne Kopf); hebt sich hervor, solange ein Knopf den Fokus hat."""
    return Segment(None, *children, Horizontal(id='buttons', classes='buttons'), classes='actions')


def key_hint(key: str, label: str) -> Text:
    text = Text()
    text.append(key, style=f'bold {ACCENT}')
    text.append(f' {label}', style=MUTED)
    return text


class FactView(TabView):
    """Tab aus Befunden: Titel, Abhilfe, Details je Befund, darunter Knöpfe."""

    FACTS: tuple[str, ...] = ()

    def compose(self):
        yield Static(Text(self.TITLE, style='bold'), classes='title')
        for key in self.FACTS:
            with Segment():
                yield from self.fact_widgets(key)
        yield actions_segment()

    @staticmethod
    def fact_widgets(key: str):
        """Titel, Abhilfe und Details eines Befunds (Inhalt eines Abschnitts)."""
        yield Static(id=f'f-{key}-title', classes='fact-title')
        yield Static(id=f'f-{key}-hint', classes='hint')
        yield Static(id=f'f-{key}-detail')

    def on_mount(self) -> None:
        bar = self.query_one('#buttons', Horizontal)
        for action in self.actions():
            bar.mount(self.action_button(action))

    def update_view(self) -> None:
        for key in self.FACTS:
            fact = self.app.fact(key)
            title = self.query_one(f'#f-{key}-title', Static)
            hint = self.query_one(f'#f-{key}-hint', Static)
            detail = self.query_one(f'#f-{key}-detail', Static)
            if fact is None:
                title.update(Text(probes_label(key), style='bold'))
                hint.display = False
                detail.update(Text('Wird geprüft …', style=MUTED))
                continue
            title.update(fact_title(fact))
            block = hint_block(fact)
            hint.display = block is not None
            if block is not None:
                hint.update(block)
                hint.set_class(fact.level == probes.FAIL, 'fail')
                hint.set_class(fact.level not in (probes.FAIL, probes.WARN), 'info')
            detail.update(kv_table(fact.detail) if fact.detail else Text(''))
        self.sync_buttons()

    def actions(self) -> list[Action]:
        actions = []
        for key in self.FACTS:
            fact = self.app.fact(key)
            if fact is not None and fact.command and fact.level in (probes.WARN, probes.FAIL):
                actions.append(Action('a', 'Abhilfe ausführen', lambda f=fact: self.app.run_fix(f), icon='fix'))
                break
        return actions


LABELS = {'dienst': 'Dienst', 'lauf': 'Lauf', 'kamera': 'Kamera', 'ausgabe': 'Ausgabe',
          'bruecke': 'Brücke', 'zertifikat': 'Zertifikat', 'speicher': 'Speicher',
          'netzwerk': 'Netzwerk', 'vorlage': 'Lesevorlage', 'kalibrierung': 'Kalibrierung', 'uart': 'UART',
          'konto': 'Konto', 'linger': 'Nach Abmeldung', 'uhr': 'Uhrzeit', 'version': 'Version'}


def probes_label(key: str) -> str:
    return LABELS.get(key, key)
