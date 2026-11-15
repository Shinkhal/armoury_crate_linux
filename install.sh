#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LEGACY_INSTALLER="$SCRIPT_DIR/install-armoury-crate.sh"

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

read_os_release() {
    if [[ -r /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
    else
        ID=unknown
    fi
}

detect_package_family() {
    local family="${ID_LIKE:-} $ID"
    if [[ -e /run/ostree-booted ]] && command -v rpm-ostree >/dev/null 2>&1; then
        PKG_FAMILY=ostree
        return
    fi
    case "$family" in
        *debian*|*ubuntu*) PKG_FAMILY=debian ;;
        *fedora*|*rhel*|*centos*) PKG_FAMILY=fedora ;;
        *arch*) PKG_FAMILY=arch ;;
        *suse*) PKG_FAMILY=suse ;;
        *alpine*) PKG_FAMILY=alpine ;;
        *void*) PKG_FAMILY=void ;;
        *gentoo*) PKG_FAMILY=gentoo ;;
        *solus*) PKG_FAMILY=solus ;;
        *nixos*) PKG_FAMILY=nix ;;
        *)
            if command -v apt-get >/dev/null 2>&1; then PKG_FAMILY=debian
            elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then PKG_FAMILY=fedora
            elif command -v pacman >/dev/null 2>&1; then PKG_FAMILY=arch
            elif command -v zypper >/dev/null 2>&1; then PKG_FAMILY=suse
            elif command -v apk >/dev/null 2>&1; then PKG_FAMILY=alpine
            elif command -v xbps-install >/dev/null 2>&1; then PKG_FAMILY=void
            elif command -v emerge >/dev/null 2>&1; then PKG_FAMILY=gentoo
            elif command -v eopkg >/dev/null 2>&1; then PKG_FAMILY=solus
            elif command -v nix >/dev/null 2>&1; then PKG_FAMILY=nix
            else PKG_FAMILY=unknown
            fi
            ;;
    esac
}

check_asus_hardware() {
    local vendor=""
    local product=""
    [[ -r /sys/class/dmi/id/sys_vendor ]] && vendor="$(< /sys/class/dmi/id/sys_vendor)"
    [[ -r /sys/class/dmi/id/product_name ]] && product="$(< /sys/class/dmi/id/product_name)"
    if [[ ! "$vendor $product" =~ (ASUS|ASUSTeK|ROG|TUF) ]]; then
        printf 'This app is designed for ASUS laptops. Detected system: %s %s\n' "${vendor:-unknown vendor}" "${product:-unknown model}" >&2
        printf 'The app may open, but ASUS controls may not work on this computer.\n' >&2
        read -r -p 'Continue anyway? [y/N] ' answer
        [[ "$answer" =~ ^[Yy]$ ]] || exit 1
    else
        printf 'Detected ASUS-compatible system: %s %s\n' "${vendor:-ASUS}" "${product:-unknown model}"
    fi
}

check_source_files() {
    [[ -x "$LEGACY_INSTALLER" ]] || fail "Missing executable installer: $LEGACY_INSTALLER"
    [[ -x "$SCRIPT_DIR/armoury-crate" ]] || fail "Missing app launcher: $SCRIPT_DIR/armoury-crate"
    [[ -d "$SCRIPT_DIR/src" ]] || fail "Missing application source directory: $SCRIPT_DIR/src"
    [[ -f "$SCRIPT_DIR/io.github.armourycrate.desktop" ]] || fail "Missing desktop entry."
    [[ -f "$SCRIPT_DIR/armoury-crate.svg" ]] || fail "Missing application icon."
}

check_python_gtk() {
    command -v python3 >/dev/null 2>&1 || return 1
    python3 - <<'PY' >/dev/null 2>&1
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
PY
}

missing_runtime_packages() {
    local -a candidates=()
    local -a commands=(asusctl supergfxctl lspci ps)
    local command_name
    for command_name in "${commands[@]}"; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            case "$command_name:$PKG_FAMILY" in
                lspci:gentoo) candidates+=(sys-apps/pciutils) ;;
                ps:gentoo) candidates+=(sys-process/procps) ;;
                lspci:*) candidates+=(pciutils) ;;
                ps:*) candidates+=(procps) ;;
                *) candidates+=("$command_name") ;;
            esac
        fi
    done
    if ! command -v python3 >/dev/null 2>&1; then candidates+=(python3); fi
    if ! check_python_gtk; then
        case "$PKG_FAMILY" in
            debian) candidates+=(python3-gi gir1.2-gtk-4.0 gir1.2-adw-1) ;;
            fedora) candidates+=(python3-gobject gtk4 libadwaita) ;;
            arch) candidates+=(python-gobject gtk4 libadwaita) ;;
            suse) candidates+=(python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1) ;;
            alpine) candidates+=(py3-gobject3 gtk4 libadwaita) ;;
            void) candidates+=(python3-gobject gtk4 libadwaita) ;;
            gentoo) candidates+=(dev-python/pygobject gui-libs/gtk gui-libs/libadwaita) ;;
            solus) candidates+=(python3-gobject gtk4 libadwaita) ;;
            nix) candidates+=(python3Packages.pygobject3 gtk4 libadwaita) ;;
            *) candidates+=(python3-gi gir1.2-gtk-4.0 gir1.2-adw-1) ;;
        esac
    fi
    if ((${#candidates[@]})); then
        printf '%s\n' "${candidates[@]}" | awk '!seen[$0]++'
    fi
}

install_packages() {
    local -a packages=("$@")
    ((${#packages[@]})) || return 0

    printf 'Missing runtime packages: %s\n' "${packages[*]}"
    printf 'The installer can use your configured repositories to install them.\n'
    read -r -p 'Install these packages now? [Y/n] ' answer
    [[ "$answer" =~ ^[Nn]$ ]] && fail "Install the listed dependencies, then run ./install.sh again."

    local -a privilege=()
    if ((EUID != 0)); then
        command -v sudo >/dev/null 2>&1 || fail "sudo is required to install system packages. Install dependencies manually and rerun ./install.sh."
        privilege=(sudo)
    fi

    case "$PKG_FAMILY" in
        debian)
            command -v apt-get >/dev/null 2>&1 || fail "apt-get was not found."
            "${privilege[@]}" apt-get install -y "${packages[@]}"
            ;;
        fedora)
            local manager=dnf
            command -v dnf >/dev/null 2>&1 || manager=yum
            command -v "$manager" >/dev/null 2>&1 || fail "dnf or yum was not found."
            if [[ "$ID" == fedora && (" ${packages[*]} " == *" asusctl "* || " ${packages[*]} " == *" supergfxctl "*) ]]; then
                printf '\nThe ASUS Linux guide uses the Terra repository to provide ASUS control tools on Fedora.\n'
                printf 'Enabling it adds a third-party package source and its signing keys to this system.\n'
                read -r -p 'Add the Terra repository and install the missing packages? [y/N] ' answer
                [[ "$answer" =~ ^[Yy]$ ]] || fail "Enable the ASUS Linux/Terra repository manually, install asusctl and supergfxctl, then rerun ./install.sh."
                "${privilege[@]}" dnf install --nogpgcheck --repofrompath "terra,https://repos.fyralabs.com/terra\$releasever" terra-release
            fi
            "${privilege[@]}" "$manager" install -y "${packages[@]}"
            ;;
        ostree)
            command -v rpm-ostree >/dev/null 2>&1 || fail "rpm-ostree was not found."
            "${privilege[@]}" rpm-ostree install "${packages[@]}"
            printf 'Layered packages will be available after reboot.\n'
            ;;
        arch)
            command -v pacman >/dev/null 2>&1 || fail "pacman was not found."
            if [[ " ${packages[*]} " == *" asusctl "* ]] && ! grep -q '^\[ogc\]' /etc/pacman.conf; then
                printf '\nThe ASUS Linux Arch guide recommends the signed OGC package repository.\n'
                read -r -p 'Add the OGC repository and its signing key? [y/N] ' answer
                [[ "$answer" =~ ^[Yy]$ ]] || fail "Configure the OGC repository manually, then rerun ./install.sh."
                "${privilege[@]}" pacman-key --recv-keys F79100EF8C802DAB81C323BB8EEA5962FE510E19
                "${privilege[@]}" pacman-key --lsign-key F79100EF8C802DAB81C323BB8EEA5962FE510E19
                "${privilege[@]}" sh -c 'printf "\n[ogc]\nServer = https://pacman.opengamingcollective.org\n" >> /etc/pacman.conf'
            fi
            local -a pacman_packages=()
            local needs_aur_supergfx=false
            for package in "${packages[@]}"; do
                if [[ "$package" == supergfxctl ]] && ((EUID != 0)) && { command -v paru >/dev/null 2>&1 || command -v yay >/dev/null 2>&1; }; then
                    needs_aur_supergfx=true
                else
                    pacman_packages+=("$package")
                fi
            done
            ((${#pacman_packages[@]} == 0)) || "${privilege[@]}" pacman -S --needed --noconfirm "${pacman_packages[@]}"
            if [[ "$needs_aur_supergfx" == true ]]; then
                if command -v paru >/dev/null 2>&1; then paru -S --needed --noconfirm supergfxctl
                else yay -S --needed --noconfirm supergfxctl
                fi
            fi
            ;;
        suse)
            command -v zypper >/dev/null 2>&1 || fail "zypper was not found."
            "${privilege[@]}" zypper --non-interactive install "${packages[@]}"
            ;;
        alpine)
            command -v apk >/dev/null 2>&1 || fail "apk was not found."
            "${privilege[@]}" apk add "${packages[@]}"
            ;;
        void)
            command -v xbps-install >/dev/null 2>&1 || fail "xbps-install was not found."
            "${privilege[@]}" xbps-install -Sy "${packages[@]}"
            ;;
        gentoo)
            command -v emerge >/dev/null 2>&1 || fail "emerge was not found."
            "${privilege[@]}" emerge --ask "${packages[@]}"
            ;;
        solus)
            command -v eopkg >/dev/null 2>&1 || fail "eopkg was not found."
            "${privilege[@]}" eopkg install "${packages[@]}"
            ;;
        nix)
            fail "NixOS manages system services declaratively. Add asusctl and supergfxctl to your NixOS configuration and enable their services, then rerun ./install.sh."
            ;;
        *)
            fail "No supported package manager was detected for '$ID'. Install GTK 4, libadwaita, PyGObject, pciutils, procps, asusctl and supergfxctl with your distro's package manager, then rerun ./install.sh."
            ;;
    esac
}

verify_runtime() {
    local missing=()
    local command_name
    for command_name in asusctl supergfxctl lspci ps; do
        command -v "$command_name" >/dev/null 2>&1 || missing+=("$command_name")
    done
    ((${#missing[@]} == 0)) || fail "Required commands are still unavailable: ${missing[*]}. Install both ASUS control tools from the repositories or instructions for your distribution, then rerun ./install.sh. See https://asus-linux.org/guides/ and https://github.com/OpenGamingCollective/asusctl."
    check_python_gtk || fail "GTK 4, libadwaita, or PyGObject is unavailable to python3 after dependency installation."
}

read_os_release
[[ "$(uname -s)" == Linux ]] || fail "This application requires Linux."
detect_package_family
check_source_files
check_asus_hardware

mapfile -t missing_packages < <(missing_runtime_packages)
install_packages "${missing_packages[@]}"
verify_runtime

"$LEGACY_INSTALLER" install
printf '\nInstallation complete. Launch Armoury Crate from your app menu or run: ~/.local/bin/armoury-crate\n'
