#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sudo apt-get install -y python3-aiohttp python3-textual python3-pam openssl
if [ ! -x .venv/bin/python ]; then
    python3 -m venv --system-site-packages .venv
fi
./.venv/bin/python -m pip install --no-deps -e .
echo 'Danach: ./.venv/bin/dispread init-tls && ./.venv/bin/dispread serve'
