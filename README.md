# MikroTik Manager

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

MikroTik Manager is an OpenCode workspace for managing MikroTik routers through a local MCP server that talks to the RouterOS API.

Licensed under the Apache License, Version 2.0. See `LICENSE`.

## Features

- RouterOS API client over TCP/TLS
- Passwordless API startup mode with SSH key-based password rotation
- Healthcheck for API, SSH/SFTP, and passwordless readiness
- stdio MCP bootstrap with FastMCP
- Low-level RouterOS read and write tools
- Tools for system, interfaces, addresses, routes, DHCP, DNS, bridges, VLANs, firewall, PPP, and WireGuard
- Router file listing, download, export, and backup collection workflows
- Optional `jq_filter` support for normalized `resource_print` results
- Mocked pytest coverage for client, startup, and tool behavior

## Layout

- `tools/mikrotik/`: active MCP server project
- `tools/mikrotik/main.py`: MCP entry script
- `tools/mikrotik/mikrotik_mcp/server.py`: server wiring and `resource_print`
- `tools/mikrotik/mikrotik_mcp/client.py`: RouterOS transport and protocol logic

## Requirements

- Python 3.11+
- RouterOS API enabled on the target router
- workspace-root `.env` with startup auth settings

Use `.env.example` as the starting point for your local `.env`.

For passwordless startup setup and behavior, see `docs/passwordless-startup.md`.

Example `.env` for the default static-password mode:

```env
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=true

# Optional SCP overrides for file download and backup tools.
MIKROTIK_SCP_HOST=
MIKROTIK_SCP_USER=
MIKROTIK_SCP_PASSWORD=
MIKROTIK_SCP_PORT=22
MIKROTIK_SCP_TIMEOUT=30.0
```

Example `.env` for passwordless startup rotation:

```env
MIKROTIK_USER=admin
MIKROTIK_API_PASSWORDLESS_ENABLED=true
MIKROTIK_API_PASSWORDLESS_LENGTH=32
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=true

# SSH bootstrap settings used to rotate a fresh API password at startup.
MIKROTIK_SCP_HOST=
MIKROTIK_SCP_USER=admin
MIKROTIK_SCP_PRIVATE_KEY=certs/router-key
MIKROTIK_SCP_KEY_PASSPHRASE=
MIKROTIK_SCP_PORT=22
MIKROTIK_SCP_TIMEOUT=30.0
```

Environment variables:

Static mode needs `MIKROTIK_USER` and `MIKROTIK_PASSWORD`.

Passwordless mode needs `MIKROTIK_USER`, `MIKROTIK_API_PASSWORDLESS_ENABLED=true`, and `MIKROTIK_SCP_PRIVATE_KEY`.

| Variable | Static | Passwordless | Default | Purpose |
|---|---|---|---|---|
| `MIKROTIK_USER` | required | required | none | RouterOS user |
| `MIKROTIK_PASSWORD` | required | unused | none | Static API password |
| `MIKROTIK_API_PASSWORDLESS_ENABLED` | optional | required (`true`) | `false` | Enable startup password rotation |
| `MIKROTIK_API_PASSWORDLESS_LENGTH` | unused | optional | `32` | Generated API password length |
| `MIKROTIK_API_SSL` | optional | optional | `true` | Use TLS for the RouterOS API |
| `MIKROTIK_API_PORT` | optional | optional | `8729` with TLS, else `8728` | API port override |
| `MIKROTIK_TLS_VERIFY` | optional | optional | `true` | Verify the router certificate |
| `MIKROTIK_SCP_HOST` | optional | optional | router host arg | SSH/SFTP host override |
| `MIKROTIK_SCP_USER` | optional | optional | `MIKROTIK_USER` | SSH/SFTP username |
| `MIKROTIK_SCP_PASSWORD` | optional | unused | `MIKROTIK_PASSWORD` | SSH/SFTP password fallback |
| `MIKROTIK_SCP_PRIVATE_KEY` | optional | required | none | SSH private key for startup rotation |
| `MIKROTIK_SCP_KEY_PASSPHRASE` | optional | optional | none | SSH private key passphrase |
| `MIKROTIK_SCP_PORT` | optional | optional | `22` | SSH/SFTP port override |
| `MIKROTIK_SCP_TIMEOUT` | optional | optional | `30.0` | SSH/SFTP timeout in seconds |

Notes:
- `.env` is loaded from the repository root.
- TLS is enabled by default.
- When `certs/` exists, `.pem`, `.crt`, and `.cer` files in it are loaded into the TLS trust store except names ending with `.disabled`.
- `certs/` is for local PEM CA certificates only; only `certs/README.md` is tracked by git.
- Passwordless startup rotation currently requires SSH key auth and fails startup if the password rotation step fails.

## Setup

Create or activate a Python environment, then install dependencies from the repository root:

```bash
pip install -r requirements.txt
```

Packaging metadata for publishing is defined in `tools/mikrotik/pyproject.toml` and uses the Apache-2.0 license.

## Run The MCP Server

From the repository root:

```bash
python tools/mikrotik/main.py <router-host>
```

The host argument is required.

## Run OpenCode In Docker

These wrappers run OpenCode inside a hardened container while keeping the workspace mounted at `/workspace` so project `opencode.json` and the local MCP server still work.

Builds are automatic on each run:

```bash
scripts/run-opencode-shared.sh
scripts/run-opencode-isolated.sh
```

Shared credentials mode:
- Reuses host OpenCode config from `~/.config/opencode`
- Reuses host provider auth from `~/.local/share/opencode/auth.json`
- Keeps container cache, logs, snapshots, and other runtime state in Docker named volumes

Fully isolated mode:
- Does not reuse any host OpenCode config or auth
- Stores config, auth, logs, snapshots, and cache in Docker named volumes only

Both wrappers:
- mount this repo at `/workspace`
- start from `/workspace` so project `opencode.json` is discovered automatically
- run with `--cap-drop=ALL` and `--security-opt no-new-privileges:true`
- disable Git credential prompting so authenticated `git push` stays a host-side action unless you explicitly add Git credentials to the container

Pass a custom command instead of the default `opencode /workspace` if needed:

```bash
scripts/run-opencode-shared.sh opencode --version
scripts/run-opencode-isolated.sh bash
```

Reset Docker volumes created by the wrappers:

```bash
scripts/reset-opencode-docker-volumes.sh
```

Note: `opencode.json` currently targets `router.local`. If that hostname does not resolve from inside Docker on your machine, replace it with the router IP or another resolvable DNS name.

The Docker wrappers use the `mikrotik-manager-opencode` image name and `mikrotik-manager-opencode-*` Docker volume names by default.

## Testing

```bash
pytest
```

Run one focused test:

```bash
pytest tools/mikrotik/tests/test_server.py -k invalid_jq_filter
```

Testing notes:
- `pytest` runs with `--disable-socket`, so default tests must stay fully mocked.
- Client transport tests use `FakeSocket` in `tools/mikrotik/tests/conftest.py`.

Live smoke test for read-only commands:

```bash
python tools/mikrotik/scripts/live_smoke_read_only.py <router-host>
```

Reports are written to `tools/mikrotik/reports/live-smoke/` as both JSON and Markdown.

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
