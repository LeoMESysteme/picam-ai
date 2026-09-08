"""Serielle Ausgabe.

Muster uebernommen von /opt/mehub/current/src/mehub/sim7600/serial.py: Port
oeffnen mit Timeout, Schreibzugriff serialisieren, Fehler zaehlen statt
werfen. Fuer zeilenorientierte Request/Response - falls der Adapter spaeter
Geraetekommandos beantworten muss - ist zusaetzlich
/opt/mehub/current/src/mehub/rm520n/atport.py die Vorlage.

Portwahl auf diesem Pi 5:

* ``/dev/ttyAMA0`` ist der Datenport (durch ``dtparam=uart0=on`` aktiv).
* ``/dev/serial0`` zeigt auf ``ttyAMA10`` und ist der 3-Pin-DEBUG-Header -
  ausdruecklich NICHT der Nutzdatenport.

Elektrisch (Konzept.md §8): Pi-GPIO-Pegel duerfen nicht direkt mit RS-232
verbunden werden. Es braucht einen Transceiver, und die galvanische Trennung
ist fuer den Laboraufbau zu bewerten (OQ-09).
"""

from __future__ import annotations

import threading
import time

from dispread.records import InvalidValuePolicy, TxReceipt, ValueRecord, ValueStatus
from dispread.sink import SinkHealth
from dispread.sink.protocol import TelegramFormatter


class SerialSink:
    """Schreibt Telegramme auf einen seriellen Port oder ein pty.

    Fuer Tests und Beispiele genuegt ein pty-Paar (``socat`` oder
    ``os.openpty()``) - damit ist die ganze Kette pruefbar, ohne dass GSVmulti
    oder ein Transceiver vorhanden sein muss.
    """

    def __init__(
        self,
        port: str,
        formatter: TelegramFormatter,
        *,
        baudrate: int = 115200,
        timeout: float = 1.0,
        write_timeout: float = 1.0,
    ) -> None:
        self.port = port
        self.formatter = formatter
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self._serial = None
        self._lock = threading.Lock()
        self._tx_seq = 0
        self._sent = 0
        self._omitted = 0
        self._errors = 0
        self._last_error: str | None = None

    def open(self) -> None:
        import serial

        self._serial = serial.Serial(
            self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.write_timeout,
        )

    def close(self) -> None:
        with self._lock:
            if self._serial is not None:
                self._serial.close()
                self._serial = None

    def emit(self, record: ValueRecord) -> TxReceipt:
        t0 = time.monotonic_ns()
        self._tx_seq += 1
        policy = getattr(self.formatter, "invalid_policy", None)

        payload = self.formatter.format(record)
        if payload is None:
            # Der Datensatz entfaellt bewusst. Das wird als omitted
            # protokolliert, damit die Luecke im Datenstrom nicht spaeter als
            # Uebertragungsfehler gedeutet wird.
            self._omitted += 1
            return TxReceipt(
                frame_sequence=record.frame_sequence,
                tx_sequence=self._tx_seq,
                format_id=self.formatter.capabilities.format_id,
                wire_bytes=None,
                t_enqueue_ns=t0,
                t_complete_ns=time.monotonic_ns(),
                invalid_policy=policy if isinstance(policy, InvalidValuePolicy) else None,
                omitted=True,
            )

        with self._lock:
            if self._serial is None:
                raise RuntimeError("SerialSink.open() wurde nicht aufgerufen")
            try:
                self._serial.write(payload)
                self._serial.flush()
                self._sent += 1
                complete = time.monotonic_ns()
            except Exception as exc:  # serial.SerialTimeoutException u. a.
                self._errors += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
                complete = None

        return TxReceipt(
            frame_sequence=record.frame_sequence,
            tx_sequence=self._tx_seq,
            format_id=self.formatter.capabilities.format_id,
            wire_bytes=payload,
            t_enqueue_ns=t0,
            t_complete_ns=complete,
            invalid_policy=policy if isinstance(policy, InvalidValuePolicy) else None,
            omitted=False,
        )

    def health(self) -> SinkHealth:
        return SinkHealth(
            open=self._serial is not None,
            sent=self._sent,
            omitted=self._omitted,
            errors=self._errors,
            last_error=self._last_error,
        )


def required_baudrate(records_per_second: float, bytes_per_telegram: int, *, bits_per_byte: int = 10) -> float:
    """Mindestbaudrate fuer eine gewuenschte Datensatzrate.

    Konzept.md §6 warnt, dass ein hoeherer Sendetakt keine zusaetzlichen
    unabhaengigen Messwerte liefert, wenn die Anzeige langsamer aktualisiert.
    Diese Funktion sagt nur, ob die Leitung die gewuenschte Rate ueberhaupt
    tragen kann - nicht, ob die Rate sinnvoll ist.

    `bits_per_byte` ist 10 fuer 8N1 (Start + 8 Daten + Stop).
    """
    return records_per_second * bytes_per_telegram * bits_per_byte


def status_is_sendable(status: ValueStatus, policy: InvalidValuePolicy) -> bool:
    """Wird ein Datensatz mit diesem Status ueberhaupt gesendet?"""
    if status is ValueStatus.VALID:
        return True
    return policy is not InvalidValuePolicy.OMIT_RECORD
