"""Die Produktinstallation darf kein Entwicklungsmedium voraussetzen."""

from pathlib import Path


def test_no_dev_data_in_src():
    root = Path(__file__).resolve().parents[1] / "src"
    forbidden = (b"DISPREAD_DEV_DATA", b"DEV_DATA", b"/mnt/ssd", b"picam-dev", b"_devdata")
    violations = [str(path.relative_to(root)) for path in sorted(root.rglob("*"))
                  if path.is_file() and "__pycache__" not in path.parts
                  and any(token in path.read_bytes() for token in forbidden)]
    assert not violations, f"Entwicklungsdaten im Produktcode: {violations}"
