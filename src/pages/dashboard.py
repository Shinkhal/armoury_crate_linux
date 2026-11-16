"""Dashboard page UI and interactions."""
import math
import json
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
        content.set_vexpand(True)
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
        main_grid.set_column_homogeneous(True)
        main_grid.set_hexpand(True)
        main_grid.set_vexpand(True)
        self.dashboard_stat_meter_values = {}
        self.dashboard_stat_meters = {}
        left_panel = self.dashboard_panel("CPU")
        left_panel.add_css_class("dashboard-cpu-panel")
        left_panel.set_hexpand(True)
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
        cpu_usage_row, self.dashboard_cpu_usage, self.dashboard_cpu_usage_bar = self.dashboard_meter("CPU Usage", "cpu_usage_card", "#35a8ff")
        gpu_usage_row, self.dashboard_gpu_usage, self.dashboard_gpu_usage_bar = self.dashboard_meter("GPU Usage", "gpu_usage_card", "#f04483")
        left_panel.append(cpu_usage_row)
        left_panel.append(gpu_usage_row)
        profile_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        profile_row.add_css_class("dashboard-profile-row")
        self.dashboard_profile_values = {}
        for name, _short, _description in PROFILES:
            button = Gtk.Button(label=name)
            button.add_css_class("dashboard-profile-name")
            button.set_hexpand(True)
            button.connect("clicked", self.on_profile_clicked, name)
            profile_row.append(button)
            self.dashboard_profile_values[name] = button
        profile_spacer = Gtk.Box(vexpand=True)
        profile_spacer.set_vexpand(True)
        left_panel.append(profile_spacer)
        left_panel.append(profile_row)
        main_grid.attach(left_panel, 0, 0, 3, 1)

        cards = Gtk.Grid(column_spacing=8, row_spacing=8)
        cards.set_column_homogeneous(True)
        cards.set_row_homogeneous(True)
        cards.set_hexpand(True)
        cards.set_vexpand(True)
        cards.add_css_class("dashboard-tiles")
        self.dashboard_tile_widgets = {}
        self.dashboard_tile_order = self.load_dashboard_tile_order()
        self.dashboard_values = {}

        cpu_stats = self.dashboard_panel("CPU Stats")
        cpu_stats.add_css_class("dashboard-compact-module")
        cpu_stats.set_spacing(4)
        self.dashboard_stat_meter(cpu_stats, "Frequency", "—", "cpu_frequency", 6000, "#35a8ff")
        self.dashboard_stat_meter(cpu_stats, "Usage", "—", "cpu_usage", 100, "#35a8ff")
        self.dashboard_stat(cpu_stats, "Temperature", "—", "cpu_temperature")
        self.dashboard_stat(cpu_stats, "Voltage", "Unavailable", "cpu_voltage")

        gpu_stats = self.dashboard_panel("GPU Stats")
        gpu_stats.add_css_class("dashboard-compact-module")
        gpu_stats.set_spacing(4)
        self.dashboard_stat_meter(gpu_stats, "Frequency", "Unavailable", "gpu_frequency", 4000, "#f04483")
        self.dashboard_stat_meter(gpu_stats, "Usage", "Unavailable", "gpu_usage", 100, "#f04483")
        self.dashboard_stat(gpu_stats, "Memory Frequency", "Unavailable", "gpu_memory_frequency")
        self.dashboard_stat(gpu_stats, "Temperature", "Unavailable", "gpu_temperature")
        self.dashboard_stat(gpu_stats, "Voltage", "Unavailable", "gpu_voltage")
        self.dashboard_stat(gpu_stats, "Power", "Unavailable", "gpu_tgp")

        self.add_dashboard_tile(cards, "cpu_stats", cpu_stats)
        self.add_dashboard_tile(cards, "gpu_stats", gpu_stats)

        fans = self.dashboard_panel("Fan Speed")
        fans.add_css_class("dashboard-compact-module")
        fans.set_spacing(4)
        self.dashboard_fan_gauges = {}
        self.dashboard_fan_details = {}
        self.dashboard_resource_usage = {
            "ram": 0.0, "storage": 0.0, "cpu_fan": 0.0, "gpu_fan": 0.0,
        }
        cpu_fan_box = self.dashboard_metric_panel("CPU", "ic_fan.svg", "cpu_fan", "#a78bfa")
        gpu_fan_box = self.dashboard_metric_panel("GPU", "ic_fan_alt.svg", "gpu_fan", "#f472b6")
        fan_columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fan_columns.add_css_class("dashboard-resource-row")
        fan_columns.set_vexpand(True)
        cpu_fan_box.set_hexpand(True)
        gpu_fan_box.set_hexpand(True)
        fan_columns.append(cpu_fan_box)
        fan_columns.append(gpu_fan_box)
        fans.append(fan_columns)
        fans.set_valign(Gtk.Align.FILL)
        self.add_dashboard_tile(cards, "fans", fans)

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
        self.add_dashboard_tile(cards, "app_configuration", shortcuts)

        battery = self.dashboard_panel("Battery Care")
        self.dashboard_battery_value = label("—", "dashboard-value-large")
        battery.append(self.dashboard_battery_value)
        self.dashboard_battery_level = None
        self.dashboard_battery_icon = Gtk.DrawingArea()
        self.dashboard_battery_icon.set_content_width(180)
        self.dashboard_battery_icon.set_content_height(38)
        self.dashboard_battery_icon.set_halign(Gtk.Align.FILL)
        self.dashboard_battery_icon.add_css_class("dashboard-battery-icon")
        self.dashboard_battery_icon.set_draw_func(self.draw_battery_icon)
        self.dashboard_battery_icon.set_tooltip_text("Battery charge")
        battery.append(self.dashboard_battery_icon)
        self.dashboard_battery_eta = label("Time estimate unavailable", "dashboard-tiny")
        battery.append(self.dashboard_battery_eta)
        self.add_dashboard_tile(cards, "battery", battery)

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
        self.add_dashboard_tile(cards, "gpu_mode", gpu_mode)

        memory_storage = self.dashboard_panel("Memory and Storage")
        memory_storage.set_spacing(6)
        self.dashboard_resource_values = {}
        self.dashboard_resource_details = {}
        self.dashboard_resource_meters = {}
        resource_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        resource_row.add_css_class("dashboard-resource-row")
        resource_row.set_hexpand(True)
        resource_row.set_vexpand(True)
        for key, title, icon, color in (
            ("ram", "RAM", "ic_ram.svg", "#08aaff"),
            ("storage", "Storage", "ic_ssd.svg", "#f04483"),
        ):
            section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            section.add_css_class("dashboard-resource-card")
            section.set_hexpand(True)
            section.set_valign(Gtk.Align.CENTER)
            meter = Gtk.DrawingArea()
            meter.set_content_width(72)
            meter.set_content_height(72)
            meter.set_size_request(72, 72)
            meter.add_css_class("dashboard-resource-meter")
            meter.set_draw_func(self.draw_resource_meter, (key, color))
            meter.set_halign(Gtk.Align.CENTER)
            section.append(meter)
            copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            copy.set_halign(Gtk.Align.CENTER)
            title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            title_row.set_halign(Gtk.Align.CENTER)
            icon_image = asus_image(icon, "drive-harddisk-symbolic" if key == "storage" else "media-floppy-symbolic", 16)
            if icon_image is not None:
                title_row.append(icon_image)
            title_row.append(label(title, "dashboard-stat-name"))
            copy.append(title_row)
            value = label("—%", "dashboard-value-large")
            value.set_wrap(False)
            value.set_xalign(.5)
            value.set_halign(Gtk.Align.CENTER)
            copy.append(value)
            detail = label("— / — GB", "dashboard-tiny")
            detail.set_wrap(False)
            detail.set_ellipsize(2)
            detail.set_xalign(.5)
            detail.set_halign(Gtk.Align.CENTER)
            copy.append(detail)
            section.append(copy)
            resource_row.append(section)
            self.dashboard_resource_values[key] = value
            self.dashboard_resource_details[key] = detail
            self.dashboard_resource_meters[key] = meter
        memory_storage.append(resource_row)
        memory_storage.set_hexpand(True)
        self.add_dashboard_tile(cards, "memory_storage", memory_storage)

        self.arrange_dashboard_tiles(cards)

        main_grid.attach(cards, 3, 0, 7, 1)
        content.append(main_grid)
        scroll.set_child(content)
        outer.append(scroll)
        return outer

    def load_dashboard_tile_order(self):
        path = os.path.join(GLib.get_user_config_dir(), "armoury-crate", "dashboard-tiles.json")
        try:
            with open(path, encoding="utf-8") as stream:
                saved = json.load(stream)
            known = ["cpu_stats", "fans", "memory_storage", "gpu_stats", "app_configuration", "battery", "gpu_mode"]
            return [key for key in saved if key in known] + [key for key in known if key not in saved]
        except (OSError, ValueError, TypeError):
            return ["cpu_stats", "fans", "memory_storage", "gpu_stats", "app_configuration", "battery", "gpu_mode"]

    def add_dashboard_tile(self, grid, key, widget):
        self.dashboard_tile_widgets[key] = widget
        widget.set_tooltip_text("Drag to rearrange this tile")
        source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        source.connect("prepare", self.dashboard_tile_drag_prepare, key)
        widget.add_controller(source)
        target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        target.connect("drop", self.dashboard_tile_drop, widget)
        widget.add_controller(target)

    def arrange_dashboard_tiles(self, grid):
        for child in tuple(self.dashboard_tile_widgets.values()):
            if child.get_parent() is grid:
                grid.remove(child)
        for position, key in enumerate(self.dashboard_tile_order):
            tile = self.dashboard_tile_widgets.get(key)
            if tile is not None:
                grid.attach(tile, position % 3, position // 3, 1, 1)

    def dashboard_tile_drag_prepare(self, _source, _x, _y, key):
        return Gdk.ContentProvider.new_for_value(key)

    def dashboard_tile_drop(self, _target, dragged_key, _x, _y, destination_widget):
        destination_key = next((key for key, widget in self.dashboard_tile_widgets.items() if widget is destination_widget), None)
        if not destination_key or dragged_key == destination_key:
            return False
        self.dashboard_tile_order.remove(dragged_key)
        self.dashboard_tile_order.insert(self.dashboard_tile_order.index(destination_key), dragged_key)
        grid = destination_widget.get_parent()
        self.arrange_dashboard_tiles(grid)
        path = os.path.join(GLib.get_user_config_dir(), "armoury-crate", "dashboard-tiles.json")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(self.dashboard_tile_order, stream)
        except OSError:
            pass
        return True

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

    def dashboard_stat_meter(self, panel, title, initial, key, scale, colour):
        value = self.dashboard_stat(panel, title, initial, key)
        meter = Gtk.DrawingArea()
        meter.set_content_height(9)
        meter.set_hexpand(True)
        meter.add_css_class("dashboard-stat-meter")
        meter.set_draw_func(self.draw_stat_meter, (key, scale, colour))
        panel.append(meter)
        if not hasattr(self, "dashboard_stat_meter_values"):
            self.dashboard_stat_meter_values = {}
            self.dashboard_stat_meters = {}
        self.dashboard_stat_meter_values[key] = None
        self.dashboard_stat_meters[key] = meter
        return value

    def draw_resource_meter(self, _area, context, width, height, user_data):
        key, color = user_data
        fraction = max(0.0, min(1.0, self.dashboard_resource_usage.get(key, 0.0)))
        center_x, center_y = width / 2, height / 2
        radius = min(width, height) * .39
        start_angle = -math.pi / 2
        red, green, blue = (int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))

        context.set_source_rgba(.015, .025, .04, .95)
        context.arc(center_x, center_y, radius * .82, 0, math.tau)
        context.fill()
        context.set_line_cap(1)
        context.set_line_width(2.5)
        context.set_source_rgba(.20, .28, .35, .85)
        context.arc(center_x, center_y, radius, 0, math.tau)
        context.stroke()
        context.set_line_width(3.5)
        context.set_source_rgba(red, green, blue, .98)
        context.arc(center_x, center_y, radius, start_angle, start_angle + math.tau * fraction)
        context.stroke()

        for tick in range(40):
            angle = start_angle + math.tau * tick / 40
            major = tick % 5 == 0
            inner_radius = radius * (.80 if major else .88)
            context.set_line_width(1.2 if major else .7)
            context.set_source_rgba(.78, .86, .94, .78 if major else .4)
            context.move_to(center_x + inner_radius * math.cos(angle), center_y + inner_radius * math.sin(angle))
            context.line_to(center_x + radius * .98 * math.cos(angle), center_y + radius * .98 * math.sin(angle))
            context.stroke()

        # Fine radar sweep points at the current used fraction.
        needle_angle = start_angle + math.tau * fraction
        context.set_line_width(1.3)
        context.set_source_rgba(red, green, blue, .9)
        context.move_to(center_x, center_y)
        context.line_to(center_x + radius * .72 * math.cos(needle_angle), center_y + radius * .72 * math.sin(needle_angle))
        context.stroke()
        context.set_source_rgba(.92, .96, 1, .9)
        context.arc(center_x, center_y, 2.1, 0, math.tau)
        context.fill()

    def draw_stat_meter(self, _area, context, width, height, user_data):
        key, scale, colour = user_data
        value = self.dashboard_stat_meter_values.get(key)
        fraction = max(0.0, min(1.0, value / scale)) if value is not None and scale else 0.0
        context.set_line_width(1)
        for tick in range(61):
            x = 1 + (max(1, width - 2) * tick / 60)
            tick_height = 7 if tick % 10 == 0 else 4
            context.set_source_rgba(.72, .78, .84, .70 if tick % 10 == 0 else .42)
            context.move_to(x, height - tick_height)
            context.line_to(x, height)
            context.stroke()
        red, green, blue = (int(colour[index:index + 2], 16) / 255 for index in (1, 3, 5))
        context.set_line_width(3)
        context.set_source_rgba(red, green, blue, .95)
        context.move_to(1, height - 1.5)
        context.line_to(max(1, width - 1) * fraction, height - 1.5)
        context.stroke()

    def dashboard_metric_panel(self, title, icon, key, color):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        panel.add_css_class("dashboard-resource-card")
        panel.set_hexpand(True)
        panel.set_valign(Gtk.Align.CENTER)
        gauge = Gtk.DrawingArea()
        gauge.add_css_class("dashboard-resource-meter")
        gauge.set_content_width(72)
        gauge.set_content_height(72)
        gauge.set_size_request(72, 72)
        gauge.set_draw_func(self.draw_resource_meter, (key, color))
        gauge.set_halign(Gtk.Align.CENTER)
        panel.append(gauge)
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        copy.set_halign(Gtk.Align.CENTER)
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        title_row.set_halign(Gtk.Align.CENTER)
        icon_image = asus_image(icon, "preferences-system-symbolic", 16)
        if icon_image is not None:
            title_row.append(icon_image)
        title_row.append(label(f"{title} Fan", "dashboard-stat-name"))
        copy.append(title_row)
        value = label("— rpm", "dashboard-value-large")
        value.set_wrap(False)
        value.set_xalign(.5)
        value.set_halign(Gtk.Align.CENTER)
        copy.append(value)
        detail = label("Fan speed", "dashboard-tiny")
        detail.set_xalign(.5)
        detail.set_halign(Gtk.Align.CENTER)
        copy.append(detail)
        panel.append(copy)
        self.dashboard_values[key] = value
        self.dashboard_fan_gauges[key] = gauge
        self.dashboard_fan_details[key] = detail
        gauge.set_tooltip_text(f"{title} speed")
        return panel

    def draw_battery_icon(self, _area, context, width, height):
        level = self.dashboard_battery_level
        x, y = 8, 7
        body_width, body_height = max(80, width - 25), height - 14
        terminal_width = 6
        context.set_line_width(2)
        context.set_source_rgba(.55, .64, .72, .95)
        context.rectangle(x, y, body_width, body_height)
        context.stroke()
        context.rectangle(x + body_width, y + body_height * .30, terminal_width, body_height * .40)
        context.fill()
        if level is None:
            context.set_source_rgba(.35, .42, .49, .85)
            context.move_to(x + body_width * .43, y + body_height * .50)
            context.line_to(x + body_width * .57, y + body_height * .50)
            context.stroke()
            return
        fill = max(0.0, min(100.0, level)) / 100
        if level <= 20:
            colour = (.95, .25, .30)
        elif level <= 50:
            colour = (.96, .65, .18)
        else:
            colour = (.20, .82, .55)
        context.set_source_rgba(*colour, .95)
        context.rectangle(x + 3, y + 3, max(2, (body_width - 6) * fill), body_height - 6)
        context.fill()
        # Subtle internal cell dividers keep the icon readable as a battery,
        # while the fill still communicates the exact percentage.
        context.set_line_width(1)
        context.set_source_rgba(.04, .10, .14, .60)
        cell_width = (body_width - 6) / 5
        for cell in range(1, 5):
            divider_x = x + 3 + cell_width * cell
            context.move_to(divider_x, y + 3)
            context.line_to(divider_x, y + body_height - 3)
            context.stroke()

    def dashboard_meter(self, title, key, color):
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label_row.append(label(title, "dashboard-stat-name"))
        value = label("—", "dashboard-stat-value")
        value.set_hexpand(True)
        value.set_halign(Gtk.Align.END)
        label_row.append(value)
        row.append(label_row)
        bar = Gtk.DrawingArea()
        bar.set_content_height(9)
        bar.set_hexpand(True)
        bar.add_css_class("dashboard-stat-meter")
        bar.set_draw_func(self.draw_stat_meter, (key, 100, color))
        row.append(bar)
        self.dashboard_stat_meter_values[key] = None
        self.dashboard_stat_meters[key] = bar
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
