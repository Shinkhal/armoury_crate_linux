"""Device resource monitor and running applications pages."""
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from config import DEVICE_MONITOR_REFRESH_SECONDS
from components.widgets import label
from hardware.asus import fan_hwmon, fan_read, rpm
from hardware.system import (
    cpu_freq_ghz, format_bytes, gpu_telemetry, memory_details,
    read_disk_active_ms, read_disk_io_bytes, read_thermal,
    top_processes,
)


class DevicePage:
    METRICS = {
        "cpu_frequency": ("CPU Frequency", "#31d4e8", 6_000_000, "frequency"),
        "cpu_temperature": ("CPU Temperature", "#ff9f43", 110, "temperature"),
        "cpu_usage": ("CPU Usage", "#ff3854", 100, "percent"),
        "gpu_temperature": ("GPU Temperature", "#68d391", 110, "temperature"),
        "gpu_usage": ("GPU Usage", "#24c9db", 100, "percent"),
        "gpu_frequency": ("GPU Frequency", "#38bdf8", 4_000, "gpu_frequency"),
        "gpu_memory": ("GPU Memory Usage", "#c084fc", 100, "percent"),
        "memory_usage": ("Memory Usage", "#e8ce4a", 100, "percent"),
        "disk_active": ("Disk Active Time", "#f5a623", 100, "percent"),
        "disk_read": ("Disk Read Speed", "#488cff", 100_000_000, "speed"),
        "disk_write": ("Disk Write Speed", "#e957d4", 100_000_000, "speed"),
        "cpu_fan": ("CPU Fan Speed", "#a78bfa", 6_000, "fan"),
        "gpu_fan": ("GPU Fan Speed", "#f472b6", 6_000, "fan"),
    }
    LEVELS = (
        ("Level 1 · Essentials", {"cpu_usage"}),
        ("Level 2 · Load & Thermals", {"cpu_usage", "cpu_temperature", "gpu_usage", "gpu_temperature"}),
        ("Level 3 · Clocks & Memory", {
            "cpu_usage", "cpu_temperature", "gpu_usage", "gpu_temperature",
            "cpu_frequency", "gpu_frequency", "memory_usage", "gpu_memory",
        }),
        ("Level 4 · Full Telemetry", set(METRICS)),
    )

    def build_device(self):
        outer, content = self.page_shell(
            "DEVICE", "Device",
            "Monitor live hardware activity and see which applications are using system resources.",
        )
        self.device_history = {key: [] for key in self.METRICS}
        self.device_previous_disk = None
        self.device_previous_disk_active = None
        self.device_process_refresh_counter = 0
        self.device_cpu_times = None
        self.device_recording = True
        self.device_recording_started = time.monotonic()
        self.device_metric_values = {}
        self.device_metric_rows = {}
        self.device_visible_metrics = set()
        self.device_chart = None

        tabs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tabs.add_css_class("device-tabs")
        self.device_tab_buttons = {}
        for key, title in (("monitor", "Resource Monitor"), ("applications", "Running Applications")):
            button = Gtk.ToggleButton(label=title)
            button.add_css_class("device-tab")
            button.connect("toggled", self.on_device_tab_toggled, key)
            tabs.append(button)
            self.device_tab_buttons[key] = button
        content.append(tabs)

        self.device_content_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.device_content_stack.set_vexpand(True)
        self.device_monitor_page = self._build_resource_monitor()
        self.device_applications_page = self._build_applications_page()
        self.device_content_stack.add_named(self.device_monitor_page, "monitor")
        self.device_content_stack.add_named(self.device_applications_page, "applications")
        content.append(self.device_content_stack)
        self.device_tab_buttons["monitor"].set_active(True)
        self.on_device_level_changed(self.device_level_dropdown, None)
        self.refresh_device_monitor()
        GLib.timeout_add_seconds(max(1, round(DEVICE_MONITOR_REFRESH_SECONDS)), self.refresh_device_monitor)
        return outer

    def _build_resource_monitor(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        toolbar.add_css_class("resource-toolbar")
        self.device_recording_label = label("●  RECORDING  00:00", "resource-recording")
        toolbar.append(self.device_recording_label)
        toolbar.append(Gtk.Box(hexpand=True))
        toolbar.append(label("LEVEL", "resource-toolbar-label"))
        self.device_level_dropdown = Gtk.DropDown.new_from_strings([item[0] for item in self.LEVELS])
        self.device_level_dropdown.set_selected(2)
        self.device_level_dropdown.connect("notify::selected", self.on_device_level_changed)
        toolbar.append(self.device_level_dropdown)
        toolbar.append(label("VIEW", "resource-toolbar-label"))
        self.device_time_view = Gtk.DropDown.new_from_strings(["1 minute", "5 minutes", "10 minutes"])
        self.device_time_view.set_selected(1)
        self.device_time_view.connect("notify::selected", self.on_device_time_view_changed)
        toolbar.append(self.device_time_view)
        self.device_record_button = Gtk.Button(label="Stop")
        self.device_record_button.add_css_class("resource-record-button")
        self.device_record_button.connect("clicked", self.on_device_record_clicked)
        toolbar.append(self.device_record_button)
        page.append(toolbar)

        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main.add_css_class("resource-monitor-frame")
        chart_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        chart_box.add_css_class("resource-chart-wrap")
        chart_box.set_hexpand(True)
        self.device_chart = Gtk.DrawingArea()
        self.device_chart.set_content_width(820)
        self.device_chart.set_content_height(500)
        self.device_chart.set_hexpand(True)
        self.device_chart.set_vexpand(True)
        self.device_chart.add_css_class("resource-chart")
        self.device_chart.set_draw_func(self.draw_resource_chart)
        chart_box.append(self.device_chart)
        main.append(chart_box)

        metrics_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        metrics_box.add_css_class("resource-metrics-panel")
        metrics_box.set_size_request(184, -1)
        metrics_box.append(label("RESOURCE METRICS", "resource-metrics-heading"))
        self.device_metric_values = {}
        for key, (title, colour, _scale, _kind) in self.METRICS.items():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            row.add_css_class("resource-metric-row")
            dot = label("", "resource-metric-dot")
            dot.set_markup(f'<span foreground="{colour}">●</span>')
            row.append(dot)
            row.append(label(title, "resource-metric-name"))
            row.append(Gtk.Box(hexpand=True))
            value = label("—", "resource-metric-value")
            value.set_halign(Gtk.Align.END)
            row.append(value)
            metrics_box.append(row)
            self.device_metric_values[key] = value
            self.device_metric_rows[key] = row
        main.append(metrics_box)
        page.append(main)

        return page

    def _build_applications_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.add_css_class("applications-panel")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.add_css_class("applications-heading")
        header.append(label("RUNNING APPLICATIONS", "resource-metrics-heading"))
        header.append(Gtk.Box(hexpand=True))
        self.device_process_summary = label("Live · sorted by CPU", "device-resource-detail")
        header.append(self.device_process_summary)
        page.append(header)

        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        list_box.add_css_class("applications-list")
        headings = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        headings.add_css_class("applications-list-headings")
        headings.append(label("APPLICATION", "device-process-column"))
        headings.append(Gtk.Box(hexpand=True))
        cpu_heading = label("CPU", "device-process-column")
        cpu_heading.set_size_request(94, -1)
        cpu_heading.set_halign(Gtk.Align.END)
        headings.append(cpu_heading)
        memory_heading = label("MEMORY", "device-process-column")
        memory_heading.set_size_request(112, -1)
        memory_heading.set_halign(Gtk.Align.END)
        headings.append(memory_heading)
        list_box.append(headings)
        self.device_process_rows = []
        for index in range(20):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
            row.add_css_class("application-row")
            icon = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
            icon.set_pixel_size(18)
            icon.add_css_class("application-icon")
            name = label("", "device-process-name")
            name.set_hexpand(True)
            name.set_ellipsize(3)
            row.append(icon)
            row.append(name)

            cpu = label("—", "device-process-value")
            cpu.set_size_request(94, -1)
            cpu.set_halign(Gtk.Align.END)
            ram = label("—", "device-process-value")
            ram.set_size_request(112, -1)
            ram.set_halign(Gtk.Align.END)
            row.append(cpu)
            row.append(ram)
            if index % 2:
                row.add_css_class("applications-row-alt")
            list_box.append(row)
            self.device_process_rows.append((row, icon, name, cpu, ram))
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_vexpand(True)
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_child(list_box)
        page.append(list_scroll)
        return page

    def on_device_tab_toggled(self, button, key):
        if not button.get_active():
            return
        for other_key, other in self.device_tab_buttons.items():
            if other_key != key:
                other.set_active(False)
        self.device_content_stack.set_visible_child_name(key)

    def on_device_level_changed(self, dropdown, _param):
        selected = dropdown.get_selected()
        if selected >= len(self.LEVELS):
            selected = 2
        self.device_visible_metrics = self.LEVELS[selected][1]
        for key, row in self.device_metric_rows.items():
            row.set_visible(key in self.device_visible_metrics)
        if self.device_chart is not None:
            self.device_chart.queue_draw()

    def on_device_time_view_changed(self, *_args):
        if self.device_chart is not None:
            self.device_chart.queue_draw()

    def on_device_record_clicked(self, _button):
        self.device_recording = not self.device_recording
        if self.device_recording:
            self.device_recording_started = time.monotonic()
            self.device_record_button.set_label("Stop")
            self.device_recording_label.set_text("●  RECORDING  00:00")
        else:
            self.device_record_button.set_label("Record")
            self.device_recording_label.set_text("Ⅱ  PAUSED")

    def refresh_device_monitor(self, cpu_sample=None, cpu_sampled=False):
        if not hasattr(self, "device_history"):
            return
        cpu_usage = self._device_cpu_usage_percent()
        gpu = gpu_telemetry()
        gpu_usage = gpu["usage"]
        memory = memory_details()
        total = memory.get("MemTotal")
        available = memory.get("MemAvailable")
        used = total - available if total is not None and available is not None else None
        memory_usage = used * 100 / total if used is not None and total else None
        frequency_ghz = cpu_freq_ghz()
        cpu_frequency = frequency_ghz * 1_000_000 if frequency_ghz else None
        cpu_temperature = read_thermal("acpitz")
        if cpu_temperature is None:
            cpu_temperature = read_thermal("k10temp") or read_thermal("coretemp")
        gpu_temperature = gpu["temperature"]
        hwmon = fan_hwmon()
        cpu_fan = fan_read(hwmon, "fan1_input") if hwmon else None
        gpu_fan = fan_read(hwmon, "fan2_input") if hwmon else None

        counters = read_disk_io_bytes()
        disk_read = disk_write = None
        now = time.monotonic()
        if counters is not None and self.device_previous_disk is not None:
            previous_time, previous_counters = self.device_previous_disk
            elapsed = max(0.1, now - previous_time)
            disk_read = max(0.0, (counters[0] - previous_counters[0]) / elapsed)
            disk_write = max(0.0, (counters[1] - previous_counters[1]) / elapsed)
        if counters is not None:
            self.device_previous_disk = now, counters
        active_counters = read_disk_active_ms()
        disk_active = None
        if active_counters is not None and self.device_previous_disk_active is not None:
            previous_time, previous_active, previous_devices = self.device_previous_disk_active
            elapsed_ms = max(100.0, (now - previous_time) * 1000)
            device_count = max(1, active_counters[1], previous_devices)
            disk_active = min(100.0, max(0.0, (active_counters[0] - previous_active) * 100 / (elapsed_ms * device_count)))
        if active_counters is not None:
            self.device_previous_disk_active = now, active_counters[0], active_counters[1]

        values = {
            "cpu_frequency": cpu_frequency,
            "cpu_temperature": cpu_temperature,
            "cpu_usage": cpu_usage,
            "gpu_temperature": gpu_temperature,
            "gpu_usage": gpu_usage,
            "gpu_frequency": gpu["frequency"],
            "gpu_memory": (
                gpu["memory_used"] * 100 / gpu["memory_total"]
                if gpu["memory_used"] is not None and gpu["memory_total"] else None
            ),
            "memory_usage": memory_usage,
            "disk_active": disk_active,
            "disk_read": disk_read,
            "disk_write": disk_write,
            "cpu_fan": cpu_fan,
            "gpu_fan": gpu_fan,
        }
        if self.device_recording:
            for key, value in values.items():
                history = self.device_history[key]
                history.append(value)
                del history[:-600]
            if self.device_chart is not None:
                self.device_chart.queue_draw()

        for key, value in values.items():
            self.device_metric_values[key].set_text(self._format_metric(key, value))
        if self.device_recording:
            elapsed = int(now - self.device_recording_started)
            minutes, seconds = divmod(elapsed, 60)
            self.device_recording_label.set_text(f"●  RECORDING  {minutes:02d}:{seconds:02d}")

        self.device_process_refresh_counter += 1
        if self.device_process_refresh_counter % 4 == 1:
            self.device_process_summary.set_text("Live · sorted by CPU")
            processes = top_processes(len(self.device_process_rows))
            for index, widgets in enumerate(self.device_process_rows):
                row, icon, name, cpu, ram = widgets
                if index < len(processes):
                    process = processes[index]
                    name.set_text(process["name"])
                    name.set_tooltip_text(f"{process['name']} · {len(process['pids'])} process(es)")
                    icon_name = self._application_icon(process["name"])
                    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
                    icon.set_from_icon_name(icon_name if theme.has_icon(icon_name) else "application-x-executable-symbolic")
                    cpu_value = max(0.0, process["cpu"])
                    cpu.set_text(f"{cpu_value:.1f}%")
                    ram.set_text(format_bytes(process["memory"]))
                    name.set_tooltip_text(f"{process['name']} · {len(process['pids'])} running process(es)")
                    row.set_visible(True)
                else:
                    row.set_visible(False)
        return True

    def _device_cpu_usage_percent(self):
        try:
            with open("/proc/stat", encoding="utf-8") as stream:
                values = [int(value) for value in stream.readline().split()[1:]]
        except (OSError, ValueError, IndexError):
            return None
        total = sum(values)
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        previous = self.device_cpu_times
        self.device_cpu_times = total, idle
        if previous is None or total <= previous[0]:
            return None
        delta_total = total - previous[0]
        return max(0.0, min(100.0, (delta_total - idle + previous[1]) * 100 / delta_total))

    def _visible_sample_count(self):
        selection = self.device_time_view.get_selected()
        minutes = (1, 5, 10)[selection if selection < 3 else 1]
        return minutes * 60

    def draw_resource_chart(self, _area, context, width, height):
        left, right, top, bottom = 42, max(46, width - 10), 12, max(20, height - 29)
        plot_height = bottom - top
        plot_width = right - left
        context.set_source_rgb(0.025, 0.035, 0.050)
        context.paint()
        context.set_font_size(9)
        for value in (0, 50, 100):
            y = bottom - plot_height * value / 100
            context.set_source_rgba(0.64, 0.69, 0.76, 0.17)
            context.set_line_width(1)
            context.move_to(left, y)
            context.line_to(right, y)
            context.stroke()
            context.set_source_rgba(0.64, 0.69, 0.76, 0.68)
            context.move_to(9, y + 3)
            context.show_text(str(value))

        visible_count = self._visible_sample_count()
        for key, (title, colour, scale, _kind) in self.METRICS.items():
            if key not in self.device_visible_metrics:
                continue
            samples = self.device_history[key][-visible_count:]
            valid = [(index, sample) for index, sample in enumerate(samples) if sample is not None]
            if len(valid) < 2:
                continue
            denominator = max(1, len(samples) - 1)
            recent_values = [float(sample) for _index, sample in valid]
            low, high = min(recent_values), max(recent_values)
            padding = max(scale * 0.025, (high - low) * 0.18)
            low = max(0.0, low - padding)
            high = min(scale, high + padding)
            if high - low < scale * 0.05:
                midpoint = (low + high) / 2
                low = max(0.0, midpoint - scale * 0.025)
                high = min(scale, midpoint + scale * 0.025)
            span = max(0.0001, high - low)
            red, green, blue = self._hex_rgb(colour)
            points = []
            for index, sample in valid:
                x = left + plot_width * index / denominator
                normalized = max(0.0, min(100.0, (float(sample) - low) * 100 / span))
                y = bottom - plot_height * normalized / 100
                points.append((x, y))
            if len(points) >= 2:
                first_x, last_x = points[0][0], points[-1][0]
                context.move_to(first_x, bottom)
                context.line_to(*points[0])
                for point_index in range(1, len(points)):
                    p0 = points[max(0, point_index - 2)]
                    p1 = points[point_index - 1]
                    p2 = points[point_index]
                    p3 = points[min(len(points) - 1, point_index + 1)]
                    cp1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
                    cp2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
                    context.curve_to(*cp1, *cp2, *p2)
                context.line_to(last_x, bottom)
                context.close_path()
                context.set_source_rgba(red, green, blue, 0.09)
                context.fill_preserve()
                context.set_source_rgba(red, green, blue, 0.92)
                context.stroke()

        context.set_source_rgba(0.64, 0.69, 0.76, 0.7)
        context.move_to(left, 9)
        context.show_text("RECENT RANGE")
        context.move_to(left, height - 8)
        minutes = self._visible_sample_count() // 60
        context.show_text(f"{minutes} minute{'s' if minutes != 1 else ''} ago")
        context.move_to(max(left + 50, right - 29), height - 8)
        context.show_text("NOW")

    def _format_metric(self, key, value):
        if value is None:
            return "Unavailable"
        _title, _colour, _scale, kind = self.METRICS[key]
        if kind == "percent":
            return f"{value:.0f}%"
        if kind == "temperature":
            return f"{value:.0f} °C"
        if kind == "frequency":
            return f"{value / 1000:.0f} MHz"
        if kind == "gpu_frequency":
            return f"{value:.0f} MHz"
        if kind == "speed":
            return f"{value / 1_000_000:.2f} MB/s"
        if kind == "fan":
            return rpm(value)
        return str(value)

    @staticmethod
    def _hex_rgb(value):
        return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))

    @staticmethod
    def _application_icon(name):
        lowered = name.lower()
        for marker, icon in (
            ("firefox", "firefox"), ("chrome", "google-chrome"),
            ("chromium", "chromium"), ("steam", "steam"),
            ("visual studio code", "visual-studio-code"), ("discord", "discord"),
            ("obs", "obs-studio"), ("vlc", "vlc"), ("spotify", "spotify"),
            ("gnome shell", "gnome-shell"), ("kde plasma", "plasmashell"),
        ):
            if marker in lowered:
                return icon
        return "application-x-executable-symbolic"
