# MikroTik Manager

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

MikroTik Manager is an OpenCode workspace for managing MikroTik routers through a local MCP server.

Licensed under the Apache License, Version 2.0. See `LICENSE`.

Current status: Phases 1-5 are implemented in `tools/mikrotik-mcp/`.

Implemented today:
- RouterOS API client over TCP/TLS
- `/login`
- RouterOS word and sentence encoding/decoding
- stdio MCP bootstrap with FastMCP
- generic read/mutation tools
- optional `jq_filter` support for `resource_print`
- core operational read tools for system, interfaces, addresses, routes, DHCP, and DNS
- file listing, file download, and backup collection workflow
- bridge, VLAN, firewall, PPP, and WireGuard tools
- mocked pytest coverage for client and tool behavior

## Layout

- `tools/mikrotik-mcp/`: active MCP server project
- `tools/mikrotik-mcp/src/main.py`: MCP entry script
- `tools/mikrotik-mcp/src/mikrotik_mcp/server.py`: server wiring and `resource_print`
- `tools/mikrotik-mcp/src/mikrotik_mcp/client.py`: RouterOS transport and protocol logic
- `docs/implementation-phases.md`: delivery roadmap

## Requirements

- Python 3.11+
- RouterOS API enabled on the target router
- workspace-root `.env` with credentials

Example `.env`:

```env
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=false
```

Notes:
- `.env` is loaded from the repository root.
- TLS is enabled by default.
- Default port is `8729` when SSL is enabled, otherwise `8728`.

## Setup

Create or activate a Python environment, then install dependencies from the repository root:

```bash
pip install -r requirements.txt
```

Packaging metadata for publishing is defined in `tools/mikrotik-mcp/pyproject.toml` and uses the Apache-2.0 license.

## Run The MCP Server

From the repository root:

```bash
python tools/mikrotik-mcp/src/main.py <router-host>
```

The host argument is required.

## Testing

```bash
pytest
```

Run one focused test:

```bash
pytest tools/mikrotik-mcp/tests/test_server.py -k invalid_jq_filter
```

Testing notes:
- `pytest` runs with `--disable-socket`, so default tests must stay fully mocked.
- Client transport tests use `FakeSocket` in `tools/mikrotik-mcp/tests/conftest.py`.

Live smoke test for read-only commands:

```bash
python tools/mikrotik-mcp/scripts/live_smoke_read_only.py <router-host>
```

Reports are written to `tools/mikrotik-mcp/reports/live-smoke/` as both JSON and Markdown.

## Tool Surface

Current phases expose these MCP tools:

- `resource_print`: generic RouterOS `/<menu>/print` access with optional `.proplist`, query words, extra attributes, and optional `jq_filter`
- `resource_add`: generic RouterOS `/<menu>/add`
- `resource_set`: generic RouterOS `/<menu>/set` with explicit `item_id`
- `resource_remove`: generic RouterOS `/<menu>/remove` with explicit `item_id`
- `command_run`: generic RouterOS command runner
- `resource_listen`: bounded listen helper for menus that support `listen`
- `command_cancel`: low-level cancel helper for tagged API commands
- `tool_ping`: bounded ping helper that returns per-probe results
- `system_resource_get`: get RouterOS system resource details
- `system_identity_get`: get RouterOS system identity
- `system_clock_get`: get RouterOS system clock settings
- `interface_list`: list interfaces with optional running and disabled filters
- `interface_get`: get one interface by `name` or `item_id`
- `ip_address_list`: list IP addresses with optional interface and disabled filters
- `ip_address_get`: get one IP address by `address` or `item_id`
- `ip_route_list`: list IP routes with optional destination and disabled filters
- `ip_route_get`: get one IP route by `dst_address` or `item_id`
- `dhcp_lease_list`: list DHCP leases with optional address, MAC, and active filters
- `dhcp_server_list`: list configured DHCP servers
- `dhcp_network_list`: list configured DHCP networks
- `dns_get`: get RouterOS DNS settings
- `dns_set`: update RouterOS DNS settings
- `file_list`: list router files with optional directory, name, and type filters
- `system_backup_save`: create a RouterOS backup file on the router
- `system_export`: export RouterOS configuration to an `.rsc` file on the router
- `file_download`: download a router file into the local workspace
- `system_backup_collect`: create and download router backup artifacts
- `bridge_list`: list bridges with optional name and disabled filters
- `bridge_add`: create a bridge using RouterOS bridge attributes
- `bridge_remove`: remove a bridge by `item_id`
- `bridge_port_list`: list bridge ports with optional bridge, interface, and disabled filters
- `bridge_port_add`: add a bridge port using RouterOS bridge port attributes
- `bridge_port_remove`: remove a bridge port by `item_id`
- `bridge_vlan_list`: list bridge VLAN entries with optional bridge, VLAN ID, and disabled filters
- `bridge_vlan_add`: add a bridge VLAN entry using RouterOS bridge VLAN attributes
- `bridge_vlan_remove`: remove a bridge VLAN entry by `item_id`
- `vlan_list`: list VLAN interfaces with optional name, parent interface, and disabled filters
- `vlan_add`: create a VLAN interface using RouterOS VLAN attributes
- `vlan_remove`: remove a VLAN interface by `item_id`
- `firewall_filter_list`: list firewall filter rules with optional chain, action, and disabled filters
- `firewall_filter_add`: add a firewall filter rule using RouterOS firewall attributes
- `firewall_filter_set`: update a firewall filter rule by `item_id`
- `firewall_filter_remove`: remove a firewall filter rule by `item_id`
- `firewall_nat_list`: list firewall NAT rules with optional chain, action, and disabled filters
- `firewall_nat_add`: add a firewall NAT rule using RouterOS firewall attributes
- `firewall_nat_set`: update a firewall NAT rule by `item_id`
- `firewall_nat_remove`: remove a firewall NAT rule by `item_id`
- `firewall_rule_move`: move a firewall filter or NAT rule by `item_id`
- `firewall_address_list_list`: list firewall address-list entries with optional list, address, and disabled filters
- `firewall_address_list_add`: add a firewall address-list entry using RouterOS firewall attributes
- `firewall_address_list_remove`: remove a firewall address-list entry by `item_id`
- `ppp_active_list`: list active PPP sessions with optional service and name filters
- `ppp_secret_list`: list PPP secrets with optional name, service, and disabled filters
- `ppp_secret_add`: create a PPP secret using RouterOS PPP secret attributes
- `ppp_secret_remove`: remove a PPP secret by `item_id`
- `wireguard_interface_list`: list WireGuard interfaces with optional name and disabled filters
- `wireguard_interface_add`: create a WireGuard interface using RouterOS WireGuard attributes
- `wireguard_peer_list`: list WireGuard peers with optional interface and disabled filters
- `wireguard_peer_add`: create a WireGuard peer using RouterOS peer attributes
- `wireguard_peer_remove`: remove a WireGuard peer by `item_id`

`jq_filter` is applied only after RouterOS replies have been normalized into Python JSON-like data.

`resource_listen` and `tool_ping` run on short-lived cloned RouterOS connections so bounded long-running operations do not interfere with the MCP server's shared session socket. `command_cancel` is available as a low-level primitive, but true cross-call session cancellation is not implemented yet.

## Next

Phase 7 is next:

- response formatting tightening
- explicit Markdown/table presentation for common operational outputs
- stable rendering rules for empty values and boolean-like fields

See `docs/implementation-phases.md` for the full roadmap.
