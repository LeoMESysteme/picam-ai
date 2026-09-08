"""Die Einstelltabelle als Daten: eine Quelle fuer Weboberflaeche und TUI.

Reine Funktionen ueber ``Controller.snapshot()``. Keine Kamera, kein Netz,
kein Rendering - deshalb direkt testbar. Der Controller bleibt die
durchsetzende Instanz; was hier steht, ist Bedienhilfe und darf keine
Regel ersetzen.
"""

from __future__ import annotations

MODES = (
    ("setup", "setup", "einrichten, keine Messwertfreigabe"),
    ("run", "run", "Betrieb; in diesem Prototyp ohne Messwertfreigabe"),
    ("annotate", "annotate", "Bild und ROI als Trainingsbeispiel ablegen"),
)
ROLES = (("main", "main (Pruefling)"), ("secondary", "secondary (Referenz)"))
RESOLUTIONS = ((640, 480), (960, 720), (1280, 960), (1640, 1232), (2028, 1520))
FRAMERATES = (5.0, 10.0, 15.0, 20.0, 30.0)
# Schrittweite und Ganzzahligkeit je Kameraregler; Grenzen kommen aus den
# Capabilities der laufenden Kamera, nicht von hier.
NUMBERS = {"ExposureTime": (100, True), "AnalogueGain": (0.1, False), "Contrast": (0.1, False)}
CONTROL_HINTS = {
    "ExposureTime": "Belichtungszeit in Mikrosekunden",
    "AnalogueGain": "Analogverstaerkung; hoehere Werte rauschen mehr",
    "Contrast": "Bildkontrast der Kamerapipeline",
}


def _number(value):
    """Ganzzahlen ohne .0 anzeigen, sonst kurz gerundet."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return str(int(value)) if float(value).is_integer() else str(round(float(value), 4))


def run_blocked(state):
    """Grund, weshalb der Modus run gerade nicht zulaessig ist, sonst None."""
    config = state["config"]
    if not config["confirmed"]:
        return "ROI erst im Kamerabild bestaetigen"
    if not state["live"]:
        return "kein Livebild"
    if state["applied_revision"] != state["revision"]:
        return "Kamerauebernahme abwarten"
    if config["camera"]["controls"].get("AeEnable", True):
        return "feste Belichtung noetig: AeEnable auf false"
    return None


def _row(key, label, kind, value, display, hint, **extra):
    row = {"key": key, "label": label, "kind": kind, "value": value, "display": display, "hint": hint}
    row.setdefault("options", [])
    row.update({"disabled": False, "reason": ""})
    row.update(extra)
    return row


def _option(value, label, ops, disabled=False, reason=""):
    return {"value": value, "label": label, "ops": ops, "disabled": disabled, "reason": reason}


def rows(state):
    """Eine Zeile je Einstellung, in der Reihenfolge der Bedienung."""
    config = state["config"]
    camera = config["camera"]
    controls = camera["controls"]
    capabilities = state["capabilities"]
    observed = state["observed"]
    result = []

    blocked = run_blocked(state)
    result.append(
        _row(
            "mode",
            "modus",
            "choice",
            state["mode"],
            state["mode"],
            next(hint for value, _label, hint in MODES if value == state["mode"]),
            options=[
                _option(
                    value,
                    label,
                    [["mode", {"value": value}]],
                    disabled=bool(value == "run" and blocked),
                    reason=blocked if value == "run" else "",
                )
                for value, label, _hint in MODES
            ],
        )
    )
    result.append(
        _row(
            "role",
            "anzeigenrolle",
            "choice",
            config["role"],
            config["role"],
            "welche Anzeige dieses Profil beschreibt",
            options=[_option(value, label, [["profile.role", {"value": value}]]) for value, label in ROLES],
        )
    )

    current = f"{camera['width']}x{camera['height']}"
    sizes = sorted({*RESOLUTIONS, (camera["width"], camera["height"])})
    result.append(
        _row(
            "resolution",
            "aufloesung",
            "choice",
            current,
            current,
            "Streamneustart; ROI muss danach neu bestaetigt werden",
            options=[
                _option(
                    f"{width}x{height}",
                    f"{width}x{height}",
                    [["camera.set", {"key": "width", "value": width}], ["camera.set", {"key": "height", "value": height}]],
                )
                for width, height in sizes
            ],
        )
    )
    rates = sorted({*FRAMERATES, float(camera["fps"])})
    result.append(
        _row(
            "fps",
            "bildrate",
            "choice",
            _number(camera["fps"]),
            _number(camera["fps"]) + " fps",
            "Streamneustart bei Aenderung",
            options=[
                _option(_number(rate), _number(rate) + " fps", [["camera.set", {"key": "fps", "value": rate}]])
                for rate in rates
            ],
        )
    )

    automatic = controls.get("AeEnable", True)
    if "AeEnable" in capabilities:
        result.append(
            _row(
                "AeEnable",
                "belichtungsautomatik",
                "choice",
                "true" if automatic else "false",
                "an" if automatic else "aus",
                "run braucht feste Belichtung, also aus",
                options=[
                    _option("true", "an (automatisch)", [["camera.set", {"key": "AeEnable", "value": True}]]),
                    _option(
                        "false",
                        "aus (feste Werte uebernehmen)",
                        [["camera.set", {"key": "AeEnable", "value": False}]],
                    ),
                ],
            )
        )
    for name, (step, integer) in NUMBERS.items():
        if name not in capabilities:
            continue
        low, high, default = capabilities[name][0], capabilities[name][1], capabilities[name][2]
        locked = automatic and name in ("ExposureTime", "AnalogueGain")
        value = controls.get(name, observed.get(name, default))
        presets = []
        for label, candidate in (
            ("min", low),
            ("Kameradefault", default),
            ("Istwert", observed.get(name)),
            ("max", high),
        ):
            if candidate is None:
                continue
            candidate = int(candidate) if integer else round(float(candidate), 4)
            if all(preset["raw"] != candidate for preset in presets):
                presets.append({"raw": candidate, "value": _number(candidate), "label": f"{label}: {_number(candidate)}"})
        result.append(
            _row(
                name,
                name.lower(),
                "number",
                _number(value),
                _number(controls[name]) if name in controls else "automatisch",
                CONTROL_HINTS[name] + (f"; {low}..{high}" if not locked else "; nur bei Automatik aus"),
                op="camera.set",
                arg=name,
                integer=integer,
                min=low,
                max=high,
                step=step,
                presets=presets,
                observed=_number(observed[name]) if name in observed else "nicht rueckgemeldet",
                disabled=locked,
                reason="Belichtungsautomatik zuerst ausschalten" if locked else "",
            )
        )

    result.append(
        _row(
            "focus",
            "fokusassistenz",
            "choice",
            "true" if state["focus"] else "false",
            "an" if state["focus"] else "aus",
            "ROI vergroessert; Schaerfe " + _number(state["quality"].get("sharpness", "—")) + " (relativ, Objektiv manuell)",
            options=[
                _option("true", "an (ROI vergroessern)", [["focus", {"value": True}]]),
                _option("false", "aus", [["focus", {"value": False}]]),
            ],
        )
    )

    names = list(state.get("profiles") or [])
    options = [_option(name, name, [["profile.load", {"name": name}]]) for name in names]
    if state["profile"] not in names:
        # Das geladene Profil steht noch nicht auf der Platte, laesst sich also
        # auch nicht laden - es bleibt sichtbar, aber nicht waehlbar.
        options.insert(
            0,
            _option(state["profile"], state["profile"], [], disabled=True, reason="noch nicht gespeichert"),
        )
    result.append(
        _row(
            "profile",
            "profil",
            "choice",
            state["profile"],
            f"{state['profile']} v{config['version']}" + (" *" if state["dirty"] else ""),
            "Laden nur ohne ungespeicherte Aenderung",
            options=options,
            disabled=state["dirty"],
            reason="ungespeicherte Aenderung: speichern oder verwerfen" if state["dirty"] else "",
        )
    )

    roi = config["roi"]
    result.append(
        _row(
            "roi",
            "anzeigebereich",
            "info",
            "",
            ("bestaetigt " + ", ".join(_number(round(v, 4)) for v in roi))
            if config["confirmed"] and roi
            else "nicht bestaetigt",
            "im Kamerabild mit E oder Doppelklick bearbeiten, Enter bestaetigt",
        )
    )
    result.append(
        _row(
            "detection",
            "erkennungsfilter",
            "info",
            "",
            " ".join(f"{name}={_number(value)}" for name, value in config["detection"].items()),
            "steuert die gelben Vorschlagsboxen; nur ueber serve-Optionen oder Profildatei",
        )
    )
    return result


def actions(state):
    """Tastenaktionen der Fusszeile mit ihrem Sperrgrund."""
    auto = state["auto"]["state"]
    running = auto in ("running", "queued")
    entries = [
        (
            "auto.start",
            "auto-setup",
            "a",
            "auto.start",
            {},
            None
            if state["mode"] == "setup" and state["config"]["confirmed"] and state["live"] and not running
            else "braucht setup-Modus, bestaetigte ROI und Livebild",
        ),
        (
            "auto.accept",
            "vorschlag uebernehmen",
            "y",
            "auto.accept",
            {},
            None if auto == "proposal" else "kein Vorschlag vorhanden",
        ),
        ("auto.cancel", "auto abbrechen", "c", "auto.cancel", {}, None if running else "kein Auto-Setup aktiv"),
        (
            "profile.save",
            "speichern",
            "s",
            "profile.save",
            {},
            None
            if not state["conflict"] and state["applied_revision"] == state["revision"] and not running
            else "Kamerauebernahme oder Konflikt offen",
        ),
        (
            "profile.save_as",
            "speichern als",
            "n",
            "profile.save",
            {},
            None if state["applied_revision"] == state["revision"] and not running else "Kamerauebernahme abwarten",
        ),
        ("profile.revert", "verwerfen", "r", "profile.revert", {}, None if state["dirty"] else "keine Aenderung"),
        (
            "profile.resolve.disk",
            "konflikt: datei",
            "d",
            "profile.resolve",
            {"value": "disk"},
            None if state["conflict"] else "kein Konflikt",
        ),
        (
            "profile.resolve.local",
            "konflikt: lokal",
            "l",
            "profile.resolve",
            {"value": "local"},
            None if state["conflict"] else "kein Konflikt",
        ),
    ]
    return [
        {
            "key": key,
            "label": label,
            "hotkey": hotkey,
            "op": op,
            "args": args,
            "needs_name": key == "profile.save_as",
            "enabled": reason is None,
            "reason": reason or "",
        }
        for key, label, hotkey, op, args, reason in entries
    ]
