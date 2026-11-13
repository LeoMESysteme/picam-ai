"""Shared Pi↔Windows bridge UART rate; unrelated to direct GSVmulti serial output.

UART_BAUD is the single source for current Pis; they announce it in the profile.
A profile without ``uart_baud`` comes from a Pi built before the field existed,
which still runs the bridge UART at LEGACY_UART_BAUD.
"""

UART_BAUD = 460800
LEGACY_UART_BAUD = 115200
