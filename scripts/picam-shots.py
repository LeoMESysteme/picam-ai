#!/usr/bin/env python3
"""Bildschirmfotos der picam-Konsole mit Beispieldaten (tests/admin_fakes.py).

Aufruf: PYTHONPATH=src python3 scripts/picam-shots.py AUSGABEORDNER NAME:BREITE:HÖHE[:zustand][:taste…] …
Beispiel: … /tmp/shots lauf:120:40:run:2 kamera:80:24:idle:4
Schreibt SVG; PNG z. B. mit cairosvg (nicht im Projekt-venv).
Farbvariante über PICAM_THEME (schiefer | petrol | hell, auch a | b | c), z. B.
PICAM_THEME=hell PYTHONPATH=src python3 scripts/picam-shots.py /tmp/shots-hell cfg:100:30:idle:c
Anordnung der neuen Bildsprache über PICAM_LAYOUT (a = Karten + Abzeichen, b = Kacheln + Details).
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
import admin_fakes  # noqa: E402


async def shoot(out: Path, spec: str) -> None:
    name, width, height, *rest = spec.split(':')
    state = rest[0] if rest and rest[0] in ('idle', 'run', 'setup', 'down') else 'idle'
    keys = rest[1:] if rest and rest[0] == state else rest
    app = admin_fakes.make_app(state)
    async with app.run_test(size=(int(width), int(height))) as pilot:
        await pilot.pause(0.5)
        for key in keys:
            await pilot.press(key)
            await pilot.pause(0.25)
        await pilot.pause(0.3)
        (out / f'{name}.svg').write_text(app.export_screenshot(title=f'picam {width}x{height}'))


async def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for spec in sys.argv[2:]:
        await shoot(out, spec)


if __name__ == '__main__':
    asyncio.run(main())
