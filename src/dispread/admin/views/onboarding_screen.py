"""Einrichtungsassistent (Onboarding) der Konsole: drei Schritte nach der Installation.

1. Konto & Adresse  – Adresse der Werkbank, Anmeldung mit dem Linux-Konto, Zertifikat im Browser vertrauen
2. Kamera & Fokus   – StreamCam erkannt?, Anschluss und Format, Bild und Fokus unter /live prüfen
3. Timing-Kalibrierung – Stand, Erklärung, Kalibrierbildschirm (``KalibrierenScreen``) öffnen

Der Assistent startet beim ersten Start der Konsole (solange die Marke ``onboarding.json``
im Datenordner fehlt), mit ``picam --onboarding`` und über Einstellungen erneut. Jeder
Abschluss (auch Esc) setzt die Marke; der Assistent ändert nichts selbst: Kamera
verbinden und Kalibrieren sind dieselben Aktionen wie im Tab Kamera.

Tasten: ``←``/``→``/Tab wechseln den Knopf, Enter löst ihn aus, ``↑``/``↓`` rollen,
Esc schließt (zählt als abgeschlossen).
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
from pathlib import Path

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from .. import calibrate, probes
from ..instance import user_config
from ..ui import MUTED, SOFT, TEXT, P, ascii_mode, bar, fade_in
from ..widgets import (
    SectionCard,
    badge,
    detail_rows,
    fact_badge,
    fields,
    header,
    help_line,
    icon,
    join,
    value,
)

MARKER = 'onboarding.json'
STEPS = (('konto', 'Konto & Adresse'), ('kamera', 'Kamera & Fokus'), ('kalibrierung', 'Timing-Kalibrierung'))
DONE, OPEN, SKIPPED = 'erledigt', 'offen', 'übersprungen'


# ----------------------------------------------------------------- Marke
def marker_paths(instance) -> list[Path]:
    """Orte der Marke: Datenordner der Werkbank, danach die Benutzerkonfiguration (falls jener nicht schreibbar ist)."""
    paths = []
    if instance.data:
        paths.append(Path(instance.data) / MARKER)
    paths.append(user_config().parent / MARKER)
    return paths


def is_done(instance) -> bool:
    return any(path.is_file() for path in marker_paths(instance))


def write_marker(instance, states: dict[str, str], how: str = 'abgeschlossen') -> Path | None:
    """Marke schreiben; Rückgabe: Ort oder None, wenn nirgends schreibbar."""
    body = json.dumps({'stand': how, 'am': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'schritte': states},
                      ensure_ascii=False, indent=2) + '\n'
    for path in marker_paths(instance):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
            return path
        except OSError:
            continue
    return None


def should_start(instance) -> bool:
    """Automatisch beim ersten Start einer installierten Werkbank (config.toml vorhanden, Marke fehlt)."""
    return bool(instance.config) and not is_done(instance)


# ----------------------------------------------------------------- Zertifikat
def fingerprint(path: Path | str | None) -> str | None:
    """SHA-256 des (ersten) Zertifikats einer PEM-Datei, Großbuchstaben in Zweiergruppen mit Doppelpunkt."""
    if not path:
        return None
    try:
        text = Path(path).read_text(encoding='ascii', errors='ignore')
        block = re.search(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', text, re.S)
        if block is None:
            return None
        digest = hashlib.sha256(ssl.PEM_cert_to_DER_cert(block.group(0))).hexdigest().upper()
    except (OSError, ValueError):
        return None
    return ':'.join(digest[i:i + 2] for i in range(0, len(digest), 2))


# ----------------------------------------------------------------- Bildschirm
class OnboardingScreen(ModalScreen[str]):
    """Drei Schritte mit Fortschrittsleiste; Rückgabe ``'fertig'`` oder ``'abgebrochen'``."""

    BINDINGS = [Binding('escape', 'close', show=False), Binding('left', 'switch(-1)', show=False),
                Binding('right', 'switch(1)', show=False),
                Binding('up', 'scroll_body(-1)', show=False), Binding('down', 'scroll_body(1)', show=False),
                Binding('pageup', 'scroll_body(-5)', show=False), Binding('pagedown', 'scroll_body(5)', show=False)]
    DEFAULT_CSS = '''
    OnboardingScreen { background: $picam-canvas; }
    #ob { height: 1fr; width: 1fr; max-width: 120; padding: 0 2; }
    #ob-title { height: 1; margin: 1 0 0 0; }
    #ob-bar { height: 1; }
    #ob-chips { height: 1; }
    #ob-body { height: 1fr; scrollbar-size-vertical: 1; }
    #ob-body > SectionCard { margin: 1 0 0 0; }
    #ob-hint { height: 1; margin: 1 0 0 0; }
    #ob-buttons { height: 1; margin: 1 0 0 0; }
    #ob-buttons Button { margin: 0 1 0 0; min-width: 8; width: auto; padding: 0 1; }
    '''

    def __init__(self, instance, *, start: int = 0):
        super().__init__()
        self.instance = instance
        self.page = max(0, min(len(STEPS) - 1, start))
        self.skipped: set[str] = set()
        self._shown: int | None = None

    # ------------------------------------------------------------ Aufbau
    def compose(self):
        with Vertical(id='ob'):
            yield Static(id='ob-title')
            yield Static(id='ob-bar')
            yield Static(id='ob-chips')
            with VerticalScroll(id='ob-body'):
                for key, _ in STEPS:
                    yield SectionCard(id=f'ob-{key}-1')
                    yield SectionCard(id=f'ob-{key}-2')
                    yield SectionCard(id=f'ob-{key}-3')
            yield Static(id='ob-hint')
            with Horizontal(id='ob-buttons'):
                yield Button('Zurück', id='ob-back')
                yield Button('Aktion', id='ob-act')
                yield Button('Überspringen', id='ob-skip')
                yield Button('Weiter', id='ob-next', variant='primary')

    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_view)
        self.update_view()
        self.query_one('#ob-next', Button).focus()

    def on_resize(self, event) -> None:
        self.call_after_refresh(self.update_view)

    # ------------------------------------------------------------ Daten
    def _fact(self, key: str):
        return self.app.fact(key)

    def _user(self) -> str | None:
        user = self.instance.pam_user
        if user:
            return user
        fact = self._fact('konto')
        return dict(fact.detail).get('Konto') if fact is not None else None

    def _service_up(self) -> bool:
        fact = self._fact('dienst')
        return fact is not None and fact.level in (probes.OK, probes.WARN)

    def state(self, key: str) -> str:
        """Zustand eines Schritts: erledigt (Befund in Ordnung), übersprungen oder offen."""
        if key == 'konto':
            fact = self._fact('zertifikat')
            ready = self._service_up() and bool(self.instance.url) and fact is not None and fact.level == probes.OK
        elif key == 'kamera':
            fact = self._fact('kamera')
            ready = fact is not None and fact.level == probes.OK
        else:
            fact = self._fact('kalibrierung')
            ready = fact is not None and fact.level == probes.OK
        if ready:
            return DONE
        return SKIPPED if key in self.skipped else OPEN

    def states(self) -> dict[str, str]:
        return {key: self.state(key) for key, _ in STEPS}

    def action(self) -> tuple[str, str, str | None] | None:
        """Knopf der Seite: (Beschriftung, Taste für Hinweis, Sperrgrund) oder None."""
        key = STEPS[self.page][0]
        if key == 'kamera':
            return 'Kamera neu verbinden', 'connect', (None if self._service_up() else 'Werkbank läuft nicht')
        if key == 'kalibrierung':
            return 'Kalibrieren …', 'clock', self.calibrate_blocker()
        return None

    def calibrate_blocker(self) -> str | None:
        fact = self._fact('kalibrierung')
        if fact is not None and fact.level == probes.OK:
            return 'Kalibrierung ist schon gültig'
        try:
            return self.app.view('kamera').calibrate_blocker()
        except Exception:  # noqa: BLE001 - ohne Kamera-Tab (Tests, Entwicklungsbetrieb) nicht anbieten
            return 'Kalibrieren ist hier nicht verfügbar'

    # ------------------------------------------------------------ Anzeige
    def _width(self, card: SectionCard) -> int:
        return card.inner_width(max(30, self.app.size.width - 10))

    def _progress(self) -> None:
        width = max(10, min(110, self.size.width - 4))
        total = len(STEPS)
        title = Text(no_wrap=True, overflow='ellipsis')
        title.append(f'{icon("setup")} ', style=P.accent)
        title.append('EINRICHTUNG', style=f'bold {SOFT}')
        title.append(f'  Schritt {self.page + 1} von {total}: {STEPS[self.page][1]}', style=MUTED)
        self.query_one('#ob-title', Static).update(title)
        self.query_one('#ob-bar', Static).update(bar((self.page + 1) / total, width, P.accent))
        compact = False
        for _ in range(2):
            chips = Text(no_wrap=True, overflow='ellipsis')
            for index, (key, label) in enumerate(STEPS):
                state = self.state(key)
                level = {DONE: probes.OK, SKIPPED: probes.WARN}.get(state, probes.OFF)
                glyph = {DONE: 'ok', SKIPPED: 'off'}.get(state, 'off')
                if index:
                    chips.append(' ')
                if index == self.page:
                    chips.append(f' {index + 1} {label} ', style=f'bold {P.select_fg} on {P.select_bg}')
                elif compact:   # schmal: nur Nummer und Zustandszeichen
                    chips.append(f' {index + 1} ', style=f'{SOFT} on {P.control}')
                    chips.append_text(badge(level, '', glyph))
                    continue
                else:
                    chips.append(f' {index + 1} {label} ', style=f'{SOFT} on {P.control}')
                chips.append_text(badge(level, state, glyph))
            if chips.cell_len <= width + 4 or compact:
                break
            compact = True
        self.query_one('#ob-chips', Static).update(chips)

    def update_view(self) -> None:
        if not self.is_attached:
            return
        self._progress()
        for index, (key, _) in enumerate(STEPS):
            for part in (1, 2, 3):
                self.query_one(f'#ob-{key}-{part}', SectionCard).display = index == self.page
        {0: self._page_account, 1: self._page_camera, 2: self._page_timing}[self.page]()
        if self._shown != self.page:
            self._shown = self.page
            self.query_one('#ob-body').scroll_home(animate=False)
            fade_in(self.query_one('#ob-body'))
        self._buttons()

    def _page_account(self) -> None:
        inst = self.instance
        card = self.query_one('#ob-konto-1', SectionCard)
        width = self._width(card)
        service = self._fact('dienst')
        card.show(header('address', 'Adresse der Werkbank', fact_badge(service), width),
                  fields([('Adresse', value(inst.url), True)], width, label_w=10),
                  help_line('Diese Adresse im Browser von Windows öffnen (Bild, Fokus, Messlauf).'))

        card = self.query_one('#ob-konto-2', SectionCard)
        width = self._width(card)
        login = Text(no_wrap=True)
        login.append('Benutzer ', style=MUTED)
        login.append(self._user() or '–', style=f'bold {TEXT} on {P.inset}')
        login.append(' mit dem Linux-Passwort dieses Kontos', style=TEXT)
        card.show(header('account', 'Anmeldung', None, width), login,
                  help_line('Dasselbe Passwort wie für SSH (ändern: passwd); kein eigenes Passwort.'))

        card = self.query_one('#ob-konto-3', SectionCard)
        width = self._width(card)
        fact = self._fact('zertifikat')
        detail = dict(fact.detail) if fact is not None else {}
        path = Path(inst.data) / 'tls' / 'cert.pem' if inst.data else None
        digest = fingerprint(path)
        rows = [('Gültig bis', value(detail.get('Gültig bis')))]
        if digest:
            half = len(digest) // 2 + 1
            rows += [('SHA-256', value(digest[:half - 1]), True), ('', value(digest[half:]), True)]
        else:
            rows.append(('SHA-256', value(None)))
        rows.append(('Datei', value(str(path) if path else None), True))
        card.show(header('cert', 'Zertifikat im Browser vertrauen', fact_badge(fact), width),
                  fields(rows, width, label_w=11),
                  help_line('Selbstsigniert: der Browser warnt zuerst; Fingerabdruck vergleichen.'))

    def _page_camera(self) -> None:
        fact = self._fact('kamera')
        card = self.query_one('#ob-kamera-1', SectionCard)
        width = self._width(card)
        rows = detail_rows(fact) or [('Gerät', value(None))]
        card.show(header('camera', 'Kamera', fact_badge(fact), width, note='Logitech StreamCam'),
                  fields(rows, width, label_w=12),
                  help_line('1920×1080 gibt es nur an einem blauen USB-3-Anschluss.'))
        card = self.query_one('#ob-kamera-2', SectionCard)
        width = self._width(card)
        url = self.instance.url
        body = Text(no_wrap=True)
        body.append('Bild und Fokus in der Werkbank unter /live prüfen:\n', style=TEXT)
        body.append(f' {url or "–"} ', style=f'bold {P.accent} on {P.inset}')
        card.show(header('template', 'Bild und Fokus prüfen', None, width), body,
                  help_line('Anzeige scharf und ohne Spiegelung; Kamera weg? Unten neu verbinden.'))
        self.query_one('#ob-kamera-3', SectionCard).display = False

    def _page_timing(self) -> None:
        fact = self._fact('kalibrierung')
        card = self.query_one('#ob-kalibrierung-1', SectionCard)
        width = self._width(card)
        rows = detail_rows(fact) or [('Datei', value(None))]
        ok = fact is not None and fact.level == probes.OK
        card.show(header('clock', 'Timing-Kalibrierung', fact_badge(fact), width),
                  fields(rows, width, label_w=12),
                  help_line('Gültig: nichts zu tun.' if ok else
                            'Voraussetzung für einen Messlauf (Zeitversatz Telegramm/Anzeige).'))
        card = self.query_one('#ob-kalibrierung-2', SectionCard)
        width = self._width(card)
        blocker = self.calibrate_blocker()
        steps = [('Vorbereitung', value('USB-RS232-Adapter vorübergehend an den GSV-2AS stecken'), True),
                 ('Dauer', value('etwa 3 Minuten Aufnahme plus Auswertung'), True),
                 ('Währenddessen', value('Werkbank einige Minuten aus, startet danach von selbst'), True)]
        card.show(header('setup', 'So läuft es ab', None, width), fields(steps, width, label_w=15),
                  help_line('Überspringen geht: später im Tab Kamera (m) oder mit picam kalibrieren.'))
        card = self.query_one('#ob-kalibrierung-3', SectionCard)
        width = self._width(card)
        adapter = calibrate.adapter_present(self.app.instance.reference_port)
        state = (badge(probes.OK, 'bereit', 'ok') if blocker is None
                 else badge(probes.OFF, 'nicht möglich', 'off'))
        rows = [('Kalibrieren', join(state, f'  {blocker}' if blocker else '  Kalibrierbildschirm öffnen'), True),
                ('Adapter', badge(probes.OK, 'erkannt') if adapter else badge(probes.OFF, 'nicht erkannt', 'off'))]
        card.show(header('check', 'Jetzt kalibrieren?', None, width), fields(rows, width, label_w=12))

    def _buttons(self) -> None:
        last = self.page == len(STEPS) - 1
        back = self.query_one('#ob-back', Button)
        back.disabled = self.page == 0
        act = self.query_one('#ob-act', Button)
        action = self.action()
        act.display = action is not None
        if action is not None:
            label, glyph, blocked = action
            act.label = f'{icon(glyph)} {label}'
            act.disabled = blocked is not None
            act.tooltip = blocked
        self.query_one('#ob-skip', Button).display = not last or self.state('kalibrierung') != DONE
        narrow = self.size.width < 90   # 80×24: sonst passen die vier Knöpfe nicht in eine Zeile
        self.query_one('#ob-next', Button).label = (('Fertig' if narrow else 'Fertig – zur Übersicht')
                                                    if last else 'Weiter')
        hint = Text(no_wrap=True, overflow='ellipsis')
        hint.append('Pfeile Knopf wählen · Enter auslösen · Esc schließen' if ascii_mode() else
                    '←→ Knopf wählen · Enter auslösen · ↑↓ rollen · Esc schließen', style=f'italic {MUTED}')
        if action is not None and action[2]:
            hint = Text(f'{icon("help")} {action[0]}: {action[2]}', style=f'italic {MUTED}', no_wrap=True,
                        overflow='ellipsis')
        self.query_one('#ob-hint', Static).update(hint)

    # ------------------------------------------------------------ Bedienung
    def go(self, step: int) -> None:
        self.page = max(0, min(len(STEPS) - 1, self.page + step))
        self.update_view()
        self.query_one('#ob-next', Button).focus()

    def finish(self, how: str = 'fertig') -> None:
        write_marker(self.instance, self.states(), 'abgeschlossen' if how == 'fertig' else 'geschlossen')
        self.dismiss(how)

    def action_close(self) -> None:
        self.finish('abgebrochen')

    def action_switch(self, step: int) -> None:
        buttons = [b for b in self.query('#ob-buttons Button') if b.display and not b.disabled]
        if not buttons:
            return
        focused = self.focused
        index = buttons.index(focused) if focused in buttons else 0
        buttons[(index + step) % len(buttons)].focus()

    def action_scroll_body(self, step: int) -> None:
        self.query_one('#ob-body').scroll_relative(y=step, animate=False)

    @on(Button.Pressed, '#ob-back')
    def _back(self) -> None:
        self.go(-1)

    @on(Button.Pressed, '#ob-skip')
    def _skip(self) -> None:
        key = STEPS[self.page][0]
        if self.state(key) != DONE:
            self.skipped.add(key)
        if self.page == len(STEPS) - 1:
            self.finish()
        else:
            self.go(1)

    @on(Button.Pressed, '#ob-next')
    def _next(self) -> None:
        if self.page == len(STEPS) - 1:
            self.finish()
        else:
            self.go(1)

    @on(Button.Pressed, '#ob-act')
    def _act(self) -> None:
        action = self.action()
        if action is None or action[2]:
            return
        if STEPS[self.page][0] == 'kamera':
            self.app.camera_connect()
        else:
            self.app.view('kamera').calibrate()
