"""Optische Displayauslesung von Messverstaerkern (Raspberry Pi 5 + AI Camera).

Fachliche Spezifikation: Konzept.md im Projektwurzelverzeichnis.

Aufbau (die Trennstellen aus Konzept.md §3):

    frames/     Bildquelle    - Kamera, Aufnahme, Bildordner, synthetisch
    detect/     Anzeige finden - bestaetigte ROI (Primaerpfad), Heuristik, IMX500
    rectify     Entzerren und Kontrast aufbereiten
    ocr/        Wert lesen    - 7-Segment (mit Segment-Evidenz), Tesseract
    validate    Freigabe      - Syntax-, Qualitaets- und Zustandsregeln (§7)
    sink/       Ausgabe       - JSONL-Audit-Log, seriell, Telegrammformate (§8)

Nicht verhandelbar (Konzept.md §7), als Invarianten im Code verankert:

* Ein veralteter Wert laeuft nie unmarkiert als aktueller gueltiger Wert weiter.
* Die Erkennung benutzt den Referenzwert nicht, um den DUT-Wert zu korrigieren -
  ValueReader und ReleaseGate bekommen ihn strukturell nicht als Parameter.
* Modell-Konfidenz ist keine nachgewiesene Fehlerwahrscheinlichkeit.
"""

__all__ = ["__version__"]

__version__ = "0.1.0.dev0"
