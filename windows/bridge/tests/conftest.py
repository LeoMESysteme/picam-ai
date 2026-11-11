"""Gemeinsame Testeinstellungen: Oberfläche ohne Bewegung (deterministisch), offscreen."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DISPREAD_UI_MOTION', '0')
os.environ.setdefault('DISPREAD_UI_FIRST_RUN_MODES', '0')   # Moduswahl beim ersten Start nur in eigenen Tests
