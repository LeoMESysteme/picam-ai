"""Tabs der picam-Konsole in Anzeigereihenfolge (ein Modul je Tab)."""

from .ausgabe import AusgabeView
from .dashboard import DashboardView
from .dienst import DienstView
from .einstellungen import EinstellungenView
from .kamera import KameraView
from .konto import KontoView
from .lauf import LaufView
from .netzwerk import NetzwerkView
from .protokoll import ProtokollView
from .sensoren import SensorenView
from .speicher import SpeicherView
from .uart import UartView
from .zertifikat import ZertifikatView

TABS = (DashboardView, LaufView, DienstView, KameraView, AusgabeView, ZertifikatView, SpeicherView,
        NetzwerkView, UartView, KontoView, ProtokollView, SensorenView, EinstellungenView)



def visible_tabs(instance=None, enabled: bool | None = None) -> tuple:
    """Tabs der Konsole; Tabs mit ``FEATURE`` nur, wenn der Schalter in den Einstellungen an ist."""
    if enabled is None:
        from .. import sensor_client

        enabled = sensor_client.feature_enabled(instance)
    return tuple(view for view in TABS if not getattr(view, 'FEATURE', '') or enabled)


__all__ = ['TABS', 'visible_tabs']
