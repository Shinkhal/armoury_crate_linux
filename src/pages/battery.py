"""Battery page UI and interactions."""
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


class BatteryPage:
    def build_battery(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("main-content")
        outer.add_css_class("battery-page")
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.add_css_class("battery-layout")
        page.set_vexpand(True)
        page.set_margin_start(26)
        page.set_margin_end(26)
        page.set_margin_top(22)
        page.set_margin_bottom(24)

        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        columns.add_css_class("battery-columns")
        columns.set_vexpand(True)

        self.selected_limit = nearest_charge_limit(read_limit())
        preview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        preview.add_css_class("battery-preview-panel")
        preview.set_size_request(350, -1)
        preview.set_vexpand(True)
        preview_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        preview_header.append(label("BATTERY HEALTH", "battery-preview-heading"))
        preview_header.append(Gtk.Box(hexpand=True))
        preview_header.append(label("ASUS FIRMWARE", "battery-preview-badge"))
        preview.append(preview_header)

        battery_art = Gtk.Overlay()
        self.battery_visual = Gtk.DrawingArea()
        self.battery_visual.set_content_width(330)
        self.battery_visual.set_content_height(440)
        self.battery_visual.set_hexpand(True)
        self.battery_visual.add_css_class("battery-visual")
        self.battery_visual.set_draw_func(self.draw_battery_visual)
        battery_art.set_child(self.battery_visual)
        self.battery_visual_value = label(f"{self.selected_limit}%", "battery-visual-value")
        self.battery_visual_value.set_halign(Gtk.Align.CENTER)
        self.battery_visual_value.set_valign(Gtk.Align.CENTER)
        battery_art.add_overlay(self.battery_visual_value)
        preview.append(battery_art)
        self.battery_visual_label = label("", "battery-visual-label")
        self.battery_visual_label.set_halign(Gtk.Align.CENTER)
        preview.append(self.battery_visual_label)
        self.battery_visual_hint = label("Selected charging ceiling", "battery-visual-hint")
        self.battery_visual_hint.set_halign(Gtk.Align.CENTER)
        preview.append(self.battery_visual_hint)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right.set_hexpand(True)
        right.set_vexpand(True)
        right.append(label("POWER MANAGEMENT", "eyebrow"))
        right.append(label("ASUS Battery Health Charging", "page-title"))
        intro = label("Choose a charging mode to help protect your battery lifespan.", "battery-page-copy")
        intro.set_wrap(True)
        right.append(intro)
        right.append(label("CHARGING MODE", "battery-section-title"))

        modes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        modes.add_css_class("battery-mode-list")
        self.battery_mode_buttons = {}
        self.battery_mode_indicators = {}
        for limit, title, description, caption, _icon in BATTERY_MODES:
            button = Gtk.Button()
            button.add_css_class("battery-mode-card")
            button.add_css_class(f"battery-limit-{limit}")
            card_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
            radio = label("○", "battery-mode-radio")
            radio.set_valign(Gtk.Align.CENTER)
            header.append(radio)
            title_label = label(title, "battery-mode-title")
            title_label.set_hexpand(True)
            title_label.set_halign(Gtk.Align.START)
            header.append(title_label)
            header.append(label(f"{limit}%", "battery-mode-limit"))
            card_content.append(header)
            description_label = label(description, "battery-mode-description")
            description_label.set_wrap(True)
            description_label.set_xalign(0)
            card_content.append(description_label)
            caption_label = label(caption.upper(), "battery-mode-caption")
            caption_label.set_xalign(0)
            card_content.append(caption_label)
            button.set_child(card_content)
            button.set_hexpand(True)
            button.connect("clicked", self.on_battery_mode_selected, limit)
            modes.append(button)
            self.battery_mode_buttons[limit] = button
            self.battery_mode_indicators[limit] = radio
        right.append(modes)

        self.limit_feedback = label("", "battery-feedback")
        self.limit_feedback.set_wrap(True)
        right.append(self.limit_feedback)

        columns.append(right)
        columns.append(preview)
        page.append(columns)

        live_footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        live_footer.add_css_class("battery-live-footer")
        live_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        live_header.add_css_class("battery-live-header")
        live_header.append(label("LIVE BATTERY STATUS", "battery-section-title"))
        live_header.append(Gtk.Box(hexpand=True))
        live_header.append(label("● LIVE", "battery-live-indicator"))
        live_footer.append(live_header)
        live_grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        live_grid.add_css_class("battery-live-grid")
        self.battery_status_value = self.add_battery_live_item(live_grid, "SAVED CHARGE LIMIT", "—")
        self.battery_level_value = self.add_battery_live_item(live_grid, "BATTERY LEVEL", "—")
        self.battery_power_value = self.add_battery_live_item(live_grid, "POWER SOURCE", "Checking…")
        self.battery_charge_value = self.add_battery_live_item(live_grid, "CHARGE STATE", "Checking…")
        self.battery_control_value = self.add_battery_live_item(live_grid, "CONTROL", "Firmware controlled")
        live_footer.append(live_grid)
        page.append(live_footer)

        scroll.set_child(page)
        outer.append(scroll)
        self.set_battery_mode(self.selected_limit)
        return outer

    def add_battery_live_item(self, parent, key, value):
        item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        item.add_css_class("battery-live-item")
        item.set_hexpand(True)
        item.append(label(key, "battery-live-key"))
        value_label = label(value, "battery-live-value")
        value_label.set_wrap(True)
        value_label.set_xalign(0)
        item.append(value_label)
        parent.append(item)
        return value_label

    def on_apply_limit(self, _button):
        value = self.selected_limit
        result = command(["asusctl", "battery", "limit", str(value)])
        if result.returncode != 0:
            ok = set_prop("ChargeControlEndThreshold", GLib.Variant("y", value))
            if not ok:
                error = (result.stderr or result.stdout).strip() or "asusd unavailable"
                self.limit_feedback.set_text(f"Apply failed: {error}")
                self.toast("Could not apply battery limit")
                return
        confirmed = read_limit()
        self.refresh()
        if confirmed == value:
            self.limit_feedback.set_text(f"Applied and verified: stop charging at {value}%.")
            self.toast(f"Battery limit applied · {value}% verified")
        else:
            self.limit_feedback.set_text(f"Requested {value}%; system reports {confirmed if confirmed is not None else 'no value'}. Please refresh or inspect asusd.")
            self.toast("Battery limit did not verify — see status below")

    def draw_battery_visual(self, _area, cr, width, height):
        accent = {
            100: (1.0, .72, .20),
            80: (.15, .78, .95),
            60: (.34, .91, .42),
        }.get(self.selected_limit, (.15, .78, .95))

        def rounded_rect(x, y, w, h, radius):
            cr.new_sub_path()
            cr.arc(x + w - radius, y + radius, radius, -math.pi / 2, 0)
            cr.arc(x + w - radius, y + h - radius, radius, 0, math.pi / 2)
            cr.arc(x + radius, y + h - radius, radius, math.pi / 2, math.pi)
            cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
            cr.close_path()

        center_x = width / 2
        body_w = min(205, width * .48)
        body_h = min(340, height * .78)
        depth = min(21, width * .05)
        left = center_x - (body_w + depth) / 2
        top = (height - body_h) / 2 + 5
        for expand, alpha in ((16, .018), (10, .035), (4, .07)):
            cr.set_source_rgba(*accent, alpha)
            rounded_rect(left - expand, top - expand, body_w + expand * 2, body_h + expand * 2, 18 + expand)
            cr.fill()

        cr.new_path()
        cr.move_to(left + body_w - 2, top + 10)
        cr.line_to(left + body_w + depth, top + 17)
        cr.line_to(left + body_w + depth, top + body_h - 12)
        cr.line_to(left + body_w - 2, top + body_h)
        cr.close_path()
        cr.set_source_rgba(accent[0] * .2, accent[1] * .3, accent[2] * .34, .92)
        cr.fill()

        cr.set_source_rgba(.10, .16, .18, 1)
        rounded_rect(left, top, body_w, body_h, 17)
        cr.fill()
        inner_x = left + 11
        inner_y = top + 12
        inner_w = body_w - 22
        inner_h = body_h - 24
        fill_h = inner_h * self.selected_limit / 100
        fill_y = inner_y + inner_h - fill_h
        cr.set_source_rgba(accent[0], accent[1], accent[2], .16)
        rounded_rect(inner_x, inner_y, inner_w, inner_h, 9)
        cr.fill()
        cr.set_source_rgba(*accent, .46)
        rounded_rect(inner_x + 2, fill_y, inner_w - 4, fill_h - 2, 8)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, .09)
        rounded_rect(inner_x + 7, fill_y + 5, 5, max(8, fill_h - 16), 3)
        cr.fill()
        for segment in range(1, 5):
            y = inner_y + inner_h * segment / 5
            cr.set_source_rgba(.03, .08, .09, .25)
            cr.set_line_width(1)
            cr.move_to(inner_x + 4, y)
            cr.line_to(inner_x + inner_w - 4, y)
            cr.stroke()

        cr.set_source_rgba(*accent, .95)
        cr.set_line_width(2.2)
        rounded_rect(left, top, body_w, body_h, 17)
        cr.stroke()
        cr.set_source_rgba(accent[0] * .58, accent[1] * .66, accent[2] * .7, .96)
        rounded_rect(center_x - 17, top - 10, 34, 12, 5)
        cr.fill()

    def set_battery_mode(self, value):
        value = nearest_charge_limit(value)
        self.selected_limit = value
        if hasattr(self, "battery_visual_value"):
            self.battery_visual_value.set_text(f"{value}%")
            mode_title = next(title for limit, title, *_rest in BATTERY_MODES if limit == value)
            self.battery_visual_label.set_text(mode_title)
            self.battery_visual.queue_draw()
        for limit, button in getattr(self, "battery_mode_buttons", {}).items():
            selected = limit == value
            if selected:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")
            indicator = getattr(self, "battery_mode_indicators", {}).get(limit)
            if indicator is not None:
                indicator.set_text("◉" if selected else "○")

    def on_battery_mode_selected(self, _button, value):
        self.set_battery_mode(value)
        mode = next(title for limit, title, *_rest in BATTERY_MODES if limit == value)
        self.limit_feedback.set_text(f"Applying {mode}…")
        self.on_apply_limit(None)

    def on_limit_changed(self, _scale):
        return

    def on_oneshot(self, _button):
        result = command(["asusctl", "battery", "oneshot"])
        if result.returncode == 0:
            self.toast("One-time full charge requested")
        else:
            self.toast("Could not request full charge: " + ((result.stderr or result.stdout).strip() or "asusctl unavailable"))
