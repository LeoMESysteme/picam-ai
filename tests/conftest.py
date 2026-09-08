"""Pytest-Konfiguration.

`--mode` uebernommen von /opt/mehub/current/tests/conftest.py: mock laeuft
ohne Hardware, real zusaetzlich die als @hardware/@serial markierten Tests.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--mode",
        action="store",
        default="mock",
        choices=("mock", "real"),
        help="mock = ohne Hardware (Default), real = mit Kamera und UART",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--mode") == "real":
        return
    skip = pytest.mark.skip(reason="braucht --mode=real (Hardware)")
    for item in items:
        if "hardware" in item.keywords or "serial" in item.keywords:
            item.add_marker(skip)
