from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.icon import icon_for_battery_level

from .const import DOMAIN, LOGGER

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = []

    try:
        # Get systems and stats from coordinator data
        systems = coordinator.data['systems']
        stats_data = coordinator.data.get('stats', {})

        for system in systems:
            try:
                entities.append(BeszelCPUSensor(coordinator, system))
                entities.append(BeszelRAMSensor(coordinator, system))
                entities.append(BeszelRAMTotalSensor(coordinator, system))
                entities.append(BeszelDiskSensor(coordinator, system))
                entities.append(BeszelDiskTotalSensor(coordinator, system))
                entities.append(BeszelBandwidthSensor(coordinator, system))
                entities.append(BeszelNetworkReceiveSensor(coordinator, system))
                entities.append(BeszelNetworkSendSensor(coordinator, system))
                entities.append(BeszelUptimeSensor(coordinator, system))

                # Get stats for this system
                system_stats = stats_data.get(system.id, {})

                if system.info.get("dt") is not None:
                    entities.append(BeszelTemperatureSensor(coordinator, system))

                if system_stats and 'su' in system_stats:
                    entities.append(BeszelSWAPSensor(coordinator, system))

                if system_stats and 'g' in system_stats:
                    for gpu_key, gpu_data in system_stats['g'].items():
                        entities.append(BeszelGPUSensor(coordinator, system, gpu_key))

                # Create EFS sensors if EFS data is available
                if system_stats and 'efs' in system_stats and isinstance(system_stats['efs'], dict):
                    for disk_name in system_stats['efs'].keys():
                        entities.append(BeszelEFSDiskSensor(coordinator, system, disk_name))
                        entities.append(BeszelDiskTotalSensor(coordinator, system, disk_name))
                        LOGGER.info(f"Created EFS sensors for {system.name} - {disk_name}")

                # Create battery sensor if data is available
                if system_stats and 'bat' in system_stats and isinstance(system_stats['bat'], list):
                    entities.append(BeszelBatterySensor(coordinator, system))

                # Create container sensors
                system_containers = coordinator.data.get('containers', {}).get(system.id, [])
                for container in system_containers:
                    try:
                        entities.append(BeszelContainerCPUSensor(coordinator, system, container))
                        entities.append(BeszelContainerMemorySensor(coordinator, system, container))
                        entities.append(BeszelContainerNetworkSensor(coordinator, system, container))
                        LOGGER.debug(f"Created sensors for container {getattr(container, 'name', 'unknown')} on {system.name}")
                    except Exception as ce:
                        LOGGER.warning(f"Failed to create sensors for container {getattr(container, 'name', 'unknown')}: {ce}")

            except Exception as e:
                LOGGER.error(f"Failed to create sensors for system {system.name if hasattr(system, 'name') else 'unknown'}: {e}")
                continue

        LOGGER.info(f"Created {len(entities)} sensors total")
        async_add_entities(entities)
    except Exception as e:
        LOGGER.error(f"Failed to setup sensors: {e}")
        raise

class BeszelBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, system):
        super().__init__(coordinator)
        self._system_id = system.id

    @property
    def system(self):
        systems = self.coordinator.data['systems']
        for s in systems:
            if s.id == self._system_id:
                return s
        return None

    @property
    def stats_data(self):
        return self.coordinator.data.get('stats', {}).get(self._system_id, {})

    @property
    def device_info(self):
        sys = self.system
        if sys is None:
            return None
        info = getattr(sys, "info", {})
        return {
            "identifiers": {(DOMAIN, sys.id)},
            "name": sys.name,
            "manufacturer": "Beszel",
            "model": info.get("m"),
            "sw_version": info.get("v"),
            "hw_version": info.get("k"),
        }

class BeszelCPUSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_cpu"

    @property
    def name(self):
        return f"{self.system.name} CPU" if self.system else None

    @property
    def icon(self):
        return "mdi:memory"

    @property
    def native_value(self):
        return self.system.info.get("cpu") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelGPUSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, gpu_key):
        super().__init__(coordinator, system)
        self._gpu_key = gpu_key

    @property
    def gpu_data(self):
        gpu_stats = self.stats_data.get("g", {})
        data = gpu_stats.get(self._gpu_key, {})
        return data if isinstance(data, dict) else {}

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_gpu_{self._gpu_key}"

    @property
    def name(self):
        gpu_name = self.gpu_data.get("n")
        return gpu_name if gpu_name else f"GPU {self._gpu_key}"

    @property
    def icon(self):
        return "mdi:expansion-card"
    
    @property
    def available(self):
        gpu_usage = self.gpu_data.get("u") if self.gpu_data else None
        return gpu_usage is not None

    @property
    def native_value(self):
        return self.gpu_data.get("u") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        attributes = {
            "gpu_vram_mb": self.gpu_data.get("mt"),
        }

        gpu_memory_used = self.gpu_data.get("mu")
        if gpu_memory_used is not None:
            attributes["gpu_memory_used_mb"] = gpu_memory_used

        gpu_power = self.gpu_data.get("p")
        if gpu_power is not None:
            attributes["gpu_power_w"] = gpu_power

        return attributes


class BeszelRAMSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram"

    @property
    def name(self):
        return f"{self.system.name} RAM" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        return self.system.info.get("mp") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Total and Used RAM in GB"""

        attributes = {}
        attributes['ram_used_gb'] = self.stats_data.get("mu")
        attributes['ram_total_gb'] = self.stats_data.get("m")

        return attributes

class BeszelSWAPSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_swap"

    @property
    def name(self):
        return f"{self.system.name} SWAP" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"
    
    @property
    def available(self):
        swap_used = self.stats_data.get("su")
        swap_total = self.stats_data.get("s")
        return swap_used is not None and swap_total is not None and swap_total > 0

    @property
    def native_value(self):
        swap_used = self.stats_data.get("su")
        swap_total = self.stats_data.get("s")
        if self.available:
            return (swap_used / swap_total * 100)
        return None

    @property
    def native_unit_of_measurement(self):
        return "%"
    
    @property
    def suggested_display_precision(self):
        return 2

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Total and Used SWAP in GB"""

        attributes = {}
        attributes['swap_used_gb'] = self.stats_data.get("su")
        attributes['swap_total_gb'] = self.stats_data.get("s")

        return attributes


class BeszelDiskSensor(BeszelBaseSensor):

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_disk"

    @property
    def name(self):
        return f"{self.system.name} Disk" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk"

    @property
    def native_value(self):
        return self.system.info.get("dp") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Total and Used DISK in GB"""

        attributes = {}
        attributes['disk_used_gb'] = self.stats_data.get("du")
        attributes['disk_total_gb'] = self.stats_data.get("d")

        return attributes


class BeszelBandwidthSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_bandwidth"

    @property
    def name(self):
        return f"{self.system.name} Bandwidth" if self.system else None

    @property
    def icon(self):
        return "mdi:router-network"
    
    @property
    def available(self):
        bandwidth = self.system.info.get("bb") if self.system else None
        return bandwidth is not None

    @property
    def native_value(self):
        bandwidth = self.system.info.get("bb") if self.system else None
        return bandwidth / 1024000 if bandwidth is not None else None

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def native_unit_of_measurement(self):
        return "MB/s"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT
    
    @property
    def suggested_display_precision(self):
        return 8


class BeszelNetworkReceiveSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_receive"

    @property
    def name(self):
        return f"{self.system.name} Network Receive" if self.system else None

    @property
    def icon(self):
        return "mdi:download-network"

    @property
    def native_value(self):
        b_data = self.stats_data.get("b")
        return b_data[1] / 1024 if self.system and b_data else None

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def native_unit_of_measurement(self):
        return "kB/s"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2
        
class BeszelNetworkSendSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_send"

    @property
    def name(self):
        return f"{self.system.name} Network Send" if self.system else None

    @property
    def icon(self):
        return "mdi:upload-network"

    @property
    def native_value(self):
        b_data = self.stats_data.get("b")
        return b_data[0] / 1024 if self.system and b_data else None

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def native_unit_of_measurement(self):
        return "kB/s"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2

class BeszelTemperatureSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_temperature"

    @property
    def name(self):
        return f"{self.system.name} temperature" if self.system else None
    
    @property
    def available(self):
        temperature = self.system.info.get("dt") if self.system else None
        return temperature is not None

    @property
    def native_value(self):
        return self.system.info.get("dt") if self.system else None

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_unit_of_measurement(self):
        return "°C"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        temperatures = self.stats_data.get("t")

        attributes = {}
        for key, value in temperatures.items():
            attributes[f"temperature_{key}"] = value

        return attributes


class BeszelUptimeSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_uptime"

    @property
    def name(self):
        return f"{self.system.name} uptime" if self.system else None

    @property
    def icon(self):
        return "mdi:sort-clock-descending"

    @property
    def device_class(self):
        return SensorDeviceClass.DURATION

    @property
    def native_value(self):
        return self.system.info.get("u") / 60 if self.system else None

    @property
    def suggested_display_precision(self):
        return 2

    @property
    def state_class(self):
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self):
        return "min"

class BeszelEFSDiskSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_efs_{self._disk_name}"

    @property
    def name(self):
        return f"{self.system.name} EFS {self._disk_name}" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk"

    @property
    def native_value(self):
        if not self.stats_data:
            return None

        efs_data = self.stats_data.get('efs', {})
        disk_data = efs_data.get(self._disk_name, {})

        total_space = disk_data.get('d')
        used_space = disk_data.get('du')

        # Calculate disk usage percentage
        if total_space and used_space and total_space > 0:
            return (used_space / total_space) * 100
        return None

    @property
    def native_unit_of_measurement(self):
        return "%"
    
    @property
    def suggested_display_precision(self):
        return 2

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the EFS disk."""
        if not self.stats_data:
            return {}

        efs_data = self.stats_data.get('efs', {})
        disk_data = efs_data.get(self._disk_name, {})

        return {
            "total_disk_space_gb": disk_data.get('d'),
            "disk_used_gb": disk_data.get('du'),
            "read_mb_s": disk_data.get('r'),
            "write_mb_s": disk_data.get('w'),
        }



class BeszelBatterySensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_battery"

    @property
    def name(self):
        return f"{self.system.name} Battery" if self.system else None

    @property
    def icon(self):
        if not self.stats_data and "bat" not in self.stats_data:
            return "mdi:battery-unknown"
        level, state = self.stats_data.get("bat")
        # https://github.com/henrygd/beszel/blob/4d05bfdff0ec90b68e820ad5dc32a5c4bccf8f0f/internal/site/src/lib/enums.ts#L41-L48
        charging = state == 3

        return icon_for_battery_level(level, charging)

    @property
    def device_class(self):
        return SensorDeviceClass.BATTERY

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if not self.stats_data:
            return None
        return self.stats_data.get("bat")[0]

    @property
    def native_unit_of_measurement(self):
        return "%"


class BeszelRAMTotalSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram_total"

    @property
    def name(self):
        return f"{self.system.name} RAM Total" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        if not self.stats_data:
            return None
        return self.stats_data.get("m")

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def native_unit_of_measurement(self):
        return "GB"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelDiskTotalSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name=None):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        suffix = f"_{self._disk_name}" if self._disk_name else ""
        return f"beszel_{self._system_id}_disk_total{suffix}"

    @property
    def name(self):
        label = f" {self._disk_name}" if self._disk_name else ""
        return f"{self.system.name} Disk Total{label}" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk"

    @property
    def native_value(self):
        if not self.stats_data:
            return None

        if self._disk_name:
            disk_data = self.stats_data.get("efs", {}).get(self._disk_name, {})
            if isinstance(disk_data, dict):
                return disk_data.get("d")
            return None

        return self.stats_data.get("d")

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def native_unit_of_measurement(self):
        return "GB"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


# ---------------------------------------------------------------------------
# Container sensors
# ---------------------------------------------------------------------------

_DOCKER_HEALTH = {0: "none", 1: "starting", 2: "healthy", 3: "unhealthy"}


class BeszelContainerBaseSensor(CoordinatorEntity, SensorEntity):
    """Base for per-container sensors. Each container is its own HA device linked to its host."""

    def __init__(self, coordinator, system, container):
        super().__init__(coordinator)
        self._system_id = system.id
        self._container_id = container.id
        self._container_name = getattr(container, 'name', container.id)

    @property
    def _container(self):
        for c in self.coordinator.data.get('containers', {}).get(self._system_id, []):
            if c.id == self._container_id:
                return c
        return None

    @property
    def _container_stats(self) -> dict:
        return self.coordinator.data.get('container_stats', {}).get(self._system_id, {}).get(self._container_name, {})

    @property
    def available(self):
        return self._container is not None

    @property
    def device_info(self):
        c = self._container
        image = getattr(c, 'image', None) if c else None
        return {
            "identifiers": {(DOMAIN, f"{self._system_id}_container_{self._container_name}")},
            "name": self._container_name,
            "manufacturer": "Docker / Podman",
            "model": image,
            "via_device": (DOMAIN, self._system_id),
        }


class BeszelContainerCPUSensor(BeszelContainerBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_cpu"

    @property
    def name(self):
        return f"{self._container_name} CPU"

    @property
    def icon(self):
        return "mdi:memory"

    @property
    def native_value(self):
        c = self._container
        if c is None:
            return None
        val = getattr(c, 'cpu', None)
        return round(float(val), 2) if val is not None else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        c = self._container
        if c is None:
            return {}
        return {
            "status": getattr(c, 'status', None),
            "health": _DOCKER_HEALTH.get(getattr(c, 'health', 0), "unknown"),
            "image": getattr(c, 'image', None),
        }


class BeszelContainerMemorySensor(BeszelContainerBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_memory"

    @property
    def name(self):
        return f"{self._container_name} Memory"

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        c = self._container
        if c is None:
            return None
        val = getattr(c, 'memory', None)
        return round(float(val), 2) if val is not None else None

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def native_unit_of_measurement(self):
        return "MB"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelContainerNetworkSensor(BeszelContainerBaseSensor):
    """Network bytes sent+received in the last polling interval (from containers.net).

    Per-direction breakdown (sent_mb, recv_mb) is added as attributes when
    container_stats data is available (b[0]=sent bytes, b[1]=recv bytes).
    """

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_network"

    @property
    def name(self):
        return f"{self._container_name} Network"

    @property
    def icon(self):
        return "mdi:swap-horizontal"

    @property
    def native_value(self):
        c = self._container
        if c is None:
            return None
        net_bytes = getattr(c, 'net', None)
        if net_bytes is None:
            return None
        return round(int(net_bytes) / (1024 * 1024), 4)

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def native_unit_of_measurement(self):
        return "MB"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        stats = self._container_stats
        if not stats:
            return {}
        bandwidth = stats.get('b')
        if bandwidth and len(bandwidth) >= 2:
            return {
                "sent_mb": round(bandwidth[0] / (1024 * 1024), 4),
                "recv_mb": round(bandwidth[1] / (1024 * 1024), 4),
            }
        attrs = {}
        ns = stats.get('ns')
        nr = stats.get('nr')
        if ns is not None:
            attrs['sent_mb'] = round(float(ns), 4)
        if nr is not None:
            attrs['recv_mb'] = round(float(nr), 4)
        return attrs
