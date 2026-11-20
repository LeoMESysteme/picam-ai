"""Tabs Speicher, Netzwerk, UART, Konto (Textual run_test mit Beispieldaten)."""

import asyncio

import admin_fakes
import pytest
from textual.widgets import Static

from dispread.admin.views import KontoView, NetzwerkView, SpeicherView, UartView

KEYS = {'7': SpeicherView, '8': NetzwerkView, '9': UartView, '0': KontoView}


def text_of(view) -> str:
    parts = []
    for widget in view.query(Static):
        if not widget.display:
            continue
        content = widget.renderable if hasattr(widget, 'renderable') else widget.content
        parts.append(content.plain if hasattr(content, 'plain') else _render(content))
    return '\n'.join(parts)


def _render(renderable) -> str:
    from rich.console import Console

    console = Console(width=200, record=True, force_terminal=False)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


def drive(test, key, *, size=(100, 34), state='idle', setup=None):
    async def main():
        app = admin_fakes.make_app(state)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            if setup:
                setup(app)
            await pilot.press(key)
            await pilot.pause(0.3)
            view = app.query_one(KEYS[key])
            view.update_view()
            await pilot.pause(0.1)
            await test(app, view, pilot)
    asyncio.run(main())


def test_speicher_zeigt_gb_reserve_und_gruppen():
    async def check(app, view, pilot):
        text = text_of(view)
        assert '31,0 GB' in text and '28,5 GB' in text and '2,5 GB' in text
        assert 'Reserve 2,0 GB frei' in text
        assert 'Reserve' in text and 'bis Reserve' in text
        for name in ('Läufe', 'Diagnose', 'Werkbank-Daten', 'Brücke', 'Programmversionen', 'Sonstiges'):
            assert name in text
        assert '/var/lib/picam/live' in text
        assert 'Läufe könnten abgelehnt werden' in text
    drive(check, '7')


def test_speicher_ohne_daten_wird_ermittelt():
    async def check(app, view, pilot):
        app.storage = None
        view.update_view()
        assert 'wird ermittelt' in text_of(view)
    drive(check, '7')


def test_speicher_aufraeumen_ruft_cli(monkeypatch):
    calls = []

    async def check(app, view, pilot):
        monkeypatch.setattr(app, 'run_cli', lambda argv, title: calls.append((argv, title)) or 0)
        await pilot.press('a')
        await pilot.pause(0.2)
        assert calls == [(['aufraeumen'], 'picam aufraeumen')]
    drive(check, '7')


def test_netzwerk_zeigt_schnittstellen_tailscale_adresse():
    async def check(app, view, pilot):
        text = text_of(view)
        assert 'raspi06' in text
        for name in ('eth0', 'wlan0', 'tailscale0'):
            assert name in text
        assert '192.168.10.42/24' in text and '88:a2:9e:c8:c4:ef' in text
        assert 'raspi06.tail4bdf43.ts.net' in text and 'Running' in text
        assert 'liegt auf eth0' in text
        assert 'synchron' in text
        assert 'nmcli' in text
    drive(check, '8')


def test_netzwerk_ohne_daten():
    async def check(app, view, pilot):
        app.network = None
        view.update_view()
        assert 'wird ermittelt' in text_of(view)
    drive(check, '8')


def test_uart_grafik_markiert_pins():
    async def check(app, view, pilot):
        text = text_of(view)
        assert 'GPIO14 TXD0' in text and 'benutzt (Senden)' in text
        assert 'GPIO15 RXD0' in text and 'nicht benutzt' in text and 'nicht bestätigt' in text
        assert '3V3' in text and '5V' in text and 'GND' in text
        assert 'RS-232' in text and 'Pegelwandler' in text
        assert '/dev/ttyAMA0' in text and 'ttyAMA10' in text
        assert 'enable_uart=1' in text
        assert 'GPIO21' in text  # breit: ganze Leiste
    drive(check, '9')


def test_uart_ascii_rueckfall(monkeypatch):
    monkeypatch.setenv('PICAM_ASCII', '1')

    async def check(app, view, pilot):
        text = text_of(view)
        assert '◀' not in text and '●' not in text and '<' in text
    drive(check, '9')


def test_konto_nennt_benutzer_und_passwort():
    async def check(app, view, pilot):
        text = text_of(view)
        assert 'Benutzer labor mit dem Linux-Passwort dieses Kontos' in text
        assert 'dialout' in text and 'video' in text
        assert 'passwd' in text and 'SSH' in text
    drive(check, '0')


@pytest.mark.parametrize('key', list(KEYS))
@pytest.mark.parametrize('size', [(80, 24), (60, 20)])
def test_kleine_groessen_ohne_fehler(key, size):
    async def check(app, view, pilot):
        assert text_of(view)
    drive(check, key, size=size)


def test_info_texte_vorhanden():
    for view in KEYS.values():
        assert view.INFO and view.INFO_TITLE


def test_fehlende_befunde_stuerzen_nicht():
    def setup(app):
        app.snapshot.facts.pop('konto', None)
        app.snapshot.facts.pop('uart', None)
        app._setup_facts.pop('konto', None)
        app._setup_facts.pop('uart', None)

    for key in ('9', '0'):
        async def check(app, view, pilot):
            assert 'wird geprüft' in text_of(view).lower()
        drive(check, key, setup=setup)
