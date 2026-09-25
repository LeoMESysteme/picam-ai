"""Bildquellen: die Trennstelle, die Arbeiten ohne Kamera moeglich macht.

Die Pipeline sieht nur `Iterator[Frame]`. Ob dahinter die StreamCam, eine
aufgezeichnete Session, ein Bildordner oder ein Generator steckt, bemerkt sie
nur an `capabilities` und an `Frame.timebase`.

`cv2`-Kamerazugriff erst in der Factory (Lazy Import). Das ist die technische
Voraussetzung dafuer, dass Tests und Beispiele ohne Kamera - und sogar auf
einem Nicht-Pi - laufen.

URI-Schemata:

    v4l2:///dev/video8?settings=/pfad/camera.json
    v4l2://?settings=/pfad/camera.json   (Geraet ueber USB-ID gesucht)
    folder:///pfad?rate=10&glob=*.png
    video:///pfad/aufnahme.mp4
    synthetic://seven-seg?digits=6&unit=N&noise=0.2&glare=0.1
    replay:///var/lib/dispread/sessions/2026-09-07_first-light

`picamera2://` und `imx500://` sind außer Betrieb seit 2026-09-25 (StreamCam
statt IMX500, siehe docs/project_history.md) - `open_source()` wirft dafuer
eine gezielte `ValueError`, kein generisches "unbekanntes Schema".

Eine URI aus einem Dateisystempfad wird mit `path_uri()` gebaut, nie per
f-String - siehe dort, warum ein relativer Pfad sonst stillschweigend
beschnitten wird.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs, quote, unquote, urlparse

from dispread.frames.types import Capability, Frame, InferenceResult

__all__ = [
    "Capability",
    "Frame",
    "FrameSource",
    "InferenceResult",
    "known_schemes",
    "open_source",
    "path_uri",
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


def path_uri(scheme: str, path: str | Path, query: str = "") -> str:
    """Dateisystempfad in eine URI dieses Schemas fassen - absolut und kodiert.

    `f"replay://{directory}"` selbst zu bauen ist eine Falle: bei einem
    relativen Pfad (`var/workbench/clips/abc`) liest `urlparse` das erste
    Segment als *Autoritaet* (netloc) und nicht als Pfadanfang - `var` fiel
    so stillschweigend weg und es wurde ein anderes, nicht existierendes
    Verzeichnis geoeffnet (Review-Fund). Deshalb hier: erst absolut machen,
    dann prozentkodieren (Leerzeichen und andere Sonderzeichen), damit der
    ganze Rest wirklich Pfad ist.
    """
    absolute = Path(path).expanduser().resolve()
    uri = f"{scheme}://{quote(str(absolute))}"
    return f"{uri}?{query}" if query else uri


def _filesystem_path(uri: str) -> str:
    """Dateisystempfad aus einer URI - auch aus einer ohne fuehrenden Schraegstrich.

    Gegenstueck zu `path_uri`. Ein von Hand gebautes `replay://relativ/pfad`
    landet mit `relativ` in `netloc`; beide Teile werden hier wieder
    zusammengesetzt, statt den Anfang des Pfads zu verlieren.
    """
    parsed = urlparse(uri)
    return unquote(parsed.netloc + parsed.path)


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

    q = _query_scalars(uri)
    return FolderSource(
        directory=_filesystem_path(uri),
        pattern=q.get("glob", "*.png"),
        rate_hz=float(q.get("rate", 10.0)),
    )


def _open_video(uri: str) -> FrameSource:
    from dispread.frames.video_source import VideoSource

    return VideoSource(path=_filesystem_path(uri))


def _open_replay(uri: str) -> FrameSource:
    from dispread.frames.replay_source import ReplaySource

    return ReplaySource(session_dir=_filesystem_path(uri))


def _open_v4l2(uri: str) -> FrameSource:
    from dispread.camera_settings import load_camera_settings
    from dispread.frames.uvc_source import UvcSource

    q = _query_scalars(uri)
    if "settings" not in q:
        raise ValueError(
            "v4l2:// braucht den Parameter settings=<pfad zur camera.json>"
        )
    settings = load_camera_settings(Path(q["settings"]))
    device = _filesystem_path(uri) or None
    return UvcSource(settings, device=device)


_REGISTRY: dict[str, Callable[[str], FrameSource]] = {
    "synthetic": _open_synthetic,
    "folder": _open_folder,
    "video": _open_video,
    "replay": _open_replay,
    "v4l2": _open_v4l2,
}

#: `picamera2://`/`imx500://` sind ausser Betrieb seit 2026-09-25 (StreamCam
#: statt IMX500) - eine gezielte Fehlermeldung statt "unbekanntes Schema".
_RETIRED_SCHEME_MESSAGE = (
    "IMX500 ausser Betrieb seit 2026-09-25 (StreamCam statt IMX500) - "
    "siehe docs/project_history.md. Aktiver Schema-Ersatz: v4l2://"
)
_RETIRED_SCHEMES = frozenset({"picamera2", "imx500"})


def known_schemes() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def open_source(uri: str) -> FrameSource:
    """Bildquelle aus einer URI erzeugen.

    Der Import der jeweiligen Implementierung passiert erst hier, damit ein
    fehlendes cv2 die uebrigen Quellen nicht unbenutzbar macht.
    """
    scheme = urlparse(uri).scheme
    if scheme in _RETIRED_SCHEMES:
        raise ValueError(_RETIRED_SCHEME_MESSAGE)
    if scheme not in _REGISTRY:
        raise ValueError(f"unbekanntes Schema {scheme!r}; bekannt: {', '.join(known_schemes())}")
    return _REGISTRY[scheme](uri)
