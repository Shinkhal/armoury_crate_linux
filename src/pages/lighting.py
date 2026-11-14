"""Lighting page UI and interactions."""
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


class LightingPage:
    def build_lighting(self):
        outer, c = self.page_shell(
            "PERSONALIZATION",
            "Keyboard Lighting",
            "Choose an Aura effect, set its colors, and adjust the keyboard backlight.",
        )
        effect_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        effect_group.add_css_class("surface")
        effect_group.append(label("LIGHTING EFFECT", "surface-title"))
        self.effect_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new([EFFECT_LABELS[name] for name in EFFECT_OPTIONS])
        )
        self.effect_dropdown.set_hexpand(True)
        effect_group.append(self.effect_dropdown)
        self.effect_description = label("", "lighting-description")
        effect_group.append(self.effect_description)

        options = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        self.speed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.speed_row.append(label("SPEED", "opt-key"))
        self.speed_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(AURA_SPEED_LABELS)
        )
        self.speed_dropdown.set_selected(1)
        self.speed_row.append(self.speed_dropdown)
        options.append(self.speed_row)

        self.direction_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.direction_row.append(label("DIRECTION", "opt-key"))
        self.direction_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(AURA_DIRECTION_LABELS)
        )
        self.direction_dropdown.set_selected(2)
        self.direction_row.append(self.direction_dropdown)
        options.append(self.direction_row)
        effect_group.append(options)

        self.apply_effect_button = Gtk.Button(label="Apply lighting effect")
        self.apply_effect_button.add_css_class("accent-button")
        self.apply_effect_button.set_halign(Gtk.Align.START)
        self.apply_effect_button.connect("clicked", self.on_apply_effect)
        effect_group.append(self.apply_effect_button)
        c.append(effect_group)

        colour_section = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.colour_controls = {}
        self.primary_colour_group = self.build_colour_control(
            "PRIMARY COLOR", "primary", AURA_DEFAULT_COLOUR
        )
        self.secondary_colour_group = self.build_colour_control(
            "SECONDARY COLOR", "secondary", "1769ff"
        )
        self.primary_colour_group.set_hexpand(True)
        self.secondary_colour_group.set_hexpand(True)
        colour_section.append(self.primary_colour_group)
        colour_section.append(self.secondary_colour_group)
        c.append(colour_section)

        brightness_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        brightness_group.add_css_class("surface")
        brightness_group.append(label("KEYBOARD BACKLIGHT", "surface-title"))
        brightness_group.append(label(
            "This firmware exposes four single-zone brightness levels; per-key RGB is not available.",
            "subtle",
        ))
        self.brightness_dirty = False
        self.syncing_brightness = True
        brightness_options = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.brightness_buttons = []
        previous = None
        for index, title in enumerate(("Off", "Low", "Medium", "High")):
            button = Gtk.ToggleButton(label=title)
            button.add_css_class("brightness-option")
            if previous is not None:
                button.set_group(previous)
            else:
                previous = button
            button.set_tooltip_text(f"Set keyboard backlight to {title.lower()}")
            button.connect("toggled", self.on_brightness_option_toggled, index)
            self.brightness_buttons.append(button)
            brightness_options.append(button)
        brightness_group.append(brightness_options)
        self.brightness_feedback = label("", "subtle")
        brightness_group.append(self.brightness_feedback)
        self.brightness_buttons[0].set_active(True)
        self.syncing_brightness = False
        apply_brightness = Gtk.Button(label="Apply brightness")
        apply_brightness.add_css_class("accent-button")
        apply_brightness.set_halign(Gtk.Align.START)
        apply_brightness.connect("clicked", self.on_apply_brightness)
        brightness_group.append(apply_brightness)
        c.append(brightness_group)

        self.effect_dropdown.connect("notify::selected", self.on_effect_selected)
        self.on_effect_selected(self.effect_dropdown, None)
        return outer

    def build_colour_control(self, title, slot, initial_colour):
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        group.add_css_class("surface")
        group.append(label(title, "surface-title"))

        palette_grid = Gtk.Grid(column_spacing=5, row_spacing=5)
        palette_grid.add_css_class("color-palette")
        control = {
            "hex": initial_colour.lower(),
            "valid": True,
            "entry": None,
            "picker": None,
            "preview": None,
            "buttons": [],
        }
        self.colour_controls[slot] = control
        for index, (name, colour) in enumerate(AURA_PRESETS.items()):
            button = Gtk.Button()
            button.add_css_class("color-swatch")
            button.set_tooltip_text(f"{name} · #{colour.upper()}")
            chip = Gtk.DrawingArea()
            chip.add_css_class("color-chip")
            chip.set_content_width(22)
            chip.set_content_height(22)
            chip.set_draw_func(self.draw_colour_chip, colour)
            button.set_child(chip)
            button.connect("clicked", self.on_colour_preset_clicked, slot, colour)
            palette_grid.attach(button, index % 6, index // 6, 1, 1)
            control["buttons"].append((colour, button))
        group.append(palette_grid)
        group.append(Gtk.Separator())

        custom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        custom_row.append(label("HEX", "opt-key"))
        picker = None
        initial_rgba = make_rgba(initial_colour)
        if hasattr(Gtk, "ColorDialogButton"):
            picker = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
            picker.set_rgba(initial_rgba)
            picker.connect("notify::rgba", self.on_colour_picker_changed, slot)
            picker.set_tooltip_text("Open the color picker")
        elif hasattr(Gtk, "ColorButton"):
            picker = Gtk.ColorButton.new_with_rgba(initial_rgba)
            picker.connect("color-set", self.on_colour_picker_changed, slot)
            picker.set_tooltip_text("Open the color picker")
        if picker is not None:
            picker.add_css_class("color-picker-button")
            control["picker"] = picker
            custom_row.append(picker)

        entry = Gtk.Entry()
        entry.add_css_class("hex-entry")
        entry.set_width_chars(8)
        entry.set_max_length(7)
        entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        entry.set_placeholder_text("#RRGGBB")
        entry.set_text("#" + initial_colour.upper())
        entry.connect("changed", self.on_colour_entry_changed, slot)
        control["entry"] = entry
        custom_row.append(entry)

        preview = Gtk.DrawingArea()
        preview.add_css_class("color-chip")
        preview.set_content_width(28)
        preview.set_content_height(28)
        preview.set_draw_func(self.draw_colour_chip, initial_colour)
        control["preview"] = preview
        custom_row.append(preview)
        custom_row.set_hexpand(True)
        group.append(custom_row)
        self.set_colour_value(slot, initial_colour, update_picker=False)
        return group

    def draw_colour_chip(self, _area, context, width, height, hex_colour):
        colour = hex_colour.lstrip("#")
        red, green, blue = (int(colour[offset:offset + 2], 16) / 255 for offset in (0, 2, 4))
        radius = max(1, min(width, height) * 0.39)
        context.arc(width / 2, height / 2, radius, 0, 6.283185307179586)
        context.set_source_rgb(red, green, blue)
        context.fill_preserve()
        context.set_line_width(1.3)
        context.set_source_rgba(1, 1, 1, 0.72)
        context.stroke()

    def set_colour_value(self, slot, colour, update_entry=True, update_picker=True):
        colour = colour.lower().lstrip("#")
        control = self.colour_controls[slot]
        control["hex"] = colour
        control["valid"] = True
        self.syncing_colours = True
        try:
            if update_entry and control["entry"].get_text() != "#" + colour.upper():
                control["entry"].set_text("#" + colour.upper())
            control["entry"].remove_css_class("invalid")
            if update_picker and control["picker"] is not None:
                rgba = make_rgba(colour)
                if rgba is not None:
                    control["picker"].set_rgba(rgba)
            control["preview"].set_draw_func(self.draw_colour_chip, colour)
            control["preview"].queue_draw()
            for preset_colour, button in control["buttons"]:
                if preset_colour == colour:
                    button.add_css_class("selected")
                else:
                    button.remove_css_class("selected")
        finally:
            self.syncing_colours = False

    def on_colour_preset_clicked(self, _button, slot, colour):
        self.set_colour_value(slot, colour)

    def on_colour_picker_changed(self, widget, parameter, slot=None):
        slot = parameter if slot is None else slot
        if self.syncing_colours:
            return
        self.set_colour_value(slot, rgba_hex(widget.get_rgba()), update_picker=False)

    def on_colour_entry_changed(self, entry, slot):
        if self.syncing_colours:
            return
        colour = entry.get_text().strip().lstrip("#")
        if len(colour) != 6 or any(char not in "0123456789abcdefABCDEF" for char in colour):
            self.colour_controls[slot]["valid"] = False
            entry.add_css_class("invalid")
            return
        rgba = make_rgba(colour)
        if rgba is None:
            self.colour_controls[slot]["valid"] = False
            entry.add_css_class("invalid")
            return
        self.set_colour_value(slot, colour, update_entry=False)

    def on_brightness_option_toggled(self, button, index):
        if button.get_active():
            button.add_css_class("active")
        else:
            button.remove_css_class("active")
        if button.get_active() and not self.syncing_brightness:
            self.brightness_dirty = True
            titles = ("off", "low", "medium", "high")
            self.brightness_feedback.set_text(
                f"Selected {titles[index]} · press Apply to save."
            )

    def on_effect_selected(self, _dropdown, _pspec):
        names = list(EFFECT_OPTIONS)
        index = self.effect_dropdown.get_selected()
        if index >= len(names):
            return
        effect = names[index]
        spec = EFFECT_OPTIONS[effect]
        self.primary_colour_group.set_visible(spec.get("colours", 0) >= 1)
        self.secondary_colour_group.set_visible(spec.get("colours", 0) >= 2)
        self.speed_row.set_visible(bool(spec.get("speed")))
        self.direction_row.set_visible(bool(spec.get("direction")))
        self.effect_description.set_text(EFFECT_DESCRIPTIONS[effect])

    def on_apply_effect(self, _button):
        names = list(EFFECT_OPTIONS)
        idx = self.effect_dropdown.get_selected()
        if idx >= len(names):
            return
        effect = names[idx]
        spec = EFFECT_OPTIONS[effect]
        required_colours = ["primary"] if spec.get("colours", 0) >= 1 else []
        if spec.get("colours", 0) >= 2:
            required_colours.append("secondary")
        if any(not self.colour_controls[slot]["valid"] for slot in required_colours):
            self.toast("Enter a valid color as six hexadecimal digits, like #FF2050.")
            return
        args = ["asusctl", "aura", "effect", effect]
        if spec.get("colours", 0) >= 1:
            args += ["--colour", self.colour_controls["primary"]["hex"]]
        if spec.get("colours", 0) >= 2:
            args += ["--colour2", self.colour_controls["secondary"]["hex"]]
        if spec.get("speed"):
            speed = self.speed_dropdown.get_selected()
            if speed >= len(AURA_SPEEDS):
                return
            args += ["--speed", AURA_SPEEDS[speed]]
        if spec.get("direction"):
            direction = self.direction_dropdown.get_selected()
            if direction >= len(AURA_DIRECTIONS):
                return
            args += ["--direction", AURA_DIRECTIONS[direction]]
        result = command(args)
        if result.returncode == 0:
            self.toast(f"Keyboard effect set to {EFFECT_LABELS[effect]}")
        else:
            self.toast("Could not apply effect: " + ((result.stderr or result.stdout).strip() or "asusctl error"))

    def on_apply_brightness(self, _button):
        value = next(
            (index for index, button in enumerate(self.brightness_buttons) if button.get_active()),
            None,
        )
        levels = ("off", "low", "med", "high")
        if value is None:
            return
        level = levels[value]
        result = command(["asusctl", "leds", "set", level])
        if result.returncode == 0:
            self.brightness_dirty = False
            self.brightness_feedback.set_text(f"Keyboard backlight set to {level}.")
            self.toast(f"Keyboard backlight set to {level}")
            self.refresh()
        else:
            self.toast("Could not set backlight: " + ((result.stderr or result.stdout).strip() or "asusctl error"))
