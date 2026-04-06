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

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..client import RouterOSClient
from ..downloads import FTPFileDownloader, FileDownloader, RouterFileDownloadError, load_file_transfer_settings
from ..server_helpers import (
    build_equality_queries,
    file_exists_in_directory,
    normalize_generated_name,
    normalize_local_directory,
    normalize_router_file_path,
    print_records,
    safe_name_component,
    unique_local_path,
    workspace_root,
)


def _build_backup_paths(
    client: RouterOSClient,
    *,
    name_prefix: str | None,
    local_dir: str | None,
) -> dict[str, str | Path]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    prefix = safe_name_component(name_prefix or "backup", default="backup")
    router_name = f"backups/{prefix}-{timestamp}"
    router_backup_path = f"{router_name}.backup"
    router_export_path = f"{router_name}.rsc"
    local_directory = normalize_local_directory(local_dir)
    router_slug = safe_name_component(client.host, default="router")

    return {
        "created_at": timestamp,
        "router_backup_path": router_backup_path,
        "router_export_path": router_export_path,
        "local_backup_path": unique_local_path(local_directory, f"{router_slug}-{prefix}-{timestamp}.backup"),
        "local_export_path": unique_local_path(local_directory, f"{router_slug}-{prefix}-{timestamp}.rsc"),
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
    normalized_router_path = normalize_router_file_path(router_path)
    resolved_downloader = downloader
    if resolved_downloader is None:
        settings = load_file_transfer_settings(client.host)
        resolved_downloader = FTPFileDownloader(settings)

    if local_path is None:
        target_path = unique_local_path(workspace_root() / "backups", Path(normalized_router_path).name)
    else:
        raw_target_path = Path(local_path)
        target_path = raw_target_path if raw_target_path.is_absolute() else workspace_root() / raw_target_path
    resolved_downloader.download_file(normalized_router_path, target_path)
    return {
        "success": True,
        "router_path": normalized_router_path,
        "local_path": str(target_path),
    }


def file_list_impl(
    client: RouterOSClient,
    *,
    directory: str | None = None,
    name: str | None = None,
    file_type: str | None = None,
) -> list[dict[str, str]]:
    queries = build_equality_queries(name=name, type=file_type)
    items = print_records(client, menu="/file", queries=queries or None)
    if name is not None:
        items = [item for item in items if item.get("name") == name]
    if file_type is not None:
        items = [item for item in items if item.get("type") == file_type]
    if directory is None:
        return items

    normalized_directory = directory.strip()
    if not normalized_directory:
        raise ValueError("directory must not be empty")
    return [item for item in items if file_exists_in_directory(item.get("name", ""), normalized_directory)]


def system_backup_save_impl(
    client: RouterOSClient,
    *,
    name: str,
) -> dict[str, str | bool]:
    normalized_name = normalize_generated_name(name, extension=".backup")
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
    normalized_name = normalize_generated_name(name, extension=".rsc")
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
