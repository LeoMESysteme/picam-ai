"""Startbild als GIF: Bilder aus Textual (run_test) mit echter Zwischenzeit.

Aufruf: PYTHONPATH=src python3 capture_intro.py <ausgabeordner> [breite höhe]
SVG → PNG → GIF braucht cairosvg und Pillow (nicht im Projekt-venv).
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import capture  # noqa: E402  (Falldaten und Instanz der Tour)

from dispread.admin.intro import Intro  # noqa: E402
from dispread.admin.tui import PicamApp  # noqa: E402

OUT = Path(sys.argv[1])
SIZE = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (100, 30)


async def main():
    Intro.MIN_S = 2.6
    app = PicamApp(capture.INST, collect=capture.collector('idle'), journal_source=capture.journal,
                   auto_refresh=False, intro=True)
    frames = []
    async with app.run_test(size=SIZE) as pilot:
        start = time.monotonic()
        while time.monotonic() - start < 4.4:
            await pilot.pause(0.06)
            frames.append((time.monotonic() - start, app.export_screenshot(title='picam')))
    for index, (at, svg) in enumerate(frames):
        (OUT / f'frame-{index:03d}-{at:.2f}.svg').write_text(svg)


if __name__ == '__main__':
    asyncio.run(main())
