"""Eigene Aufnahme-Verwaltung fuer den Datensatz-Sammelmodus.

Bewusst getrennt vom kleinen vorhandenen ROI-Editor-Cache
(``Controller.frames``, siehe ``command()`` Op ``freeze``): eigene Tokens,
eigene Grenzen. Ein Sammelablauf soll den Editor-Cache nicht verdraengen und
umgekehrt.

Ein Capture-Eintrag bleibt nach einem erfolgreichen Save absichtlich im
Speicher (als ``saved``), statt sofort entfernt zu werden: so bleibt ein
verlorener HTTP-Antwortpfad reparierbar (derselbe Token liefert bei einem
Retry dieselbe, bereits gespeicherte Probe, siehe ``DatasetStore.save_sample``
Idempotenz) statt mit "Aufnahme unbekannt" abzubrechen. Nur *offene* (noch
nicht gespeicherte) Eintraege zaehlen gegen ``MAX_OPEN_CAPTURES`` - ein
gespeicherter Entwurf blockiert keinen neuen Aufnahmeplatz mehr.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

MAX_OPEN_CAPTURES = 2
MAX_TOTAL_BYTES = 64 * 1024 * 1024
CAPTURE_TIMEOUT_S = 10 * 60


class CaptureError(ValueError):
    """Aufnahme unbekannt, abgelaufen, oder ein Limit ist erschoepft."""


class CaptureRegistry:
    def __init__(self, now=time.monotonic):
        self._now = now
        self._captures: dict[str, dict[str, Any]] = {}

    def _expire(self) -> None:
        cutoff = self._now() - CAPTURE_TIMEOUT_S
        expired = [token for token, entry in self._captures.items() if entry["created_at"] < cutoff]
        for token in expired:
            del self._captures[token]

    def begin(self, image, fields: dict) -> str:
        """Ein frisch eingefrorenes Rohbild aufnehmen; liefert den neuen Token.

        Lehnt ab statt ein bestehendes Token still zu verdraengen - Konzept.md
        AGENTS.md-Linie "nicht raten/nicht stillschweigend ueberschreiben".
        """
        self._expire()
        open_count = sum(1 for entry in self._captures.values() if not entry.get("saved"))
        if open_count >= MAX_OPEN_CAPTURES:
            raise CaptureError("Maximal zwei offene Aufnahmen gleichzeitig; zuerst speichern oder verwerfen")
        total = image.nbytes + sum(entry["image"].nbytes for entry in self._captures.values())
        if total > MAX_TOTAL_BYTES:
            raise CaptureError("Rohbildspeicher fuer offene Aufnahmen erschoepft (64 MiB)")
        token = uuid.uuid4().hex
        self._captures[token] = {"created_at": self._now(), "image": image, "saved": False, **fields}
        return token

    def get(self, token: str) -> dict:
        self._expire()
        entry = self._captures.get(token)
        if entry is None:
            raise CaptureError("Aufnahme unbekannt oder abgelaufen; neu aufnehmen")
        return entry

    def mark_saved(self, token: str) -> None:
        entry = self._captures.get(token)
        if entry is not None:
            entry["saved"] = True

    def discard(self, token: str) -> None:
        self._captures.pop(token, None)

    def open_count(self) -> int:
        self._expire()
        return sum(1 for entry in self._captures.values() if not entry.get("saved"))
