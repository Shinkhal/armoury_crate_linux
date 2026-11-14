"""Cooling page UI and interactions."""
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


class CoolingPage:
    def make_profile_cards(self, parent, compact=False):
        row = Gtk.Box(spacing=10)
        buttons = {}
        for name, short, desc in PROFILES:
            button = Gtk.Button()
            button.add_css_class("mode-option" if compact else "profile-card")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            badge = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            badge.add_css_class("profile-badge")
            badge.set_size_request(46, 46)
            badge.set_halign(Gtk.Align.START)
            badge.set_valign(Gtk.Align.CENTER)
            symbol = label(PROFILE_SYMBOLS[name], "profile-symbol")
            symbol.set_halign(Gtk.Align.CENTER)
            symbol.set_valign(Gtk.Align.CENTER)
            badge.append(symbol)
            box.append(badge)
            box.append(label(short, "profile-name"))
            if not compact:
                box.append(label(desc, "profile-desc"))
            button.set_child(box)
            button.set_hexpand(True)
            button.connect("clicked", self.on_profile_clicked, name)
            row.append(button)
            buttons[name] = button
        parent.append(row)
        return buttons

    def build_cooling(self):
        outer, c = self.page_shell("THERMAL CONTROL", "Operating Mode", "Select the ASUS firmware profile that controls CPU power and the laptop's automatic fan behavior.")
        c.append(label("SELECT PROFILE", "eyebrow"))
        self.cool_profile_buttons = self.make_profile_cards(c)
        row = Gtk.Box(spacing=12)
        self.cpu_fan_card, self.cpu_fan_value = card("CPU FAN SPEED", "—", "Read-only sensor · firmware controlled")
        self.gpu_fan_card, self.gpu_fan_value = card("GPU FAN SPEED", "—", "Read-only sensor · firmware controlled")
        self.cpu_fan_card.set_hexpand(True)
        self.gpu_fan_card.set_hexpand(True)
        row.append(self.cpu_fan_card)
        row.append(self.gpu_fan_card)
        c.append(row)
        note, self.thermal_note = card("FAN CURVES", "Automatic · Firmware controlled", "This FA506IHRB firmware does not expose custom fan curves to Linux. Quiet, Balanced, and Performance select the supported built-in fan behavior.")
        c.append(note)
        return outer
