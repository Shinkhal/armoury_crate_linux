"""Device-level System Configuration page modeled on Armoury Crate."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, Gtk

from components.widgets import label


class SystemConfigurationPage:
    _CARDS = (
        ("Win Key", "keyboard-windows-symbolic", "Windows key behavior", False),
        ("ROG Key", "starred-symbolic", "Dedicated hardware key", False),
        ("Normal Function key", "keyboard-symbolic", "F1–F12 keys use their normal function", False),
        ("Touch Pad", "input-touchpad-symbolic", "Enable or disable the touchpad", True),
        ("Boot Up Sound", "audio-speakers-symbolic", "Startup sound", False),
        ("Modern Standby Assistant", "weather-clear-night-symbolic", "Suspend and battery behavior", False),
        ("Panel Power Saver", "video-display-symbolic", "Lower display refresh rate on battery", False),
        ("Power mode synchronization", "power-profile-balanced-symbolic", "Sync desktop power mode with ASUS profile", False),
    )

    def _tab(self, title, destination, selected=False):
        button = Gtk.Button(label=title)
        button.add_css_class("system-config-tab")
        if selected:
            button.add_css_class("selected")
        button.connect("clicked", self._on_tab_clicked, destination)
        return button

    def _on_tab_clicked(self, _button, destination):
        self.system_config_stack.set_visible_child_name(destination)
        for name, button in self.system_config_tabs.items():
            button.remove_css_class("selected")
            if name == destination:
                button.add_css_class("selected")

    def _config_card(self, title, icon_name, description, supported):
        button = Gtk.Button()
        button.add_css_class("system-config-card")
        if not supported:
            button.add_css_class("unavailable")
            button.set_tooltip_text("This Windows control is not exposed by the current Linux firmware")
        button.connect("clicked", self._on_config_card_clicked, title, supported)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.set_halign(Gtk.Align.CENTER)
        artwork = Gtk.Box()
        artwork.add_css_class("system-config-artwork")
        artwork.set_size_request(74, 74)
        artwork.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(42)
        icon.add_css_class("system-config-icon")
        artwork.append(icon)
        body.append(artwork)
        name = label(title, "system-config-title")
        name.set_xalign(.5)
        body.append(name)
        detail = label(description, "system-config-description")
        detail.set_xalign(.5)
        detail.set_justify(Gtk.Justification.CENTER)
        detail.set_wrap(True)
        body.append(detail)
        status = label("Unavailable on Linux", "system-config-status")
        status.set_xalign(.5)
        body.append(status)
        if title == "Touch Pad":
            settings = Gio.Settings.new("org.gnome.desktop.peripherals.touchpad")
            status.set_text("Enabled" if settings.get_string("send-events") != "disabled" else "Disabled")
            self.touchpad_status = status
        button.set_child(body)
        return button

    def _on_config_card_clicked(self, _button, title, supported):
        if title == "Touch Pad":
            settings = Gio.Settings.new("org.gnome.desktop.peripherals.touchpad")
            enabled = settings.get_string("send-events") != "disabled"
            settings.set_string("send-events", "disabled" if enabled else "enabled")
            state = "Disabled" if enabled else "Enabled"
            self.touchpad_status.set_text(state)
            self.toast(f"Touchpad {state.lower()}")
            return
        if supported:
            self.toast(f"{title} applied")
        else:
            self.toast(f"{title} is not exposed by this laptop's Linux firmware")

    def build_system_configuration(self):
        outer, content = self.page_shell(
            "DEVICE SETTINGS", "System Configuration",
            "Device controls exposed by your laptop firmware and Linux services.",
        )
        tabs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tabs.add_css_class("system-config-tabs")
        self.system_config_tabs = {}
        for title, destination, selected in (
            ("Slash Lighting", "slash", False),
            ("System Configuration", "system", True),
            ("GPU Performance", "gpu", False),
            ("Lighting", "lighting", False),
            ("Audio", "audio", False),
            ("•••", "more", False),
        ):
            tab = self._tab(title, destination, selected)
            tabs.append(tab)
            self.system_config_tabs[destination] = tab
        content.append(tabs)

        self.system_config_stack = Gtk.Stack()
        self.system_config_stack.set_vexpand(True)

        grid = Gtk.Grid()
        grid.add_css_class("system-config-grid")
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)
        grid.set_column_spacing(14)
        grid.set_row_spacing(14)
        for index, card_data in enumerate(self._CARDS):
            grid.attach(self._config_card(*card_data), index % 4, index // 4, 1, 1)
        self.system_config_stack.add_named(grid, "system")
        slash = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        slash.append(label("SLASH LIGHTING", "eyebrow"))
        slash.append(label("Slash lighting", "page-title"))
        slash.append(label("This laptop does not expose an ASUS Slash light bar. The control is unavailable on this device.", "subtle"))
        self.system_config_stack.add_named(slash, "slash")
        self.system_config_stack.add_named(self.build_gpu(), "gpu")
        self.system_config_stack.add_named(self.build_lighting(), "lighting")
        audio = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        audio.append(label("AUDIO", "eyebrow"))
        audio.append(label("Audio controls", "page-title"))
        audio.append(label("PipeWire controls will appear here when an audio backend is available.", "subtle"))
        self.system_config_stack.add_named(audio, "audio")
        more = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        more.append(label("MORE DEVICE SETTINGS", "eyebrow"))
        more.append(label("No additional Linux controls detected", "page-title"))
        self.system_config_stack.add_named(more, "more")
        content.append(self.system_config_stack)
        return outer
