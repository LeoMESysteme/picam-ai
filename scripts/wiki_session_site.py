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
    return f"{value:.{digits}f}".replace(".", ",") if isinstance(value, (float, int)) else "—"


def percent(value):
    return number(value * 100) + " %" if isinstance(value, (float, int)) else "—"


def static_content(catalog: dict, notice: str) -> str:
    """Real tables remain readable before JS and after a JS failure."""
    chunks = [f'<p class="session-archive-notice" role="status">{esc(notice)} '
              f'Archivstand (UTC): <time>{esc(catalog.get("generated_at"))}</time>.</p>']
    if not catalog["runs"]:
        chunks.append("<p>Keine Sessions veröffentlicht. Abgeschlossene Läufe erscheinen nach einer "
                      "Exportphase mit beendeter Workbench und einem regulären Wiki-Deploy.</p>")
    else:
        chunks.append('<details class="session-source"><summary>Archivkennzahlen und Dateien als Tabelle</summary>')
        for group in catalog["groups"]:
            kind = "Testläufe" if group.get("test_run") else "reguläre Läufe"
            chunks.append(f'<h3>{esc(group.get("label"))} · {kind}</h3><p>{esc(group.get("session_count"))} '
                          f'Läufe · {esc(group.get("frames"))} Frames</p>')
            chunks.append("<table><thead><tr><th>Kennzahl</th><th>Jeder Lauf zählt gleich</th>"
                          "<th>Alle Frames gemeinsam</th></tr></thead><tbody>")
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
                chunks.append(f'<tr><th>{esc(label)}</th><td>{esc(left)}</td><td>{esc(right)}</td></tr>')
            chunks.append("</tbody></table>")
        chunks.append("<table><thead><tr><th>Lauf / Start (UTC)</th><th>Gerät</th>"
                      "<th>Statistik</th><th>Hinweise</th><th>Dateien</th></tr></thead><tbody>")
        for run in catalog["runs"]:
            query = quote(run["id"], safe="")
            files = []
            for file in run["files"]:
                links = " ".join(f'<a href="../assets/sessions/{quote(part["path"], safe="/")}" download>'
                                 f'Teil {i + 1}</a>' for i, part in enumerate(file["parts"]))
                files.append(f'<li>{esc(file["name"])} ({esc(file["size"])} Bytes): {links}</li>')
            warnings = (["Testlauf – nicht für Messungen verwenden"] if run.get("test_run") else []) + run.get("warnings", [])
            stats = run["stats"]
            proc = stats.get("processing_ms") or {}
            conf = stats.get("confidence") or {}
            value = stats.get("value") or {}
            summary = (f'{esc(stats.get("frames"))} Frames<br>Verarbeitung Median / p95: '
                       f'{number(proc.get("median"))} / {number(proc.get("p95"))} ms<br>'
                       f'Konfidenzmedian (VALID): {percent(conf.get("median"))}<br>'
                       f'Leserate: {number(stats.get("rate_hz"))} Hz<br>'
                       f'Messwertmedian (VALID): {number(value.get("median"), 6)} {esc(run.get("unit"))}')
            chunks.append(f'<tr><td><a href="../assets/records-explorer/index.html?a={query}" target="_blank" '
                          f'rel="noopener">{esc(run["id"])}</a><br>{esc(run.get("started_at_utc"))}</td>'
                          f'<td>{esc(run.get("device_id"))}</td><td>{summary}</td>'
                          f'<td>{esc(" · ".join(warnings))}</td><td><ul>{"".join(files)}</ul>'
                          f'<a href="../assets/sessions/{quote(run["manifest"], safe="/")}">Manifest</a></td></tr>')
        chunks.append("</tbody></table></details>")
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
            for name in sorted(paths):
                destination = stage / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(member(chosen, name), destination)
        else:
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


def select_snapshots(root: Path, state: Path, wait_s=15, report=None) -> list[Path]:
    """Request a fixed exporter operation; never send commands or source paths."""
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
    try:
        with (root / "request").open("wb") as request:
            request.write(b"export\n")
        # Waiting is bounded even if the export service is absent or busy.
        deadline = time.monotonic() + min(15, max(0, wait_s))
        while time.monotonic() < deadline:
            if current() != before:
                break
            time.sleep(min(.25, max(0, deadline - time.monotonic())))
    except OSError:
        pass
    after = current()
    if report is not None:
        report["update_notice"] = "" if after and after != before else "Keine neue Archivgeneration im Wartefenster; eine zurückgestellte Aktualisierung verändert den angezeigten Stand nicht."
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
    parser.add_argument("--wait", type=float, default=15)
    parser.add_argument("--snapshot", type=Path, help="Explizite Generation, z. B. Integrationsfixture; keine Exportanfrage")
    args = parser.parse_args()
    try:
        report = {}
        snapshots = [args.snapshot] if args.snapshot else select_snapshots(args.export_root, args.state, args.wait, report)
        result = attach(args.site, snapshots, update_notice=report.get("update_notice", ""))
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
