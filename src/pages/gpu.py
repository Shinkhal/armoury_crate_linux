"""GPU mode selection through ASUS firmware controls or supergfxctl."""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from components.widgets import asus_image, label
from hardware.asus import command
from hardware.system import pretty_product_name, text


_gpu_switch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu-switch")


GPU_PENDING_PATH = os.path.join(GLib.get_user_config_dir(), "armoury-crate", "gpu-mode-pending.json")
GPU_MODE_CARDS = (
    ("Ultimate", "Ultimate", "Gaming and intensive tasks get the best performance and lowest display latency.", "bolt-symbolic"),
    ("Standard", "Hybrid", "Windows default. Uses integrated graphics for everyday work and the discrete GPU for demanding apps.", None),
    ("Eco Mode", "Integrated", "Turns off the discrete GPU to reduce power use, temperature, and fan noise.", "leaf-symbolic"),
    ("Optimized", None, "Automatically adapts GPU power saving to the power source and workload.", "emblem-synchronizing-symbolic"),
)


def boot_id():
    return text("/proc/sys/kernel/random/boot_id", "")


def load_pending_gpu_request():
    try:
        with open(GPU_PENDING_PATH, encoding="utf-8") as stream:
            request = json.load(stream)
        if not isinstance(request, dict) or not isinstance(request.get("mode"), str):
            return None
        # Older versions saved only the mode. File age lets us recognize a
        # request made before this boot without pretending it is still queued.
        if not request.get("boot_id"):
            for line in text("/proc/stat", "").splitlines():
                if line.startswith("btime "):
                    request["previous_boot"] = os.path.getmtime(GPU_PENDING_PATH) < int(line.split()[1])
                    break
        return request
    except (OSError, ValueError, AttributeError):
        return None


def save_pending_gpu_mode(mode, backend):
    request = {"mode": mode, "backend": backend, "boot_id": boot_id()}
    try:
        os.makedirs(os.path.dirname(GPU_PENDING_PATH), exist_ok=True)
        temporary = GPU_PENDING_PATH + ".tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(request, stream)
        os.replace(temporary, GPU_PENDING_PATH)
    except OSError:
        pass
    return request


def request_crossed_boot(request):
    if not request:
        return False
    current_boot = boot_id()
    return bool(request.get("previous_boot") or (
        request.get("boot_id") and current_boot and request["boot_id"] != current_boot
    ))


def clear_pending_gpu_mode():
    try:
        os.unlink(GPU_PENDING_PATH)
    except OSError:
        pass


def _parse_armoury_attributes(output):
    attributes = {}
    for name, body in re.findall(r"(?m)^([a-z_]+):\s*\n((?:[ \t].*\n?)*)", output):
        current = re.search(r"current:\s*\[\((-?\d+)\)", body)
        if current:
            attributes[name] = int(current.group(1))
        else:
            attributes[name] = None
    return attributes


def _read_supergfxctl_state():
    supported = command(["supergfxctl", "-s"])
    if supported.returncode != 0:
        return None, (supported.stderr or supported.stdout).strip() or "supergfxd is unavailable"
    labels = {
        "integrated": "Integrated", "hybrid": "Hybrid", "asusmuxdgpu": "Ultimate",
    }
    modes = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", supported.stdout):
        label = labels.get(token.lower())
        if label and label not in modes:
            modes.append(label)
    if not modes:
        return None, "supergfxctl did not report any supported GPU modes"
    current_result = command(["supergfxctl", "-g"])
    current = current_result.stdout.strip() if current_result.returncode == 0 else None
    current = labels.get(current.lower(), current) if current else None
    if current not in modes:
        return None, (current_result.stderr or "supergfxctl did not report a known current mode").strip()
    pending_result = command(["supergfxctl", "-P"])
    pending = labels.get(pending_result.stdout.strip().lower()) if pending_result.returncode == 0 else None
    action_result = command(["supergfxctl", "-p"])
    action = action_result.stdout.strip() if action_result.returncode == 0 else ""
    commands = {labels[token.lower()]: token for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", supported.stdout)
                if token.lower() in labels}
    return {"backend": "supergfxctl", "modes": modes, "current": current,
            "attributes": {}, "commands": commands, "pending": pending, "action": action}, None


class GpuPage:
    def build_gpu(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("main-content")
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_start(30)
        content.set_margin_end(30)
        content.set_margin_top(18)
        content.set_margin_bottom(26)

        device_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        device_header.add_css_class("gpu-device-header")
        device_icon = asus_image("ic_laptop.svg", "computer-symbolic", 42)
        if device_icon is not None:
            device_header.append(device_icon)
        device_name = pretty_product_name(text("/sys/class/dmi/id/product_name", "ASUS laptop"))
        device_title = label(device_name, "gpu-device-title")
        device_title.set_valign(Gtk.Align.CENTER)
        device_header.append(device_title)
        device_header.append(Gtk.Box(hexpand=True))
        self.gpu_current_mode = "Unavailable"
        self.gpu_current_badge = label("Checking GPU mode…", "gpu-current-badge")
        self.gpu_current_badge.set_valign(Gtk.Align.CENTER)
        device_header.append(self.gpu_current_badge)
        content.append(device_header)

        section_title = label("GPU Mode", "gpu-section-title")
        section_title.set_margin_top(30)
        section_title.set_margin_bottom(36)
        content.append(section_title)

        self.gpu_mode_grid = Gtk.Grid()
        self.gpu_mode_grid.add_css_class("gpu-mode-grid")
        self.gpu_mode_grid.set_column_homogeneous(True)
        self.gpu_mode_grid.set_column_spacing(12)
        self.gpu_cards = {}
        self.gpu_card_status = {}
        for index, (title, mode, description, badge_icon) in enumerate(GPU_MODE_CARDS):
            button, status = self._build_gpu_mode_card(title, description, badge_icon)
            button.connect("clicked", self.on_request_gpu, title)
            self.gpu_mode_grid.attach(button, index, 0, 1, 1)
            self.gpu_cards[title] = button
            self.gpu_card_status[title] = status
        content.append(self.gpu_mode_grid)

        self.gpu_mode_feedback = label("Checking available GPU controls…", "gpu-mode-feedback")
        self.gpu_mode_feedback.set_wrap(True)
        self.gpu_mode_feedback.set_margin_top(22)
        content.append(self.gpu_mode_feedback)
        scroll.set_child(content)
        outer.append(scroll)

        self.gpu_pending_request = load_pending_gpu_request()
        self.gpu_pending_mode = (self.gpu_pending_request or {}).get("mode")
        self.gpu_backend = None
        self.gpu_supported_modes = []
        self.gpu_mode_commands = {}
        self.gpu_state_refresh_in_progress = False
        self.refresh_gpu_state()
        return outer

    def _build_gpu_mode_card(self, title, description, badge_icon):
        button = Gtk.Button()
        button.add_css_class("gpu-mode-card")
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.set_valign(Gtk.Align.CENTER)
        body.set_halign(Gtk.Align.FILL)

        artwork = Gtk.Overlay()
        artwork.set_size_request(82, 78)
        artwork.set_halign(Gtk.Align.CENTER)
        gpu_asset = "ic_igpu.svg" if title == "Eco Mode" else "ic_gpu.svg"
        emblem = asus_image(gpu_asset, "video-display-symbolic", 64)
        if emblem is not None:
            artwork.set_child(emblem)
        if badge_icon:
            badge = Gtk.Image.new_from_icon_name(badge_icon)
            badge.set_pixel_size(24)
            badge.add_css_class("gpu-mode-badge-icon")
            badge.set_halign(Gtk.Align.END)
            badge.set_valign(Gtk.Align.END)
            artwork.add_overlay(badge)
        body.append(artwork)

        title_label = label(title, "gpu-mode-title")
        title_label.set_xalign(.5)
        title_label.set_justify(Gtk.Justification.CENTER)
        body.append(title_label)
        description_label = label(description, "gpu-mode-description")
        description_label.set_xalign(.5)
        description_label.set_justify(Gtk.Justification.CENTER)
        description_label.set_valign(Gtk.Align.START)
        body.append(description_label)
        status = label("Checking support…", "gpu-mode-status")
        status.set_xalign(.5)
        body.append(status)
        button.set_child(body)
        return button, status

    def _read_gpu_state(self):
        # Prefer the ASUS firmware attribute when present. It is the persistent
        # control on this laptop; supergfxd otherwise restores Hybrid at boot.
        result = command(["asusctl", "armoury", "list"])
        attributes = {}
        if result.returncode == 0:
            attributes = _parse_armoury_attributes(result.stdout)
            if "dgpu_disable" in attributes and attributes["dgpu_disable"] in (0, 1):
                mux_available = "gpu_mux_mode" in attributes and attributes["gpu_mux_mode"] in (0, 1)
                modes = ["Integrated", "Hybrid"]
                if mux_available:
                    modes.append("Ultimate")
                dgpu_disabled = attributes["dgpu_disable"] == 1
                mux_mode = attributes.get("gpu_mux_mode")
                if dgpu_disabled:
                    current = "Integrated"
                elif mux_available and mux_mode == 0:
                    current = "Ultimate"
                else:
                    current = "Hybrid"
                return {
                    "backend": "armoury", "modes": modes, "current": current,
                    "attributes": attributes,
                }, None

        state, error = _read_supergfxctl_state()
        if state:
            return state, None
        armoury_error = (result.stderr or result.stdout).strip()
        if "dgpu_disable" not in attributes:
            detail = armoury_error or "ASUS dGPU firmware control is not available"
            return None, f"{detail}. {error}"
        return None, error

    def refresh_gpu_state(self):
        """Probe GPU services off the GTK thread, then apply state on GTK."""
        # Keep the helper directly usable by headless tests and small tools
        # that instantiate the page without building its GTK widgets.
        if not hasattr(self, "gpu_state_refresh_in_progress"):
            self._apply_gpu_state(*self._read_gpu_state())
            return
        if self.gpu_state_refresh_in_progress:
            return
        self.gpu_state_refresh_in_progress = True
        future = _gpu_switch_executor.submit(self._read_gpu_state)
        future.add_done_callback(
            lambda completed: GLib.idle_add(self._finish_gpu_state_refresh, completed)
        )

    def _finish_gpu_state_refresh(self, future):
        try:
            state, error = future.result()
        except Exception as error:
            state, error = None, str(error)
        self.gpu_state_refresh_in_progress = False
        self._apply_gpu_state(state, error)
        return GLib.SOURCE_REMOVE

    def _apply_gpu_state(self, state, error):
        if state is None:
            self.gpu_backend = None
            self.gpu_supported_modes = []
            self.gpu_current_mode = "Unavailable"
            self.gpu_current_badge.set_text("GPU MODE UNAVAILABLE")
            for title, button in self.gpu_cards.items():
                button.set_sensitive(False)
                button.remove_css_class("active")
                button.remove_css_class("pending")
                self.gpu_card_status[title].set_text("Unavailable")
            self.gpu_mode_feedback.set_text(error or "No GPU switching control is available.")
            if hasattr(self, "dashboard_gpu_mode_value"):
                self.dashboard_gpu_mode_value.set_text("Unavailable")
            return

        self.gpu_backend = state["backend"]
        self.gpu_supported_modes = state["modes"]
        self.gpu_mode_commands = state.get("commands", {})
        self.gpu_current_mode = state["current"] or "Unavailable"

        if self.gpu_pending_mode == state["current"] and not state.get("pending"):
            self.gpu_pending_mode = None
            self.gpu_pending_request = None
            clear_pending_gpu_mode()
        failed_mode = None
        if (self.gpu_pending_mode and state["current"] and
                request_crossed_boot(self.gpu_pending_request) and not state.get("pending")):
            failed_mode = self.gpu_pending_mode
        pending_mode = state.get("pending") or (None if failed_mode else self.gpu_pending_mode)
        current_card = self._card_title_for_mode(state["current"])
        pending_card = self._card_title_for_mode(pending_mode) if pending_mode else None
        if pending_mode in state["modes"]:
            if state["backend"] == "armoury":
                feedback = f"{pending_card} is pending. Reboot to apply the firmware change."
                shown_dashboard_mode = f"{pending_card} · pending reboot"
            else:
                action = state.get("action") or "Check the GPU service for the required action."
                feedback = f"{pending_card} is pending. {action}"
                shown_dashboard_mode = f"{pending_card} · pending"
        elif failed_mode:
            feedback = (f"The computer restarted, but {self._card_title_for_mode(failed_mode)} did not take effect. "
                        f"Current mode: {current_card}. Select the desired mode to try again.")
            shown_dashboard_mode = current_card or "Unavailable"
        else:
            feedback = "Changes are applied by ASUS firmware during shutdown and take effect after reboot." \
                if state["backend"] == "armoury" else "Mode availability and changes are managed by supergfxd."
            shown_dashboard_mode = current_card or "Unavailable"
        self.gpu_current_badge.set_text(f"CURRENT · {current_card or 'Unavailable'}")
        mode_by_card = {title: mode for title, mode, _description, _icon in GPU_MODE_CARDS}
        for title, button in self.gpu_cards.items():
            mode = mode_by_card[title]
            supported = mode is not None and mode in state["modes"]
            active = supported and mode == state["current"]
            pending = supported and title == pending_card
            button.set_sensitive(supported)
            for css_class in ("active", "pending"):
                button.remove_css_class(css_class)
            if pending:
                button.add_css_class("pending")
                self.gpu_card_status[title].set_text("PENDING REBOOT" if state["backend"] == "armoury" else "CHANGE PENDING")
            elif active:
                button.add_css_class("active")
                self.gpu_card_status[title].set_text("ACTIVE MODE")
            elif mode and mode == failed_mode:
                self.gpu_card_status[title].set_text("CHANGE NOT APPLIED")
            elif not supported:
                reason = "Requires a GPU MUX" if title == "Ultimate" else (
                    "Automatic switching unavailable" if title == "Optimized" else "Unavailable"
                )
                self.gpu_card_status[title].set_text(reason.upper())
            else:
                self.gpu_card_status[title].set_text("SELECT MODE")
        self.gpu_mode_feedback.set_text(feedback)
        if hasattr(self, "dashboard_gpu_mode_value"):
            self.dashboard_gpu_mode_value.set_text(shown_dashboard_mode)

    def on_request_gpu(self, _button, card_title):
        # Ignore repeated clicks while the same confirmation is already open.
        # Otherwise Adw.AlertDialog creates a separate modal for every click.
        if getattr(self, "gpu_confirmation_dialog", None) is not None:
            return
        mode = next((mode for title, mode, _description, _icon in GPU_MODE_CARDS if title == card_title), None)
        if mode is None or mode not in self.gpu_supported_modes:
            return
        current = self.gpu_current_mode
        if mode == current and self.gpu_pending_mode is None:
            self.toast(f"{card_title} is already active")
            return
        reboot_note = " The change takes effect after reboot." if self.gpu_backend == "armoury" else ""
        dialog = Adw.AlertDialog(
            heading="Change GPU mode?",
            body=f"Switch from {self._card_title_for_mode(current)} to {card_title}?{reboot_note}",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("apply", "Change mode")
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.connect("response", self.on_gpu_response, mode, card_title)
        self.gpu_confirmation_dialog = dialog
        dialog.present(self)

    @staticmethod
    def _card_title_for_mode(mode):
        return next((title for title, value, _description, _icon in GPU_MODE_CARDS if value == mode), mode)

    def on_gpu_response(self, dialog, response, mode, card_title):
        if self.gpu_confirmation_dialog is dialog:
            self.gpu_confirmation_dialog = None
        if response != "apply":
            return
        self.gpu_mode_feedback.set_text(f"Applying {card_title}… The app will remain responsive.")
        for button in self.gpu_cards.values():
            button.set_sensitive(False)
        backend = self.gpu_backend
        command_name = self.gpu_mode_commands.get(mode, mode)
        future = _gpu_switch_executor.submit(
            self._set_armoury_gpu_mode if backend == "armoury" else command,
            mode if backend == "armoury" else ["supergfxctl", "-m", command_name],
        )
        future.add_done_callback(
            lambda completed: GLib.idle_add(self._finish_gpu_switch, completed, mode, card_title)
        )

    def _finish_gpu_switch(self, future, mode, card_title):
        try:
            result = future.result()
        except Exception as error:
            result = subprocess.CompletedProcess([], 1, "", str(error))
        if result.returncode == 0:
            self.gpu_pending_mode = mode
            self.gpu_pending_request = save_pending_gpu_mode(mode, self.gpu_backend)
            pending_text = (
                f"{card_title} is pending. Reboot to apply the firmware change."
                if self.gpu_backend == "armoury"
                else f"{card_title} is pending. Follow the logout or reboot action required by supergfxd."
            )
            self.gpu_mode_feedback.set_text(pending_text)
            if hasattr(self, "dashboard_gpu_mode_value"):
                self.dashboard_gpu_mode_value.set_text(
                    f"{card_title} · pending reboot" if self.gpu_backend == "armoury" else f"{card_title} · pending"
                )
            self.toast(f"{card_title} change requested")
            self._show_gpu_restart_prompt(card_title)
            self.refresh_gpu_state()
        else:
            detail = (result.stderr or result.stdout).strip() or "GPU mode command failed"
            self.gpu_mode_feedback.set_text(detail)
            self.toast("GPU mode change failed: " + detail)
            self.refresh_gpu_state()
        return GLib.SOURCE_REMOVE

    def _show_gpu_restart_prompt(self, card_title):
        """Offer the user an immediate restart after a mode change."""
        if getattr(self, "gpu_action_dialog", None) is not None:
            return
        if self.gpu_backend == "armoury":
            body = (
                f"{card_title} is ready to apply. Restart now to activate the new GPU mode, "
                "or continue working and restart later."
            )
        else:
            body = (
                f"{card_title} is ready to apply. Restart now to finish the GPU mode change, "
                "or restart later."
            )
        dialog = Adw.AlertDialog(heading="Restart to apply GPU mode?", body=body)
        dialog.add_response("later", "Later")
        dialog.add_response("restart", "Restart now")
        dialog.set_response_appearance("restart", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("restart")
        dialog.connect("response", self.on_gpu_action_response)
        self.gpu_action_dialog = dialog
        dialog.present(self)

    def on_gpu_action_response(self, dialog, response):
        if self.gpu_action_dialog is dialog:
            self.gpu_action_dialog = None
        if response != "restart":
            return
        self.gpu_mode_feedback.set_text("Restarting to apply the GPU mode…")
        # Keep the GTK loop free while logind authorizes and schedules reboot.
        _gpu_switch_executor.submit(command, ["systemctl", "reboot"])

    def _set_armoury_gpu_mode(self, mode):
        state, error = self._read_gpu_state()
        if state is None or state["backend"] != "armoury":
            return subprocess.CompletedProcess([], 1, "", error or "ASUS firmware GPU controls are unavailable")
        attributes = state["attributes"]
        if mode == "Integrated":
            requested = [("dgpu_disable", 1)]
            if "gpu_mux_mode" in attributes:
                requested.append(("gpu_mux_mode", 1))
        elif mode == "Hybrid":
            requested = [("dgpu_disable", 0)]
            if "gpu_mux_mode" in attributes:
                requested.append(("gpu_mux_mode", 1))
        elif mode == "Ultimate" and "gpu_mux_mode" in attributes:
            requested = [("dgpu_disable", 0), ("gpu_mux_mode", 0)]
        else:
            return subprocess.CompletedProcess([], 2, "", f"Unsupported GPU mode: {mode}")

        for property_name, value in requested:
            result = command(["asusctl", "armoury", "set", property_name, str(value)])
            if result.returncode != 0:
                return result
        return subprocess.CompletedProcess([], 0, f"{mode} queued", "")
