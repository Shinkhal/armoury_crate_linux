"""GPU backend selection and pending-request regression tests (no GPU writes)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "src")
try:
    from pages import gpu
except Exception:
    # The package-build job intentionally runs the hardware tests without
    # installing GTK/PyGObject. GUI-specific tests are skipped there; the
    # smoke-test job exercises the real GTK import path separately.
    gpu = None


@unittest.skipIf(gpu is None, "GTK bindings are unavailable")
class GpuStateTests(unittest.TestCase):
    def page(self, current="Hybrid", pending=None, backend="supergfxctl"):
        page = gpu.GpuPage()
        page.gpu_pending_mode = "Integrated"
        page.gpu_pending_request = {"mode": "Integrated", "boot_id": "old"}
        page.gpu_current_badge = MagicMock()
        page.gpu_mode_feedback = MagicMock()
        page.dashboard_gpu_mode_value = MagicMock()
        page.gpu_cards = {title: MagicMock() for title, *_ in gpu.GPU_MODE_CARDS}
        page.gpu_card_status = {title: MagicMock() for title in page.gpu_cards}
        page._read_gpu_state = MagicMock(return_value=({
            "backend": backend, "modes": ["Integrated", "Hybrid"],
            "current": current, "pending": pending, "action": "Logout required",
        }, None))
        return page

    @patch("pages.gpu.boot_id", return_value="new")
    def test_failed_request_after_reboot_displays_actual_mode(self, _boot):
        page = self.page()
        page.refresh_gpu_state()
        page.dashboard_gpu_mode_value.set_text.assert_called_with("Standard")
        page.gpu_card_status["Eco Mode"].set_text.assert_called_with("CHANGE NOT APPLIED")
        self.assertIn("did not take effect", page.gpu_mode_feedback.set_text.call_args.args[0])
        page.refresh_gpu_state()
        self.assertIn("did not take effect", page.gpu_mode_feedback.set_text.call_args.args[0])

    @patch("pages.gpu.boot_id", return_value="old")
    def test_same_boot_firmware_request_remains_pending(self, _boot):
        page = self.page(backend="armoury")
        page.refresh_gpu_state()
        page.gpu_card_status["Eco Mode"].set_text.assert_called_with("PENDING REBOOT")

    @patch("pages.gpu.clear_pending_gpu_mode")
    def test_successful_switch_clears_saved_request(self, clear):
        page = self.page(current="Integrated")
        page.refresh_gpu_state()
        clear.assert_called_once()
        self.assertIsNone(page.gpu_pending_request)
        page.gpu_card_status["Eco Mode"].set_text.assert_called_with("ACTIVE MODE")

    @patch("pages.gpu.boot_id", return_value="new")
    def test_service_pending_action_takes_precedence(self, _boot):
        page = self.page(pending="Integrated")
        page.refresh_gpu_state()
        page.gpu_card_status["Eco Mode"].set_text.assert_called_with("CHANGE PENDING")
        self.assertIn("Logout required", page.gpu_mode_feedback.set_text.call_args.args[0])

    def test_legacy_request_detected_before_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "pending.json")
            Path(path).write_text(json.dumps({"mode": "Integrated"}))
            os.utime(path, (100, 100))
            with patch.object(gpu, "GPU_PENDING_PATH", path), patch.object(gpu, "text", return_value="btime 200"):
                self.assertTrue(gpu.load_pending_gpu_request()["previous_boot"])

    def test_saved_request_records_boot_and_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "pending.json")
            with patch.object(gpu, "GPU_PENDING_PATH", path), patch.object(gpu, "boot_id", return_value="boot"):
                gpu.save_pending_gpu_mode("Integrated", "supergfxctl")
                self.assertEqual(gpu.load_pending_gpu_request(), {
                    "mode": "Integrated", "backend": "supergfxctl", "boot_id": "boot"})

    @patch("pages.gpu.command")
    @patch("pages.gpu._read_supergfxctl_state")
    def test_firmware_backend_precedes_service_when_available(self, read_service, command):
        read_service.return_value = ({"backend": "supergfxctl", "current": "Integrated"}, None)
        command.return_value = subprocess.CompletedProcess([], 0, "dgpu_disable:\n  current: [(1),0]\n", "")
        state, error = gpu.GpuPage()._read_gpu_state()
        self.assertEqual(state["backend"], "armoury")

    @patch("pages.gpu.command")
    @patch("pages.gpu._read_supergfxctl_state", return_value=(None, "unavailable"))
    def test_firmware_fallback_when_service_unavailable(self, _service, command):
        command.return_value = subprocess.CompletedProcess([], 0, "dgpu_disable:\n  current: [(0),1]\n", "")
        state, error = gpu.GpuPage()._read_gpu_state()
        self.assertEqual(state["backend"], "armoury")
        self.assertEqual(state["current"], "Hybrid")


if __name__ == "__main__":
    unittest.main()
