## Custom CA Certificates

Place local `.pem`, `.crt`, or `.cer` CA certificates for RouterOS API TLS verification in this directory.

Rules:
- `.pem`, `.crt`, and `.cer` files in `certs/` are loaded into the MCP TLS trust store.
- Files whose names end with `.disabled` are ignored.
- Keep only CA certificates here, not private keys.
- This repository tracks only `certs/README.md`; other files in this directory stay untracked.

Examples:
- `router-ca.pem`
- `lab-root.crt`
- `old-ca.pem.disabled`
