"""Linux hardware telemetry and system identity discovery."""
import glob
import os

from hardware.asus import command, int_or_none, text

_cpu_times = None
_gpu_names = None


def read_memory():
    total = available = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    available = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return total, available


def read_disks():
    disks = []
    try:
        for device in sorted(os.listdir("/sys/block")):
            if device.startswith(("loop", "ram", "zram", "fd", "sr", "dm-")):
                continue
            model = text(f"/sys/block/{device}/device/model", "").strip()
            sectors = int_or_none(text(f"/sys/block/{device}/size", ""))
            if sectors:
                capacity = f"{sectors * 512 / 1e9:.1f} GB".rstrip("0").rstrip(".")
                disks.append(capacity + (" · " + model if model else f" · {device}"))
    except OSError:
        pass
    return disks


def pretty_product_name(raw):
    name = raw.strip()
    if "_" in name:
        prefix, suffix = name.rsplit("_", 1)
        if prefix.endswith(suffix):
            name = prefix
    return name


def read_thermal(hwmon_name):
    for path in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(os.path.join(path, "name"), encoding="utf-8") as stream:
                if stream.read().strip() != hwmon_name:
                    continue
        except OSError:
            continue
        value = int_or_none(text(os.path.join(path, "temp1_input"), ""))
        if value is not None:
            return value / 1000.0
    return None


def cpu_freq_ghz():
    total = count = 0.0
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("cpu MHz"):
                    total += float(line.split(":", 1)[1])
                    count += 1
    except (OSError, ValueError, IndexError):
        return 0.0
    return total / count / 1000 if count else 0.0


def cpu_usage_percent():
    global _cpu_times
    try:
        with open("/proc/stat", encoding="utf-8") as stream:
            values = [int(value) for value in stream.readline().split()[1:]]
    except (OSError, ValueError, IndexError):
        return None
    total = sum(values)
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    previous = _cpu_times
    _cpu_times = total, idle
    if previous is None or total <= previous[0]:
        return None
    delta_total = total - previous[0]
    delta_idle = idle - previous[1]
    return max(0.0, min(100.0, (delta_total - delta_idle) * 100 / delta_total))


def gpu_usage_percent():
    for path in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
        value = int_or_none(text(path, ""))
        if value is not None and 0 <= value <= 100:
            return value
    return None


def cpu_model():
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (OSError, IndexError):
        pass
    return "Processor"


def disk_usage(path="/"):
    try:
        stats = os.statvfs(path)
        total = stats.f_blocks * stats.f_frsize / 1e9
        free = stats.f_bavail * stats.f_frsize / 1e9
        return total, free, (total - free) / total * 100 if total else 0.0
    except OSError:
        return 0.0, 0.0, 0.0


def gpu_names():
    global _gpu_names
    if _gpu_names is None:
        dgpu = igpu = "Integrated graphics"
        result = command(["lspci"])
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                low = line.lower()
                is_graphics = any(token in low for token in ("vga", "3d controller", "display controller"))
                if not is_graphics or ":" not in line:
                    continue
                description = line.split(":", 2)[-1].strip()
                if "[" in description and "]" in description:
                    description = description[description.index("[") + 1:description.index("]")]
                description = description.split(" (rev ")[0]
                if "nvidia" in low:
                    dgpu = description
                elif "amd" in low or "ati" in low:
                    igpu = description
        _gpu_names = dgpu, igpu
    return _gpu_names


def os_pretty_name():
    try:
        with open("/etc/os-release", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "Unknown Linux"
