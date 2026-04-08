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

import base64
from dataclasses import dataclass
import hashlib
import socket
from pathlib import Path
import os
import shlex
from typing import Protocol

import paramiko

from .server_helpers import workspace_root


class RouterFileDownloadError(RuntimeError):
    pass


class RouterSSHCommandError(RuntimeError):
    pass


class RouterSSHProbeError(RuntimeError):
    pass


@dataclass(slots=True)
class FileTransferSettings:
    host: str
    username: str
    password: str | None = None
    private_key: str | None = None
    key_passphrase: str | None = None
    ssh_host_fingerprint_sha256: str | None = None
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
        return open_ssh_client(self.settings)

    def _close_session(self, ssh_client: paramiko.SSHClient) -> None:
        ssh_client.close()


def load_file_transfer_settings(host: str) -> FileTransferSettings:
    username = os.getenv("MIKROTIK_SCP_USER") or os.getenv("MIKROTIK_USER")
    private_key = resolve_scp_private_key_path()
    password = None if private_key else (os.getenv("MIKROTIK_SCP_PASSWORD") or os.getenv("MIKROTIK_PASSWORD"))
    ssh_host_fingerprint_sha256 = os.getenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256")
    if not username or (not private_key and not password):
        raise RuntimeError(
            "MIKROTIK_SCP_USER plus either MIKROTIK_SCP_PRIVATE_KEY, MIKROTIK_SCP_PASSWORD, or MIKROTIK_PASSWORD must be set before downloading files"
        )
    return FileTransferSettings(
        host=os.getenv("MIKROTIK_SCP_HOST") or host,
        username=username,
        password=password,
        private_key=private_key,
        key_passphrase=os.getenv("MIKROTIK_SCP_KEY_PASSPHRASE"),
        ssh_host_fingerprint_sha256=(
            normalize_ssh_sha256_fingerprint(ssh_host_fingerprint_sha256) if ssh_host_fingerprint_sha256 else None
        ),
        port=int(os.getenv("MIKROTIK_SCP_PORT") or 22),
        timeout=float(os.getenv("MIKROTIK_SCP_TIMEOUT") or 30.0),
    )


def load_password_rotation_settings(host: str) -> FileTransferSettings:
    if not os.getenv("MIKROTIK_SCP_PRIVATE_KEY"):
        raise RuntimeError("MIKROTIK_SCP_PRIVATE_KEY must be set when API passwordless startup rotation is enabled")
    settings = load_file_transfer_settings(host)
    if not settings.private_key:
        raise RuntimeError("MIKROTIK_SCP_PRIVATE_KEY must be set when API passwordless startup rotation is enabled")
    return settings


def rotate_routeros_user_password(*, host: str, username: str, new_password: str) -> None:
    settings = load_password_rotation_settings(host)
    ssh_client = open_ssh_client(settings)
    command = _build_password_set_command(username=username, password=new_password)
    try:
        run_ssh_command(ssh_client, command, timeout=settings.timeout)
    except (paramiko.SSHException, OSError, RouterSSHCommandError) as exc:
        raise RouterSSHCommandError(
            f"Failed to rotate RouterOS password for user '{username}' on {settings.host}:{settings.port}: {exc}"
        ) from exc
    finally:
        ssh_client.close()


def check_routeros_password_rotation_ready(*, host: str, username: str) -> dict[str, object]:
    settings = load_password_rotation_settings(host)
    ssh_client = open_ssh_client(settings)
    command = _build_password_ready_command(username=username)
    try:
        result = run_ssh_command(ssh_client, command, timeout=settings.timeout)
    except (paramiko.SSHException, OSError, RouterSSHCommandError) as exc:
        raise RouterSSHCommandError(
            f"Failed to verify RouterOS passwordless readiness for user '{username}' on {settings.host}:{settings.port}: {exc}"
        ) from exc
    finally:
        ssh_client.close()

    user_count = _parse_count_output(result)
    if user_count != 1:
        raise RouterSSHCommandError(f"RouterOS user '{username}' was not found over SSH")

    return {
        "host": settings.host,
        "port": settings.port,
        "username": username,
        "target_exists": True,
        "command": command,
    }


def resolve_scp_private_key_path() -> str | None:
    configured_path = os.getenv("MIKROTIK_SCP_PRIVATE_KEY")
    if configured_path:
        resolved_path = _resolve_local_path(configured_path)
        if not resolved_path.is_file():
            raise RuntimeError(f"SCP private key file '{resolved_path}' does not exist")
        return str(resolved_path)
    return None


def _resolve_local_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return workspace_root() / candidate


def _normalize_router_path(router_path: str) -> str:
    value = router_path.strip()
    if not value:
        raise ValueError("router_path is required")
    return value.lstrip("/")


def open_ssh_client(settings: FileTransferSettings) -> paramiko.SSHClient:
    ssh_client = paramiko.SSHClient()
    if settings.ssh_host_fingerprint_sha256:
        ssh_client.set_missing_host_key_policy(SSHSha256FingerprintPolicy(settings.host, settings.ssh_host_fingerprint_sha256))
    else:
        ssh_client.set_missing_host_key_policy(PermissiveMissingHostKeyPolicy())
    connect_kwargs: dict[str, object] = {
        "hostname": settings.host,
        "port": settings.port,
        "username": settings.username,
        "timeout": settings.timeout,
    }
    if settings.private_key:
        connect_kwargs["key_filename"] = settings.private_key
        if settings.key_passphrase:
            connect_kwargs["passphrase"] = settings.key_passphrase
    elif settings.password:
        connect_kwargs["password"] = settings.password

    ssh_client.connect(**connect_kwargs)
    return ssh_client


def probe_ssh_server_fingerprint(*, host: str, port: int, timeout: float) -> dict[str, object]:
    raw_socket = None
    transport = None
    try:
        raw_socket = socket.create_connection((host, port), timeout=timeout)
        transport = paramiko.Transport(raw_socket)
        transport.banner_timeout = timeout
        transport.handshake_timeout = timeout
        transport.start_client(timeout=timeout)
        server_key = transport.get_remote_server_key()
        return {
            "host": host,
            "port": port,
            "key_type": server_key.get_name(),
            "fingerprint_sha256": ssh_host_key_sha256(server_key),
        }
    except (paramiko.SSHException, OSError) as exc:
        raise RouterSSHProbeError(f"Failed to fetch SSH server fingerprint from {host}:{port}: {exc}") from exc
    finally:
        if transport is not None:
            transport.close()
        if raw_socket is not None:
            raw_socket.close()


def run_ssh_command(ssh_client: paramiko.SSHClient, command: str, *, timeout: float) -> str:
    _, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
    stdout_data = stdout.read()
    stderr_data = stderr.read()
    stdout_text = _decode_ssh_stream(stdout_data)
    stderr_text = _decode_ssh_stream(stderr_data)

    exit_status = 0
    channel = getattr(stdout, "channel", None)
    if channel is not None and hasattr(channel, "recv_exit_status"):
        exit_status = channel.recv_exit_status()

    if exit_status != 0 or stderr_text:
        problem = stderr_text or stdout_text or f"remote command exited with status {exit_status}"
        raise RouterSSHCommandError(problem)
    return stdout_text


def _decode_ssh_stream(data: bytes | str) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace").strip()
    return str(data).strip()


def _build_password_set_command(*, username: str, password: str) -> str:
    quoted_username = shlex.quote(_normalize_routeros_string(username, field_name="username"))
    quoted_password = shlex.quote(_normalize_routeros_string(password, field_name="password"))
    return f"/user set [find where name={quoted_username}] password={quoted_password}"


def _build_password_ready_command(*, username: str) -> str:
    quoted_username = shlex.quote(_normalize_routeros_string(username, field_name="username"))
    return f"/user print count-only where name={quoted_username}"


def _normalize_routeros_string(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _parse_count_output(value: str) -> int:
    normalized = value.strip()
    if not normalized:
        raise RouterSSHCommandError("RouterOS readiness probe returned an empty response")
    try:
        return int(normalized)
    except ValueError as exc:
        raise RouterSSHCommandError(f"RouterOS readiness probe returned an unexpected response: {normalized}") from exc


class SSHSha256FingerprintPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, hostname: str, expected_fingerprint: str | None) -> None:
        if not expected_fingerprint:
            raise ValueError("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256 must be set before opening SSH or SCP connections")
        self.hostname = hostname
        self.expected_fingerprint = normalize_ssh_sha256_fingerprint(expected_fingerprint)

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        presented_fingerprint = ssh_host_key_sha256(key)
        if presented_fingerprint != self.expected_fingerprint:
            raise paramiko.SSHException(
                f"SSH host key fingerprint mismatch for {hostname}: expected {self.expected_fingerprint}, got {presented_fingerprint}"
            )


class PermissiveMissingHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        return None


def ssh_host_key_sha256(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    encoded = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{encoded}"


def normalize_ssh_sha256_fingerprint(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256 must not be empty")

    if normalized.lower().startswith("sha256:"):
        fingerprint_body = normalized[7:]
    else:
        fingerprint_body = normalized

    if not fingerprint_body:
        raise ValueError("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256 must include a SHA256 fingerprint value")
    if any(character.isspace() for character in fingerprint_body):
        raise ValueError("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256 must not contain whitespace")

    padded = fingerprint_body + "=" * (-len(fingerprint_body) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True)
    except ValueError as exc:
        raise ValueError("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256 must be an OpenSSH-style SHA256 fingerprint") from exc
    if len(decoded) != hashlib.sha256().digest_size:
        raise ValueError("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256 must decode to a SHA256 digest")
    encoded = base64.b64encode(decoded).decode("ascii").rstrip("=")
    return f"SHA256:{encoded}"
