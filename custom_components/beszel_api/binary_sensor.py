"""Binary sensor platform for Beszel — host status, S.M.A.R.T., and container state."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER

# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[BinarySensorEntity] = []

    systems = coordinator.data.get("systems", [])
    smart_by_system = coordinator.data.get("smart_devices", {})

    for system in systems:
        entities.append(BeszelStatusBinarySensor(coordinator, system))

        for device in smart_by_system.get(system.id, []):
            entities.append(BeszelSmartBinarySensor(coordinator, system, device))

        container_names = list(coordinator.data.get("container_stats", {}).get(system.id, {}).keys())
        for cname in container_names:
            entities.append(BeszelContainerStatusBinarySensor(coordinator, system.id, cname))
            meta = coordinator.data.get("containers_meta", {}).get(system.id, {}).get(cname)
            if meta and getattr(meta, "health", 0) != 0:
                entities.append(BeszelContainerHealthBinarySensor(coordinator, system.id, cname))

    LOGGER.info("Created %d binary sensors total", len(entities))
    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------

class BeszelBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
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


# ---------------------------------------------------------------------------
# Host — status
# ---------------------------------------------------------------------------

class BeszelStatusBinarySensor(BeszelBaseBinarySensor):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_status"

    @property
    def name(self):
        return f"{self.system.name} Status" if self.system else None

    @property
    def is_on(self):
        sys = self.system
        return getattr(sys, "status", "") == "up" if sys else False


# ---------------------------------------------------------------------------
# Host — S.M.A.R.T. disk health
# ---------------------------------------------------------------------------

class BeszelSmartBinarySensor(BeszelBaseBinarySensor):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, system, device_data: dict):
        super().__init__(coordinator, system)
        self._device_id = device_data.get("id", "")
        self._device_name = device_data.get("name", "")
        self._disk_name = self._device_name.replace("/dev/", "")

    @property
    def _smart(self) -> dict:
        for d in self.coordinator.data.get("smart_devices", {}).get(self._system_id, []):
            if d.get("id") == self._device_id:
                return d
        return {}

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._device_id}_smart"

    @property
    def name(self):
        model = self._smart.get("model", self._disk_name)
        short = model.split()[0] if model and " " in model else (model or self._disk_name)
        return f"{self.system.name} {short} S.M.A.R.T." if self.system else None

    @property
    def is_on(self):
        d = self._smart
        return d.get("state", "") != "PASSED" if d else None

    @property
    def icon(self):
        if self.is_on:
            return "mdi:harddisk-remove"
        if "nvme" in self._disk_name.lower() or self._smart.get("type") == "nvme":
            return "mdi:expansion-card"
        return "mdi:harddisk"

    @property
    def extra_state_attributes(self):
        d = self._smart
        if not d:
            return {}
        attrs: dict = {"device": self._device_name, "health_state": d.get("state", "")}
        if d.get("temp") is not None:
            attrs["temperature_c"] = d["temp"]
        capacity = d.get("capacity", 0)
        if capacity:
            attrs["capacity_gb"] = round(capacity / (1024 ** 3), 2)
        if d.get("hours") is not None:
            attrs["power_on_hours"] = d["hours"]
            attrs["power_on_days"] = round(d["hours"] / 24, 1)
        if d.get("cycles") is not None:
            attrs["power_cycles"] = d["cycles"]
        for key in ("model", "serial", "firmware", "type"):
            if d.get(key):
                attrs[key] = d[key]
        return attrs


# ---------------------------------------------------------------------------
# Container binary sensors
# ---------------------------------------------------------------------------

_DOCKER_HEALTH = {0: "none", 1: "starting", 2: "healthy", 3: "unhealthy"}


class BeszelContainerBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_force_update = True

    def __init__(self, coordinator, system_id: str, container_name: str):
        super().__init__(coordinator)
        self._system_id = system_id
        self._container_name = container_name

    @property
    def _cstats(self) -> dict:
        return (
            self.coordinator.data
            .get("container_stats", {})
            .get(self._system_id, {})
            .get(self._container_name, {})
        )

    @property
    def _cmeta(self):
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


class BeszelContainerStatusBinarySensor(BeszelContainerBaseBinarySensor):
    """True when the container is running.
    Uses containers_meta.status when available; falls back to presence in container_stats.
    """
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_status"

    @property
    def name(self):
        return f"{self._container_name} Running"

    @property
    def is_on(self):
        meta = self._cmeta
        if meta is not None:
            return getattr(meta, "status", "") == "running"
        return bool(self._cstats)

    @property
    def extra_state_attributes(self):
        meta = self._cmeta
        if meta is None:
            return {}
        return {
            "status": getattr(meta, "status", None),
            "image": getattr(meta, "image", None),
        }


class BeszelContainerHealthBinarySensor(BeszelContainerBaseBinarySensor):
    """True (= problem) when Docker health check is unhealthy (state 3).
    Only created when containers_meta is populated (newer Beszel agents).
    """
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_container_{self._container_name}_health"

    @property
    def name(self):
        return f"{self._container_name} Health"

    @property
    def is_on(self):
        meta = self._cmeta
        return getattr(meta, "health", 0) == 3 if meta else False

    @property
    def icon(self):
        meta = self._cmeta
        return "mdi:alert-circle" if (meta and getattr(meta, "health", 0) == 3) else "mdi:check-circle"

    @property
    def extra_state_attributes(self):
        meta = self._cmeta
        if meta is None:
            return {}
        return {"health_state": _DOCKER_HEALTH.get(getattr(meta, "health", 0), "unknown")}
