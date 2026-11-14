"""Device page UI and interactions."""
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


class DevicePage:
    def build_device(self):
        outer, content = self.page_shell("DEVICE", "System Information", "Live details reported by Linux and the ASUS firmware.")
        panel = self.dashboard_panel("Hardware")
        details = (
            ("Model", pretty_product_name(text("/sys/class/dmi/id/product_name", "ASUS laptop"))),
            ("BIOS", text("/sys/class/dmi/id/bios_version", "Unavailable")),
            ("Operating System", os_pretty_name()),
            ("Kernel", os.uname().release),
            ("CPU", cpu_model()),
            ("GPU", " · ".join(gpu_names())),
            ("Memory", self.memory_summary()),
            ("Storage", self.disk_summary()),
        )
        for title, value in details:
            self.dashboard_stat(panel, title, value, f"device_{title}")
        content.append(panel)
        return outer

    def memory_summary(self):
        total, available = read_memory()
        if total is None or available is None:
            return "Unavailable"
        used = total - available
        return f"{total / 1048576:.1f} GB · {used / 1048576:.1f} GB in use"

    def disk_summary(self):
        disks = read_disks()
        return " | ".join(disks) if disks else "Unavailable"
