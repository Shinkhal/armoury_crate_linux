"""Application startup and process entry point."""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from config import APP_ID
from styles import CSS
from window import ArmouryWindow


class ArmouryApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self.on_activate)

    def on_activate(self, _app):
        window = self.get_active_window()
        if window is None:
            window = ArmouryWindow(self)
        window.present()


def main():
    GLib.set_application_name("Armoury Crate")
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
    )
    return ArmouryApplication().run(sys.argv)
