#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '\n' < "$ROOT_DIR/VERSION")"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.+~-][0-9A-Za-z.-]+)?$ ]] || {
    echo "Invalid or missing release version: $VERSION" >&2
    exit 1
}
OUTPUT_DIR="${1:-$ROOT_DIR/dist}"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

for command_name in rpmbuild dpkg-deb; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "Missing required build tool: $command_name" >&2
        exit 1
    fi
done

install -d "$OUTPUT_DIR"

DEB_ROOT="$BUILD_DIR/deb"
install -d "$DEB_ROOT/DEBIAN" "$DEB_ROOT/usr/bin" \
    "$DEB_ROOT/usr/share/applications" \
    "$DEB_ROOT/usr/share/armoury-crate" \
    "$DEB_ROOT/usr/share/icons/hicolor/scalable/apps"
install -m 0644 "$ROOT_DIR/packaging/debian/control" "$DEB_ROOT/DEBIAN/control"
sed -i "s/^Version:.*/Version: $VERSION/" "$DEB_ROOT/DEBIAN/control"
install -m 0755 "$ROOT_DIR/armoury-crate" "$DEB_ROOT/usr/bin/armoury-crate"
cp -a "$ROOT_DIR/src" "$DEB_ROOT/usr/share/armoury-crate/"
install -m 0644 "$ROOT_DIR/io.github.armourycrate.desktop" "$DEB_ROOT/usr/share/applications/"
install -m 0644 "$ROOT_DIR/armoury-crate.svg" "$DEB_ROOT/usr/share/icons/hicolor/scalable/apps/"
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$OUTPUT_DIR/armoury-crate_${VERSION}_all.deb"

RPM_TOP="$BUILD_DIR/rpm"
install -d "$RPM_TOP/BUILD" "$RPM_TOP/BUILDROOT" "$RPM_TOP/RPMS" "$RPM_TOP/SOURCES" "$RPM_TOP/SPECS" "$RPM_TOP/SRPMS"
install -m 0755 "$ROOT_DIR/armoury-crate" "$RPM_TOP/SOURCES/armoury-crate"
cp -a "$ROOT_DIR/src" "$RPM_TOP/SOURCES/"
install -m 0644 "$ROOT_DIR/io.github.armourycrate.desktop" "$RPM_TOP/SOURCES/io.github.armourycrate.desktop"
install -m 0644 "$ROOT_DIR/armoury-crate.svg" "$RPM_TOP/SOURCES/armoury-crate.svg"
rpmbuild -bb "$ROOT_DIR/packaging/rpm/armoury-crate.spec" \
    --define "_topdir $RPM_TOP" --define "_sourcedir $RPM_TOP/SOURCES" \
    --define "pkg_version $VERSION"
find "$RPM_TOP/RPMS" -type f -name '*.rpm' -exec cp -f {} "$OUTPUT_DIR/" \;

DEB_PACKAGE="$OUTPUT_DIR/armoury-crate_${VERSION}_all.deb"
RPM_PACKAGE="$(find "$OUTPUT_DIR" -maxdepth 1 -type f -name "armoury-crate-*.rpm" -print -quit)"
dpkg-deb --info "$DEB_PACKAGE" >/dev/null
[[ -n "$RPM_PACKAGE" ]] && rpm -qip "$RPM_PACKAGE" >/dev/null
test -f "$DEB_PACKAGE"

echo "Built packages in $OUTPUT_DIR"
