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

import secrets
import string
import os
import sys

from dotenv import load_dotenv

from .app import create_app
from .client import RouterOSClient
from .downloads import rotate_routeros_user_password
from .server_helpers import parse_bool, workspace_root


CERTIFICATE_EXTENSIONS = {".pem", ".crt", ".cer"}
PASSWORDLESS_PASSWORD_ALPHABET = string.ascii_letters + string.digits
DEFAULT_PASSWORDLESS_LENGTH = 32
STARTUP_PASSWORDLESS_STATUS_ENV = "MIKROTIK_STARTUP_PASSWORDLESS_STATUS"
STARTUP_PASSWORDLESS_CODE_ENV = "MIKROTIK_STARTUP_PASSWORDLESS_CODE"
STARTUP_PASSWORDLESS_MESSAGE_ENV = "MIKROTIK_STARTUP_PASSWORDLESS_MESSAGE"
MIKROTIK_ENV_PREFIX = "MIKROTIK_"


def clear_empty_mikrotik_env_vars() -> None:
    for name, value in tuple(os.environ.items()):
        if name.startswith(MIKROTIK_ENV_PREFIX) and value == "":
            os.environ.pop(name, None)


def load_tls_ca_files() -> tuple[str, ...]:
    certs_dir = workspace_root() / "certs"
    if not certs_dir.is_dir():
        return ()

    cert_files = [
        path
        for path in sorted(certs_dir.iterdir())
        if path.is_file() and path.suffix.lower() in CERTIFICATE_EXTENSIONS and not path.name.endswith(".disabled")
    ]
    return tuple(str(path) for path in cert_files)


def load_settings(host: str) -> RouterOSClient:
    clear_empty_mikrotik_env_vars()
    load_dotenv(workspace_root() / ".env")

    username = os.getenv("MIKROTIK_USER")
    if not username:
        raise RuntimeError("MIKROTIK_USER must be set before starting the MCP server")

    if passwordless_enabled():
        password = resolve_startup_api_password(host, username=username)
    else:
        clear_startup_passwordless_state()
        password = os.getenv("MIKROTIK_PASSWORD")
        if not password:
            raise RuntimeError("MIKROTIK_USER and MIKROTIK_PASSWORD must be set before starting the MCP server")

    use_ssl = parse_bool(os.getenv("MIKROTIK_API_SSL"), default=True)
    tls_verify = parse_bool(os.getenv("MIKROTIK_TLS_VERIFY"), default=True)
    port = int(os.getenv("MIKROTIK_API_PORT") or (8729 if use_ssl else 8728))
    tls_ca_files = load_tls_ca_files()

    return RouterOSClient(
        host,
        username,
        password,
        port=port,
        use_ssl=use_ssl,
        tls_verify=tls_verify,
        tls_ca_files=tls_ca_files,
    )


def passwordless_enabled() -> bool:
    return parse_bool(os.getenv("MIKROTIK_API_PASSWORDLESS_ENABLED"), default=False)


def clear_startup_passwordless_state() -> None:
    os.environ.pop(STARTUP_PASSWORDLESS_STATUS_ENV, None)
    os.environ.pop(STARTUP_PASSWORDLESS_CODE_ENV, None)
    os.environ.pop(STARTUP_PASSWORDLESS_MESSAGE_ENV, None)


def set_startup_passwordless_state(*, status: str, code: str, message: str) -> None:
    os.environ[STARTUP_PASSWORDLESS_STATUS_ENV] = status
    os.environ[STARTUP_PASSWORDLESS_CODE_ENV] = code
    os.environ[STARTUP_PASSWORDLESS_MESSAGE_ENV] = message


def startup_passwordless_state() -> dict[str, str] | None:
    status = os.getenv(STARTUP_PASSWORDLESS_STATUS_ENV)
    code = os.getenv(STARTUP_PASSWORDLESS_CODE_ENV)
    message = os.getenv(STARTUP_PASSWORDLESS_MESSAGE_ENV)
    if not status or not code or not message:
        return None
    return {
        "status": status,
        "code": code,
        "message": message,
    }


def resolve_startup_api_password(host: str, *, username: str) -> str:
    fingerprint = os.getenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256")
    fallback_password = os.getenv("MIKROTIK_PASSWORD")
    if not fingerprint:
        set_startup_passwordless_state(
            status="skipped",
            code="passwordless.fingerprint_missing",
            message="SSH host fingerprint verification is not configured; startup password rotation was skipped",
        )
        return fallback_password or ""

    try:
        password = rotate_startup_api_password(host, username=username)
    except Exception as exc:
        set_startup_passwordless_state(
            status="failed",
            code="passwordless.startup_failed",
            message=f"Startup password rotation failed: {exc}",
        )
        return fallback_password or ""

    clear_startup_passwordless_state()
    return password


def rotate_startup_api_password(host: str, *, username: str) -> str:
    length = int(os.getenv("MIKROTIK_API_PASSWORDLESS_LENGTH") or DEFAULT_PASSWORDLESS_LENGTH)
    if length < 1:
        raise RuntimeError("MIKROTIK_API_PASSWORDLESS_LENGTH must be at least 1")

    new_password = generate_api_password(length)
    rotate_routeros_user_password(host=host, username=username, new_password=new_password)
    return new_password


def generate_api_password(length: int) -> str:
    return "".join(secrets.choice(PASSWORDLESS_PASSWORD_ALPHABET) for _ in range(length))


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        raise SystemExit("Usage: python tools/mikrotik/main.py <host>")

    client = load_settings(args[0])
    try:
        create_app(client).run(transport="stdio")
    finally:
        client.close()
