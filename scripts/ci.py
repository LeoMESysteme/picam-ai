#!/usr/bin/env python3
"""Einheitlicher Stufenrunner: lokal und in der CI derselbe Aufruf.

  scripts/ci.py t0       pre-commit: ruff, gitleaks (staged), bandit, CHANGELOG-Regel
  scripts/ci.py t1       fokussiert: T0 + betroffene Tests (eskaliert bei grossen Aenderungen auf T2)
  scripts/ci.py t2       voll: komplette pytest-Suite, Playwright, bandit/gitleaks voll, Coverage
  scripts/ci.py t3       Release: T2 + timing seriell, Perf-Gate, Versionen, Release-Trockenlauf
  scripts/ci.py nightly  Trend und Drift: Security voll, Perf-Trend, Hardware-Tests wenn Geraet da

Optionen: --base <ref>, --dry-run, --changed-from-file <datei>, --staged,
--only/--skip <gruppe,...>, --no-escalate. Jeder Lauf endet mit
"Zum lokalen Nachstellen: <Befehl>"; bei Fehlern folgt je Fehlerklasse eine
Ursachen-/Fix-Zeile (Katalog: docs/ci-failures.md). JUnit-XML liegt in reports/.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
TIERS = ("t0", "t1", "t2", "t3", "nightly")
GROUPS = ("lint", "security", "changelog", "pytest", "playwright", "release", "perf", "hardware")
SLOW_MARKERS = "not slow and not timing and not hardware and not serial"
CHANGELOG_TRIGGERS = ("src/", "examples/", "scripts/", "systemd/", "udev/")
PLAYWRIGHT_TRIGGERS = (
    "src/dispread/workbench/static/", "docs/", "docs-site/", "docs-overrides/", "zensical.toml",
    "playwright", "package.json", "package-lock.json", "tests/live_ui_server.py",
)
RUFF_FULL_PATHS = ["src", "tests", "scripts", "packaging", "examples"]
# Die eingefrorene Lesevorlage liegt nicht im Repo (var/ ist ignoriert); unter src/dispread/data/ entsteht sie erst
# im Release-Archiv. Auf dem Runner kann PICAM_RELEASE_TEMPLATES auf eine bereitgestellte Kopie zeigen.
TEMPLATE_ENV = "PICAM_RELEASE_TEMPLATES"
TEMPLATE_PATH = "var/dotmatrix/templates-stufe2c-2026-09-30.json"

#: Fehlerklasse -> (Ursache, Fix, Anker in docs/ci-failures.md)
HINTS: dict[str, tuple[str, str, str]] = {
    "ruff": ("Stil-/Importregel verletzt (Regel-ID steht vor der Meldung).",
             "ruff check --fix <datei> fuer behebbare Regeln, sonst Stelle anpassen.", "ruff"),
    "gitleaks": ("gitleaks meldet ein moegliches Geheimnis (Inhalt wird absichtlich nicht gezeigt, nur datei:zeile).",
                 "Echtes Geheimnis: entfernen und ROTIEREN. Fehlalarm: begruendet in .gitleaks.toml freigeben.", "gitleaks"),
    "bandit": ("bandit meldet einen neuen Fund ab Schwelle medium (Test-ID wie B602 steht in der Meldung).",
               "Code absichern oder begruendet mit '# nosec <ID>' markieren; Bestand steht in der Baseline.", "bandit"),
    "changelog": ("Quelle geaendert, aber CHANGELOG.md nicht (AGENTS.md: Eintrag im selben Commit).",
                  "Eintrag unter '## Unveroeffentlicht' ergaenzen.", "changelog"),
    "pytest": ("Mindestens ein Test ist rot oder die pytest-Konfiguration ist ungueltig (Exit 2/4 = Konfiguration, z. B. unbekannter Marker).",
               "Namen unten einzeln nachstellen: pytest <nodeid> -x; bei Marker-Fehler Marker in pyproject.toml registrieren.", "pytest"),
    "playwright": ("Browser-Test der Doku oder der Werkbank-Oberflaeche rot oder Browser/Doku-Build fehlt.",
                   "npm ci, npx playwright install --only-shell chromium, dann den Befehl einzeln wiederholen.", "playwright"),
    "release": ("Versionsstaende widersprechen sich oder der Release-Trockenlauf scheitert.",
                "VERSION, CHANGELOG-Kopfzeile und Tag angleichen; PICAM_RELEASE_TEMPLATES pruefen (docs/ci-failures.md#release).", "release"),
    "perf": ("Perf-Gate verletzt oder Lauf ungueltig (z. B. Throttling).",
             "perf-report.py einzeln wiederholen; bei Throttling Kuehlung/Netzteil pruefen statt Baseline anpassen.", "perf"),
    "hardware": ("Hardware-Test im real-Modus rot.", "Kamera/UART pruefen (scripts/camera-commissioning.sh).", "hardware"),
    "tool": ("Ein Pflichtwerkzeug fehlt (gitleaks/bandit/Playwright).",
             "scripts/install-security-tools.sh bzw. npm ci ausfuehren.", "werkzeug-fehlt"),
}


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # noetig fuer dataclasses
    spec.loader.exec_module(mod)
    return mod


select_mod = _load("picam_test_select", "test-select.py")


@dataclass
class Step:
    group: str
    name: str
    cmd: list[str] | None = None
    fn: object = None  # Callable[[], tuple[bool, str]] statt Kommando
    required: bool = True
    skip_reason: str = ""  # gesetzt: nicht ausfuehrbar
    cwd: Path = ROOT
    junit: Path | None = None


@dataclass
class Result:
    step: Step
    status: str  # ok | fail | skip | warn
    seconds: float = 0.0
    detail: str = ""


def find_tool(name: str, extra: tuple[str, ...] = ()) -> str | None:
    for cand in extra:
        if Path(cand).is_file() and os.access(cand, os.X_OK):
            return cand
    return shutil.which(name)


def venv_python() -> str:
    p = ROOT / ".venv" / "bin" / "python"
    return str(p) if p.is_file() else sys.executable


def has_module(mod: str) -> bool:
    return subprocess.run([venv_python(), "-c", f"import {mod}"], capture_output=True).returncode == 0


def sh_quote(cmd: list[str]) -> str:
    return " ".join(shlex.quote(c) for c in cmd)


@dataclass
class Context:
    tier: str
    base: str | None
    staged: bool
    files: list[str]
    decision: object
    effective: str  # t0..nightly nach Eskalation
    escalated: bool = False
    notes: list[str] = field(default_factory=list)


def bandit_config() -> list[str]:
    cfg: list[str] = []
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8") if (ROOT / "pyproject.toml").is_file() else ""
    if "[tool.bandit]" in text:
        cfg += ["-c", "pyproject.toml"]
    for cand in (".bandit-baseline.json", "bandit-baseline.json", "security/bandit-baseline.json",
                 ".security/bandit-baseline.json"):
        if (ROOT / cand).is_file():
            cfg += ["-b", cand]
            break
    return cfg


def lint_steps(ctx: Context, full: bool) -> list[Step]:
    ruff = find_tool("ruff", (str(ROOT / ".venv/bin/ruff"), str(ROOT / ".venv-tools/bin/ruff")))
    if not ruff:
        return [Step("lint", "ruff", skip_reason="ruff nicht gefunden (.venv/bin/pip install ruff)")]
    if full:
        return [Step("lint", "ruff (voll)", [ruff, "check", *RUFF_FULL_PATHS])]
    py = [f for f in ctx.files if f.endswith(".py") and (ROOT / f).is_file()
          and f.split("/", 1)[0] in {"src", "tests", "scripts", "packaging", "examples"}]
    if not py:
        return [Step("lint", "ruff (geaenderte Dateien)", skip_reason="keine geaenderten Python-Dateien")]
    return [Step("lint", "ruff (geaenderte Dateien)", [ruff, "check", *py])]


def security_steps(ctx: Context, full: bool, hard: bool) -> list[Step]:
    steps: list[Step] = []
    gl = find_tool("gitleaks", (str(Path.home() / ".local/bin/gitleaks"),))
    cfg = ROOT / ".gitleaks.toml"
    if not gl:
        steps.append(Step("security", "gitleaks", required=hard,
                          skip_reason="gitleaks nicht gefunden (scripts/install-security-tools.sh)"))
    else:
        cmd = [gl, "git", "--redact", "--no-banner"]
        if cfg.is_file():
            cmd += ["-c", str(cfg)]
        if full:
            label = "gitleaks (gesamte Historie)"
        elif ctx.staged:
            cmd += ["--pre-commit", "--staged"]
            label = "gitleaks (staged)"
        else:
            base = ctx.base or select_mod.default_base()
            cmd += ["--log-opts", f"{base}..HEAD"]
            label = f"gitleaks ({base}..HEAD)"
        if not cfg.is_file():
            ctx.notes.append("Hinweis: .gitleaks.toml fehlt, gitleaks nutzt Standardregeln (Paket B liefert die Konfig)")
        steps.append(Step("security", label, cmd))
    bd = find_tool("bandit", (str(ROOT / ".venv-tools/bin/bandit"), str(ROOT / ".venv/bin/bandit")))
    if not bd:
        steps.append(Step("security", "bandit", required=hard,
                          skip_reason="bandit nicht gefunden (scripts/install-security-tools.sh, nicht in .venv)"))
    else:
        base_args = [bd, "-ll", "-q", *bandit_config()]
        if full:
            steps.append(Step("security", "bandit (voll)", [*base_args, "-r", "src"]))
        else:
            py = [f for f in ctx.files if f.startswith("src/") and f.endswith(".py") and (ROOT / f).is_file()]
            if py:
                steps.append(Step("security", "bandit (geaenderte Dateien)", [*base_args, *py]))
            else:
                steps.append(Step("security", "bandit (geaenderte Dateien)", skip_reason="keine geaenderten Dateien unter src/"))
    return steps


def changelog_step(ctx: Context) -> Step:
    def check() -> tuple[bool, str]:
        trig = [f for f in ctx.files if f.startswith(CHANGELOG_TRIGGERS) and not f.startswith("src/dispread/workbench/static/vendor/")]
        if not trig:
            return True, "keine Aenderung an src/, examples/, scripts/, systemd/, udev/"
        if "CHANGELOG.md" in ctx.files:
            return True, "CHANGELOG.md ist mitgeaendert"
        return False, f"{trig[0]} (+{len(trig) - 1} weitere) geaendert, CHANGELOG.md nicht (Regel aus AGENTS.md)"
    return Step("changelog", "CHANGELOG-Regel", fn=check)


def pytest_steps(ctx: Context, tier: str, full: bool) -> list[Step]:
    py = venv_python()
    xdist = has_module("xdist")
    timeout = has_module("pytest_timeout")
    cov = has_module("pytest_cov")
    base = [py, "-m", "pytest", "-q"]
    if timeout:
        base += ["--timeout", "600" if tier in ("t3", "nightly") else "300"]
    else:
        ctx.notes.append("Hinweis: pytest-timeout nicht installiert, Tests laufen ohne Zeitlimit (docs/dependencies.md)")
    # Der Forgejo-Runner hat CPUQuota=200% und MemoryMax=2G (systemd-Unit): dort PICAM_CI_WORKERS=2 setzen.
    workers = os.environ.get("PICAM_CI_WORKERS", "4")
    par = ["-n", workers] if xdist else []
    if not xdist:
        ctx.notes.append("Hinweis: pytest-xdist fehlt, Suite laeuft seriell (deutlich langsamer)")
    steps: list[Step] = []
    junit = REPORTS / f"junit-{tier}.xml"
    if not full:
        tests = ctx.decision.tests
        if not tests:
            return [Step("pytest", "pytest (fokussiert)", skip_reason="keine betroffenen Tests")]
        steps.append(Step("pytest", f"pytest fokussiert ({len(tests)} Dateien)",
                          [*base, *par, "-m", SLOW_MARKERS, f"--junitxml={junit}", *tests], junit=junit))
        return steps
    cmd = [*base, *par, f"--junitxml={junit}"]
    if tier in ("t2", "t3"):
        if cov:
            cmd += ["--cov=dispread", f"--cov-report=xml:{REPORTS / 'coverage.xml'}", "--cov-report=term:skip-covered"]
        else:
            ctx.notes.append("Hinweis: pytest-cov nicht installiert, Coverage uebersprungen")
    steps.append(Step("pytest", "pytest voll (mock)", cmd, junit=junit))
    if tier in ("t3", "nightly"):
        j2 = REPORTS / f"junit-{tier}-timing.xml"
        steps.append(Step("pytest", "pytest timing (seriell)", [*base, "-m", "timing", f"--junitxml={j2}"], junit=j2))
    return steps


def playwright_steps(ctx: Context) -> list[Step]:
    pw = ROOT / "node_modules/.bin/playwright"
    if not pw.is_file():
        return [Step("playwright", "Playwright", skip_reason="node_modules/.bin/playwright fehlt (npm ci)")]
    npx = shutil.which("npx") or "npx"
    steps = []
    if (ROOT / "scripts/docs-site.sh").is_file():
        steps.append(Step("playwright", "Doku bauen", ["./scripts/docs-site.sh", "build", "-s"]))
    steps.append(Step("playwright", "Playwright Doku", [npx, "playwright", "test", "-c", "playwright.docs.config.ts",
                                                       "--workers=1", "--reporter=line"]))
    steps.append(Step("playwright", "Playwright Werkbank /live", [npx, "playwright", "test", "-c", "playwright.live.config.ts",
                                                                 "--workers=1", "--reporter=line"]))
    return steps


def version_check() -> tuple[bool, str]:
    ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    msgs, ok = [f"VERSION = {ver}"], True
    m = re.search(r"^## (\d+\.\d+\.\d+)\b", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    if not m or m.group(1) != ver:
        ok = False
        msgs.append(f"CHANGELOG-Kopfzeile = {m.group(1) if m else 'nicht gefunden'} (erwartet {ver})")
    tag = os.environ.get("CI_COMMIT_TAG") or os.environ.get("GITHUB_REF_NAME") or ""
    if not tag:
        tag = select_mod._git("describe", "--exact-match", "--tags", "HEAD", root=ROOT).strip()
    if tag.startswith("v"):
        if tag[1:] != ver:
            ok = False
            msgs.append(f"Tag {tag} passt nicht zu VERSION {ver}")
        else:
            msgs.append(f"Tag {tag} passt")
    else:
        msgs.append("kein v*-Tag auf HEAD, Tag-Pruefung uebersprungen")
    try:
        pj = json.loads((ROOT / "package.json").read_text(encoding="utf-8")).get("version")
        if pj != ver:
            msgs.append(f"WARNUNG (nicht blockierend): package.json version = {pj}, VERSION = {ver}")
    except (OSError, ValueError):
        pass
    return ok, "; ".join(msgs)


def release_steps(ctx: Context) -> list[Step]:
    steps = [Step("release", "Versions-Konsistenz", fn=version_check)]
    env_tpl = os.environ.get(TEMPLATE_ENV, "")
    tpl = Path(env_tpl) if env_tpl else ROOT / TEMPLATE_PATH
    if tpl.is_file():
        import tempfile
        out = Path(tempfile.gettempdir()) / "picam-ci-release-dryrun" / "picam-release.tar.gz"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        steps.append(Step("release", "build-release.py Trockenlauf",
                          [venv_python(), "scripts/build-release.py", "--output", str(out), "--templates", str(tpl),
                           "--release-id", "ci-dryrun"]))
    elif env_tpl:
        # Ausdruecklich konfiguriert, aber nicht da: das ist ein Fehler, kein Auslassen.
        steps.append(Step("release", "build-release.py Trockenlauf",
                          fn=lambda: (False, f"{TEMPLATE_ENV} zeigt auf eine fehlende Datei: {env_tpl}")))
    else:
        steps.append(Step("release", "build-release.py Trockenlauf", required=False,
                          skip_reason=f"Lesevorlage nicht vorhanden ({TEMPLATE_PATH}); Release-Build NICHT geprueft. "
                                      f"Auf dem Runner {TEMPLATE_ENV}=<Pfad> setzen."))
    return steps


def perf_steps(tier: str) -> list[Step]:
    script = ROOT / "scripts/perf-report.py"
    if not script.is_file():
        return [Step("perf", "Perf-Gate", skip_reason="scripts/perf-report.py fehlt (Paket C) - Perf-Gate NICHT geprueft",
                     required=False)]
    if os.environ.get("PICAM_PERF_GATE") == "skip":
        # Der Runner laeuft mit Nice=19, CPUWeight=10 und CPUQuota=200%: Latenzen dort sind nicht mit der
        # Baseline (ungedrosselter Pi) vergleichbar. Gate dann am freien Geraet pruefen.
        return [Step("perf", "Perf-Gate", required=False,
                     skip_reason="PICAM_PERF_GATE=skip (gedrosselter Runner) - Perf-Gate NICHT geprueft; "
                                 "vor dem Tag am freien Geraet: scripts/ci.py t3 --only perf")]
    if tier == "t3":
        baseline = ROOT / "perf" / "baseline.json"
        if not baseline.is_file():
            return [Step("perf", "Perf-Gate", fn=lambda: (False, "perf/baseline.json fehlt (perf-report.py --update-baseline auf dem Runner)"))]
        return [Step("perf", "Perf-Gate", [venv_python(), str(script), "--compare", str(baseline),
                                           "--summary-file", str(REPORTS / "perf-summary.md")])]
    return [Step("perf", "Perf-Trend", [venv_python(), str(script)])]


def hardware_steps() -> list[Step]:
    dev = [p for p in ("/dev/video0", "/dev/ttyAMA0", "/dev/ttyUSB0") if Path(p).exists()]
    if not dev:
        return [Step("hardware", "Hardware-Tests (real)", skip_reason="kein Geraet gefunden (/dev/video0, ttyAMA0, ttyUSB0)",
                     required=False)]
    return [Step("hardware", "Hardware-Tests (real)", [venv_python(), "-m", "pytest", "-q", "--mode=real",
                                                      "-m", "hardware or serial",
                                                      f"--junitxml={REPORTS / 'junit-nightly-hardware.xml'}"],
                 junit=REPORTS / "junit-nightly-hardware.xml")]


def build_plan(ctx: Context) -> list[Step]:
    t = ctx.effective
    steps: list[Step] = []
    if t in ("t0", "t1"):
        steps += lint_steps(ctx, False) + security_steps(ctx, False, False) + [changelog_step(ctx)]
        if t == "t1":
            steps += pytest_steps(ctx, "t1", False)
        return steps
    steps += lint_steps(ctx, True)
    steps += security_steps(ctx, True, True)
    if t == "t2" and ctx.escalated:
        steps.append(changelog_step(ctx))
    if t in ("t2", "t3"):
        steps += pytest_steps(ctx, t, True)
        if t == "t3" or not ctx.escalated or any(f.startswith(PLAYWRIGHT_TRIGGERS) for f in ctx.files):
            steps += playwright_steps(ctx)
    if t == "t3":
        steps += release_steps(ctx) + perf_steps("t3")
    if t == "nightly":
        steps += pytest_steps(ctx, "nightly", True)[:1] + perf_steps("nightly") + hardware_steps()
    return steps


def failed_tests(junit: Path, limit: int = 10) -> list[str]:
    if not junit or not junit.is_file():
        return []
    out = []
    try:
        for tc in ET.parse(junit).getroot().iter("testcase"):
            if tc.find("failure") is not None or tc.find("error") is not None:
                cls = (tc.get("classname") or "").replace(".", "/")
                out.append(f"{cls}.py::{tc.get('name')}" if cls else tc.get("name", "?"))
    except ET.ParseError:
        return []
    return out[:limit]


def run_step(step: Step, strict_missing: bool) -> Result:
    if step.skip_reason:
        if step.required and strict_missing:
            return Result(step, "fail", detail=step.skip_reason)
        return Result(step, "skip", detail=step.skip_reason)
    t0 = time.monotonic()
    if step.fn:
        ok, msg = step.fn()
        return Result(step, "ok" if ok else "fail", time.monotonic() - t0, msg)
    print(f"\n$ {sh_quote(step.cmd)}", flush=True)
    try:
        rc = subprocess.run(step.cmd, cwd=step.cwd).returncode
    except FileNotFoundError as exc:
        return Result(step, "fail", time.monotonic() - t0, str(exc))
    return Result(step, "ok" if rc == 0 else "fail", time.monotonic() - t0, f"Exit {rc}")


def repro_command(argv: list[str]) -> str:
    return "scripts/ci.py " + sh_quote(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tier", choices=TIERS)
    ap.add_argument("--base", help="Basis-Ref fuer geaenderte Dateien (Default: Upstream/origin/master)")
    ap.add_argument("--dry-run", action="store_true", help="nur anzeigen: Stufe, Testauswahl, Schritte")
    ap.add_argument("--changed-from-file", metavar="DATEI", help="Liste geaenderter Dateien ('-' = stdin) statt git")
    ap.add_argument("--staged", action="store_true", help="nur gestagte Dateien (pre-commit)")
    ap.add_argument("--only", default="", help=f"nur diese Gruppen: {','.join(GROUPS)}")
    ap.add_argument("--skip", default="", help="diese Gruppen auslassen")
    ap.add_argument("--no-escalate", action="store_true", help="T1 nie auf T2 eskalieren")
    args = ap.parse_args(argv)
    only = {g for g in args.only.split(",") if g}
    skip = {g for g in args.skip.split(",") if g}
    bad = (only | skip) - set(GROUPS)
    if bad:
        ap.error(f"unbekannte Gruppe(n): {', '.join(sorted(bad))}")

    if args.changed_from_file:
        files = select_mod.read_file_list(args.changed_from_file)
    else:
        files = select_mod.changed_files(args.base, args.staged)
    decision = select_mod.select(files)
    effective, escalated = args.tier, False
    if args.tier == "t1" and decision.level == "full" and not args.no_escalate:
        effective, escalated = "t2", True
    ctx = Context(args.tier, args.base, args.staged, files, decision, effective, escalated)
    steps = [s for s in build_plan(ctx) if (not only or s.group in only) and s.group not in skip]

    print(f"Stufe {args.tier.upper()}" + (" -> eskaliert auf T2" if escalated else "") + f", {len(files)} geaenderte Datei(en)")
    if args.tier in ("t0", "t1") or escalated:
        print(select_mod.format_decision(decision, len(files)))
    for n in ctx.notes:
        print(n)
    strict = effective in ("t2", "t3", "nightly")
    results: list[Result] = []
    if args.dry_run:
        print("\nSchritte (Trockenlauf, nichts ausgefuehrt):")
        for s in steps:
            if s.skip_reason:
                verdict = "FEHLER (Pflicht)" if s.required and strict else "uebersprungen"
                print(f"  [{s.group}] {s.name}: {verdict} - {s.skip_reason}")
            elif s.fn:
                print(f"  [{s.group}] {s.name}: interne Pruefung")
            else:
                print(f"  [{s.group}] {s.name}: {sh_quote(s.cmd)}")
        print(f"\nZum lokalen Nachstellen: {repro_command(argv)}")
        return 0

    REPORTS.mkdir(exist_ok=True)
    for s in steps:
        results.append(run_step(s, strict))

    print("\n=== Zusammenfassung ===")
    for r in results:
        print(f"  {r.status.upper():5} [{r.step.group}] {r.step.name}"
              + (f" ({r.seconds:.0f}s)" if r.seconds else "") + (f": {r.detail}" if r.detail and r.status != "ok" else ""))
        if r.step.fn and r.status == "ok" and r.detail:
            print(f"        {r.detail}")
    failed = [r for r in results if r.status == "fail"]
    for r in failed:
        key = "tool" if r.step.skip_reason else r.step.group
        cause, fix, anchor = HINTS.get(key, ("unbekannt", "Ausgabe oben lesen", ""))
        print(f"\nFEHLER {r.step.name}: {r.detail}")
        if r.step.junit:
            names = failed_tests(r.step.junit)
            for n in names:
                print(f"  rot: {n}   (nachstellen: pytest {n} -x)")
        print(f"  Ursache: {cause}\n  Fix: {fix}\n  Katalog: docs/ci-failures.md#{anchor}")
        if r.step.cmd:
            print(f"  Einzelschritt: {sh_quote(r.step.cmd)}")
    for r in results:
        if r.status == "skip" and not r.step.required or (r.status == "skip" and r.step.group == "perf"):
            print(f"Hinweis: {r.step.name} uebersprungen - {r.detail}")
    print(f"\nZum lokalen Nachstellen: {repro_command(argv)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
