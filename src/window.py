"""Main application shell, navigation, and cross-page state."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from config import (
    CHARGE_LIMITS, PPD_IFACE, PPD_NAME, PPD_PATH,
    PROFILE_IDS, TELEMETRY_REFRESH_SECONDS,
)
from components.widgets import asus_image, label, page_heading
from hardware.asus import (
    command, fan_hwmon, fan_read, get_prop, int_or_none,
    nearest_charge_limit, power_adapter_online, read_limit, read_profile,
    rpm, set_prop, system_bus,
)
from hardware.system import (
    cpu_freq_ghz, cpu_max_freq_ghz, cpu_model, cpu_usage_percent, cpu_voltage_mv,
    disk_usage, gpu_memory_freq_mhz, gpu_names, gpu_power_watts, gpu_telemetry,
    gpu_usage_percent, gpu_voltage_mv, os_pretty_name, pretty_product_name,
    read_battery_state, read_memory, read_thermal, text,
    shutdown_telemetry,
)
from styles import CSS
from pages.dashboard import DashboardPage
from pages.device import DevicePage
from pages.battery import BatteryPage
from pages.lighting import LightingPage
from pages.gpu import GpuPage
from pages.system_configuration import SystemConfigurationPage

SIDEBAR_EXPANDED_WIDTH = 130
SIDEBAR_COLLAPSED_WIDTH = 68


class ArmouryWindow(
    DashboardPage,
    DevicePage,
    BatteryPage,
    LightingPage,
    GpuPage,
    SystemConfigurationPage,
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
        self.sidebar.set_size_request(SIDEBAR_EXPANDED_WIDTH, -1)
        self.sidebar.add_css_class("sidebar")
        root.append(self.sidebar)
        self.sidebar_collapsed = False
        self.sidebar_labels = []
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
        self.telemetry_timer_id = GLib.timeout_add_seconds(
            max(1, round(TELEMETRY_REFRESH_SECONDS)), self.refresh_timer
        )
        self.refresh()

    def do_close_request(self):
        """Cancel periodic callbacks before GTK tears down the window."""
        for attribute in ("telemetry_timer_id", "device_timer_id"):
            source_id = getattr(self, attribute, None)
            if source_id:
                GLib.source_remove(source_id)
                setattr(self, attribute, None)
        shutdown_telemetry()
        return False

    def add_page(self, name, title, icon_file, fallback_icon, builder):
        button = Gtk.ToggleButton()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.FILL)
        icon = asus_image(icon_file, fallback_icon, 14)
        if icon is not None:
            box.append(icon)
        nav_label = Gtk.Label(label=title, xalign=0)
        nav_label.set_wrap(False)
        nav_label.set_ellipsize(3)
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
        self.sidebar.append(brand)
        self.sidebar.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        section_label = label("DEVICE", "nav-section")
        device_label = label(pretty_product_name(text("/sys/class/dmi/id/product_name", "ASUS laptop")), "subtle")
        device_label.set_wrap(False)
        device_label.set_ellipsize(3)
        device_label.set_hexpand(True)
        self.sidebar.append(section_label)
        self.sidebar.append(device_label)
        self.sidebar_labels.extend([section_label, device_label])
        self.sidebar.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.add_page("home", "Home", "ic_laptop.svg", "computer-symbolic", self.build_home)
        self.add_page("device", "Device", "ic_laptop.svg", "computer-symbolic", self.build_device)
        self.add_page("system", "System Configuration", None, "preferences-system-symbolic", self.build_system_configuration)
        self.add_page("battery", "Battery", None, "battery-symbolic", self.build_battery)
        self.nav_buttons["home"].set_active(True)
        self.sidebar.append(Gtk.Box(vexpand=True))
        footer = label("Live status · 4 sec refresh", "footer")
        footer.set_wrap(False)
        footer.set_ellipsize(3)
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
        width = SIDEBAR_COLLAPSED_WIDTH if self.sidebar_collapsed else SIDEBAR_EXPANDED_WIDTH
        self.sidebar.set_size_request(width, -1)
        self.sidebar.set_spacing(12 if self.sidebar_collapsed else 6)
        button.set_tooltip_text("Expand navigation" if self.sidebar_collapsed else "Collapse navigation")
        for widget in self.sidebar_labels:
            widget.set_visible(not self.sidebar_collapsed)
        for nav_box in self.sidebar_nav_boxes:
            nav_box.set_halign(Gtk.Align.CENTER if self.sidebar_collapsed else Gtk.Align.FILL)

    def on_nav_toggled(self, button, name):
        if not button.get_active():
            return
        self.stack.set_visible_child_name(name)
        if name == "lighting" and hasattr(self, "refresh_lighting_state"):
            self.refresh_lighting_state()
        if name == "gpu" and hasattr(self, "refresh_gpu_state"):
            self.refresh_gpu_state()
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
        if hasattr(self, "cool_active_value"):
            self.cool_active_value.set_text(active or "Unavailable")
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
        gpu_fan = fan_read(hwmon, "fan2_input")
        if hasattr(self, "dashboard_values"):
            cpu_temp = read_thermal("acpitz")
            gpu = gpu_telemetry()
            gpu_temp = gpu["temperature"] or read_thermal("amdgpu") or read_thermal("nvidia")
            freq = cpu_freq_ghz()
            total_gb, free_gb, used_pct = disk_usage()
            cpu_usage = cpu_usage_percent()
            gpu_usage = gpu["usage"]
            self.cpu_temperature = cpu_temp
            self.cpu_gauge.queue_draw()
            self.dashboard_gauge_value.set_text(f"{cpu_temp:.0f} °C" if cpu_temp is not None else "— °C")
            max_freq = cpu_max_freq_ghz()
            freq_text = f"{freq * 1000:.0f} / {max_freq * 1000:.0f} MHz" if freq and max_freq else (f"{freq * 1000:.0f} MHz" if freq else "Unavailable")
            self.dashboard_values["cpu_frequency"].set_text(freq_text)
            self.dashboard_stat_meter_values["cpu_frequency"] = freq * 1000 if freq else None
            self.dashboard_stat_meters["cpu_frequency"].queue_draw()
            self.dashboard_values["cpu_usage"].set_text(f"{cpu_usage:.0f}%" if cpu_usage is not None else "Sampling…")
            self.dashboard_stat_meter_values["cpu_usage"] = cpu_usage
            self.dashboard_stat_meters["cpu_usage"].queue_draw()
            self.dashboard_values["cpu_temperature"].set_text(f"{cpu_temp:.0f} °C" if cpu_temp is not None else "Unavailable")
            cpu_voltage = cpu_voltage_mv()
            self.dashboard_values["cpu_voltage"].set_text(
                f"{cpu_voltage} mV" if cpu_voltage is not None else "Unavailable"
            )
            self.dashboard_cpu_usage.set_text(f"{cpu_usage:.0f}%" if cpu_usage is not None else "Sampling…")
            self.dashboard_stat_meter_values["cpu_usage_card"] = cpu_usage
            self.dashboard_cpu_usage_bar.queue_draw()
            self.dashboard_values["gpu_temperature"].set_text(f"{gpu_temp:.0f} °C" if gpu_temp is not None else "Unavailable")
            self.dashboard_values["gpu_usage"].set_text(f"{gpu_usage:.0f}%" if gpu_usage is not None else "Unavailable")
            self.dashboard_stat_meter_values["gpu_usage"] = gpu_usage
            self.dashboard_stat_meters["gpu_usage"].queue_draw()
            gpu_frequency = gpu["frequency"]
            self.dashboard_values["gpu_frequency"].set_text(
                f"{gpu_frequency:.0f} MHz" if gpu_frequency is not None else "Unavailable"
            )
            self.dashboard_stat_meter_values["gpu_frequency"] = gpu_frequency
            self.dashboard_stat_meters["gpu_frequency"].queue_draw()
            memory_frequency = gpu.get("memory_frequency") or (gpu_memory_freq_mhz() if gpu.get("vendor") == "amd" else None)
            self.dashboard_values["gpu_memory_frequency"].set_text(
                f"{memory_frequency} MHz" if memory_frequency is not None else "Unavailable"
            )
            gpu_voltage = gpu.get("voltage")
            self.dashboard_values["gpu_voltage"].set_text(
                f"{gpu_voltage} mV" if gpu_voltage is not None else "Unavailable"
            )
            gpu_power = gpu.get("power")
            vendor = gpu.get("vendor", "")
            power_label = "AMD PPT" if vendor == "amd" else "TGP"
            self.dashboard_values["gpu_tgp"].set_text(
                f"{gpu_power:.1f} W ({power_label})" if gpu_power is not None else "Unavailable"
            )
            self.dashboard_gpu_usage.set_text(f"{gpu_usage:.0f}%" if gpu_usage is not None else "Unavailable")
            self.dashboard_stat_meter_values["gpu_usage_card"] = gpu_usage
            self.dashboard_gpu_usage_bar.queue_draw()
            for key, speed in (("cpu_fan", cpu), ("gpu_fan", gpu_fan)):
                self.dashboard_values[key].set_text(rpm(speed))
                self.dashboard_fan_details[key].set_text(
                    f"{max(0, min(6000, speed)) / 60:.0f}% max" if speed is not None else "Fan speed unavailable"
                )
                self.dashboard_resource_usage[key] = (
                    max(0, min(6000, speed)) / 6000 if speed is not None else 0.0
                )
                self.dashboard_fan_gauges[key].queue_draw()
            memory_total, memory_available = read_memory()
            if memory_total is not None and memory_available is not None:
                memory_used = memory_total - memory_available
                memory_percent = memory_used / memory_total * 100 if memory_total else 0
                self.dashboard_resource_values["ram"].set_text(f"{memory_percent:.1f}%")
                self.dashboard_resource_details["ram"].set_text(
                    f"{memory_used / 1048576:.1f}/{memory_total / 1048576:.1f} GB"
                )
                self.dashboard_resource_usage["ram"] = memory_percent / 100
                self.dashboard_resource_meters["ram"].queue_draw()
            storage_used_gb = total_gb - free_gb
            self.dashboard_resource_values["storage"].set_text(f"{used_pct:.0f}%")
            self.dashboard_resource_details["storage"].set_text(
                f"{storage_used_gb:.1f}/{total_gb:.1f} GB"
            )
            self.dashboard_resource_usage["storage"] = used_pct / 100
            self.dashboard_resource_meters["storage"].queue_draw()
            battery_level, battery_status, battery_eta = read_battery_state()
            battery_label = f"{battery_level}% · {battery_status}" if battery_level is not None else "Unavailable"
            self.dashboard_battery_value.set_text(battery_label)
            self.dashboard_battery_level = battery_level
            self.dashboard_battery_icon.queue_draw()
            if battery_status == "Full":
                estimate_label = "Fully charged"
            elif battery_eta is None:
                estimate_label = "Time estimate unavailable"
            else:
                hours, minutes = divmod(battery_eta, 60)
                duration = f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
                suffix = "to full" if battery_status == "Charging" else "remaining"
                estimate_label = f"Estimated {duration} {suffix}"
            self.dashboard_battery_eta.set_text(estimate_label)
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
        if brightness is not None and 0 <= brightness <= 3 and hasattr(self, "brightness_scale"):
            self.syncing_brightness = True
            self.brightness_scale.set_value(brightness)
            self.syncing_brightness = False
            self.last_brightness_level = brightness
            brightness_label = ("Off", "Low", "Medium", "High")[brightness]
            self.brightness_value_label.set_text(f"{brightness_label} · {round(brightness * 100 / 3)}%")
            self.brightness_feedback.set_text(
                f"Current keyboard backlight: {brightness_label}."
            )
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
        # Use asusctl first so the ASUS profile manager applies its matching
        # power and fan policy. Fall back to the desktop profile service on
        # systems where asusd is unavailable.
        ppd_profile = {"Quiet": "power-saver", "Balanced": "balanced", "Performance": "performance"}.get(name)
        result = command(["asusctl", "profile", "set", name])
        applied = result.returncode == 0
        error = (result.stderr or result.stdout).strip()

        if not applied and ppd_profile is not None:
            bus = system_bus()
            if bus is not None:
                try:
                    # Power Profiles exposes ActiveProfile as a writable D-Bus
                    # property; there is no SetActiveProfile method.
                    bus.call_sync(PPD_NAME, PPD_PATH, "org.freedesktop.DBus.Properties", "Set",
                                  GLib.Variant("(ssv)", (PPD_IFACE, "ActiveProfile", GLib.Variant("s", ppd_profile))), None,
                                  Gio.DBusCallFlags.NONE, 5000, None)
                    applied = True
                except GLib.Error as dbus_error:
                    error = str(dbus_error)

        if not applied:
            applied = set_prop("PlatformProfile", GLib.Variant("u", PROFILE_IDS[name]))
        if not applied:
            self.toast(f"Could not select {name}: {error or 'ASUS profile service is unavailable'}")
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
