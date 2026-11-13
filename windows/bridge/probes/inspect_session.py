"""Read-only archive evidence probe; exit 2 means known but export blocked."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from dispread_bridge_app.session_templates import (
    SessionTemplateError,
    inspect_template,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path, help='Existing session/channel file to inspect')
    args = parser.parse_args()
    report = {'provisional': True, 'time_claim': False, 'automatic_export_allowed': False}
    try:
        evidence = inspect_template(args.path)
    except (SessionTemplateError, OSError) as error:
        report.update(status='unknown_template', detail=str(error))
        print(json.dumps(report))
        return 1
    report.update(asdict(evidence))
    try:
        evidence.require_automatic_export()
    except SessionTemplateError as error:
        report.update(status='automatic_export_blocked', detail=str(error))
        print(json.dumps(report))
        return 2
    report.update(status='restricted_generator_available', automatic_export_allowed=True)
    print(json.dumps(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
