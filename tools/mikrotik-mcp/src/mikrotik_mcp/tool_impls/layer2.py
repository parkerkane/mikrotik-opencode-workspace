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

from typing import Any

from ..client import RouterOSClient
from ..server_helpers import build_equality_queries, print_records, require_attributes, require_exactly_one_locator, print_single_record


def bridge_list_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(name=name, disabled=disabled)
    return print_records(client, menu="/interface/bridge", queries=queries or None)


def bridge_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/bridge", attrs=require_attributes(attributes))


def bridge_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/interface/bridge", item_id)


def bridge_port_list_impl(
    client: RouterOSClient,
    *,
    bridge: str | None = None,
    interface: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(bridge=bridge, interface=interface, disabled=disabled)
    return print_records(client, menu="/interface/bridge/port", queries=queries or None)


def bridge_port_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/bridge/port", attrs=require_attributes(attributes))


def bridge_port_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/interface/bridge/port", item_id)


def bridge_vlan_list_impl(
    client: RouterOSClient,
    *,
    bridge: str | None = None,
    vlan_ids: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(bridge=bridge, **{"vlan-ids": vlan_ids, "disabled": disabled})
    return print_records(client, menu="/interface/bridge/vlan", queries=queries or None)


def bridge_vlan_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/bridge/vlan", attrs=require_attributes(attributes))


def bridge_vlan_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/interface/bridge/vlan", item_id)


def vlan_list_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    interface: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(name=name, interface=interface, disabled=disabled)
    return print_records(client, menu="/interface/vlan", queries=queries or None)


def vlan_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/vlan", attrs=require_attributes(attributes))


def vlan_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/interface/vlan", item_id)
