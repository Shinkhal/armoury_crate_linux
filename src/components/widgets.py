"""Small GTK components shared by application pages."""
import os

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from config import ASSET_DIR


def label(value, css=None):
    widget = Gtk.Label(label=value, xalign=0, wrap=True)
    if css:
        widget.add_css_class(css)
    if css in ("surface-title", "eyebrow", "info-key", "opt-key", "footer",
               "brand-title", "brand-subtitle", "header-title", "hero-tag", "status-dot"):
        widget.set_wrap(False)
    return widget


def asus_image(filename, fallback_icon=None, size=18):
    image = None
    if filename:
        path = os.path.join(ASSET_DIR, filename)
        if os.path.isfile(path):
            try:
                image = Gtk.Image.new_from_file(path)
            except Exception:
                image = None
    if image is None and fallback_icon:
        image = Gtk.Image.new_from_icon_name(fallback_icon)
    if image is None:
        return None
    image.set_pixel_size(size)
    image.add_css_class("info-icon")
    return image


def rgba_hex(rgba):
    return "%02x%02x%02x" % (
        round(rgba.red * 255) % 256,
        round(rgba.green * 255) % 256,
        round(rgba.blue * 255) % 256,
    )


def make_rgba(hex_colour):
    rgba = Gdk.RGBA()
    return rgba if rgba.parse("#" + hex_colour.lstrip("#")) else None


def card(title, value, detail=""):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.add_css_class("surface")
    box.append(label(title.upper(), "surface-title"))
    value_widget = label(value, "surface-value")
    box.append(value_widget)
    if detail:
        box.append(label(detail, "subtle"))
    return box, value_widget


def page_heading(kicker, title, subtitle):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    if kicker:
        box.append(label(kicker.upper(), "eyebrow"))
    box.append(label(title, "page-title"))
    if subtitle:
        box.append(label(subtitle, "subtle"))
    box.set_margin_bottom(16)
    return box
