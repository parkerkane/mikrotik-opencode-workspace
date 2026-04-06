from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import RouterOSClient
from .filters import apply_jq_filter


def resource_print_impl(
    client: RouterOSClient,
    *,
    menu: str,
    proplist: Sequence[str] | None = None,
    queries: Sequence[str] | None = None,
    attributes: dict[str, Any] | None = None,
    jq_filter: str | None = None,
) -> Any:
    items = client.print(
        menu,
        proplist=list(proplist) if proplist is not None else None,
        queries=list(queries) if queries is not None else None,
        attrs=attributes,
    )
    if jq_filter:
        return apply_jq_filter(items, jq_filter)
    return items


def create_app(client: RouterOSClient) -> FastMCP:
    app = FastMCP("mikrotik")

    @app.tool(
        description="Run a generic RouterOS print command and optionally apply jq to the normalized array response.",
    )
    def resource_print(
        menu: str,
        proplist: list[str] | None = None,
        queries: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
        jq_filter: str | None = None,
    ) -> Any:
        return resource_print_impl(
            client,
            menu=menu,
            proplist=proplist,
            queries=queries,
            attributes=attributes,
            jq_filter=jq_filter,
        )

    return app


def load_settings(host: str) -> RouterOSClient:
    workspace_root = Path(__file__).resolve().parents[4]
    load_dotenv(workspace_root / ".env")

    username = os.getenv("MIKROTIK_USER")
    password = os.getenv("MIKROTIK_PASSWORD")
    if not username or not password:
        raise RuntimeError("MIKROTIK_USER and MIKROTIK_PASSWORD must be set before starting the MCP server")

    use_ssl = _parse_bool(os.getenv("MIKROTIK_API_SSL"), default=True)
    tls_verify = _parse_bool(os.getenv("MIKROTIK_TLS_VERIFY"), default=True)
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
        raise SystemExit("Usage: python packages/mcp-server/src/main.py <host>")

    client = load_settings(args[0])
    client.open()
    try:
        create_app(client).run(transport="stdio")
    finally:
        client.close()


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
