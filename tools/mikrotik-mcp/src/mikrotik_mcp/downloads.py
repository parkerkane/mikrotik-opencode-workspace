from __future__ import annotations

from dataclasses import dataclass
from ftplib import FTP, FTP_TLS, all_errors
from pathlib import Path
import os
import ssl
from typing import Protocol


class RouterFileDownloadError(RuntimeError):
    pass


@dataclass(slots=True)
class FileTransferSettings:
    host: str
    username: str
    password: str
    port: int = 21
    use_tls: bool = True
    tls_verify: bool = True
    timeout: float = 30.0


class FileDownloader(Protocol):
    def download_file(self, router_path: str, local_path: str | Path) -> None: ...


class FTPFileDownloader:
    def __init__(self, settings: FileTransferSettings) -> None:
        self.settings = settings

    def download_file(self, router_path: str, local_path: str | Path) -> None:
        remote_name = _normalize_router_path(router_path)
        target_path = Path(local_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            session = self._connect()
        except all_errors as exc:
            raise RouterFileDownloadError(f"Failed to connect to FTP service on {self.settings.host}:{self.settings.port}: {exc}") from exc

        try:
            with target_path.open("wb") as handle:
                session.retrbinary(f"RETR {remote_name}", handle.write)
        except OSError as exc:
            raise RouterFileDownloadError(f"Failed to write local file '{target_path}': {exc}") from exc
        except all_errors as exc:
            raise RouterFileDownloadError(f"Failed to download router file '{remote_name}': {exc}") from exc
        finally:
            try:
                session.quit()
            except all_errors:
                session.close()

    def _connect(self) -> FTP | FTP_TLS:
        if self.settings.use_tls:
            context = ssl.create_default_context()
            if not self.settings.tls_verify:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            session = FTP_TLS(context=context, timeout=self.settings.timeout)
        else:
            session = FTP(timeout=self.settings.timeout)

        session.connect(self.settings.host, self.settings.port)
        session.login(self.settings.username, self.settings.password)
        if self.settings.use_tls:
            session.prot_p()
        return session


def load_file_transfer_settings(host: str) -> FileTransferSettings:
    username = os.getenv("MIKROTIK_FTP_USER") or os.getenv("MIKROTIK_USER")
    password = os.getenv("MIKROTIK_FTP_PASSWORD") or os.getenv("MIKROTIK_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "MIKROTIK_FTP_USER/MIKROTIK_FTP_PASSWORD or MIKROTIK_USER/MIKROTIK_PASSWORD must be set before downloading files"
        )

    use_tls = _parse_bool(os.getenv("MIKROTIK_FTP_TLS"), default=True)
    tls_verify = _parse_bool(os.getenv("MIKROTIK_FTP_TLS_VERIFY"), default=_parse_bool(os.getenv("MIKROTIK_TLS_VERIFY"), default=True))

    return FileTransferSettings(
        host=os.getenv("MIKROTIK_FTP_HOST") or host,
        username=username,
        password=password,
        port=int(os.getenv("MIKROTIK_FTP_PORT") or 21),
        use_tls=use_tls,
        tls_verify=tls_verify,
        timeout=float(os.getenv("MIKROTIK_FTP_TIMEOUT") or 30.0),
    )


def _normalize_router_path(router_path: str) -> str:
    value = router_path.strip()
    if not value:
        raise ValueError("router_path is required")
    return value.lstrip("/")


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
