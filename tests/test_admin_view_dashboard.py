"""Dashboard und Lauf der picam-Konsole: Zustände und Größen (Headless)."""

import asyncio
import functools
import time

import admin_fakes
import pytest

SIZES = [(80, 24), (60, 20), (120, 40), (180, 50)]
STATES = ['idle', 'run', 'setup', 'down']


def sync(coro):
    @functools.wraps(coro)
    def run(*args, **kwargs):
        asyncio.run(coro(*args, **kwargs))
    return run


def plain(app, selector):
    widget = app.main_screen.query_one(selector)
    content = widget.render()
    return getattr(content, 'plain', str(content))


def all_text(app, ids):
    return '\n'.join(plain(app, i) for i in ids)


@pytest.mark.parametrize('state', STATES)
@pytest.mark.parametrize('size', SIZES)
@sync
async def test_views_render_without_error(state, size):
    app = admin_fakes.make_app(state)
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.4)
        card = plain(app, '#dash-run')
        assert card.strip()
        await pilot.press('2')
        await pilot.pause(0.3)
        assert app.current == 'lauf'
        assert plain(app, '#run-state').strip()


@pytest.mark.parametrize('size', SIZES)
@sync
async def test_run_card_shows_counts_and_age(size):
    app = admin_fakes.make_app('run')
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.4)
        card = plain(app, '#dash-run')
        assert 'Lauf aktiv' in card
        assert '2.841' in card and 'vor' in card


@sync
async def test_idle_and_setup_cards():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        assert 'Kein Lauf' in plain(app, '#dash-run')
        assert 'https://' in plain(app, '#dash-run')
    app = admin_fakes.make_app('setup')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        assert 'Einrichtung' in plain(app, '#dash-run') and 'Fokus' in plain(app, '#dash-run')
    app = admin_fakes.make_app('down')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        assert 'unbekannt' in plain(app, '#dash-run')


@sync
async def test_click_and_enter_open_lauf():
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        await pilot.click('#dash-run')
        await pilot.pause(0.3)
        assert app.current == 'lauf'
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        app.main_screen.query_one('#dash-run').focus()
        await pilot.press('enter')
        await pilot.pause(0.3)
        assert app.current == 'lauf'


@sync
async def test_logo_hidden_when_small_shown_when_large():
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.4)
        assert not app.main_screen.query_one('#dash-logo').display
        assert app.main_screen.query_one('#dash-run').region.bottom <= 24
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        assert app.main_screen.query_one('#dash-logo').display


@sync
async def test_stacked_puts_list_first():
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause(0.4)
        right = app.main_screen.query_one('#dash-right')
        left = app.main_screen.query_one('#dash-left')
        assert right.region.y < left.region.y


@sync
async def test_lauf_content_wide_and_narrow():
    for size in ((120, 40), (80, 24)):
        app = admin_fakes.make_app('run')
        async with app.run_test(size=size) as pilot:
            await pilot.press('2')
            await pilot.pause(0.5)
            text = all_text(app, ['#run-state', '#run-latest', '#run-counts', '#run-strip', '#run-proc',
                                  '#run-system'])
            for needle in ('2.841', 'Margin (Abstand beste/zweitbeste Vorlage)', 'ms', 'vor', 'CPU', '%',
                           'Bilder/s', '12:04'):
                assert needle in text, needle


@sync
async def test_lauf_idle_names_werkbank_url():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press('2')
        await pilot.pause(0.4)
        assert 'Werkbank' in plain(app, '#run-state') and 'https://' in plain(app, '#run-state')


@sync
async def test_stale_latest_is_marked():
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        app.snapshot.live['run']['latest_age_s'] = 42.0
        app.snapshot.collected_at = time.time()
        app.view('dashboard').update_view()
        await pilot.press('2')
        await pilot.pause(0.4)
        text = plain(app, '#run-latest')
        assert 'vor 4' in text and 'nicht mehr frisch' in text
        assert 'vor 42' in plain(app, '#dash-run')
        app.snapshot.live['run']['latest_age_s'] = 0.3
        app.view('lauf').update_view()
        assert 'nicht mehr frisch' not in plain(app, '#run-latest')


@sync
async def test_unknown_values_are_dashes():
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.4)
        app.snapshot.live['run']['proc'] = {'fps': None, 'latency_ms': None, 'latency_recent': [],
                                           'skipped_recent': None, 'cells': {'min_margin': None, 'uncertain': 0},
                                           'age_s': None}
        app.view('lauf').update_view()
        assert 'Bilder/s' not in plain(app, '#run-proc')
        assert '–' in plain(app, '#run-proc')
