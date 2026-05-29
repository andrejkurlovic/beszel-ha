"""Sensor platform for Beszel — host systems and Docker/Podman containers."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER

# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = []

    systems = coordinator.data.get("systems", [])
    stats_by_system = coordinator.data.get("stats", {})

    for system in systems:
        sid = system.id
        stats = stats_by_system.get(sid, {})

        # --- Always-present host sensors ---
        entities += [
            BeszelCPUSensor(coordinator, system),
            BeszelRAMSensor(coordinator, system),
            BeszelRAMTotalSensor(coordinator, system),
            BeszelDiskSensor(coordinator, system),
            BeszelDiskTotalSensor(coordinator, system),
            BeszelNetworkReceiveSensor(coordinator, system),
            BeszelNetworkSendSensor(coordinator, system),
            BeszelBandwidthSensor(coordinator, system),
            BeszelUptimeSensor(coordinator, system),
        ]

        # --- Conditional host sensors (only when data is present) ---
        if system.info.get("dt") is not None:
            entities.append(BeszelTemperatureSensor(coordinator, system))

        if stats.get("la"):
            entities += [
                BeszelLoadAvgSensor(coordinator, system, 0),  # 1-minute
                BeszelLoadAvgSensor(coordinator, system, 1),  # 5-minute
                BeszelLoadAvgSensor(coordinator, system, 2),  # 15-minute
            ]

        if stats.get("su") is not None:
            entities.append(BeszelSWAPSensor(coordinator, system))

        if stats.get("dr") is not None:
            entities += [
                BeszelDiskReadSensor(coordinator, system),
                BeszelDiskWriteSensor(coordinator, system),
            ]

        if isinstance(stats.get("g"), dict):
            for gpu_key in stats["g"]:
                entities.append(BeszelGPUSensor(coordinator, system, gpu_key))

        if isinstance(stats.get("efs"), dict):
            for disk_name in stats["efs"]:
                entities += [
                    BeszelEFSDiskSensor(coordinator, system, disk_name),
                    BeszelEFSDiskTotalSensor(coordinator, system, disk_name),
                ]
                LOGGER.debug("Created EFS sensors for %s - %s", system.name, disk_name)

        if isinstance(stats.get("bat"), list):
            entities.append(BeszelBatterySensor(coordinator, system))

        # --- Container sensors ---
        container_names = list(coordinator.data.get("container_stats", {}).get(sid, {}).keys())
        LOGGER.debug("Creating sensors for %d containers on %s", len(container_names), system.name)
        for cname in container_names:
            entities += [
                BeszelContainerCPUSensor(coordinator, sid, cname),
                BeszelContainerMemorySensor(coordinator, sid, cname),
                BeszelContainerNetworkSensor(coordinator, sid, cname),
            ]

    LOGGER.info("Created %d sensors total", len(entities))
    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------

class BeszelBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for a Beszel host system."""

    # Force HA recorder to write a row on every coordinator update, not just
    # on value change. This ensures smooth graphs even for stable metrics.
    _attr_force_update = True

    def __init__(self, coordinator, system):
        super().__init__(coordinator)
        self._system_id = system.id

    @property
    def system(self):
        for s in self.coordinator.data.get("systems", []):
            if s.id == self._system_id:
                return s
        return None

    @property
    def stats(self) -> dict:
        return self.coordinator.data.get("stats", {}).get(self._system_id, {})

    @property
    def device_info(self):
        sys = self.system
        if sys is None:
            return None
        info = getattr(sys, "info", {}) or {}
        return {
            "identifiers": {(DOMAIN, sys.id)},
            "name": sys.name,
            "manufacturer": "Beszel",
            "model": info.get("m"),
            "sw_version": info.get("v"),
            "hw_version": info.get("k"),
        }


class BeszelContainerBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for a Docker/Podman container. Uses container_stats as primary source."""

    _attr_force_update = True

    def __init__(self, coordinator, system_id: str, container_name: str):
        super().__init__(coordinator)
        self._system_id = system_id
        self._container_name = container_name

    @property
    def _cstats(self) -> dict:
        """Latest stats for this container from the container_stats collection."""
        return (
            self.coordinator.data
            .get("container_stats", {})
            .get(self._system_id, {})
            .get(self._container_name, {})
        )

    @property
    def _cmeta(self):
        """Optional record from the containers collection (may be None for older agents)."""
        return (
            self.coordinator.data
            .get("containers_meta", {})
            .get(self._system_id, {})
            .get(self._container_name)
        )

    @property
    def available(self) -> bool:
        return bool(self._cstats)

    @property
    def device_info(self):
        meta = self._cmeta
        image = getattr(meta, "image", None) if meta else None
        return {
            "identifiers": {(DOMAIN, f"{self._system_id}_container_{self._container_name}")},
            "name": self._container_name,
            "manufacturer": "Docker / Podman",
            "model": image,
            "via_device": (DOMAIN, self._system_id),
        }


# ---------------------------------------------------------------------------
# Host — CPU / RAM / Disk
# ---------------------------------------------------------------------------

class BeszelCPUSensor(BeszelBaseSensor):
    _attr_icon = "mdi:cpu-64-bit"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_cpu"

    @property
    def name(self):
        return f"{self.system.name} CPU" if self.system else None

    @property
    def native_value(self):
        return self.system.info.get("cpu") if self.system else None


class BeszelRAMSensor(BeszelBaseSensor):
    _attr_icon = "mdi:chip"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram"

    @property
    def name(self):
        return f"{self.system.name} RAM" if self.system else None

    @property
    def native_value(self):
        return self.system.info.get("mp") if self.system else None

    @property
    def extra_state_attributes(self):
        return {
            "ram_used_gb": self.stats.get("mu"),
            "ram_total_gb": self.stats.get("m"),
        }


class BeszelRAMTotalSensor(BeszelBaseSensor):
    _attr_icon = "mdi:chip"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = "GB"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram_total"

    @property
    def name(self):
        return f"{self.system.name} RAM Total" if self.system else None

    @property
    def native_value(self):
        return self.stats.get("m")


class BeszelDiskSensor(BeszelBaseSensor):
    _attr_icon = "mdi:harddisk"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_disk"

    @property
    def name(self):
        return f"{self.system.name} Disk" if self.system else None

    @property
    def native_value(self):
        return self.system.info.get("dp") if self.system else None

    @property
    def extra_state_attributes(self):
        return {
            "disk_used_gb": self.stats.get("du"),
            "disk_total_gb": self.stats.get("d"),
        }


class BeszelDiskTotalSensor(BeszelBaseSensor):
    _attr_icon = "mdi:harddisk"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = "GB"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_disk_total"

    @property
    def name(self):
        return f"{self.system.name} Disk Total" if self.system else None

    @property
    def native_value(self):
        return self.stats.get("d")


# ---------------------------------------------------------------------------
# Host — Network
# ---------------------------------------------------------------------------

class BeszelBandwidthSensor(BeszelBaseSensor):
    """Total bandwidth from system.info.bb (bytes/s → MB/s)."""

    _attr_icon = "mdi:router-network"
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = "MB/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_bandwidth"

    @property
    def name(self):
        return f"{self.system.name} Bandwidth" if self.system else None

    @property
    def available(self):
        return self.system is not None and self.system.info.get("bb") is not None

    @property
    def native_value(self):
        bb = self.system.info.get("bb") if self.system else None
        if bb is None:
            return None
        # bb is bytes/s — convert to MB/s
        return round(bb / (1024 * 1024), 6)


class BeszelNetworkReceiveSensor(BeszelBaseSensor):
    """Receive bytes from the latest 1m stats record (bytes → kB)."""

    _attr_icon = "mdi:download-network"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = "kB"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_receive"

    @property
    def name(self):
        return f"{self.system.name} Network Receive" if self.system else None

    @property
    def native_value(self):
        b = self.stats.get("b")
        if not b or len(b) < 2:
            return None
        # b = [sent_bytes, recv_bytes] in the 1m interval
        return round(b[1] / 1024, 2)


class BeszelNetworkSendSensor(BeszelBaseSensor):
    """Send bytes from the latest 1m stats record (bytes → kB)."""

    _attr_icon = "mdi:upload-network"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = "kB"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_send"

    @property
    def name(self):
        return f"{self.system.name} Network Send" if self.system else None

    @property
    def native_value(self):
        b = self.stats.get("b")
        if not b or len(b) < 2:
            return None
        # b = [sent_bytes, recv_bytes] in the 1m interval
        return round(b[0] / 1024, 2)


# ---------------------------------------------------------------------------
# Host — Disk I/O
# ---------------------------------------------------------------------------

class BeszelDiskReadSensor(BeszelBaseSensor):
    _attr_icon = "mdi:harddisk"
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = "MB/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_disk_read"

    @property
    def name(self):
        return f"{self.system.name} Disk Read" if self.system else None

    @property
    def available(self):
        return self.system is not None and self.stats.get("dr") is not None

    @property
    def native_value(self):
        return self.stats.get("dr")


class BeszelDiskWriteSensor(BeszelBaseSensor):
    _attr_icon = "mdi:harddisk"
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = "MB/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_disk_write"

    @property
    def name(self):
        return f"{self.system.name} Disk Write" if self.system else None

    @property
    def available(self):
        return self.system is not None and self.stats.get("dw") is not None

    @property
    def native_value(self):
        return self.stats.get("dw")


# ---------------------------------------------------------------------------
# Host — Load average
# ---------------------------------------------------------------------------

_LOAD_LABELS = {0: "1m", 1: "5m", 2: "15m"}


class BeszelLoadAvgSensor(BeszelBaseSensor):
    _attr_icon = "mdi:chart-line"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, system, index: int):
        super().__init__(coordinator, system)
        self._index = index
        self._label = _LOAD_LABELS[index]

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_load_{self._label}"

    @property
    def name(self):
        return f"{self.system.name} Load {self._label}" if self.system else None

    @property
    def available(self):
        la = self.stats.get("la")
        return la is not None and len(la) > self._index

    @property
    def native_value(self):
        la = self.stats.get("la")
        if not la or len(la) <= self._index:
            return None
        return round(float(la[self._index]), 2)


# ---------------------------------------------------------------------------
# Host — Temperature / SWAP / Uptime / Battery / GPU
# ---------------------------------------------------------------------------

class BeszelTemperatureSensor(BeszelBaseSensor):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_temperature"

    @property
    def name(self):
        return f"{self.system.name} Temperature" if self.system else None

    @property
    def available(self):
        return self.system is not None and self.system.info.get("dt") is not None

    @property
    def native_value(self):
        return self.system.info.get("dt") if self.system else None

    @property
    def extra_state_attributes(self):
        temps = self.stats.get("t")
        if not temps or not isinstance(temps, dict):
            return {}
        return {f"temperature_{k}": v for k, v in temps.items()}


class BeszelSWAPSensor(BeszelBaseSensor):
    _attr_icon = "mdi:chip"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_swap"

    @property
    def name(self):
        return f"{self.system.name} SWAP" if self.system else None

    @property
    def available(self):
        su = self.stats.get("su")
        s = self.stats.get("s")
        return su is not None and s is not None and s > 0

    @property
    def native_value(self):
        if not self.available:
            return None
        return round(self.stats["su"] / self.stats["s"] * 100, 2)

    @property
    def extra_state_attributes(self):
        return {
            "swap_used_gb": self.stats.get("su"),
            "swap_total_gb": self.stats.get("s"),
        }


class BeszelUptimeSensor(BeszelBaseSensor):
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"
    # MEASUREMENT not TOTAL_INCREASING — uptime resets on reboot
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_uptime"

    @property
    def name(self):
        return f"{self.system.name} Uptime" if self.system else None

    @property
    def native_value(self):
        u = self.system.info.get("u") if self.system else None
        return round(u / 60, 0) if u is not None else None

    @property
    def extra_state_attributes(self):
        u = self.system.info.get("u") if self.system else None
        if u is None:
            return {}
        days = u // 86400
        hours = (u % 86400) // 3600
        mins = (u % 3600) // 60
        return {"uptime_human": f"{days}d {hours}h {mins}m"}


class BeszelBatterySensor(BeszelBaseSensor):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_battery"

    @property
    def name(self):
        return f"{self.system.name} Battery" if self.system else None

    @property
    def icon(self):
        bat = self.stats.get("bat") if self.stats else None
        if not bat or len(bat) < 2:
            return "mdi:battery-unknown"
        level, state = bat[0], bat[1]
        # state 3 = charging (Beszel enum)
        return icon_for_battery_level(level, charging=(state == 3))

    @property
    def native_value(self):
        bat = self.stats.get("bat")
        return bat[0] if bat and len(bat) >= 1 else None


class BeszelGPUSensor(BeszelBaseSensor):
    _attr_icon = "mdi:expansion-card"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, system, gpu_key: str):
        super().__init__(coordinator, system)
        self._gpu_key = gpu_key

    @property
    def _gpu(self) -> dict:
        g = self.stats.get("g", {})
        data = g.get(self._gpu_key, {})
        return data if isinstance(data, dict) else {}

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_gpu_{self._gpu_key}"

    @property
    def name(self):
        return self._gpu.get("n") or f"{self.system.name} GPU {self._gpu_key}"

    @property
    def available(self):
        return self._gpu.get("u") is not None

    @property
    def native_value(self):
        return self._gpu.get("u")

    @property
    def extra_state_attributes(self):
        gpu = self._gpu
        attrs = {}
        if gpu.get("mt") is not None:
            attrs["vram_total_mb"] = gpu["mt"]
        if gpu.get("mu") is not None:
            attrs["vram_used_mb"] = gpu["mu"]
        if gpu.get("p") is not None:
            attrs["power_w"] = gpu["p"]
        return attrs


# ---------------------------------------------------------------------------
# Host — Extra filesystems (EFS)
# ---------------------------------------------------------------------------

class BeszelEFSDiskSensor(BeszelBaseSensor):
    _attr_icon = "mdi:harddisk"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, system, disk_name: str):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    def _efs(self) -> dict:
        return self.stats.get("efs", {}).get(self._disk_name, {})

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_efs_{self._disk_name}"

    @property
    def name(self):
        return f"{self.system.name} EFS {self._disk_name}" if self.system else None

    @property
    def native_value(self):
        d = self._efs()
        total = d.get("d")
        used = d.get("du")
        if total and used and total > 0:
            return round(used / total * 100, 1)
        return None

    @property
    def extra_state_attributes(self):
        d = self._efs()
        return {
            "total_gb": d.get("d"),
            "used_gb": d.get("du"),
            "read_mb_s": d.get("r"),
            "write_mb_s": d.get("w"),
        }


class BeszelEFSDiskTotalSensor(BeszelBaseSensor):
    _attr_icon = "mdi:harddisk"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = "GB"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, system, disk_name: str):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_efs_{self._disk_name}_total"

    @property
    def name(self):
        return f"{self.system.name} EFS {self._disk_name} Total" if self.system else None

    @property
    def native_value(self):
        return self.stats.get("efs", {}).get(self._disk_name, {}).get("d")


# ---------------------------------------------------------------------------
# Container sensors
# ---------------------------------------------------------------------------

_DOCKER_HEALTH = {0: "none", 1: "starting", 2: "healthy", 3: "unhealthy"}


class BeszelContainerCPUSensor(BeszelContainerBaseSensor):
    _attr_icon = "mdi:memory"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_cpu"

    @property
    def name(self):
        return f"{self._container_name} CPU"

    @property
    def native_value(self):
        val = self._cstats.get("c")
        return round(float(val), 2) if val is not None else None

    @property
    def extra_state_attributes(self):
        meta = self._cmeta
        if meta is None:
            return {}
        return {
            "status": getattr(meta, "status", None),
            "health": _DOCKER_HEALTH.get(getattr(meta, "health", 0), "unknown"),
            "image": getattr(meta, "image", None),
        }


class BeszelContainerMemorySensor(BeszelContainerBaseSensor):
    _attr_icon = "mdi:chip"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = "MB"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_memory"

    @property
    def name(self):
        return f"{self._container_name} Memory"

    @property
    def native_value(self):
        val = self._cstats.get("m")
        return round(float(val), 2) if val is not None else None


class BeszelContainerNetworkSensor(BeszelContainerBaseSensor):
    """Total network bytes in the last poll interval (sent + recv) from container_stats.b"""

    _attr_icon = "mdi:swap-horizontal"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = "MB"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_network"

    @property
    def name(self):
        return f"{self._container_name} Network"

    @property
    def native_value(self):
        stats = self._cstats
        b = stats.get("b")
        if b and len(b) >= 2:
            return round((b[0] + b[1]) / (1024 * 1024), 4)
        # fall back to deprecated per-direction MB fields for older agents
        ns = stats.get("ns", 0) or 0
        nr = stats.get("nr", 0) or 0
        if ns or nr:
            return round(float(ns) + float(nr), 4)
        return None

    @property
    def extra_state_attributes(self):
        stats = self._cstats
        b = stats.get("b")
        if b and len(b) >= 2:
            return {
                "sent_mb": round(b[0] / (1024 * 1024), 4),
                "recv_mb": round(b[1] / (1024 * 1024), 4),
            }
        attrs = {}
        if stats.get("ns") is not None:
            attrs["sent_mb"] = round(float(stats["ns"]), 4)
        if stats.get("nr") is not None:
            attrs["recv_mb"] = round(float(stats["nr"]), 4)
        return attrs
