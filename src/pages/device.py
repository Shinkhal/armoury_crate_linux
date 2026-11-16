"""Device resource monitor and running applications pages."""
import math
import time

import cairo
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
        self.device_recording = False
        self.device_recording_started = None
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
        self.device_timer_id = GLib.timeout_add_seconds(
            max(1, round(DEVICE_MONITOR_REFRESH_SECONDS)), self.refresh_device_monitor
        )
        return outer

    def _build_resource_monitor(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.set_margin_top(8)
        page.set_margin_bottom(12)

        # ── Header bar with title and controls ──
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        header.add_css_class("resource-monitor-header")

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_valign(Gtk.Align.CENTER)
        title_box.append(label("Resource Monitor", "monitor-panel-title"))
        title_box.append(label("Live hardware telemetry and performance overview", "device-resource-detail"))
        header.append(title_box)
        header.append(Gtk.Box(hexpand=True))
        page.append(header)

        # ── Toolbar: recording status, level, time view, record button ──
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        toolbar.add_css_class("resource-toolbar")

        status_pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_pill.add_css_class("resource-status-pill")
        status_pill.add_css_class("resource-toolbar-item")
        status_pill.set_valign(Gtk.Align.CENTER)
        self.device_recording_label = label("⏸  STOPPED", "resource-paused")
        status_pill.append(self.device_recording_label)
        toolbar.append(status_pill)

        toolbar.append(Gtk.Box(hexpand=True))

        # Level selector
        level_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        level_group.add_css_class("resource-toolbar-item")
        level_group.set_valign(Gtk.Align.CENTER)
        level_label = label("LEVEL", "resource-toolbar-label")
        level_label.set_valign(Gtk.Align.CENTER)
        level_group.append(level_label)
        self.device_level_dropdown = Gtk.DropDown.new_from_strings([item[0] for item in self.LEVELS])
        self.device_level_dropdown.set_selected(0)
        self.device_level_dropdown.add_css_class("resource-toolbar-dropdown")
        self.device_level_dropdown.connect("notify::selected", self.on_device_level_changed)
        level_group.append(self.device_level_dropdown)
        toolbar.append(level_group)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.add_css_class("resource-toolbar-sep")
        toolbar.append(sep)

        # Time view selector
        view_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        view_group.add_css_class("resource-toolbar-item")
        view_group.set_valign(Gtk.Align.CENTER)
        view_label = label("VIEW", "resource-toolbar-label")
        view_label.set_valign(Gtk.Align.CENTER)
        view_group.append(view_label)
        self.device_time_view = Gtk.DropDown.new_from_strings(["1 minute", "5 minutes", "10 minutes"])
        self.device_time_view.set_selected(1)
        self.device_time_view.add_css_class("resource-toolbar-dropdown")
        self.device_time_view.connect("notify::selected", self.on_device_time_view_changed)
        view_group.append(self.device_time_view)
        toolbar.append(view_group)

        # Separator
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep2.add_css_class("resource-toolbar-sep")
        toolbar.append(sep2)

        # Record/Stop button
        self.device_record_button = Gtk.Button(label="Record")
        self.device_record_button.add_css_class("resource-record-button")
        self.device_record_button.connect("clicked", self.on_device_record_clicked)
        toolbar.append(self.device_record_button)
        page.append(toolbar)

        # ── Main monitor frame: chart + side metrics ──
        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main.add_css_class("resource-monitor-frame")

        # Chart area with hover tooltip
        chart_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        chart_box.add_css_class("resource-chart-wrap")
        chart_box.set_hexpand(True)
        self.device_chart = Gtk.DrawingArea()
        self.device_chart.set_content_width(820)
        self.device_chart.set_content_height(500)
        self.device_chart.set_hexpand(True)
        self.device_chart.set_vexpand(True)
        self.device_chart.add_css_class("resource-chart")
        self.device_chart.set_draw_func(self.draw_resource_chart)

        # Hover motion controller for tooltip
        self.device_chart_hover_x = -1
        self.device_chart_hover_y = -1
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_chart_motion)
        motion.connect("leave", self._on_chart_leave)
        self.device_chart.add_controller(motion)

        chart_box.append(self.device_chart)
        main.append(chart_box)

        # Metrics sidebar
        metrics_scroll = Gtk.ScrolledWindow()
        metrics_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        metrics_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        metrics_box.add_css_class("resource-metrics-panel")
        metrics_box.set_size_request(210, -1)

        metrics_heading = label("RESOURCE METRICS", "resource-metrics-heading")
        metrics_heading.set_margin_bottom(8)
        metrics_box.append(metrics_heading)

        self.device_metric_values = {}
        for key, (title, colour, _scale, _kind) in self.METRICS.items():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("resource-metric-row")
            row.set_valign(Gtk.Align.CENTER)

            dot = label("", "resource-metric-dot")
            dot.set_markup(f'<span foreground="{colour}">●</span>')
            dot.set_valign(Gtk.Align.CENTER)
            row.append(dot)

            name_label = label(title, "resource-metric-name")
            name_label.set_hexpand(True)
            name_label.set_ellipsize(3)
            name_label.set_valign(Gtk.Align.CENTER)
            row.append(name_label)

            value = label("—", "resource-metric-value")
            value.set_halign(Gtk.Align.END)
            value.set_valign(Gtk.Align.CENTER)
            row.append(value)

            metrics_box.append(row)
            self.device_metric_values[key] = value
            self.device_metric_rows[key] = row

        metrics_scroll.set_child(metrics_box)
        main.append(metrics_scroll)
        page.append(main)

        return page

    def _on_chart_motion(self, _controller, x, y):
        self.device_chart_hover_x = x
        self.device_chart_hover_y = y
        if self.device_chart is not None:
            self.device_chart.queue_draw()

    def _on_chart_leave(self, _controller):
        self.device_chart_hover_x = -1
        self.device_chart_hover_y = -1
        if self.device_chart is not None:
            self.device_chart.queue_draw()

    def _build_applications_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.add_css_class("applications-panel")
        page.set_margin_top(8)

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
            self.device_recording_label.remove_css_class("resource-paused")
            self.device_recording_label.add_css_class("resource-recording")
        else:
            self.device_record_button.set_label("Record")
            self.device_recording_label.set_text("⏸  STOPPED")
            self.device_recording_label.remove_css_class("resource-recording")
            self.device_recording_label.add_css_class("resource-paused")

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
        # Margins: extra left for Y-axis label, extra bottom for X-axis label
        left, right, top, bottom = 56, max(60, width - 16), 22, max(30, height - 46)
        plot_height = bottom - top
        plot_width = right - left
        visible_count = self._visible_sample_count()
        minutes = visible_count // 60

        # ── Background ──
        context.set_source_rgb(0.020, 0.030, 0.045)
        context.paint()

        # Subtle radial glow in the center of the plot
        gradient = cairo.RadialGradient(
            left + plot_width * 0.5, top + plot_height * 0.4, plot_width * 0.05,
            left + plot_width * 0.5, top + plot_height * 0.4, plot_width * 0.7,
        )
        gradient.add_color_stop_rgba(0, 0.04, 0.07, 0.12, 0.30)
        gradient.add_color_stop_rgba(1, 0.02, 0.03, 0.045, 0.0)
        context.set_source(gradient)
        context.paint()

        context.select_font_face("Cantarell", 0, 0)

        # ── Y-axis gridlines: 0, 10, 20, … 100 ──
        context.set_font_size(9)
        for value in range(0, 101, 10):
            y = bottom - plot_height * value / 100
            is_major = value % 50 == 0
            is_mid = value % 20 == 0
            # Gridline
            context.set_line_width(0.8 if is_major else 0.5)
            context.set_source_rgba(
                0.45, 0.52, 0.62,
                0.20 if is_major else (0.12 if is_mid else 0.07),
            )
            context.move_to(left, y)
            context.line_to(right, y)
            context.stroke()
            # Small tick mark on left edge
            context.set_source_rgba(0.50, 0.58, 0.68, 0.35)
            context.set_line_width(1)
            context.move_to(left - 4, y)
            context.line_to(left, y)
            context.stroke()
            # Label
            context.set_source_rgba(
                0.55, 0.62, 0.72,
                0.70 if is_major else (0.50 if is_mid else 0.35),
            )
            text_str = str(value)
            extents = context.text_extents(text_str)
            context.move_to(left - 8 - extents.width, y + 3.5)
            context.show_text(text_str)

        # ── X-axis gridlines: time ticks every 30 seconds ──
        total_seconds = minutes * 60
        tick_interval = 30  # seconds
        num_ticks = total_seconds // tick_interval
        for tick in range(num_ticks + 1):
            seconds_ago = total_seconds - tick * tick_interval
            x = left + plot_width * tick / max(1, num_ticks)
            is_minute = seconds_ago % 60 == 0
            # Vertical gridline
            context.set_line_width(0.7 if is_minute else 0.4)
            context.set_source_rgba(
                0.45, 0.52, 0.62,
                0.15 if is_minute else 0.07,
            )
            context.move_to(x, top)
            context.line_to(x, bottom)
            context.stroke()
            # Small tick mark on bottom edge
            context.set_source_rgba(0.50, 0.58, 0.68, 0.35)
            context.set_line_width(1)
            context.move_to(x, bottom)
            context.line_to(x, bottom + 4)
            context.stroke()
            # Label
            if is_minute or num_ticks <= 4:
                context.set_source_rgba(0.55, 0.62, 0.72, 0.60)
                if seconds_ago == 0:
                    time_label = "now"
                elif seconds_ago < 60:
                    time_label = f"-{seconds_ago}s"
                else:
                    m = seconds_ago // 60
                    s = seconds_ago % 60
                    time_label = f"-{m}m" if s == 0 else f"-{m}m{s:02d}s"
                extents = context.text_extents(time_label)
                label_x = x - extents.width / 2
                label_x = max(left, min(right - extents.width, label_x))
                context.move_to(label_x, bottom + 15)
                context.show_text(time_label)

        # ── Axis labels ──
        # Y-axis label (rotated)
        context.save()
        context.set_font_size(9)
        context.set_source_rgba(0.50, 0.58, 0.68, 0.60)
        y_label = "Usage (%)"
        extents = context.text_extents(y_label)
        context.move_to(10, top + plot_height / 2 + extents.width / 2)
        context.rotate(-1.5708)  # -90 degrees
        context.show_text(y_label)
        context.restore()

        # X-axis label
        context.set_font_size(9)
        context.set_source_rgba(0.50, 0.58, 0.68, 0.60)
        x_label = "Time"
        extents = context.text_extents(x_label)
        context.move_to(left + plot_width / 2 - extents.width / 2, height - 6)
        context.show_text(x_label)

        # ── Plot border ──
        context.set_source_rgba(0.30, 0.38, 0.48, 0.30)
        context.set_line_width(1.0)
        context.rectangle(left, top, plot_width, plot_height)
        context.stroke()

        # ── Draw data series ──
        # Collect tooltip data while drawing
        tooltip_data = []
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

                # Fill gradient under the curve
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

                fill_gradient = cairo.LinearGradient(0, top, 0, bottom)
                fill_gradient.add_color_stop_rgba(0, red, green, blue, 0.14)
                fill_gradient.add_color_stop_rgba(1, red, green, blue, 0.01)
                context.set_source(fill_gradient)
                context.fill()

                # Redraw curve for the stroke
                context.move_to(*points[0])
                for point_index in range(1, len(points)):
                    p0 = points[max(0, point_index - 2)]
                    p1 = points[point_index - 1]
                    p2 = points[point_index]
                    p3 = points[min(len(points) - 1, point_index + 1)]
                    cp1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
                    cp2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
                    context.curve_to(*cp1, *cp2, *p2)

                # Glow pass
                context.set_line_width(3.5)
                context.set_source_rgba(red, green, blue, 0.15)
                context.stroke_preserve()

                # Main line
                context.set_line_width(1.6)
                context.set_source_rgba(red, green, blue, 0.92)
                context.stroke()

                # Latest value dot
                last_point = points[-1]
                context.set_source_rgba(red, green, blue, 0.25)
                context.arc(last_point[0], last_point[1], 4.5, 0, 6.2832)
                context.fill()
                context.set_source_rgba(red, green, blue, 0.95)
                context.arc(last_point[0], last_point[1], 2.2, 0, 6.2832)
                context.fill()

            # Collect for tooltip: map sample index → x position, store samples
            tooltip_data.append((key, title, colour, samples, denominator, left, plot_width))

        # ── Hover tooltip ──
        hover_x = getattr(self, "device_chart_hover_x", -1)
        hover_y = getattr(self, "device_chart_hover_y", -1)
        if left <= hover_x <= right and top <= hover_y <= bottom and tooltip_data:
            # Draw crosshair line
            context.set_source_rgba(0.70, 0.76, 0.84, 0.30)
            context.set_line_width(0.8)
            context.move_to(hover_x, top)
            context.line_to(hover_x, bottom)
            context.stroke()

            # Find the sample index closest to the hover x position
            # Use the first series to figure out the sample mapping
            _key0, _title0, _colour0, samples0, denom0, left0, pw0 = tooltip_data[0]
            if denom0 > 0 and pw0 > 0:
                hover_index = round((hover_x - left0) / pw0 * denom0)
                hover_index = max(0, min(denom0, hover_index))

                # Collect visible metric values at this index
                lines = []
                for key, title, colour, samples, _denom, _l, _pw in tooltip_data:
                    if key not in self.device_visible_metrics:
                        continue
                    if 0 <= hover_index < len(samples) and samples[hover_index] is not None:
                        formatted = self._format_metric(key, samples[hover_index])
                        lines.append((title, formatted, colour))

                if lines:
                    # Compute time ago
                    total_samples = len(samples0)
                    samples_from_now = max(0, total_samples - 1 - hover_index)
                    seconds_ago_hover = samples_from_now  # 1 sample per second
                    if seconds_ago_hover == 0:
                        time_text = "Now"
                    elif seconds_ago_hover < 60:
                        time_text = f"{seconds_ago_hover}s ago"
                    else:
                        m_ago = seconds_ago_hover // 60
                        s_ago = seconds_ago_hover % 60
                        time_text = f"{m_ago}m {s_ago:02d}s ago"

                    # Measure tooltip size
                    context.set_font_size(9.5)
                    max_title_w = 0
                    max_value_w = 0
                    for title, formatted, _c in lines:
                        te = context.text_extents(title)
                        max_title_w = max(max_title_w, te.width)
                        ve = context.text_extents(formatted)
                        max_value_w = max(max_value_w, ve.width)
                    time_extents = context.text_extents(time_text)

                    tooltip_w = max(max_title_w + max_value_w + 40, time_extents.width + 24)
                    line_height = 16
                    tooltip_h = 10 + 16 + 6 + len(lines) * line_height + 8
                    tooltip_x = hover_x + 14
                    tooltip_y = hover_y - tooltip_h / 2

                    # Keep tooltip within the chart area
                    if tooltip_x + tooltip_w > right - 4:
                        tooltip_x = hover_x - tooltip_w - 14
                    tooltip_y = max(top + 2, min(bottom - tooltip_h - 2, tooltip_y))

                    # Draw tooltip background
                    self._draw_rounded_rect(context, tooltip_x, tooltip_y, tooltip_w, tooltip_h, 6)
                    context.set_source_rgba(0.05, 0.07, 0.10, 0.92)
                    context.fill_preserve()
                    context.set_source_rgba(0.35, 0.42, 0.52, 0.55)
                    context.set_line_width(1)
                    context.stroke()

                    # Time header
                    context.set_source_rgba(0.65, 0.72, 0.82, 0.85)
                    context.set_font_size(9)
                    context.move_to(tooltip_x + 10, tooltip_y + 15)
                    context.show_text(time_text)

                    # Metric lines
                    context.set_font_size(9.5)
                    for i, (title, formatted, colour) in enumerate(lines):
                        line_y = tooltip_y + 10 + 16 + 4 + i * line_height
                        r, g, b = self._hex_rgb(colour)
                        # Colour dot
                        context.set_source_rgba(r, g, b, 0.95)
                        context.arc(tooltip_x + 14, line_y + 2, 3, 0, 6.2832)
                        context.fill()
                        # Title
                        context.set_source_rgba(0.78, 0.83, 0.90, 0.90)
                        context.move_to(tooltip_x + 22, line_y + 5)
                        context.show_text(title)
                        # Value (right-aligned)
                        ve = context.text_extents(formatted)
                        context.set_source_rgba(0.95, 0.97, 1.0, 0.95)
                        context.move_to(tooltip_x + tooltip_w - 10 - ve.width, line_y + 5)
                        context.show_text(formatted)

    @staticmethod
    def _draw_rounded_rect(context, x, y, w, h, r):
        """Draw a rounded rectangle path."""
        context.new_sub_path()
        context.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        context.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        context.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        context.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        context.close_path()

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
