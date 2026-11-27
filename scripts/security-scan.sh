#!/usr/bin/env bash
# Security-Scan fuer picam-ai: gitleaks (Geheimnisse) + bandit (Python-Schwachstellen).
#
# Aufruf: scripts/security-scan.sh [staged|tree|history]
#   staged   (Standard) nur Staging-Bereich: gitleaks + bandit auf gestagte src/**/*.py  (Pre-Commit)
#   tree     Arbeitsbaum: gitleaks ueber alle Dateien + bandit ueber src/             (T2/Nightly)
#   history  gesamte Git-Historie mit gitleaks                                          (T3 Release)
# Exit 0 = sauber, 1 = Fund, 2 = Werkzeug fehlt/Aufruffehler.
# Werkzeuge einmalig installieren: scripts/install-security-tools.sh
# Testhilfe: SCAN_ROOT=<Verzeichnis> scannt ein anderes Verzeichnis (nur Modus tree).
set -uo pipefail

MODE="${1:-staged}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 2
export PATH="$HOME/.local/bin:$PATH"
GITLEAKS="$(command -v gitleaks || true)"
BANDIT="${BANDIT:-$REPO_ROOT/.venv-tools/bin/bandit}"
BASELINE="$REPO_ROOT/.bandit-baseline.json"
CONFIG="$REPO_ROOT/.gitleaks.toml"
IGNORE="$REPO_ROOT/.gitleaksignore"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
RC=0

# Bandit-Ausschluesse (Tests, Worktrees, Venvs); bewusst hier statt in pyproject.toml,
# damit das Skript unabhaengig von [tool.bandit] stabil bleibt.
BANDIT_EXCLUDE='*/tests/*,*/.worktrees/*,*/.venv*,*/node_modules/*'

die() { echo "FEHLER: $*" >&2; exit 2; }
[ -n "$GITLEAKS" ] || die "gitleaks nicht gefunden - scripts/install-security-tools.sh ausfuehren"
case "$MODE" in staged|tree|history) ;; *) die "unbekannter Modus '$MODE' (staged|tree|history)" ;; esac

# gitleaks-Report (JSON, redigiert) lesbar ausgeben: Regel-ID, datei:zeile, Fix-Hinweis. Nie Inhalte.
report_gitleaks() {
  python3 -I - "$1" <<'PY'
import json, sys
funde = json.load(open(sys.argv[1]))
print(f"\n== gitleaks: {len(funde)} Fund(e) ==")
for f in funde[:50]:
    ort = f"{f['File']}:{f['StartLine']}"
    commit = f.get("Commit") or ""
    print(f"  [{f['RuleID']}] {ort}" + (f"  (Commit {commit[:8]})" if commit else ""))
    print(f"      Fingerprint: {f['Fingerprint']}")
if len(funde) > 50:
    print(f"  ... und {len(funde) - 50} weitere (gleiche Ursache pruefen; voller Report nur mit --redact lokal erzeugen)")
print("""
So beheben:
  1. Echtes Geheimnis: Wert aus der Datei entfernen (Umgebungsvariable/Secret-Store), das Geheimnis
     SOFORT ROTIEREN - auch wenn es nie gepusht wurde. Fund in der Historie: Rotation reicht, kein Umschreiben.
  2. Fehlalarm (Hash, Zufalls-ID, Testwert): gezielt freigeben, nie pauschal:
     - Pfad/Muster: Eintrag mit Kommentar-Begruendung in .gitleaks.toml unter [[allowlists]] paths
     - einzelner Fund (v. a. Historie): obigen Fingerprint in .gitleaksignore, Kommentarzeile mit Begruendung davor
     - einzelne Zeile im Code: Kommentar  # gitleaks:allow  in dieselbe Zeile (nur mit Begruendung im Review)
  Details: docs/security-scan.md""")
PY
}

run_gitleaks() {
  local report="$WORK/gitleaks.json" out rc
  # --redact: Geheimnisse erscheinen nie im Log oder Report.
  out="$("$GITLEAKS" "$@" -c "$CONFIG" --gitleaks-ignore-path "$IGNORE" --redact --no-banner \
        -l warn -f json -r "$report" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then echo "gitleaks: keine Funde"; return 0; fi
  if [ "$rc" -eq 1 ] && [ -s "$report" ]; then report_gitleaks "$report"; return 1; fi
  echo "$out" >&2; die "gitleaks-Aufruf fehlgeschlagen (Exit $rc)"
}

# bandit: nur NEUE Funde ab Severity medium gegenueber .bandit-baseline.json brechen.
run_bandit() {
  [ -x "$BANDIT" ] || die "bandit nicht gefunden ($BANDIT) - scripts/install-security-tools.sh ausfuehren"
  [ -f "$BASELINE" ] || die "Baseline fehlt: $BASELINE"
  local report="$WORK/bandit.json" args=("$@")
  "$BANDIT" "${args[@]}" -ll -b "$BASELINE" -f json -o "$report" -q >/dev/null 2>"$WORK/bandit.err"
  local rc=$?
  if [ ! -s "$report" ]; then cat "$WORK/bandit.err" >&2; die "bandit-Aufruf fehlgeschlagen (Exit $rc)"; fi
  python3 -I - "$report" ${STAGED_LIST:+"$STAGED_LIST"} <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
res = d["results"]
if len(sys.argv) > 2:  # Modus staged: nur Funde in gestagten Dateien melden
    gestagt = {z.strip() for z in open(sys.argv[2]) if z.strip()}
    res = [r for r in res if r["filename"].removeprefix("./") in gestagt]
if not res:
    print("bandit: keine neuen Funde ab Severity medium")
    sys.exit(0)
print(f"\n== bandit: {len(res)} NEUE(r) Fund(e) ab Severity medium ==")
for r in res:
    print(f"  [{r['test_id']}] {r['filename']}:{r['line_number']}  {r['issue_severity']}/{r['issue_confidence']}  {r['test_name']}")
    print(f"      {r['issue_text']}")
    print(f"      Doku: {r['more_info']}")
print("""
So beheben:
  1. Code sicherer machen (z. B. shell=True vermeiden, yaml.safe_load, tempfile statt festem /tmp-Pfad).
  2. Nachweislich unkritisch: Kommentar in der betroffenen Zeile  # nosec B<nummer> - <Begruendung>
     (immer mit Test-ID UND Begruendung, nie nacktes # nosec).
  3. Bewusst akzeptierter Bestand: nur nach Review die Baseline neu erzeugen
     (Befehl in docs/security-scan.md, Abschnitt Baseline pflegen) und die Bewertung dort ergaenzen.
  Details: docs/security-scan.md""")
sys.exit(1)
PY
}

case "$MODE" in
  staged)
    echo "== Modus staged =="
    run_gitleaks git "$REPO_ROOT" --pre-commit --staged || RC=1
    mapfile -t FILES < <(git diff --cached --name-only --diff-filter=ACMR -- 'src/*.py' 'src/**/*.py' | sort -u)
    if [ "${#FILES[@]}" -eq 0 ]; then
      echo "bandit: keine gestagten Python-Dateien unter src/"
    else
      # Immer ueber src/ scannen (nur so passen die Dateinamen zur Baseline: ein Einzeldatei-Aufruf
      # liefert "./src/..." und wuerde Bestandsfunde faelschlich als neu melden); gemeldet werden
      # danach nur Funde in gestagten Dateien.
      printf '%s\n' "${FILES[@]}" > "$WORK/staged.txt"
      STAGED_LIST="$WORK/staged.txt" run_bandit -r src -x "$BANDIT_EXCLUDE" || RC=1
    fi
    ;;
  tree)
    ROOT="${SCAN_ROOT:-.}"
    echo "== Modus tree ($ROOT) =="
    # Relativer Pfad noetig: die Allowlist-Pfade in .gitleaks.toml sind am Repo-Wurzelverzeichnis verankert.
    if [ -n "${SCAN_ROOT:-}" ]; then cd "$SCAN_ROOT" || die "SCAN_ROOT nicht erreichbar"; ROOT=.; fi
    run_gitleaks dir "$ROOT" || RC=1
    if [ -z "${SCAN_ROOT:-}" ] && [ -d src ]; then
      run_bandit -r src -x "$BANDIT_EXCLUDE" || RC=1
    fi
    ;;
  history)
    echo "== Modus history =="
    run_gitleaks git "$REPO_ROOT" || RC=1
    ;;
esac

if [ "$RC" -eq 0 ]; then echo "Security-Scan ($MODE): OK"; else echo "Security-Scan ($MODE): FEHLGESCHLAGEN"; fi
echo "Nachstellen: scripts/security-scan.sh $MODE"
exit "$RC"
