#!/usr/bin/env python3
"""Vergleicht die vollstaendigen Leser- und Einrichtungsbefunde auf aufgezeichneten Bildern.

Aufruf aus der Repo-Wurzel. PYTHONPATH bestimmt die gepruefte dispread-Version.
Die Referenztexte dienen ausschliesslich dem Gegenlesen im Einrichtungscheck.
"""

import argparse
import json
import os
import runpy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields
from pathlib import Path

import cv2
import numpy as np
from _devdata import diagnose_dir, input_path

from dispread.dotlattice import LatticeFit, evaluate_quad, fit_lattice
from dispread.layout import CharLayout
from dispread.live import DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256
from dispread.live.setup import DEFAULT_TARGET_SIZE, GSV2AS_EMPTY_CELLS, LATTICE_GRID
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.rectify import rectify
from dispread.setup_checks import check_setup, diagnose_reader, raster_offset_check
from dispread.setup_hint import find_green_hint_box


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def image(path):
    frame = cv2.imread(str(path))
    if frame is None:
        raise ValueError(f'Bild nicht lesbar: {path}')
    return frame


def json_value(value):
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def reading(reader, frame, quad):
    crop = rectify(frame, quad, target_size=DEFAULT_TARGET_SIZE).image
    return asdict(reader.read(crop, CharLayout(grid=LATTICE_GRID, unit='mV/V')))


def setup_sample(reader, path, *, saved_quad=None, reference=None):
    frame = image(path)
    hint = find_green_hint_box(frame)
    fit = 'keine_hinweisbox' if hint is None else fit_lattice(frame, hint, empty_cells=GSV2AS_EMPTY_CELLS)
    result = {'fit_lattice': asdict(fit) if isinstance(fit, LatticeFit) else fit}
    quad = saved_quad if saved_quad is not None else (fit.quad if isinstance(fit, LatticeFit) else None)
    if quad is None:
        result['reader'] = None
        return result
    result['reader'] = reading(reader, frame, quad)
    evaluated = 'keine_hinweisbox' if hint is None else evaluate_quad(frame, hint, quad, empty_cells=GSV2AS_EMPTY_CELLS)
    result['evaluate_quad'] = asdict(evaluated) if isinstance(evaluated, LatticeFit) else evaluated
    checks_fit = evaluated if isinstance(evaluated, LatticeFit) else fit
    if isinstance(checks_fit, LatticeFit):
        offset = None
        if reference is not None:
            frames = [(frame, reference)]
            offset = raster_offset_check(frames, checks_fit.quad)
            result['gegenlesen'] = diagnose_reader(frames, checks_fit.quad, DEFAULT_TEMPLATES,
                                                   DEFAULT_TEMPLATES_SHA256, reference_kind='seriell').to_dict()
        result['check_setup'] = check_setup(frame, checks_fit, offset_check=offset).to_dict()
    return result


def setup_samples(reader, jobs):
    def run(job):
        path, options = job
        return setup_sample(reader, path, **options)

    with ThreadPoolExecutor(max_workers=4) as workers:
        return dict(zip(jobs, workers.map(run, jobs.values()), strict=True))


def regression(reader, root):
    jobs = {}
    initial_fits = {}
    folders = sorted((root / 'regression/2026-11-11').glob('live-*'))
    if len(folders) != 16:
        raise ValueError(f'OQ-69-Korpus unvollstaendig: {len(folders)}/16 Aufstellungen')
    for folder in folders:
        entries = load_json(folder / 'cell-text.json')
        proposal = folder / 'proposal.json'
        saved_quad = load_json(proposal)['quad'] if proposal.is_file() else None
        for stem in ('still', 'stability'):
            path = folder / f'{stem}.png'
            if stem == 'stability' and not path.exists():
                continue
            reference = next(e['masked'] for e in reversed(entries) if e['still'] == stem)
            key = f'{folder.name}/{path.name}'
            jobs[key] = path, {'saved_quad': saved_quad, 'reference': reference}
            initial = folder / 'initial-fit-oq72.json'
            if stem == 'still' and initial.exists():
                initial_fits[key] = initial

    result = setup_samples(reader, jobs)
    for key, initial in initial_fits.items():
        data = load_json(initial)
        fit = LatticeFit(**{f.name: data[f.name] for f in fields(LatticeFit) if f.name in data})
        result[key]['check_setup_oq72'] = check_setup(image(jobs[key][0]), fit).to_dict()
    return result


def development_setup(reader):
    jobs = {}
    for name, number, profile in (
        ('ab1', 17, 'ab1-profile'), ('ab2', 17, 'ab2-profile'), ('ab3', 15, 'ab3-profile'),
        ('ab4', 16, 'ab4-profile-regrid1.json'), ('ab5', 7, 'ab5-profile'), ('ab6', 22, 'ab6-profile'),
        ('sc3', 17, 'sc3b-profile'), ('sc4', 17, 'sc4-profile'), ('sc5', 17, 'sc5-profile'),
        ('sc6', 15, 'sc6-profile'), ('sc6', 18, 'sc6-profile'),
    ):
        key = f'diagnostics/{name}-still/frames/frame_{number:06d}.png'
        quad = load_json(input_path(f'diagnostics/{profile}'))['quad']
        jobs[key] = input_path(key), {'saved_quad': quad}
    sc7a = load_json(input_path('diagnostics/sc7a-quad.json'))
    for filename in ('sc7-assist/still.png', 'sc7-assist/stability.png', 'sc7a-assist/still.png',
                     'r13-winkel-links10-20261023/frames/frame_000016.jpg',
                     *(f'sc7a-still/frames/frame_{i:06d}.png' for i in (7, 14, 16, 23))):
        key = f'diagnostics/{filename}'
        jobs[key] = input_path(key), {'saved_quad': sc7a if filename.startswith('sc7a') else None}
    for stamp in ('20261014T123033', '20261014T123533', '20261014T154211', '20261023T123820',
                  '20261026T082712', '20261026T083418', '20261028T134306', '20261028T123044',
                  '20261028T110248', '20261023T100613', '20261028T113959', '20261028T114104',
                  '20261113T121656', '20261113T130253', '20261113T115232'):
        key = f'live/live-{stamp}Z/setup'
        folder = input_path(key)
        paths = sorted(folder.glob('still*.png'))
        if not paths:
            raise ValueError(f'Einrichtungsaufnahmen fehlen: {folder}')
        if stamp == '20261014T123033':
            paths.append(folder / 'stability.png')
        proposal = folder / 'proposal.json'
        saved = load_json(proposal).get('quad') if proposal.exists() else None
        for path in paths:
            jobs[f'{key}/{path.name}'] = path, {'saved_quad': saved}
    return setup_samples(reader, jobs)


def tracking(reader):
    """OCR auf Trackingquads, bei Verlust separat auf dem festen Einrichtungsquad."""
    result = {}
    for stamp in ('20261028T110248', '20261028T113238', '20261028T121101', '20261030T113427',
                  '20261111T103604', '20261111T122753'):
        session = f'live-{stamp}Z'
        root = input_path(f'live/{session}/profile.json').parent
        quad = load_json(root / 'profile.json')['quad']
        folder = diagnose_dir(root / 'run-01')
        for line in (folder / 'images.jsonl').read_text().splitlines():
            row = json.loads(line)
            recorded = row['tracking'].get('quad')
            result[f'{session}/{row["image"]}'] = {
                'quad_quelle': 'tracking' if recorded is not None else 'einrichtungsprofil',
                'reader': reading(reader, image(folder / row['image']), recorded if recorded is not None else quad),
            }
    fixtures = Path('tests/fixtures/r13')
    for folder, metadata in ((fixtures, 'r13-fixtures.json'), (fixtures / 'display-motion-20261023', 'sources.json')):
        quad = load_json(folder / metadata)['quad']
        for path in sorted(folder.glob('*.jpg')):
            result[str(path.relative_to(fixtures))] = {'reader': reading(reader, image(path), quad)}
    profile = load_json(input_path('live/live-20261021T151835Z/profile.json'))
    for i in (289, 390, 440):
        key = f'diagnostics/r13-werteplan-20261021/frames/frame_{i:06d}.png'
        result[key] = {'reader': reading(reader, image(input_path(key)), profile['quad'])}
    return result


def dataset_samples(reader, root, profile_map):
    dataset = runpy.run_path(str(Path(__file__).with_name('dotmatrix-dataset.py')))
    stats = {}
    records = dataset['load_resolved_records'](root, dataset['read_profile_map'](profile_map), stats=stats)
    if not records:
        raise ValueError(f'Keine aufloesbaren Reader-Check-Proben unter {root}')
    return {rec.sample_id: asdict(reader.read(rec.crop_gray, CharLayout(grid=rec.grid, unit='mV/V')))
            for rec in records}, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dataset-root', type=Path, default=Path('var/workbench/datasets'))
    parser.add_argument('--dev-data', type=Path, default=Path(os.getenv('DISPREAD_DEV_DATA', '/mnt/ssd/picam-dev')))
    args = parser.parse_args()
    os.environ['DISPREAD_DEV_DATA'] = str(args.dev_data)
    cv2.setNumThreads(1)
    reader = DotMatrixReader.from_file(DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256)
    sources = {}
    sources['frame_tracking'] = tracking(reader)
    sources['reader_check'], stats = dataset_samples(reader, args.dataset_root,
                                                     input_path('diagnostics/dotmatrix-profile-map.json'))
    sources['setup'] = development_setup(reader)
    sources['regression'] = regression(reader, args.dev_data)
    with args.out.open('w', encoding='utf-8') as stream:
        json.dump({'quellen': sources, 'datensatz_zaehler': stats}, stream, ensure_ascii=False,
                  sort_keys=True, allow_nan=False, separators=(',', ':'), default=json_value)
        stream.write('\n')
    print({key: len(samples) for key, samples in sources.items()})


if __name__ == '__main__':
    main()
