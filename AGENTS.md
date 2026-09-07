# Repository Guidelines

## Project Structure & Module Organization

This project reads measurement-amplifier displays using a Raspberry Pi 5 and AI Camera, with serial output to GSVmulti as the intended integration.

- `src/dispread/`: Python package. `frames/` defines frames and synthetic inputs; `detect/` handles manual display regions; `ocr/` decodes seven-segment displays. Shared modules define layouts, records, validation, and runtime paths.
- `scripts/camera-commissioning.sh`: read-only Raspberry Pi camera diagnostics.
- `Konzept.md`: German-language design and measurement requirements.
- `pyproject.toml`: packaging, Ruff, and pytest configuration.
- `tests/` is configured but does not exist yet. No committed asset collection exists; generated diagnostics belong under ignored `var/`.

`CLAUDE.md` contains outdated project-status statements; verify workflow details against current files.

## Build, Test, and Development Commands

Use Python 3.13 or newer. NumPy, OpenCV, pyserial, Picamera2, and libcamera must come from Debian system packages; pip copies can cause ABI conflicts.

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip install 'pytest>=8' 'ruff>=0.6'
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
bash scripts/camera-commissioning.sh
```

These commands create the environment, install the editable package and development tools, lint, test, and diagnose camera readiness. Run Python tooling through `.venv/bin/python`. Pytest currently has no tests to collect. Declared `dispread-doctor` and `dispread-replay` entry points lack implementation modules; they are not usable run commands yet.

## Coding Style & Naming Conventions

Use four-space indentation, type annotations, and descriptive docstrings, matching existing modules. Use `snake_case` for functions/modules, `PascalCase` for classes, and `UPPER_CASE` for constants. Ruff targets Python 3.13 with a 120-character configured line length and checks imports, common errors, modernization, and bug patterns.

## Testing Guidelines

Add pytest tests under `tests/test_*.py` with `test_*` functions. Prefer synthetic frames for reproducible camera-free tests. Mark camera, UART, and lengthy tests with `hardware`, `serial`, and `slow`, respectively. Run hardware-independent tests with `-m "not hardware and not serial"`. No coverage threshold is configured.

## Commit & Pull Request Guidelines

Existing commits use short, action-oriented subjects in English or German; no mandatory prefix convention exists. Keep commits focused. PRs should explain behavior changes, related requirements/issues, validation performed, and hardware limitations. Include diagnostic images when changing visual recognition.

## Measurement & Configuration Constraints

Never correct DUT readings using reference values or silently reuse stale values. Preserve explicit validity states and timestamp semantics. Override runtime locations using `DISPREAD_*` variables from `paths.py` during tests. Keep SSH keys and generated captures out of commits.
