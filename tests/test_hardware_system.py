import sys
import types
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, "src")

# Keep these calculations testable on CI runners without PyGObject installed.
asus_stub = types.ModuleType("hardware.asus")
asus_stub.command = lambda *args, **kwargs: None
asus_stub.int_or_none = lambda value: int(value) if value not in (None, "") else None
asus_stub.text = lambda path, default="—": default
sys.modules.setdefault("hardware.asus", asus_stub)

from hardware import system


class BatteryEtaTests(unittest.TestCase):
    def test_battery_eta_for_discharge(self):
        self.assertEqual(system.estimate_battery_minutes("Discharging", 50, 100, 25), 120)

    def test_battery_eta_for_full(self):
        self.assertEqual(system.estimate_battery_minutes("Full", 100, 100, 10), 0)

    def test_battery_eta_rejects_missing_rate(self):
        self.assertIsNone(system.estimate_battery_minutes("Charging", 50, 100, None))

    def test_battery_eta_rejects_zero_rate(self):
        self.assertIsNone(system.estimate_battery_minutes("Discharging", 50, 100, 0))

    def test_battery_eta_for_charging(self):
        self.assertEqual(system.estimate_battery_minutes("Charging", 60, 100, 20), 120)


class BatteryAggregationTests(unittest.TestCase):
    def _mock_batteries(self, paths, values):
        return patch.object(system.glob, "glob", return_value=paths), patch.object(
            system, "text", side_effect=lambda path, default="—": values.get(
                (path.rsplit("/", 1)[0], path.rsplit("/", 1)[1]), default
            )
        )

    def test_battery_state_aggregates_same_unit(self):
        """Two energy-unit batteries should sum normally."""
        paths = ["/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"]
        values = {
            (paths[0], "capacity"): "50", (paths[0], "status"): "Discharging",
            (paths[0], "energy_now"): "500", (paths[0], "energy_full"): "1000",
            (paths[0], "power_now"): "100",
            (paths[1], "capacity"): "75", (paths[1], "status"): "Discharging",
            (paths[1], "energy_now"): "750", (paths[1], "energy_full"): "1000",
            (paths[1], "power_now"): "100",
        }
        glob_patch, text_patch = self._mock_batteries(paths, values)
        with glob_patch, text_patch:
            self.assertEqual(system.read_battery_state(), (62, "Discharging", 375))

    def test_battery_mixed_units_uses_weighted_percentage(self):
        """Mixed energy/charge batteries must not sum raw values."""
        paths = ["/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"]
        values = {
            (paths[0], "capacity"): "50", (paths[0], "status"): "Discharging",
            (paths[0], "energy_now"): "25000", (paths[0], "energy_full"): "50000",
            (paths[0], "power_now"): "10000",
            # BAT1 uses charge units — no energy_now/energy_full
            (paths[1], "capacity"): "80", (paths[1], "status"): "Discharging",
            (paths[1], "charge_now"): "4000", (paths[1], "charge_full"): "5000",
            (paths[1], "current_now"): "1000",
        }
        glob_patch, text_patch = self._mock_batteries(paths, values)
        with glob_patch, text_patch:
            capacity, status, eta = system.read_battery_state()
            self.assertIsNotNone(capacity)
            # Naive (25000+4000)/(50000+5000) = 52% which incorrectly mixes µWh and µAh.
            self.assertNotEqual(capacity, 52)
            self.assertEqual(status, "Discharging")
            # Cannot compute ETA across mixed units.
            self.assertIsNone(eta)

    def test_battery_mixed_units_eta_is_none(self):
        """ETA must be None when battery units differ."""
        paths = ["/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"]
        values = {
            (paths[0], "capacity"): "90", (paths[0], "status"): "Discharging",
            (paths[0], "energy_now"): "9000", (paths[0], "energy_full"): "10000",
            (paths[0], "power_now"): "5000",
            (paths[1], "capacity"): "90", (paths[1], "status"): "Discharging",
            (paths[1], "charge_now"): "900", (paths[1], "charge_full"): "1000",
            (paths[1], "current_now"): "500",
        }
        glob_patch, text_patch = self._mock_batteries(paths, values)
        with glob_patch, text_patch:
            _, _, eta = system.read_battery_state()
            self.assertIsNone(eta)

    def test_single_battery_returns_capacity(self):
        paths = ["/sys/class/power_supply/BAT0"]
        values = {
            (paths[0], "capacity"): "72", (paths[0], "status"): "Charging",
            (paths[0], "energy_now"): "7200", (paths[0], "energy_full"): "10000",
            (paths[0], "power_now"): "2800",
        }
        glob_patch, text_patch = self._mock_batteries(paths, values)
        with glob_patch, text_patch:
            capacity, status, eta = system.read_battery_state()
            self.assertEqual(capacity, 72)
            self.assertEqual(status, "Charging")
            self.assertIsNotNone(eta)

    def test_no_batteries_returns_none(self):
        with patch.object(system.glob, "glob", return_value=[]):
            self.assertEqual(system.read_battery_state(), (None, "Unknown", None))


class HwmonSensorTests(unittest.TestCase):
    def test_returns_none_when_label_not_found(self):
        """Requesting a label that doesn't exist must not return an unrelated sensor."""
        hwmon_path = "/sys/class/hwmon/hwmon0"
        with patch.object(system.glob, "glob") as mock_glob, \
             patch.object(system, "text") as mock_text:
            # First glob call: find hwmon devices
            # Second glob call: find label files
            mock_glob.side_effect = lambda pattern: {
                "/sys/class/hwmon/hwmon*": [hwmon_path],
            }.get(pattern, [])
            # name file returns "amdgpu", but no label matches "vddgfx"
            mock_text.side_effect = lambda path, default="—": {
                f"{hwmon_path}/name": "amdgpu",
                f"{hwmon_path}/in0_input": "1200",  # unrelated sensor
            }.get(path, default)
            result = system.hwmon_sensor_value("amdgpu", "in0_input", "vddgfx")
            self.assertIsNone(result)

    def test_reads_correct_labelled_sensor(self):
        """When the label exists, read the corresponding input file."""
        hwmon_path = "/sys/class/hwmon/hwmon0"
        with patch.object(system.glob, "glob") as mock_glob, \
             patch.object(system, "text") as mock_text:
            mock_glob.side_effect = lambda pattern: {
                "/sys/class/hwmon/hwmon*": [hwmon_path],
                f"{hwmon_path}/*_label": [f"{hwmon_path}/in1_label"],
            }.get(pattern, [])
            mock_text.side_effect = lambda path, default="—": {
                f"{hwmon_path}/name": "amdgpu",
                f"{hwmon_path}/in1_label": "vddgfx",
                f"{hwmon_path}/in1_input": "850",
                f"{hwmon_path}/in0_input": "1200",  # should NOT be read
            }.get(path, default)
            result = system.hwmon_sensor_value("amdgpu", "in0_input", "vddgfx")
            self.assertEqual(result, 850)

    def test_reads_unlabelled_sensor(self):
        """When no label is requested, read the filename directly."""
        hwmon_path = "/sys/class/hwmon/hwmon0"
        with patch.object(system.glob, "glob") as mock_glob, \
             patch.object(system, "text") as mock_text:
            mock_glob.side_effect = lambda pattern: {
                "/sys/class/hwmon/hwmon*": [hwmon_path],
            }.get(pattern, [])
            mock_text.side_effect = lambda path, default="—": {
                f"{hwmon_path}/name": "coretemp",
                f"{hwmon_path}/temp1_input": "65000",
            }.get(path, default)
            result = system.hwmon_sensor_value("coretemp", "temp1_input")
            self.assertEqual(result, 65000)


class GpuClassifyTests(unittest.TestCase):
    def test_classify_nvidia(self):
        with patch.object(system, "text", return_value="0x10de"):
            self.assertEqual(system._classify_gpu("/sys/class/drm/card0/device"), "nvidia")

    def test_classify_amd(self):
        with patch.object(system, "text", return_value="0x1002"):
            self.assertEqual(system._classify_gpu("/sys/class/drm/card0/device"), "amd")

    def test_classify_intel(self):
        with patch.object(system, "text", return_value="0x8086"):
            self.assertEqual(system._classify_gpu("/sys/class/drm/card0/device"), "intel")

    def test_classify_unknown(self):
        with patch.object(system, "text", return_value="—"):
            self.assertEqual(system._classify_gpu("/sys/class/drm/card0/device"), "unknown")


class HelperTests(unittest.TestCase):
    def test_format_bytes(self):
        self.assertEqual(system.format_bytes(None), "Unavailable")
        self.assertEqual(system.format_bytes(0), "0 B")
        self.assertEqual(system.format_bytes(1500), "1.5 KB")

    def test_pretty_product_name_dedup(self):
        self.assertEqual(system.pretty_product_name("ROG_ROG"), "ROG")
        self.assertEqual(system.pretty_product_name("Zephyrus G14"), "Zephyrus G14")

    def test_cpu_freq_ghz_empty(self):
        with patch("builtins.open", side_effect=OSError):
            self.assertEqual(system.cpu_freq_ghz(), 0.0)


if __name__ == "__main__":
    unittest.main()
