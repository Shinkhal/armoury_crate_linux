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
            logo.add_css_class("dashboard-brand-image")
            toolbar.append(logo)
        toolbar.append(Gtk.Box(hexpand=True))
        dgpu, _igpu = gpu_names()
        machine_specs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.dashboard_cpu_model = label(cpu_model(), "dashboard-machine-spec")
        self.dashboard_gpu_model = label(dgpu, "dashboard-machine-spec")
        machine_specs.append(self.dashboard_cpu_model)
        machine_specs.append(self.dashboard_gpu_model)
        toolbar.append(machine_specs)
        content.append(toolbar)

        main_grid = Gtk.Grid(column_spacing=9, row_spacing=9, column_homogeneous=True)
        left_panel = self.dashboard_panel("CPU")
        left_panel.set_size_request(340, 690)
        self.cpu_temperature = None
        self.cpu_gauge = Gtk.DrawingArea()
        self.cpu_gauge.set_content_width(320)
        self.cpu_gauge.set_content_height(380)
        self.cpu_gauge.set_vexpand(True)
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
        left_modes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        self.home_profile_buttons = {}
        for name, short, _description in PROFILES:
            mode_button = Gtk.Button(label=short)
            mode_button.add_css_class("dashboard-mode-button")
            mode_button.connect("clicked", self.on_profile_clicked, name)
            left_modes.append(mode_button)
            self.home_profile_buttons[name] = mode_button
        left_panel.append(left_modes)
        main_grid.attach(left_panel, 0, 0, 3, 5)

        cards = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        self.dashboard_values = {}
        self.dashboard_bars = {}

        cpu_stats = self.dashboard_panel("CPU Stats")
        self.dashboard_stat(cpu_stats, "Frequency", "—", "cpu_frequency")
        self.dashboard_stat(cpu_stats, "Usage", "—", "cpu_usage")
        self.dashboard_stat(cpu_stats, "Temperature", "—", "cpu_temperature")
        cards.attach(cpu_stats, 0, 0, 1, 2)

        gpu_stats = self.dashboard_panel("GPU Stats")
        self.dashboard_stat(gpu_stats, "Temperature", "—", "gpu_temperature")
        self.dashboard_stat(gpu_stats, "Usage", "Unavailable", "gpu_usage")
        cards.attach(gpu_stats, 0, 2, 1, 2)

        fans = self.dashboard_panel("Fan Speed")
        cpu_fan_box = self.dashboard_metric_panel("CPU Fan", "ic_fan.svg", "cpu_fan")
        gpu_fan_box = self.dashboard_metric_panel("GPU Fan", "ic_fan_alt.svg", "gpu_fan")
        fans.append(cpu_fan_box)
        fans.append(Gtk.Separator())
        fans.append(gpu_fan_box)
        cards.attach(fans, 1, 0, 1, 1)

        config = self.dashboard_panel("System Configuration")
        self.dashboard_stat(config, "BIOS", text("/sys/class/dmi/id/bios_version", "Unavailable"), "bios")
        self.dashboard_stat(config, "Kernel", os.uname().release, "kernel")
        self.dashboard_stat(config, "OS", os_pretty_name(), "os")
        cards.attach(config, 1, 1, 1, 2)

        shortcuts = self.dashboard_panel("App Configuration")
        for title, page in (("Aura Sync", "lighting"), ("Battery Care", "battery"), ("GPU Mode", "gpu")):
            shortcut = Gtk.Button(label=title)
            shortcut.add_css_class("dashboard-quick-button")
            shortcut.connect("clicked", self.on_dashboard_navigate, page)
            shortcuts.append(shortcut)
        cards.attach(shortcuts, 1, 3, 1, 1)

        scenarios = self.dashboard_panel("Scenario Profiles")
        self.dashboard_profile_values = {}
        for name, _short, description in PROFILES:
            button = Gtk.Button()
            button.add_css_class("dashboard-profile-entry")
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
            row.append(label(PROFILE_SYMBOLS[name], "profile-symbol"))
            profile_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            profile_copy.append(label(name, "profile-name"))
            profile_copy.append(label(description, "dashboard-tiny"))
            row.append(profile_copy)
            button.set_child(row)
            button.connect("clicked", self.on_profile_clicked, name)
            scenarios.append(button)
            self.dashboard_profile_values[name] = button
        cards.attach(scenarios, 2, 0, 1, 1)

        battery = self.dashboard_panel("Battery Care")
        self.dashboard_battery_value = label("—", "dashboard-value-large")
        battery.append(self.dashboard_battery_value)
        battery.append(label("Charge limit and battery status", "dashboard-tiny"))
        battery_button = Gtk.Button(label="Open Battery")
        battery_button.add_css_class("dashboard-quick-button")
        battery_button.connect("clicked", self.on_dashboard_navigate, "battery")
        battery.append(battery_button)
        cards.attach(battery, 2, 1, 1, 1)

        device = self.dashboard_panel("My Device")
        self.dashboard_device_value = label(pretty_product_name(text("/sys/class/dmi/id/product_name", "ASUS laptop")), "dashboard-stat-value")
        device.append(self.dashboard_device_value)
        device.append(label(cpu_model(), "dashboard-tiny"))
        device.append(label(dgpu, "dashboard-tiny"))
        cards.attach(device, 2, 2, 1, 1)

        gpu_mode = self.dashboard_panel("GPU Mode")
        self.dashboard_gpu_mode_value = label("Unavailable", "dashboard-value-large")
        gpu_mode.append(self.dashboard_gpu_mode_value)
        gpu_mode_button = Gtk.Button(label="Open GPU Mode")
        gpu_mode_button.add_css_class("dashboard-quick-button")
        gpu_mode_button.connect("clicked", self.on_dashboard_navigate, "gpu")
        gpu_mode.append(gpu_mode_button)
        cards.attach(gpu_mode, 2, 3, 1, 1)

        resources = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.dashboard_resource_values = {}
        for key, title, icon_name in (("ram", "Memory", "ic_ram.svg"), ("storage", "Storage", "ic_ssd.svg"), ("ssd", "SSD", "ic_ssd.svg")):
            panel = self.dashboard_panel(title)
            icon = asus_image(icon_name, "drive-harddisk-symbolic", 20)
            if icon is not None:
                panel.prepend(icon)
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
        cards.attach(resources, 0, 4, 3, 1)
        main_grid.attach(cards, 3, 0, 7, 5)
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
        panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        panel.add_css_class("dashboard-module")
        icon_image = asus_image(icon, "preferences-system-symbolic", 18)
        if icon_image is not None:
            panel.append(icon_image)
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        copy.append(label(title, "dashboard-stat-name"))
        value = label("— rpm", "dashboard-stat-value")
        copy.append(value)
        panel.append(copy)
        self.dashboard_values[key] = value
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
