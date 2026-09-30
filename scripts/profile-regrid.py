#!/usr/bin/env python3
"""Punktraster eines Sitzungsprofils gegen die Punkte pruefen und korrigieren.

Befund 2026-09-30 (VALIDATION.md, Rasterversatz): Die Profile `ab3`/`ab4`
(auch `ernte1`, `auf2`, `auf3`) tasten bis 0,5-0,8 Punktspalten neben den
Punktmitten ab. Dieses Werkzeug misst den Versatz an den geernteten Proben
einer Gruppe (Bild plus serielles Label) und passt das Quad neu an
(`dispread.lattice_offsets`). Es arbeitet ohne Leser und ohne Vorlagen.

    measure  Median-Versatz je Zelle/Halbzelle fuer ein Profil
    refine   Quad an einer Haelfte der Proben anpassen, an der anderen
             pruefen; schreibt ein NEUES, unbestaetigtes Profil, einen
             Bericht (`<out>.regrid.json`) und ein Kontrollbild
    confirm  korrigiertes Profil nach Sichtpruefung bestaetigen

Ein korrigiertes Profil gilt erst nach `confirm`. In die Profilzuordnung
kommt es mit `replaces` = Pruefsumme des abgeloesten Profils (siehe
`scripts/dotmatrix-dataset.py`, `_resolve_profile`).
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from dispread.lattice_offsets import (
    FULL,
    max_abs_offset,
    measure_offsets,
    median_offsets,
    refine_quad,
)
from dispread.session_profile import SessionProfile

METHOD = "lattice_offsets_v1"
#: Ziel nach der Korrektur, gemessen an den Pruefproben (nicht angepasst):
#: waagerecht je Halbzelle (erfasst Scherung), senkrecht je ganzer Zelle
#: (Halbzellen messen bei `+` systematisch entgegengesetzt, siehe
#: `lattice_offsets.FULL`).
MAX_OFFSET_COLS = 0.1
MAX_OFFSET_ROWS = 0.15
CELL_COUNT = 9


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _group_frames(dataset_root: Path, group: str, limit: int) -> list[tuple[Path, str]]:
    """Bildpfad und Zellentext (Zellen 0-8) der seriell gelabelten Proben
    einer Gruppe, gleichmaessig ueber die Gruppe verteilt."""
    found: list[tuple[Path, str]] = []
    for sample_json in sorted((dataset_root / "samples").glob("*/sample.json")):
        sample = json.loads(sample_json.read_text(encoding="utf-8"))
        if sample.get("label_origin") != "serial_ascii" or sample.get("label_state") != "readable":
            continue
        detail = sample.get("label_origin_detail") or {}
        if detail.get("session_id") != group:
            continue
        found.append((sample_json.parent / "image.png", str(detail.get("cell_text", ""))[:CELL_COUNT]))
    if len(found) > limit:
        idx = np.linspace(0, len(found) - 1, limit).round().astype(int)
        found = [found[i] for i in idx]
    return found


def _load_frames(items: list[tuple[Path, str]]) -> list[tuple[np.ndarray, str]]:
    frames = []
    for path, text in items:
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            frames.append((img, text))
    return frames


def _fmt(offsets: dict) -> str:
    return "  ".join(f"{c}.{'ou'[h]}:{v[0]:+.2f}/{v[1]:+.2f}" for (c, h), v in offsets.items())


def _offsets_json(offsets: dict) -> list[dict]:
    return [
        {"cell": c, "half": h, "dx_cols": round(v[0], 4), "dy_rows": round(v[1], 4), "n": v[2]}
        for (c, h), v in offsets.items()
    ]


def _cmd_measure(args: argparse.Namespace) -> int:
    profile = SessionProfile.load(args.profile)
    frames = _load_frames(_group_frames(args.dataset_root, args.group, args.n))
    if not frames:
        print(f"Keine Proben fuer Gruppe {args.group!r}.", file=sys.stderr)
        return 2
    meds = median_offsets(
        [measure_offsets(img, profile.quad, profile.grid, profile.target_size, t) for img, t in frames]
    )
    dx, dy = max_abs_offset(meds)
    print(f"{args.group}: {len(frames)} Bilder, groesster Versatz {dx:.2f} Punktspalten / {dy:.2f} Punktzeilen")
    print("  " + _fmt(meds))
    return 0


def _overlay(image: np.ndarray, quads: list[tuple[np.ndarray, tuple[int, int, int]]], profile) -> np.ndarray:
    """Punktmitten der Zellen 0-8 fuer jedes Quad, ausgeschnitten und
    vergroessert (rot = alt, gruen = neu)."""
    vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    w, h = profile.target_size
    g = profile.grid
    col_w = g.pitch / (g.dot_columns + g.gap_columns)
    row_h = (g.bottom - g.top) / 8
    lattice = np.array(
        [
            (g.left + cell * g.pitch + (c + 0.5) * col_w, g.top + (r + 0.5) * row_h)
            for cell in range(CELL_COUNT)
            for r in range(7)
            for c in range(5)
        ],
        np.float32,
    )
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32)
    all_pts = []
    for quad, color in quads:
        hom = cv2.getPerspectiveTransform(dst, np.asarray(quad, np.float32))
        pts = cv2.perspectiveTransform(lattice[None], hom)[0]
        all_pts.append((pts, color))
    xs = np.concatenate([p[:, 0] for p, _ in all_pts])
    ys = np.concatenate([p[:, 1] for p, _ in all_pts])
    x0, y0 = int(max(0, xs.min() - 15)), int(max(0, ys.min() - 15))
    x1, y1 = int(min(vis.shape[1], xs.max() + 15)), int(min(vis.shape[0], ys.max() + 15))
    f = max(1, int(round(1400 / max(1, x1 - x0))))
    big = cv2.resize(vis[y0:y1, x0:x1], None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    for pts, color in all_pts:
        for x, y in pts:
            cv2.circle(big, (int((x - x0) * f), int((y - y0) * f)), max(2, f // 2), color, -1)
    return big


def _cmd_refine(args: argparse.Namespace) -> int:
    if args.out.exists():
        print(f"{args.out} existiert schon - nicht ueberschreiben.", file=sys.stderr)
        return 2
    profile = SessionProfile.load(args.profile)
    items = _group_frames(args.dataset_root, args.group, args.n)
    fit_frames = _load_frames(items[0::2])
    check_frames = _load_frames(items[1::2])
    if len(fit_frames) < 3 or len(check_frames) < 3:
        print(f"Zu wenige Proben fuer Gruppe {args.group!r} ({len(items)}).", file=sys.stderr)
        return 2

    def check(quad, row_sets=None) -> dict:
        kw = {} if row_sets is None else {"row_sets": row_sets}
        return median_offsets(
            [measure_offsets(img, quad, profile.grid, profile.target_size, t, **kw) for img, t in check_frames]
        )

    def worst(quad) -> tuple[dict, float, float]:
        halves = check(quad)
        return halves, max_abs_offset(halves)[0], max_abs_offset(check(quad, FULL))[1]

    before, bdx, bdy = worst(profile.quad)
    new_quad, history = refine_quad(fit_frames, profile.quad, profile.grid, profile.target_size)
    after, adx, ady = worst(new_quad)
    ok = adx <= MAX_OFFSET_COLS and ady <= MAX_OFFSET_ROWS
    print(f"{args.group}: Anpassung an {len(fit_frames)} Bildern, Pruefung an {len(check_frames)}")
    print(f"  vorher  groesster Versatz {bdx:.2f} (Halbzellen, x) / {bdy:.2f} (Zellen, y):  " + _fmt(before))
    print(f"  nachher groesster Versatz {adx:.2f} (Halbzellen, x) / {ady:.2f} (Zellen, y):  " + _fmt(after))
    print(f"  altes Quad {np.round(np.asarray(profile.quad), 1).tolist()}")
    print(f"  neues Quad {np.round(new_quad, 1).tolist()}")
    if not ok:
        print(
            f"Ziel verfehlt (hoechstens {MAX_OFFSET_COLS} Punktspalten / {MAX_OFFSET_ROWS} Punktzeilen) - "
            "kein Profil geschrieben.",
            file=sys.stderr,
        )
        return 3

    new_profile = dataclasses.replace(
        profile,
        session_id=profile.session_id,
        quad=[[round(float(x), 2), round(float(y), 2)] for x, y in new_quad],
        confirmed_by=None,
        confirmed_at_utc=None,
    )
    new_profile.save(args.out)
    report = {
        "method": METHOD,
        "group": args.group,
        "source_profile": str(args.profile),
        "source_sha256": _sha256(args.profile),
        "profile": str(args.out),
        "created_utc": dt.datetime.now(dt.UTC).isoformat(),
        "n_fit": len(fit_frames),
        "n_check": len(check_frames),
        "max_offset_before": [round(bdx, 4), round(bdy, 4)],
        "max_offset_after": [round(adx, 4), round(ady, 4)],
        "target": [MAX_OFFSET_COLS, MAX_OFFSET_ROWS],
        "offsets_before": _offsets_json(before),
        "offsets_after": _offsets_json(after),
        "iterations": len(history),
        "quad_before": np.asarray(profile.quad).tolist(),
        "quad_after": new_quad.tolist(),
    }
    report_path = Path(str(args.out) + ".regrid.json")
    report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    overlay_path = Path(str(args.out) + ".overlay.png")
    cv2.imwrite(
        str(overlay_path),
        _overlay(check_frames[0][0], [(np.asarray(profile.quad), (0, 0, 255)), (new_quad, (0, 200, 0))], profile),
    )
    print(f"Profil (unbestaetigt): {args.out}")
    print(f"Bericht: {report_path}")
    print(f"Kontrollbild (rot alt, gruen neu): {overlay_path}")
    return 0


def _cmd_confirm(args: argparse.Namespace) -> int:
    report_path = Path(str(args.profile) + ".regrid.json")
    if not report_path.is_file():
        print(f"Kein Bericht {report_path} - nur korrigierte Profile hier bestaetigen.", file=sys.stderr)
        return 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    adx, ady = report["max_offset_after"]
    if adx > MAX_OFFSET_COLS or ady > MAX_OFFSET_ROWS:
        print("Bericht verfehlt das Ziel - nicht bestaetigt.", file=sys.stderr)
        return 3
    profile = SessionProfile.load(args.profile)
    if profile.confirmed_by:
        print(f"{args.profile} ist schon bestaetigt ({profile.confirmed_by}).", file=sys.stderr)
        return 2
    confirmed = dataclasses.replace(
        profile, confirmed_by=args.confirmed_by, confirmed_at_utc=dt.datetime.now(dt.UTC).isoformat()
    )
    confirmed.save(args.profile)
    print(f"Bestaetigt: {args.profile} (sha256 {_sha256(args.profile)})")
    print(f"Ersetzt: {report['source_profile']} (sha256 {report['source_sha256']})")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, func in (("measure", _cmd_measure), ("refine", _cmd_refine)):
        s = sub.add_parser(name)
        s.add_argument("--profile", type=Path, required=True)
        s.add_argument("--group", required=True, help="session_id der Proben im Datensatz")
        s.add_argument("--dataset-root", type=Path, default=Path("var/workbench/datasets"))
        s.add_argument("--n", type=int, default=40, help="hoechstens so viele Proben (gleichmaessig verteilt)")
        s.set_defaults(func=func)
        if name == "refine":
            s.add_argument("--out", type=Path, required=True, help="neue Profildatei (darf nicht existieren)")
    c = sub.add_parser("confirm")
    c.add_argument("--profile", type=Path, required=True)
    c.add_argument("--confirmed-by", required=True)
    c.set_defaults(func=_cmd_confirm)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
