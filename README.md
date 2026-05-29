# Beszel — Home Assistant Integration

Monitor your [Beszel](https://github.com/henrygd/beszel) servers and **Docker / Podman containers** directly in Home Assistant.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

> **Forked from [Ronjar/beszel-ha](https://github.com/Ronjar/beszel-ha)** and extended with full Docker/Podman container monitoring — CPU, memory, network, running status, and health checks per container.

---

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrejkurlovic&repository=beszel-ha&category=integration)

Or manually via HACS:
1. Go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/andrejkurlovic/beszel-ha` as an **Integration**
3. Search for **Beszel API** and install it
4. Restart Home Assistant

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Beszel API**
3. Fill in the form:

| Field | Description |
|-------|-------------|
| **URL** | Root URL of your Beszel hub, e.g. `http://beszel.example.com` |
| **Username** | Your Beszel account email (or create a dedicated read-only user) |
| **Password** | Account password |
| **Update interval** | Poll interval in seconds (default: 120) |
| **Verify SSL** | Uncheck for self-signed certificates |

> **Tip:** Create a dedicated Beszel user with only the agents you want exposed — that way only those systems and containers appear in HA.

---

## What you get

### Per server (host system)

| Entity | Type | Description |
|--------|------|-------------|
| Status | Binary sensor | Server reachable (connectivity) |
| CPU | Sensor | CPU usage % |
| RAM | Sensor | RAM usage % |
| RAM Total | Sensor | Total RAM (GB) |
| Disk | Sensor | Disk usage % |
| Disk Total | Sensor | Total disk size (GB) |
| Bandwidth | Sensor | Current bandwidth (MB/s) |
| Network Receive | Sensor | Receive rate (kB/s) |
| Network Send | Sensor | Send rate (kB/s) |
| Uptime | Sensor | System uptime (minutes) |
| Temperature | Sensor | CPU/system temperature (°C) — if available |
| SWAP | Sensor | Swap usage % — if swap is configured |
| GPU | Sensor | GPU usage % — if GPU is present |
| Battery | Sensor | Battery level % — if applicable |
| EFS Disk | Sensor | Extra filesystem usage % — per mount |
| S.M.A.R.T. | Binary sensor | Disk health (PROBLEM when failed) — per disk |
| Hub Update | Update entity | Beszel hub update available |

### Per Docker / Podman container

Each container discovered by Beszel appears as its own **HA device** linked to its host server.

| Entity | Type | Description |
|--------|------|-------------|
| Running | Binary sensor | `True` when `status == running` |
| Health | Binary sensor | `True` (= problem) when health check fails — only created for containers that have a healthcheck |
| CPU | Sensor | Container CPU usage % |
| Memory | Sensor | Container memory usage (MB) |
| Network | Sensor | Network bytes transferred in last poll interval (MB) — attributes include `sent_mb` and `recv_mb` breakdown |

Container entity IDs follow the pattern `sensor.<container_name>_cpu`, `binary_sensor.<container_name>_running`, etc.

---

## Dashboard example

Here is a card layout for a server using [mushroom](https://github.com/piitaya/lovelace-mushroom) and [bar-card](https://github.com/custom-cards/bar-card):

```yaml
type: custom:vertical-stack-in-card
cards:
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: My Server
        icon: mdi:server
        secondary: ""
        icon_color: |-
          {% if states('binary_sensor.myserver_status') | bool %}
            green
          {% else %}
            red
          {% endif %}
        entity: binary_sensor.myserver_status
      - type: custom:mushroom-template-card
        entity: sensor.myserver_uptime
        icon: mdi:sort-clock-descending
        primary: "{{ (states('sensor.myserver_uptime') | int / 1440) | int }} Days"
        secondary: ""
        icon_color: blue
  - type: custom:bar-card
    entities:
      - entity: sensor.myserver_cpu
        name: CPU
        color: "#4caf50"
      - entity: sensor.myserver_ram
        name: RAM
        color: "#2196f3"
      - entity: sensor.myserver_disk
        name: Disk
        color: "#f44336"
    positions:
      indicator: "off"
```

For a container overview you can use a standard **Entities card** or filter by device area:

```yaml
type: entities
title: Docker Containers
entities:
  - binary_sensor.my_container_running
  - sensor.my_container_cpu
  - sensor.my_container_memory
  - sensor.my_container_network
```

---

## Screenshots

![Device entities list](/pictures/sensors.png)

![Dashboard card example](/pictures/example_card.png)

---

## Notes

- Container entities are registered at startup. If you add new containers to Beszel, reload the integration (Settings → Integrations → Beszel API → ⋮ → Reload) to pick them up.
- The health binary sensor is only created for containers that have a Docker healthcheck configured (containers without `HEALTHCHECK` in their image will not get this entity).
- Network sensor value represents bytes transferred in the last polling interval, not a continuous rate.

---

## Credits

Built on top of the original integration by [@Ronjar](https://github.com/Ronjar). Container monitoring and fork maintained by [@andrejkurlovic](https://github.com/andrejkurlovic).
