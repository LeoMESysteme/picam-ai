"""Die gemeinsame venv darf keinen anderen Checkout in die Tests einschleusen."""

from pathlib import Path

import dispread


def test_dispread_kommt_aus_diesem_checkout():
    expected = Path(__file__).resolve().parents[1] / "src" / "dispread" / "__init__.py"
    assert dispread.__file__ is not None
    actual = Path(dispread.__file__).resolve()
    assert actual == expected.resolve(), f"dispread kommt aus {actual}, erwartet {expected}"
