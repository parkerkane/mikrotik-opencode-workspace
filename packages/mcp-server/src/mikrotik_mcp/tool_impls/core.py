from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..client import RouterOSClient
from ..filters import apply_jq_filter
from ..server_helpers import build_equality_queries, print_records, print_single_record, require_exactly_one_locator


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
