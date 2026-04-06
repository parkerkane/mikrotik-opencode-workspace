# MCP Server Design

## Startup & Configuration

The server is launched by OpenCode as a child process:

```
python tools/mikrotik-mcp/src/main.py <host>
```

| Source | Value | Where used |
|--------|-------|------------|
| CLI arg `0` | Router host/IP | API socket destination |
| `MIKROTIK_USER` | `.env` | `/login` username |
| `MIKROTIK_PASSWORD` | `.env` | `/login` password |
| `MIKROTIK_API_SSL` | `.env` | Select `api` vs `api-ssl` |
| `MIKROTIK_API_PORT` | `.env` | Override API port if needed |
| `MIKROTIK_TLS_VERIFY` | `.env` | `true`/`false`, default `true` |

Default connection settings:

- plain API: `8728`
- API-SSL: `8729`

## RouterOS API Model

The MCP server should not think in terms of HTTP resources. It should think in terms of RouterOS API sentences that closely follow CLI commands.

Examples of raw RouterOS API command words:

- list interfaces: `/interface/print`
- add address: `/ip/address/add`
- update interface: `/interface/set`
- remove route: `/ip/route/remove`
- reboot router: `/system/reboot`

Each API exchange is sentence-based:

- first word is the command, such as `/ip/address/print`
- attributes are encoded as words like `=address=192.168.88.1/24`
- API attributes include `.tag` for correlating replies
- query words such as `?dynamic=true` and `?#|` are used with `print`
- replies arrive as `!re`, `!done`, `!trap`, `!empty`, or `!fatal`

## Client Responsibilities

The RouterOS API client should:

- open the TCP or TLS socket
- perform `/login`
- encode words and sentence termination correctly
- expose high-level helpers for common API verbs
- support `.tag` on concurrent commands when needed
- normalize RouterOS replies into Python data structures

Suggested client surface as thin wrappers over RouterOS API commands:

- `print(menu, proplist=None, queries=None, **attrs)` -> sends `/<menu>/print`
- `add(menu, **attrs)` -> sends `/<menu>/add`
- `set(menu, id, **attrs)` -> sends `/<menu>/set` with `=.id=<id>`
- `remove(menu, id)` -> sends `/<menu>/remove` with `=.id=<id>`
- `command(path, **attrs)` -> sends the raw command word such as `/system/reboot`
- `listen(menu, queries=None, **attrs)` -> sends `/<menu>/listen`
- `cancel(tag)` -> sends `/cancel` with `=tag=<tag>`

## MCP Tool Catalog

Tools are grouped by RouterOS menu domain.

The practical design is:

- dedicated tools for common operations
- a small generic command layer for advanced or less common RouterOS menus

---

### System

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `system_get_identity` | Get router name/identity | `/system/identity/print` |
| `system_get_resource` | CPU, memory, uptime, version | `/system/resource/print` |
| `system_get_routerboard` | Hardware info | `/system/routerboard/print` |
| `system_get_clock` | Get router date/time settings | `/system/clock/print` |
| `system_get_health` | Read PSU, temperature, voltage if supported | `/system/health/print` |
| `system_get_package_update` | Check package update status | `/system/package/update/print` |
| `system_reboot` | Reboot the router | `/system/reboot` |
| `system_shutdown` | Shut down the router if supported | `/system/shutdown` |
| `system_backup_save` | Create a backup file | `/system/backup/save` |
| `system_export` | Export configuration to `.rsc` | `/export` |
| `system_backup_collect` | Create backup and export on-router, then download both locally | composite workflow |

---

### Interfaces

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `interface_list` | List all interfaces with status | `/interface/print` |
| `interface_get` | Get single interface by name or id | `/interface/print` with query |
| `interface_enable` | Enable interface | `/interface/set` |
| `interface_disable` | Disable interface | `/interface/set` |
| `interface_set_comment` | Update interface comment or metadata | `/interface/set` |
| `interface_monitor` | Run one-shot monitor on an interface family that supports it | `/interface/<family>/monitor` |

### Bridge / Switching

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `bridge_list` | List bridges | `/interface/bridge/print` |
| `bridge_add` | Create a bridge | `/interface/bridge/add` |
| `bridge_remove` | Remove a bridge | `/interface/bridge/remove` |
| `bridge_port_list` | List bridge ports | `/interface/bridge/port/print` |
| `bridge_port_add` | Add interface to bridge | `/interface/bridge/port/add` |
| `bridge_port_remove` | Remove bridge port | `/interface/bridge/port/remove` |
| `bridge_vlan_list` | List bridge VLAN entries | `/interface/bridge/vlan/print` |
| `bridge_vlan_add` | Add bridge VLAN entry | `/interface/bridge/vlan/add` |
| `bridge_vlan_remove` | Remove bridge VLAN entry | `/interface/bridge/vlan/remove` |

---

### VLAN

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `vlan_list` | List VLAN interfaces | `/interface/vlan/print` |
| `vlan_add` | Create VLAN interface | `/interface/vlan/add` |
| `vlan_remove` | Remove VLAN interface | `/interface/vlan/remove` |

---

### IP Addresses

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `ip_address_list` | List assigned IP addresses | `/ip/address/print` |
| `ip_address_add` | Assign IP to interface | `/ip/address/add` |
| `ip_address_set` | Update IP assignment | `/ip/address/set` |
| `ip_address_remove` | Remove IP assignment | `/ip/address/remove` |

---

### IP Routes

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `ip_route_list` | List routing table | `/ip/route/print` |
| `ip_route_add` | Add static route | `/ip/route/add` |
| `ip_route_set` | Update route | `/ip/route/set` |
| `ip_route_remove` | Remove route | `/ip/route/remove` |

### ARP / Neighbors

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `ip_arp_list` | List ARP table entries | `/ip/arp/print` |
| `neighbor_list` | List discovered neighbors | `/ip/neighbor/print` |

---

### DHCP

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `dhcp_server_list` | List DHCP servers | `/ip/dhcp-server/print` |
| `dhcp_server_add` | Create DHCP server | `/ip/dhcp-server/add` |
| `dhcp_lease_list` | List current leases | `/ip/dhcp-server/lease/print` |
| `dhcp_lease_get` | Get a single lease | `/ip/dhcp-server/lease/print` with query |
| `dhcp_lease_make_static` | Convert lease to static | `/ip/dhcp-server/lease/make-static` |
| `dhcp_network_list` | List DHCP networks | `/ip/dhcp-server/network/print` |

---

### PPP / VPN

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `ppp_active_list` | List active PPP sessions | `/ppp/active/print` |
| `ppp_secret_list` | List PPP secrets | `/ppp/secret/print` |
| `ppp_secret_add` | Create PPP secret | `/ppp/secret/add` |
| `ppp_secret_remove` | Remove PPP secret | `/ppp/secret/remove` |
| `wireguard_interface_list` | List WireGuard interfaces | `/interface/wireguard/print` |
| `wireguard_interface_add` | Add WireGuard interface | `/interface/wireguard/add` |
| `wireguard_peer_list` | List WireGuard peers | `/interface/wireguard/peers/print` |
| `wireguard_peer_add` | Add WireGuard peer | `/interface/wireguard/peers/add` |
| `wireguard_peer_remove` | Remove WireGuard peer | `/interface/wireguard/peers/remove` |

---

### Firewall

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `firewall_filter_list` | List filter rules | `/ip/firewall/filter/print` |
| `firewall_filter_add` | Add filter rule | `/ip/firewall/filter/add` |
| `firewall_filter_set` | Update filter rule | `/ip/firewall/filter/set` |
| `firewall_filter_remove` | Remove filter rule | `/ip/firewall/filter/remove` |
| `firewall_nat_list` | List NAT rules | `/ip/firewall/nat/print` |
| `firewall_nat_add` | Add NAT rule | `/ip/firewall/nat/add` |
| `firewall_nat_set` | Update NAT rule | `/ip/firewall/nat/set` |
| `firewall_nat_remove` | Remove NAT rule | `/ip/firewall/nat/remove` |
| `firewall_rule_move` | Reorder firewall rule position | `/ip/firewall/<table>/move` |
| `firewall_address_list_list` | List address lists | `/ip/firewall/address-list/print` |
| `firewall_address_list_add` | Add entry to address list | `/ip/firewall/address-list/add` |
| `firewall_address_list_remove` | Remove address list entry | `/ip/firewall/address-list/remove` |

---

### DNS

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `dns_get` | Get DNS settings | `/ip/dns/print` |
| `dns_set` | Set DNS servers and related options | `/ip/dns/set` |
| `dns_static_list` | List static DNS entries | `/ip/dns/static/print` |
| `dns_static_add` | Add static DNS entry | `/ip/dns/static/add` |
| `dns_static_remove` | Remove static entry | `/ip/dns/static/remove` |

### Files / Scripts / Logs

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `file_list` | List files on the router | `/file/print` |
| `file_download` | Download a router file to the local workspace | file transfer helper |
| `log_list` | List recent log entries | `/log/print` |
| `log_add` | Add a log entry through script execution | `/system/script/run` or generic command |
| `script_list` | List saved scripts | `/system/script/print` |
| `script_run` | Run a saved script | `/system/script/run` |
| `script_execute` | Execute a one-off console script via generic command path | generic command |

---

## Custom Backup Workflow

The server should expose a dedicated `system_backup_collect` tool for the backup behavior that spans multiple RouterOS commands plus a local file write.

Expected behavior:

1. Ensure a `backups/` directory exists on the router filesystem
2. Run `/system/backup/save` and write the binary backup into the router-side `backups/` directory
3. Run `/export` and write the exported config into the router-side `backups/` directory
4. Download both generated files into the local workspace `backups/` directory
5. Return the local file paths and router file paths in the tool result

Suggested tool name:

- `system_backup_collect`

Suggested inputs:

- `name_prefix`: optional base name for the generated files
- `include_sensitive`: optional flag for whether export should include sensitive values if supported by the chosen export mode
- `local_dir`: optional local target directory, default `backups/`

Not recommended for this tool:

- `jq_filter`: this tool's primary output is file creation and file download, not a large JSON payload. If filtering is needed, it makes more sense on generic data-returning tools such as `resource_print`, not on the backup collection workflow.

Suggested generated filenames:

- router binary backup: `backups/<prefix>-<timestamp>.backup`
- router export: `backups/<prefix>-<timestamp>.rsc`
- local binary backup: `backups/<router>-<prefix>-<timestamp>.backup`
- local export: `backups/<router>-<prefix>-<timestamp>.rsc`

Suggested RouterOS API command sequence:

1. `/file/print` to check whether `backups` already exists
2. If missing, create it using a generic command or script-assisted file creation supported by the implementation
3. `/system/backup/save` with `=name=backups/<filename-without-extension>`
4. `/export` with `=file=backups/<filename-without-extension>`
5. `/file/print` with query filters to confirm both files exist
6. use the file download helper to copy both files into the local workspace

Failure handling requirements:

- if router backup creation succeeds but export fails, do not download partial results silently; return a clear partial-failure error
- if both router files exist but one local download fails, return both the completed and failed paths
- never overwrite local files implicitly; generate unique names or fail clearly
- surface router-side permission or storage errors with the original RouterOS message when possible

Response shape should include:

- `router_backup_path`
- `router_export_path`
- `local_backup_path`
- `local_export_path`
- `created_at`

This tool is intentionally composite rather than a thin wrapper because the user-facing requirement is a complete backup collection workflow, not just a single RouterOS command.

---

### Wireless / WiFi (if applicable)

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `wireless_list` | List wireless interfaces | `/interface/wireless/print` |
| `wireless_registration_list` | List connected clients | `/interface/wireless/registration-table/print` |
| `wifi_list` | List RouterOS WiFi interfaces | `/interface/wifi/print` |
| `wifi_registration_list` | List connected WiFi clients | `/interface/wifi/registration-table/print` |
| `wifi_monitor` | Run one-shot WiFi monitor | `/interface/wifi/monitor` |

---

### Diagnostics / Tools

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `tool_ping` | Ping from router | `/tool/ping` |
| `tool_traceroute` | Traceroute from router | `/tool/traceroute` |
| `tool_fetch` | Run RouterOS fetch tool for remote retrieval | `/tool/fetch` |
| `tool_bandwidth_test` | Run bandwidth test | `/tool/bandwidth-test` |

---

### Generic API Access

| Tool | Description | RouterOS API command |
|------|-------------|----------------------|
| `resource_print` | Generic `print` with query words and `.proplist` support | `/<menu>/print` |
| `resource_add` | Generic add for supported menus | `/<menu>/add` |
| `resource_set` | Generic set for supported menus | `/<menu>/set` |
| `resource_remove` | Generic remove for supported menus | `/<menu>/remove` |
| `command_run` | Generic command runner for documented console commands | `/<command>` |
| `resource_listen` | Listen for changes on menus where `listen` is supported | `/<menu>/listen` |
| `command_cancel` | Cancel a tagged long-running API command | `/cancel` |

---

## Minimum Viable Coverage

If the first implementation needs to stay small, the minimum useful set should still include:

- system identity, resources, reboot, backup, and export
- custom backup collection to local `backups/`
- interfaces, bridges, VLANs, IP addresses, routes, ARP, and neighbors
- DHCP, DNS, firewall filter/NAT/address-lists, and rule reordering
- files, logs, scripts, ping, traceroute, and fetch
- WireGuard and a generic `resource_print` / `command_run` fallback

Without those generic tools, the design will lag behind RouterOS API coverage because RouterOS exposes a very broad CLI-shaped command surface.

## Tool Schema Pattern

Each tool follows this MCP tool definition shape:

```json
{
  "name": "interface_list",
  "description": "List all network interfaces and their status",
  "inputSchema": {
    "type": "object",
    "properties": {
      "running_only": {
        "type": "boolean",
        "description": "Only return interfaces that are currently running"
      }
    },
    "required": []
  }
}
```

## Cross-Cutting Output Options

It can make sense to support a common optional `jq_filter` parameter on data-returning tools, but not on every tool.

Good candidates:

- list tools such as `interface_list`, `ip_route_list`, `dhcp_lease_list`
- get/query tools such as `resource_print`
- diagnostics that return structured arrays or objects

Poor candidates:

- mutating tools whose main value is the side effect, such as `system_reboot`
- composite workflow tools whose main value is created artifacts, such as `system_backup_collect`
- streaming or listen-style tools

Recommended behavior:

- apply `jq_filter` only after the raw RouterOS reply has already been normalized into JSON
- keep the raw tool behavior as the default when `jq_filter` is omitted
- if the filter fails to parse or evaluate, return a clear MCP error instead of partial output
- document whether the filter is applied to an array payload, an object payload, or a wrapped response object

Recommended scope for the first implementation:

- support `jq_filter` on `resource_print`
- optionally add it to other high-volume read tools later if it proves useful

This keeps the feature useful without forcing every tool to carry extra output-shaping complexity.

## Error Handling

- login failure should surface a clear credential error
- `!trap` replies should include RouterOS `message` and `category` when present
- `!fatal` should be surfaced as a connection-ending error
- network errors and timeouts should return actionable messages
- TLS errors should suggest `MIKROTIK_TLS_VERIFY=false` for self-signed lab environments

## Response Format

All tools return structured JSON content in the MCP response. List tools return arrays assembled from `!re` replies; mutating tools return the resulting `!done` data when present and otherwise a small success object. Long-running or streaming commands should be exposed only where the MCP UX makes sense.

## Testability

- Keep the RouterOS API transport isolated so tool tests can mock it directly
- Prefer mocking the transport or client object over hitting a real router in default test runs
- Use `pytest` fixtures for fake credentials, fake hosts, encoded reply sequences, and reusable RouterOS payloads
