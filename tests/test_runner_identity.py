"""Guard against replacing a registered runner UUID while reusing its token."""

import subprocess
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "forgejo-runner-identity.sh"
OLD = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"


def check(config: Path, uuid: str, token_file: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GUARD), str(config), uuid, token_file],
        text=True,
        capture_output=True,
        check=False,
    )


def test_existing_runner_rejects_new_uuid_without_new_token(tmp_path: Path):
    config = tmp_path / "config.yml"
    config.write_text(f"server:\n  connections:\n    ds1515:\n      uuid: {OLD}\n")

    result = check(config, NEW)

    assert result.returncode != 0
    assert "--token-file" in result.stderr
    assert check(config, OLD).returncode == 0
    assert check(config, NEW, "/tmp/new-runner-token").returncode == 0


def test_fresh_runner_does_not_require_existing_identity(tmp_path: Path):
    assert check(tmp_path / "missing.yml", NEW).returncode == 0
