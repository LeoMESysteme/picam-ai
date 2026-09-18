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
from pathlib import Path
from typing import Any

import cv2

from .profiles import atomic_json

DEVICES_SCHEMA_VERSION = 1
SAMPLE_SCHEMA_VERSION = 1
EXPORT_SCHEMA_VERSION = 1

TECHNOLOGIES = ("LED", "LCD", "VFD", "other")
SPLITS = ("development", "heldout")
LABEL_STATES = ("readable", "unreadable", "uncertain", "draft")

_NAME_MAX = 120
_MODEL_MAX = 120
_NOTE_MAX = 1000
_VALUE_MAX = 64

_FAMILY_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")
_LABEL_RE = re.compile(r"^-?(\d+\.\d+|\.\d+|\d+)$")


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

    def _device_has_samples(self, device_id: str) -> bool:
        samples_dir = self.root / "samples"
        if not samples_dir.is_dir():
            return False
        for sample_dir in samples_dir.iterdir():
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                with open(sample_json, encoding="utf-8") as handle:
                    sample = json.load(handle)
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
        samples_dir = self.root / "samples"
        if not samples_dir.is_dir():
            return None
        for sample_dir in samples_dir.iterdir():
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                with open(sample_json, encoding="utf-8") as handle:
                    sample = json.load(handle)
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
                "independence_confirmation": bool(annotation.get("independence_confirmation", True)),
                "synthetic": bool(capture.get("synthetic", False)),
                "stored_at_utc": capture.get("stored_at_utc"),
                "stored_timebase": "UTC",
                "source": capture.get("source"),
                "license": capture.get("license"),
                "formatter_provisional": True,
                "metadata_revision": 0,
                "duplicate_of": duplicate_of,
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

    def _find_duplicate_hash(self, sha256: str) -> str | None:
        samples_dir = self.root / "samples"
        if not samples_dir.is_dir():
            return None
        for sample_dir in samples_dir.iterdir():
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                with open(sample_json, encoding="utf-8") as handle:
                    sample = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
            if sample.get("sha256") == sha256:
                return sample["id"]
        return None

    def _load_all_samples(self) -> list[dict]:
        samples_dir = self.root / "samples"
        if not samples_dir.is_dir():
            return []
        out = []
        for sample_dir in sorted(samples_dir.iterdir()):
            sample_json = sample_dir / "sample.json"
            if not sample_json.exists():
                continue
            try:
                with open(sample_json, encoding="utf-8") as handle:
                    out.append(json.load(handle))
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
        with open(sample_json, encoding="utf-8") as handle:
            sample = json.load(handle)
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
        groups = {s["independence_group"] for s in samples}
        readable = [s for s in samples if s["label_state"] == "readable"]
        unreadable = [s for s in samples if s["label_state"] == "unreadable"]
        uncertain = [s for s in samples if s["label_state"] in ("uncertain", "draft")]
        families = {registry["devices"][s["device_id"]]["family"] for s in samples if s["device_id"] in registry["devices"]}
        technologies = {registry["devices"][s["device_id"]]["technology"] for s in samples if s["device_id"] in registry["devices"]}
        return {
            "devices": len(registry["devices"]),
            "samples": len(samples),
            "independence_groups": len(groups),
            "readable": len(readable),
            "unreadable": len(unreadable),
            "uncertain_or_draft": len(uncertain),
            "families": sorted(families),
            "technologies": sorted(technologies),
        }

    # -- Export ------------------------------------------------------------

    def export(self) -> dict:
        with self._lock:
            return self._export_locked()

    def _export_locked(self) -> dict:
        registry = self._load_devices()
        samples = self._load_all_samples()

        by_group: dict[str, list[dict]] = {}
        for sample in samples:
            by_group.setdefault(sample["independence_group"], []).append(sample)

        included: list[dict] = []
        excluded: list[dict] = []
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
        return {
            "images": len(included),
            "independence_groups": len({s["independence_group"] for s in included}),
            "verified_devices": len(verified_devices),
            "readable": len([s for s in included if s["label_state"] == "readable"]),
            "unreadable": len([s for s in included if s["label_state"] == "unreadable"]),
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
