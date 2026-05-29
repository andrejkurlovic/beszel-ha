# Beszel — Home Assistant Integration

Monitor your [Beszel](https://github.com/henrygd/beszel) servers and Docker/Podman containers directly in Home Assistant.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

> **Forked from [Ronjar/beszel-ha](https://github.com/Ronjar/beszel-ha)** and extended with container monitoring, load average, disk I/O, graph history fixes, and Lovelace card examples.

---

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrejkurlovic&repository=beszel-ha&category=integration)

Or manually via HACS:
1. **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/andrejkurlovic/beszel-ha` as an **Integration**
3. Search for **Beszel API** and install it
4. Restart Home Assistant

---

## Setup

**Settings → Devices & Services → Add Integration → Beszel API**

| Field | Description |
|-------|-------------|
| **URL** | Beszel hub URL, e.g. `http://beszel.local:8090` |
| **Username** | Beszel account email |
| **Password** | Account password |
| **Update interval** | Poll interval in seconds (default: **30**) |
| **Verify SSL** | Uncheck for self-signed certificates |

> Create a dedicated read-only Beszel user and assign only the agents you want exposed to HA.

---

## Entities

### Per server (host)

| Entity | Description | Notes |
|--------|-------------|-------|
| Status | Online / offline | Binary sensor |
| CPU | CPU usage % | Graphable |
| RAM | RAM usage % | Graphable, attributes: used/total GB |
| RAM Total | Total RAM in GB | |
| Disk | Root disk usage % | Attributes: used/total GB |
| Disk Total | Root disk size in GB | |
| Bandwidth | Total bandwidth MB/s | From `system.info.bb` |
| Network Receive | Received kB per interval | From latest 1m stats record |
| Network Send | Sent kB per interval | From latest 1m stats record |
| Disk Read | Disk read rate MB/s | From stats, if available |
| Disk Write | Disk write rate MB/s | From stats, if available |
| Load 1m | 1-minute load average | From stats, if available |
| Load 5m | 5-minute load average | From stats, if available |
| Load 15m | 15-minute load average | From stats, if available |
| Uptime | Uptime in minutes | Attributes: human-readable (Xd Yh Zm) |
| Temperature | CPU/system temp °C | Only if Beszel reports it |
| SWAP | Swap usage % | Only if swap is configured |
| Battery | Battery % | Only on laptops/UPS systems |
| GPU | GPU usage % | One per GPU, only if detected |
| EFS Disk | Extra filesystem usage % | One per extra mount |
| S.M.A.R.T. | Disk health (PROBLEM=failed) | Binary sensor, per disk |

### Per Docker / Podman container

Each container is its own **HA device** linked to its host server via `via_device`.

| Entity | Description |
|--------|-------------|
| Running | True when container status is `running` |
| Health | True when healthcheck is `unhealthy` (only if healthcheck is configured) |
| CPU | Container CPU usage % |
| Memory | Container memory usage MB |
| Network | Total bytes sent+recv per interval (MB), attributes: sent_mb / recv_mb |

---

## Dashboard cards

Install [mushroom](https://github.com/piitaya/lovelace-mushroom) and [bar-card](https://github.com/custom-cards/bar-card) via HACS for the best experience.

### Server overview card

```yaml
type: custom:vertical-stack-in-card
cards:
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: "{{ device_attr('sensor.myserver_cpu', 'name') | regex_replace(' CPU', '') }}"
        secondary: >
          {{ states('sensor.myserver_uptime_human', default='') }}
          {% if states('sensor.myserver_uptime') | int > 0 %}
          up {{ (states('sensor.myserver_uptime') | int / 1440) | int }}d
          {% endif %}
        icon: mdi:server
        icon_color: >
          {% if is_state('binary_sensor.myserver_status', 'on') %}green{% else %}red{% endif %}
        entity: binary_sensor.myserver_status
        tap_action:
          action: navigate
          navigation_path: /lovelace/servers
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
    max: 100
    positions:
      indicator: "off"
      name: inside
      value: inside
```

### Uptime card

```yaml
type: custom:mushroom-template-card
entity: sensor.myserver_uptime
primary: "{{ state_attr('sensor.myserver_uptime', 'uptime_human') }}"
secondary: "Uptime"
icon: mdi:clock-outline
icon_color: blue
```

### Network / bandwidth graph

```yaml
type: history-graph
entities:
  - entity: sensor.myserver_network_receive
    name: Receive
  - entity: sensor.myserver_network_send
    name: Send
hours_to_show: 6
title: Network (kB per interval)
```

### Load average card (server health at a glance)

```yaml
type: glance
title: Load Average
entities:
  - entity: sensor.myserver_load_1m
    name: 1 min
  - entity: sensor.myserver_load_5m
    name: 5 min
  - entity: sensor.myserver_load_15m
    name: 15 min
```

### Container overview card

```yaml
type: entities
title: Docker Containers
entities:
  - entity: binary_sensor.my_container_running
    name: my-container
    secondary_info: last-changed
  - entity: sensor.my_container_cpu
    name: CPU
  - entity: sensor.my_container_memory
    name: Memory
  - entity: sensor.my_container_network
    name: Network
```

### All containers at a glance (mushroom chips)

```yaml
type: custom:mushroom-chips-card
chips:
  - type: entity
    entity: binary_sensor.nginx_running
    icon: mdi:web
  - type: entity
    entity: binary_sensor.postgres_running
    icon: mdi:database
  - type: entity
    entity: binary_sensor.homeassistant_running
    icon: mdi:home-assistant
```

### Full server card with containers

```yaml
type: custom:vertical-stack-in-card
title: My Server
cards:
  - type: glance
    entities:
      - entity: binary_sensor.myserver_status
        name: Status
      - entity: sensor.myserver_cpu
        name: CPU
      - entity: sensor.myserver_ram
        name: RAM
      - entity: sensor.myserver_disk
        name: Disk
      - entity: sensor.myserver_uptime
        name: Uptime (min)
  - type: entities
    title: Containers
    entities:
      - entity: binary_sensor.nginx_running
      - entity: binary_sensor.postgres_running
      - entity: binary_sensor.redis_running
```

---

## Notes on graphs

- All sensors have `force_update = True` — every poll writes a new HA history record, even for unchanged values, giving smooth graphs instead of flat lines.
- Default poll interval is **30 seconds**. Change it in **Settings → Integrations → Beszel API → Configure** to a higher value if you have many systems.
- HA's long-term statistics (shown in the Statistics dashboard) accumulate min/mean/max at 5-minute intervals — these populate automatically over time.
- If you just installed the integration, graphs will be sparse until history builds up. That's normal.

## Notes on containers

- Containers are discovered from the `container_stats` PocketBase collection (same pattern as `system_stats`) — works for all Beszel agent versions.
- If you add or remove containers, reload the integration: **Settings → Integrations → Beszel API → ⋮ → Reload**.
- The `containers` collection (for status/health/image metadata) is only populated by newer Beszel agents. If these attributes are missing, it means your agent is older — the core CPU/memory/network sensors still work.

---

## Credits

Original integration by [@Ronjar](https://github.com/Ronjar). Container monitoring, graph fixes, load average, disk I/O, and dashboard examples by [@andrejkurlovic](https://github.com/andrejkurlovic).
