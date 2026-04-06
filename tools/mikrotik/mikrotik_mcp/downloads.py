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

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Protocol

import paramiko


class RouterFileDownloadError(RuntimeError):
    pass


@dataclass(slots=True)
class FileTransferSettings:
    host: str
    username: str
    password: str
    port: int = 22
    timeout: float = 30.0


class FileDownloader(Protocol):
    def download_file(self, router_path: str, local_path: str | Path) -> None: ...


class SCPFileDownloader:
    def __init__(self, settings: FileTransferSettings) -> None:
        self.settings = settings

    def check_connection(self) -> dict[str, object]:
        try:
            ssh_client = self._connect()
        except (paramiko.SSHException, OSError) as exc:
            raise RouterFileDownloadError(
                f"Failed to connect to SCP service on {self.settings.host}:{self.settings.port}: {exc}"
            ) from exc

        try:
            sftp_client = ssh_client.open_sftp()
            working_directory = sftp_client.normalize(".")
            entries = [entry.filename for entry in sftp_client.listdir_attr(working_directory)]
        except (paramiko.SSHException, OSError) as exc:
            raise RouterFileDownloadError(f"Connected to SCP service but directory probe failed: {exc}") from exc
        finally:
            self._close_session(ssh_client)

        return {
            "working_directory": working_directory,
            "listing_count": len(entries),
            "listing_sample": entries[:5],
            "operation": "normalize+listdir_attr",
        }

    def download_file(self, router_path: str, local_path: str | Path) -> None:
        remote_name = _normalize_router_path(router_path)
        target_path = Path(local_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            ssh_client = self._connect()
        except (paramiko.SSHException, OSError) as exc:
            raise RouterFileDownloadError(
                f"Failed to connect to SCP service on {self.settings.host}:{self.settings.port}: {exc}"
            ) from exc

        try:
            with target_path.open("wb") as handle:
                sftp_client = ssh_client.open_sftp()
                remote_file = sftp_client.file(remote_name, mode="rb")
                try:
                    handle.write(remote_file.read())
                finally:
                    remote_file.close()
                    sftp_client.close()
        except OSError as exc:
            raise RouterFileDownloadError(f"Failed to write local file '{target_path}': {exc}") from exc
        except (paramiko.SSHException, OSError) as exc:
            raise RouterFileDownloadError(f"Failed to download router file '{remote_name}': {exc}") from exc
        finally:
            self._close_session(ssh_client)

    def _connect(self) -> paramiko.SSHClient:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=self.settings.host,
            port=self.settings.port,
            username=self.settings.username,
            password=self.settings.password,
            timeout=self.settings.timeout,
        )
        return ssh_client

    def _close_session(self, ssh_client: paramiko.SSHClient) -> None:
        ssh_client.close()


def load_file_transfer_settings(host: str) -> FileTransferSettings:
    username = os.getenv("MIKROTIK_SCP_USER") or os.getenv("MIKROTIK_USER")
    password = os.getenv("MIKROTIK_SCP_PASSWORD") or os.getenv("MIKROTIK_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "MIKROTIK_SCP_USER/MIKROTIK_SCP_PASSWORD or MIKROTIK_USER/MIKROTIK_PASSWORD must be set before downloading files"
        )

    return FileTransferSettings(
        host=os.getenv("MIKROTIK_SCP_HOST") or host,
        username=username,
        password=password,
        port=int(os.getenv("MIKROTIK_SCP_PORT") or 22),
        timeout=float(os.getenv("MIKROTIK_SCP_TIMEOUT") or 30.0),
    )


def _normalize_router_path(router_path: str) -> str:
    value = router_path.strip()
    if not value:
        raise ValueError("router_path is required")
    return value.lstrip("/")
