"""Linux hardware telemetry and system identity discovery."""
import glob
import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

from hardware.asus import command, int_or_none, text

_cpu_times = None
_gpu_names = None
_nvidia_gpu_cache = None
_nvidia_gpu_cache_time = 0.0
_nvidia_gpu_future = None
_nvidia_gpu_last_started = 0.0
_nvidia_gpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nvidia-telemetry")
_NVIDIA_GPU_CACHE_TTL = 8.0
_smart_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="smart-storage")
_smart_future = None
_smart_future_names = set()
_smart_cache = {}
_smart_queried = set()
_smart_disk_cache = {}
_smart_cache_loaded = False
_smart_identity_by_name = {}


def _query_nvidia_gpu():
    return command([
        "nvidia-smi",
        "--query-gpu=utilization.gpu,temperature.gpu,clocks.gr,memory.used,memory.total,power.draw",
        "--format=csv,noheader,nounits",
    ], timeout=2)


def shutdown_telemetry():
    """Stop background telemetry work during application shutdown."""
    global _nvidia_gpu_future, _smart_future
    if _nvidia_gpu_future is not None and not _nvidia_gpu_future.done():
        _nvidia_gpu_future.cancel()
    _nvidia_gpu_future = None
    _nvidia_gpu_executor.shutdown(wait=False, cancel_futures=True)
    if _smart_future is not None and not _smart_future.done():
        _smart_future.cancel()
    _smart_future = None
    _smart_executor.shutdown(wait=False, cancel_futures=True)


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

    units = {item["unit"] for item in batteries}
    if len(units) == 1:
        # All batteries use the same unit — safe to add raw values.
        total_full = sum(item["full"] for item in batteries)
        total_remaining = sum(item["remaining"] for item in batteries)
        capacity = round(total_remaining * 100 / total_full) if total_full else None
    else:
        # Mixed units (energy vs charge) cannot be physically aggregated.
        # Fall back to the arithmetic mean of the individual battery percentages.
        individual_capacities = [
            item["capacity"] if item["capacity"] is not None
            else round(item["remaining"] * 100 / item["full"])
            for item in batteries if item["full"] > 0
        ]
        capacity = round(sum(individual_capacities) / len(individual_capacities)) if individual_capacities else None
        total_remaining = total_full = None

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
    if len(units) == 1 and total_remaining is not None:
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


def _query_smart_devices(devices, elevated=False):
    """Read SMART summary fields off the GTK thread."""
    results = {}
    for device in devices:
        device_path = f"/dev/{device['name']}"
        smartctl = shutil.which("smartctl") or "smartctl"
        args = [smartctl, "-a", "-j", device_path]
        if elevated and shutil.which("pkexec"):
            args.insert(0, shutil.which("pkexec"))
        result = command(args, timeout=60 if elevated else 4)
        try:
            payload = json.loads(result.stdout)
        except (TypeError, ValueError):
            results[device["name"]] = {
                "health": "Unavailable",
                "error": result.stderr.strip() or "SMART data could not be read.",
            }
            continue
        nvme = payload.get("nvme_smart_health_information_log", {})
        ata = payload.get("ata_smart_attributes", {}).get("table", [])
        attributes = {item.get("name", "").lower(): item.get("raw", {}).get("value") for item in ata}
        messages = payload.get("smartctl", {}).get("messages", [])
        error = " ".join(message.get("string", "") for message in messages).strip()
        if any(token in f"{result.stderr} {error}".lower() for token in ("permission", "denied", "not authorized")):
            error = "Permission denied. Use Refresh SMART to authorize a read."
        results[device["name"]] = {
            "health": "PASSED" if payload.get("smart_status", {}).get("passed") is True else (
                "FAILED" if payload.get("smart_status", {}).get("passed") is False else "Unavailable"
            ),
            "error": error,
            "temperature": nvme.get("temperature") or payload.get("temperature", {}).get("current"),
            "percentage_used": nvme.get("percentage_used"),
            "available_spare": nvme.get("available_spare"),
            "power_on_hours": nvme.get("power_on_time", {}).get("hours") or attributes.get("power_on_hours"),
            "data_read_bytes": (
                nvme["data_units_read"] * 512_000
                if isinstance(nvme.get("data_units_read"), (int, float)) else None
            ),
            "data_written_bytes": (
                nvme["data_units_written"] * 512_000
                if isinstance(nvme.get("data_units_written"), (int, float)) else None
            ),
            "media_errors": nvme.get("media_errors"),
        }
    return results


def _smart_cache_path():
    cache_root = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(cache_root, "armoury-crate", "smart-storage.json")


def _load_smart_disk_cache():
    global _smart_cache_loaded, _smart_disk_cache
    if _smart_cache_loaded:
        return
    _smart_cache_loaded = True
    try:
        with open(_smart_cache_path(), encoding="utf-8") as stream:
            payload = json.load(stream)
        if payload.get("version") == 1 and isinstance(payload.get("drives"), dict):
            _smart_disk_cache = {
                name: entry for name, entry in payload["drives"].items()
                if isinstance(entry, dict)
                and isinstance(entry.get("identity"), str)
                and isinstance(entry.get("smart"), dict)
            }
    except (OSError, ValueError, AttributeError):
        _smart_disk_cache = {}


def _save_smart_disk_cache():
    cache_path = _smart_cache_path()
    temporary_path = cache_path + ".tmp"
    try:
        os.makedirs(os.path.dirname(cache_path), mode=0o700, exist_ok=True)
        with open(temporary_path, "w", encoding="utf-8") as stream:
            json.dump({"version": 1, "drives": _smart_disk_cache}, stream, separators=(",", ":"))
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, cache_path)
    except OSError:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass


def _smart_drive_identity(device):
    return "|".join((device["name"], device["vendor"], device["model"], str(device["capacity"])))


def storage_devices(refresh_smart=False):
    """Return physical drives and persistent SMART data, refreshing only on request."""
    global _smart_future, _smart_future_names, _smart_cache, _smart_queried
    _load_smart_disk_cache()
    devices = []
    try:
        names = sorted(os.listdir("/sys/block"))
    except OSError:
        names = []
    for name in names:
        if name.startswith(("loop", "ram", "zram", "fd", "sr", "dm-")):
            continue
        size = int_or_none(text(f"/sys/block/{name}/size", ""))
        if not size:
            continue
        model = text(f"/sys/block/{name}/device/model", "").strip()
        vendor = text(f"/sys/block/{name}/device/vendor", "").strip()
        rotational = text(f"/sys/block/{name}/queue/rotational", "1") == "1"
        devices.append({
            "name": name,
            "model": model or name,
            "vendor": vendor,
            "capacity": size * 512,
            "kind": "NVMe SSD" if name.startswith("nvme") else ("SSD" if not rotational else "HDD"),
            "smart": _smart_cache.get(name, {}),
        })
    for device in devices:
        name = device["name"]
        identity = _smart_drive_identity(device)
        _smart_identity_by_name[name] = identity
        cached = _smart_disk_cache.get(name, {})
        if cached.get("identity") == identity and isinstance(cached.get("smart"), dict):
            _smart_cache[name] = cached["smart"]
            _smart_queried.add(name)
        elif cached:
            _smart_disk_cache.pop(name, None)
            _smart_cache.pop(name, None)
    if _smart_future is not None and _smart_future.done():
        try:
            refreshed = _smart_future.result()
            _smart_cache.update(refreshed)
            for name, smart in refreshed.items():
                identity = _smart_identity_by_name.get(name)
                if identity:
                    _smart_disk_cache[name] = {"identity": identity, "smart": smart}
            _save_smart_disk_cache()
        except Exception:
            pass
        _smart_queried.update(_smart_future_names)
        _smart_future = None
        _smart_future_names = set()
    names = {device["name"] for device in devices}
    if refresh_smart:
        _smart_queried.difference_update(names)
    unqueried = [device for device in devices if device["name"] not in _smart_queried | _smart_future_names]
    if unqueried and _smart_future is None:
        _smart_future_names = {device["name"] for device in unqueried}
        _smart_future = _smart_executor.submit(_query_smart_devices, unqueried, refresh_smart)
    for device in devices:
        device["smart"] = _smart_cache.get(device["name"], {})
    return devices


def storage_smart_refreshing():
    return _smart_future is not None and not _smart_future.done()


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
    values = []
    for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
        value = int_or_none(text(path, ""))
        if value is not None and value > 0:
            values.append(value)
    if values:
        return sum(values) / len(values) / 1_000_000
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


def cpu_max_freq_ghz():
    """Return the advertised CPU maximum frequency from cpufreq sysfs."""
    values = []
    for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq"):
        value = int_or_none(text(path, ""))
        if value is not None and value > 0:
            values.append(value)
    return max(values) / 1_000_000 if values else None


def cpu_topology():
    """Return logical CPU count, distinct physical cores, and boost state."""
    cpu_paths = glob.glob("/sys/devices/system/cpu/cpu[0-9]*")
    logical = len(cpu_paths) or (os.cpu_count() or 0)
    cores = set()
    for path in cpu_paths:
        package = int_or_none(text(os.path.join(path, "topology/physical_package_id"), ""))
        core = int_or_none(text(os.path.join(path, "topology/core_id"), ""))
        if core is not None:
            cores.add((package or 0, core))
    boost = text("/sys/devices/system/cpu/cpufreq/boost", "")
    if not boost:
        boost = text("/sys/devices/system/cpu/cpufreq/amd_pstate/cpb_boost", "")
    return {
        "logical": logical,
        "cores": len(cores) or logical,
        "boost": "Enabled" if boost == "1" else ("Disabled" if boost == "0" else "Unavailable"),
    }


def hwmon_sensor_value(hwmon_name, filename, label_name=None):
    """Read a labelled value from an hwmon device, preserving its raw unit."""
    for path in glob.glob("/sys/class/hwmon/hwmon*"):
        if text(os.path.join(path, "name"), "").strip() != hwmon_name:
            continue
        if label_name is not None:
            matched = False
            for label_path in glob.glob(os.path.join(path, "*_label")):
                if text(label_path, "").strip().lower() == label_name.lower():
                    filename = os.path.basename(label_path).replace("_label", "_input")
                    matched = True
                    break
            if not matched:
                # Label was requested but not found — do NOT fall back to
                # an unrelated sensor.  Skip this hwmon device.
                continue
        value = int_or_none(text(os.path.join(path, filename), ""))
        if value is not None:
            return value
    return None


def gpu_memory_freq_mhz():
    for path in glob.glob("/sys/class/drm/card*/device/pp_dpm_mclk"):
        for line in text(path, "").splitlines():
            if "*" in line:
                digits = "".join(character for character in line.split(":", 1)[-1] if character.isdigit())
                value = int_or_none(digits)
                if value is not None:
                    return value
    return None


def gpu_voltage_mv():
    value = hwmon_sensor_value("amdgpu", "in0_input", "vddgfx")
    return value if value is not None else None


def cpu_voltage_mv():
    for hwmon_name in ("coretemp", "k10temp", "zenpower"):
        value = hwmon_sensor_value(hwmon_name, "in0_input", "vcore")
        if value is not None:
            return value
    return None


def gpu_power_watts():
    value = hwmon_sensor_value("amdgpu", "power1_input", "PPT")
    return value / 1_000_000 if value is not None else None


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


def integrated_gpu_telemetry():
    """Read kernel DRM telemetry for the non-NVIDIA GPU, commonly an AMD APU."""
    for device in sorted(glob.glob("/sys/class/drm/card[0-9]*/device")):
        vendor = _classify_gpu(device)
        if vendor in ("unknown", "nvidia"):
            continue
        usage = int_or_none(text(os.path.join(device, "gpu_busy_percent"), ""))
        used = int_or_none(text(os.path.join(device, "mem_info_vram_used"), ""))
        total = int_or_none(text(os.path.join(device, "mem_info_vram_total"), ""))
        frequency = int_or_none(text(os.path.join(device, "gt_cur_freq_mhz"), ""))
        if frequency is None:
            for line in text(os.path.join(device, "pp_dpm_sclk"), "").splitlines():
                if "*" in line:
                    frequency = int_or_none("".join(ch for ch in line.split(":", 1)[-1] if ch.isdigit()))
                    break
        return {
            "vendor": vendor,
            "usage": usage if usage is not None and 0 <= usage <= 100 else None,
            "memory_used": used,
            "memory_total": total,
            "frequency": frequency,
        }
    return {}


def _classify_gpu(device_path):
    """Return 'nvidia', 'amd', 'intel', or 'unknown' for a DRM device."""
    raw = text(os.path.join(device_path, "vendor"), "").strip()
    try:
        vendor = int(raw, 16) if raw.startswith("0x") else int(raw)
    except (ValueError, TypeError):
        return "unknown"
    if vendor == 0x10de:
        return "nvidia"
    if vendor == 0x1002:
        return "amd"
    if vendor == 0x8086:
        return "intel"
    return "unknown"


def gpu_telemetry():
    """Read available GPU sensors, preferring discrete over integrated."""
    global _nvidia_gpu_cache, _nvidia_gpu_cache_time
    global _nvidia_gpu_future, _nvidia_gpu_last_started
    result = {
        "usage": None,
        "temperature": None,
        "frequency": None,
        "memory_used": None,
        "memory_total": None,
        "power": None,
        "voltage": None,
        "vendor": None,
    }

    # Collect per-device readings, preferring discrete GPU:
    # 0: NVIDIA (discrete)
    # 1: AMD (discrete or APU if no NVIDIA)
    # 2: Intel (integrated)
    # 3: Unknown
    candidates = []
    for device in sorted(glob.glob("/sys/class/drm/card*/device")):
        vendor = _classify_gpu(device)
        priority = 0 if vendor == "nvidia" else (1 if vendor == "amd" else (2 if vendor == "intel" else 3))
        frequency = int_or_none(text(os.path.join(device, "gt_cur_freq_mhz"), ""))
        if frequency is None:
            for line in text(os.path.join(device, "pp_dpm_sclk"), "").splitlines():
                if "*" in line:
                    digits = "".join(character for character in line.split(":", 1)[-1] if character.isdigit())
                    frequency = int_or_none(digits)
                    break
        usage = int_or_none(text(os.path.join(device, "gpu_busy_percent"), ""))
        used = int_or_none(text(os.path.join(device, "mem_info_vram_used"), ""))
        total = int_or_none(text(os.path.join(device, "mem_info_vram_total"), ""))
        candidates.append((priority, vendor, {
            "frequency": frequency,
            "usage": usage if usage is not None and 0 <= usage <= 100 else None,
            "memory_used": used,
            "memory_total": total if total and used is not None else None,
        }))

    if candidates:
        # Sort by priority first (NVIDIA > AMD > Intel), then by largest VRAM for multi-GPU
        candidates.sort(key=lambda c: (c[0], -(c[2]["memory_total"] or 0)))
        best_vendor = candidates[0][1]
        best = candidates[0][2]
        result["vendor"] = best_vendor
        if best["frequency"] is not None:
            result["frequency"] = best["frequency"]
        if best["usage"] is not None:
            result["usage"] = best["usage"]
        if best["memory_total"] is not None:
            result["memory_used"] = best["memory_used"]
            result["memory_total"] = best["memory_total"]
        if best_vendor == "amd":
            result["temperature"] = read_thermal("amdgpu")
            result["power"] = gpu_power_watts()
            result["voltage"] = gpu_voltage_mv()
        elif best_vendor == "nvidia":
            result["temperature"] = read_thermal("nvidia")

    now = time.monotonic()
    if _nvidia_gpu_future is not None and _nvidia_gpu_future.done():
        try:
            nvidia = _nvidia_gpu_future.result()
        except Exception:
            nvidia = None
        _nvidia_gpu_future = None
        if nvidia is not None and nvidia.returncode == 0 and nvidia.stdout.strip():
            fields = [part.strip() for part in nvidia.stdout.splitlines()[0].split(",")]
            try:
                if len(fields) >= 5:
                    power_draw = None
                    if len(fields) >= 6:
                        try:
                            power_draw = float(fields[5])
                        except ValueError:
                            power_draw = None
                    _nvidia_gpu_cache = {
                        "vendor": "nvidia",
                        "usage": float(fields[0]),
                        "temperature": float(fields[1]),
                        "frequency": float(fields[2]),
                        "memory_used": float(fields[3]) * 1_048_576,
                        "memory_total": float(fields[4]) * 1_048_576,
                        "power": power_draw,
                    }
                    _nvidia_gpu_cache_time = now
            except ValueError:
                pass
    if _nvidia_gpu_future is None and now - _nvidia_gpu_last_started >= 4:
        _nvidia_gpu_last_started = now
        _nvidia_gpu_future = _nvidia_gpu_executor.submit(_query_nvidia_gpu)
    # Never let a successful old sample mask unavailable hardware forever.
    # Keep the short query cache above, but expire it even when nvidia-smi
    # disappears or starts failing. Sysfs readings collected above remain a
    # useful per-sensor fallback.
    if _nvidia_gpu_cache is not None and now - _nvidia_gpu_cache_time <= _NVIDIA_GPU_CACHE_TTL:
        result.update(_nvidia_gpu_cache)
        # Clear AMD-specific voltage when NVIDIA telemetry is active
        result["voltage"] = None
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
                if "nvidia" in low:
                    match = re.search(r"\[([^\]]+)\]", description)
                    dgpu = match.group(1) if match and "geforce" in match.group(1).lower() else description
                elif "amd" in low or "ati" in low:
                    description = description.replace("Advanced Micro Devices, Inc. [AMD/ATI]", "AMD Radeon Graphics")
                    description = re.sub(r"\s+\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\].*$", "", description)
                    description = description.split(" (rev ")[0]
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
