import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

# Keep these calculations testable on CI runners without PyGObject installed.
asus_stub = types.ModuleType("hardware.asus")
asus_stub.command = lambda *args, **kwargs: None
asus_stub.int_or_none = lambda value: int(value) if value not in (None, "") else None
asus_stub.text = lambda path, default="—": default
sys.modules.setdefault("hardware.asus", asus_stub)

from hardware import system


class TelemetryTests(unittest.TestCase):
    def test_battery_eta_for_discharge(self):
        self.assertEqual(system.estimate_battery_minutes("Discharging", 50, 100, 25), 120)

    def test_battery_eta_for_full(self):
        self.assertEqual(system.estimate_battery_minutes("Full", 100, 100, 10), 0)

    def test_battery_eta_rejects_missing_rate(self):
        self.assertIsNone(system.estimate_battery_minutes("Charging", 50, 100, None))

    def test_battery_state_aggregates_multiple_devices(self):
        paths = ["/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"]
        values = {
            (paths[0], "capacity"): "50", (paths[0], "status"): "Discharging",
            (paths[0], "energy_now"): "500", (paths[0], "energy_full"): "1000",
            (paths[0], "power_now"): "100",
            (paths[1], "capacity"): "75", (paths[1], "status"): "Discharging",
            (paths[1], "energy_now"): "750", (paths[1], "energy_full"): "1000",
            (paths[1], "power_now"): "100",
        }
        with patch.object(system.glob, "glob", return_value=paths), patch.object(
            system, "text", side_effect=lambda path, default="—": values.get(
                (path.rsplit("/", 1)[0], path.rsplit("/", 1)[1]), default
            )
        ):
            self.assertEqual(system.read_battery_state(), (62, "Discharging", 375))


if __name__ == "__main__":
    unittest.main()
