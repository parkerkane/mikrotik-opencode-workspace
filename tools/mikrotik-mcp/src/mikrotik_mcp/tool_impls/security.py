from __future__ import annotations

from typing import Any

from ..client import RouterOSClient
from ..server_helpers import (
    build_equality_queries,
    normalize_firewall_table,
    normalize_move_destination,
    normalize_required_string,
    print_records,
    require_attributes,
)


def firewall_filter_list_impl(
    client: RouterOSClient,
    *,
    chain: str | None = None,
    action: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(chain=chain, action=action, disabled=disabled)
    return print_records(client, menu="/ip/firewall/filter", queries=queries or None)


def firewall_filter_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/ip/firewall/filter", attrs=require_attributes(attributes))


def firewall_filter_set_impl(
    client: RouterOSClient,
    *,
    item_id: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.set("/ip/firewall/filter", item_id, attrs=require_attributes(attributes))


def firewall_filter_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/ip/firewall/filter", item_id)


def firewall_nat_list_impl(
    client: RouterOSClient,
    *,
    chain: str | None = None,
    action: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(chain=chain, action=action, disabled=disabled)
    return print_records(client, menu="/ip/firewall/nat", queries=queries or None)


def firewall_nat_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/ip/firewall/nat", attrs=require_attributes(attributes))


def firewall_nat_set_impl(
    client: RouterOSClient,
    *,
    item_id: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.set("/ip/firewall/nat", item_id, attrs=require_attributes(attributes))


def firewall_nat_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/ip/firewall/nat", item_id)


def firewall_rule_move_impl(
    client: RouterOSClient,
    *,
    table: str,
    item_id: str,
    destination: str,
) -> dict[str, str] | dict[str, bool]:
    normalized_table = normalize_firewall_table(table)
    return client.run(
        f"/ip/firewall/{normalized_table}/move",
        attrs={".id": normalize_required_string(item_id, field_name="item_id"), "destination": normalize_move_destination(destination)},
    )


def firewall_address_list_list_impl(
    client: RouterOSClient,
    *,
    list_name: str | None = None,
    address: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(address=address, disabled=disabled, **{"list": list_name})
    return print_records(client, menu="/ip/firewall/address-list", queries=queries or None)


def firewall_address_list_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/ip/firewall/address-list", attrs=require_attributes(attributes))


def firewall_address_list_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/ip/firewall/address-list", item_id)
