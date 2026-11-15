#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LEGACY_INSTALLER="$SCRIPT_DIR/install-armoury-crate.sh"

[[ -x "$LEGACY_INSTALLER" ]] || {
    printf 'Error: missing executable installer: %s\n' "$LEGACY_INSTALLER" >&2
    exit 1
}

"$LEGACY_INSTALLER" uninstall
rm -rf "$HOME/.local/share/armoury-crate"
printf 'Removed Armoury Crate application files from ~/.local. System dependencies were left installed.\n'
