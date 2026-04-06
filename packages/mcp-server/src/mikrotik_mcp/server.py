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


def _stringify_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _print_records(
    client: RouterOSClient,
    *,
    menu: str,
    proplist: Sequence[str] | None = None,
    queries: Sequence[str] | None = None,
    attributes: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    return client.print(
        menu,
        proplist=list(proplist) if proplist is not None else None,
        queries=list(queries) if queries is not None else None,
        attrs=attributes,
    )


def _print_single_record(
    client: RouterOSClient,
    *,
    menu: str,
    queries: Sequence[str] | None = None,
    attributes: dict[str, Any] | None = None,
    entity_name: str,
) -> dict[str, str]:
    items = _print_records(client, menu=menu, queries=queries, attributes=attributes)
    if not items:
        raise ValueError(f"No matching {entity_name} found")
    if len(items) > 1:
        raise ValueError(f"Multiple {entity_name} records matched")
    return items[0]


def _build_equality_queries(**filters: Any) -> list[str]:
    return [f"{field}={_stringify_value(value)}" for field, value in filters.items() if value is not None]


def _require_exactly_one_locator(entity_name: str, **locators: str | None) -> tuple[str, str]:
    selected = [(field, value.strip()) for field, value in locators.items() if value is not None and value.strip()]
    if len(selected) != 1:
        options = ", ".join(locators)
        raise ValueError(f"Exactly one {entity_name} locator is required: {options}")
    return selected[0]


def _normalize_generated_name(name: str, *, extension: str, field_name: str = "name") -> str:
    value = name.strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    if value.endswith("/"):
        raise ValueError(f"{field_name} must not end with '/'")
    if value.lower().endswith(extension.lower()):
        value = value[: -len(extension)]
    if not value:
        raise ValueError(f"{field_name} is required")
    return value


def _file_exists_in_directory(file_name: str, directory: str) -> bool:
    normalized_directory = directory.strip().strip("/")
    if not normalized_directory:
        return True
    normalized_name = file_name.strip().strip("/")
    return normalized_name == normalized_directory or normalized_name.startswith(f"{normalized_directory}/")


def resource_print_impl(
    client: RouterOSClient,
    *,
    menu: str,
    proplist: Sequence[str] | None = None,
    queries: Sequence[str] | None = None,
    attributes: dict[str, Any] | None = None,
    jq_filter: str | None = None,
) -> Any:
    items = _print_records(client, menu=menu, proplist=proplist, queries=queries, attributes=attributes)
    if jq_filter:
        return apply_jq_filter(items, jq_filter)
    return items


def resource_add_impl(
    client: RouterOSClient,
    *,
    menu: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add(menu, attrs=attributes)


def resource_set_impl(
    client: RouterOSClient,
    *,
    menu: str,
    item_id: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.set(menu, item_id, attrs=attributes)


def resource_remove_impl(
    client: RouterOSClient,
    *,
    menu: str,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove(menu, item_id)


def command_run_impl(
    client: RouterOSClient,
    *,
    command: str,
    attributes: dict[str, Any] | None = None,
    queries: Sequence[str] | None = None,
) -> Any:
    return client.run(
        command,
        attrs=attributes,
        queries=list(queries) if queries is not None else None,
    )


def system_resource_get_impl(client: RouterOSClient) -> dict[str, str]:
    return _print_single_record(client, menu="/system/resource", entity_name="system resource")


def system_identity_get_impl(client: RouterOSClient) -> dict[str, str]:
    return _print_single_record(client, menu="/system/identity", entity_name="system identity")


def system_clock_get_impl(client: RouterOSClient) -> dict[str, str]:
    return _print_single_record(client, menu="/system/clock", entity_name="system clock")


def interface_list_impl(
    client: RouterOSClient,
    *,
    running_only: bool = False,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(disabled=disabled)
    if running_only:
        queries.append("running=true")
    return _print_records(client, menu="/interface", queries=queries or None)


def interface_get_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    item_id: str | None = None,
) -> dict[str, str]:
    field, value = _require_exactly_one_locator("interface", name=name, item_id=item_id)
    query_field = ".id" if field == "item_id" else "name"
    return _print_single_record(client, menu="/interface", queries=[f"{query_field}={value}"], entity_name="interface")


def ip_address_list_impl(
    client: RouterOSClient,
    *,
    interface: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(interface=interface, disabled=disabled)
    return _print_records(client, menu="/ip/address", queries=queries or None)


def ip_address_get_impl(
    client: RouterOSClient,
    *,
    address: str | None = None,
    item_id: str | None = None,
) -> dict[str, str]:
    field, value = _require_exactly_one_locator("IP address", address=address, item_id=item_id)
    query_field = ".id" if field == "item_id" else "address"
    return _print_single_record(client, menu="/ip/address", queries=[f"{query_field}={value}"], entity_name="IP address")


def ip_route_list_impl(
    client: RouterOSClient,
    *,
    dst_address: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(**{"dst-address": dst_address, "disabled": disabled})
    return _print_records(client, menu="/ip/route", queries=queries or None)


def ip_route_get_impl(
    client: RouterOSClient,
    *,
    dst_address: str | None = None,
    item_id: str | None = None,
) -> dict[str, str]:
    field, value = _require_exactly_one_locator("IP route", dst_address=dst_address, item_id=item_id)
    query_field = ".id" if field == "item_id" else "dst-address"
    return _print_single_record(client, menu="/ip/route", queries=[f"{query_field}={value}"], entity_name="IP route")


def dhcp_lease_list_impl(
    client: RouterOSClient,
    *,
    address: str | None = None,
    mac_address: str | None = None,
    active_only: bool = False,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(address=address, **{"mac-address": mac_address})
    if active_only:
        queries.append("status=bound")
    return _print_records(client, menu="/ip/dhcp-server/lease", queries=queries or None)


def dhcp_server_list_impl(client: RouterOSClient) -> list[dict[str, str]]:
    return _print_records(client, menu="/ip/dhcp-server")


def dhcp_network_list_impl(client: RouterOSClient) -> list[dict[str, str]]:
    return _print_records(client, menu="/ip/dhcp-server/network")


def dns_get_impl(client: RouterOSClient) -> dict[str, str]:
    return _print_single_record(client, menu="/ip/dns", entity_name="DNS settings")


def dns_set_impl(
    client: RouterOSClient,
    *,
    servers: Sequence[str] | None = None,
    allow_remote_requests: bool | None = None,
    cache_size: str | None = None,
) -> dict[str, str] | dict[str, bool]:
    attributes: dict[str, Any] = {}
    if servers is not None:
        cleaned_servers = [server.strip() for server in servers if server.strip()]
        if not cleaned_servers:
            raise ValueError("servers must include at least one non-empty address")
        attributes["servers"] = ",".join(cleaned_servers)
    if allow_remote_requests is not None:
        attributes["allow-remote-requests"] = allow_remote_requests
    if cache_size is not None:
        if not cache_size.strip():
            raise ValueError("cache_size must not be empty")
        attributes["cache-size"] = cache_size.strip()
    if not attributes:
        raise ValueError("At least one DNS setting must be provided")
    return client.run("/ip/dns/set", attrs=attributes)


def file_list_impl(
    client: RouterOSClient,
    *,
    directory: str | None = None,
    name: str | None = None,
    file_type: str | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(name=name, type=file_type)
    items = _print_records(client, menu="/file", queries=queries or None)
    if name is not None:
        items = [item for item in items if item.get("name") == name]
    if file_type is not None:
        items = [item for item in items if item.get("type") == file_type]
    if directory is None:
        return items

    normalized_directory = directory.strip()
    if not normalized_directory:
        raise ValueError("directory must not be empty")
    return [item for item in items if _file_exists_in_directory(item.get("name", ""), normalized_directory)]


def system_backup_save_impl(
    client: RouterOSClient,
    *,
    name: str,
) -> dict[str, str | bool]:
    normalized_name = _normalize_generated_name(name, extension=".backup")
    client.run("/system/backup/save", attrs={"name": normalized_name})
    return {
        "success": True,
        "name": normalized_name,
        "path": f"{normalized_name}.backup",
    }


def system_export_impl(
    client: RouterOSClient,
    *,
    name: str,
    include_sensitive: bool = False,
    compact: bool = False,
) -> dict[str, str | bool]:
    normalized_name = _normalize_generated_name(name, extension=".rsc")
    attributes: dict[str, Any] = {"file": normalized_name}
    if include_sensitive:
        attributes["show-sensitive"] = ""
    if compact:
        attributes["compact"] = ""
    client.run("/export", attrs=attributes)
    return {
        "success": True,
        "name": normalized_name,
        "path": f"{normalized_name}.rsc",
        "include_sensitive": include_sensitive,
        "compact": compact,
    }


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

    @app.tool(description="Run a generic RouterOS add command for a menu path.")
    def resource_add(
        menu: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return resource_add_impl(client, menu=menu, attributes=attributes)

    @app.tool(description="Run a generic RouterOS set command for a menu path and item id.")
    def resource_set(
        menu: str,
        item_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return resource_set_impl(client, menu=menu, item_id=item_id, attributes=attributes)

    @app.tool(description="Run a generic RouterOS remove command for a menu path and item id.")
    def resource_remove(
        menu: str,
        item_id: str,
    ) -> dict[str, str] | dict[str, bool]:
        return resource_remove_impl(client, menu=menu, item_id=item_id)

    @app.tool(description="Run a generic RouterOS command path and return normalized output.")
    def command_run(
        command: str,
        attributes: dict[str, Any] | None = None,
        queries: list[str] | None = None,
    ) -> Any:
        return command_run_impl(client, command=command, attributes=attributes, queries=queries)

    @app.tool(description="Get RouterOS system resource details.")
    def system_resource_get() -> dict[str, str]:
        return system_resource_get_impl(client)

    @app.tool(description="Get the RouterOS system identity.")
    def system_identity_get() -> dict[str, str]:
        return system_identity_get_impl(client)

    @app.tool(description="Get the RouterOS system clock settings.")
    def system_clock_get() -> dict[str, str]:
        return system_clock_get_impl(client)

    @app.tool(description="List network interfaces with optional status filters.")
    def interface_list(
        running_only: bool = False,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return interface_list_impl(client, running_only=running_only, disabled=disabled)

    @app.tool(description="Get one interface by name or RouterOS item id.")
    def interface_get(
        name: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, str]:
        return interface_get_impl(client, name=name, item_id=item_id)

    @app.tool(description="List IP addresses with optional interface and disabled filters.")
    def ip_address_list(
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return ip_address_list_impl(client, interface=interface, disabled=disabled)

    @app.tool(description="Get one IP address by address or RouterOS item id.")
    def ip_address_get(
        address: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, str]:
        return ip_address_get_impl(client, address=address, item_id=item_id)

    @app.tool(description="List IP routes with optional destination and disabled filters.")
    def ip_route_list(
        dst_address: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return ip_route_list_impl(client, dst_address=dst_address, disabled=disabled)

    @app.tool(description="Get one IP route by destination or RouterOS item id.")
    def ip_route_get(
        dst_address: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, str]:
        return ip_route_get_impl(client, dst_address=dst_address, item_id=item_id)

    @app.tool(description="List DHCP leases with optional address, MAC, and active filters.")
    def dhcp_lease_list(
        address: str | None = None,
        mac_address: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, str]]:
        return dhcp_lease_list_impl(client, address=address, mac_address=mac_address, active_only=active_only)

    @app.tool(description="List configured DHCP servers.")
    def dhcp_server_list() -> list[dict[str, str]]:
        return dhcp_server_list_impl(client)

    @app.tool(description="List configured DHCP networks.")
    def dhcp_network_list() -> list[dict[str, str]]:
        return dhcp_network_list_impl(client)

    @app.tool(description="Get RouterOS DNS settings.")
    def dns_get() -> dict[str, str]:
        return dns_get_impl(client)

    @app.tool(description="Update RouterOS DNS settings.")
    def dns_set(
        servers: list[str] | None = None,
        allow_remote_requests: bool | None = None,
        cache_size: str | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return dns_set_impl(
            client,
            servers=servers,
            allow_remote_requests=allow_remote_requests,
            cache_size=cache_size,
        )

    @app.tool(description="List router files with optional directory, name, and type filters.")
    def file_list(
        directory: str | None = None,
        name: str | None = None,
        file_type: str | None = None,
    ) -> list[dict[str, str]]:
        return file_list_impl(client, directory=directory, name=name, file_type=file_type)

    @app.tool(description="Create a RouterOS backup file on the router.")
    def system_backup_save(name: str) -> dict[str, str | bool]:
        return system_backup_save_impl(client, name=name)

    @app.tool(description="Export RouterOS configuration to an .rsc file on the router.")
    def system_export(
        name: str,
        include_sensitive: bool = False,
        compact: bool = False,
    ) -> dict[str, str | bool]:
        return system_export_impl(client, name=name, include_sensitive=include_sensitive, compact=compact)

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
