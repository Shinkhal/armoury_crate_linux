"""Lighting page UI and interactions."""
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


LIGHTING_STATE_PATH = os.path.join(GLib.get_user_config_dir(), "armoury-crate", "lighting-state.json")


def load_lighting_state():
    try:
        with open(LIGHTING_STATE_PATH, encoding="utf-8") as stream:
            state = json.load(stream)
        if not isinstance(state, dict):
            return {}
        return state
    except (OSError, ValueError):
        return {}


def save_lighting_state(state):
    try:
        os.makedirs(os.path.dirname(LIGHTING_STATE_PATH), exist_ok=True)
        temporary_path = LIGHTING_STATE_PATH + ".tmp"
        with open(temporary_path, "w", encoding="utf-8") as stream:
            json.dump(state, stream, separators=(",", ":"))
        os.replace(temporary_path, LIGHTING_STATE_PATH)
    except OSError:
        pass


class LightingPage:
    def build_lighting(self):
        outer, c = self.page_shell(
            "PERSONALIZATION",
            "Keyboard Lighting",
            "Select an Aura effect, customize its settings, and control keyboard brightness.",
        )
        layout = Gtk.Grid()
        layout.add_css_class("lighting-layout")
        layout.set_column_spacing(14)
        layout.set_row_spacing(14)

        effects_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        effects_panel.add_css_class("surface")
        effects_panel.add_css_class("lighting-effects-panel")
        effects_panel.append(self._lighting_section_header(
            "applications-graphics-symbolic", "Basic effects",
            "Choose an effect to preview it on your keyboard.",
        ))

        effects_grid = Gtk.Grid()
        effects_grid.add_css_class("lighting-effects-grid")
        effects_grid.set_column_spacing(7)
        effects_grid.set_row_spacing(7)
        effects_grid.set_column_homogeneous(True)
        self.effect_buttons = {}
        self.lighting_state = load_lighting_state()
        saved_effect = self.lighting_state.get("effect", "static")
        self.current_effect = saved_effect if saved_effect in EFFECT_OPTIONS else "static"
        self.syncing_effect = True
        previous = None
        effect_icons = {
            "static": ("color-select-symbolic", "applications-graphics-symbolic"),
            "breathe": ("weather-clear-symbolic", "applications-graphics-symbolic"),
            "rainbow-cycle": ("applications-graphics-symbolic", "view-refresh-symbolic"),
            "rainbow-wave": ("media-playlist-shuffle-symbolic", "applications-graphics-symbolic"),
            "rain": ("weather-showers-symbolic", "weather-clear-symbolic"),
            "stars": ("starred-symbolic", "emblem-favorite-symbolic"),
            "highlight": ("emblem-favorite-symbolic", "applications-graphics-symbolic"),
            "laser": ("media-record-symbolic", "applications-graphics-symbolic"),
            "ripple": ("view-refresh-symbolic", "applications-graphics-symbolic"),
            "pulse": ("audio-volume-high-symbolic", "applications-graphics-symbolic"),
            "comet": ("weather-clear-symbolic", "applications-graphics-symbolic"),
            "flash": ("weather-lightning-symbolic", "applications-graphics-symbolic"),
        }
        for index, effect in enumerate(EFFECT_OPTIONS):
            button = Gtk.ToggleButton()
            button.add_css_class("lighting-effect-button")
            button.set_hexpand(True)
            button.set_tooltip_text(EFFECT_DESCRIPTIONS[effect])
            if previous is not None:
                button.set_group(previous)
            else:
                previous = button
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
            tile.set_halign(Gtk.Align.CENTER)
            icon_name, fallback = effect_icons.get(effect, ("applications-graphics-symbolic", "image-x-generic-symbolic"))
            icon = self._lighting_icon(icon_name, fallback, 32)
            icon.add_css_class("lighting-effect-icon")
            tile.append(icon)
            title = label(EFFECT_LABELS[effect], "lighting-effect-label")
            title.set_justify(Gtk.Justification.CENTER)
            title.set_xalign(0.5)
            tile.append(title)
            button.set_child(tile)
            button.connect("toggled", self.on_effect_button_toggled, effect)
            effects_grid.attach(button, index % 4, index // 4, 1, 1)
            self.effect_buttons[effect] = button
        self.effect_buttons[self.current_effect].set_active(True)

        effects_panel.append(effects_grid)
        layout.attach(effects_panel, 0, 0, 1, 1)

        settings = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        settings.add_css_class("surface")
        settings.add_css_class("lighting-settings")
        settings_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        settings_header.append(self._lighting_icon("emblem-system-symbolic", "preferences-system-symbolic", 18))
        settings_header.append(label("SETTINGS", "lighting-settings-heading"))
        settings.append(settings_header)
        self.selected_effect_title = label("Static", "lighting-selected-effect")
        settings.append(self.selected_effect_title)
        self.effect_description = label("", "lighting-description")
        settings.append(self.effect_description)
        self.effect_feedback = label("", "lighting-status")
        settings.append(self.effect_feedback)
        settings.append(Gtk.Separator())

        settings.append(label("COLOR", "lighting-control-heading"))
        self.colour_controls = {}
        primary_colour = self._saved_colour("primary", AURA_DEFAULT_COLOUR)
        secondary_colour = self._saved_colour("secondary", "1769ff")
        self.primary_colour_group = self.build_colour_control("Primary", "primary", primary_colour)
        self.secondary_colour_group = self.build_colour_control("Secondary", "secondary", secondary_colour)
        settings.append(self.primary_colour_group)
        settings.append(self.secondary_colour_group)

        self.speed_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.speed_header = self._lighting_control_header("SPEED", "Medium")
        self.speed_row.append(self.speed_header)
        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, len(AURA_SPEEDS) - 1, 1)
        self.speed_scale.set_draw_value(False)
        self.speed_scale.set_round_digits(0)
        saved_speed = self.lighting_state.get("speed", 1)
        self.speed_scale.set_value(saved_speed if isinstance(saved_speed, int) and 0 <= saved_speed < len(AURA_SPEEDS) else 1)
        self.speed_scale.add_mark(0, Gtk.PositionType.BOTTOM, "Low")
        self.speed_scale.add_mark(1, Gtk.PositionType.BOTTOM, "Medium")
        self.speed_scale.add_mark(2, Gtk.PositionType.BOTTOM, "High")
        self.speed_scale.add_css_class("lighting-slider")
        self.speed_scale.connect("value-changed", self.on_effect_option_changed)
        self.speed_row.append(self.speed_scale)
        settings.append(self.speed_row)

        self.direction_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self.direction_row.append(label("DIRECTION", "lighting-control-heading"))
        direction_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.direction_buttons = []
        previous_direction = None
        direction_icons = ("go-up-symbolic", "go-down-symbolic", "go-previous-symbolic", "go-next-symbolic")
        for index, (direction, direction_icon) in enumerate(zip(AURA_DIRECTIONS, direction_icons)):
            button = Gtk.ToggleButton()
            button.add_css_class("lighting-direction-button")
            button.set_tooltip_text(AURA_DIRECTION_LABELS[index])
            if previous_direction is not None:
                button.set_group(previous_direction)
            else:
                previous_direction = button
            button.set_child(self._lighting_icon(direction_icon, "go-next-symbolic", 16))
            button.connect("toggled", self.on_direction_button_toggled, index)
            direction_buttons.append(button)
            self.direction_buttons.append(button)
        saved_direction = self.lighting_state.get("direction", 2)
        if not isinstance(saved_direction, int) or not 0 <= saved_direction < len(self.direction_buttons):
            saved_direction = 2
        self.direction_buttons[saved_direction].set_active(True)
        self.direction_row.append(direction_buttons)
        settings.append(self.direction_row)

        settings.append(Gtk.Separator())
        brightness_heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        brightness_heading.append(self._lighting_icon("input-keyboard-symbolic", "preferences-desktop-keyboard-symbolic", 17))
        brightness_heading.append(label("BRIGHTNESS", "lighting-control-heading"))
        brightness_heading.append(Gtk.Box(hexpand=True))
        self.brightness_value_label = label("—", "lighting-brightness-value")
        brightness_heading.append(self.brightness_value_label)
        settings.append(brightness_heading)
        self.syncing_brightness = True
        self.last_brightness_level = None
        self.brightness_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 3, 1)
        self.brightness_scale.set_draw_value(False)
        self.brightness_scale.set_round_digits(0)
        for index, title in enumerate(("Off", "Low", "Medium", "High")):
            self.brightness_scale.add_mark(index, Gtk.PositionType.BOTTOM, "")
        self.brightness_scale.add_css_class("lighting-slider")
        self.brightness_scale.connect("value-changed", self.on_brightness_scale_changed)
        settings.append(self.brightness_scale)
        self.brightness_feedback = label("", "lighting-status")
        settings.append(self.brightness_feedback)
        self.syncing_brightness = False
        self.syncing_effect = False

        layout.attach(settings, 1, 0, 1, 1)
        c.append(layout)

        self.on_effect_selected(self.current_effect)
        self.refresh_lighting_state()
        return outer

    def _saved_colour(self, slot, default):
        value = self.lighting_state.get(slot, default)
        if isinstance(value, str) and len(value.lstrip("#")) == 6:
            try:
                int(value.lstrip("#"), 16)
                return value.lstrip("#").lower()
            except ValueError:
                pass
        return default

    def refresh_lighting_state(self):
        """Read keyboard brightness from the kernel's live LED state."""
        brightness_path = "/sys/class/leds/asus::kbd_backlight/brightness"
        maximum_path = "/sys/class/leds/asus::kbd_backlight/max_brightness"
        try:
            with open(brightness_path, encoding="utf-8") as stream:
                brightness = int(stream.read().strip())
            with open(maximum_path, encoding="utf-8") as stream:
                maximum = int(stream.read().strip())
        except (OSError, ValueError):
            saved_level = self.lighting_state.get("brightness")
            if isinstance(saved_level, int) and 0 <= saved_level <= 3:
                self.syncing_brightness = True
                self.brightness_scale.set_value(saved_level)
                self.syncing_brightness = False
                self.last_brightness_level = saved_level
                self.on_brightness_scale_changed(self.brightness_scale)
            return
        if maximum <= 0:
            return
        level = max(0, min(3, round(brightness * 3 / maximum)))
        self.syncing_brightness = True
        self.brightness_scale.set_value(level)
        self.syncing_brightness = False
        self.last_brightness_level = level
        self.on_brightness_scale_changed(self.brightness_scale)

    @staticmethod
    def _lighting_icon(icon_name, fallback, size):
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        image = Gtk.Image.new_from_icon_name(icon_name if theme.has_icon(icon_name) else fallback)
        image.set_pixel_size(size)
        return image

    def _lighting_section_header(self, icon_name, title, description):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.add_css_class("lighting-section-header")
        icon = self._lighting_icon(icon_name, "applications-graphics-symbolic", 22)
        icon.add_css_class("lighting-section-icon")
        header.append(icon)
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        copy.set_hexpand(True)
        copy.append(label(title, "lighting-section-title"))
        copy.append(label(description, "lighting-section-description"))
        header.append(copy)
        return header

    @staticmethod
    def _lighting_control_header(title, value):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.append(label(title, "lighting-control-heading"))
        header.append(Gtk.Box(hexpand=True))
        header.append(label(value, "lighting-brightness-value"))
        return header

    def build_colour_control(self, title, slot, initial_colour):
        group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        group.add_css_class("lighting-color-row")
        group.append(label(title.upper(), "lighting-color-label"))
        group.append(Gtk.Box(hexpand=True))
        control = {
            "hex": initial_colour.lower(),
            "valid": True,
            "entry": None,
            "picker": None,
            "preview": None,
            "buttons": [],
        }
        self.colour_controls[slot] = control
        swatch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        preset_colours = (
            ("ROG Red", "ff2050"), ("Ice Blue", "00d6e8"),
            ("Blue", "1769ff"), ("White", "f5f5f5"),
        )
        previous = None
        for name, colour in preset_colours:
            button = Gtk.ToggleButton()
            button.add_css_class("lighting-color-swatch")
            button.set_tooltip_text(f"{name} · #{colour.upper()}")
            if previous is not None:
                button.set_group(previous)
            else:
                previous = button
            chip = Gtk.DrawingArea()
            chip.set_content_width(17)
            chip.set_content_height(17)
            chip.set_draw_func(self.draw_colour_chip, colour)
            button.set_child(chip)
            button.connect("clicked", self.on_colour_preset_clicked, slot, colour)
            swatch_box.append(button)
            control["buttons"].append((colour, button))
        group.append(swatch_box)

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
            picker.set_size_request(36, 36)
            control["picker"] = picker
            picker_overlay = Gtk.Overlay()
            picker_overlay.add_css_class("lighting-color-picker-overlay")
            picker_overlay.set_size_request(38, 38)
            picker_overlay.set_child(picker)
            pin = self._lighting_icon("color-picker-symbolic", "color-select-symbolic", 12)
            pin.add_css_class("lighting-color-picker-pin")
            pin.set_halign(Gtk.Align.CENTER)
            pin.set_valign(Gtk.Align.CENTER)
            picker_overlay.add_overlay(pin)
            group.append(picker_overlay)

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
            if control["entry"] is not None and update_entry and control["entry"].get_text() != "#" + colour.upper():
                control["entry"].set_text("#" + colour.upper())
            if control["entry"] is not None:
                control["entry"].remove_css_class("invalid")
            if update_picker and control["picker"] is not None:
                rgba = make_rgba(colour)
                if rgba is not None:
                    control["picker"].set_rgba(rgba)
            if control["preview"] is not None:
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
        self.on_apply_effect(None)

    def on_colour_picker_changed(self, widget, parameter, slot=None):
        slot = parameter if slot is None else slot
        if self.syncing_colours:
            return
        self.set_colour_value(slot, rgba_hex(widget.get_rgba()), update_picker=False)
        self.on_apply_effect(None)

    def on_brightness_scale_changed(self, scale):
        value = round(scale.get_value())
        titles = ("Off", "Low", "Medium", "High")
        self.brightness_value_label.set_text(f"{titles[value]} · {round(value * 100 / 3)}%")
        if self.syncing_brightness:
            return
        if value == self.last_brightness_level:
            return
        self.last_brightness_level = value
        self.brightness_feedback.set_text(f"Setting keyboard backlight to {titles[value].lower()}…")
        self.apply_brightness_level(value)

    def on_effect_button_toggled(self, button, effect):
        if not button.get_active() or self.syncing_effect:
            return
        self.current_effect = effect
        self.on_effect_selected(effect)
        self.on_apply_effect(None)

    def on_effect_option_changed(self, _scale):
        value = round(self.speed_scale.get_value())
        self.speed_header.get_last_child().set_text(AURA_SPEED_LABELS[value])
        if not self.syncing_effect:
            self.on_apply_effect(None)

    def on_direction_button_toggled(self, button, index):
        if button.get_active() and not self.syncing_effect:
            self.on_apply_effect(None)

    def on_effect_selected(self, effect):
        spec = EFFECT_OPTIONS[effect]
        self.primary_colour_group.set_visible(spec.get("colours", 0) >= 1)
        self.secondary_colour_group.set_visible(spec.get("colours", 0) >= 2)
        self.speed_row.set_visible(bool(spec.get("speed")))
        self.direction_row.set_visible(bool(spec.get("direction")))
        self.selected_effect_title.set_text(EFFECT_LABELS[effect])
        self.effect_description.set_text(EFFECT_DESCRIPTIONS[effect])

    def on_apply_effect(self, _button=None):
        effect = self.current_effect
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
            speed = round(self.speed_scale.get_value())
            if speed >= len(AURA_SPEEDS):
                return
            args += ["--speed", AURA_SPEEDS[speed]]
        if spec.get("direction"):
            direction = next((index for index, button in enumerate(self.direction_buttons) if button.get_active()), 0)
            args += ["--direction", AURA_DIRECTIONS[direction]]
        result = command(args)
        if result.returncode == 0:
            self.effect_feedback.set_text(f"{EFFECT_LABELS[effect]} effect applied")
            self.lighting_state.update({
                "effect": effect,
                "primary": self.colour_controls["primary"]["hex"],
                "secondary": self.colour_controls["secondary"]["hex"],
                "speed": round(self.speed_scale.get_value()),
                "direction": next((index for index, button in enumerate(self.direction_buttons) if button.get_active()), 2),
            })
            save_lighting_state(self.lighting_state)
        else:
            self.effect_feedback.set_text("Could not apply lighting effect")
            self.toast("Could not apply effect: " + ((result.stderr or result.stdout).strip() or "asusctl error"))

    def apply_brightness_level(self, value):
        levels = ("off", "low", "med", "high")
        if value is None or value >= len(levels):
            return
        level = levels[value]
        result = command(["asusctl", "leds", "set", level])
        if result.returncode == 0:
            self.brightness_feedback.set_text(f"Keyboard backlight set to {level}.")
            self.lighting_state["brightness"] = value
            save_lighting_state(self.lighting_state)
        else:
            self.brightness_feedback.set_text(f"Could not set keyboard backlight to {level}.")
            self.toast("Could not set backlight: " + ((result.stderr or result.stdout).strip() or "asusctl error"))
        self.refresh()
