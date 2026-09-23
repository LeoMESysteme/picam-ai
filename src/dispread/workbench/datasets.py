"""Geräte- und Sample-Verwaltung für den geführten Datensatz-Sammelmodus.

Eigenständiger Speicherpfad unter ``Controller.root / "datasets"``, unabhängig
von Produktionsprofil, OCR und Freigabegate (Konzept.md §7/§8 bleiben davon
unberührt). Diese Datei kennt keine Kamera und keine ``Controller``-Instanz -
sie bekommt eine bereits eingefrorene Rohbildkopie samt Metadaten übergeben
und entscheidet nur über deren sichere, atomare Ablage.

Layout:

    devices.json                  schema_version=1, UUID -> Gerätestammdaten
    samples/<sample_uuid>/
      image.png                   unveraenderte Pixelkopie, verlustfrei
      sample.json                 Hash, Label, Gruppe, Geraet, Provenienz
    exports/<export_uuid>/
      manifest.json, coverage.json, selection.json, images/<uuid>.png
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import tempfile
import threading
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .profiles import atomic_json

DEVICES_SCHEMA_VERSION = 1
#: Version 2 (2026-09-22, OQ-38 Punkt 6): fuegt das Pflichtfeld
#: ``label_origin`` (+ optional ``label_origin_detail``) hinzu. Proben mit
#: ``schema_version == 1`` haben dieses Feld nicht und werden beim Laden
#: ABSICHTLICH hart abgelehnt (siehe ``_load_sample_json``), analog zu
#: ``_load_devices``. Eine Migration der Bestandsproben unter ``var/`` ist
#: noch NICHT gebaut - siehe CHANGELOG.md und OQ-38 Punkt 6.
SAMPLE_SCHEMA_VERSION = 2
#: Version 2 (2026-09-23): jeder exportierte Sample-Eintrag traegt jetzt
#: ``label_origin`` (+ optional ``label_origin_detail``) mit, und
#: ``coverage.json`` bekommt eine Aufschluesselung ``label_origin_counts``.
#: Ohne dieses Feld waeren von Hand und automatisch gelabelte Proben im
#: exportierten Datensatz nicht mehr unterscheidbar, und jede daraus
#: berichtete Benchmark-Zahl muesste die Herkunftsmischung verschweigen statt
#: nennen (siehe CLAUDE.md-Auftrag zu dieser Aenderung). Ein Export mit
#: ``schema_version == 1`` hat dieses Feld nicht.
EXPORT_SCHEMA_VERSION = 2

TECHNOLOGIES = ("LED", "LCD", "VFD", "other")
SPLITS = ("development", "heldout")
LABEL_STATES = ("readable", "unreadable", "uncertain", "draft")
#: Herkunft eines Labels (OQ-38 Punkt 6, DISPLAYBUS_TAP.md "Anbindung an den
#: Sammelmodus"): "manual" - ein Mensch hat den Sollwert eingetippt;
#: "serial_ascii" - aus dem seriellen GSV-2AS-ASCII-Strom abgeleitet (noch
#: nicht implementiert, nur das Herkunftsmerkmal selbst ist Gegenstand
#: dieser Aenderung). Ohne dieses Feld waeren von Hand und automatisch
#: gelabelte Proben im Bestand nicht mehr unterscheidbar.
LABEL_ORIGINS = ("manual", "serial_ascii")
#: Pflichtschluessel in ``label_origin_detail`` bei ``label_origin ==
#: "serial_ascii"`` und ihr erwarteter Python-Typ. Zusaetzliche, unbekannte
#: Schluessel sind erlaubt (nicht antizipierbar, welche Diagnosefelder ein
#: spaeterer Ableiter braucht) - nur diese hier sind Pflicht und typgeprueft.
_SERIAL_ASCII_DETAIL_REQUIRED: dict[str, type | tuple[type, ...]] = {
    "source_port": str,
    "guard_margin_ms": (int, float),
    "plateau_start_ns": int,
    "plateau_end_ns": int,
    "telegram_count": int,
}
_LABEL_ORIGIN_DETAIL_MAX_KEYS = 20
_LABEL_ORIGIN_DETAIL_STRING_MAX = 200
#: Aufgabenkatalog aus Konzept.md, Ablauf-Schritt 4 - dieselben Schluessel wie
#: in static/dataset.js. Dient hier nur der Luecken-Uebersicht (Aufgabe 5),
#: keiner automatischen Vollstaendigkeitspruefung.
CONDITION_KEYS = (
    "frontal",
    "angled",
    "distance",
    "digits",
    "negative",
    "decimal",
    "multiline",
    "reflection",
    "dim",
)
#: Heuristischer Aehnlichkeitsschwellwert (mittlere normierte Graustufen-
#: differenz eines kleinen Vergleichsbilds), keine validierte Grenze - siehe
#: AGENTS.md ("kein Erfinden von Genauigkeit").
SIMILARITY_THRESHOLD = 0.02

_NAME_MAX = 120
_MODEL_MAX = 120
_NOTE_MAX = 1000
_VALUE_MAX = 64

_FAMILY_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")
_LABEL_RE = re.compile(r"^-?(\d+\.\d+|\.\d+|\d+)$")
_SAMPLE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class DatasetError(ValueError):
    """Basisklasse aller vom Sammelmodus geworfenen Fehler."""


class RevisionConflict(DatasetError):
    """Eine Änderung/ein Save bezog sich auf eine überholte Revision."""


class WriteFailure(DatasetError):
    """Bild oder Metadaten konnten nicht geschrieben werden.

    Unterschieden von einem reinen Validierungsfehler (Konzept: Schreibfehler
    nicht verschlucken, nicht mit einer abgelehnten Eingabe verwechseln).
    """


def normalize_label(raw: Any) -> str:
    """Getippten Anzeigewert normalisieren: Komma->Punkt, sonst unveraendert.

    Erhaelt Vorzeichen, fuehrende Nullen und Dezimalposition exakt wie
    eingegeben - kein numerisches Parsen, keine Rundung. Lehnt alles ab, was
    kein einfacher, eindeutiger Dezimalwert ist (Konzept: unlesbar ablehnen,
    nicht raten).
    """
    if not isinstance(raw, str):
        raise DatasetError("Anzeigewert muss Text sein")
    text = raw.strip().replace(",", ".")
    if not text or len(text) > _VALUE_MAX:
        raise DatasetError("Anzeigewert fehlt oder ist zu lang")
    if not _LABEL_RE.fullmatch(text):
        raise DatasetError(f"Ungueltiger Anzeigewert: {raw!r}")
    return text


def validate_bbox(bbox: Any, width: int, height: int) -> list[float]:
    """Achsparallele Zielbox in Originalbildpixeln pruefen. Nie klemmen, nur ablehnen."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise DatasetError("bbox erwartet [x, y, width, height]")
    values = list(bbox)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise DatasetError("bbox muss endliche Zahlen enthalten")
    x, y, w, h = (float(v) for v in values)
    if w <= 0 or h <= 0:
        raise DatasetError("bbox muss positive Flaeche haben")
    if x < 0 or y < 0 or x + w > width or y + h > height:
        raise DatasetError("bbox liegt ausserhalb des Bildes")
    return [x, y, w, h]


def _short_text(value: Any, field: str, max_len: int, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise DatasetError(f"{field} ist Pflicht")
        return None
    if not isinstance(value, str) or not value.strip():
        if required:
            raise DatasetError(f"{field} ist Pflicht")
        return None
    text = value.strip()
    if len(text) > max_len or not text.isprintable():
        raise DatasetError(f"{field}: bis zu {max_len} druckbare Zeichen")
    return text


def _validate_label_origin_detail(detail: Any) -> dict:
    """``label_origin_detail`` fuer ``label_origin == "serial_ascii"`` pruefen.

    Verlangt die fuenf Pflichtschluessel aus ``_SERIAL_ASCII_DETAIL_REQUIRED``
    mit passendem Typ (Konzept: kein stilles "wird schon passen"). Weitere
    Schluessel sind erlaubt, aber begrenzt (Gesamtgroesse, Stringlaenge) und
    nur als JSON-faehige Skalare/Zahlen - kein Erfinden zusaetzlicher
    Nachrichtenstruktur.
    """
    if not isinstance(detail, dict):
        raise DatasetError("label_origin_detail muss ein Objekt sein")
    if len(detail) > _LABEL_ORIGIN_DETAIL_MAX_KEYS:
        raise DatasetError(f"label_origin_detail: hoechstens {_LABEL_ORIGIN_DETAIL_MAX_KEYS} Schluessel")

    for key, expected_type in _SERIAL_ASCII_DETAIL_REQUIRED.items():
        if key not in detail:
            raise DatasetError(f"label_origin_detail: Pflichtschluessel {key!r} fehlt")
        value = detail[key]
        if isinstance(value, bool) or not isinstance(value, expected_type):
            raise DatasetError(f"label_origin_detail[{key!r}] hat den falschen Typ")
        if isinstance(value, float) and not math.isfinite(value):
            raise DatasetError(f"label_origin_detail[{key!r}] muss endlich sein")

    out: dict[str, Any] = {}
    for key, value in detail.items():
        if not isinstance(key, str) or not key or len(key) > _NAME_MAX:
            raise DatasetError("label_origin_detail: Schluessel muessen kurze Zeichenketten sein")
        if isinstance(value, bool):
            out[key] = value
        elif isinstance(value, str):
            if len(value) > _LABEL_ORIGIN_DETAIL_STRING_MAX:
                raise DatasetError(f"label_origin_detail[{key!r}]: Text zu lang")
            out[key] = value
        elif isinstance(value, int):
            out[key] = value
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise DatasetError(f"label_origin_detail[{key!r}] muss endlich sein")
            out[key] = value
        elif value is None:
            out[key] = None
        else:
            raise DatasetError(f"label_origin_detail[{key!r}]: nicht JSON-faehiger Skalarwert")
    return out


def _validate_label_origin(annotation: dict) -> tuple[str, dict | None]:
    """``label_origin``/``label_origin_detail`` einer Annotation pruefen.

    ``label_origin`` ist Pflicht - ein fehlender Wert ist ein Fehler, kein
    stiller "manual"-Default (OQ-38 Punkt 6: ein stillschweigendes "war wohl
    manuell" ist genau die Art Annahme, die dieses Projekt nicht haben will).
    Fehlend und explizit ``None`` werden gleich behandelt, beides lehnt ab.
    """
    label_origin = annotation.get("label_origin")
    if label_origin not in LABEL_ORIGINS:
        raise DatasetError(f"label_origin ist Pflicht und muss eine von {LABEL_ORIGINS} sein")
    detail = annotation.get("label_origin_detail")
    if label_origin == "manual":
        if detail is not None:
            raise DatasetError("label_origin_detail muss bei label_origin=manual None sein")
        return label_origin, None
    # label_origin == "serial_ascii"
    return label_origin, _validate_label_origin_detail(detail)


def _load_sample_json(path: Path) -> dict:
    """``sample.json`` laden und die Schemaversion pruefen.

    Analog zu ``DatasetStore._load_devices``: eine unerwartete
    ``schema_version`` wird hart abgelehnt, nicht still als aktuelles Schema
    behandelt. Seit Version 2 (OQ-38 Punkt 6) ist ``label_origin`` Pflicht;
    eine Probe mit ``schema_version == 1`` hat dieses Feld nicht und
    verlangt eine Migration, bevor der Sammelmodus wieder darauf zugreift
    (siehe CHANGELOG.md und ``docs/open-questions.md`` OQ-38 Punkt 6 - die
    Migration selbst ist bewusst NICHT Teil dieser Aenderung).
    """
    with open(path, encoding="utf-8") as handle:
        sample = json.load(handle)
    if sample.get("schema_version") != SAMPLE_SCHEMA_VERSION:
        raise DatasetError(
            f"Probe {path}: unbekannte/veraltete schema_version "
            f"{sample.get('schema_version')!r} (erwartet {SAMPLE_SCHEMA_VERSION}) - "
            "Migration der Bestandsproben noetig, bevor der Sammelmodus sie liest "
            "(siehe OQ-38 Punkt 6)"
        )
    return sample


def _validate_device_fields(data: dict, *, partial: bool) -> dict:
    out = {}
    if "name" in data or not partial:
        out["name"] = _short_text(data.get("name"), "Anzeigename", _NAME_MAX, required=True)
    if "model" in data or not partial:
        out["model"] = _short_text(data.get("model"), "Modell", _MODEL_MAX, required=False)
    if "family" in data or not partial:
        family = data.get("family")
        if not isinstance(family, str) or not _FAMILY_RE.fullmatch(family):
            raise DatasetError("family: technischer Enum-Wert, a-z/A-Z/0-9/_/- bis 32 Zeichen")
        out["family"] = family
    if "technology" in data or not partial:
        technology = data.get("technology")
        if technology not in TECHNOLOGIES:
            raise DatasetError(f"technology muss eine von {TECHNOLOGIES} sein")
        out["technology"] = technology
    if "split" in data or not partial:
        split = data.get("split")
        if split not in SPLITS:
            raise DatasetError(f"split muss eine von {SPLITS} sein")
        out["split"] = split
    if "identity_evidence" in data or not partial:
        # "identity_verified=true nur nach menschlicher Bestaetigung des
        # physischen Geraets; Belegart zusaetzlich als identity_evidence
        # protokollieren" (Konzept, Exportvertrag) - Software kann eine
        # falsche menschliche Angabe nicht beweisen, aber die Belegart bleibt
        # nachvollziehbar dokumentiert statt implizit "irgendwie bestaetigt".
        out["identity_evidence"] = _short_text(
            data.get("identity_evidence"), "Belegart der Identitätsbestätigung", _NOTE_MAX, required=True
        )
    return out


class DatasetStore:
    """Eigene Instanz mit eigenem Lock, unabhaengig vom Kamera-/Profil-Lock des Controllers."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._devices_path = self.root / "devices.json"
        # Eigenes Lock, unabhaengig von Controller.lock - serialisiert nur
        # die eigenen Lese-Aendere-Schreibe-Abschnitte dieser Instanz.
        self._lock = threading.Lock()

    # -- interne Persistenz ------------------------------------------------

    def _load_devices(self) -> dict:
        if not self._devices_path.exists():
            return {"schema_version": DEVICES_SCHEMA_VERSION, "devices": {}}
        with open(self._devices_path, encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("schema_version") != DEVICES_SCHEMA_VERSION:
            raise DatasetError("Unbekanntes devices.json-Schema")
        return data

    def _save_devices(self, data: dict) -> None:
        try:
            atomic_json(self._devices_path, data)
        except OSError as error:
            raise WriteFailure(f"Geraeteregistrierung nicht geschrieben: {error}") from error

    def _iter_sample_dirs(self) -> list[Path]:
        """Nur vollständig veröffentlichte Sample-Verzeichnisse (UUID-Name).

        Ein Absturz zwischen dem Schreiben von ``sample.json`` und dem
        abschließenden ``rename()`` (siehe ``_save_sample_locked``)
        hinterlässt ein temporäres ``.sample-*``-Verzeichnis mit demselben
        Dateiinhalt. Das darf nach einem Neustart nicht als fertige Probe
        zählen (Konzept, Aufgabe 1: "Unvollständige temporäre Verzeichnisse
        zählen nach Neustart nicht mit"). Ausschließlich der UUID-Name
        entscheidet, nicht die Existenz von ``sample.json`` allein.
        """
        samples_dir = self.root / "samples"
        if not samples_dir.is_dir():
            return []
        return [entry for entry in sorted(samples_dir.iterdir()) if entry.is_dir() and _SAMPLE_ID_RE.fullmatch(entry.name)]

    def _count_incomplete_sample_dirs(self) -> int:
        """Diagnostische Zählung liegen gebliebener Temp-Verzeichnisse (siehe ``_iter_sample_dirs``)."""
        samples_dir = self.root / "samples"
        if not samples_dir.is_dir():
            return 0
        return sum(
            1 for entry in samples_dir.iterdir() if entry.is_dir() and not _SAMPLE_ID_RE.fullmatch(entry.name)
        )

    def _device_has_samples(self, device_id: str) -> bool:
        for sample_dir in self._iter_sample_dirs():
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                sample = _load_sample_json(sample_json)
            except (OSError, json.JSONDecodeError):
                continue
            if sample.get("device_id") == device_id:
                return True
        return False

    # -- Geraete -------------------------------------------------------------

    def create_device(self, data: dict) -> dict:
        fields = _validate_device_fields(data, partial=False)
        if data.get("identity_confirmed") is not True:
            raise DatasetError("Physische Geraeteidentitaet muss bestaetigt werden")
        with self._lock:
            registry = self._load_devices()
            device_id = uuid.uuid4().hex
            record = {
                "id": device_id,
                "revision": 0,
                "identity_confirmed": True,
                "groups": {},
                **fields,
            }
            registry["devices"][device_id] = record
            self._save_devices(registry)
            return copy.deepcopy(record)

    def get_device(self, device_id: str) -> dict:
        registry = self._load_devices()
        device = registry["devices"].get(device_id)
        if device is None:
            raise DatasetError(f"Unbekanntes Geraet: {device_id}")
        return copy.deepcopy(device)

    def list_devices(self) -> list[dict]:
        """Alle Geraete inkl. ihrer Situationsgruppen, fuer die Schrittauswahl der Oberflaeche.

        Sortiert nach Anzeigename - keine Identitaet, nur eine stabile
        Bedienreihenfolge (die UUID bleibt die eigentliche Kennung).
        """
        registry = self._load_devices()
        devices = [copy.deepcopy(device) for device in registry["devices"].values()]
        devices.sort(key=lambda device: device["name"].lower())
        return devices

    def update_device(self, device_id: str, revision: int, changes: dict) -> dict:
        with self._lock:
            registry = self._load_devices()
            device = registry["devices"].get(device_id)
            if device is None:
                raise DatasetError(f"Unbekanntes Geraet: {device_id}")
            if device["revision"] != revision:
                raise RevisionConflict(
                    f"Geraet {device_id}: erwartete Revision {revision}, aktuell {device['revision']}"
                )
            if "split" in changes and changes["split"] != device["split"] and self._device_has_samples(device_id):
                raise DatasetError("Gerätesplit ist nach der ersten Aufnahme gesperrt")
            fields = _validate_device_fields({**device, **changes}, partial=False)
            device = {**device, **fields, "revision": device["revision"] + 1}
            registry["devices"][device_id] = device
            self._save_devices(registry)
            return copy.deepcopy(device)

    def begin_group(self, device_id: str, change_note: str) -> dict:
        note = _short_text(change_note, "Situationsbeschreibung", _NOTE_MAX, required=True)
        with self._lock:
            registry = self._load_devices()
            device = registry["devices"].get(device_id)
            if device is None:
                raise DatasetError(f"Unbekanntes Geraet: {device_id}")
            group_id = uuid.uuid4().hex
            device["groups"][group_id] = {"device_id": device_id, "change_note": note}
            registry["devices"][device_id] = device
            self._save_devices(registry)
            return {"group_id": group_id, "device_id": device_id, "change_note": note}

    def _resolve_group(self, registry: dict, device_id: str, group_id: str) -> dict:
        device = registry["devices"].get(device_id)
        if device is None:
            raise DatasetError(f"Unbekanntes Geraet: {device_id}")
        group = device["groups"].get(group_id)
        if group is None:
            raise DatasetError(f"Unbekannte Situationsgruppe: {group_id}")
        return group

    def resolve_group(self, device_id: str, group_id: str) -> dict:
        """Oeffentliche Vorabpruefung: existiert Geraet/Gruppe so wie behauptet?"""
        return self._resolve_group(self._load_devices(), device_id, group_id)

    def get_export_dir(self, export_id: str) -> Path:
        """Export-ID serverseitig zu einem Verzeichnis unterhalb der Exporte aufloesen.

        Keine vom Browser frei bestimmbaren Pfadparameter (Konzept.md §4) -
        nur ein bereits validiertes Hex-Format wird ueberhaupt angesehen.
        """
        if not re.fullmatch(r"[0-9a-f]{32}", export_id):
            raise DatasetError("Ungueltige Export-ID")
        path = self.root / "exports" / export_id
        if not path.is_dir():
            raise DatasetError(f"Unbekannter Export: {export_id}")
        return path

    # -- Samples ---------------------------------------------------------

    def _sample_dir(self, sample_id: str) -> Path:
        return self.root / "samples" / sample_id

    def _find_existing_sample_for_token(self, capture_token: str) -> dict | None:
        for sample_dir in self._iter_sample_dirs():
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                sample = _load_sample_json(sample_json)
            except (OSError, json.JSONDecodeError):
                continue
            if sample.get("capture_token") == capture_token:
                return sample
        return None

    def save_sample(self, capture: dict, annotation: dict) -> dict:
        with self._lock:
            return self._save_sample_locked(capture, annotation)

    def _save_sample_locked(self, capture: dict, annotation: dict) -> dict:
        """Ein eingefrorenes Rohbild plus Zielbox/Label sicher, atomar speichern.

        Idempotent fuer denselben ``capture_token``: ein wiederholter Aufruf
        mit identischem Label liefert die bereits gespeicherte Probe zurueck,
        statt eine zweite anzulegen. Ein wiederholter Aufruf mit einem
        *anderen* Label auf denselben, bereits gespeicherten Token ist ein
        Revisionskonflikt, kein stilles Ueberschreiben.
        """
        image = capture.get("image")
        if image is None:
            raise DatasetError("capture ohne Rohbild")
        capture_token = capture.get("capture_token")
        if not capture_token or not isinstance(capture_token, str):
            raise DatasetError("capture_token fehlt")
        device_id = capture.get("device_id")
        group_id = capture.get("group_id")
        registry = self._load_devices()
        self._resolve_group(registry, device_id, group_id)

        height, width = image.shape[:2]
        bbox = validate_bbox(annotation.get("bbox"), width, height)
        label_state = annotation.get("label_state")
        if label_state not in LABEL_STATES:
            raise DatasetError(f"label_state muss eine von {LABEL_STATES} sein")
        expected_text = None
        if label_state == "readable":
            expected_text = normalize_label(annotation.get("expected_text"))
        elif annotation.get("expected_text") is not None:
            raise DatasetError("expected_text ist nur bei label_state=readable erlaubt")
        target_label = _short_text(annotation.get("target_label"), "Zielbezeichnung", 200, required=False)
        conditions = list(annotation.get("conditions") or [])
        if not all(isinstance(c, str) and c and len(c) <= 64 for c in conditions):
            raise DatasetError("conditions muessen kurze Textschluessel sein")
        label_origin, label_origin_detail = _validate_label_origin(annotation)

        existing = self._find_existing_sample_for_token(capture_token)
        pending = {
            "device_id": device_id,
            "group_id_for_check": group_id,
            "bbox": bbox,
            "target_label": target_label,
            "label_state": label_state,
            "expected_text": expected_text,
            "conditions": conditions,
        }
        if existing is not None:
            unchanged = (
                existing["device_id"] == device_id
                and existing["independence_group"] == group_id
                and existing["bbox"] == bbox
                and existing["target_label"] == target_label
                and existing["label_state"] == label_state
                and existing["expected_text"] == expected_text
                and existing["conditions"] == conditions
                and existing.get("label_origin") == label_origin
                and existing.get("label_origin_detail") == label_origin_detail
            )
            if not unchanged:
                raise RevisionConflict(
                    f"capture_token {capture_token} ist bereits mit anderem Label gespeichert"
                )
            return copy.deepcopy(existing)
        del pending

        sample_id = uuid.uuid4().hex
        final_dir = self._sample_dir(sample_id)
        temp_dir = Path(tempfile.mkdtemp(dir=self.root / "samples" if (self.root / "samples").is_dir() else self.root, prefix=".sample-"))
        try:
            ok = cv2.imwrite(str(temp_dir / "image.png"), image)
            if not ok:
                raise WriteFailure("Rohbild konnte nicht geschrieben werden")
            with open(temp_dir / "image.png", "rb") as handle:
                image_bytes = handle.read()
            sha256 = hashlib.sha256(image_bytes).hexdigest()

            duplicate_of = self._find_duplicate_hash(sha256)
            similar = None if duplicate_of is not None else self._find_similar_in_group(image, group_id, sha256)
            similarity_reason = None
            if similar is not None:
                similarity_reason = _short_text(annotation.get("similarity_reason"), "Begründung", _NOTE_MAX, required=False)
                if not annotation.get("similarity_confirmed") or not similarity_reason:
                    raise DatasetError(
                        f"Ähnlich zu vorhandener Probe {similar[0]} in dieser Situation "
                        f"(Heuristik-Score {similar[1]:.4f}, kein Beweis für/gegen Unabhängigkeit). "
                        "Mit similarity_confirmed=true und einer Begründung erneut speichern, "
                        "falls trotzdem eigenständig."
                    )

            sample = {
                "schema_version": SAMPLE_SCHEMA_VERSION,
                "id": sample_id,
                "device_id": device_id,
                "device_revision": registry["devices"][device_id]["revision"],
                "split": registry["devices"][device_id]["split"],
                "independence_group": group_id,
                "capture_token": capture_token,
                "source_id": capture.get("source_id"),
                "frame_sequence": capture.get("frame_sequence"),
                "capture_timestamp": capture.get("capture_timestamp"),
                "source_revision": capture.get("source_revision"),
                "sha256": sha256,
                "width": width,
                "height": height,
                "bbox": bbox,
                "target_label": target_label,
                "label_state": label_state,
                "expected_text": expected_text,
                "conditions": conditions,
                "label_origin": label_origin,
                "label_origin_detail": label_origin_detail,
                "independence_confirmation": bool(annotation.get("independence_confirmation", True)),
                "synthetic": bool(capture.get("synthetic", False)),
                "stored_at_utc": capture.get("stored_at_utc"),
                "stored_timebase": "UTC",
                "source": capture.get("source"),
                "license": capture.get("license"),
                "formatter_provisional": True,
                "metadata_revision": 0,
                "duplicate_of": duplicate_of,
                "similarity_warning": {"candidate": similar[0], "score": similar[1]} if similar else None,
                "similarity_confirmation_reason": similarity_reason,
            }
            try:
                with open(temp_dir / "sample.json", "w", encoding="utf-8") as handle:
                    json.dump(sample, handle, indent=2, allow_nan=False)
                    handle.write("\n")
            except OSError as error:
                raise WriteFailure(f"Sample-Metadaten nicht geschrieben: {error}") from error

            (self.root / "samples").mkdir(parents=True, exist_ok=True)
            try:
                temp_dir.rename(final_dir)
            except OSError as error:
                raise WriteFailure(f"Sample-Verzeichnis nicht veroeffentlicht: {error}") from error
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        return copy.deepcopy(sample)

    def _similarity_score(self, image: np.ndarray, other_path: Path) -> float:
        """Mittlere normierte Graustufendifferenz eines kleinen Vergleichsbilds.

        Nur ein Hinweis (Heuristik, siehe SIMILARITY_THRESHOLD) - kein Beweis
        fuer/gegen tatsaechliche Bildidentitaet oder -unabhaengigkeit.
        """
        other = cv2.imread(str(other_path))
        if other is None:
            return 1.0
        a = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        b = other if other.ndim == 2 else cv2.cvtColor(other, cv2.COLOR_BGR2GRAY)
        a = cv2.resize(a, (32, 32)).astype(np.float32)
        b = cv2.resize(b, (32, 32)).astype(np.float32)
        return float(np.abs(a - b).mean() / 255.0)

    def _find_similar_in_group(self, image: np.ndarray, group_id: str, own_sha256: str) -> tuple[str, float] | None:
        best: tuple[str, float] | None = None
        for other in self._load_all_samples():
            if other["independence_group"] != group_id or other["sha256"] == own_sha256:
                continue
            score = self._similarity_score(image, self._sample_dir(other["id"]) / "image.png")
            if score < SIMILARITY_THRESHOLD and (best is None or score < best[1]):
                best = (other["id"], score)
        return best

    def _find_duplicate_hash(self, sha256: str) -> str | None:
        for sample_dir in self._iter_sample_dirs():
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                sample = _load_sample_json(sample_json)
            except (OSError, json.JSONDecodeError):
                continue
            if sample.get("sha256") == sha256:
                return sample["id"]
        return None

    def _load_all_samples(self) -> list[dict]:
        out = []
        for sample_dir in self._iter_sample_dirs():
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                out.append(_load_sample_json(sample_json))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def select_sample(self, sample_id: str, revision: int) -> dict:
        with self._lock:
            return self._select_sample_locked(sample_id, revision)

    def _select_sample_locked(self, sample_id: str, revision: int) -> dict:
        """Diese Probe als Vertreter ihrer Unabhaengigkeitsgruppe markieren."""
        final_dir = self._sample_dir(sample_id)
        sample_json = final_dir / "sample.json"
        if not sample_json.exists():
            raise DatasetError(f"Unbekannte Probe: {sample_id}")
        sample = _load_sample_json(sample_json)
        if sample.get("metadata_revision", 0) != revision:
            raise RevisionConflict(
                f"Probe {sample_id}: erwartete Revision {revision}, aktuell {sample.get('metadata_revision', 0)}"
            )
        registry = self._load_devices()
        device = registry["devices"].get(sample["device_id"])
        for other in self._load_all_samples():
            if other["independence_group"] == sample["independence_group"] and other["id"] != sample_id:
                other["selected"] = False
                self._rewrite_sample(other)
        sample["selected"] = True
        sample["metadata_revision"] = sample.get("metadata_revision", 0) + 1
        self._rewrite_sample(sample)
        del device
        return copy.deepcopy(sample)

    def relabel_sample(self, sample_id: str, revision: int, expected_text: str, reason: str) -> dict:
        with self._lock:
            return self._relabel_sample_locked(sample_id, revision, expected_text, reason)

    def _relabel_sample_locked(self, sample_id: str, revision: int, expected_text: str, reason: str) -> dict:
        """Getippte Ground Truth einer bereits gespeicherten Probe korrigieren.

        Anders als ``save_sample`` (Idempotenz/Revisionskonflikt bei *neuen*
        Proben) ist das hier die ausdrueckliche, begruendete Korrektur einer
        vorhandenen: ``var/`` liegt nicht unter Versionskontrolle, also ist
        ``label_history`` die einzige Spur des vorherigen Werts. Nur bei
        ``label_state="readable"`` sinnvoll - bei unlesbaren Proben ist
        ``expected_text`` bereits ``None`` und eine andere Operation gefragt.

        Entscheidung zu ``label_origin`` (OQ-38 Punkt 6): ein Umlabeln von
        Hand setzt ``label_origin`` immer auf ``"manual"`` und loescht ein
        vorhandenes ``label_origin_detail`` (die Invariante "manual ⇒ detail
        ist None" gilt danach wieder). Die Alternative - automatisch
        gelabelte Proben vom Umlabeln auszuschliessen - wurde verworfen: ein
        Mensch, der eine Probe korrigiert, IST in diesem Moment die neue,
        massgebliche Quelle, und die vorherige Herkunft (samt ihrem Detail)
        bleibt vollstaendig im ``label_history``-Eintrag erhalten
        (``previous_label_origin``/``previous_label_origin_detail``) statt
        verloren zu gehen. ``previous_label_origin`` wird IMMER geschrieben,
        auch wenn die Probe schon ``"manual"`` war - ein einheitliches Schema
        ist verlaesslicher als ein bedingter Schluessel.

        Nebenwirkung, bewusst in Kauf genommen: der bestehende Leerlauf-Schutz
        weiter unten (unveraendertes ``expected_text`` ist ein Fehler) gilt
        auch hier - eine ``serial_ascii``-Probe, deren Wert bereits korrekt
        ist, kann NICHT allein zum Zweck der Herkunftsaenderung "umgelabelt"
        werden. Das ist gewollt: keine Herkunfts-Reinwaschung ohne echte
        Wertkorrektur.
        """
        final_dir = self._sample_dir(sample_id)
        sample_json = final_dir / "sample.json"
        if not sample_json.exists():
            raise DatasetError(f"Unbekannte Probe: {sample_id}")
        sample = _load_sample_json(sample_json)
        if sample.get("metadata_revision", 0) != revision:
            raise RevisionConflict(
                f"Probe {sample_id}: erwartete Revision {revision}, aktuell {sample.get('metadata_revision', 0)}"
            )
        if sample.get("label_state") != "readable":
            raise DatasetError(
                "relabel_sample nur fuer label_state=readable - "
                "eine unlesbare Probe braucht eine andere Operation, kein Umlabeln"
            )
        reason_text = _short_text(reason, "Begründung", _NOTE_MAX, required=True)
        new_text = normalize_label(expected_text)
        if new_text == sample.get("expected_text"):
            raise DatasetError("expected_text unveraendert - kein Umlabeln noetig")

        history = list(sample.get("label_history") or [])
        history.append(
            {
                "previous_expected_text": sample.get("expected_text"),
                "changed_at_utc": datetime.now(UTC).isoformat(),
                "reason": reason_text,
                "previous_label_origin": sample.get("label_origin"),
                "previous_label_origin_detail": sample.get("label_origin_detail"),
            }
        )
        sample["label_history"] = history
        sample["expected_text"] = new_text
        sample["label_origin"] = "manual"
        sample["label_origin_detail"] = None
        sample["metadata_revision"] = sample.get("metadata_revision", 0) + 1
        self._rewrite_sample(sample)
        return copy.deepcopy(sample)

    def _rewrite_sample(self, sample: dict) -> None:
        sample_dir = self._sample_dir(sample["id"])
        try:
            atomic_json(sample_dir / "sample.json", sample)
        except OSError as error:
            raise WriteFailure(f"Sample-Metadaten nicht aktualisiert: {error}") from error

    # -- Uebersicht --------------------------------------------------------

    def summary(self) -> dict:
        registry = self._load_devices()
        samples = self._load_all_samples()
        # Unabhaengigkeitszahl haengt an der Gruppen-ID, nicht an der Anzahl
        # Wiederholungen darin - zehn Aufnahmen derselben Situation zaehlen als
        # eine Gruppe, ein Auswahlwechsel (select_sample) aendert nur den
        # Vertreter, nie diese Zahl.
        groups = {s["independence_group"] for s in samples}
        # "Real" schliesst synthetische Fixtures aus - sie duerfen den Zaehler
        # lesbarer/unlesbarer *realer* Testwerte nicht aufblaehen (Aufgabe 5).
        real = [s for s in samples if not s["synthetic"]]
        readable = [s for s in real if s["label_state"] == "readable"]
        unreadable = [s for s in real if s["label_state"] == "unreadable"]
        uncertain = [s for s in real if s["label_state"] in ("uncertain", "draft")]
        device_ids = {s["device_id"] for s in samples if not s["synthetic"]}
        families = {registry["devices"][d]["family"] for d in device_ids if d in registry["devices"]}
        technologies = {registry["devices"][d]["technology"] for d in device_ids if d in registry["devices"]}
        return {
            "devices": len(registry["devices"]),
            "samples": len(samples),
            "independence_groups": len(groups),
            "readable": len(readable),
            "unreadable": len(unreadable),
            "uncertain_or_draft": len(uncertain),
            "families": sorted(families),
            "technologies": sorted(technologies),
            "missing_conditions": self._missing_conditions(registry, real),
            "incomplete_temp_dirs": self._count_incomplete_sample_dirs(),
        }

    def _missing_conditions(self, registry: dict, real_samples: list[dict]) -> dict:
        """Fehlende Bedingungen je Geraet und insgesamt - eine Luecke, keine fingierte Abdeckung."""
        seen_by_device: dict[str, set[str]] = {}
        seen_overall: set[str] = set()
        for sample in real_samples:
            seen_by_device.setdefault(sample["device_id"], set()).update(sample["conditions"])
            seen_overall.update(sample["conditions"])
        by_device = {
            device_id: sorted(set(CONDITION_KEYS) - seen)
            for device_id, seen in seen_by_device.items()
            if device_id in registry["devices"]
        }
        return {"overall": sorted(set(CONDITION_KEYS) - seen_overall), "by_device": by_device}

    # -- Export ------------------------------------------------------------

    def export(self) -> dict:
        with self._lock:
            return self._export_locked()

    def _export_locked(self) -> dict:
        registry = self._load_devices()
        samples = self._load_all_samples()

        included: list[dict] = []
        excluded: list[dict] = []

        # "Unsichere/Entwurfs-/synthetische/ueberzaehlige Wiederholungsbilder
        # nicht in samples aufnehmen" (Konzept, Exportvertrag) - synthetisch
        # steht ausdruecklich in derselben Aufzaehlung wie uncertain/draft und
        # darf den Export ebensowenig als reale Abdeckung erreichen.
        real_samples = []
        for sample in samples:
            if sample["synthetic"]:
                excluded.append({"id": sample["id"], "reason": "synthetic"})
                continue
            real_samples.append(sample)

        by_group: dict[str, list[dict]] = {}
        for sample in real_samples:
            by_group.setdefault(sample["independence_group"], []).append(sample)
        for _group_id, group_samples in by_group.items():
            selected = [s for s in group_samples if s.get("selected")]
            if len(group_samples) > 1 and not selected:
                for sample in group_samples:
                    excluded.append({"id": sample["id"], "reason": "group_without_selection"})
                continue
            chosen = selected[0] if selected else group_samples[0]
            for sample in group_samples:
                if sample["id"] == chosen["id"]:
                    continue
                excluded.append({"id": sample["id"], "reason": "repeat_in_group"})
            if chosen["label_state"] in ("uncertain", "draft"):
                excluded.append({"id": chosen["id"], "reason": f"label_state={chosen['label_state']}"})
                continue
            included.append(chosen)

        # Der externe Experiment-Loader lehnt ein doppeltes Bildhash ueber ALLE
        # Proben eines Exports hinweg ab (nicht nur innerhalb einer Gruppe) -
        # zwei verschiedene Situationen koennten sonst zufaellig dasselbe Bild
        # als je "eigene" unabhaengige Probe einreichen. Nur der erste Treffer
        # bleibt drin, alle weiteren werden mit Grund ausgeschlossen.
        deduped: list[dict] = []
        seen_hashes: dict[str, str] = {}
        for sample in included:
            if sample["sha256"] in seen_hashes:
                excluded.append(
                    {"id": sample["id"], "reason": f"duplicate_image_hash_of={seen_hashes[sample['sha256']]}"}
                )
                continue
            seen_hashes[sample["sha256"]] = sample["id"]
            deduped.append(sample)
        included = deduped

        export_id = uuid.uuid4().hex
        final_dir = self.root / "exports" / export_id
        temp_dir = Path(tempfile.mkdtemp(dir=self.root if self.root.is_dir() else None, prefix=".export-"))
        try:
            (temp_dir / "images").mkdir(parents=True, exist_ok=True)
            manifest_samples = []
            for sample in included:
                device = registry["devices"].get(sample["device_id"], {})
                src_image = self._sample_dir(sample["id"]) / "image.png"
                dst_image = temp_dir / "images" / f"{sample['id']}.png"
                shutil.copyfile(src_image, dst_image)
                image_bytes = dst_image.read_bytes()
                sha256 = hashlib.sha256(image_bytes).hexdigest()
                if sha256 != sample["sha256"]:
                    raise WriteFailure(f"Bildhash weicht ab: {sample['id']}")
                manifest_samples.append(
                    {
                        "id": sample["id"],
                        "path": f"images/{sample['id']}.png",
                        "sha256": sha256,
                        "device_id": sample["device_id"],
                        "identity_verified": bool(device.get("identity_confirmed")),
                        "identity_evidence": device.get("identity_evidence"),
                        "family": device.get("family"),
                        "technology": device.get("technology"),
                        "split": sample["split"],
                        "independence_group": sample["independence_group"],
                        "source": sample.get("source") or f"local-workbench:{sample['device_id']}/{sample['id']}",
                        "license": sample.get("license") or "LicenseRef-Project-Local-Evaluation",
                        "expected_text": sample["expected_text"],
                        "bbox": sample["bbox"],
                        "conditions": sample["conditions"],
                        "all_displays_annotated": False,
                        "label_origin": sample["label_origin"],
                        "label_origin_detail": sample.get("label_origin_detail"),
                    }
                )
            manifest = {"schema_version": EXPORT_SCHEMA_VERSION, "samples": manifest_samples}
            try:
                with open(temp_dir / "manifest.json", "w", encoding="utf-8") as handle:
                    json.dump(manifest, handle, indent=2, allow_nan=False)
                    handle.write("\n")
            except OSError as error:
                raise WriteFailure(f"Manifest nicht geschrieben: {error}") from error

            coverage = self._coverage(registry, included)
            try:
                with open(temp_dir / "coverage.json", "w", encoding="utf-8") as handle:
                    json.dump(coverage, handle, indent=2, allow_nan=False)
                    handle.write("\n")
                with open(temp_dir / "selection.json", "w", encoding="utf-8") as handle:
                    json.dump({"excluded": excluded}, handle, indent=2, allow_nan=False)
                    handle.write("\n")
            except OSError as error:
                raise WriteFailure(f"Exportmetadaten nicht geschrieben: {error}") from error

            (self.root / "exports").mkdir(parents=True, exist_ok=True)
            try:
                temp_dir.rename(final_dir)
            except OSError as error:
                raise WriteFailure(f"Export nicht veroeffentlicht: {error}") from error
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        return {"export_id": export_id, "coverage": coverage, "path": final_dir}

    def _coverage(self, registry: dict, included: list[dict]) -> dict:
        verified_devices = {s["device_id"] for s in included if registry["devices"].get(s["device_id"], {}).get("identity_confirmed")}
        heldout = [s for s in included if s["split"] == "heldout"]
        heldout_groups = {s["independence_group"] for s in heldout}
        families = {registry["devices"][s["device_id"]]["family"] for s in included if s["device_id"] in registry["devices"]}
        technologies = {registry["devices"][s["device_id"]]["technology"] for s in included if s["device_id"] in registry["devices"]}
        warnings = []
        if heldout and all(s["label_state"] == "unreadable" for s in heldout):
            warnings.append("Abschlusstest enthaelt nur unlesbare Bilder")
        if not any(registry["devices"].get(s["device_id"], {}).get("technology") == "LED" for s in included):
            warnings.append("keine beleuchteten LED-Anzeigen im Export")
        # Herkunftsmischung des Exports (OQ-38 Punkt 6 / label_origin, siehe
        # EXPORT_SCHEMA_VERSION): jede aus diesem Export berichtete
        # Benchmark-Zahl muss die Herkunftsmischung nennen koennen, statt sie
        # zu verschweigen - deshalb hier gezaehlt, nicht nur pro Probe im
        # Manifest mitgefuehrt.
        label_origin_counts = {origin: 0 for origin in LABEL_ORIGINS}
        for sample in included:
            label_origin_counts[sample["label_origin"]] = label_origin_counts.get(sample["label_origin"], 0) + 1
        return {
            "images": len(included),
            "independence_groups": len({s["independence_group"] for s in included}),
            "verified_devices": len(verified_devices),
            "readable": len([s for s in included if s["label_state"] == "readable"]),
            "unreadable": len([s for s in included if s["label_state"] == "unreadable"]),
            "label_origin_counts": label_origin_counts,
            "families": sorted(families),
            "technologies": sorted(technologies),
            "heldout_independence_groups": len(heldout_groups),
            "targets": {
                "verified_devices": 6,
                "families": 3,
                "requires_led_and_lcd": True,
                "reserved_devices": 2,
                "heldout_independence_groups": 30,
            },
            "warnings": warnings,
        }


def zip_export(export_dir: Path, zip_path: Path) -> None:
    """Einen bereits veroeffentlichten Export als ZIP mit identischem Inhalt buendeln."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(export_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(export_dir))
