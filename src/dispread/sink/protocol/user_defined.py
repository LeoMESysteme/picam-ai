"""Provisional, single-channel GSVmulti UserDefined formatter.

Receiver acceptance, including NaN semantics, is still a Windows test gate.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from dispread.records import InvalidValuePolicy, ValueRecord, ValueStatus
from dispread.sink.protocol import FormatterCapabilities

_NUMBER = re.compile(r"[+-]?[0-9]+\.[0-9]+", re.ASCII)


@dataclass(frozen=True)
class UserDefinedFormatter:
    invalid_policy: InvalidValuePolicy = InvalidValuePolicy.OMIT_RECORD
    demo: bool = False

    def __post_init__(self):
        allowed = {InvalidValuePolicy.OMIT_RECORD}
        if self.demo:
            allowed.add(InvalidValuePolicy.SEND_NAN)
        if self.invalid_policy not in allowed:
            raise ValueError("Invalid policy requires receiver evidence; NaN is demo-only")

    @property
    def capabilities(self) -> FormatterCapabilities:
        return FormatterCapabilities(
            format_id="user_defined/provisional",
            carries_capture_timestamp=False,
            timestamp_resolution_ns=None,
            supported_invalid_policies=frozenset(
                {InvalidValuePolicy.OMIT_RECORD, InvalidValuePolicy.SEND_NAN}
                if self.demo
                else {InvalidValuePolicy.OMIT_RECORD}
            ),
            provisional=True,
        )

    def format(self, record: ValueRecord) -> bytes | None:
        if record.status is not ValueStatus.VALID:
            return b"%NaN\r\n" if self.invalid_policy is InvalidValuePolicy.SEND_NAN else None
        raw = record.raw_text
        if (
            record.unit != "mV/V"
            or record.value is None
            or not math.isfinite(record.value)
            or not isinstance(raw, str)
            or len(raw) > 32
            or not _NUMBER.fullmatch(raw)
            or float(raw) != record.value
        ):
            raise ValueError("Value must be a finite, matching decimal DUT value in mV/V")
        return ("%" + raw + "\r\n").encode("ascii")
