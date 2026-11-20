#!/usr/bin/env python3
"""Build an explicit, verified PiCam release; never download or publish."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New tar.gz outside the source worktree")
    parser.add_argument("--templates", type=Path, required=True, help="Explicit frozen template; SHA256 is verified")
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("picam_release_builder", root / "packaging/release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        artifact = module.build_release(root, args.output, args.templates, args.release_id)
    except (OSError, ValueError, SyntaxError) as exc:
        parser.exit(2, f"Release build failed: {exc}\n")
    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
