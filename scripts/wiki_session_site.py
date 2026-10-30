#!/usr/bin/env python3
"""Attach an optional, validated session generation to an already built wiki.

No live source access, project imports or package installation. Session errors
fall back to a previous generation or to an explicit empty state. Authentication
and deployment errors remain the responsibility of the existing deployment gate.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote

START = "<!-- SESSION-SNAPSHOT:START -->"
END = "<!-- SESSION-SNAPSHOT:END -->"
MAX_FILE = 25 * 1024 * 1024
MAX_FILES = 20_000


def read_json(path):
    if path.stat().st_size > MAX_FILE:
        raise ValueError("Metadatendatei zu groß")
    return json.loads(path.read_text(encoding="utf-8"))


def member(root: Path, name: str) -> Path:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or str(path) != name:
        raise ValueError("Ungültiger Archivpfad")
    result = root
    for part in path.parts:
        result = result / part
        if result.is_symlink():
            raise ValueError("Symlink im Archiv")
    if not result.is_file():
        raise ValueError("Archivdatei fehlt")
    return result


def validate(snapshot: Path) -> tuple[dict, set[str]]:
    root = snapshot.resolve(strict=True)
    catalog = read_json(member(root, "catalog.json"))
    if not isinstance(catalog, dict):
        raise ValueError("Katalog ist kein Objekt")
    if catalog.get("schema") != "sessions/1" or catalog.get("stats_version") != "sessions-stats/1":
        raise ValueError("Unbekanntes Archivformat")
    if not isinstance(catalog.get("runs"), list) or not isinstance(catalog.get("groups"), list):
        raise ValueError("Ungültiger Katalog")
    for group in catalog["groups"]:
        if not isinstance(group, dict) or not isinstance(group.get("id"), str):
            raise ValueError("Ungültige Vergleichsgruppe")
        for weighting in ("run_equal", "frame_weighted"):
            metrics = group.get(weighting)
            if not isinstance(metrics, dict) or not isinstance(metrics.get("shares"), dict):
                raise ValueError("Ungültige Gesamtkennzahlen")
            for value in [*metrics["shares"].values(), *[v for k, v in metrics.items() if k != "shares"]]:
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                    raise ValueError("Ungültiger Gesamtwert")
    paths = {"catalog.json"}
    ids = set()
    for run in catalog["runs"]:
        if not isinstance(run, dict) or not isinstance(run.get("id"), str) or run["id"] in ids:
            raise ValueError("Doppelte Laufkennung")
        if not isinstance(run.get("stats"), dict) or not isinstance(run.get("warnings"), list) or any(not isinstance(w, str) for w in run["warnings"]):
            raise ValueError("Ungültige Laufstatistik oder Hinweise")
        if not isinstance(run["stats"].get("counts"), dict):
            raise ValueError("Ungültige Statuszähler")
        ids.add(run["id"])
        manifest_path = run["manifest"]
        manifest = read_json(member(root, manifest_path))
        if not isinstance(manifest, dict) or manifest.get("schema") != "session-files/1" or manifest.get("id") != run["id"] or not isinstance(manifest.get("files"), list):
            raise ValueError("Manifest passt nicht zum Lauf")
        if manifest.get("files") != run.get("files"):
            raise ValueError("Dateiliste passt nicht zum Katalog")
        paths.add(manifest_path)
        for file in manifest["files"]:
            if not isinstance(file, dict) or not isinstance(file.get("name"), str) or not isinstance(file.get("parts"), list) or PurePosixPath(file["name"]).name != file["name"]:
                raise ValueError("Ungültiger Dateiname")
            raw_size = 0
            for part in file["parts"]:
                if not isinstance(part, dict):
                    raise ValueError("Ungültiger Dateiteil")
                if any(type(part.get(k)) is not int or part[k] < 0 for k in ("size", "raw_size")):
                    raise ValueError("Ungültige Dateiteilgröße")
                path = member(root, part["path"])
                if path.stat().st_size != part["size"] or part["size"] > MAX_FILE:
                    raise ValueError("Größe eines Dateiteils passt nicht")
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != part["sha256"]:
                    raise ValueError("Prüfsumme eines Dateiteils passt nicht")
                if not re.fullmatch(r"[0-9a-f]{64}", part["raw_sha256"]) or part["raw_size"] < 0:
                    raise ValueError("Ungültige Original-Prüfsumme")
                raw_size += part["raw_size"]
                paths.add(part["path"])
            if raw_size != file["size"]:
                raise ValueError("Originalgröße passt nicht")
    return catalog, paths


def esc(value):
    return html.escape(str(value if value is not None else "—"), quote=True)


def number(value, digits=2):
    if not isinstance(value, (float, int)):
        return "—"
    return f"{value:,.{digits}f}".translate(str.maketrans(",.", ".,"))


def utc_text(value):
    """ISO-Zeitstempel als „28.10.2026, 16:31 UTC“; Unlesbares bleibt sichtbar unverändert."""
    try:
        moment = datetime.fromisoformat(str(value)).astimezone(UTC)
    except (TypeError, ValueError):
        return "unbekannt" if value is None else str(value)
    return moment.strftime("%d.%m.%Y, %H:%M UTC")


def kib(value):
    return number(value / 1024, 1) + " KiB" if isinstance(value, (float, int)) else "Größe unbekannt"


def percent(value):
    return number(value * 100) + " %" if isinstance(value, (float, int)) else "—"


def static_content(catalog: dict, notice: str) -> str:
    """Real tables remain readable before JS and after a JS failure."""
    chunks = [f'<p class="session-archive-notice" role="status">{esc(notice)} '
              f'Archivstand: <time datetime="{esc(catalog.get("generated_at"))}">'
              f'{esc(utc_text(catalog.get("generated_at")))}</time>.</p>']
    if not catalog["runs"]:
        chunks.append("<p>Keine Sessions veröffentlicht. Abgeschlossene Läufe erscheinen nach einer "
                      "Exportphase mit beendeter Workbench und einem regulären Wiki-Deploy.</p>")
    else:
        chunks.append('<details class="session-source wiki-layer wiki-layer--hintergrund">'
                      '<summary>Archivkennzahlen und Dateien als Tabelle</summary><div>')
        for group in catalog["groups"]:
            kind = "Testläufe" if group.get("test_run") else "reguläre Läufe"
            # Kein h3: die Fassung steht vor dem ersten h2 der Seite.
            chunks.append(f'<p class="session-source-group">{esc(group.get("label"))} · {kind}</p>'
                          f'<p>{esc(group.get("session_count"))} Läufe · {esc(number(group.get("frames"), 0))} Frames</p>')
            chunks.append(f'<table><caption>Kennzahlen: {esc(group.get("label"))} · {kind}</caption>'
                          '<thead><tr><th scope="col">Kennzahl</th><th scope="col">Jeder Lauf zählt gleich</th>'
                          '<th scope="col">Alle Frames gemeinsam</th></tr></thead><tbody>')
            a, b = group["run_equal"], group["frame_weighted"]
            rows = []
            for status in ("valid", "transition", "unreadable", "stale"):
                default = 0 if group.get("frames") else None
                rows.append((status.upper() + ", Frameanteil", percent(a["shares"].get(status, default)),
                             percent(b["shares"].get(status, default))))
            rows.extend([
                ("Verarbeitung Median / p95 (ms); links Median der Session-Quantile",
                 number(a.get("processing_median_ms")) + " / " + number(a.get("processing_p95_ms")),
                 number(b.get("processing_median_ms")) + " / " + number(b.get("processing_p95_ms"))),
                ("Konfidenzmedian (VALID); links Median der Session-Mediane", percent(a.get("confidence_median")), percent(b.get("confidence_median"))),
                ("Leserate (Hz)", number(a.get("rate_hz")), number(b.get("rate_hz"))),
                ("Trackingverluste / 1.000 Frames", number(a.get("tracking_per_1000")), number(b.get("tracking_per_1000"))),
            ])
            for label, left, right in rows:
                chunks.append(f'<tr><th scope="row">{esc(label)}</th><td>{esc(left)}</td><td>{esc(right)}</td></tr>')
            chunks.append("</tbody></table>")
        # Eine Spalte je Kennzahl, damit die Werte nicht in einer schmalen Zelle umbrechen.
        chunks.append('<div class="session-source-scroll" tabindex="0" role="region" aria-label="Läufe und Dateien, waagerecht scrollbar">'
                      '<table class="session-source-runs"><caption>Läufe und Dateien; Status in % als VALID / TRANSITION / UNREADABLE / STALE</caption><thead><tr>'
                      '<th scope="col">Lauf, Start (UTC), Gerät</th><th scope="col">Frames</th>'
                      '<th scope="col">Status in %<br>V / T / U / S</th>'
                      '<th scope="col">Verarbeitung in ms<br>Median / p95</th><th scope="col">Leserate in Hz</th>'
                      '<th scope="col">Konfidenzmedian VALID</th><th scope="col">Messwertmedian VALID</th>'
                      '<th scope="col">Hinweise</th><th scope="col">Dateien</th></tr></thead><tbody>')
        for run in catalog["runs"]:
            query = quote(run["id"], safe="")
            files = []
            for file in run["files"]:
                links = " ".join(f'<a href="../assets/sessions/{quote(part["path"], safe="/")}" download>'
                                 f'Teil {i + 1}</a>' for i, part in enumerate(file["parts"]))
                files.append(f'<li>{esc(file["name"])} ({esc(kib(file["size"]))}): {links}</li>')
            warnings = (["Testlauf – nicht für Messungen verwenden"] if run.get("test_run") else []) + run.get("warnings", [])
            stats = run["stats"]
            proc = stats.get("processing_ms") or {}
            conf = stats.get("confidence") or {}
            value = stats.get("value") or {}
            frames = stats.get("frames") or 0
            counts = stats.get("counts") or {}
            shares = " / ".join(number(counts.get(status, 0) / frames * 100, 1) if frames else "—"
                                for status in ("valid", "transition", "unreadable", "stale"))
            measured = number(value.get("median"), 6)
            cells = [esc(number(frames, 0)), esc(shares), f'{number(proc.get("median"))} / {number(proc.get("p95"))}',
                     esc(number(stats.get("rate_hz"))), esc(percent(conf.get("median"))),
                     esc(measured + (" " + run["unit"] if measured != "—" and run.get("unit") else ""))]
            chunks.append(f'<tr><th scope="row" class="session-source-run"><a href="../assets/records-explorer/index.html?a={query}" target="_blank" '
                          f'rel="noopener">{esc(run["id"])}</a><br>{esc(utc_text(run.get("started_at_utc")))}<br>{esc(run.get("device_id"))}</th>'
                          + "".join(f"<td>{cell}</td>" for cell in cells) +
                          f'<td>{esc(" · ".join(warnings))}</td><td><ul>{"".join(files)}</ul>'
                          f'<a href="../assets/sessions/{quote(run["manifest"], safe="/")}">Manifest</a></td></tr>')
        chunks.append("</tbody></table></div></div></details>")
    for error in catalog.get("errors", []):
        chunks.append(f'<p>Archivhinweis: {esc(error)}</p>')
    return "\n".join(chunks)


def attach(site: Path, candidates: list[Path], *, max_files=MAX_FILES, max_file=MAX_FILE, update_notice="") -> dict:
    page = site / "docs/session-explorer.html"
    if not page.is_file():
        return {"attached": False, "error": "Session-Seite fehlt im Build"}
    original = page.read_text(encoding="utf-8")
    if START not in original or END not in original:
        return {"attached": False, "error": "Session-Platzhalter fehlt"}
    target = site / "assets/sessions"
    existing = [p for p in site.rglob("*") if p.is_file() and not p.is_relative_to(target)]
    issues = []
    chosen = None
    paths = set()
    catalog = {"schema": "sessions/1", "stats_version": "sessions-stats/1", "generated_at": None,
               "runs": [], "groups": [], "errors": []}
    for snapshot in dict.fromkeys(candidates):
        try:
            candidate, files = validate(snapshot)
            if len(existing) + len(files) > max_files:
                raise ValueError("Dateianzahl von Website und Archiv überschreitet Hosting-Grenze")
            if any(member(snapshot, name).stat().st_size > max_file for name in files):
                raise ValueError("Archivdatei überschreitet Hosting-Grenze")
            # Validate the static fallback before any built files are changed.
            static_content(candidate, "Geprüfter Archivstand.")
            catalog, paths, chosen = candidate, files, snapshot
            break
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError) as error:
            issues.append(str(error))
    assets = site / "assets"
    assets.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".sessions-", dir=assets))
    try:
        if chosen:
            try:
                for name in sorted(paths):
                    destination = stage / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(member(chosen, name), destination)
            except (OSError, ValueError) as error:
                # Generation verschwand beim Kopieren: echter Leerzustand statt halber Seite.
                issues.append(str(error))
                shutil.rmtree(stage)
                stage.mkdir()
                chosen = None
                catalog = {"schema": "sessions/1", "stats_version": "sessions-stats/1", "generated_at": None,
                           "runs": [], "groups": [], "errors": []}
        if not chosen:
            (stage / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    notice = "Geprüfter Archivstand. Neue Läufe werden ausschließlich bei beendeter Workbench übernommen."
    if issues:
        notice = "Aktualisierung zurückgestellt; bisheriger Archivstand oder Leerzustand. " + "; ".join(issues)
    if update_notice:
        notice += " " + update_notice
    content = static_content(catalog, notice)
    before, remainder = original.split(START, 1)
    _, after = remainder.split(END, 1)
    page.write_text(before + START + "\n" + content + "\n" + END + after, encoding="utf-8")
    return {"attached": chosen is not None, "snapshot": str(chosen) if chosen else None, "issues": issues}


REQUEST = Path("/var/lib/forgejo-runner/wiki-export-request")


def select_snapshots(root: Path, state: Path, wait_s=15, report=None, request: Path = REQUEST) -> list[Path]:
    """Request a fixed exporter operation; never send commands or source paths.

    The request lives in the runner's only writable directory (its systemd unit
    has ProtectSystem=strict). picam-wiki-export.path watches it; the content
    is never read. A failed write is reported, not swallowed.
    """
    pointer = root / "archive/current"

    def current():
        try:
            generation = pointer.read_text(encoding="ascii").strip()
            if not re.fullmatch(r"generation-[0-9a-f]{32}", generation):
                return None
            path = (root / "archive/snapshots" / generation).resolve(strict=True)
            if not path.is_relative_to((root / "archive/snapshots").resolve()):
                return None
            if not (path / "published").is_file() or (path / "published").is_symlink():
                return None
            return path
        except OSError:
            return None

    before = current()
    request_error = None
    try:
        with request.open("wb") as stream:
            stream.write(b"export\n")
    except OSError as error:
        request_error = f"Exportanfrage {request} nicht geschrieben: {error.strerror or error}"
    if request_error is None:
        # Waiting is bounded even if the export service is absent or busy.
        deadline = time.monotonic() + min(15, max(0, wait_s))
        while time.monotonic() < deadline:
            if current() != before:
                break
            time.sleep(min(.25, max(0, deadline - time.monotonic())))
    after = current()
    if report is not None:
        report["update_notice"] = "" if after and after != before else "Keine neue Archivgeneration im Wartefenster; eine zurückgestellte Aktualisierung verändert den angezeigten Stand nicht."
        report["request_error"] = request_error
    candidates = [path for path in [after, before] if path]
    try:
        previous = Path(read_json(state)["snapshot"]).resolve(strict=True)
        if previous.is_relative_to((root / "archive/snapshots").resolve()):
            candidates.append(previous)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return list(dict.fromkeys(candidates))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--export-root", type=Path, default=Path("/srv/picam-wiki-export"))
    parser.add_argument("--state", type=Path, default=Path("/var/lib/forgejo-runner/wiki-session-state.json"))
    parser.add_argument("--request", type=Path, default=REQUEST, help="Feste Anfragedatei; Inhalt wird nicht ausgewertet")
    parser.add_argument("--wait", type=float, default=15)
    parser.add_argument("--snapshot", type=Path, help="Explizite Generation, z. B. Integrationsfixture; keine Exportanfrage")
    args = parser.parse_args()
    try:
        report = {}
        snapshots = ([args.snapshot] if args.snapshot
                     else select_snapshots(args.export_root, args.state, args.wait, report, args.request))
        result = attach(args.site, snapshots, update_notice=report.get("update_notice", ""))
        if report.get("request_error"):
            result["request_error"] = report["request_error"]
        if result.get("snapshot") and not args.snapshot:
            args.state.parent.mkdir(parents=True, exist_ok=True)
            temp = args.state.with_suffix(".tmp")
            temp.write_text(json.dumps({"snapshot": result["snapshot"]}), encoding="utf-8")
            os.replace(temp, args.state)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError) as error:
        # Optional session data never becomes a new prerequisite for doc CI.
        print(json.dumps({"attached": False, "error": str(error)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
