"""Sensor-Marktplatz: Katalog lesen, Pakete installieren, einreichen.

Experimentell und hinter dem Schalter `[features] sensor_assistant` (siehe `features`). Der Katalog ist
der Git-Zweig `sensor-katalog` des Spiegel-Repos (nur Lesen, ohne Anmeldung). Einreichungen gehen als
Issue mit Paketanhang an das Firmen-Forgejo; eine CI prueft sie und schreibt in den Zweig. Das Netz wird
nie im Messpfad benutzt. Alle HTTP-Aufrufe nehmen `opener` entgegen (Tests), Standard ist ein urllib-Opener
ohne Weiterleitungen, damit ein Token nie an einen anderen Host geht. Das Token wird nie protokolliert
und steht in keiner Meldung.
"""

from __future__ import annotations

import fcntl
import gzip
import hashlib
import io
import json
import os
import re
import secrets
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from . import (
    bundled_sensors,
    load_definition,
    local_root,
    registry_with_errors,
    templates,
)

CATALOG_RAW_BASE = "https://raw.githubusercontent.com/LeoMESysteme/picam-ai/sensor-katalog/"
FORGEJO_BASE = "https://ds1515.me-systeme.de"
FORGEJO_REPO = "l.hentschke/picam-ai"
SUBMISSION_LABEL = "sensor-einreichung"

MAX_INDEX_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_BUNDLE_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 5000
BUNDLE_FILES = ("sensor.json", "display.json", "templates.json", "README.md")
REQUIRED_FILES = ("sensor.json", "display.json", "templates.json")
_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,62}")
_SHA = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{16,128}")
_ENTRY_KEYS = {"id", "version", "status", "display_name", "manufacturer", "aliases", "unit", "family",
               "polarity", "example", "files", "submitted", "checks"}
#: Optionale Felder: aeltere Indizes ohne sie bleiben gueltig.
_OPTIONAL_ENTRY_KEYS = {"connection"}
CONNECTIONS = ("rs232", "usb", "none", "unknown")
UNREACHABLE = ("Forgejo ist nur im Firmennetz oder über Tailscale erreichbar. "
               "Das Paket liegt im Ausgang; „Ausstehende senden“ versucht es erneut.")


class CatalogUnreachable(ValueError):
    """Katalog oder Forgejo nicht erreichbar (Netz, Zeitlimit, DNS)."""


class HttpStatus(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ----------------------------------------------------------------- Orte und Hilfen
def catalog_dir(instance) -> Path:
    """Ablage neben den Sensorpaketen: <Datenstamm>/sensor-catalog."""
    return local_root(instance).parent / "sensor-catalog"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _check_id(sensor_id) -> str:
    if not isinstance(sensor_id, str) or not _ID.fullmatch(sensor_id):
        raise ValueError(f"Ungültige Sensor-id {sensor_id!r}")
    return sensor_id


def _clean(text, limit=120) -> str:
    return "".join(ch if ch.isprintable() else " " for ch in str(text)).strip()[:limit]


def _default_opener():
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    return urllib.request.build_opener(NoRedirect).open


def _http(req: urllib.request.Request, *, timeout, limit, opener=None) -> bytes:
    if not req.full_url.startswith("https://"):
        raise ValueError("Nur HTTPS-Adressen sind erlaubt")
    opener = opener or _default_opener()
    try:
        with opener(req, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            data = response.read(limit + 1)
    except urllib.error.HTTPError as error:
        raise HttpStatus(error.code, f"HTTP {error.code}") from None
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise CatalogUnreachable(f"Katalog nicht erreichbar: {type(error).__name__}") from None
    if status not in (200, 201):
        raise HttpStatus(status, f"HTTP {status}")
    if len(data) > limit:
        raise ValueError(f"Antwort größer als {limit} Bytes")
    return data


def _get(url, *, timeout, limit, opener=None, token=None) -> bytes:
    headers = {"User-Agent": "picam-sensor-catalog", "Accept": "*/*"}
    if token:
        headers["Authorization"] = f"token {token}"
    return _http(urllib.request.Request(url, headers=headers), timeout=timeout, limit=limit, opener=opener)


# ----------------------------------------------------------------- Index
def _text_field(value, name, *, limit=200, empty=False):
    if (not isinstance(value, str) or (not empty and not value.strip()) or len(value) > limit
            or any(not ch.isprintable() for ch in value)):
        raise ValueError(f"Index: {name} ungültig")
    return value


def validate_index(data) -> dict:
    """Strenge Schemaprüfung von sensors/index.json; wirft ValueError."""
    if not isinstance(data, dict) or data.keys() != {"schema", "generated", "sensors"}:
        raise ValueError("Index: unerwartete Schlüssel")
    if type(data["schema"]) is not int or data["schema"] != 1:
        raise ValueError("Index: Schema wird nicht unterstützt")
    _text_field(data["generated"], "generated", limit=40)
    entries = data["sensors"]
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValueError("Index: sensors muss eine Liste sein")
    seen = set()
    for entry in entries:
        if (not isinstance(entry, dict) or not _ENTRY_KEYS <= entry.keys()
                or not entry.keys() <= _ENTRY_KEYS | _OPTIONAL_ENTRY_KEYS):
            raise ValueError("Index: Eintrag mit unerwarteten Schlüsseln")
        if entry.get("connection", "unknown") not in CONNECTIONS:
            raise ValueError("Index: connection ungültig")
        _check_id(entry["id"])
        if entry["id"] in seen:
            raise ValueError(f"Index: doppelte id {entry['id']}")
        seen.add(entry["id"])
        if type(entry["version"]) is not int or entry["version"] < 1:
            raise ValueError("Index: version ungültig")
        if entry["status"] not in ("provisional", "verified"):
            raise ValueError("Index: status ungültig")
        for key in ("display_name", "manufacturer", "unit", "family", "polarity"):
            _text_field(entry[key], key)
        _text_field(entry["example"], "example", limit=16, empty=True)
        _text_field(entry["submitted"], "submitted", limit=40)
        aliases = entry["aliases"]
        if not isinstance(aliases, list) or len(aliases) > 20:
            raise ValueError("Index: aliases ungültig")
        for alias in aliases:
            _text_field(alias, "alias")
        files = entry["files"]
        if (not isinstance(files, dict) or not set(REQUIRED_FILES) <= files.keys()
                or not files.keys() <= set(BUNDLE_FILES)):
            raise ValueError("Index: files ungültig")
        if any(not isinstance(value, str) or not _SHA.fullmatch(value) for value in files.values()):
            raise ValueError("Index: Prüfsumme ungültig")
        checks = entry["checks"]
        if (not isinstance(checks, dict) or checks.keys() != {"runs"} or type(checks["runs"]) is not int
                or checks["runs"] < 0):
            raise ValueError("Index: checks ungültig")
    return data


def preview_example(definition) -> str:
    """Formatvorschau (hoechstens 16 Zeichen) aus den Rollen der Anzeige, wenn kein Beispiel gespeichert ist.

    Beispiel GSV-2AS: `+ 0.00000 mV/V` (vorzeichen, Zahlenblock mit Nullen, Einheit in den Einheitszellen).
    """
    display = definition.display
    cells = [" "] * display.cells
    roles, fmt = display.roles, display.format
    if roles.sign and fmt.sign_chars:
        cells[roles.sign[0]] = fmt.sign_chars[0]
    digits = "0" * fmt.digits
    number = digits if fmt.decimal != "point" else "0." + "0" * (fmt.digits - 1)
    for offset, char in enumerate(number[: len(roles.number)]):
        cells[roles.number[offset]] = char
    for position, char in zip(roles.unit, definition.unit, strict=False):
        cells[position] = char
    return "".join(cells).rstrip()[:16]


def _parse_index(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise ValueError(f"Index nicht lesbar: {error}") from None
    return validate_index(data)


def fetch_index(instance, *, timeout=10, opener=None) -> dict:
    """Index vom Katalogzweig holen, prüfen und als Cache ablegen."""
    raw = _get(CATALOG_RAW_BASE + "sensors/index.json", timeout=timeout, limit=MAX_INDEX_BYTES, opener=opener)
    data = _parse_index(raw)
    _atomic_write(catalog_dir(instance) / "index.json", raw)
    return data


def cached_index(instance) -> dict | None:
    path = catalog_dir(instance) / "index.json"
    try:
        if not path.is_file() or path.stat().st_size > MAX_INDEX_BYTES:
            return None
        return _parse_index(path.read_bytes())
    except (OSError, ValueError):
        return None


def search(entries, text) -> list:
    """Alle Wörter müssen in Name, Hersteller, Alias, Kennung oder Einheit vorkommen; leer = alle."""
    words = (text or "").casefold().split()
    result = []
    for entry in entries:
        haystack = " ".join([str(entry.get(key, "")) for key in ("display_name", "manufacturer", "id", "unit")]
                            + [str(alias) for alias in entry.get("aliases", ())]).casefold()
        if all(word in haystack for word in words):
            result.append(entry)
    return result


# ----------------------------------------------------------------- Herkunft
def _ledger_path(instance) -> Path:
    return catalog_dir(instance) / "installed.json"


def installed(instance) -> dict:
    """Aus dem Marktplatz installierte Pakete: id -> {version, pulled, files}."""
    try:
        data = json.loads(_ledger_path(instance).read_text(encoding="utf-8"))
        sensors = data["sensors"]
        return sensors if isinstance(sensors, dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def _record_install(instance, sensor_id, entry) -> None:
    sensors = installed(instance)
    sensors[sensor_id] = {"version": entry["version"], "pulled": _now(), "catalog_status": entry["status"],
                          "files": entry["files"]}
    payload = {"schema": 1, "sensors": sensors}
    _atomic_write(_ledger_path(instance), (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode())


# ----------------------------------------------------------------- Installieren
def _names(definition):
    return {definition.id, *definition.aliases}


def pull(instance, sensor_id, *, overwrite=False, timeout=15, opener=None) -> dict:
    """Katalogpaket laden, prüfen und lokal als vorläufig installieren."""
    _check_id(sensor_id)
    try:
        index = fetch_index(instance, opener=opener, timeout=timeout)
    except CatalogUnreachable:
        index = cached_index(instance)
        if index is None:
            raise
    entry = next((item for item in index["sensors"] if item["id"] == sensor_id), None)
    if entry is None:
        raise ValueError(f"Sensor {sensor_id!r} steht nicht im Katalog")
    root = local_root(instance)
    root.mkdir(parents=True, exist_ok=True)
    existing, _ = registry_with_errors(instance=instance)
    target = root / sensor_id
    current = existing.get(sensor_id)
    if current is not None and current.directory.parent != root:
        raise ValueError(f"{sensor_id} ist ein mitgeliefertes Paket und wird nicht ersetzt")
    if (target.exists() or target.is_symlink()) and not overwrite:
        raise ValueError(f"Sensor-id bereits vorhanden: {sensor_id} (zum Ersetzen --overwrite)")
    with (root / ".pakete.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(dir=root, prefix=".katalog-") as tmp:
            staged = Path(tmp) / sensor_id
            staged.mkdir(mode=0o755)
            for name, digest in entry["files"].items():
                data = _get(f"{CATALOG_RAW_BASE}sensors/{sensor_id}/{name}", timeout=timeout,
                            limit=MAX_FILE_BYTES, opener=opener)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError(f"Prüfsumme von {name} stimmt nicht mit dem Index überein")
                (staged / name).write_bytes(data)
            definition = load_definition(staged)
            templates(definition)
            if definition.id != sensor_id or definition.version != entry["version"]:
                raise ValueError("Paket passt nicht zum Indexeintrag (id oder Version)")
            if definition.templates.file != "templates.json":
                raise ValueError("templates.file muss templates.json heißen")
            for other in existing.values():
                if other.id != sensor_id and _names(definition) & _names(other):
                    raise ValueError(f"Name oder Alias kollidiert mit Sensor {other.id}")
            if definition.status != "provisional":
                # Verifizierte Pakete kommen per Release, nie aus dem Katalog.
                raw = json.loads((staged / "sensor.json").read_text(encoding="utf-8"))
                raw["status"] = "provisional"
                (staged / "sensor.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
                definition = load_definition(staged)
            backup = Path(tmp) / "alt"
            if target.exists() or target.is_symlink():
                if target.is_symlink():
                    raise ValueError("Symlink als Paketverzeichnis unzulässig")
                target.rename(backup)
            try:
                staged.rename(target)
            except OSError:
                if backup.exists():
                    backup.rename(target)
                raise
    _record_install(instance, sensor_id, entry)
    return {"sensor_id": sensor_id, "directory": str(target), "status": "provisional"}


# ----------------------------------------------------------------- Bundle
def bundle(instance, sensor_id) -> Path:
    """Lokales vorläufiges Paket als deterministisches tar.gz (nur erlaubte Dateien)."""
    _check_id(sensor_id)
    root = local_root(instance)
    directory = root / sensor_id
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError(f"Kein lokales Sensorpaket {sensor_id!r}")
    definition = load_definition(directory)
    if definition.status != "provisional":
        raise ValueError("Nur vorläufige Pakete können eingereicht werden")
    members = []
    total = 0
    for name in BUNDLE_FILES:
        path = directory / name
        if not path.exists() and name == "README.md":
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"{name} fehlt oder ist kein regulärer Dateiname")
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"{name} ist größer als {MAX_FILE_BYTES} Bytes")
        total += len(data)
        members.append((name, data))
    out = catalog_dir(instance) / "bundles" / f"{sensor_id}-v{definition.version}.tar.gz"
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data in members:
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.mode = len(data), 0, 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    blob = raw.getvalue()
    if len(blob) > MAX_BUNDLE_BYTES or total > MAX_BUNDLE_BYTES:
        raise ValueError("Paket ist größer als 4 MiB")
    _atomic_write(out, blob)
    result = check_bundle(out)
    if not result["ok"]:
        out.unlink(missing_ok=True)
        raise ValueError("Paket besteht die Prüfung nicht: " + "; ".join(result["errors"]))
    return out


class _Limited(io.RawIOBase):
    """Begrenzt die entpackte Datenmenge (Schutz vor Dekompressionsbomben)."""

    def __init__(self, stream, limit):
        self.stream, self.left = stream, limit

    def readable(self):
        return True

    def readinto(self, buffer):
        data = self.stream.read(len(buffer))
        self.left -= len(data)
        if self.left < 0:
            raise ValueError("Archiv entpackt größer als erlaubt")
        buffer[:len(data)] = data
        return len(data)


def _unpack(path: Path, dest: Path) -> list[str]:
    """Sichere Entpackung: nur reguläre Dateien mit erlaubten Namen, je ≤ 4 MiB."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Paketdatei fehlt")
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("Archiv ist größer als 4 MiB")
    names = []
    with gzip.open(path, "rb") as zipped:
        limited = io.BufferedReader(_Limited(zipped, len(BUNDLE_FILES) * MAX_FILE_BYTES + 65536))
        with tarfile.open(fileobj=limited, mode="r|") as archive:
            for member in archive:
                if member.name not in BUNDLE_FILES:
                    raise ValueError(f"Unerlaubter Eintrag im Archiv: {_clean(member.name, 60)!r}")
                if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
                    raise ValueError(f"{member.name} ist keine reguläre Datei (Links sind verboten)")
                if member.name in names:
                    raise ValueError(f"{member.name} kommt doppelt vor")
                if member.size > MAX_FILE_BYTES:
                    raise ValueError(f"{member.name} ist größer als {MAX_FILE_BYTES} Bytes")
                data = archive.extractfile(member).read(MAX_FILE_BYTES + 1)
                if len(data) != member.size:
                    raise ValueError(f"{member.name}: Größe passt nicht")
                (dest / member.name).write_bytes(data)
                names.append(member.name)
    return names


def check_bundle(path, *, index=None) -> dict:
    """Prüft ein Einreichungspaket ohne etwas zu installieren; wirft nie."""
    result = {"ok": False, "sensor_id": None, "version": None, "display_name": None, "errors": []}
    errors = result["errors"]
    try:
        with tempfile.TemporaryDirectory(prefix="picam-bundle-") as tmp:
            raw_dir = Path(tmp) / "raw"
            raw_dir.mkdir()
            names = _unpack(Path(path), raw_dir)
            missing = [name for name in REQUIRED_FILES if name not in names]
            if missing:
                raise ValueError("Dateien fehlen: " + ", ".join(missing))
            try:
                sensor_id = json.loads((raw_dir / "sensor.json").read_text(encoding="utf-8")).get("id")
            except (ValueError, AttributeError):
                raise ValueError("sensor.json nicht lesbar") from None
            _check_id(sensor_id)
            result["sensor_id"] = sensor_id
            staged = Path(tmp) / sensor_id
            raw_dir.rename(staged)
            readme = staged / "README.md"
            if readme.exists():
                try:
                    if "\x00" in readme.read_text(encoding="utf-8"):
                        raise ValueError
                except ValueError:
                    raise ValueError("README.md ist kein Text") from None
            definition = load_definition(staged)
            result.update(version=definition.version, display_name=definition.display_name)
            if definition.templates.file != "templates.json":
                raise ValueError("templates.file muss templates.json heißen")
            templates(definition)  # prüft die Vorlagen-Prüfsumme
            if definition.status != "provisional":
                raise ValueError("Eingereichte Pakete müssen status provisional haben")
            for known in bundled_sensors():
                if _names(definition) & _names(known):
                    raise ValueError(f"Kennung oder Alias gehört zum mitgelieferten Sensor {known.id}")
            if index is not None:
                old = next((item for item in index.get("sensors", ()) if item.get("id") == sensor_id), None)
                if old is not None and old.get("status") == "verified":
                    raise ValueError("Verifizierte Katalogeinträge werden nur über ein Review geändert")
                if old is not None and definition.version <= old["version"]:
                    raise ValueError(f"Version {definition.version} ist nicht höher als die Katalogversion "
                                     f"{old['version']}")
    except (ValueError, OSError, EOFError, tarfile.TarError, KeyError) as error:
        errors.append(str(error) or type(error).__name__)
    result["ok"] = not errors
    return result


# ----------------------------------------------------------------- Token
def _token_path(instance) -> Path:
    return catalog_dir(instance) / "forgejo-token"


def _read_token(instance) -> str | None:
    try:
        token = _token_path(instance).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token if _TOKEN.fullmatch(token) else None


def token_status(instance) -> dict:
    return {"present": _read_token(instance) is not None, "path": str(_token_path(instance))}


def save_token(instance, token, *, timeout=10, opener=None) -> dict:
    token = (token or "").strip()
    if not _TOKEN.fullmatch(token):
        raise ValueError("Token hat ein ungültiges Format")
    # Geprüft wird über die Repo-Labels (Scope issue): Tokens, die auf ein Repository beschränkt sind,
    # dürfen in Forgejo keinen user-Scope haben.
    try:
        raw = _get(_api("/labels?limit=100"), timeout=timeout, limit=MAX_INDEX_BYTES, opener=opener,
                   token=token)
    except HttpStatus as error:
        if error.status in (401, 403):
            raise ValueError("Forgejo lehnt das Token ab (ungültig oder abgelaufen)") from None
        raise ValueError(f"Forgejo meldet {error}") from None
    except CatalogUnreachable:
        raise CatalogUnreachable("Forgejo ist nur im Firmennetz oder über Tailscale erreichbar; "
                                 "das Token wurde nicht gespeichert.") from None
    try:
        names = {item.get("name") for item in json.loads(raw) if isinstance(item, dict)}
    except (ValueError, TypeError):
        names = set()
    _atomic_write(_token_path(instance), (token + "\n").encode(), mode=0o600)
    return {"ok": True, "label_present": SUBMISSION_LABEL in names}


def delete_token(instance) -> dict:
    path = _token_path(instance)
    existed = path.exists()
    path.unlink(missing_ok=True)
    return {"deleted": existed}


# ----------------------------------------------------------------- Einreichen
def _outbox(instance) -> Path:
    return catalog_dir(instance) / "outbox"


def _api(path):
    return f"{FORGEJO_BASE}/api/v1/repos/{FORGEJO_REPO}{path}"


def _call(method, url, token, *, body=None, content_type=None, timeout=15, opener=None):
    headers = {"User-Agent": "picam-sensor-catalog", "Authorization": f"token {token}",
               "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        raw = _http(req, timeout=timeout, limit=MAX_INDEX_BYTES, opener=opener)
    except HttpStatus as error:
        if error.status in (401, 403):
            raise ValueError("Forgejo lehnt das Token ab. Token neu eintragen.") from None
        if error.status == 404:
            raise ValueError("Forgejo: Repository oder Ressource nicht gefunden (Token ohne Zugriff?)") from None
        raise ValueError(f"Forgejo meldet {error}") from None
    except CatalogUnreachable:
        raise CatalogUnreachable(UNREACHABLE) from None
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        raise ValueError("Forgejo antwortet nicht mit JSON") from None


def _json_call(method, path, token, payload, **options):
    return _call(method, _api(path), token, body=json.dumps(payload).encode(),
                 content_type="application/json", **options)


def _multipart(filename, data):
    boundary = "picam" + secrets.token_hex(16)
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"attachment\"; "
            f"filename=\"{filename}\"\r\nContent-Type: application/gzip\r\n\r\n").encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def _issue_body(meta) -> str:
    return "\n".join([
        f"Einreichung eines Sensorpakets aus picam (Version {meta['version']}).", "",
        f"* Name: {meta['display_name']}", f"* Kennung: {meta['sensor_id']}",
        f"* Hersteller: {meta['manufacturer']}", f"* Einheit: {meta['unit']}",
        f"* Archiv-SHA256: {meta['sha256']}", "",
        "Das Paket (Format, Vorlagen, keine Bilder) hängt als Archiv an. Der Bediener hat der "
        f"Veröffentlichung im öffentlichen Katalog zugestimmt ({meta['consent_at']}). Die Prüfung läuft automatisch.",
    ])


def _label_id(token, **options) -> int:
    labels = _call("GET", _api("/labels?limit=100"), token, **options)
    for label in labels or ():
        if isinstance(label, dict) and label.get("name") == SUBMISSION_LABEL and type(label.get("id")) is int:
            return label["id"]
    raise ValueError(f"Label {SUBMISSION_LABEL!r} fehlt im Forgejo-Repository")


def _save_meta(path, meta):
    _atomic_write(path, (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode(), mode=0o600)


def _send(meta_path: Path, token, *, timeout=15, opener=None) -> dict:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("consent") is not True:
        raise ValueError("Einwilligung fehlt im Ausgang")
    archive = meta_path.with_suffix(".tar.gz")
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != meta["sha256"]:
        raise ValueError("Ausgang beschädigt: Prüfsumme stimmt nicht")
    options = {"timeout": timeout, "opener": opener}
    label = _label_id(token, **options)
    if not meta.get("issue_number"):
        issue = _json_call("POST", "/issues", token, {
            "title": f"Sensor-Einreichung: {_clean(meta['display_name'], 80)} ({meta['sensor_id']})",
            "body": _issue_body(meta)}, **options)
        if not isinstance(issue, dict) or type(issue.get("number")) is not int:
            raise ValueError("Forgejo lieferte keine Issue-Nummer")
        meta["issue_number"] = issue["number"]
        _save_meta(meta_path, meta)
    number = meta["issue_number"]
    if not meta.get("asset_done"):
        filename = f"{meta['sensor_id']}-v{meta['version']}.tar.gz"
        body, content_type = _multipart(filename, data)
        _call("POST", _api(f"/issues/{number}/assets?name={urllib.parse.quote(filename)}"), token,
              body=body, content_type=content_type, **options)
        meta["asset_done"] = True
        _save_meta(meta_path, meta)
    # Das Label zuletzt: erst jetzt startet die CI, und der Anhang ist schon da.
    _json_call("POST", f"/issues/{number}/labels", token, {"labels": [label]}, **options)
    archive.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)
    return {"sensor_id": meta["sensor_id"], "issue_number": number,
            "issue_url": f"{FORGEJO_BASE}/{FORGEJO_REPO}/issues/{number}"}


def submit(instance, sensor_id, *, consent: bool, timeout=15, opener=None) -> dict:
    """Lokales vorläufiges Paket als Issue mit Anhang einreichen. Einwilligung ist Pflicht."""
    if consent is not True:
        raise ValueError("Einwilligung fehlt: Paketdateien werden öffentlich im Katalog sichtbar")
    token = _read_token(instance)
    if token is None:
        raise ValueError("Kein Forgejo-Token gespeichert (picam sensor catalog token set)")
    archive = bundle(instance, sensor_id)
    definition = load_definition(local_root(instance) / sensor_id)
    outbox = _outbox(instance)
    outbox.mkdir(parents=True, exist_ok=True)
    blob = archive.read_bytes()
    stem = f"{sensor_id}-v{definition.version}"
    meta_path = outbox / f"{stem}.json"
    _atomic_write(outbox / f"{stem}.tar.gz", blob, mode=0o600)
    meta = {"schema": 1, "sensor_id": sensor_id, "version": definition.version,
            "display_name": _clean(definition.display_name), "manufacturer": _clean(definition.manufacturer),
            "unit": _clean(definition.unit), "sha256": hashlib.sha256(blob).hexdigest(),
            "consent": True, "consent_at": _now(), "created": _now()}
    if meta_path.is_file():  # gleicher Stand schon im Ausgang: Fortschritt behalten, kein zweites Issue
        try:
            old = json.loads(meta_path.read_text(encoding="utf-8"))
            if old.get("sha256") == meta["sha256"]:
                meta = {**meta, **{key: old[key] for key in ("issue_number", "asset_done") if key in old}}
        except (OSError, ValueError):
            pass
    _save_meta(meta_path, meta)
    return _send(meta_path, token, timeout=timeout, opener=opener)


def pending(instance) -> list:
    result = []
    for path in sorted(_outbox(instance).glob("*.json")):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            result.append({"sensor_id": meta["sensor_id"], "version": meta["version"],
                           "created": meta.get("created"), "issue_number": meta.get("issue_number")})
        except (OSError, ValueError, KeyError):
            continue
    return result


def submit_pending(instance, *, timeout=15, opener=None) -> list:
    """Ausgang erneut senden; je Eintrag ein Ergebnis (ok oder error)."""
    results = []
    token = _read_token(instance)
    for path in sorted(_outbox(instance).glob("*.json")):
        try:
            if token is None:
                raise ValueError("Kein Forgejo-Token gespeichert")
            results.append({"ok": True, **_send(path, token, timeout=timeout, opener=opener)})
        except CatalogUnreachable as error:
            results.append({"ok": False, "sensor_id": path.stem, "error": str(error)})
            break
        except (ValueError, OSError, KeyError) as error:
            results.append({"ok": False, "sensor_id": path.stem, "error": str(error)})
    return results
