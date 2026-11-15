"""Dashboard page UI and interactions."""
import math
import os
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from config import *
from components.widgets import *
from hardware.asus import *
from hardware.system import *


class DashboardPage:
    def build_home(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("main-content")
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.add_css_class("ac-dashboard")
        content.set_margin_start(8)
        content.set_margin_end(8)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        toolbar.add_css_class("dashboard-toolbar")
        logo_path = os.path.join(ASSET_DIR, "asus_gc_landing_rog_logo.png")
        if os.path.isfile(logo_path):
            logo = Gtk.Picture.new_for_filename(logo_path)
            logo.set_content_fit(Gtk.ContentFit.CONTAIN)
            logo.set_size_request(105, 28)
            logo.set_halign(Gtk.Align.START)
            logo.set_valign(Gtk.Align.CENTER)
            logo.add_css_class("dashboard-brand-image")
            toolbar.append(logo)
        toolbar.append(Gtk.Box(hexpand=True))
        content.append(toolbar)

        system_strip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        system_strip.add_css_class("dashboard-system-strip")
        system_heading = label("System Information", "dashboard-module-title")
        system_heading.add_css_class("dashboard-system-heading")
        system_strip.append(system_heading)
        device_name = pretty_product_name(text("/sys/class/dmi/id/product_name", "ASUS laptop"))
        dgpu, igpu = gpu_names()
        system_details = (
            ("DEVICE", device_name, "computer-symbolic"),
            ("PROCESSOR", cpu_model(), "utilities-system-monitor-symbolic"),
            ("GRAPHICS", f"{igpu} · {dgpu}", "video-display-symbolic"),
            ("SYSTEM", f"{os_pretty_name()} · {os.uname().release}", "preferences-system-details-symbolic"),
        )
        system_details_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        for index, (title, value, icon_name) in enumerate(system_details):
            item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            item.add_css_class("dashboard-system-info-item")
            item.set_hexpand(True)
            item.append(label(title, "dashboard-info-label"))
            detail = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            detail.set_valign(Gtk.Align.CENTER)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(20)
            icon.add_css_class("dashboard-info-icon")
            detail.append(icon)
            info_value = label(value, "dashboard-info-value")
            info_value.set_ellipsize(2)
            detail.append(info_value)
            item.append(detail)
            system_details_row.append(item)
            if index < len(system_details) - 1:
                system_details_row.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        system_strip.append(system_details_row)
        content.append(system_strip)

        main_grid = Gtk.Grid(column_spacing=9, row_spacing=9)
        main_grid.set_hexpand(True)
        left_panel = self.dashboard_panel("CPU")
        left_panel.set_size_request(370, -1)
        left_panel.set_hexpand(False)
        self.cpu_temperature = None
        self.cpu_gauge = Gtk.DrawingArea()
        self.cpu_gauge.set_content_width(300)
        self.cpu_gauge.set_content_height(280)
        self.cpu_gauge.add_css_class("dashboard-cpu-gauge")
        self.cpu_gauge.set_draw_func(self.draw_dashboard_gauge)
        left_panel.append(self.cpu_gauge)
        self.dashboard_gauge_value = label("— °C", "dashboard-gauge-value")
        self.dashboard_gauge_value.set_halign(Gtk.Align.CENTER)
        left_panel.append(self.dashboard_gauge_value)
        cpu_usage_row, self.dashboard_cpu_usage, self.dashboard_cpu_usage_bar = self.dashboard_meter("CPU Usage")
        gpu_usage_row, self.dashboard_gpu_usage, self.dashboard_gpu_usage_bar = self.dashboard_meter("GPU Usage")
        left_panel.append(cpu_usage_row)
        left_panel.append(gpu_usage_row)
        main_grid.attach(left_panel, 0, 0, 1, 1)

        cards = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        cards.set_hexpand(True)
        self.dashboard_values = {}
        self.dashboard_bars = {}

        cpu_stats = self.dashboard_panel("CPU Stats")
        cpu_stats.add_css_class("dashboard-compact-module")
        cpu_stats.set_spacing(4)
        self.dashboard_stat(cpu_stats, "Frequency", "—", "cpu_frequency")
        self.dashboard_stat(cpu_stats, "Usage", "—", "cpu_usage")
        self.dashboard_stat(cpu_stats, "Temperature", "—", "cpu_temperature")
        cards.attach(cpu_stats, 0, 0, 1, 1)

        gpu_stats = self.dashboard_panel("GPU Stats")
        gpu_stats.add_css_class("dashboard-compact-module")
        gpu_stats.set_spacing(4)
        self.dashboard_stat(gpu_stats, "Temperature", "—", "gpu_temperature")
        self.dashboard_stat(gpu_stats, "Usage", "Unavailable", "gpu_usage")
        cards.attach(gpu_stats, 1, 0, 1, 1)

        fans = self.dashboard_panel("Fan Speed")
        fans.add_css_class("dashboard-compact-module")
        fans.set_spacing(4)
        self.dashboard_fan_bars = {}
        cpu_fan_box = self.dashboard_metric_panel("CPU Fan", "ic_fan.svg", "cpu_fan")
        gpu_fan_box = self.dashboard_metric_panel("GPU Fan", "ic_fan_alt.svg", "gpu_fan")
        fans.append(cpu_fan_box)
        fans.append(Gtk.Separator())
        fans.append(gpu_fan_box)
        cards.attach(fans, 2, 0, 1, 1)

        shortcuts = self.dashboard_panel("App Configuration")
        shortcut_items = (
            ("Aura Sync", "lighting", "ic_lighting.svg", "preferences-desktop-display-symbolic"),
            ("Battery Care", "battery", None, "battery-symbolic"),
        )
        for title, page, icon_file, fallback_icon in shortcut_items:
            shortcut = Gtk.Button()
            shortcut.add_css_class("dashboard-action-button")
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.set_halign(Gtk.Align.FILL)
            icon = asus_image(icon_file, fallback_icon, 20)
            if icon is not None:
                row.append(icon)
            row.append(label(title, "dashboard-action-label"))
            row.append(Gtk.Box(hexpand=True))
            row.append(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            shortcut.set_child(row)
            shortcut.set_hexpand(True)
            shortcut.connect("clicked", self.on_dashboard_navigate, page)
            shortcuts.append(shortcut)
        cards.attach(shortcuts, 0, 2, 1, 1)

        battery = self.dashboard_panel("Battery Care")
        self.dashboard_battery_value = label("—", "dashboard-value-large")
        battery.append(self.dashboard_battery_value)
        self.dashboard_battery_bar = Gtk.LevelBar.new_for_interval(0, 100)
        self.dashboard_battery_bar.add_css_class("dashboard-battery-meter")
        battery.append(self.dashboard_battery_bar)
        self.dashboard_battery_eta = label("Time estimate unavailable", "dashboard-tiny")
        battery.append(self.dashboard_battery_eta)
        cards.attach(battery, 1, 2, 1, 1)

        gpu_mode = self.dashboard_panel("GPU Mode")
        gpu_mode.set_vexpand(True)
        gpu_mode_center = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14, hexpand=True, vexpand=True)
        gpu_mode_center.set_halign(Gtk.Align.CENTER)
        gpu_mode_center.set_valign(Gtk.Align.CENTER)
        gpu_icon = asus_image("ic_gpu.svg", "video-display-symbolic", 42)
        if gpu_icon is not None:
            gpu_mode_center.append(gpu_icon)
        gpu_mode_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        gpu_mode_copy.set_valign(Gtk.Align.CENTER)
        self.dashboard_gpu_mode_value = label("Unavailable", "dashboard-value-large")
        gpu_mode_copy.append(self.dashboard_gpu_mode_value)
        gpu_mode_copy.append(label("Graphics profile", "dashboard-tiny"))
        gpu_mode_center.append(gpu_mode_copy)
        gpu_mode.append(gpu_mode_center)
        gpu_mode_button = Gtk.Button(label="Open GPU Mode")
        gpu_mode_button.add_css_class("dashboard-quick-button")
        gpu_mode_button.set_valign(Gtk.Align.END)
        gpu_mode_button.connect("clicked", self.on_dashboard_navigate, "gpu")
        gpu_mode.append(gpu_mode_button)
        cards.attach(gpu_mode, 2, 2, 1, 1)

        resources = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.dashboard_resource_values = {}
        for key, title in (("ram", "Memory"), ("storage", "Storage"), ("ssd", "SSD")):
            panel = self.dashboard_panel(title)
            value = label("—", "dashboard-stat-value")
            value.set_wrap(False)
            value.set_ellipsize(2)
            panel.append(value)
            bar = Gtk.LevelBar.new_for_interval(0, 100)
            bar.add_css_class("dashboard-meter")
            panel.append(bar)
            self.dashboard_resource_values[key] = value
            self.dashboard_bars[key] = bar
            panel.set_hexpand(True)
            resources.append(panel)
        cards.attach(resources, 0, 1, 3, 1)

        scenarios = self.dashboard_panel("Scenario Profiles")
        self.dashboard_profile_values = {}
        profile_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for name, _short, description in PROFILES:
            button = Gtk.Button()
            button.add_css_class("dashboard-profile-entry")
            button.set_hexpand(True)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
            symbol = label(PROFILE_SYMBOLS[name], "profile-symbol")
            symbol.set_halign(Gtk.Align.CENTER)
            symbol.set_valign(Gtk.Align.CENTER)
            row.append(symbol)
            profile_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            profile_copy.set_valign(Gtk.Align.CENTER)
            profile_copy.append(label(name, "profile-name"))
            profile_copy.append(label(description, "dashboard-tiny"))
            row.append(profile_copy)
            button.set_child(row)
            button.connect("clicked", self.on_profile_clicked, name)
            profile_row.append(button)
            self.dashboard_profile_values[name] = button
        scenarios.append(profile_row)
        cards.attach(scenarios, 0, 3, 3, 1)

        main_grid.attach(cards, 1, 0, 1, 1)
        content.append(main_grid)
        scroll.set_child(content)
        outer.append(scroll)
        return outer

    def dashboard_panel(self, title):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.add_css_class("dashboard-module")
        panel.append(label(title, "dashboard-module-title"))
        return panel

    def dashboard_stat(self, panel, title, initial, key):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("dashboard-stat-row")
        row.append(label(title, "dashboard-stat-name"))
        value = label(initial, "dashboard-stat-value")
        value.set_hexpand(True)
        value.set_halign(Gtk.Align.END)
        value.set_ellipsize(2)
        row.append(value)
        panel.append(row)
        self.dashboard_values[key] = value
        return value

    def dashboard_metric_panel(self, title, icon, key):
        panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        panel.add_css_class("dashboard-fan-metric")
        panel.set_hexpand(True)
        icon_image = asus_image(icon, "preferences-system-symbolic", 22)
        if icon_image is not None:
            panel.append(icon_image)
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        copy.set_hexpand(True)
        copy.append(label(title, "dashboard-stat-name"))
        value = label("— rpm", "dashboard-stat-value")
        copy.append(value)
        bar = Gtk.LevelBar.new_for_interval(0, 6000)
        bar.add_css_class("dashboard-fan-meter")
        bar.set_hexpand(True)
        copy.append(bar)
        panel.append(copy)
        self.dashboard_values[key] = value
        self.dashboard_fan_bars[key] = bar
        return panel

    def dashboard_meter(self, title):
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label_row.append(label(title, "dashboard-stat-name"))
        value = label("—", "dashboard-stat-value")
        value.set_hexpand(True)
        value.set_halign(Gtk.Align.END)
        label_row.append(value)
        row.append(label_row)
        bar = Gtk.LevelBar.new_for_interval(0, 100)
        bar.add_css_class("dashboard-meter")
        row.append(bar)
        return row, value, bar

    def draw_dashboard_gauge(self, _area, context, width, height):
        center_x = width / 2
        center_y = height * 0.50
        radius = min(width * 0.43, height * 0.45)
        value = max(0.0, min(100.0, self.cpu_temperature or 0.0))
        start_angle = math.radians(135)
        sweep = math.radians(270)
        end_angle = start_angle + sweep

        context.set_source_rgba(0.01, 0.025, 0.04, 0.7)
        context.arc(center_x, center_y, radius * 1.04, 0, math.tau)
        context.fill()
        for ring_radius, opacity, line_width in ((radius, .45, 1), (radius * .91, .18, 1), (radius * .73, .35, 2)):
            context.set_source_rgba(.48, .72, .87, opacity)
            context.set_line_width(line_width)
            context.arc(center_x, center_y, ring_radius, 0, math.tau)
            context.stroke()

        context.set_line_width(max(3, radius * .022))
        context.set_line_cap(1)
        context.set_source_rgba(.10, .26, .37, .9)
        context.arc(center_x, center_y, radius * .83, start_angle, end_angle)
        context.stroke()
        context.set_source_rgba(.97, .13, .34, .98)
        context.arc(center_x, center_y, radius * .83, start_angle, start_angle + sweep * value / 100)
        context.stroke()
        context.set_line_width(max(2, radius * .012))
        context.set_source_rgba(.12, .62, .92, .85)
        context.arc(center_x, center_y, radius * .69, start_angle, end_angle)
        context.stroke()

        context.select_font_face("Cantarell", 0, 1)
        for tick in range(41):
            angle = start_angle + sweep * tick / 40
            major = tick % 5 == 0
            inner_radius = radius * (.91 if major else .945)
            context.set_line_width(2 if major else 1)
            context.set_source_rgba(.82, .89, .96, .92 if major else .55)
            context.move_to(center_x + inner_radius * math.cos(angle), center_y + inner_radius * math.sin(angle))
            context.line_to(center_x + radius * .97 * math.cos(angle), center_y + radius * .97 * math.sin(angle))
            context.stroke()
            if major:
                context.set_font_size(max(9, radius * .065))
                context.move_to(center_x + radius * .79 * math.cos(angle) - 6, center_y + radius * .79 * math.sin(angle) + 4)
                context.show_text(str(round(tick * 2.5 / 10)))

        needle_angle = start_angle + sweep * value / 100
        context.set_line_width(max(2, radius * .012))
        context.set_source_rgba(.9, .96, 1, .95)
        context.move_to(center_x, center_y)
        context.line_to(center_x + radius * .70 * math.cos(needle_angle), center_y + radius * .70 * math.sin(needle_angle))
        context.stroke()
        context.set_source_rgba(.94, .97, 1, .95)
        context.arc(center_x, center_y, radius * .045, 0, math.tau)
        context.fill()
        context.set_source_rgba(.8, .88, .95, .9)
        context.set_font_size(max(11, radius * .08))
        context.move_to(center_x - radius * .08, center_y + radius * .32)
        context.show_text("CPU")

    def on_dashboard_navigate(self, _button, page):
        self.nav_buttons[page].set_active(True)
