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

    def test_battery_mixed_units_uses_arithmetic_mean(self):
        """Mixed energy/charge batteries must use the arithmetic mean of individual percentages."""
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
            # BAT0: 50%, BAT1: 80% -> unweighted arithmetic mean is exactly (50 + 80) // 2 = 65%
            self.assertEqual(capacity, 65)
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


class GpuTelemetryTests(unittest.TestCase):
    def setUp(self):
        system._nvidia_gpu_cache = None
        system._nvidia_gpu_cache_time = 0.0

    def test_gpu_telemetry_prefers_nvidia_on_hybrid(self):
        """On hybrid laptops with card0=AMD (iGPU) and card1=NVIDIA (dGPU), pick NVIDIA."""
        devices = ["/sys/class/drm/card0/device", "/sys/class/drm/card1/device"]
        mock_data = {
            f"{devices[0]}/vendor": "0x1002",
            f"{devices[0]}/gt_cur_freq_mhz": "1200",
            f"{devices[0]}/gpu_busy_percent": "15",
            f"{devices[0]}/mem_info_vram_used": "512",
            f"{devices[0]}/mem_info_vram_total": "512",
            f"{devices[1]}/vendor": "0x10de",
            f"{devices[1]}/gt_cur_freq_mhz": "1950",
            f"{devices[1]}/gpu_busy_percent": "78",
            f"{devices[1]}/mem_info_vram_used": "4096",
            f"{devices[1]}/mem_info_vram_total": "8192",
        }
        with patch.object(system.glob, "glob", return_value=devices), \
             patch.object(system, "text", side_effect=lambda path, default="—": mock_data.get(path, default)), \
             patch.object(system, "read_thermal", return_value=62.0):
            telemetry = system.gpu_telemetry()
            self.assertEqual(telemetry["vendor"], "nvidia")
            self.assertEqual(telemetry["frequency"], 1950)
            self.assertEqual(telemetry["usage"], 78)
            self.assertEqual(telemetry["memory_total"], 8192)
            # NVIDIA should not receive AMD voltage
            self.assertIsNone(telemetry["voltage"])

    def test_gpu_telemetry_amd_system(self):
        """On AMD-only system, report AMD vendor, temperature, voltage and power."""
        devices = ["/sys/class/drm/card0/device"]
        mock_data = {
            f"{devices[0]}/vendor": "0x1002",
            f"{devices[0]}/gt_cur_freq_mhz": "1600",
            f"{devices[0]}/gpu_busy_percent": "45",
            f"{devices[0]}/mem_info_vram_used": "1024",
            f"{devices[0]}/mem_info_vram_total": "4096",
        }
        with patch.object(system.glob, "glob", return_value=devices), \
             patch.object(system, "text", side_effect=lambda path, default="—": mock_data.get(path, default)), \
             patch.object(system, "read_thermal", return_value=58.0), \
             patch.object(system, "gpu_power_watts", return_value=35.5), \
             patch.object(system, "gpu_voltage_mv", return_value=875):
            telemetry = system.gpu_telemetry()
            self.assertEqual(telemetry["vendor"], "amd")
            self.assertEqual(telemetry["frequency"], 1600)
            self.assertEqual(telemetry["power"], 35.5)
            self.assertEqual(telemetry["voltage"], 875)

    def test_gpu_telemetry_nvidia_cache_overrides_vendor_and_clears_voltage(self):
        """When NVIDIA cache is active, vendor must be nvidia and voltage must be None."""
        import time
        system._nvidia_gpu_cache = {
            "vendor": "nvidia",
            "usage": 85.0,
            "temperature": 71.0,
            "frequency": 2100.0,
            "memory_used": 6000000000,
            "memory_total": 8000000000,
            "power": 115.0,
        }
        system._nvidia_gpu_cache_time = time.monotonic()
        with patch.object(system.glob, "glob", return_value=[]):
            telemetry = system.gpu_telemetry()
            self.assertEqual(telemetry["vendor"], "nvidia")
            self.assertEqual(telemetry["power"], 115.0)
            self.assertEqual(telemetry["frequency"], 2100.0)
            self.assertIsNone(telemetry["voltage"])


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
