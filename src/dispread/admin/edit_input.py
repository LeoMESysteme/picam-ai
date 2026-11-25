"""Eingabefeld mit zwei Zuständen für Tabs: Navigieren (Standard) und Bearbeiten.

Im Navigationszustand ist das Feld fokussierbar und wie ein Knopf markiert, Tippen schreibt aber nichts:
↑/↓ (und ←/→) wechseln wie überall in der Konsole das Element, Enter (oder ein Mausklick) beginnt die
Bearbeitung. Im Bearbeitungszustand schreibt Tippen, ←/→/Pos1/Ende bewegen den Cursor, ↑/↓ bleiben im Feld;
Enter übernimmt (``Input.Submitted``) und kehrt zurück, Esc verwirft und kehrt zurück (das Esc wird
verbraucht und führt nicht zum Dashboard). Verliert das Feld den Fokus, wird verworfen.
Nicht für modale Dialoge und Passwortfelder, wo man direkt tippt.
"""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import Checkbox, Input

#: Hinweis für die Hilfezeile des Tabs, solange ein Feld bearbeitet wird.
EDIT_HINT = 'Enter übernehmen · Esc verwerfen'


class NavCheckbox(Checkbox):
    """Kontrollkästchen, dessen ↑/↓ in Tabs (Rollcontainer fangen sie sonst ab) das Element wechseln."""

    async def _on_key(self, event: events.Key) -> None:
        if event.key in ('up', 'down'):
            event.stop()
            event.prevent_default()
            step = getattr(self.app, 'action_focus_step', None)
            if step is not None:
                step(1 if event.key == 'down' else -1)


class EditInput(Input):
    class EditingChanged(Message):
        """Das Feld hat den Bearbeitungszustand betreten oder verlassen."""

        def __init__(self, field: EditInput, editing: bool) -> None:
            super().__init__()
            self.field = field
            self.editing = editing

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault('select_on_focus', False)
        super().__init__(*args, **kwargs)
        self.editing = False
        self._saved = self.value
        self._cursor_visible = False

    # ---------------------------------------------------------- Zustand
    def start_edit(self) -> None:
        if self.editing:
            return
        self._saved = self.value
        self.editing = True
        self.cursor_position = len(self.value)
        self._restart_blink()
        self._style_state()
        self.post_message(self.EditingChanged(self, True))

    def stop_edit(self, *, keep: bool) -> None:
        if not self.editing:
            return
        if not keep:
            self.value = self._saved
        self.editing = False
        self._cursor_visible = False
        self._style_state()
        self.post_message(self.EditingChanged(self, False))

    def _style_state(self, focused: bool | None = None) -> None:
        """Navigieren: gefüllt wie ein fokussierter Knopf; Bearbeiten: Feldfläche mit Akzentbalken.

        ``focused`` überschreibt ``has_focus``: im Blur-Ereignis meldet Textual noch den alten Fokus, das Feld
        würde sonst die Markierung neu setzen und behielte sie nach dem Fokuswechsel."""
        styles = self.styles
        for rule in ('background', 'color', 'text_style', 'border_left'):
            styles.clear_rule(rule)
        if not (self.has_focus if focused is None else focused):
            return
        variables = self.app.get_css_variables()
        accent = variables.get('picam-accent-strong', '#3d9be9')
        if self.editing:
            styles.border_left = ('wide', accent)
            styles.text_style = 'bold'
        else:
            styles.background = accent
            styles.color = variables.get('picam-on-accent', '#ffffff')
            styles.text_style = 'bold'

    # ---------------------------------------------------------- Tasten
    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == 'submit':
            return True
        return self.editing  # Cursor-/Löschbefehle nur beim Bearbeiten; sonst reicht die Konsole Pfeile weiter

    async def action_submit(self) -> None:
        if not self.editing:
            self.start_edit()
            return
        await super().action_submit()
        self.stop_edit(keep=True)

    async def _on_key(self, event: events.Key) -> None:
        if self.editing and event.key == 'escape':
            event.stop()
            event.prevent_default()
            self.stop_edit(keep=False)
            return
        if event.key in ('up', 'down'):
            event.stop()
            event.prevent_default()
            if not self.editing:  # wie überall in der Konsole: Element wechseln (↑ wie ←, ↓ wie →)
                step = getattr(self.app, 'action_focus_step', None)
                if step is not None:
                    step(1 if event.key == 'down' else -1)
            return  # im Bearbeiten: im Feld bleiben
        if not self.editing:
            event.prevent_default()  # Input-Handler (Tippen) überspringen
            # prevent_default verhindert auch die Bindungsprüfung: Tasten der Konsole (Ziffern, i, Aktionen) hier auslösen
            if await self._run_console_binding(event.key):
                event.stop()

    async def _run_console_binding(self, key: str) -> bool:
        # Textual blendet druckbare Tasten-Bindungen aus der Kette, solange ein Eingabefeld Fokus hat; die
        # Bindungen der App (Ziffern, i, g, q) hier direkt ausführen
        for binding in self.app._bindings.key_to_bindings.get(key, ()):
            if not binding.priority and await self.app.run_action(binding.action, self.app):
                return True
        return False

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        self.start_edit()
        await super()._on_mouse_down(event)

    # ---------------------------------------------------------- Cursor nur beim Bearbeiten
    def _toggle_cursor(self) -> None:
        if self.editing:
            super()._toggle_cursor()
        else:
            self._cursor_visible = False

    def _restart_blink(self) -> None:
        super()._restart_blink()
        if not self.editing:
            self._cursor_visible = False

    def _on_focus(self, event: events.Focus) -> None:
        super()._on_focus(event)
        self._style_state()

    def _on_blur(self, event: events.Blur) -> None:
        self.stop_edit(keep=False)
        super()._on_blur(event)
        self._style_state(focused=False)

    def _on_paste(self, event: events.Paste) -> None:
        if self.editing:
            super()._on_paste(event)
