"""Bedienertexte zu Nachfuehr- und Lesegruenden (Quelle fuer /live, Setup und Pruefungen)."""

# Human-readable Gruende fuer eine abgelehnte Nachfuehrung (track.py:
# TrackResult.reason); siehe _reading_rows.
REASONS = {
    "low_score": "Bild passt nicht mehr zur Referenz",
    "bildgroesse_abweichend": "bildgroesse weicht von der Referenz ab",
    "vorschlag_ungeeignet": "rahmenvorschlag ungeeignet",
    "zu_wenig_rahmenbereiche": "zu wenige geeignete Rahmenbereiche",
    # OQ-70: Bedienhilfe schon bei der Einrichtung, nicht erst als spaeteres Laufproblem.
    "rahmenbereiche_einseitig": (
        "nachfuehrbereiche zu einseitig verteilt; Kamera leicht drehen oder verschieben und neu einrichten"),
    "rahmenbereiche_ohne_reserve": (
        "nachfuehrbereiche ohne Reserve fuer zwei Ausfaelle; Kamera leicht drehen oder verschieben "
        "und neu einrichten"),
    "rahmenbereiche_zweitbild_instabil": (
        "rahmenbereiche im Zweitbild nicht stabil genug wiedergefunden; "
        "mehr Licht auf den Rahmen geben oder anderen Blickwinkel waehlen und neu einrichten"),
    "zweitbild_peak_zu_niedrig": "Rahmenbereich im Zweitbild nicht deutlich genug wiedergefunden",
    "zweitbild_mehrdeutig": "Rahmenbereich im Zweitbild nicht eindeutig wiedergefunden",
    "zweitbild_suchrand": "Rahmenbereich im Zweitbild am Rand des Suchbereichs",
    "zweitbild_am_bildrand": "Rahmenbereich im Zweitbild zu nah am Bildrand",
    "zweitbild_lage_abweichend": "Rahmenbereich im Zweitbild an anderer Position wiedergefunden",
    "rahmenbereiche_ersatz_ohne_lagekonsistenz": (
        "Ersatz-Rahmenbereiche ohne belegte Lagekonsistenz in den Einzelbildern; "
        "Aufbau ruhig halten, mehr Licht auf den Rahmen geben oder anderen Blickwinkel waehlen und neu einrichten"),
    "rahmenbereiche_zweitbild_fehlt": "rahmenbereiche ohne unabhaengiges Zweitbild; neu einrichten",
    "rahmenbereiche_einzelbilder_fehlen": "rahmenbereiche ohne ausreichende Einzelbilder; neu einrichten",
    "zu_wenig_rahmenmerkmale": "zu wenige Rahmenmerkmale wiedergefunden",
    "rahmen_mehrdeutig": "rahmenmerkmale nicht eindeutig zugeordnet",
    "rahmen_unstimmig": "rahmenbewegungen passen nicht zusammen",
    "lcd_rand_fehlt": "lcd-rand nicht ausreichend bestaetigt",
    "shift_out_of_bounds": "zu weit verschoben",
    "rotation_out_of_bounds": "zu stark gedreht",
    "ecc_diverged": "Anzeige nicht wiedergefunden",
}

DISPLAY_DEFECT_HINT = "Kamera leicht verschieben, Glas reinigen oder Reflex abschatten"
LIVE_CAUSE_TEXT = {
    "leerzelle_gestoert": "gestoert - Kratzer, Staub oder Reflex?",
    "zelle_unbekannt": "Zeichen nicht sicher erkannt",
    "zelle_mehrdeutig": "Zeichen mehrdeutig",
    "vorzeichen": "Vorzeichen nicht sicher erkannt",
    "format": "Zahlenformat nicht sicher erkannt",
    "kontrast": "Kontrast zu gering",
    "ueberbelichtet": "Anzeige ueberbelichtet",
    "anzeige_wechselt": "Wert wechselt",
    "testlauf_keine_freigabe": "Testlauf: keine Wertfreigabe",
    "awaiting_confirmation": "Warte auf Bestaetigung in weiteren Bildern",
    "decimal_point_unknown": "Dezimalpunkt nicht sicher erkannt",
    "sign_region_unreadable": "Vorzeichenbereich nicht lesbar",
    "low_segment_margin": "Zeichen nicht sicher erkannt",
    "low_contrast": "Kontrast zu gering",
    "no_value": "Kein lesbarer Wert",
}


def live_cause(cause: dict) -> dict:
    """Maschinengrund mit ehrlicher Bedienhilfe und Zellnummer ergaenzen."""
    reason = cause['reason']
    parts = reason.split(':')
    cell = None
    if parts[0] == 'leser':
        if len(parts) == 3 and parts[2].isdigit():
            cell = int(parts[2])
        text = LIVE_CAUSE_TEXT.get(parts[1], 'Leser konnte den Wert nicht erkennen')
        if cell is not None:
            position = ' (rechts der Einheit)' if cell in (13, 14, 15) else ' (Trennzelle)' if cell == 8 else ''
            text = f'Zelle {cell}{position}: {text}'
    elif parts[0] == 'tracking_lost':
        text = 'Rahmenbereiche verdeckt oder verschoben - Kamera und Sicht pruefen'
    else:
        text = LIVE_CAUSE_TEXT.get(reason, 'Bild nicht freigegeben - ' + reason)
    return {**cause, 'cell': cell, 'explanation': text}
