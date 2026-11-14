"""Gpu page UI and interactions."""
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


class GpuPage:
    def build_gpu(self):
        outer, c = self.page_shell("GRAPHICS", "GPU Mode", "Switch between integrated graphics and hybrid graphics. The change takes effect after logout or reboot.")
        self.gpu_current_card, self.gpu_current_value = card("CURRENT GPU MODE", "—", "Reported by supergfxctl")
        self.gpu_current_card.add_css_class("hero")
        self.gpu_current_value.add_css_class("hero-value")
        c.append(self.gpu_current_card)
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        group.add_css_class("surface")
        group.append(label("AVAILABLE MODES", "surface-title"))
        self.gpu_dropdown = Gtk.DropDown(model=Gtk.StringList.new(GPU_MODES))
        group.append(self.gpu_dropdown)
        change = Gtk.Button(label="Change GPU mode")
        change.add_css_class("accent-button")
        change.set_halign(Gtk.Align.START)
        change.connect("clicked", self.on_request_gpu)
        group.append(change)
        group.append(label("This laptop exposes Integrated and Hybrid modes. Select only when ready to log out or restart.", "subtle"))
        c.append(group)
        return outer

    def on_request_gpu(self, _button):
        idx = self.gpu_dropdown.get_selected()
        if idx >= len(GPU_MODES):
            return
        mode = GPU_MODES[idx]
        current = self.gpu_current_value.get_text().strip()
        if current == mode:
            self.toast(f"{mode} mode is already active")
            return
        dialog = Adw.AlertDialog(heading="Change GPU mode?", body=f"Switch to {mode}? A logout or reboot is needed before the change takes effect.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("apply", "Change mode")
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.connect("response", self.on_gpu_response, mode)
        dialog.present(self)

    def on_gpu_response(self, _dialog, response, mode):
        if response != "apply":
            return
        result = command(["supergfxctl", "-m", mode])
        if result.returncode == 0:
            self.toast(f"{mode} requested · log out or reboot to complete")
            self.refresh()
        else:
            self.toast("GPU mode change failed: " + ((result.stderr or result.stdout).strip() or "supergfxctl error"))
