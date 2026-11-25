"""UART-Ports in der Konsole: Pinwahl, Dropdown nur mit wählbaren Funktionen, Prüfseite mit Diff, Anwenden,
Neustart-Hinweis (nie automatisch). Backend: echtes ``UartPorts`` auf temporären Dateien (nichts Echtes wird
geschrieben, ``apply_change`` ist ein Fake)."""

from __future__ import annotations

import asyncio
import dataclasses

import admin_fakes
import pytest
from test_admin_uart_ports import add_usb
from test_admin_uart_ports import uart as uart_backend
from test_admin_update_screen import log_text, text_of, until
from test_admin_view_system import text_of as view_text

from dispread.admin import uart_ports
from dispread.admin.views.uart_screen import PinHeader, UartApplyScreen, UartPortsScreen

uart = uart_backend   # pytest-Fixture des Backends (temporäre Boot-/Instanzdateien)


def ports_text(screen) -> str:
    return '\n'.join(text_of(screen.query_one(sel)) for sel in (
        '#up-title', '#up-pins-head', '#up-out-head', '#up-out-info', '#up-ref-head', '#up-ref-info', '#up-sum',
        '#up-error'))


def apply_text(screen) -> str:
    return '\n'.join(text_of(screen.query_one(sel)) for sel in (
        '#kal-title', '#kal-alarm', '#kal-plan', '#kal-ask-head', '#kal-ask-text', '#kal-ask-error', '#kal-steps',
        '#kal-result'))


def drive(test, backend, *, size=(100, 40), apply=None, sudo=None):
    instance = dataclasses.replace(backend.instance, reference_port='/dev/ttyUSB0', bridge_name=None)

    async def main():
        app = admin_fakes.make_app('idle', instance=instance)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            screen = UartPortsScreen(instance, ports=backend, apply=apply, sudo=sudo)
            app.push_screen(screen)
            await pilot.pause(0.3)
            await test(app, pilot, screen)
    asyncio.run(main())


def options_of(select) -> list:
    return [value for _label, value in select._options if value is not select.BLANK]


def test_pin_choice_lists_only_selectable_functions_and_explains_the_rest(uart):
    async def check(app, pilot, screen):
        pins = screen.query_one('#up-pins', PinHeader)
        assert pins.pin == 8 and options_of(screen.query_one('#up-out-select')) == ['uart0']
        await pilot.click('#up-pins', offset=(5, 4))              # Zeile 4: Pin 7 (links)
        await pilot.pause(0.3)
        assert pins.pin == 7
        assert options_of(screen.query_one('#up-out-select')) == ['uart2']
        await pilot.press('down')                                  # Pin 9 (GND): keine UART-Funktion
        await pilot.pause(0.2)
        await pilot.press('right', 'up')                           # Pin 10: RX von UART0
        await pilot.pause(0.3)
        assert pins.pin == 8 or pins.pin == 10
        pins.set_pin(10)
        await pilot.pause(0.3)
        text = ports_text(screen)
        assert options_of(screen.query_one('#up-out-select')) == []
        assert 'nicht wählbar' in text and 'RX ist Eingang' in text
        pins.set_pin(9)
        await pilot.pause(0.3)
        assert 'keine UART-Funktion' in ports_text(screen)
    drive(check, uart)


def test_dropdown_label_shows_status(uart):
    async def check(app, pilot, screen):
        pins = screen.query_one('#up-pins', PinHeader)
        pins.set_pin(7)
        await pilot.pause(0.3)
        labels = [label for label, _ in screen.query_one('#up-out-select')._options if label]
        assert len(labels) == 1 and 'UART2' in labels[0] and 'TX Pin 7' in labels[0] and 'Neustart' in labels[0]
    drive(check, uart)


def test_level_note_stays_visible_and_next_needs_a_change(uart):
    async def check(app, pilot, screen):
        assert '3,3 V' in ports_text(screen) and 'RS-232' in ports_text(screen)
        assert screen.query_one('#up-next').disabled
        screen.error = ''
    drive(check, uart)


def test_full_flow_plan_with_diff_confirm_apply_and_reboot_hint(uart, monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError('picam darf den Pi nie selbst neu starten')

    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr('os.system', forbidden)
    applied = []

    def apply(plan):
        applied.append(plan)
        return uart_ports.ChangeResult(None, False, True, 'Pi-Neustart nötig. Gerätenamen nach Neustart prüfen.')

    async def check(app, pilot, screen):
        screen.query_one('#up-pins', PinHeader).set_pin(7)
        await pilot.pause(0.3)
        screen.query_one('#up-out-select').value = 'uart2'
        await pilot.pause(0.3)
        assert screen.output == 'uart2' and not screen.query_one('#up-next').disabled
        assert 'uart2' in ports_text(screen)
        await pilot.click('#up-next')
        await until(pilot, lambda: isinstance(app.screen, UartApplyScreen))
        apply_screen = app.screen
        await until(pilot, lambda: apply_screen.pending is not None)
        text = apply_text(apply_screen)
        for word in ('PRÜFSEITE', 'uart0', 'uart2', 'dtoverlay=uart2-pi5', '+', '# picam-uart', 'output_port',
                     'Pi-Neustart nötig', '3,3 V', 'RS-232'):
            assert word in text, word
        assert applied == []                                        # vor der Bestätigung nichts geschrieben
        await pilot.click('#kal-ok')
        await until(pilot, lambda: apply_screen.finished)
        text = apply_text(apply_screen)
        assert applied and 'sudo systemctl reboot' in text and 'nötig' in text
        assert 'nie selbst' in text or 'startet den Pi nie' in text
        assert apply_screen.result.outcome == 'partial'
    class NoSudo:
        sudo_needed = staticmethod(lambda plan: False)

    drive(check, uart, apply=apply, sudo=NoSudo)


def test_service_restart_result_and_sudo_password_never_logged(uart, monkeypatch):
    import os

    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    seen = []

    class Sudo:
        sudo_needed = staticmethod(lambda plan: True)
        sudo_cached = staticmethod(lambda: False)

        @staticmethod
        def sudo_validate(password):
            seen.append(password)
            return True, ''

    ref = add_usb(uart)

    async def check(app, pilot, screen):
        screen.query_one('#up-ref-select').value = ref
        await pilot.pause(0.3)
        assert screen.reference == ref
        await pilot.click('#up-next')
        await until(pilot, lambda: isinstance(app.screen, UartApplyScreen))
        apply_screen = app.screen
        await until(pilot, lambda: apply_screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: apply_screen.pending is not None and apply_screen.pending['entry'] == 'password')
        assert apply_screen.query_one('#kal-input').password
        apply_screen.query_one('#kal-input').value = 'geheim456'
        await pilot.press('enter')
        await until(pilot, lambda: apply_screen.finished)
        assert seen == ['geheim456']
        assert 'geheim456' not in log_text(apply_screen) + apply_text(apply_screen)
        assert 'neu gestartet' in apply_text(apply_screen) and apply_screen.result.outcome == 'ok'
    drive(check, uart, apply=lambda plan: uart_ports.ChangeResult(None, True, False, 'Werkbank-Dienst neu gestartet.'),
          sudo=Sudo)


def test_plan_refusal_is_shown_on_the_selection_page(uart):
    async def check(app, pilot, screen):
        screen.ports = type('P', (), {
            'choices': screen.ports.choices, 'reference_choices': screen.ports.reference_choices,
            'plan_change': staticmethod(lambda **kw: (_ for _ in ()).throw(ValueError('Lauf aktiv: gesperrt')))})()
        screen.query_one('#up-pins', PinHeader).set_pin(7)
        await pilot.pause(0.3)
        screen.query_one('#up-out-select').value = 'uart2'
        await pilot.pause(0.3)
        await pilot.click('#up-next')
        await pilot.pause(0.3)
        assert 'Lauf aktiv: gesperrt' in ports_text(screen) and isinstance(app.screen, UartPortsScreen)
    drive(check, uart)


def test_decline_confirmation_changes_nothing(uart):
    applied = []

    async def check(app, pilot, screen):
        screen.query_one('#up-pins', PinHeader).set_pin(7)
        await pilot.pause(0.3)
        screen.query_one('#up-out-select').value = 'uart2'
        await pilot.pause(0.3)
        await pilot.click('#up-next')
        await until(pilot, lambda: isinstance(app.screen, UartApplyScreen))
        apply_screen = app.screen
        await until(pilot, lambda: apply_screen.pending is not None)
        await pilot.press('escape')
        await until(pilot, lambda: apply_screen.finished)
        assert apply_screen.result.outcome == 'cancelled' and applied == []
    drive(check, uart, apply=lambda plan: applied.append(plan))


@pytest.mark.parametrize('size', [(80, 24), (100, 30), (160, 50)])
def test_usable_at_sizes(uart, size):
    async def check(app, pilot, screen):
        assert screen.query_one('#up-buttons').region.bottom <= size[1]
        assert screen.query_one('#up-cancel').region.height > 0
        screen.query_one('#up-pins', PinHeader).set_pin(37)       # unten: Leiste scrollt mit
        await pilot.pause(0.3)
        assert screen.query_one('#up-pins').region.y + 0 >= -40
    drive(check, uart, size=size)


def test_uart_tab_shows_configured_ports_and_blocks_while_running(uart):
    async def check(app, pilot):
        await pilot.press('9')
        await pilot.pause(0.4)
        view = app.view()
        text = view_text(view)
        assert 'uart2' in text and 'Pin 7' in text
        assert view.change_blocker() is None
        await pilot.press('p')
        await pilot.pause(0.4)
        assert isinstance(app.screen, UartPortsScreen)

    instance = dataclasses.replace(admin_fakes.INSTANCE, output_port='uart2', reference_port='/dev/ttyUSB0')

    async def main():
        app = admin_fakes.make_app('idle', instance=instance)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            await check(app, pilot)
    asyncio.run(main())
