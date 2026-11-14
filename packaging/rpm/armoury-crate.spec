Name:           armoury-crate
Version:        %{pkg_version}
Release:        1
Summary:        GTK control center for supported ASUS laptops
License:        MIT
URL:            https://github.com/Shinkhal/armoury_crate_linux
BuildArch:      noarch
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       asusctl
Requires:       supergfxctl
Requires:       pciutils

%description
Community-built Armoury Crate-inspired controls for Linux, including ASUS
profiles, battery limits, keyboard lighting and GPU mode management.

%prep

%build

%install
install -Dpm 0755 %{_sourcedir}/armoury-crate %{buildroot}%{_bindir}/armoury-crate
install -Dpm 0644 %{_sourcedir}/io.github.armourycrate.desktop %{buildroot}%{_datadir}/applications/io.github.armourycrate.desktop
install -Dpm 0644 %{_sourcedir}/armoury-crate.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/armoury-crate.svg

%files
%{_bindir}/armoury-crate
%{_datadir}/applications/io.github.armourycrate.desktop
%{_datadir}/icons/hicolor/scalable/apps/armoury-crate.svg

%changelog
* Sat Nov 14 2026 Shinkhal Sinha <shinkhalsinha@gmail.com> - 0.1.0-1
- Initial package
