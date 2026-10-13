#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/.config/systemd/user" runtime/tmp runtime/logs
sed "s|@PROJECT_ROOT@|$PWD|g" ops/xhs-publisher.service > "$HOME/.config/systemd/user/xhs-publisher.service"
systemctl --user daemon-reload
systemctl --user enable --now xhs-publisher.service
systemctl --user show xhs-publisher.service -p ActiveState -p MainPID
