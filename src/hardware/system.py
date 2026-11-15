"""Linux hardware telemetry and system identity discovery."""
import glob
import os
import time

from hardware.asus import command, int_or_none, text

_cpu_times = None
_gpu_names = None
_nvidia_gpu_cache = None
_nvidia_gpu_cache_time = 0.0
_NVIDIA_GPU_CACHE_TTL = 8.0


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


def estimate_battery_minutes(status, current, full, rate):
    if current is None or rate is None or rate == 0:
        return None
    rate = abs(rate)
    state = status.strip().lower()
    if state == "discharging":
        remaining = current
    elif state == "charging" and full is not None:
        remaining = max(0, full - current)
    elif state == "full":
        return 0
    else:
        return None
    return round(remaining / rate * 60)


def read_battery_state():
    batteries = []
    for battery_path in sorted(glob.glob("/sys/class/power_supply/BAT*")):
        capacity = int_or_none(text(os.path.join(battery_path, "capacity"), ""))
        status = text(os.path.join(battery_path, "status"), "Unknown").strip().title()
        energy_now = int_or_none(text(os.path.join(battery_path, "energy_now"), ""))
        energy_full = int_or_none(text(os.path.join(battery_path, "energy_full"), ""))
        power_now = int_or_none(text(os.path.join(battery_path, "power_now"), ""))
        current_now = int_or_none(text(os.path.join(battery_path, "current_now"), ""))
        charge_now = int_or_none(text(os.path.join(battery_path, "charge_now"), ""))
        charge_full = int_or_none(text(os.path.join(battery_path, "charge_full"), ""))
        remaining = energy_now if energy_now is not None else charge_now
        full = energy_full if energy_now is not None else charge_full
        rate = power_now if energy_now is not None else current_now
        if remaining is None or full is None or full <= 0:
            continue
        batteries.append({
            "capacity": capacity,
            "status": status,
            "remaining": remaining,
            "full": full,
            "rate": rate,
            # Energy and charge values cannot be added together safely.
            "unit": "energy" if energy_now is not None else "charge",
        })
    if not batteries:
        return None, "Unknown", None

    total_full = sum(item["full"] for item in batteries)
    total_remaining = sum(item["remaining"] for item in batteries)
    capacity = round(total_remaining * 100 / total_full) if total_full else None
    statuses = {item["status"].lower() for item in batteries}
    if "discharging" in statuses:
        status = "Discharging"
    elif "charging" in statuses:
        status = "Charging"
    elif statuses and statuses <= {"full"}:
        status = "Full"
    else:
        status = next(iter(statuses)).title() if statuses else "Unknown"

    # Only calculate a combined ETA when every battery uses the same unit.
    eta = None
    if len({item["unit"] for item in batteries}) == 1:
        eta = estimate_battery_minutes(
            status,
            total_remaining,
            total_full,
            sum(item["rate"] or 0 for item in batteries),
        )
    return capacity, status, eta


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


def gpu_telemetry():
    """Read available GPU sensors from NVIDIA tooling or Linux DRM sysfs."""
    global _nvidia_gpu_cache, _nvidia_gpu_cache_time
    result = {
        "usage": gpu_usage_percent(),
        "temperature": read_thermal("amdgpu") or read_thermal("nvidia"),
        "frequency": None,
        "memory_used": None,
        "memory_total": None,
    }
    for device in glob.glob("/sys/class/drm/card*/device"):
        frequency = int_or_none(text(os.path.join(device, "gt_cur_freq_mhz"), ""))
        if frequency is None:
            for line in text(os.path.join(device, "pp_dpm_sclk"), "").splitlines():
                if "*" in line:
                    digits = "".join(character for character in line.split(":", 1)[-1] if character.isdigit())
                    frequency = int_or_none(digits)
                    break
        if frequency is not None and result["frequency"] is None:
            result["frequency"] = frequency
        used = int_or_none(text(os.path.join(device, "mem_info_vram_used"), ""))
        total = int_or_none(text(os.path.join(device, "mem_info_vram_total"), ""))
        if used is not None and total and result["memory_total"] is None:
            result["memory_used"], result["memory_total"] = used, total

    now = time.monotonic()
    if _nvidia_gpu_cache is None or now - _nvidia_gpu_cache_time >= 4:
        nvidia = command([
            "nvidia-smi",
            "--query-gpu=utilization.gpu,temperature.gpu,clocks.gr,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ], timeout=2)
        if nvidia.returncode == 0 and nvidia.stdout.strip():
            fields = [part.strip() for part in nvidia.stdout.splitlines()[0].split(",")]
            try:
                if len(fields) >= 5:
                    _nvidia_gpu_cache = {
                        "usage": float(fields[0]),
                        "temperature": float(fields[1]),
                        "frequency": float(fields[2]),
                        "memory_used": float(fields[3]) * 1_048_576,
                        "memory_total": float(fields[4]) * 1_048_576,
                    }
                    _nvidia_gpu_cache_time = now
            except ValueError:
                pass
    # Never let a successful old sample mask unavailable hardware forever.
    # Keep the short query cache above, but expire it even when nvidia-smi
    # disappears or starts failing. Sysfs readings collected above remain a
    # useful per-sensor fallback.
    if _nvidia_gpu_cache is not None and now - _nvidia_gpu_cache_time <= _NVIDIA_GPU_CACHE_TTL:
        result.update(_nvidia_gpu_cache)
    return result


def read_disk_io_bytes():
    """Return total sectors read and written across physical block devices."""
    devices = set()
    try:
        devices = {
            device for device in os.listdir("/sys/block")
            if not device.startswith(("loop", "ram", "zram", "fd", "sr", "dm-"))
        }
        totals = [0, 0]
        with open("/proc/diskstats", encoding="utf-8") as stream:
            for line in stream:
                fields = line.split()
                if len(fields) > 9 and fields[2] in devices:
                    totals[0] += int(fields[5])
                    totals[1] += int(fields[9])
        return totals[0] * 512, totals[1] * 512
    except (OSError, ValueError, IndexError):
        return None


def read_disk_active_ms():
    """Return cumulative busy time in milliseconds for physical block devices."""
    try:
        devices = {
            device for device in os.listdir("/sys/block")
            if not device.startswith(("loop", "ram", "zram", "fd", "sr", "dm-"))
        }
        active_ms = 0
        count = 0
        with open("/proc/diskstats", encoding="utf-8") as stream:
            for line in stream:
                fields = line.split()
                if len(fields) > 12 and fields[2] in devices:
                    active_ms += int(fields[12])
                    count += 1
        return active_ms, count
    except (OSError, ValueError, IndexError):
        return None


def top_processes(limit=10):
    """List active applications and processes by CPU and resident memory."""
    result = command(["ps", "-eo", "pid=,comm=,pcpu=,rss="])
    if result.returncode != 0:
        return []
    processes = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 3)
        if len(fields) != 4:
            continue
        try:
            pid = int(fields[0])
            cpu = float(fields[2])
            memory_kib = int(fields[3])
        except ValueError:
            continue
        if memory_kib <= 0:
            continue
        processes.append({
            "pid": pid,
            "name": fields[1],
            "cpu": cpu,
            "memory": memory_kib * 1024,
        })

    count = max(1, limit // 2)
    by_cpu = sorted(processes, key=lambda item: item["cpu"], reverse=True)[:count]
    by_memory = sorted(processes, key=lambda item: item["memory"], reverse=True)[:count]
    selected = {process["pid"]: process for process in by_cpu + by_memory}

    display_names = {
        "firefox": "Firefox", "chrome": "Chrome", "chromium": "Chromium",
        "steam": "Steam", "code": "VS Code", "discord": "Discord",
        "obs": "OBS Studio", "vlc": "VLC", "spotify": "Spotify",
        "thunderbird": "Thunderbird", "lutris": "Lutris", "heroic": "Heroic Games Launcher",
        "gnome-shell": "GNOME Shell", "plasmashell": "KDE Plasma",
    }
    grouped = {}
    for process in selected.values():
        name = process["name"]
        display_name = display_names.get(name.lower(), name.replace("_", " ").replace("-", " ").title())
        app = grouped.setdefault(display_name, {"name": display_name, "cpu": 0.0, "memory": 0, "pids": []})
        app["cpu"] += process["cpu"]
        app["memory"] += process["memory"]
        app["pids"].append(process["pid"])
    return sorted(grouped.values(), key=lambda item: (item["cpu"], item["memory"]), reverse=True)[:limit]


def cpu_model():
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (OSError, IndexError):
        pass
    return "Processor"


def memory_details():
    """Read RAM and swap totals, available values are in KiB."""
    values = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as stream:
            for line in stream:
                key, _, value = line.partition(":")
                if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                    values[key] = int(value.strip().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return values


def format_bytes(value):
    if value is None:
        return "Unavailable"
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1000 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{amount:.0f} B"
        amount /= 1000


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
