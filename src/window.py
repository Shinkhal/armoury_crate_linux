"""Main application shell, navigation, and cross-page state."""
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from config import (
    ASSET_DIR, GPU_MODES, PPD_IFACE, PPD_NAME, PPD_PATH, PROFILE_IDS,
)
from components.widgets import asus_image, label, page_heading
from hardware.asus import command, fan_hwmon, fan_read, get_prop, read_limit, read_profile, rpm, set_prop
from hardware.system import (
    cpu_freq_ghz, cpu_model, cpu_usage_percent, disk_usage, gpu_names,
    gpu_usage_percent, os_pretty_name, pretty_product_name, read_disks,
    read_memory, read_thermal, text,
)
from styles import CSS
from pages.dashboard import DashboardPage
from pages.device import DevicePage
from pages.cooling import CoolingPage
from pages.battery import BatteryPage
from pages.lighting import LightingPage
from pages.gpu import GpuPage


class ArmouryWindow(
    DashboardPage,
    DevicePage,
    CoolingPage,
    BatteryPage,
    LightingPage,
    GpuPage,
    Gtk.ApplicationWindow,
):
    def __init__(self, app):
        super().__init__(application=app, title="Armoury Crate")
        self.set_default_size(1600, 900)
        self.set_size_request(850, 620)
        self.toast_overlay = Adw.ToastOverlay()
        self.set_child(self.toast_overlay)
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.toast_overlay.set_child(root)
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.sidebar.set_size_request(250, -1)
        self.sidebar.add_css_class("sidebar")
        root.append(self.sidebar)
        self.sidebar_collapsed = False
        self.sidebar_labels = []
        self.sidebar_compact_hidden = []
        self.sidebar_nav_boxes = []
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=160)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.nav_buttons = {}
        self.pending_profile = None
        root.append(self.stack)
        # Single headerbar for the whole app: app title centered,
        # live status and refresh at the end. Minimize/maximize/close follow
        # the system's gtk-decoration-layout setting (theme + extensions).
        header = Adw.HeaderBar()
        self.header_title = label("Armoury Crate", "header-title")
        self.header_title.set_wrap(False)
        self.header_title.set_ellipsize(0)
        header.set_title_widget(self.header_title)
        self.clock_status = label("●  SYSTEM CONNECTED", "status-dot")
        end_box = Gtk.Box(spacing=8)
        end_box.set_valign(Gtk.Align.CENTER)
        end_box.append(self.clock_status)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh status")
        refresh.connect("clicked", self.on_refresh)
        end_box.append(refresh)
        header.pack_end(end_box)
        self.set_titlebar(header)
        self.build_pages()
        GLib.timeout_add_seconds(4, self.refresh_timer)
        self.refresh()

    def add_page(self, name, title, icon_file, fallback_icon, builder):
        button = Gtk.ToggleButton()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.FILL)
        icon = asus_image(icon_file, fallback_icon, 16)
        if icon is not None:
            box.append(icon)
        nav_label = Gtk.Label(label=title, xalign=0)
        box.append(nav_label)
        button.set_child(box)
        button.set_tooltip_text(title)
        button.add_css_class("nav")
        button.connect("toggled", self.on_nav_toggled, name)
        self.sidebar.append(button)
        self.nav_buttons[name] = button
        self.sidebar_labels.append(nav_label)
        self.sidebar_nav_boxes.append(box)
        page = builder()
        self.stack.add_named(page, name)

    def build_pages(self):
        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        brand.add_css_class("sidebar-brand")
        menu = Gtk.ToggleButton(tooltip_text="Expand navigation")
        menu.add_css_class("sidebar-menu-button")
        menu_glyph = Gtk.DrawingArea()
        menu_glyph.set_content_width(18)
        menu_glyph.set_content_height(18)
        menu_glyph.set_draw_func(self.draw_sidebar_hamburger)
        menu.set_child(menu_glyph)
        menu.connect("toggled", self.on_sidebar_toggle)
        self.sidebar_menu_button = menu
        brand.append(menu)
        brand_logo_path = os.path.join(ASSET_DIR, "asus_gc_landing_rog_logo.png")
        if os.path.isfile(brand_logo_path):
            brand_logo = Gtk.Picture.new_for_filename(brand_logo_path)
            brand_logo.set_content_fit(Gtk.ContentFit.CONTAIN)
            brand_logo.set_size_request(72, 30)
            brand.append(brand_logo)
        brand_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        brand_text.append(label("ARMOURY CRATE", "sidebar-brand-name"))
        brand_text.append(label("REPUBLIC OF GAMERS", "sidebar-brand-subtitle"))
        brand.append(brand_text)
        self.sidebar_compact_hidden.extend([brand_logo if os.path.isfile(brand_logo_path) else None, brand_text])
        self.sidebar.append(brand)
        self.sidebar.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        section_label = label("DEVICE", "nav-section")
        device_label = label(pretty_product_name(text("/sys/class/dmi/id/product_name", "ASUS laptop")), "subtle")
        self.sidebar.append(section_label)
        self.sidebar.append(device_label)
        self.sidebar_labels.extend([section_label, device_label])
        self.sidebar.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.add_page("home", "Home", "ic_laptop.svg", "computer-symbolic", self.build_home)
        self.add_page("device", "Device", "ic_laptop.svg", "computer-symbolic", self.build_device)
        self.add_page("lighting", "Aura Sync", "ic_lighting.svg", "night-light-symbolic", self.build_lighting)
        self.add_page("cooling", "Scenario Profiles", "ic_fan_alt.svg", "preferences-system-symbolic", self.build_cooling)
        self.add_page("battery", "Battery", None, "battery-symbolic", self.build_battery)
        self.add_page("gpu", "GPU Mode", "ic_gpu.svg", "video-display-symbolic", self.build_gpu)
        self.nav_buttons["home"].set_active(True)
        self.sidebar.append(Gtk.Box(vexpand=True))
        footer = label("Live status · 4 sec refresh", "footer")
        self.sidebar.append(footer)
        self.sidebar_labels.append(footer)
        self.sidebar.set_margin_bottom(20)
        menu.set_active(True)

    def draw_sidebar_hamburger(self, _area, context, width, height):
        context.set_source_rgba(.88, .91, .96, .95)
        context.set_line_width(1.8)
        context.set_line_cap(1)
        for line in range(3):
            y = height * (.25 + line * .25)
            context.move_to(width * .17, y)
            context.line_to(width * .83, y)
        context.stroke()

    def on_sidebar_toggle(self, button):
        self.sidebar_collapsed = button.get_active()
        self.sidebar.set_size_request(68 if self.sidebar_collapsed else 250, -1)
        button.set_tooltip_text("Expand navigation" if self.sidebar_collapsed else "Collapse navigation")
        for widget in self.sidebar_labels + [w for w in self.sidebar_compact_hidden if w is not None]:
            widget.set_visible(not self.sidebar_collapsed)
        for nav_box in self.sidebar_nav_boxes:
            nav_box.set_halign(Gtk.Align.CENTER if self.sidebar_collapsed else Gtk.Align.FILL)

    def on_nav_toggled(self, button, name):
        if not button.get_active():
            return
        self.stack.set_visible_child_name(name)
        self.header_title.set_text("Armoury Crate")
        for key, other in self.nav_buttons.items():
            if key != name and other.get_active():
                other.set_active(False)

    def page_shell(self, kicker, title, subtitle):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("main-content")
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(28)
        content.set_margin_end(28)
        content.set_margin_top(16)
        content.set_margin_bottom(28)
        content.append(page_heading(kicker, title, subtitle))
        scroll.set_child(content)
        outer.append(scroll)
        return outer, content

    def toast(self, message):
        toast = Adw.Toast.new(" ".join(str(message).split())[:180])
        toast.set_timeout(4)
        self.toast_overlay.add_toast(toast)

    def update_profile_styles(self, active):
        for group in (getattr(self, "home_profile_buttons", {}), getattr(self, "cool_profile_buttons", {})):
            for name, button in group.items():
                if name == active:
                    button.add_css_class("active")
                else:
                    button.remove_css_class("active")
        for name, button in getattr(self, "dashboard_profile_values", {}).items():
            if name == active:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    def refresh(self):
        profile = read_profile()
        # While a profile change is still propagating through PPD/TuneD to the
        # firmware (~1s), show what the user asked for instead of stale state.
        if self.pending_profile is not None:
            profile = self.pending_profile
        self.update_profile_styles(profile)
        limit = read_limit()
        shown_limit = f"{limit}%" if limit is not None else "Not available"
        self.battery_status_value.set_text(shown_limit)
        if limit is not None:
            self.set_battery_mode(nearest_charge_limit(limit))
            if limit in CHARGE_LIMITS:
                self.limit_feedback.set_text(f"The system reports a {limit}% charge limit.")
            else:
                self.limit_feedback.set_text(
                    f"The system reports {limit}%; this firmware supports 60%, 80%, or 100%."
                )
        else:
            self.limit_feedback.set_text("No battery charge threshold was found. Check that asusctl and the ASUS kernel module are available.")
        hwmon = fan_hwmon()
        cpu = fan_read(hwmon, "fan1_input")
        gpu = fan_read(hwmon, "fan2_input")
        self.cpu_fan_value.set_text(rpm(cpu))
        self.gpu_fan_value.set_text(rpm(gpu))
        if hasattr(self, "dashboard_values"):
            cpu_temp = read_thermal("acpitz")
            gpu_temp = read_thermal("amdgpu")
            freq = cpu_freq_ghz()
            total_gb, free_gb, used_pct = disk_usage()
            cpu_usage = cpu_usage_percent()
            gpu_usage = gpu_usage_percent()
            self.cpu_temperature = cpu_temp
            self.cpu_gauge.queue_draw()
            self.dashboard_gauge_value.set_text(f"{cpu_temp:.0f} °C" if cpu_temp is not None else "— °C")
            self.dashboard_values["cpu_frequency"].set_text(f"{freq * 1000:.0f} MHz" if freq else "Unavailable")
            self.dashboard_values["cpu_usage"].set_text(f"{cpu_usage:.0f}%" if cpu_usage is not None else "Sampling…")
            self.dashboard_values["cpu_temperature"].set_text(f"{cpu_temp:.0f} °C" if cpu_temp is not None else "Unavailable")
            self.dashboard_cpu_usage.set_text(f"{cpu_usage:.0f}%" if cpu_usage is not None else "Sampling…")
            self.dashboard_cpu_usage_bar.set_value(cpu_usage or 0)
            self.dashboard_values["gpu_temperature"].set_text(f"{gpu_temp:.0f} °C" if gpu_temp is not None else "Unavailable")
            self.dashboard_values["gpu_usage"].set_text(f"{gpu_usage:.0f}%" if gpu_usage is not None else "Unavailable")
            self.dashboard_gpu_usage.set_text(f"{gpu_usage:.0f}%" if gpu_usage is not None else "Unavailable")
            self.dashboard_gpu_usage_bar.set_value(gpu_usage or 0)
            for key, speed in (("cpu_fan", cpu), ("gpu_fan", gpu)):
                self.dashboard_values[key].set_text(rpm(speed))
            self.dashboard_resource_values["storage"].set_text(f"{free_gb:.0f} GB free · {used_pct:.0f}% used")
            self.dashboard_bars["storage"].set_value(used_pct)
            memory_total, memory_available = read_memory()
            if memory_total is not None and memory_available is not None:
                memory_used = memory_total - memory_available
                memory_percent = memory_used / memory_total * 100 if memory_total else 0
                self.dashboard_resource_values["ram"].set_text(f"{memory_used / 1048576:.1f} / {memory_total / 1048576:.1f} GB")
                self.dashboard_bars["ram"].set_value(memory_percent)
            disk_models = read_disks()
            self.dashboard_resource_values["ssd"].set_text(" · ".join(disk_models) if disk_models else "Unavailable")
            self.dashboard_bars["ssd"].set_value(used_pct)
            self.dashboard_battery_value.set_text(f"{level}%" if (level := int_or_none(text("/sys/class/power_supply/BAT1/capacity", ""))) is not None else "—")
        level = int_or_none(text("/sys/class/power_supply/BAT1/capacity", ""))
        status = text("/sys/class/power_supply/BAT1/status", "Battery status unavailable")
        self.battery_level_value.set_text(f"{level}% · {status}" if level is not None else status)
        adapter_online = power_adapter_online()
        self.battery_power_value.set_text(
            "Plugged in" if adapter_online is True
            else "On battery" if adapter_online is False
            else "Status unavailable"
        )
        normalized_status = status.strip().lower()
        charge_state = {
            "charging": "Charging",
            "discharging": "Discharging",
            "not charging": "Not charging",
            "full": "Full",
        }.get(normalized_status, status)
        self.battery_charge_value.set_text(charge_state)
        self.battery_control_value.set_text("Firmware controlled")
        brightness = int_or_none(text("/sys/class/leds/asus::kbd_backlight/brightness", ""))
        if brightness is not None and 0 <= brightness < len(self.brightness_buttons):
            if not self.brightness_dirty:
                self.syncing_brightness = True
                for index, button in enumerate(self.brightness_buttons):
                    button.set_active(index == brightness)
                self.syncing_brightness = False
            if not self.brightness_dirty:
                brightness_label = ("Off", "Low", "Medium", "High")[brightness]
                self.brightness_feedback.set_text(
                    f"Current keyboard backlight: {brightness_label}."
                )
        gpu_mode = command(["supergfxctl", "-g"])
        self.gpu_current_value.set_text(gpu_mode.stdout.strip() if gpu_mode.returncode == 0 else "Unavailable")
        if hasattr(self, "dashboard_gpu_mode_value"):
            self.dashboard_gpu_mode_value.set_text(gpu_mode.stdout.strip() if gpu_mode.returncode == 0 else "Unavailable")
        current_mode = gpu_mode.stdout.strip() if gpu_mode.returncode == 0 else None
        if current_mode in GPU_MODES:
            self.gpu_dropdown.set_selected(GPU_MODES.index(current_mode))
        device_name = pretty_product_name(text("/sys/class/dmi/id/product_name", "ASUS laptop"))
        if hasattr(self, "hero_device"):
            self.hero_device.set_text(device_name)
        connected = get_prop("PlatformProfile") is not None
        self.clock_status.set_text("●  SYSTEM CONNECTED" if connected else "●  SYSTEM UNAVAILABLE")
        if connected:
            self.clock_status.remove_css_class("off")
        else:
            self.clock_status.add_css_class("off")
        return True

    def refresh_timer(self):
        self.refresh()
        return GLib.SOURCE_CONTINUE

    def on_refresh(self, _button):
        self.refresh()
        self.toast("Status refreshed")

    def on_profile_clicked(self, _button, name):
        # Prefer the desktop power-profiles daemon so TuneD (which also owns the
        # firmware platform profile applies the mode itself. This
        # keeps the selected fan mode from being overwritten a moment later.
        ppd_profile = {"Quiet": "power-saver", "Balanced": "balanced", "Performance": "performance"}.get(name)
        applied = False
        bus = system_bus()
        if bus is not None and ppd_profile is not None:
            try:
                # power-profiles-daemon has no SetActiveProfile method; the
                # supported way to switch is the ActiveProfile D-Bus property.
                bus.call_sync(PPD_NAME, PPD_PATH, "org.freedesktop.DBus.Properties", "Set",
                              GLib.Variant("(ssv)", (PPD_IFACE, "ActiveProfile", GLib.Variant("s", ppd_profile))), None,
                              Gio.DBusCallFlags.NONE, 5000, None)
                applied = True
            except GLib.Error:
                applied = False
        if not applied:
            result = command(["asusctl", "profile", "set", name])
            if result.returncode != 0:
                ok = set_prop("PlatformProfile", GLib.Variant("u", PROFILE_IDS[name]))
                if not ok:
                    self.toast(f"Could not select {name}: {(result.stderr or result.stdout).strip() or 'asusd unavailable'}")
                    self.refresh()
                    return
        # The firmware takes up to ~1s to report the new profile; highlight the
        # requested card now and confirm after the change has propagated.
        self.pending_profile = name
        self.update_profile_styles(name)
        self.refresh()
        GLib.timeout_add(1500, self.verify_profile, name)

    def verify_profile(self, name):
        self.pending_profile = None
        self.refresh()
        current = read_profile()
        if current == name:
            self.toast(f"{name} mode selected · ASUS firmware confirmed")
        else:
            self.toast(f"Requested {name}; system currently reports {current}")
        return False
