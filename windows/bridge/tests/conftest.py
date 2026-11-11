"""Gemeinsame Testeinstellungen: Oberfläche ohne Bewegung (deterministisch), offscreen."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DISPREAD_UI_MOTION', '0')
