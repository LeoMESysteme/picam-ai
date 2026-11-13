"""Machine-readable readiness; local COM readiness never proves GSV receipt."""
from dataclasses import dataclass, replace

from dispread.bridge.output_state import RELEASE_BLOCK
from dispread.bridge.protocol import TEST_RELEASE

from .worker import WorkerStatus


@dataclass(frozen=True)
class Readiness:
    components: str
    adapter: str
    peer: str
    output: str
    com: str
    gsv: str
    next_action: str | None


def peer_output_readiness(state: str, run_id: str | None, release_block: str | None,
                          release: str | None = None) -> tuple[str, str | None]:
    """Project validated peer evidence to fixed codes, never peer UI instructions.

    ``test_release`` (R1, 2026-11-09) only from the authenticated Pi marker
    ``release == "test_unaccepted"`` of the current run; a block always wins.
    """
    if release_block is not None:
        return 'blocked', 'dut_release_blocked' if release_block == RELEASE_BLOCK else 'peer_release_blocked'
    if state == 'output_off' or (state == 'ready' and run_id is None):
        return 'output_off', 'output_off'
    if state == 'ready' and release is not None:
        return ('test_release', None) if release == TEST_RELEASE else ('unavailable', 'peer_output_unknown')
    if state == 'ready':
        return 'demo_only', None
    if state == 'ended':
        return 'ended', 'run_ended'
    return 'unavailable', 'peer_output_unknown'


def aggregate_readiness(base: Readiness, worker: WorkerStatus | None) -> Readiness:
    if worker is None:
        return base
    if worker.code:
        return replace(base, output='blocked', com='blocked', next_action=worker.code, gsv='unconfirmed')
    if not worker.output_ready:
        # Peer off/block/ended evidence remains visible; COM independently says
        # idle/starting/recovering. A local failure above always wins.
        output = base.output if base.output in {'output_off', 'blocked', 'ended'} else 'unavailable'
        return replace(base, output=output, com=worker.state, gsv='unconfirmed')
    return replace(base, com='driver_ready', gsv='unconfirmed')
