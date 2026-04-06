# Copyright 2026 Timo Reunanen <timo@reunanen.eu>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .app import create_app
from .client import RouterOSClient
from .server_helpers import parse_bool, workspace_root


def load_settings(host: str) -> RouterOSClient:
    load_dotenv(workspace_root() / ".env")

    username = os.getenv("MIKROTIK_USER")
    password = os.getenv("MIKROTIK_PASSWORD")
    if not username or not password:
        raise RuntimeError("MIKROTIK_USER and MIKROTIK_PASSWORD must be set before starting the MCP server")

    use_ssl = parse_bool(os.getenv("MIKROTIK_API_SSL"), default=True)
    tls_verify = parse_bool(os.getenv("MIKROTIK_TLS_VERIFY"), default=True)
    port = int(os.getenv("MIKROTIK_API_PORT") or (8729 if use_ssl else 8728))

    return RouterOSClient(
        host,
        username,
        password,
        port=port,
        use_ssl=use_ssl,
        tls_verify=tls_verify,
    )


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        raise SystemExit("Usage: python tools/mikrotik/main.py <host>")

    client = load_settings(args[0])
    try:
        create_app(client).run(transport="stdio")
    finally:
        client.close()
