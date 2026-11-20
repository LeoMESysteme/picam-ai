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
Bildsprache (Karten, Wertfelder, Abzeichen, Hilfezeile, Aktionsleiste) aus
``dispread.admin.widgets``, Farben aus ``dispread.admin.ui``. Nichts erfinden:
unbekannt wird „–“.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Button

from .. import probes
from ..ui import Action
from ..widgets import ActionBar, action_label


class TabView(VerticalScroll):
    TAB_ID = ''
    TITLE = ''
    KEY = ''          # Direkttaste (Ziffer) oder ''
    INFO_TITLE = ''
    #: Erklärung des Tabs (Taste i); dahinter die vollständigen Hinweise der Befunde
    #: in ``INFO_FACTS`` (auf dem Tab steht nur ihr erster Satz).
    ABOUT: tuple[str, ...] = ()
    INFO_FACTS: tuple[str, ...] = ()
    #: Eigene Aktionsleiste mit Tastenfeldern (``widgets.ActionBar``); die Tastenzeile
    #: unten nennt dann nur noch die allgemeinen Tasten.
    OWN_BAR = False
    can_focus = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.OWN_BAR:  # Inhalt scrollt in ``.tab-body``, die Aktionsleiste bleibt unten stehen
            self.add_class('own-bar')

    @property
    def INFO(self) -> tuple[str, ...]:  # noqa: N802 - Schnittstelle der App (view.INFO)
        hints = []
        for key in self.INFO_FACTS:
            fact = self.app.fact(key) if self.is_mounted else None
            if fact is not None and fact.hint:
                hints.append(f'{fact.label}: {fact.hint}' + (f' Befehl: {fact.command}' if fact.command else ''))
        return (*self.ABOUT, *hints)

    def update_view(self) -> None:
        """Inhalt aus ``self.app`` neu zeichnen (billig, oft aufgerufen)."""

    def on_resize(self, event) -> None:
        # Karten messen Zeilen selbst aus (Abzeichen rechtsbündig, Pfade gekürzt)
        if self.OWN_BAR:
            self.call_after_refresh(self.update_view)

    def card_width(self, card=None, margin: int = 6) -> int:
        """Innenbreite einer Karte (vor dem ersten Layout aus der Tab-Breite geschätzt)."""
        fallback = max(30, (self.size.width or self.app.size.width - 4) - margin)
        if card is None:
            return fallback
        width = card.content_size.width or card.size.width
        return width if width > 0 else fallback

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
        actions = self.actions()
        if self.OWN_BAR:
            # Aktionen kommen und gehen mit dem Zustand (z. B. „Abhilfe“): Knöpfe nachziehen
            for bar in self.query(ActionBar):
                have = {b.id for b in bar.query('Button.act')}
                for action in actions:
                    if f'act-{action.key}' not in have:
                        bar.mount(self.action_button(action))
                shown = {f'act-{a.key}' for a in actions}
                for button in bar.query('Button.act'):
                    button.display = button.id in shown
                bar.display = bool(actions)
        for action in actions:
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


class FactView(TabView):
    """Tab aus Befunden; bietet „Abhilfe ausführen“ an, sobald ein Befund einen Befehl dafür hat."""

    FACTS: tuple[str, ...] = ()
    OWN_BAR = True

    def on_mount(self) -> None:
        for bar in self.query(ActionBar):
            for action in self.actions():
                bar.mount(self.action_button(action))

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
