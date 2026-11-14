#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STAGING_DIR="$SCRIPT_DIR/armoury-crate"
BIN_SRC="$STAGING_DIR/armoury-crate"
DESKTOP_SRC="$STAGING_DIR/io.github.armourycrate.desktop"
ICON_SRC="$STAGING_DIR/armoury-crate.svg"
APP_ICON_SRC="$STAGING_DIR/assets/asus_armourycrate_icon.png"
ASSET_SRC="$STAGING_DIR/assets"

BIN_DST="$HOME/.local/bin/armoury-crate"
DESKTOP_DST="$HOME/.local/share/applications/io.github.armourycrate.desktop"
APP_ICON_DST="$HOME/.local/share/icons/hicolor/48x48/apps/armoury-crate.png"
ASSET_DST="$HOME/.local/share/armoury-crate/assets"
LEGACY_ASSET_DST="$HOME/.local/share/armoury-fedora/assets"
ICON_DST="$HOME/.local/share/icons/hicolor/scalable/apps/armoury-crate.svg"
LEGACY_BIN_DST="$HOME/.local/bin/armoury-fedora"
LEGACY_DESKTOP_DST="$HOME/.local/share/applications/armoury-fedora.desktop"
LEGACY_ICON_DST="$HOME/.local/share/icons/hicolor/scalable/apps/armoury-fedora.svg"

usage() {
    echo "Usage: $0 {install|uninstall}"
    exit 1
}

install_files() {
    for f in "$BIN_SRC" "$DESKTOP_SRC" "$ICON_SRC"; do
        if [ ! -f "$f" ]; then
            echo "Missing staged file: $f"
            exit 1
        fi
    done
    mkdir -p "$(dirname "$BIN_DST")" "$(dirname "$DESKTOP_DST")" "$(dirname "$APP_ICON_DST")" "$(dirname "$ICON_DST")" "$ASSET_DST"
    install -m 755 "$BIN_SRC" "$BIN_DST"
    sed "s|^Exec=.*|Exec=$BIN_DST|" "$DESKTOP_SRC" > "$DESKTOP_DST"
    if [ -f "$APP_ICON_SRC" ]; then
        install -m 644 "$APP_ICON_SRC" "$APP_ICON_DST"
        rm -f "$ICON_DST"
    else
        install -m 644 "$ICON_SRC" "$ICON_DST"
        rm -f "$APP_ICON_DST"
    fi
    if [ -d "$LEGACY_ASSET_DST" ] && [ ! -d "$ASSET_DST" ]; then
        mkdir -p "$(dirname "$ASSET_DST")"
        cp -a "$LEGACY_ASSET_DST" "$ASSET_DST"
    fi
    if [ -d "$ASSET_SRC" ]; then
        cp -a "$ASSET_SRC/." "$ASSET_DST/"
    fi
    rm -f "$LEGACY_BIN_DST" "$LEGACY_DESKTOP_DST" "$LEGACY_ICON_DST"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications"
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache --force --ignore-theme-index "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
    fi
    echo "Installed to ~/.local"
}

uninstall_files() {
    rm -f "$BIN_DST" "$DESKTOP_DST" "$APP_ICON_DST" "$ICON_DST" "$LEGACY_BIN_DST" "$LEGACY_DESKTOP_DST" "$LEGACY_ICON_DST"
    echo "Removed from ~/.local"
}

case "${1:-}" in
    install) install_files ;;
    uninstall) uninstall_files ;;
    *) usage ;;
esac
