"""Bildquellen: die Trennstelle, die Arbeiten ohne Kamera moeglich macht.

Die Pipeline sieht nur `Iterator[Frame]`. Ob dahinter die AI Camera, eine
aufgezeichnete Session, ein Bildordner oder ein Generator steckt, bemerkt sie
nur an `capabilities` und an `Frame.timebase`.

`picamera2` wird ausschliesslich in den Kameramodulen importiert, und zwar erst
in der Factory (Lazy Import). Das ist die technische Voraussetzung dafuer, dass
Tests und Beispiele ohne Kamera - und sogar auf einem Nicht-Pi - laufen.

URI-Schemata:

    picamera2://?size=2028x1520&fps=10
    imx500://?rpk=/usr/share/imx500-models/....rpk&size=2028x1520
    folder:///pfad?rate=10&glob=*.png
    video:///pfad/aufnahme.mp4
    synthetic://seven-seg?digits=6&unit=N&noise=0.2&glare=0.1
    replay:///var/lib/dispread/sessions/2026-09-07_first-light
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs, urlparse

from dispread.frames.types import Capability, Frame, InferenceResult

__all__ = [
    "Capability",
    "Frame",
    "FrameSource",
    "InferenceResult",
    "known_schemes",
    "open_source",
]


@runtime_checkable
class FrameSource(Protocol):
    """Eine Bildquelle."""

    def open(self) -> None: ...

    def close(self) -> None: ...

    def frames(self) -> Iterator[Frame]: ...

    @property
    def source_id(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[Capability]: ...

    def describe(self) -> dict[str, Any]:
        """Selbstbeschreibung fuer das Runartefakt - was war die Quelle?"""
        ...


def _query_scalars(uri: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(uri).query).items()}


def _parse_size(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    w, _, h = value.partition("x")
    return int(w), int(h)


def _open_synthetic(uri: str) -> FrameSource:
    from dispread.frames.synthetic_source import SyntheticSource

    parsed = urlparse(uri)
    q = _query_scalars(uri)
    return SyntheticSource(
        kind=parsed.netloc or "seven-seg",
        digits=int(q.get("digits", 5)),
        decimals=int(q.get("decimals", 2)),
        unit=q.get("unit", "N"),
        noise=float(q.get("noise", 0.0)),
        glare=float(q.get("glare", 0.0)),
        perspective=float(q.get("perspective", 0.0)),
        blur=float(q.get("blur", 0.0)),
        count=int(q["count"]) if "count" in q else None,
        seed=int(q.get("seed", 0)),
    )


def _open_folder(uri: str) -> FrameSource:
    from dispread.frames.folder_source import FolderSource

    parsed = urlparse(uri)
    q = _query_scalars(uri)
    return FolderSource(
        directory=parsed.path,
        pattern=q.get("glob", "*.png"),
        rate_hz=float(q.get("rate", 10.0)),
    )


def _open_video(uri: str) -> FrameSource:
    from dispread.frames.video_source import VideoSource

    return VideoSource(path=urlparse(uri).path)


def _open_replay(uri: str) -> FrameSource:
    from dispread.frames.replay_source import ReplaySource

    return ReplaySource(session_dir=urlparse(uri).path)


def _open_picamera2(uri: str) -> FrameSource:
    from dispread.frames.picamera_source import Picamera2Source

    q = _query_scalars(uri)
    return Picamera2Source(
        size=_parse_size(q.get("size")) or (2028, 1520),
        fps=float(q["fps"]) if "fps" in q else None,
    )


def _open_imx500(uri: str) -> FrameSource:
    from dispread.frames.imx500_source import Imx500Source

    q = _query_scalars(uri)
    if "rpk" not in q:
        raise ValueError("imx500:// braucht den Parameter rpk=<pfad zur .rpk>")
    return Imx500Source(
        rpk=q["rpk"],
        size=_parse_size(q.get("size")) or (2028, 1520),
        fps=float(q["fps"]) if "fps" in q else None,
    )


_REGISTRY: dict[str, Callable[[str], FrameSource]] = {
    "synthetic": _open_synthetic,
    "folder": _open_folder,
    "video": _open_video,
    "replay": _open_replay,
    "picamera2": _open_picamera2,
    "imx500": _open_imx500,
}


def known_schemes() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def open_source(uri: str) -> FrameSource:
    """Bildquelle aus einer URI erzeugen.

    Der Import der jeweiligen Implementierung passiert erst hier, damit ein
    fehlendes picamera2 die uebrigen Quellen nicht unbenutzbar macht.
    """
    scheme = urlparse(uri).scheme
    if scheme not in _REGISTRY:
        raise ValueError(f"unbekanntes Schema {scheme!r}; bekannt: {', '.join(known_schemes())}")
    return _REGISTRY[scheme](uri)
