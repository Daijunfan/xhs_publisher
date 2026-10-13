#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p runtime/tmp runtime/logs
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi
export PATH="$PWD/runtime/tools/bin:$HOME/.local/bin:$PATH"
if command -v vpn >/dev/null 2>&1; then
    eval "$(vpn env)"
fi
export TMPDIR="${TMPDIR:-$PWD/runtime/tmp}"
export HTML_PHOTO_BROWSER_PATH="${HTML_PHOTO_BROWSER_PATH:-$(.venv/bin/python -c 'from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()')}"
for library in /usr/local/cuda/lib64 "$PWD/runtime/tools/cudnn/lib" "$PWD"/.venv/lib/python*/site-packages/nvidia/{cublas,cudnn}/lib; do
    if [[ -d "$library" ]]; then
        export LD_LIBRARY_PATH="$library${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    fi
done
if [[ $# -eq 0 ]]; then set -- run; fi
exec .venv/bin/xhs "$@"
