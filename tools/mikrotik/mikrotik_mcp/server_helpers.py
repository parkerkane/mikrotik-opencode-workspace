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

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .client import RouterOSClient


def workspace_root() -> Path:
    return Path.cwd()


def stringify_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def print_records(
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


def print_single_record(
    client: RouterOSClient,
    *,
    menu: str,
    queries: Sequence[str] | None = None,
    attributes: dict[str, Any] | None = None,
    entity_name: str,
) -> dict[str, str]:
    items = print_records(client, menu=menu, queries=queries, attributes=attributes)
    if not items:
        raise ValueError(f"No matching {entity_name} found")
    if len(items) > 1:
        raise ValueError(f"Multiple {entity_name} records matched")
    return items[0]


def build_equality_queries(**filters: Any) -> list[str]:
    return [f"{field}={stringify_value(value)}" for field, value in filters.items() if value is not None]


def require_exactly_one_locator(entity_name: str, **locators: str | None) -> tuple[str, str]:
    selected = [(field, value.strip()) for field, value in locators.items() if value is not None and value.strip()]
    if len(selected) != 1:
        options = ", ".join(locators)
        raise ValueError(f"Exactly one {entity_name} locator is required: {options}")
    return selected[0]


def normalize_generated_name(name: str, *, extension: str, field_name: str = "name") -> str:
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


def file_exists_in_directory(file_name: str, directory: str) -> bool:
    normalized_directory = directory.strip().strip("/")
    if not normalized_directory:
        return True
    normalized_name = file_name.strip().strip("/")
    return normalized_name == normalized_directory or normalized_name.startswith(f"{normalized_directory}/")


def normalize_local_directory(local_dir: str | None) -> Path:
    root = workspace_root()
    if local_dir is None:
        return root / "backups"
    value = local_dir.strip()
    if not value:
        raise ValueError("local_dir must not be empty")
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def normalize_router_file_path(router_path: str) -> str:
    value = router_path.strip().strip("/")
    if not value:
        raise ValueError("router_path is required")
    if value.endswith("/"):
        raise ValueError("router_path must not end with '/'")
    return value


def require_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    if not attributes:
        raise ValueError("attributes are required")
    return attributes


def normalize_firewall_table(table: str) -> str:
    value = table.strip().lower()
    if value not in {"filter", "nat"}:
        raise ValueError("table must be either 'filter' or 'nat'")
    return value


def normalize_move_destination(destination: str) -> str:
    value = destination.strip()
    if not value:
        raise ValueError("destination is required")
    return value


def normalize_required_string(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def safe_name_component(value: str, *, default: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.strip().lower())
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return collapsed or default


def unique_local_path(directory: Path, file_name: str) -> Path:
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


def require_attribute_fields(attributes: dict[str, Any] | None, *, required_fields: Sequence[str]) -> dict[str, Any]:
    normalized = require_attributes(attributes)
    missing = [field for field in required_fields if field not in normalized or not str(normalized[field]).strip()]
    if missing:
        if len(missing) == 1:
            raise ValueError(f"{missing[0]} is required")
        raise ValueError(f"Required attributes are missing: {', '.join(missing)}")
    return normalized


def parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
