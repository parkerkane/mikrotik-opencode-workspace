# Memory

Shared durable project context intended to be safe to keep in git.

## Project
- Active package: `tools/mikrotik/`.

## Entry Points
- OpenCode/MCP entry script: `tools/mikrotik/main.py`
- Server wiring: `tools/mikrotik/mikrotik_mcp/server.py`
- RouterOS client logic: `tools/mikrotik/mikrotik_mcp/client.py`

## Runtime Gotchas
- `main.py` requires router host arg: `python tools/mikrotik/main.py <host>`.
- Startup loads `.env` from the workspace root.
- Default startup env vars: `MIKROTIK_USER`, `MIKROTIK_PASSWORD`.
- `MIKROTIK_API_PASSWORDLESS_ENABLED=true` switches startup to SSH key-based API password rotation and no longer requires `MIKROTIK_PASSWORD`.
- Passwordless startup rotation requires `MIKROTIK_SCP_PRIVATE_KEY` and reuses the existing `MIKROTIK_SCP_*` SSH settings.
- `MIKROTIK_API_PASSWORDLESS_LENGTH` controls the generated API password length and defaults to `32`.
- Optional transport env vars: `MIKROTIK_API_SSL`, `MIKROTIK_API_PORT`, `MIKROTIK_TLS_VERIFY`.
- SCP key auth requires an explicit `MIKROTIK_SCP_PRIVATE_KEY`; otherwise SCP falls back to password env vars.
- SCP key passphrases can be provided with `MIKROTIK_SCP_KEY_PASSPHRASE`.
- SSH/SCP trust uses optional `MIKROTIK_SCP_HOST_FINGERPRINT_SHA256` in `SHA256:...` format; when unset, healthcheck warns and startup password rotation is skipped while generic SCP diagnostics still run.
- TLS defaults to enabled; default port is `8729` when SSL is on, else `8728`.

## Operations
- "create backup" or "create and download backup" maps to `system_backup_collect` with `name_prefix="backup"` unless the user specifies otherwise.
- Default local backup destination: workspace-root `backups/`.
- Default local destination for downloaded router files: workspace-root `exports/`, except backup artifacts which stay in `backups/`.

## RouterOS Notes
- `www-ssl` requires an explicit certificate binding before browser HTTPS works.
- Dynamic `/ip/service` entries with `connection=true` are active client sessions, not separately configurable services.
- RouterOS may reject signing a second certificate with the same subject/SAN set while another matching certificate already exists; renaming the active certificate is often the minimal safe fix.
- Back to Home is fully disabled by setting `/ip/cloud back-to-home-vpn=revoked-and-disabled`; disabling the generated WireGuard interface alone can leave dynamic helper objects behind.
- `/ip/ssh password-authentication=yes-if-no-key` can break password-based SCP even when `/ip/service ssh` remains enabled.
- Router `/system/script` entries should have concise English comments describing the operational purpose in sentence case.
- On this router, `/interface/wifi/registration-table` exposes current client rates and uptime but not usable per-client byte totals, and `/ip/accounting` is unavailable.

## Testing
- `pytest` is configured with `--disable-socket` in root `pytest.ini`; default tests must stay fully mocked.
- Transport tests use `FakeSocket` in `tools/mikrotik/tests/conftest.py`.
- Tool-layer tests use `Mock()`.
- `jq_filter` behavior stays tool-side after RouterOS replies are normalized.
