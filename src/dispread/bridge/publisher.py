"""Live output adapter: legacy config names select paired UART or WSS only."""
from __future__ import annotations

from .output_state import OutputState


class PairedOutputPublisher(OutputState):
    def __init__(self, config, out_dir, *, hub, demo=False, run_id=None, release=None,
                 tick_rate_hz=None, tick_max_frame_age_ns=None):
        # Frischegrenze nur fuer die bestaetigte Testfreigabe echter Werte;
        # max_frame_age_ms ist der bestehende Konfigurationswert (1..1000 ms).
        # B2: mit tick_rate_hz entscheidet der Pi-Takt (Ticker) ueber jede Zeile.
        super().__init__(out_dir, demo=demo, release=release,
                         max_offer_age_ns=(config.max_frame_age_ms * 1_000_000
                                           if release and tick_rate_hz is None else None),
                         tick_rate_hz=tick_rate_hz, tick_max_frame_age_ns=tick_max_frame_age_ns)
        self.config, self.hub = config, hub
        if run_id is not None:
            self.run_id = run_id
        self._bound = False

    def start(self, *, clock_log=None):
        if self.config.transport == 'off':
            self._state = 'off'
            return
        if self.hub is None:
            raise ValueError('paired bridge hub is not configured')
        transport = 'network' if self.config.transport == 'tcp' else 'uart'
        if transport == 'uart' and not self.hub.status()['uart_prepared']:
            raise ValueError('UART requires explicit operator prepare')
        super().start(clock_log=clock_log)
        try:
            self.hub.bind_run(self.run_id, self, transport=transport)
            self._bound = True
        except BaseException:
            super().stop()
            raise

    def metadata(self):
        return {**self.config.to_dict(), **super().metadata(),
                'protocol_version': 2, 'paired': True,
                'wire_transport': 'wss' if self.config.transport == 'tcp' else self.config.transport}

    def status(self):
        status = {'transport': self.config.transport, **super().status()}
        if self.hub and status['state'] == 'waiting':
            ready = self.hub.status()
            transport = 'network' if self.config.transport == 'tcp' else self.config.transport
            if ready['connected'] and ready['transport'] == transport:
                status['state'] = 'bridge_connected'
        return status

    def stop(self):
        if self.tick_mode:
            # Erst Takte ausliefern lassen (begrenzt), dann die Bindung loesen.
            try:
                self._stop_ticks()
            except OSError:
                pass  # audit_failed ist gesetzt; Abbau geht weiter
        try:
            if self._bound:
                self.hub.unbind_run(self.run_id)
                self._bound = False
        finally:
            super().stop()
