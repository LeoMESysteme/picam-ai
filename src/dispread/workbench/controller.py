"""Ein Kamerabesitzer; Profil- und UI-Zustand unabhaengig vom Webtransport."""

from __future__ import annotations

import contextlib
import copy
import json
import queue
import threading
import time
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from dispread.frames.replay_source import CLIP_SCHEMA_VERSION
from dispread.layout import SEGMENT_NAMES, SEGMENT_SAMPLE_POINTS, DisplayLayout
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.records import TimeBaseKind
from dispread.rectify import rectify
from dispread.validate import GateConfig, ReleaseGate

from .profiles import DEFAULT, atomic_json, profile_name, quad_from_roi, roi_from_quad, validate
from .vision import DetectionConfig, find_display_candidates, fit_ocr_box, fit_quad_in_region

#: Zielgroesse des entzerrten Ausschnitts. Fest, weil der Segmentleser gegen
#: das Profilraster abtastet - schwankende Groessen verschieben die Punkte.
CROP_SIZE = (400, 160)

#: Jeder Stream-Neuaufbau ist ein Power-Zyklus des RP2040-Bridge-Chips auf
#: der AI-Camera; nach ~20-25 Zyklen in einer Bootsitzung antwortet er nicht
#: mehr auf I2C (OQ-22). Mehrere Aenderungen in kurzer Folge - z. B. Breite
#: und Hoehe als getrennte "camera.set"-Befehle - werden deshalb zu einem
#: einzigen Neuaufbau gebuendelt statt je Befehl einen auszuloesen.
GEOMETRY_DEBOUNCE_S = 0.25

#: Harte Obergrenze fuer Geometrie-Neuaufbauten je Bootsitzung. Beobachtet:
#: der RP2040-Bridge-Chip antwortet nach rund 20-25 Power-Zyklen nicht mehr
#: auf I2C (OQ-22), reproduzierbar, unabhaengig von Aufloesung/Fremdprozessen.
#: Mit Sicherheitsabstand darunter verweigert die Workbench weitere
#: Aufloesungs-/Bildratenaenderungen, statt den Chip unkontrolliert
#: gegen das tatsaechliche Limit laufen zu lassen - ein Neustart von
#: `dispread` (mit anschliessendem Host-Reboot) wird dann verlangt, statt
#: dass die Kamera mitten in einer Messreihe unvorhersehbar haengt.
MAX_GEOMETRY_CYCLES = 15

#: Wachhund fuer blockierende Kamera-Ioctls. Eine haengende Operation laesst
#: sich aus Python nicht abbrechen (der Treiber-Thread bleibt in einem
#: ioctl haengen), aber ohne Wachhund wuerde der Worker fuer immer schweigend
#: einfrieren statt die RP2040-Sperre (OQ-22) sichtbar zu melden.
CAMERA_OP_TIMEOUT_S = 6.0

#: Die Vorschau bleibt fluessig, waehrend die deutlich langsamere
#: Werterkennung mit eigener, fuer die Einrichtung ausreichender Rate laeuft.
#: Ein Messpfad darf daraus spaeter keine Zeit- oder Latenzaussage ableiten.
OCR_INTERVAL_S = 0.2

#: Bedienerrueckmeldung: nach einem Neustart laedt der Controller die zuletzt
#: bestaetigte Geometrie unveraendert (Konzept.md §4 - Bestaetigung ist der
#: Akt eines Menschen, kein automatischer Ersatz). Vor OQ-24 lief die
#: Vollbild-Kandidatensuche (gelbe Boxen) aber *nie* mehr, sobald einmal
#: bestaetigt war - der Bediener hatte danach keinerlei visuellen Hinweis
#: mehr, ob die alte Geometrie noch zur aktuellen Szene passt. Gedrosselt statt
#: unbedingt, um die mit OQ-24 behobene Vollbildsuche-pro-Bild-Kosten
#: (30,837 ms/Bild, siehe VALIDATION.md) nicht wieder einzufuehren; lieber
#: verglichen als blind vertraut, aber nie automatisch uebernommen.
CANDIDATE_INTERVAL_S = 1.0

#: Mehrbildbestaetigung fuer die Live-Vorschau (ReleaseGate.confirm_frames).
#: Bedienerrueckmeldung: multiplexende Anzeigen flackern gegen die niedrige
#: Kamerabildrate, ein einzelnes Bild kann mitten in einem Umschaltvorgang
#: liegen und wird dann falsch gelesen. Ein anderer Wert setzt die Bestaetigung
#: zurueck statt zu glaetten (Konzept.md §7); das kostet hier nur zusaetzliche
#: Vorschau-Latenz (bis zu GATE_CONFIRM_FRAMES * OCR_INTERVAL_S), keine
#: Messwertfreigabe findet in der Workbench ohnehin statt. Vorabdefault wie in
#: examples/16_end_to_end_headless.py; nicht an realen Multiplexperioden
#: validiert (OQ-20).
GATE_CONFIRM_FRAMES = 3

#: Wieviele Bilder hoechstens auf das Schreiben warten duerfen. Ein PNG von
#: 960x720 kostet 20-30 ms; im publish()-Pfad wuerde das die Vorschau bei
#: 15 fps anhalten. Laeuft die Queue voll, wird gezaehlt statt still verworfen.
CLIP_QUEUE_DEPTH = 24

#: Obergrenze je Clip. Ein Kalibrierpunkt braucht Sekunden, nicht Minuten;
#: ohne Grenze laeuft eine vergessene Aufnahme die Platte voll.
CLIP_MAX_SECONDS = 120


class CameraWedgedError(RuntimeError):
    """Eine Kamera-Ioctl kehrte nicht innerhalb von CAMERA_OP_TIMEOUT_S zurueck.

    Bekanntes Symptom des RP2040-Bridge-Fehlers (OQ-22): nur ein Reboot hilft,
    ein erneuter Zugriff auf dasselbe Kameraobjekt haengt ebenfalls.
    """


def roi_box(image, roi):
    """Normierte ROI in Bildkoordinaten, mindestens ein Pixel gross."""
    height, width = image.shape[:2]
    x, y, w, h = roi
    return int(x * width), int(y * height), max(1, int(w * width)), max(1, int(h * height))


def roi_quad(image, config):
    """Bestaetigten normierten Vierpunktausschnitt in Bildpixel umrechnen."""
    height, width = image.shape[:2]
    normalized = config.get("roi_quad") or quad_from_roi(config["roi"])
    if normalized is None:
        raise ValueError("Keine ROI bestaetigt")
    return tuple((float(x * width), float(y * height)) for x, y in normalized)


def crop_box(image, box):
    """Normierten Innenausschnitt schneiden und auf Leserformat skalieren."""
    height, width = image.shape[:2]
    x, y, box_width, box_height = box
    left, top = int(round(x * width)), int(round(y * height))
    right, bottom = int(round((x + box_width) * width)), int(round((y + box_height) * height))
    cropped = image[max(0, top) : min(height, bottom), max(0, left) : min(width, right)]
    if cropped.size == 0:
        raise ValueError("OCR-Rahmen ist leer")
    return cv2.resize(cropped, CROP_SIZE, interpolation=cv2.INTER_LINEAR)


def grid_geometry(layout_data):
    """Normiertes Leseraster fuer den Browsereditor bereitstellen."""
    layout = DisplayLayout.from_dict(layout_data)
    width, height = CROP_SIZE

    def normalized(box):
        x, y, box_width, box_height = box
        return [x / width, y / height, box_width / width, box_height / height]

    return {
        "cells": [normalized(box) for box in layout.cell_boxes(width, height)],
        "sign": normalized(layout.sign_box(width, height)) if layout.sign_box(width, height) else None,
        "samples": [[name, x, y] for name, (x, y) in SEGMENT_SAMPLE_POINTS.items()],
        # Profilfeste Dezimalposition: nur Kalibriermarker, solange OQ-17 die
        # optische Punktmessung noch nicht geklaert hat.
        "decimal_after": layout.decimal_point_index(),
    }


def quality(image, roi):
    h, w = image.shape[:2]
    if roi:
        x, y, rw, rh = roi
        image = image[
            int(y * h) : max(int((y + rh) * h), int(y * h) + 1), int(x * w) : max(int((x + rw) * w), int(x * w) + 1)
        ]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {
        "sharpness": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
        "saturated_fraction": round(float((gray >= 250).mean()), 4),
        "contrast": round(float(np.percentile(gray, 95) - np.percentile(gray, 5)) / 255, 4),
        "brightness": float(gray.mean()) / 255,
    }


class Controller:
    def __init__(self, root, camera_index=0, simulate=False):
        self.root = Path(root)
        self.camera_index, self.simulate = camera_index, simulate
        self.lock = threading.RLock()
        self.config = copy.deepcopy(DEFAULT)
        self.saved = copy.deepcopy(DEFAULT)
        self.name = "default"
        self.revision, self.applied = 0, -1
        self.boot_id, self.geometry_cycles = self._load_geometry_cycles()
        self.mode, self.error = "setup", None
        self.dirty = False
        self.conflict = None
        self.file_seen = None
        self.logs = deque(maxlen=300)
        self.log_id = 0
        self.sequence, self.last_frame, self.first_frame = 0, None, None
        self.jpeg, self.raw = None, None
        self.metadata, self.metrics, self.capabilities, self.observed = {}, {}, {}, {}
        self.frames = {}
        # Letzte Vollbild-Kandidatensuche (gelbe Vorschlagsboxen, Pixelkoordinaten,
        # Bildkoordinatensystem). Nur solange gepflegt, wie das Profil
        # unbestaetigt ist - erstes Einfrieren eines frischen Profils startet
        # damit an der zuletzt sichtbaren erkannten Position statt an einer
        # festen Standardbox.
        self.candidates = ()
        # Nach einer Bestaetigung ersetzt eine lokale, auf die bestaetigte ROI
        # eingegrenzte Suche (fit_quad_in_region statt der Vollbildsuche) die
        # Kandidaten - sonst leuchten bei jedem Vergleich auch andere Anzeigen
        # im Bild gelb auf (Bedienerbefund). Gedrosselt (CANDIDATE_INTERVAL_S,
        # siehe publish()), damit eine bestaetigte Geometrie vergleichbar
        # bleibt statt blind vertraut, ohne die mit OQ-24 behobene
        # Vollbildsuche-pro-Bild-Kosten zurueckzubringen.
        self.verify_quad = None
        self.last_candidates_at = 0.0
        self.focus = False
        self.reader = SevenSegmentReader()
        self.gate, self.gate_revision = None, None
        self.reading = None
        self.last_ocr_at = 0.0
        self.stop = threading.Event()
        self.cancel_auto = threading.Event()
        self.auto = {"state": "idle"}
        self.auto_requested = False
        self.thread = None
        self.clip = None  # laufende Aufnahme oder None
        self.clip_queue = None  # queue.Queue der zu schreibenden Bilder
        self.clip_thread = None
        self.calibrated_on = None  # Frame-Sequenz der letzten Bestaetigung; Task 5 setzt es
        self.log("info", "Workbench gestartet; gelbe Boxen sind unbestaetigte Vorschlaege.")
        if self.path.exists():
            self._load(self.path)
            if self.config["confirmed"]:
                # Bedienerwunsch: jede Sitzung beginnt mit einer frischen
                # menschlichen Bestaetigung (Konzept.md §4 - Bestaetigung ist
                # der Akt eines Menschen), statt stillschweigend eine alte
                # Bestaetigung fuer den run-Modus weiterzuverwenden. Nur die
                # Laufzeitkopie verliert `confirmed`; die gespeicherte Datei
                # bleibt unveraendert, und roi/roi_quad/ocr_box bleiben als
                # Startpunkt fuer eine schnelle erneute Bestaetigung erhalten.
                # Reaktiviert nebenbei die volle Kandidatensuche auf dem
                # Livebild (publish(): unbestaetigt sucht jedes Bild).
                self._change({**copy.deepcopy(self.config), "confirmed": False})
                self.log(
                    "warn",
                    "Sitzungsstart: geladene ROI/OCR-Geometrie muss diese Sitzung erneut "
                    "bestaetigt werden, bevor der run-Modus verfuegbar ist - Kandidatensuche "
                    "laeuft wieder auf dem Livebild.",
                )

    @property
    def path(self):
        return self.root / "profiles" / (self.name + ".json")

    @property
    def cycles_path(self):
        return self.root / "camera_cycles.json"

    def _load_geometry_cycles(self):
        """Power-Zyklus-Zaehler ueber Prozessneustarts hinweg fortfuehren.

        Der RP2040-Chip merkt sich Power-Zyklen pro **Boot**, nicht pro
        Prozess (OQ-22: ein Test mit je einem frischen Python-Prozess je
        Zyklus haengte trotzdem nach ~24 Zyklen). Ein reiner
        In-Memory-Zaehler wuerde nach einem `dispread`-Neustart faelschlich
        wieder bei 0 anfangen und so mehr echte Zyklen erlauben, als das
        Budget vorsieht. Deshalb an die Boot-ID gebunden persistieren; bei
        echtem Reboot (andere Boot-ID oder Datei fehlt) faengt der Zaehler
        korrekt wieder bei 0 an.
        """
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        except OSError:
            boot_id = None
        try:
            data = json.loads(self.cycles_path.read_text())
        except (OSError, ValueError):
            data = {}
        if boot_id is not None and data.get("boot_id") == boot_id:
            return boot_id, int(data.get("cycles", 0))
        return boot_id, 0

    def _save_geometry_cycles(self):
        if self.boot_id is None:
            return  # keine Boot-ID verfuegbar - nichts Verlaessliches zu persistieren
        atomic_json(self.cycles_path, {"boot_id": self.boot_id, "cycles": self.geometry_cycles})

    def profile_names(self):
        """Nur wirklich vorhandene Profildateien; ungueltige Namen ueberspringen."""
        names = set()
        try:
            for entry in (self.root / "profiles").glob("*.json"):
                with contextlib.suppress(ValueError):
                    names.add(profile_name(entry.stem))
        except OSError as error:
            self.log("error", f"Profilverzeichnis nicht lesbar: {error}")
        return sorted(names)

    def log(self, level, message):
        with self.lock:
            self.log_id += 1
            self.logs.append(
                {
                    "id": self.log_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "timebase": "UTC",
                    "level": level,
                    "message": str(message),
                }
            )

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            age = None if self.last_frame is None else now - self.last_frame
            return {
                "live": age is not None and age < 2 and self.error is None and not self.stop.is_set(),
                "sequence": self.sequence,
                "processing_fps": round((self.sequence - 1) / max(now - (self.first_frame or now), 1e-6), 1),
                "frame_age_seconds": age,
                "age_timebase": "CLOCK_MONOTONIC",
                "error": self.error,
                "mode": self.mode,
                "profile": self.name,
                "profiles": self.profile_names(),
                "config": copy.deepcopy(self.config),
                "ocr_grid": grid_geometry(self.config["layout"]),
                "revision": self.revision,
                "applied_revision": self.applied,
                "geometry_cycles": self.geometry_cycles,
                "geometry_cycles_max": MAX_GEOMETRY_CYCLES,
                "dirty": self.dirty,
                "conflict": bool(self.conflict),
                "observed": dict(self.observed),
                "capabilities": dict(self.capabilities),
                "quality": dict(self.metrics),
                "focus": self.focus,
                "reading": copy.deepcopy(self.reading),
                "auto": copy.deepcopy(self.auto),
                "logs": list(self.logs),
                "stopped": self.stop.is_set(),
                "simulated": self.simulate,
                "clip": {
                    "state": "idle" if self.clip is None else "recording",
                    "frames": 0 if self.clip is None else len(self.clip["entries"]),
                    "dropped": 0 if self.clip is None else self.clip["dropped"],
                    "path": None if self.clip is None else str(self.clip["path"]),
                    "seconds_left": None
                    if self.clip is None
                    else max(0.0, self.clip["deadline"] - time.monotonic()),
                },
            }

    def _change(self, data):
        if self.auto["state"] in ("running", "queued"):
            raise ValueError("Automatische Einrichtung zuerst abbrechen")
        self.config = validate(data, self.capabilities or None)
        # Die Freigabepruefung ist zustandsbehaftet; nach einer Aenderung darf
        # sie keine Bestaetigung aus der alten Konfiguration mitschleppen.
        self.gate, self.gate_revision = None, None
        self.reading = None
        self.last_ocr_at = 0.0
        self.revision += 1
        self.dirty = self.config != self.saved
        if self.mode == "run":
            self.mode = "setup"
            self.log("warn", "Konfiguration geaendert; run -> setup")
        self.log("info", f"Konfiguration r{self.revision} angefordert")

    def _load(self, path):
        data = validate(json.loads(path.read_text()), self.capabilities or None)
        self._change(data)
        self.saved, self.dirty = copy.deepcopy(data), False
        self.conflict = None
        self.file_seen = path.read_bytes()
        self.log("info", f"Profil {self.name} geladen")
        if data["confirmed"]:
            # Bedienerrueckmeldung: nach einem Neustart wirkte die geladene
            # Geometrie wie unveraendert uebernommen, ohne jeden Hinweis, dass
            # sie noch nicht gegen die aktuelle Szene verglichen wurde. Die
            # Bestaetigung selbst bleibt unangetastet (Konzept.md §4) - die
            # gedrosselte Kandidatensuche in publish() liefert den Vergleich.
            self.log(
                "warn",
                "Geladene ROI/OCR-Geometrie ist bestaetigt, aber noch nicht gegen die "
                "aktuelle Szene verglichen - gelbe Kandidatenbox beobachten, bevor "
                "der Wert vertraut wird",
            )

    def watch_profile(self):
        with self.lock:
            if not self.path.exists():
                return
            raw = self.path.read_bytes()
            if raw == self.file_seen:
                return
            # Erster Tick merkt den Inhalt, zweiter unveraenderter Tick wendet an.
            if raw != getattr(self, "file_pending", None):
                self.file_pending = raw
                return
            self.file_seen = raw
            try:
                data = validate(json.loads(raw), self.capabilities or None)
                if self.dirty or self.auto["state"] in ("running", "queued"):
                    self.conflict = data
                    self.log("warn", "Externe Profiländerung: profile resolve disk|local erforderlich")
                else:
                    self._change(data)
                    self.saved, self.dirty = copy.deepcopy(data), False
            except (ValueError, TypeError, KeyError) as error:
                self.log("error", f"Profil nicht übernommen: {error}")

    def _apply_camera_key(self, data, key, value):
        """Ein Kamerafeld in `data` setzen; von camera.set und camera.set_many geteilt."""
        if key in ("width", "height", "fps"):
            data["camera"][key] = value
            if key in ("width", "height"):
                data["confirmed"] = False
        else:
            data["camera"]["controls"][key] = value
            if key == "AeEnable" and value is True:
                for name in ("ExposureTime", "AnalogueGain"):
                    data["camera"]["controls"].pop(name, None)
            elif key == "AeEnable" and value is False:
                for name in ("ExposureTime", "AnalogueGain"):
                    current = self.observed.get(name)
                    if current is None and name in self.capabilities:
                        current = self.capabilities[name][2]
                    if current is not None:
                        data["camera"]["controls"][name] = current

    def _check_geometry_budget(self, data):
        """Verweigert eine echte Geometrieaenderung, sobald das RP2040-Power-
        Zyklus-Budget erreicht ist (OQ-22). Ein Wiederwaehlen der bereits
        aktiven Aufloesung/Bildrate ist immer erlaubt, da es keinen neuen
        Stream-Neuaufbau ausloest.
        """
        old = (self.config["camera"]["width"], self.config["camera"]["height"], self.config["camera"]["fps"])
        new = (data["camera"]["width"], data["camera"]["height"], data["camera"]["fps"])
        if new != old and self.geometry_cycles >= MAX_GEOMETRY_CYCLES:
            raise ValueError(
                f"Power-Zyklus-Budget der Kamera erreicht ({MAX_GEOMETRY_CYCLES}, OQ-22) - "
                "dispread neu starten (danach Host-Reboot empfohlen), bevor Aufloesung "
                "oder Bildrate erneut geaendert wird"
            )

    def command(self, op, args=None):
        args = args or {}
        if op == "ocr.suggest":
            # Eigener, absichtlich VOR dem Controller-Lock behandelter Befehl:
            # die eigentliche OpenCV-Arbeit (fit_ocr_box) braucht das Lock
            # nicht und soll es - wie publish() - nicht waehrend eines ganzen
            # Suchlaufs halten. Das war die Ursache eines gemeldeten Bugs:
            # eine langsame, gesperrte Anfrage liess genug Zeit fuer eine
            # Bedienereingabe, die dann die eintreffende Vermutung ueberschrieb.
            return self._suggest_ocr_box(args)
        with self.lock:
            if op == "status":
                return self.snapshot()
            if op == "mode":
                mode = args["value"]
                if mode not in ("setup", "run", "annotate"):
                    raise ValueError("Modus: setup|run|annotate")
                if self.auto["state"] in ("running", "queued"):
                    raise ValueError("Automatische Einrichtung zuerst beenden")
                if mode == "run" and (
                    not self.config["confirmed"]
                    or not self.snapshot()["live"]
                    or self.applied != self.revision
                    or self.config["camera"]["controls"].get("AeEnable", True)
                ):
                    raise ValueError("run braucht bestaetigte ROI, Livebild und uebernommene feste Belichtung")
                self.mode = mode
                self.log("info", f"Modus: {mode}; keine Messwertfreigabe in diesem Prototyp")
            elif op == "camera.set":
                data = copy.deepcopy(self.config)
                self._apply_camera_key(data, args["key"], args["value"])
                self._check_geometry_budget(data)
                self._change(data)
            elif op == "camera.set_many":
                # Mehrere Kamerafelder atomar in einer Revision setzen - z. B.
                # Breite und Hoehe einer Aufloesung zusammen, damit daraus
                # genau ein Stream-Neuaufbau (ein RP2040-Power-Zyklus, OQ-22)
                # wird statt zwei durch getrennte "camera.set"-Befehle.
                data = copy.deepcopy(self.config)
                for key, value in args["values"].items():
                    self._apply_camera_key(data, key, value)
                self._check_geometry_budget(data)
                self._change(data)
            elif op == "layout.set":
                data = copy.deepcopy(self.config)
                key = args["key"]
                if key not in DEFAULT["layout"]:
                    raise ValueError(f"Unbekanntes Layoutfeld: {key}")
                data["layout"][key] = args["value"]
                self._change(data)
                # Ein eingefrorenes Original bleibt fuer reine
                # Leseraster-Aenderungen gueltig: Bildgeometrie und Aufnahme
                # haben sich nicht geaendert. Andere Konfigurationsbefehle
                # aktualisieren diese Revision bewusst nicht.
                for frame in self.frames.values():
                    frame["revision"] = self.revision
                    frame["profile"]["layout"] = copy.deepcopy(self.config["layout"])
            elif op == "focus":
                if type(args["value"]) is not bool:
                    raise ValueError("Fokusassistenz erwartet true/false")
                self.focus = bool(args["value"])
                self.log("info", "Fokusassistenz: Objektiv mechanisch einstellen; Schärfewert relativ")
            elif op == "profile.load":
                name = profile_name(args["name"])
                if self.dirty:
                    raise ValueError("Ungespeicherte Vorschau zuerst speichern oder revert ausfuehren")
                path = self.root / "profiles" / (name + ".json")
                data = validate(json.loads(path.read_text()), self.capabilities or None)
                self._change(data)
                self.name, self.saved, self.dirty = name, copy.deepcopy(data), False
                self.file_seen, self.conflict = path.read_bytes(), None
            elif op == "profile.save":
                if self.conflict:
                    raise ValueError("Profilkonflikt zuerst mit resolve disk|local loesen")
                if self.applied != self.revision or self.auto["state"] in ("running", "queued"):
                    raise ValueError("Erst auf erfolgreiche Kamerauebernahme warten")
                name = profile_name(args.get("name") or self.name)
                data = copy.deepcopy(self.config)
                data["version"] += 1
                atomic_json(self.root / "profiles" / (name + ".json"), data)
                self.name, self.config = name, data
                self.saved, self.dirty = copy.deepcopy(self.config), False
                self.file_seen = self.path.read_bytes()
                self.log("info", f"Profil {self.name} v{self.config['version']} gespeichert")
            elif op == "profile.revert":
                self._change(self.saved)
            elif op == "profile.role":
                data = copy.deepcopy(self.config)
                data["role"] = args["value"]
                self._change(data)
            elif op == "profile.resolve":
                if args["value"] not in ("disk", "local") or self.conflict is None:
                    raise ValueError("Kein Konflikt oder ungueltige Auswahl")
                if args["value"] == "disk":
                    self._change(self.conflict)
                    self.saved, self.dirty = copy.deepcopy(self.config), False
                self.conflict = None
                self.log("info", "Profilkonflikt aufgeloest")
            elif op == "freeze":
                if self.mode not in ("setup", "annotate") or not self.snapshot()["live"]:
                    raise ValueError("Editieren braucht Livebild und setup/annotate")
                token = uuid.uuid4().hex
                if len(self.frames) >= 4:
                    self.frames.pop(next(iter(self.frames)))
                self.frames[token] = {
                    "image": self.raw.copy(),
                    "metadata": copy.deepcopy(self.metadata),
                    "sequence": self.sequence,
                    "profile": copy.deepcopy(self.config),
                    "revision": self.revision,
                    "profile_name": self.name,
                }
                img_h, img_w = self.raw.shape[:2]
                # Kandidatenliste fuer den Editor: die zuletzt bekannte, ausser
                # sie ist leer (z. B. nach einer Bestaetigung in derselben
                # Sitzung - publish() pflegt self.candidates nur unbestaetigt).
                # Dann ein einmaliger Vollbild-Suchlauf, damit ein erneutes
                # Editieren nicht ohne jede anklickbare Vorschlagsbox dasteht -
                # kostet nur diesen einen Aufruf, nicht pro Livebild (OQ-24).
                candidates = self.candidates or find_display_candidates(
                    self.raw, DetectionConfig(**self.config["detection"])
                )
                roi = self.config["roi"]
                if roi is None and candidates:
                    # Frisches, nie bestaetigtes Profil: an der besten gerade
                    # sichtbaren gelben Vorschlagsbox starten statt an einer
                    # festen Standardbox in der Bildmitte - sonst verliert der
                    # Bediener beim Editieren-Start die bereits erkannte Position.
                    x, y, w, h = candidates[0]
                    roi = [x / img_w, y / img_h, w / img_w, h / img_h]
                roi = roi or [0.2, 0.3, 0.6, 0.3]
                quad = copy.deepcopy(self.config.get("roi_quad") or quad_from_roi(roi))
                ocr_box = self.config["ocr_box"]
                if ocr_box == DEFAULT["ocr_box"]:
                    # Unberuehrter Default deckt sich direkt nach einer
                    # frischen roi-Bestaetigung mit roi_quad - das Verklicken
                    # aus dem Bedienerbefund. Reine Editor-Sitzungsgroesse:
                    # weder self.config noch eine Bestaetigung aendern sich.
                    ocr_box = [0.15, 0.15, 0.7, 0.7]
                return {
                    "id": token,
                    "width": img_w,
                    "height": img_h,
                    "roi": roi,
                    "quad": quad,
                    "candidates": [
                        [x / img_w, y / img_h, w / img_w, h / img_h] for x, y, w, h in candidates
                    ],
                    "ocr_box": copy.deepcopy(ocr_box),
                    "ocr_grid": grid_geometry(self.config["layout"]),
                }
            elif op == "roi":
                frame = self.frames[args["id"]]
                if self.mode not in ("setup", "annotate") or frame["revision"] != self.revision:
                    raise ValueError("Modus/Profil geaendert; neues Bild einfrieren")
                data = copy.deepcopy(self.config)
                quad = copy.deepcopy(args.get("quad") or quad_from_roi(args["roi"]))
                data.update(
                    roi=roi_from_quad(quad),
                    roi_quad=quad,
                    ocr_box=copy.deepcopy(args.get("ocr_box", data["ocr_box"])),
                    confirmed=True,
                    role=args.get("role", "main"),
                )
                data = validate(data, self.capabilities or None)
                if self.mode == "annotate":
                    target = self.root / "annotations" / uuid.uuid4().hex
                    target.mkdir(parents=True)
                    if not cv2.imwrite(str(target / "image.png"), frame["image"]):
                        raise ValueError("Bild konnte nicht gespeichert werden")
                    atomic_json(
                        target / "annotation.json",
                        {
                            "schema_version": 2,
                            "frame_sequence": frame["sequence"],
                            "metadata": frame["metadata"],
                            "profile": frame["profile"],
                            "profile_name": frame["profile_name"],
                            "revision": frame["revision"],
                            "image": "image.png",
                            "roi": data["roi"],
                            "roi_quad": data["roi_quad"],
                            "ocr_box": data["ocr_box"],
                            "ocr_box_coordinate_system": "rectified_roi_normalized_xywh",
                            "role": data["role"],
                            "coordinate_system": "normalized_quad_tl_tr_br_bl",
                            # Getippter Anzeigewert, rein additiv (Konzept.md
                            # §9-Datensatzaufbau) - keine automatische
                            # Ablesung, keine Erkennungsgarantie.
                            "ground_truth_text": args.get("ground_truth_text"),
                            "formatter_provisional": True,
                            "created_at": datetime.now(UTC).isoformat(),
                            "created_timebase": "UTC",
                        },
                    )
                    self.log("info", f"Annotation gespeichert: {target}")
                else:
                    self._change(data)
                del self.frames[args["id"]]
            elif op == "auto.start":
                if self.mode != "setup" or not self.config["confirmed"] or not self.snapshot()["live"]:
                    raise ValueError("Auto-Setup braucht Livebild und bestaetigte ROI im setup-Modus")
                if self.auto["state"] in ("running", "queued"):
                    raise ValueError("Auto-Setup laeuft bereits")
                self.cancel_auto.clear()
                self.auto, self.auto_requested = {"state": "queued"}, True
            elif op == "auto.cancel":
                self.cancel_auto.set()
            elif op == "auto.accept":
                if self.auto["state"] != "proposal":
                    raise ValueError("Kein Auto-Vorschlag vorhanden")
                data = copy.deepcopy(self.config)
                data["camera"]["controls"] = self.auto["controls"]
                self._change(data)
                self.auto = {"state": "accepted"}
            elif op == "clip.start":
                if not self.config["confirmed"] or not self.snapshot()["live"]:
                    raise ValueError("Clipaufnahme braucht bestaetigte Geometrie und Livebild")
                if self.mode not in ("setup", "annotate"):
                    raise ValueError("Clipaufnahme laeuft in setup oder annotate")
                if self.clip is not None:
                    raise ValueError("Clipaufnahme laeuft bereits")
                device_id = str(args.get("device_id", "")).strip()
                text = str(args.get("ground_truth_text", "")).strip()
                if not device_id:
                    # Splitgrenze ist die Geraeteinstanz, nie der Frame (ROADMAP).
                    # Ohne Kennung ist der Datensatz fuer einen Gruppensplit wertlos.
                    raise ValueError("Geraetekennung fehlt")
                if not text:
                    raise ValueError("Sollwert fehlt - ein Clip ohne Label ist kein Testdatum")
                seconds = float(args.get("seconds", 5.0))
                if not 0.5 <= seconds <= CLIP_MAX_SECONDS:
                    raise ValueError(f"Clipdauer 0.5..{CLIP_MAX_SECONDS} s")
                self._clip_start(device_id, text, seconds)
            elif op == "clip.stop":
                self._clip_stop()
            else:
                raise ValueError(f"Unbekannter Befehl: {op}")
            return self.snapshot()

    def _suggest_ocr_box(self, args):
        """OCR-Rahmen-Vermutung fuer ein gegebenes, evtl. unbestaetigtes Quad.

        Wird bewusst ausserhalb von `self.lock` gerechnet - siehe `command()`.
        `frame["image"]` ist eine bei `freeze()` gezogene Kopie und wird sonst
        nirgends veraendert; eine parallele LRU-Verdraengung in `self.frames`
        entfernt nur den Dict-Eintrag, die hier gehaltene Referenz bleibt
        gueltig. `self.log()` nimmt sein eigenes (reentrantes) Lock, ein
        Aufruf ausserhalb dieses Locks ist unproblematisch.
        """
        with self.lock:
            frame = self.frames[args["id"]]
            layout_data = copy.deepcopy(self.config["layout"])
        layout = DisplayLayout.from_dict(layout_data)
        img_h, img_w = frame["image"].shape[:2]
        quad_px = tuple((float(x * img_w), float(y * img_h)) for x, y in args["quad"])
        crop = rectify(frame["image"], quad_px, target_size=CROP_SIZE)
        ocr_box = fit_ocr_box(crop.image, layout=layout)
        if ocr_box is None:
            self.log("info", "ocr.suggest: kein Kandidat im markierten Bereich gefunden")
        return {"ocr_box": list(ocr_box) if ocr_box is not None else None}

    def _clip_start(self, device_id, text, seconds):
        target = self.root / "clips" / uuid.uuid4().hex
        target.mkdir(parents=True)
        self.clip_queue = queue.Queue(maxsize=CLIP_QUEUE_DEPTH)
        self.clip = {
            "path": target,
            "device_id": device_id,
            "ground_truth_text": text,
            "deadline": time.monotonic() + seconds,
            "profile": copy.deepcopy(self.config),
            "profile_name": self.name,
            "calibrated_on_frame_sequence": self.calibrated_on,
            "entries": [],
            "dropped": 0,
        }
        # Die Queue an den Thread binden statt sie ueber self.clip_queue immer
        # wieder neu nachzuschlagen: ein rasches stop/start-Paar zeigt
        # self.clip_queue sonst schon auf die naechste Aufnahme, waehrend
        # dieser Thread noch die alte leerraeumt.
        self.clip_thread = threading.Thread(
            target=self._clip_writer, args=(self.clip_queue,), name="clip", daemon=True
        )
        self.clip_thread.start()
        self.log("info", f"Clipaufnahme {target.name} gestartet: {device_id}, Sollwert {text!r}")

    def _clip_writer(self, clip_queue):
        """Bilder schreiben, ohne den Bildpfad aufzuhalten.

        `clip_queue` ist die beim Threadstart uebergebene Queue dieser einen
        Aufnahme - nicht `self.clip_queue`, das ein nachfolgender
        clip.start bereits auf eine neue Queue umgebogen haben kann,
        waehrend dieser Thread noch die alte leerraeumt.
        """
        while True:
            item = clip_queue.get()
            if item is None:
                return
            path, image = item
            if not cv2.imwrite(str(path), image):
                self.log("error", f"Clipbild nicht geschrieben: {path}")

    def _clip_stop(self):
        if self.clip is None:
            return
        clip, self.clip = self.clip, None
        if self.clip_queue is not None:
            self.clip_queue.put(None)
        atomic_json(
            clip["path"] / "clip.json",
            {
                "schema_version": CLIP_SCHEMA_VERSION,
                "clip_id": clip["path"].name,
                "device_id": clip["device_id"],
                "ground_truth_text": clip["ground_truth_text"],
                "profile": clip["profile"],
                "profile_name": clip["profile_name"],
                "calibrated_on_frame_sequence": clip["calibrated_on_frame_sequence"],
                "dropped_frames": clip["dropped"],
                "created_at": datetime.now(UTC).isoformat(),
                "created_timebase": "UTC",
                "frames": clip["entries"],
            },
        )
        self.log(
            "info",
            f"Clip {clip['path'].name}: {len(clip['entries'])} Bilder, {clip['dropped']} verworfen",
        )

    def drain_clip_writer(self):
        """Auf den Schreib-Thread warten. Fuer Tests - kein Bedienbefehl."""
        if self.clip_thread is not None:
            self.clip_thread.join(timeout=10)
            self.clip_thread = None

    def publish(self, image, metadata):
        """Ein Bild ohne lange Sperre fuer Status-, ROI- oder Stopbefehle verarbeiten."""
        with self.lock:
            config, revision = copy.deepcopy(self.config), self.revision
            focus, mode = self.focus, self.mode
            cached_reading = copy.deepcopy(self.reading)
            cached_verify_quad = self.verify_quad
            now = time.monotonic()
            should_read = config["confirmed"] and (cached_reading is None or now - self.last_ocr_at >= OCR_INTERVAL_S)
            # Nach einer Bestaetigung nur noch gedrosselt und nie im
            # run-Modus - die mit OQ-24 behobene Vollbildsuche-pro-Bild-Kosten
            # sollen nicht zurueckkommen, aber eine bestaetigte Geometrie ohne
            # jeden visuellen Vergleich zur aktuellen Szene war der gemeldete
            # Mangel.
            should_verify = (
                config["confirmed"] and mode != "run" and now - self.last_candidates_at >= CANDIDATE_INTERVAL_S
            )

        # OpenCV-Arbeit bewusst ausserhalb des Controller-Locks.
        metrics = quality(image, config["roi"])
        overlay = image.copy()
        boxes = ()
        verify_quad = cached_verify_quad
        if not config["confirmed"]:
            # Vor der Bestaetigung jedes Bild frisch ueber das ganze Bild
            # suchen (Kalibrierfluss, unveraendert) - hier gibt es noch keine
            # bestaetigte Geometrie, die den Suchbereich eingrenzen koennte.
            boxes = find_display_candidates(image, DetectionConfig(**config["detection"]))
        elif should_verify:
            # Eingegrenzt auf die bestaetigte ROI statt einer Vollbildsuche -
            # sonst leuchten bei jedem Vergleich auch andere Anzeigen im Bild
            # gelb auf (Bedienerbefund; dieselbe Haupt-/Nebenanzeige-Grenze
            # wie bei OQ-25, hier durch den engen Suchbereich vermieden statt
            # erneut riskiert).
            verify_quad = fit_quad_in_region(image, config["roi"], layout=DisplayLayout.from_dict(config["layout"]))
        for x, y, w, h in boxes:
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 220, 220), 2)
        if verify_quad is not None:
            img_h, img_w = image.shape[:2]
            verify_points = np.array([[px * img_w, py * img_h] for px, py in verify_quad], dtype=np.int32)
            cv2.polylines(overlay, [verify_points], True, (0, 220, 220), 2)

        reading = cached_reading
        quad = None
        if config["confirmed"]:
            quad = roi_quad(image, config)
            cv2.polylines(overlay, [np.rint(quad).astype(np.int32)], True, (130, 220, 130), 2)
            if should_read:
                # Gate-Zustand ist geteilter Controllerzustand; nur dieser
                # kurze Teil bleibt gesperrt. Entzerrung/Segmentanalyse sind
                # klein gegen die vorherige Vollbildsuche.
                with self.lock:
                    if revision != self.revision:
                        return
                    reading = self._read(image, config, quad)
                    self.last_ocr_at = now
            if focus:
                ih, iw = image.shape[:2]
                crop = rectify(image, quad, target_size=(iw, ih))
                overlay = cv2.resize(crop_box(crop.image, config["ocr_box"]), (iw, ih))
            elif reading and not reading.get("error"):
                self._draw_cells(overlay, quad, config["ocr_box"], config["layout"], reading)

        ok, jpeg = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise RuntimeError("JPEG fehlgeschlagen")
        observed = {k: metadata[k] for k in ("ExposureTime", "AnalogueGain", "FrameDuration") if k in metadata}

        with self.lock:
            # Eine waehrend der Bildarbeit geaenderte Geometrie darf kein
            # Ergebnis aus der alten Revision zurueckschreiben.
            if revision != self.revision:
                return
            self.raw, self.metadata = image, metadata
            self.metrics = metrics
            self.candidates = boxes
            self.verify_quad = verify_quad
            if should_verify:
                self.last_candidates_at = now
            self.observed = observed
            self.reading = reading
            self.jpeg = jpeg.tobytes()
            self.sequence += 1
            if self.clip is not None:
                if time.monotonic() >= self.clip["deadline"]:
                    self._clip_stop()
                else:
                    name = f"frame_{len(self.clip['entries']) + 1:06d}.png"
                    try:
                        self.clip_queue.put_nowait((self.clip["path"] / name, image))
                    except queue.Full:
                        # Gezaehlt, nicht stillschweigend verworfen - die Zahl steht im
                        # clip.json und macht einen lueckenhaften Clip erkennbar.
                        self.clip["dropped"] += 1
                    else:
                        self.clip["entries"].append(
                            {
                                "file": name,
                                "frame_sequence": self.sequence,
                                "capture_timestamp": {
                                    "value_ns": int(metadata.get("SensorTimestamp", 0)),
                                    "base": metadata.get("timebase", TimeBaseKind.FILE_MTIME.value),
                                    "semantics": metadata.get("timestamp_semantics", "unknown"),
                                    "uncertainty_ns": metadata.get("uncertainty_ns"),
                                },
                                "metadata": copy.deepcopy(metadata),
                            }
                        )
            self.last_frame = now
            if self.first_frame is None:
                self.first_frame = self.last_frame
            self.error = None

    def _read(self, image, config, quad):
        """Bestaetigte ROI entzerren, Ziffern lesen, Freigabe nur als Vorschau.

        Erzeugt ausdruecklich **keinen** `ValueRecord` und sendet nichts. Die
        Freigabeentscheidung wird angezeigt, damit der Bediener sieht, woran
        eine Ablesung scheitert - sie ist keine Freigabe (Konzept.md §7).
        """
        try:
            layout = DisplayLayout.from_dict(config["layout"])
            crop = rectify(image, quad, target_size=CROP_SIZE)
            reader_crop = crop_box(crop.image, config["ocr_box"])
            read = self.reader.read(reader_crop, layout)
            if self.gate is None or self.gate_revision != self.revision:
                self.gate = ReleaseGate(GateConfig(expected_unit=layout.unit, confirm_frames=GATE_CONFIRM_FRAMES))
                self.gate_revision = self.revision
            # CLOCK_MONOTONIC, nur fuer die Veralterung dieser Vorschau. Aus
            # dieser Zahl darf kein Zeitbezug eines Messwerts abgeleitet
            # werden; der Aufnahmezeitstempel liegt in SENSOR_BOOTTIME.
            decision = self.gate.evaluate(read, time.monotonic_ns())
            return {
                "raw_text": read.raw_text,
                "value": read.value,
                "unit": read.unit_text,
                "unit_source": read.diagnostics.get("unit_source"),
                "sign_detected": read.sign_detected,
                "sign_region_readable": read.sign_region_readable,
                "decimal_point_detected": read.decimal_point_detected,
                "status_flags": sorted(read.status_flags),
                "digits": [g.text for g in read.glyphs],
                "segments": [list(g.segments) if g.segments else None for g in read.glyphs],
                "ambiguous_with": [list(g.ambiguous_with) for g in read.glyphs],
                "min_margin": round(float(read.diagnostics.get("min_margin", 0.0)), 4),
                "contrast": round(float(read.diagnostics.get("contrast", 0.0)), 4),
                "unreadable_cells": int(read.diagnostics.get("unreadable_cells", 0)),
                "crop_sharpness": round(crop.sharpness, 2),
                "crop_saturated_fraction": round(crop.saturated_fraction, 4),
                "backend": f"{read.backend_id}/{read.backend_version}",
                "confidence_calibrated": self.reader.declares_confidence_calibrated,
                "gate_status": decision.status.value,
                "gate_reasons": list(decision.reject_reasons),
                "gate_confidence": round(decision.confidence, 4),
                "gate_timebase": "CLOCK_MONOTONIC",
                "released": False,
                "error": None,
            }
        except (ValueError, TypeError, KeyError, cv2.error) as error:
            return {"error": str(error), "raw_text": None, "value": None, "released": False}

    def _draw_cells(self, overlay, quad, ocr_box, layout_data, reading):
        """Ziffernzellen und Abtastpunkte ins Kamerabild zurueckzeichnen.

        Die Punkte werden mit der inversen Perspektivtransformation aus dem
        entzerrten Ausschnitt zurueck ins Kamerabild gelegt. Der Bediener sieht
        damit unmittelbar, ob Ecken, Zellen und Abtastpunkte sitzen.
        """
        layout = DisplayLayout.from_dict(layout_data)
        crop_w, crop_h = CROP_SIZE
        source = np.float32([[0, 0], [crop_w - 1, 0], [crop_w - 1, crop_h - 1], [0, crop_h - 1]])
        transform = cv2.getPerspectiveTransform(source, np.float32(quad))
        box_x, box_y, box_width, box_height = ocr_box

        def to_image(cx, cy):
            outer_x = (box_x + cx / crop_w * box_width) * (crop_w - 1)
            outer_y = (box_y + cy / crop_h * box_height) * (crop_h - 1)
            point = cv2.perspectiveTransform(np.float32([[[outer_x, outer_y]]]), transform)[0, 0]
            return int(round(float(point[0]))), int(round(float(point[1])))

        def draw_box(cell, colour):
            x, y, width, height = cell
            points = np.int32([to_image(x, y), to_image(x + width, y), to_image(x + width, y + height), to_image(x, y + height)])
            cv2.polylines(overlay, [points], True, colour, 1)

        sign = layout.sign_box(crop_w, crop_h)
        if sign:
            colour = (130, 220, 130) if reading.get("sign_detected") else (90, 120, 90)
            draw_box(sign, colour)

        segments = reading.get("segments") or []
        for index, cell in enumerate(layout.cell_boxes(crop_w, crop_h)):
            cx, cy, cw, ch = cell
            draw_box(cell, (90, 120, 90))
            active = segments[index] if index < len(segments) else None
            for name, (rx, ry) in SEGMENT_SAMPLE_POINTS.items():
                point = to_image(cx + rx * cw, cy + ry * ch)
                on = bool(active[SEGMENT_NAMES.index(name)]) if active else False
                cv2.circle(overlay, point, 2, (130, 220, 130) if on else (70, 90, 110), -1)

    def start(self):
        self.thread = threading.Thread(target=self._worker, name="camera", daemon=True)
        self.thread.start()

    def close(self):
        with self.lock:
            self._clip_stop()
        # _clip_stop() nur schreibt clip.json und weckt den Schreib-Thread mit
        # dem None-Sentinel auf - es wartet NICHT, bis die letzten PNGs
        # tatsaechlich auf der Platte liegen. Ohne diesen Join koennte der
        # Prozess beenden, waehrend im gerade geschriebenen Manifest gelistete
        # Bilder noch fehlen. Gleicher Stil/Timeout wie der Kamerathread unten.
        if self.clip_thread is not None:
            self.clip_thread.join(timeout=8)
            if self.clip_thread.is_alive():
                self.log("error", "Clip-Schreiber hat nicht rechtzeitig beendet")
            self.clip_thread = None
        self.stop.set()
        self.cancel_auto.set()
        if self.thread:
            self.thread.join(timeout=8)
            if self.thread.is_alive():
                self.log("error", "Kamerathread hat nicht rechtzeitig beendet")

    def _guarded(self, action, func, timeout_s=CAMERA_OP_TIMEOUT_S):
        """Fuehrt eine blockierende Kamera-Operation mit Wachhund aus.

        Ein transienter Stau (z. B. `capture_request(wait=2.0)` bei kurzem
        Rueckstand) laeuft in der eigenen Frist ab und wird normal
        durchgereicht. Kehrt der Aufruf gar nicht zurueck, ist das nach
        OQ-22 die RP2040-Sperre - das wird als `CameraWedgedError` sichtbar,
        statt den Worker fuer immer schweigend haengen zu lassen. Der
        blockierte Thread selbst laesst sich aus Python nicht abbrechen und
        bleibt bewusst haengen; die aufrufende Seite darf `camera` danach
        nicht mehr anfassen.
        """
        outcome = {}

        def run():
            try:
                outcome["value"] = func()
            except Exception as error:  # noqa: BLE001 - an den Aufrufer weiterreichen
                outcome["error"] = error

        thread = threading.Thread(target=run, name=f"camera-{action}", daemon=True)
        thread.start()
        thread.join(timeout_s)
        if thread.is_alive():
            raise CameraWedgedError(
                f"Kamera reagiert nicht ({action}); vermutlich RP2040-Sperre (OQ-22), Reboot noetig"
            )
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def _capture(self, camera):
        request = self._guarded("capture", lambda: camera.capture_request(wait=2.0))
        try:
            image = request.make_array("main").copy()
            metadata = request.get_metadata()
            # Nur JSON-faehige echte Metadaten; SensorTimestamp unveraendert.
            metadata = {k: v for k, v in metadata.items() if isinstance(v, (str, bool, int, float))}
            metadata["timebase"] = TimeBaseKind.SENSOR_BOOTTIME.value
            metadata["timestamp_semantics"] = "unknown"
            metadata["uncertainty_ns"] = None
            return image, metadata
        finally:
            request.release()

    def _settle(self, camera, controls):
        """Warte auf Istwerte manueller Belichtung, nicht nur set_controls()."""
        for index in range(20):
            _image, metadata = self._capture(camera)
            matched = True
            if controls.get("AeEnable") is False:
                for name, tolerance in (("ExposureTime", 0.03), ("AnalogueGain", 0.08)):
                    if name in controls:
                        actual = metadata.get(name)
                        matched &= actual is not None and abs(actual - controls[name]) <= max(
                            1e-6, abs(controls[name]) * tolerance
                        )
            if index >= 3 and matched:
                return metadata
        raise ValueError("Manuelle Belichtung nicht in Kamerametadaten bestaetigt")

    def _automatic(self, camera):
        with self.lock:
            original = copy.deepcopy(self.config)
            self.auto_requested = False
            self.auto = {"state": "running"}
        self.log("info", "Auto-Setup sucht Vorschlag; keine Lesegarantie")
        try:
            camera.set_controls({"AeEnable": True})
            for _ in range(20):
                image, md = self._capture(camera)
                self.publish(image, md)
                if self.cancel_auto.is_set() or self.stop.is_set():
                    raise InterruptedError("Auto-Setup abgebrochen")
            baseline = (md["ExposureTime"], md["AnalogueGain"])
            candidates = []
            for exp_factor in (0.5, 1.0, 2.0):
                for gain_factor in (0.75, 1.0, 1.5):
                    controls = dict(original["camera"]["controls"], AeEnable=False)
                    for name, value in zip(
                        ("ExposureTime", "AnalogueGain"),
                        (baseline[0] * exp_factor, baseline[1] * gain_factor),
                        strict=True,
                    ):
                        low, high = self.capabilities[name][:2]
                        controls[name] = max(low, min(high, value))
                    controls["ExposureTime"] = int(controls["ExposureTime"])
                    camera.set_controls(controls)
                    self._settle(camera, controls)
                    samples = []
                    for index in range(10):
                        if self.cancel_auto.is_set() or self.stop.is_set():
                            raise InterruptedError("Auto-Setup abgebrochen")
                        image, md = self._capture(camera)
                        self.publish(image, md)
                        if index >= 4:
                            samples.append(quality(image, original["roi"]))
                    glare = max(s["saturated_fraction"] for s in samples)
                    contrast = min(s["contrast"] for s in samples)
                    variation = float(np.std([s["brightness"] for s in samples]))
                    if glare < 0.02 and contrast > 0.05 and variation < 0.05:
                        candidates.append((contrast - variation - 5 * glare, controls))
            with self.lock:
                self.auto = (
                    {"state": "proposal", "controls": max(candidates, key=lambda v: v[0])[1]}
                    if candidates
                    else {"state": "failed", "reason": "Kein brauchbarer Vorschlag"}
                )
            self.log("info", "Auto-Setup beendet: " + self.auto["state"] + "; Originaleinstellungen wiederhergestellt")
        except InterruptedError:
            self.auto = {"state": "cancelled"}
            self.log("warn", "Auto-Setup abgebrochen; Original wiederhergestellt")
        finally:
            camera.set_controls(original["camera"]["controls"])
            with self.lock:
                self.applied = -1

    def _worker(self):
        camera = None
        wedged = False
        try:
            if self.simulate:
                self.capabilities = {
                    "AeEnable": [False, True, True],
                    "ExposureTime": [100, 100000, 10000],
                    "AnalogueGain": [1.0, 16.0, 1.0],
                    "Contrast": [0.1, 4.0, 1.0],
                }
            else:
                from picamera2 import Picamera2

                camera = Picamera2(self.camera_index)
            previous = None
            pending_geometry, pending_since = None, 0.0
            while not self.stop.is_set():
                with self.lock:
                    data, revision = copy.deepcopy(self.config), self.revision
                cam = data["camera"]
                geometry = (cam["width"], cam["height"], cam["fps"])
                if camera:
                    if geometry != pending_geometry:
                        pending_geometry, pending_since = geometry, time.monotonic()
                    stable = time.monotonic() - pending_since >= GEOMETRY_DEBOUNCE_S
                else:
                    # Simulation fasst keine Hardware an, keine Entprellung noetig.
                    stable = True
                if previous != geometry and stable:
                    if camera:
                        if previous:
                            self._guarded("stop", camera.stop)
                        self._guarded(
                            "configure",
                            lambda geometry=geometry, cam=cam: camera.configure(
                                camera.create_video_configuration(
                                    main={"size": geometry[:2], "format": "RGB888"},
                                    controls={"FrameRate": cam["fps"]},
                                    queue=False,
                                )
                            ),
                        )
                        self.capabilities = {
                            k: list(v)
                            for k, v in camera.camera_controls.items()
                            if k in ("AeEnable", "ExposureTime", "AnalogueGain", "Contrast")
                        }
                        self._guarded("start", lambda: camera.start(show_preview=False))
                        with self.lock:
                            self.geometry_cycles += 1
                            self._save_geometry_cycles()
                    previous = geometry
                    self.applied = -1
                    self.log("info", f"Kamerastream {geometry}; Fokus mechanisch")
                if camera and previous is None:
                    # Entprellfrist fuer die allererste Konfiguration laeuft noch;
                    # es gibt noch keinen aktiven Stream zum Auslesen.
                    self.stop.wait(0.05)
                    continue
                if revision != self.applied:
                    validate(data, self.capabilities)
                    if camera:
                        camera.set_controls(cam["controls"])
                        self._settle(camera, cam["controls"])
                    with self.lock:
                        self.applied = revision
                    self.log("info", f"Controls r{revision} gesetzt; Ist-Belichtung separat in Metadaten")
                if self.auto_requested:
                    if camera:
                        self._automatic(camera)
                    else:
                        self.auto_requested = False
                        self.auto = {"state": "failed", "reason": "Auto-Setup braucht echte Kamera"}
                if camera:
                    image, metadata = self._capture(camera)
                else:
                    image = np.zeros((cam["height"], cam["width"], 3), np.uint8)
                    cv2.rectangle(
                        image,
                        (int(cam["width"] * 0.2), int(cam["height"] * 0.3)),
                        (int(cam["width"] * 0.8), int(cam["height"] * 0.6)),
                        (160, 160, 160),
                        -1,
                    )
                    cv2.putText(
                        image,
                        "012.50",
                        (int(cam["width"] * 0.25), int(cam["height"] * 0.52)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        2,
                        (0, 0, 0),
                        3,
                    )
                    metadata = {"timebase": TimeBaseKind.SYNTHETIC.value, "uncertainty_ns": None}
                    self.stop.wait(1 / cam["fps"])
                self.publish(image, metadata)
        except Exception as error:
            with self.lock:
                self.error, self.jpeg = str(error), None
            self.log("error", f"Kamera gestoppt: {error}")
            wedged = isinstance(error, CameraWedgedError)
            if isinstance(error, TimeoutError) and camera:
                camera.cancel_all_and_flush()
        finally:
            # Bei einer erkannten RP2040-Sperre haengt bereits ein Thread in
            # der Kamera fest (siehe _guarded); ein weiterer stop()/close()
            # auf demselben Objekt wuerde nur denselben Zustand erneut treffen.
            if camera and not wedged:
                for action, operation in (("stop", camera.stop), ("close", camera.close)):
                    try:
                        self._guarded(action, operation, timeout_s=3.0)
                    except CameraWedgedError as error:
                        self.log("error", f"Kameraabschluss abgebrochen: {error}")
                        break
                    except Exception as error:  # noqa: BLE001 - Shutdown darf den Prozess nicht festhalten
                        self.log("warn", f"Kameraabschluss {action}: {error}")
