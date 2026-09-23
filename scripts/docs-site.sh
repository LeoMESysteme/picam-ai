#!/usr/bin/env bash
# Doku-Seite mit Zensical bauen oder lokal ansehen.
#
#   ./scripts/docs-site.sh build   # -> site/
#   ./scripts/docs-site.sh serve   # -> http://127.0.0.1:8000 (Adresse: --dev-addr)
#
# Zensical erlaubt kein docs_dir = "." und folgt keinen Verzeichnis-Symlinks.
# Deshalb baut dieses Skript docs-site/ vor jedem Lauf aus Datei-Symlinks auf:
# docs/ als Baum, dazu die Doku-Dateien im Wurzelverzeichnis. Die relativen
# Links der Markdown-Dateien bleiben so exakt gültig, und neue Dateien unter
# docs/ erscheinen ohne weiteres Zutun. Die Symlinks sind absolut und deshalb
# nicht versioniert (.gitignore); versioniert ist nur docs-site/api/.
#
# Einmalige Einrichtung (eigene venv, die Projekt-.venv bleibt unberührt):
#   python3 -m venv .venv-docs
#   ./.venv-docs/bin/pip install -r requirements-docs.txt
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_SRC="$ROOT/docs-site"
ZENSICAL="$ROOT/.venv-docs/bin/zensical"
ROOT_DOCS=(Konzept.md CHANGELOG.md AGENTS.md CLAUDE.md TODO.md PLANNED_FEATURES.md)

if [[ ! -x "$ZENSICAL" ]]; then
    echo "zensical fehlt: siehe Einrichtung im Kopf von $0" >&2
    exit 1
fi

rm -rf "$SITE_SRC/docs"
cp -rs "$ROOT/docs" "$SITE_SRC/docs"
for f in "${ROOT_DOCS[@]}"; do
    ln -sfn "$ROOT/$f" "$SITE_SRC/$f"
done
# README.md ist die Startseite.
ln -sfn "$ROOT/README.md" "$SITE_SRC/index.md"

cd "$ROOT"
exec "$ZENSICAL" "${1:-build}" "${@:2}"
