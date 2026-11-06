"""Machine-readable readiness; local COM readiness never proves GSV receipt."""
from dataclasses import dataclass, replace

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


def aggregate_readiness(base: Readiness, worker: WorkerStatus | None) -> Readiness:
    if worker is None:
        return base
    if worker.code:
        return replace(base, output='blocked', com='blocked', next_action=worker.code, gsv='unconfirmed')
    if not worker.output_ready:
        return replace(base, output='unavailable', com=worker.state, gsv='unconfirmed')
    return replace(base, com='driver_ready', gsv='unconfirmed')
