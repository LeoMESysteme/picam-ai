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
from .speicher import SpeicherView
from .uart import UartView
from .zertifikat import ZertifikatView

TABS = (DashboardView, LaufView, DienstView, KameraView, AusgabeView, ZertifikatView, SpeicherView,
        NetzwerkView, UartView, KontoView, ProtokollView, EinstellungenView)

__all__ = ['TABS']
