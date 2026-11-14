"""Feste Port-/Ratenvorgaben ohne Hardwarezugriff beim Import."""

# Pi-5-Datenport; /dev/serial0 ist der reservierte Debug-Header.
GSV_UART_PORT = '/dev/ttyAMA0'
# Direkte UserDefined-Ausgabe. Die Pi/Windows-Bruecke hat ihren eigenen
# UART_BAUD-/LEGACY_UART_BAUD-Vertrag in bridge/baud.py.
DIRECT_UART_BAUD = 115200
