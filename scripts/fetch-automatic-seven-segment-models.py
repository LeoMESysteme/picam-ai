#!/usr/bin/env python3
"""Fetch pinned public model artifacts; never install a training framework."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'experiments/automatic_seven_segment/candidates.json')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    root = args.manifest.resolve().parent
    data = json.loads(args.manifest.read_text())
    for candidate in data['candidates']:
        for artifact in candidate.get('artifacts', []):
            destination = (root / artifact['path']).resolve()
            if not destination.is_relative_to(root / 'models'):
                raise ValueError('artifact must remain in the models directory')
            expected = artifact['sha256']
            if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
                print(f'verified {artifact["path"]}')
                continue
            if args.verify_only:
                raise ValueError(f'missing or changed artifact: {destination}')
            if not artifact['url'].startswith('https://'):
                raise ValueError('model download requires HTTPS')
            destination.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(artifact['url'], headers={'User-Agent': 'picam-ai-offline-evaluation/1'})
            with urllib.request.urlopen(request, timeout=90) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError(f'download hash mismatch: {artifact["path"]}')
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            temporary.replace(destination)
            print(f'downloaded and verified {artifact["path"]}')


if __name__ == '__main__':
    main()
