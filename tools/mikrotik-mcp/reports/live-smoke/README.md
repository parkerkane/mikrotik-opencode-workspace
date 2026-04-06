# Live Smoke Reports

This directory stores generated live smoke reports for read-only MikroTik MCP commands.

Usage from the repository root:

```bash
python tools/mikrotik-mcp/scripts/live_smoke_read_only.py <router-host>
```

The runner writes two files per execution:

- `<timestamp>-<host>-read-only.json`
- `<timestamp>-<host>-read-only.md`

The JSON report is intended for automation. The Markdown report is intended for quick review and commit history.

Reports are intentionally summarized. They record pass/fail status, durations, and shape metadata without storing sensitive values like PPP passwords, WireGuard private keys, or router file contents.
