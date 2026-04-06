from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import RouterOSClient
from .downloads import FTPFileDownloader, FileDownloader, RouterFileDownloadError, load_file_transfer_settings
from .filters import apply_jq_filter


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


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


def _normalize_local_directory(local_dir: str | None) -> Path:
    workspace_root = _workspace_root()
    if local_dir is None:
        return workspace_root / "backups"
    value = local_dir.strip()
    if not value:
        raise ValueError("local_dir must not be empty")
    path = Path(value)
    if path.is_absolute():
        return path
    return workspace_root / path


def _normalize_router_file_path(router_path: str) -> str:
    value = router_path.strip().strip("/")
    if not value:
        raise ValueError("router_path is required")
    if value.endswith("/"):
        raise ValueError("router_path must not end with '/'")
    return value


def _require_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    if not attributes:
        raise ValueError("attributes are required")
    return attributes


def _normalize_firewall_table(table: str) -> str:
    value = table.strip().lower()
    if value not in {"filter", "nat"}:
        raise ValueError("table must be either 'filter' or 'nat'")
    return value


def _normalize_move_destination(destination: str) -> str:
    value = destination.strip()
    if not value:
        raise ValueError("destination is required")
    return value


def _normalize_required_string(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _safe_name_component(value: str, *, default: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.strip().lower())
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return collapsed or default


def _unique_local_path(directory: Path, file_name: str) -> Path:
    candidate = directory / file_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        candidate = directory / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _build_backup_paths(
    client: RouterOSClient,
    *,
    name_prefix: str | None,
    local_dir: str | None,
) -> dict[str, str | Path]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    prefix = _safe_name_component(name_prefix or "backup", default="backup")
    router_name = f"backups/{prefix}-{timestamp}"
    router_backup_path = f"{router_name}.backup"
    router_export_path = f"{router_name}.rsc"
    local_directory = _normalize_local_directory(local_dir)
    router_slug = _safe_name_component(client.host, default="router")

    return {
        "created_at": timestamp,
        "router_backup_path": router_backup_path,
        "router_export_path": router_export_path,
        "local_backup_path": _unique_local_path(local_directory, f"{router_slug}-{prefix}-{timestamp}.backup"),
        "local_export_path": _unique_local_path(local_directory, f"{router_slug}-{prefix}-{timestamp}.rsc"),
    }


def _ensure_router_backup_directory(client: RouterOSClient) -> None:
    matches = file_list_impl(client, name="backups")
    if any(item.get("name") == "backups" and item.get("type") == "directory" for item in matches):
        return
    client.add("/file", attrs={"name": "backups", "type": "directory"})


def _download_router_file(
    client: RouterOSClient,
    *,
    router_path: str,
    local_path: str | Path | None = None,
    downloader: FileDownloader | None = None,
) -> dict[str, str | bool]:
    normalized_router_path = _normalize_router_file_path(router_path)
    resolved_downloader = downloader
    if resolved_downloader is None:
        settings = load_file_transfer_settings(client.host)
        resolved_downloader = FTPFileDownloader(settings)

    if local_path is None:
        target_path = _unique_local_path(_workspace_root() / "backups", Path(normalized_router_path).name)
    else:
        raw_target_path = Path(local_path)
        target_path = raw_target_path if raw_target_path.is_absolute() else _workspace_root() / raw_target_path
    resolved_downloader.download_file(normalized_router_path, target_path)
    return {
        "success": True,
        "router_path": normalized_router_path,
        "local_path": str(target_path),
    }


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


def bridge_list_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(name=name, disabled=disabled)
    return _print_records(client, menu="/interface/bridge", queries=queries or None)


def bridge_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/bridge", attrs=_require_attributes(attributes))


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
    queries = _build_equality_queries(bridge=bridge, interface=interface, disabled=disabled)
    return _print_records(client, menu="/interface/bridge/port", queries=queries or None)


def bridge_port_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/bridge/port", attrs=_require_attributes(attributes))


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
    queries = _build_equality_queries(bridge=bridge, **{"vlan-ids": vlan_ids, "disabled": disabled})
    return _print_records(client, menu="/interface/bridge/vlan", queries=queries or None)


def bridge_vlan_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/bridge/vlan", attrs=_require_attributes(attributes))


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
    queries = _build_equality_queries(name=name, interface=interface, disabled=disabled)
    return _print_records(client, menu="/interface/vlan", queries=queries or None)


def vlan_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/interface/vlan", attrs=_require_attributes(attributes))


def vlan_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/interface/vlan", item_id)


def firewall_filter_list_impl(
    client: RouterOSClient,
    *,
    chain: str | None = None,
    action: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(chain=chain, action=action, disabled=disabled)
    return _print_records(client, menu="/ip/firewall/filter", queries=queries or None)


def firewall_filter_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/ip/firewall/filter", attrs=_require_attributes(attributes))


def firewall_filter_set_impl(
    client: RouterOSClient,
    *,
    item_id: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.set("/ip/firewall/filter", item_id, attrs=_require_attributes(attributes))


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
    queries = _build_equality_queries(chain=chain, action=action, disabled=disabled)
    return _print_records(client, menu="/ip/firewall/nat", queries=queries or None)


def firewall_nat_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/ip/firewall/nat", attrs=_require_attributes(attributes))


def firewall_nat_set_impl(
    client: RouterOSClient,
    *,
    item_id: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.set("/ip/firewall/nat", item_id, attrs=_require_attributes(attributes))


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
    normalized_table = _normalize_firewall_table(table)
    return client.run(
        f"/ip/firewall/{normalized_table}/move",
        attrs={".id": _normalize_required_string(item_id, field_name="item_id"), "destination": _normalize_move_destination(destination)},
    )


def firewall_address_list_list_impl(
    client: RouterOSClient,
    *,
    list_name: str | None = None,
    address: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(address=address, disabled=disabled, **{"list": list_name})
    return _print_records(client, menu="/ip/firewall/address-list", queries=queries or None)


def firewall_address_list_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    return client.add("/ip/firewall/address-list", attrs=_require_attributes(attributes))


def firewall_address_list_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/ip/firewall/address-list", item_id)


def _require_attribute_fields(attributes: dict[str, Any] | None, *, required_fields: Sequence[str]) -> dict[str, Any]:
    normalized = _require_attributes(attributes)
    missing = [field for field in required_fields if field not in normalized or not str(normalized[field]).strip()]
    if missing:
        if len(missing) == 1:
            raise ValueError(f"{missing[0]} is required")
        raise ValueError(f"Required attributes are missing: {', '.join(missing)}")
    return normalized


def ppp_active_list_impl(
    client: RouterOSClient,
    *,
    service: str | None = None,
    name: str | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(service=service, name=name)
    return _print_records(client, menu="/ppp/active", queries=queries or None)


def ppp_secret_list_impl(
    client: RouterOSClient,
    *,
    name: str | None = None,
    service: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(name=name, service=service, disabled=disabled)
    return _print_records(client, menu="/ppp/secret", queries=queries or None)


def ppp_secret_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    normalized = _require_attribute_fields(attributes, required_fields=("name", "password"))
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
    queries = _build_equality_queries(name=name, disabled=disabled)
    return _print_records(client, menu="/interface/wireguard", queries=queries or None)


def wireguard_interface_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    normalized = _require_attribute_fields(attributes, required_fields=("name",))
    return client.add("/interface/wireguard", attrs=normalized)


def wireguard_peer_list_impl(
    client: RouterOSClient,
    *,
    interface: str | None = None,
    disabled: bool | None = None,
) -> list[dict[str, str]]:
    queries = _build_equality_queries(interface=interface, disabled=disabled)
    return _print_records(client, menu="/interface/wireguard/peers", queries=queries or None)


def wireguard_peer_add_impl(
    client: RouterOSClient,
    *,
    attributes: dict[str, Any] | None = None,
) -> dict[str, str] | dict[str, bool]:
    normalized = _require_attribute_fields(attributes, required_fields=("interface", "public-key"))
    return client.add("/interface/wireguard/peers", attrs=normalized)


def wireguard_peer_remove_impl(
    client: RouterOSClient,
    *,
    item_id: str,
) -> dict[str, str] | dict[str, bool]:
    return client.remove("/interface/wireguard/peers", item_id)


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


def file_download_impl(
    client: RouterOSClient,
    *,
    router_path: str,
    local_path: str | None = None,
    downloader: FileDownloader | None = None,
) -> dict[str, str | bool]:
    return _download_router_file(client, router_path=router_path, local_path=local_path, downloader=downloader)


def system_backup_collect_impl(
    client: RouterOSClient,
    *,
    name_prefix: str | None = None,
    include_sensitive: bool = False,
    compact: bool = False,
    local_dir: str | None = None,
    downloader: FileDownloader | None = None,
) -> dict[str, str | bool]:
    paths = _build_backup_paths(client, name_prefix=name_prefix, local_dir=local_dir)
    router_backup_path = str(paths["router_backup_path"])
    router_export_path = str(paths["router_export_path"])
    local_backup_path = Path(paths["local_backup_path"])
    local_export_path = Path(paths["local_export_path"])

    _ensure_router_backup_directory(client)
    system_backup_save_impl(client, name=router_backup_path)
    try:
        system_export_impl(client, name=router_export_path, include_sensitive=include_sensitive, compact=compact)
    except Exception as exc:
        raise RuntimeError(
            f"Router backup created at '{router_backup_path}', but export creation failed before downloads started: {exc}"
        ) from exc

    backup_files = file_list_impl(client, directory="backups")
    available_paths = {item.get("name") for item in backup_files}
    missing_paths = [path for path in (router_backup_path, router_export_path) if path not in available_paths]
    if missing_paths:
        raise RuntimeError(f"Expected router backup files were not found: {', '.join(missing_paths)}")

    try:
        _download_router_file(client, router_path=router_backup_path, local_path=local_backup_path, downloader=downloader)
        _download_router_file(client, router_path=router_export_path, local_path=local_export_path, downloader=downloader)
    except RouterFileDownloadError as exc:
        raise RuntimeError(
            "Backup files were created on the router, but local download failed. "
            f"backup_local='{local_backup_path}', export_local='{local_export_path}': {exc}"
        ) from exc

    return {
        "success": True,
        "created_at": str(paths["created_at"]),
        "router_backup_path": router_backup_path,
        "router_export_path": router_export_path,
        "local_backup_path": str(local_backup_path),
        "local_export_path": str(local_export_path),
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

    @app.tool(description="List bridges with optional name and disabled filters.")
    def bridge_list(
        name: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return bridge_list_impl(client, name=name, disabled=disabled)

    @app.tool(description="Create a bridge using RouterOS bridge attributes.")
    def bridge_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return bridge_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a bridge by RouterOS item id.")
    def bridge_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return bridge_remove_impl(client, item_id=item_id)

    @app.tool(description="List bridge ports with optional bridge, interface, and disabled filters.")
    def bridge_port_list(
        bridge: str | None = None,
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return bridge_port_list_impl(client, bridge=bridge, interface=interface, disabled=disabled)

    @app.tool(description="Add a bridge port using RouterOS bridge port attributes.")
    def bridge_port_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return bridge_port_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a bridge port by RouterOS item id.")
    def bridge_port_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return bridge_port_remove_impl(client, item_id=item_id)

    @app.tool(description="List bridge VLAN entries with optional bridge, VLAN ID, and disabled filters.")
    def bridge_vlan_list(
        bridge: str | None = None,
        vlan_ids: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return bridge_vlan_list_impl(client, bridge=bridge, vlan_ids=vlan_ids, disabled=disabled)

    @app.tool(description="Add a bridge VLAN entry using RouterOS bridge VLAN attributes.")
    def bridge_vlan_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return bridge_vlan_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a bridge VLAN entry by RouterOS item id.")
    def bridge_vlan_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return bridge_vlan_remove_impl(client, item_id=item_id)

    @app.tool(description="List VLAN interfaces with optional name, parent interface, and disabled filters.")
    def vlan_list(
        name: str | None = None,
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return vlan_list_impl(client, name=name, interface=interface, disabled=disabled)

    @app.tool(description="Create a VLAN interface using RouterOS VLAN attributes.")
    def vlan_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return vlan_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a VLAN interface by RouterOS item id.")
    def vlan_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return vlan_remove_impl(client, item_id=item_id)

    @app.tool(description="List firewall filter rules with optional chain, action, and disabled filters.")
    def firewall_filter_list(
        chain: str | None = None,
        action: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return firewall_filter_list_impl(client, chain=chain, action=action, disabled=disabled)

    @app.tool(description="Add a firewall filter rule using RouterOS firewall attributes.")
    def firewall_filter_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return firewall_filter_add_impl(client, attributes=attributes)

    @app.tool(description="Update a firewall filter rule by RouterOS item id.")
    def firewall_filter_set(
        item_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return firewall_filter_set_impl(client, item_id=item_id, attributes=attributes)

    @app.tool(description="Remove a firewall filter rule by RouterOS item id.")
    def firewall_filter_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return firewall_filter_remove_impl(client, item_id=item_id)

    @app.tool(description="List firewall NAT rules with optional chain, action, and disabled filters.")
    def firewall_nat_list(
        chain: str | None = None,
        action: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return firewall_nat_list_impl(client, chain=chain, action=action, disabled=disabled)

    @app.tool(description="Add a firewall NAT rule using RouterOS firewall attributes.")
    def firewall_nat_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return firewall_nat_add_impl(client, attributes=attributes)

    @app.tool(description="Update a firewall NAT rule by RouterOS item id.")
    def firewall_nat_set(
        item_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return firewall_nat_set_impl(client, item_id=item_id, attributes=attributes)

    @app.tool(description="Remove a firewall NAT rule by RouterOS item id.")
    def firewall_nat_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return firewall_nat_remove_impl(client, item_id=item_id)

    @app.tool(description="Move a firewall filter or NAT rule to a new destination position or item id.")
    def firewall_rule_move(
        table: str,
        item_id: str,
        destination: str,
    ) -> dict[str, str] | dict[str, bool]:
        return firewall_rule_move_impl(client, table=table, item_id=item_id, destination=destination)

    @app.tool(description="List firewall address-list entries with optional list, address, and disabled filters.")
    def firewall_address_list_list(
        list_name: str | None = None,
        address: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return firewall_address_list_list_impl(client, list_name=list_name, address=address, disabled=disabled)

    @app.tool(description="Add a firewall address-list entry using RouterOS firewall attributes.")
    def firewall_address_list_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return firewall_address_list_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a firewall address-list entry by RouterOS item id.")
    def firewall_address_list_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return firewall_address_list_remove_impl(client, item_id=item_id)

    @app.tool(description="List active PPP sessions with optional service and name filters.")
    def ppp_active_list(
        service: str | None = None,
        name: str | None = None,
    ) -> list[dict[str, str]]:
        return ppp_active_list_impl(client, service=service, name=name)

    @app.tool(description="List PPP secrets with optional name, service, and disabled filters.")
    def ppp_secret_list(
        name: str | None = None,
        service: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return ppp_secret_list_impl(client, name=name, service=service, disabled=disabled)

    @app.tool(description="Create a PPP secret using RouterOS PPP secret attributes.")
    def ppp_secret_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return ppp_secret_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a PPP secret by RouterOS item id.")
    def ppp_secret_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return ppp_secret_remove_impl(client, item_id=item_id)

    @app.tool(description="List WireGuard interfaces with optional name and disabled filters.")
    def wireguard_interface_list(
        name: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return wireguard_interface_list_impl(client, name=name, disabled=disabled)

    @app.tool(description="Create a WireGuard interface using RouterOS WireGuard attributes.")
    def wireguard_interface_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return wireguard_interface_add_impl(client, attributes=attributes)

    @app.tool(description="List WireGuard peers with optional interface and disabled filters.")
    def wireguard_peer_list(
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return wireguard_peer_list_impl(client, interface=interface, disabled=disabled)

    @app.tool(description="Create a WireGuard peer using RouterOS peer attributes.")
    def wireguard_peer_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return wireguard_peer_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a WireGuard peer by RouterOS item id.")
    def wireguard_peer_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return wireguard_peer_remove_impl(client, item_id=item_id)

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

    @app.tool(description="Download a router file into the local workspace.")
    def file_download(
        router_path: str,
        local_path: str | None = None,
    ) -> dict[str, str | bool]:
        return file_download_impl(client, router_path=router_path, local_path=local_path)

    @app.tool(description="Create router backup artifacts and download them into the local workspace.")
    def system_backup_collect(
        name_prefix: str | None = None,
        include_sensitive: bool = False,
        compact: bool = False,
        local_dir: str | None = None,
    ) -> dict[str, str | bool]:
        return system_backup_collect_impl(
            client,
            name_prefix=name_prefix,
            include_sensitive=include_sensitive,
            compact=compact,
            local_dir=local_dir,
        )

    return app


def load_settings(host: str) -> RouterOSClient:
    workspace_root = _workspace_root()
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
