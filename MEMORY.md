# Memory

Shared durable project context intended to be safe to keep in git.

## Project
- Active package: `tools/mikrotik/`.

## Entry Points
- OpenCode/MCP entry script: `tools/mikrotik/main.py`
- Claude Code project MCP config: `.mcp.json`
- Server wiring: `tools/mikrotik/mikrotik_mcp/server.py`
- RouterOS client logic: `tools/mikrotik/mikrotik_mcp/client.py`

## Runtime Gotchas
- `main.py` requires router host arg: `python tools/mikrotik/main.py <host>`.
- Startup reads `MIKROTIK_*` from the process environment first; `.env` is an optional fallback loaded from the current working directory.
- Default startup env vars: `MIKROTIK_USER`, `MIKROTIK_PASSWORD`.
- `MIKROTIK_API_PASSWORDLESS_ENABLED=true` switches startup to SSH key-based API password rotation and no longer requires `MIKROTIK_PASSWORD`.
- Passwordless startup rotation requires `MIKROTIK_SCP_PRIVATE_KEY` and reuses the existing `MIKROTIK_SCP_*` SSH settings.
- `MIKROTIK_API_PASSWORDLESS_LENGTH` controls the generated API password length and defaults to `32`.
- Optional transport env vars: `MIKROTIK_API_SSL`, `MIKROTIK_API_PORT`, `MIKROTIK_TLS_VERIFY`.
- SCP key auth requires an explicit `MIKROTIK_SCP_PRIVATE_KEY`; otherwise SCP falls back to password env vars.
- SCP key passphrases can be provided with `MIKROTIK_SCP_KEY_PASSPHRASE`.
- SSH/SCP trust uses `MIKROTIK_SCP_HOST_FINGERPRINT_SHA256` in `SHA256:...` format; it is optional for generic diagnostics but required when passwordless startup rotation is enabled.
- TLS defaults to enabled; default port is `8729` when SSL is on, else `8728`.

## Operations
- "create backup" or "create and download backup" maps to `system_backup_collect` with `name_prefix="backup"` unless the user specifies otherwise.
- Default local backup destination: current-working-directory `backups/`.
- Default local destination for downloaded router files: current-working-directory `exports/`, except backup artifacts which stay in `backups/`.

## RouterOS Notes
- `www-ssl` requires an explicit certificate binding before browser HTTPS works.
- Dynamic `/ip/service` entries with `connection=true` are active client sessions, not separately configurable services.
- RouterOS may reject signing a second certificate with the same subject/SAN set while another matching certificate already exists; renaming the active certificate is often the minimal safe fix.
- Back to Home is fully disabled by setting `/ip/cloud back-to-home-vpn=revoked-and-disabled`; disabling the generated WireGuard interface alone can leave dynamic helper objects behind.
- `/ip/ssh password-authentication=yes-if-no-key` can break password-based SCP even when `/ip/service ssh` remains enabled.
- Router `/system/script` entries should have concise English comments describing the operational purpose in sentence case.
- On this router, `/interface/wifi/registration-table` exposes current client rates and uptime but not usable per-client byte totals, and `/ip/accounting` is unavailable.
- RouterOS `dst-port` match values accept at most 15 comma-separated elements per rule; larger bait-port sets must be split across multiple equivalent rules.
- WAN honeypot policy on this router uses staged address-lists `honeypot_stage1` `15m`, `honeypot_stage2` `1d`, `honeypot_block` `7d`, with `raw prerouting` drop for `honeypot_block`, TCP bait ports only, bait list split across multiple rules covering `21,22,23,25,53,80,110,443,445,1433,1723,3389,5060,5061,5800,5900,8080,8291,8728,8729,10000,1337,16993,44443`, and medium-annoyance IPv4 tarpit on `honeypot_stage1` and `honeypot_stage2` for new TCP bait-port hits with `limit=10,5:packet` before final WAN drop.
- IPv6 WAN honeypot policy matches IPv4 staged behavior with `honeypot6_stage1` `15m`, `honeypot6_stage2` `1d`, `honeypot6_block` `7d`, `raw prerouting` drop for `honeypot6_block`, TCP bait ports only, no ICMPv6 trapping, and same split bait-port set as IPv4.

## Testing
- `pytest` is configured with `--disable-socket` in root `pytest.ini`; default tests must stay fully mocked.
- Transport tests use `FakeSocket` in `tools/mikrotik/tests/conftest.py`.
- Tool-layer tests use `Mock()`.
- `jq_filter` behavior stays tool-side after RouterOS replies are normalized.
