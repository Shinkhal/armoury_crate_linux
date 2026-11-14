"""Application identity and ASUS feature configuration."""
import glob
import os

APP_ID = "io.github.armourycrate"
ASSET_DIR = os.path.join(os.path.expanduser("~/.local/share/armoury-crate"), "assets")
ASUSD_NAME = "xyz.ljones.Asusd"
ASUSD_PATH = "/xyz/ljones"
PLATFORM_IFACE = "xyz.ljones.Platform"
BATTERY_PATHS = glob.glob("/sys/class/power_supply/BAT*/charge_control_end_threshold")
PROFILES = [
    ("Quiet", "Quiet", "Less fan noise · lower power"),
    ("Balanced", "Balanced", "Everyday performance"),
    ("Performance", "Performance", "Maximum cooling and speed"),
]
PROFILE_IDS = {"Quiet": 2, "Balanced": 0, "Performance": 1}
PROFILE_VALUES = {0: "Balanced", 1: "Performance", 2: "Quiet", 3: "LowPower"}
PROFILE_SYMBOLS = {"Quiet": "☾", "Balanced": "◈", "Performance": "ϟ"}
CHARGE_LIMITS = (60, 80, 100)
BATTERY_MODES = (
    (100, "Full Capacity Mode", "Charges to full capacity for longer use away from the adapter.", "Best for travel", "⚡"),
    (80, "Balanced Mode", "Stops charging above 80% and resumes below 78%.", "Recommended for everyday use", "◐"),
    (60, "Maximum Lifespan Mode", "Stops charging above 60% and resumes below 58%.", "Best when usually plugged in", "▥"),
)
AURA_DEFAULT_COLOUR = "ff2050"
EFFECT_OPTIONS = {
    "static": {"colours": 1}, "breathe": {"colours": 2, "speed": True},
    "rainbow-cycle": {"speed": True}, "rainbow-wave": {"speed": True, "direction": True},
    "rain": {"speed": True}, "stars": {"colours": 2, "speed": True},
    "highlight": {"colours": 1, "speed": True}, "laser": {"colours": 1, "speed": True},
    "ripple": {"colours": 1, "speed": True}, "pulse": {"colours": 1},
    "comet": {"colours": 1}, "flash": {"colours": 1},
}
AURA_SPEEDS = ["low", "med", "high"]
AURA_SPEED_LABELS = ["Low", "Medium", "High"]
AURA_DIRECTIONS = ["up", "down", "left", "right"]
AURA_DIRECTION_LABELS = ["Up", "Down", "Left", "Right"]
AURA_PRESETS = {
    "ROG Red": "ff2050", "Red": "ff0000", "Orange": "ff7a00", "Yellow": "ffd400",
    "Green": "00c853", "Cyan": "00d6e8", "Blue": "1769ff", "Purple": "8b5cf6",
    "Magenta": "f000b8", "Pink": "ff6b92", "White": "f5f5f5",
}
EFFECT_LABELS = {
    "static": "Static", "breathe": "Breathing", "rainbow-cycle": "Rainbow Cycle",
    "rainbow-wave": "Rainbow Wave", "rain": "Rain", "stars": "Stars",
    "highlight": "Highlight", "laser": "Laser", "ripple": "Ripple",
    "pulse": "Pulse", "comet": "Comet", "flash": "Flash",
}
EFFECT_DESCRIPTIONS = {
    "static": "A steady single-colour glow.", "breathe": "Fade smoothly between two colours.",
    "rainbow-cycle": "Cycle through the colour spectrum.",
    "rainbow-wave": "Move a rainbow wave in the chosen direction.",
    "rain": "A flowing colour effect with adjustable speed.",
    "stars": "Two-colour star-like pulses.", "highlight": "A moving highlight in one colour.",
    "laser": "A sweeping single-colour beam.", "ripple": "A single-colour ripple effect.",
    "pulse": "A steady single-colour pulse.", "comet": "A single-colour comet trail.",
    "flash": "A single-colour flash.",
}
GPU_MODES = ["Integrated", "Hybrid"]
PPD_NAME = "org.freedesktop.UPower.PowerProfiles"
PPD_PATH = "/org/freedesktop/UPower/PowerProfiles"
PPD_IFACE = "org.freedesktop.UPower.PowerProfiles"
PPD_TO_ASUS = {"power-saver": "Quiet", "balanced": "Balanced", "performance": "Performance"}
