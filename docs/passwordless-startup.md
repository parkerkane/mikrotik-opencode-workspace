# Passwordless Startup Rotation

## Purpose

This MCP server can avoid storing a long-lived RouterOS API password in `.env`.

When passwordless startup mode is enabled, the server uses SSH key authentication during startup to rotate a fresh API password for the configured RouterOS user, then uses that generated password for the current process.

Default behavior is unchanged: the feature is disabled unless explicitly enabled.

## How It Works

Startup flow:

1. Load `.env` from the workspace root.
2. Read `MIKROTIK_USER` as the target RouterOS user.
3. If `MIKROTIK_API_PASSWORDLESS_ENABLED=true`, require SSH key bootstrap settings.
4. Generate a fresh alphanumeric API password in memory.
5. Connect to the router over SSH using Paramiko and `MIKROTIK_SCP_*` settings.
6. Run `/user set [find where name=<user>] password=<generated-password>`.
7. Create the RouterOS API client with the generated password.

The generated password is not written back to `.env`.

## Required Environment

Static password mode:

```env
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
```

Passwordless startup mode:

```env
MIKROTIK_USER=admin
MIKROTIK_API_PASSWORDLESS_ENABLED=true
MIKROTIK_API_PASSWORDLESS_LENGTH=32

MIKROTIK_SCP_USER=admin
MIKROTIK_SCP_PRIVATE_KEY=certs/router-key
MIKROTIK_SCP_KEY_PASSPHRASE=
```

Common transport settings:

```env
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=true
MIKROTIK_SCP_HOST=
MIKROTIK_SCP_PORT=22
MIKROTIK_SCP_TIMEOUT=30.0
```

## Environment Reference

- `MIKROTIK_API_PASSWORDLESS_ENABLED`: enables startup password rotation. Default: `false`.
- `MIKROTIK_API_PASSWORDLESS_LENGTH`: generated API password length. Default: `32`.
- `MIKROTIK_USER`: RouterOS user whose password is rotated and then used for API login.
- `MIKROTIK_SCP_USER`: SSH bootstrap username. Falls back to `MIKROTIK_USER`.
- `MIKROTIK_SCP_PRIVATE_KEY`: SSH private key path. Required in passwordless mode.
- `MIKROTIK_SCP_KEY_PASSPHRASE`: optional SSH private key passphrase.
- `MIKROTIK_SCP_HOST`: optional SSH host override. Defaults to the router host argument.
- `MIKROTIK_SCP_PORT`: optional SSH port override. Default: `22`.
- `MIKROTIK_SCP_TIMEOUT`: optional SSH timeout in seconds. Default: `30.0`.

`MIKROTIK_PASSWORD` is not required when passwordless startup mode is enabled.

## Current Assumptions

- The same RouterOS user is used for both SSH bootstrap and API login.
- Passwordless mode currently requires SSH key auth.
- If startup rotation fails, MCP startup fails.
- Generated passwords are conservative alphanumeric values to avoid RouterOS CLI quoting problems during non-interactive SSH execution.

## Healthcheck Behavior

`healthcheck` reports three relevant components:

1. `api`: RouterOS API login and identity lookup.
2. `scp`: SSH/SFTP connectivity using the configured bootstrap settings.
3. `passwordless`: readiness of the passwordless startup path.

When passwordless mode is enabled, the `passwordless` check runs a harmless SSH CLI command:

```text
/user print count-only where name=<MIKROTIK_USER>
```

This verifies:

- SSH key authentication works.
- Remote command execution works.
- The target RouterOS user exists.

This check does not change the password.

## Failure Modes

Startup can fail in passwordless mode when:

- `MIKROTIK_SCP_PRIVATE_KEY` is missing.
- SSH key authentication fails.
- The router is unreachable over SSH.
- RouterOS rejects the password change command.
- The target user does not exist.

Healthcheck can surface passwordless-specific failures as `passwordless.*` status codes without mutating router state.

## Operational Notes

- Both startup rotation and passwordless healthcheck use Paramiko, not a system `ssh` subprocess.
- The rotated password is process-local. Restarting the MCP server rotates a new password again.
- If you enable passwordless mode, keep the SSH private key available to the local process that launches the MCP server.
