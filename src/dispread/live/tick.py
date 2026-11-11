"""Fester Pi-Takt; Daten und Uhrumrechnung bleiben vom Drahtformat getrennt."""
import math
import subprocess
import time
from dataclasses import dataclass
from fractions import Fraction

from dispread.live.clock import ClockLog
from dispread.records import TimeBaseKind, ValueStatus, to_boottime_ns
from dispread.sink.protocol.userdefined import UserDefinedFormatter
from dispread.sink.protocol.userdefined_4ch import checked_value_text


@dataclass(frozen=True, slots=True)
class Tick:
    seq: int
    valid: bool
    value_text: str | None
    time_unix_ns: int
    frame_sequence: int | None


class TickTimebase:
    """REALTIME-MONOTONIC am Start geklammert messen und danach einfrieren.

    Kamerazeiten werden ausschliesslich mit to_boottime_ns umgerechnet.
    Der BOOTTIME-Versatz wird frisch geprueft, damit Suspend fail-closed ist.
    NTP-Status ist kein Unsicherheitsbudget; OQ-43 bleibt offen.
    """

    def __init__(self, clock_log, *, clock=None, ntp_status=None):
        self.clock_log = clock_log
        self._clock = clock or time.clock_gettime_ns
        if not clock_log.samples:
            clock_log.sample()
        self.offset_ns, self.offset_uncertainty_ns = self._measure()
        self.ntp_synchronized = ntp_status if ntp_status is not None else _ntp_status()
        self.max_deviation_ns = 0

    def _measure(self):
        before = self._clock(time.CLOCK_MONOTONIC)
        realtime = self._clock(time.CLOCK_REALTIME)
        after = self._clock(time.CLOCK_MONOTONIC)
        return realtime - (before + after) // 2, (after - before + 1) // 2

    def observe(self):
        offset, uncertainty = self._measure()
        deviation = abs(offset - self.offset_ns)
        # Aufrufdauer nicht als Uhrsprung ausgeben.
        if deviation > uncertainty + self.offset_uncertainty_ns + 1_000_000:
            self.max_deviation_ns = max(self.max_deviation_ns, deviation)

    def capture_monotonic_ns(self, timestamp):
        session = {'clock_offset_boottime_minus_monotonic_ns': self.clock_log.checked_offset_bounds()}
        boot = to_boottime_ns(timestamp.to_dict(), session)
        # Auch fuer SENSOR_BOOTTIME die sichere Rueckrechnung pruefen; bei
        # Suspend darf kein Startversatz auf eine neue Uhrenpaarung treffen.
        mono_origin_boot = to_boottime_ns({'base': TimeBaseKind.HOST_MONOTONIC.value, 'value_ns': 0}, session)
        return boot - mono_origin_boot

    def unix_ns(self, monotonic_ns):
        # Bereits auf MONOTONIC bezogener Zeitpunkt + gepaarter Startversatz.
        return monotonic_ns + self.offset_ns

    def status(self):
        return {
            'realtime_minus_monotonic_ns': self.offset_ns,
            'offset_measurement_uncertainty_ns': self.offset_uncertainty_ns,
            'ntp_synchronized': self.ntp_synchronized,
            'time_uncertainty_ns': None,
            'time_base': 'unix_realtime_from_monotonic',
            'provisional': True,
            'realtime_jump_detected': bool(self.max_deviation_ns),
            'realtime_max_deviation_ns': self.max_deviation_ns,
        }


def _ntp_status():
    try:
        result = subprocess.run(['timedatectl', 'show', '--property=NTPSynchronized', '--value'],
                                capture_output=True, text=True, timeout=1, check=True)
        value = result.stdout.strip()
        return value if value in ('yes', 'no') else 'unknown'
    except (OSError, subprocess.SubprocessError):
        return 'unknown'


def validate_rate(rate_hz):
    if (type(rate_hz) not in (int, float) or not math.isfinite(rate_hz)
            or not 1 <= rate_hz <= 10):
        raise ValueError('Takt muss zwischen 1 und 10 Hz liegen')
    return rate_hz


class Ticker:
    """Latest-only je Rasterfenster; nach Verspaetung nur den aktuellen Takt.

    Der Aufrufer serialisiert on_record/due. Gleicher Zahlenwert aus neuem
    Bild ist erlaubt, erneutes Senden desselben Bilds bleibt gesperrt.
    """

    def __init__(self, rate_hz=10, clock_ns=time.monotonic_ns, max_frame_age_ns=500_000_000,
                 *, timebase=None):
        self.rate_hz = validate_rate(rate_hz)
        if max_frame_age_ns <= 0:
            raise ValueError('max_frame_age_ns muss positiv sein')
        self.timebase = timebase or TickTimebase(ClockLog())
        self.start_ns = clock_ns()
        self._period = Fraction(1_000_000_000) / Fraction(str(rate_hz))
        self.max_frame_age_ns = max_frame_age_ns
        self._seq = self._total = self._valid = self._missed = 0
        self._latest = None
        self._last_frame = -1

    @property
    def next_deadline_ns(self):
        return self.start_ns + math.ceil((self._seq + 1) * self._period)

    def on_record(self, record):
        self._latest = record

    def due(self, now_ns):
        seq = int(Fraction(now_ns - self.start_ns) // self._period)
        if seq <= self._seq:
            return None
        self.timebase.observe()
        self._missed += seq - self._seq - 1
        self._seq = seq
        deadline = self.start_ns + math.ceil(seq * self._period)
        record = self._latest
        text = capture = None
        if record is not None and record.status is ValueStatus.VALID and record.frame_sequence > self._last_frame:
            try:
                capture = self.timebase.capture_monotonic_ns(record.capture_timestamp)
                candidate = checked_value_text(record.raw_text)
                # Bestand prueft auch Text/Wert-Konsistenz dezimal und exakt.
                # Neues, noch nicht gesendetes Bild und jünger als die Altersgrenze.
                # Kein Fenster-Zwang auf den eigenen Takt: Die Auswertung braucht
                # 50-90 ms, der Zeitkanal trägt die echte Erfassungszeit
                # (Simulation Lauf 11.11.: 40 % statt 51 % gültige Takte mit Fenster).
                if (capture <= now_ns and now_ns - capture < self.max_frame_age_ns
                        and UserDefinedFormatter().format(record) is not None):
                    text = candidate
            except ValueError:
                pass  # Unbekannte Zeitbasis, Suspend oder reservierter Text: Fehlwert.
        valid = text is not None
        if valid:
            self._last_frame = record.frame_sequence
        self._total += 1
        self._valid += int(valid)
        return Tick(seq, valid, text, self.timebase.unix_ns(capture if valid else deadline),
                    record.frame_sequence if valid else None)

    def stats(self):
        return {'seq': self._seq, 'total': self._total, 'valid': self._valid,
                'invalid': self._total - self._valid, 'missed': self._missed}
