from __future__ import annotations

from typing import Any

from ..client import RouterOSClient
from ..server_helpers import build_equality_queries, print_records, require_attribute_fields


def ppp_active_list_impl(
    client: RouterOSClient,
    *,
    service: str | None = None,
    name: str | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(service=service, name=name)
    return print_records(client, menu="/ppp/active", queries=queries or None)


def ppp_secret_list_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    service: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(name=name, service=service, disabled=disabled)
    return print_records(client, menu="/ppp/secret", queries=queries or None)


def ppp_secret_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    normalized = require_attribute_fields(attributes, required_fields=("name", "password"))
    return client.add("/ppp/secret", attrs=normalized)


def ppp_secret_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/ppp/secret", item_id)


def wireguard_interface_list_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(name=name, disabled=disabled)
    return print_records(client, menu="/interface/wireguard", queries=queries or None)


def wireguard_interface_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    normalized = require_attribute_fields(attributes, required_fields=("name",))
    return client.add("/interface/wireguard", attrs=normalized)


def wireguard_peer_list_impl(
    client: RouterOSClient,
    *,
    interface: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(interface=interface, disabled=disabled)
    return print_records(client, menu="/interface/wireguard/peers", queries=queries or None)


def wireguard_peer_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    normalized = require_attribute_fields(attributes, required_fields=("interface", "public-key"))
    return client.add("/interface/wireguard/peers", attrs=normalized)


def wireguard_peer_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/interface/wireguard/peers", item_id)
