from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..client import RouterOSClient
from ..filters import apply_jq_filter
from ..server_helpers import (
    build_equality_queries,
    normalize_required_string,
    print_records,
    print_single_record,
    require_exactly_one_locator,
)


def resource_print_impl(
    client: RouterOSClient,
    *,
    menu: str,
    proplist: Sequence[str] | None = None,
    queries: Sequence[str] | None = None,
    attributes: dict[str, Any] | None = None,
    jq_filter: str | None = None,
) -> Any:
    items = print_records(client, menu=menu, proplist=proplist, queries=queries, attributes=attributes)
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


def resource_listen_impl(
    client: RouterOSClient,
    *,
    menu: str,
    proplist: Sequence[str] | None = None,
    queries: Sequence[str] | None = None,
    attributes: dict[str, Any] | None = None,
    tag: str | None = None,
    max_events: int = 10,
) -> dict[str, Any]:
    with client.isolated() as isolated_client:
        result = isolated_client.listen(
            menu,
            proplist=list(proplist) if proplist is not None else None,
            queries=list(queries) if queries is not None else None,
            attrs=attributes,
            tag=tag,
            max_events=max_events,
        )
    return {
        "tag": result.tag,
        "events": result.records,
        "done": result.done or None,
        "traps": result.traps,
        "empty": result.empty,
        "cancelled": result.cancelled,
        "limit_reached": result.limit_reached,
        "cancel_done": result.cancel_done or None,
    }


def command_cancel_impl(
    client: RouterOSClient,
    *,
    tag: str,
) -> dict[str, str] | dict[str, bool]:
    normalized_tag = normalize_required_string(tag, field_name="tag")
    result = client.cancel(normalized_tag)
    return {"tag": normalized_tag, **result}


def tool_ping_impl(
    client: RouterOSClient,
    *,
    address: str,
    count: int = 4,
    interval: str | None = None,
    interface: str | None = None,
    packet_size: int | None = None,
) -> list[dict[str, str]]:
    normalized_address = normalize_required_string(address, field_name="address")
    if count < 1:
        raise ValueError("count must be at least 1")

    attributes: dict[str, Any] = {
        "address": normalized_address,
        "count": count,
    }
    if interval is not None:
        attributes["interval"] = normalize_required_string(interval, field_name="interval")
    if interface is not None:
        attributes["interface"] = normalize_required_string(interface, field_name="interface")
    if packet_size is not None:
        if packet_size < 1:
            raise ValueError("packet_size must be at least 1")
        attributes["size"] = packet_size

    with client.isolated() as isolated_client:
        result = isolated_client.run("/tool/ping", attrs=attributes)

    if isinstance(result, list):
        return result
    return []


def tool_traceroute_impl(
    client: RouterOSClient,
    *,
    address: str,
    count: int = 3,
    max_hops: int = 30,
    interval: str | None = None,
    interface: str | None = None,
    packet_size: int | None = None,
) -> list[dict[str, str]]:
    normalized_address = normalize_required_string(address, field_name="address")
    if count < 1:
        raise ValueError("count must be at least 1")
    if max_hops < 1:
        raise ValueError("max_hops must be at least 1")

    attributes: dict[str, Any] = {
        "address": normalized_address,
        "count": count,
        "max-hops": max_hops,
    }
    if interval is not None:
        attributes["interval"] = normalize_required_string(interval, field_name="interval")
    if interface is not None:
        attributes["interface"] = normalize_required_string(interface, field_name="interface")
    if packet_size is not None:
        if packet_size < 1:
            raise ValueError("packet_size must be at least 1")
        attributes["size"] = packet_size

    with client.isolated() as isolated_client:
        result = isolated_client.run("/tool/traceroute", attrs=attributes)

    if isinstance(result, list):
        return result
    return []


def dns_resolve_impl(
    client: RouterOSClient,
    *,
    name: str,
    server: str | None = None,
) -> dict[str, str]:
    normalized_name = normalize_required_string(name, field_name="name")

    attributes: dict[str, Any] = {"domain-name": normalized_name}
    if server is not None:
        attributes["server"] = normalize_required_string(server, field_name="server")

    with client.isolated() as isolated_client:
        result = isolated_client.run("/resolve", attrs=attributes)

    if not isinstance(result, dict):
        raise ValueError("RouterOS resolve command did not return a single result")

    address = result.get("ret") or result.get("address")
    if not address:
        raise ValueError("RouterOS resolve command did not return an address")

    resolved = {"name": normalized_name, "address": address}
    if server is not None:
        resolved["server"] = attributes["server"]
    return resolved


def interface_monitor_impl(
    client: RouterOSClient,
    *,
    name: str,
) -> dict[str, str]:
    normalized_name = normalize_required_string(name, field_name="name")

    with client.isolated() as isolated_client:
        result = isolated_client.run("/interface/monitor-traffic", attrs={"interface": normalized_name, "once": True})

    if isinstance(result, list):
        if not result:
            raise ValueError("No interface monitor result returned")
        return result[0]
    if isinstance(result, dict) and result:
        return result
    raise ValueError("No interface monitor result returned")


def system_resource_get_impl(client: RouterOSClient) -> dict[str, str]:
    return print_single_record(client, menu="/system/resource", entity_name="system resource")


def system_identity_get_impl(client: RouterOSClient) -> dict[str, str]:
    return print_single_record(client, menu="/system/identity", entity_name="system identity")


def system_clock_get_impl(client: RouterOSClient) -> dict[str, str]:
    return print_single_record(client, menu="/system/clock", entity_name="system clock")


def interface_list_impl(
    client: RouterOSClient,
    *,
    running_only: bool = False,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(disabled=disabled)
    if running_only:
        queries.append("running=true")
    return print_records(client, menu="/interface", queries=queries or None)


def interface_get_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    item_id: str | None = None,
) -> dict[str, str]:
    field, value = require_exactly_one_locator("interface", name=name, item_id=item_id)
    query_field = ".id" if field == "item_id" else "name"
    return print_single_record(client, menu="/interface", queries=[f"{query_field}={value}"], entity_name="interface")


def ip_address_list_impl(
    client: RouterOSClient,
    *,
    interface: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(interface=interface, disabled=disabled)
    return print_records(client, menu="/ip/address", queries=queries or None)


def ip_address_get_impl(
    client: RouterOSClient,
    *,
    address: str | None = None,
    item_id: str | None = None,
) -> dict[str, str]:
    field, value = require_exactly_one_locator("IP address", address=address, item_id=item_id)
    query_field = ".id" if field == "item_id" else "address"
    return print_single_record(client, menu="/ip/address", queries=[f"{query_field}={value}"], entity_name="IP address")


def ip_route_list_impl(
    client: RouterOSClient,
    *,
    dst_address: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(**{"dst-address": dst_address, "disabled": disabled})
    return print_records(client, menu="/ip/route", queries=queries or None)


def ip_route_get_impl(
    client: RouterOSClient,
    *,
    dst_address: str | None = None,
    item_id: str | None = None,
) -> dict[str, str]:
    field, value = require_exactly_one_locator("IP route", dst_address=dst_address, item_id=item_id)
    query_field = ".id" if field == "item_id" else "dst-address"
    return print_single_record(client, menu="/ip/route", queries=[f"{query_field}={value}"], entity_name="IP route")


def dhcp_lease_list_impl(
    client: RouterOSClient,
    *,
    address: str | None = None,
    mac_address: str | None = None,
    active_only: bool = False,
) -> list[dict[str, str]]:
    queries = build_equality_queries(address=address, **{"mac-address": mac_address})
    if active_only:
        queries.append("status=bound")
    return print_records(client, menu="/ip/dhcp-server/lease", queries=queries or None)


def dhcp_server_list_impl(client: RouterOSClient) -> list[dict[str, str]]:
    return print_records(client, menu="/ip/dhcp-server")


def dhcp_network_list_impl(client: RouterOSClient) -> list[dict[str, str]]:
    return print_records(client, menu="/ip/dhcp-server/network")


def dns_get_impl(client: RouterOSClient) -> dict[str, str]:
    return print_single_record(client, menu="/ip/dns", entity_name="DNS settings")


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
