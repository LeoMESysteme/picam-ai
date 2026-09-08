"""Tastaturbediente Einrichtung im echten Terminal.

Zeilen, Optionen und Aktionen kommen aus `fields.py` - dieselbe Quelle, aus
der der setup-Tab der Weboberflaeche rendert. Gibt es hier eine Auswahlliste,
gibt es sie dort auch.
"""

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from .cli import request
from .fields import actions, rows

DIALOG_CSS = "#dialog {width: 72; height: auto; max-height: 20; border: solid gray; padding: 1;}"


class ChoiceScreen(ModalScreen):
    """Auswahl statt Freitext; unzulaessige Werte stehen nicht zur Wahl."""

    BINDINGS = [("escape", "cancel", "Abbrechen")]
    CSS = "ChoiceScreen {align: center middle;} " + DIALOG_CSS

    def __init__(self, title, options, value):
        super().__init__()
        self.title_text, self.options, self.value = title, options, value

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self.title_text)
            yield OptionList(
                *[
                    Option(
                        option["label"] + (f"  ({option['reason']})" if option["disabled"] else ""),
                        id=option["value"],
                        disabled=option["disabled"],
                    )
                    for option in self.options
                ]
            )

    def on_mount(self):
        option_list = self.query_one(OptionList)
        for index, option in enumerate(self.options):
            if option["value"] == self.value:
                option_list.highlighted = index
        option_list.focus()

    @on(OptionList.OptionSelected)
    def choose(self, event):
        self.dismiss(event.option.id)

    def action_cancel(self):
        self.dismiss(None)


class NumberScreen(ModalScreen):
    """Zahl mit Grenzen und Schnellwahl; kein JSON."""

    BINDINGS = [("escape", "cancel", "Abbrechen")]
    CSS = "NumberScreen {align: center middle;} " + DIALOG_CSS

    def __init__(self, title, presets, value):
        super().__init__()
        self.title_text, self.presets, self.value = title, presets, value

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self.title_text + "\nTab: Schnellwahl, Enter: uebernehmen, Esc: abbrechen")
            yield OptionList(*[Option(preset["label"], id=preset["value"]) for preset in self.presets])
            yield Input(value=str(self.value), type="number", id="value")

    def on_mount(self):
        self.query_one(Input).focus()

    @on(OptionList.OptionSelected)
    def choose(self, event):
        self.dismiss(event.option.id)

    @on(Input.Submitted)
    def submit(self, event):
        self.dismiss(event.value)

    def action_cancel(self):
        self.dismiss(None)


class NameScreen(ModalScreen):
    """Einzige Freitextstelle: ein neuer Profilname."""

    BINDINGS = [("escape", "cancel", "Abbrechen")]
    CSS = "NameScreen {align: center middle;} " + DIALOG_CSS

    def __init__(self, value):
        super().__init__()
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Profil speichern als (Buchstaben, Ziffern, _ und -)")
            yield Input(value=str(self.value), id="value")

    def on_mount(self):
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def submit(self, event):
        self.dismiss(event.value)

    def action_cancel(self):
        self.dismiss(None)


class WorkbenchTUI(App):
    TITLE = "dispread / setup"
    CSS = "Screen {background: #0b0d0f;} DataTable {height: 1fr;} #summary, #message {height: auto; padding: 0 1;}"
    BINDINGS = [
        Binding("q", "quit", "Shell"),
        Binding("a", "trigger('a')", "Auto-Setup"),
        Binding("y", "trigger('y')", "Vorschlag übernehmen"),
        Binding("c", "trigger('c')", "Auto abbrechen"),
        Binding("s", "trigger('s')", "Speichern"),
        Binding("n", "trigger('n')", "Speichern als"),
        Binding("r", "trigger('r')", "Verwerfen"),
        Binding("d", "trigger('d')", "Konflikt: Datei"),
        Binding("l", "trigger('l')", "Konflikt: lokal"),
        Binding("o", "open_row('profile')", "Profil laden"),
    ]
    state = None
    refreshing = False

    def __init__(self):
        super().__init__()
        self.rows, self.actions = [], []

    def compose(self) -> ComposeResult:
        yield Static("Verbinde …", id="summary")
        yield DataTable(id="settings", cursor_type="row")
        yield Static("Enter: Wert wählen | Modus setup/annotate: Anzeigebereich im Kamerabild bearbeiten", id="message")
        yield Footer()

    async def on_mount(self):
        self.query_one(DataTable).add_columns("Parameter", "Soll", "Ist / Hinweis")
        await self.refresh_state()
        self.set_interval(0.8, self.refresh_state)

    def message(self, text):
        self.query_one("#message", Static).update(str(text))

    async def refresh_state(self):
        if self.refreshing or len(self.screen_stack) > 1:
            return
        self.refreshing = True
        try:
            self.state = await request("status")
            state = self.state
            self.rows, self.actions = rows(state), actions(state)
            table = self.query_one(DataTable)
            row = table.cursor_row
            table.clear()
            for entry in self.rows:
                hint = entry["reason"] or entry["hint"]
                if entry.get("observed"):
                    hint = f"{entry['observed']} | {hint}"
                table.add_row(entry["label"], entry["display"], hint, key=entry["key"])
            table.move_cursor(row=min(row, table.row_count - 1))
            self.query_one("#summary", Static).update(
                f"{state['profile']} v{state['config']['version']} | {state['mode']} | "
                f"r{state['revision']}/gesetzt r{state['applied_revision']} | dirty={state['dirty']} "
                f"conflict={state['conflict']} | auto={state['auto']['state']}\n"
                f"Bild {state['sequence']} | {state['processing_fps']} fps | "
                f"Glanz {state['quality'].get('saturated_fraction', '—')} | {state['error'] or ''}"
            )
        except Exception as error:
            self.message(error)
        finally:
            self.refreshing = False

    async def perform(self, operations):
        try:
            for op, args in operations:
                await request(op, args)
            self.message(operations[-1][0] + " OK")
            await self.refresh_state()
        except Exception as error:
            self.message(error)

    def row_by_key(self, key):
        return next((entry for entry in self.rows if entry["key"] == key), None)

    def edit_row(self, key):
        row = self.row_by_key(key)
        if row is None:
            return
        if row["kind"] == "info":
            self.message(f"{row['label']}: {row['hint']}")
            return
        if row["disabled"]:
            self.message(f"{row['label']}: {row['reason']}")
            return
        if row["kind"] == "choice":

            async def choose(value):
                option = next((entry for entry in row["options"] if entry["value"] == value), None)
                if option is None:
                    return
                if option["disabled"]:
                    self.message(f"{row['label']}: {option['reason']}")
                    return
                await self.perform(option["ops"])

            self.push_screen(ChoiceScreen(row["label"], row["options"], row["value"]), choose)
            return

        async def enter(text):
            if text is None or text == "":
                return
            try:
                value = round(float(text)) if row["integer"] else float(text)
            except ValueError:
                self.message(f"{row['label']}: Zahl erwartet")
                return
            if not row["min"] <= value <= row["max"]:
                self.message(f"{row['label']}: erlaubt {row['min']} bis {row['max']}")
                return
            await self.perform([[row["op"], {"key": row["arg"], "value": value}]])

        self.push_screen(
            NumberScreen(f"{row['label']} ({row['min']} bis {row['max']})", row["presets"], row["value"]), enter
        )

    @on(DataTable.RowSelected)
    def select(self, event):
        self.edit_row(event.row_key.value)

    def action_open_row(self, key):
        self.edit_row(key)

    async def action_trigger(self, hotkey):
        entry = next((action for action in self.actions if action["hotkey"] == hotkey), None)
        if entry is None:
            return
        if not entry["enabled"]:
            self.message(f"{entry['label']}: {entry['reason']}")
            return
        if entry["needs_name"]:

            async def named(name):
                if name:
                    await self.perform([[entry["op"], {"name": name}]])

            self.push_screen(NameScreen(self.state["profile"] if self.state else "default"), named)
            return
        await self.perform([[entry["op"], entry["args"]]])
