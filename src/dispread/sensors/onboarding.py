"""Onboarding-Lauf fuer neue Sensoren: Laufmappe, Ereignisstrom, Fragen.

Gemeinsamer Vertrag zwischen Werkzeug-CLI (`picam sensor ...`), Agent und
TUI. Eine Laufmappe enthaelt `request.json` (Eingaben des Assistenten),
`events.jsonl` (ein JSON-Objekt je Zeile, fortlaufende `seq`),
`answers/<id>.json` (Antworten der TUI), optional `cancel` (Abbruch
gewuenscht) sowie `work/` fuer Arbeitsdateien. Der Agent laeuft nur zur
Einrichtungszeit; nichts hiervon gehoert zum laufenden Messpfad (Konzept §2).
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENT_VERSION = 1

#: Feste Checkliste (Schluessel, Bedienertext) in Ablaufreihenfolge.
STEPS: tuple[tuple[str, str], ...] = (
    ("anfrage", "Angaben prüfen"),
    ("werkzeug", "KI-Assistent bereit"),
    ("anschluss", "Anschluss finden"),
    ("schnittstelle", "Schnittstelle erkennen"),
    ("kamera", "Anzeige aufnehmen"),
    ("format", "Format bestimmen"),
    ("bestaetigung", "Bediener bestätigt"),
    ("paket", "Sensorpaket erzeugen"),
    ("pruefung", "Probelesung"),
    ("aktivieren", "Als aktiven Sensor setzen"),
)
STEP_KEYS = tuple(key for key, _ in STEPS)
STEP_STATES = ("waiting", "running", "done", "failed", "skipped")
EVENT_TYPES = ("step", "log", "question", "answer", "error", "done")
QUESTION_KINDS = ("choice", "text", "confirm")

_QID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}\Z")


class OnboardingCancelled(RuntimeError):
    """Der Bediener hat den Lauf abgebrochen (Datei `cancel`)."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "sensor")[:40]


@dataclass(frozen=True)
class RunDir:
    path: Path

    @property
    def events_path(self) -> Path:
        return self.path / "events.jsonl"

    @property
    def request_path(self) -> Path:
        return self.path / "request.json"

    @property
    def answers_dir(self) -> Path:
        return self.path / "answers"

    @property
    def work_dir(self) -> Path:
        return self.path / "work"

    @classmethod
    def create(cls, root: Path, request: dict[str, Any], *, now: datetime | None = None) -> RunDir:
        stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
        name = f"{stamp}-{slugify(str(request.get('name', '')))}"
        path = Path(root) / name
        path.mkdir(parents=True, exist_ok=False)
        run = cls(path)
        run.answers_dir.mkdir()
        run.work_dir.mkdir()
        run.request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run.events_path.touch()
        return run

    @classmethod
    def open(cls, path: Path | str) -> RunDir:
        run = cls(Path(path))
        if not run.request_path.is_file():
            raise ValueError(f"keine Onboarding-Laufmappe (request.json fehlt): {run.path}")
        return run

    def request(self) -> dict[str, Any]:
        return json.loads(self.request_path.read_text(encoding="utf-8"))

    # --- Ereignisse ---------------------------------------------------------
    def append(self, type_: str, **fields: Any) -> dict[str, Any]:
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unbekannter Ereignistyp: {type_}")
        if type_ == "step":
            if fields.get("key") not in STEP_KEYS:
                raise ValueError(f"unbekannter Schritt: {fields.get('key')}")
            if fields.get("state") not in STEP_STATES:
                raise ValueError(f"unbekannter Schrittzustand: {fields.get('state')}")
            fields.setdefault("label", dict(STEPS)[fields["key"]])
        with open(self.events_path, "a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                handle.seek(0)
                seq = sum(1 for line in handle if line.strip()) + 1
                event = {"v": EVENT_VERSION, "seq": seq, "ts": _now(), "type": type_, **fields}
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                handle.flush()
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
        return event

    def step(self, key: str, state: str, detail: str | None = None) -> dict[str, Any]:
        extra = {} if detail is None else {"detail": detail}
        return self.append("step", key=key, state=state, **extra)

    def log(self, text: str, source: str = "tool") -> dict[str, Any]:
        return self.append("log", text=text, source=source)

    def error(self, text: str, step: str | None = None) -> dict[str, Any]:
        extra = {} if step is None else {"step": step}
        return self.append("error", text=text, **extra)

    def done(self, ok: bool, message: str, sensor_id: str | None = None) -> dict[str, Any]:
        extra = {} if sensor_id is None else {"sensor_id": sensor_id}
        return self.append("done", ok=ok, message=message, **extra)

    def read_events(self, since_seq: int = 0) -> list[dict[str, Any]]:
        """Ereignisse mit seq > since_seq; eine halb geschriebene letzte Zeile wird uebergangen."""
        if not self.events_path.exists():
            return []
        events = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and int(event.get("seq", 0)) > since_seq:
                events.append(event)
        return events

    # --- Fragen und Abbruch -------------------------------------------------
    def cancelled(self) -> bool:
        return (self.path / "cancel").exists()

    def request_cancel(self) -> None:
        (self.path / "cancel").touch()

    def answer_path(self, qid: str) -> Path:
        if not _QID.match(qid):
            raise ValueError(f"ungueltige Frage-ID: {qid!r}")
        return self.answers_dir / f"{qid}.json"

    def write_answer(self, qid: str, value: Any) -> None:
        """Von der TUI aufgerufen; atomar ueber eine Zwischendatei."""
        target = self.answer_path(qid)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({"value": value}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, target)

    def ask(self, qid: str, kind: str, prompt: str, options: list[dict[str, str]] | None = None,
            default: Any = None, timeout_s: float | None = None, poll_s: float = 0.2,
            sleep: Callable[[float], None] = time.sleep) -> Any:
        """Frage stellen und blockierend auf die Antwort warten.

        Abbruch -> OnboardingCancelled; Zeitueberschreitung -> TimeoutError
        (gilt als nicht bestaetigt).
        """
        if kind not in QUESTION_KINDS:
            raise ValueError(f"unbekannte Frageart: {kind}")
        if kind == "choice" and not options:
            raise ValueError("Auswahlfrage ohne Optionen")
        target = self.answer_path(qid)
        if target.exists():
            raise ValueError(f"Frage-ID bereits beantwortet: {qid}")
        fields: dict[str, Any] = {"id": qid, "kind": kind, "prompt": prompt}
        if options:
            fields["options"] = options
        if default is not None:
            fields["default"] = default
        self.append("question", **fields)
        waited = 0.0
        while not target.exists():
            if self.cancelled():
                raise OnboardingCancelled("Onboarding abgebrochen")
            if timeout_s is not None and waited >= timeout_s:
                raise TimeoutError(f"keine Antwort auf {qid}")
            sleep(poll_s)
            waited += poll_s
        value = json.loads(target.read_text(encoding="utf-8"))["value"]
        self.append("answer", id=qid, value=value)
        return value
