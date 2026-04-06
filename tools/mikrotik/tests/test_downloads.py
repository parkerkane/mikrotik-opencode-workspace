from __future__ import annotations

from pathlib import Path

import pytest

from mikrotik_mcp.downloads import SCPFileDownloader, RouterFileDownloadError, load_file_transfer_settings


def test_load_file_transfer_settings_uses_scp_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIKROTIK_USER", "api-user")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "api-pass")
    monkeypatch.setenv("MIKROTIK_SCP_HOST", "files.router.test")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "scp-user")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")
    monkeypatch.setenv("MIKROTIK_SCP_PORT", "2222")
    monkeypatch.setenv("MIKROTIK_SCP_TIMEOUT", "12.5")

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "files.router.test"
    assert settings.username == "scp-user"
    assert settings.password == "scp-pass"
    assert settings.port == 2222
    assert settings.timeout == 12.5


def test_load_file_transfer_settings_falls_back_to_api_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.delenv("MIKROTIK_SCP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_HOST", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PORT", raising=False)

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "router.test"
    assert settings.username == "admin"
    assert settings.password == "secret"
    assert settings.port == 22


def test_load_file_transfer_settings_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIKROTIK_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="must be set before downloading files"):
        load_file_transfer_settings("router.test")


class FakeDirEntry:
    def __init__(self, filename: str) -> None:
        self.filename = filename


class FakeRemoteFile:
    def __init__(self, payload: bytes = b"backup-data", *, fail_on_read: bool = False) -> None:
        self.payload = payload
        self.fail_on_read = fail_on_read

    def read(self) -> bytes:
        if self.fail_on_read:
            raise OSError("read failed")
        return self.payload

    def close(self) -> None:
        return None


class FakeSFTPClient:
    def __init__(self, payload: bytes = b"backup-data", *, fail_on_read: bool = False, fail_on_listdir: bool = False) -> None:
        self.payload = payload
        self.fail_on_read = fail_on_read
        self.fail_on_listdir = fail_on_listdir
        self.closed = False

    def normalize(self, path: str) -> str:
        assert path == "."
        return "/"

    def listdir_attr(self, path: str) -> list[FakeDirEntry]:
        assert path == "/"
        if self.fail_on_listdir:
            raise OSError("listing failed")
        return [FakeDirEntry("backups"), FakeDirEntry("flash"), FakeDirEntry("skins")]

    def file(self, path: str, mode: str = "rb") -> FakeRemoteFile:
        assert path == "backups/router.backup"
        assert mode == "rb"
        return FakeRemoteFile(self.payload, fail_on_read=self.fail_on_read)

    def close(self) -> None:
        self.closed = True


class FakeSSHClient:
    def __init__(self, *, fail_on_connect: bool = False, sftp_client: FakeSFTPClient | None = None) -> None:
        self.connected_to: tuple[str, int] | None = None
        self.logged_in_as: tuple[str, str] | None = None
        self.close_called = False
        self.policy = None
        self.fail_on_connect = fail_on_connect
        self.sftp_client = sftp_client or FakeSFTPClient()

    def set_missing_host_key_policy(self, policy) -> None:
        self.policy = policy

    def connect(self, hostname: str, port: int, username: str, password: str, timeout: float) -> None:
        if self.fail_on_connect:
            raise OSError("connect failed")
        self.connected_to = (hostname, port)
        self.logged_in_as = (username, password)
        self.timeout = timeout

    def open_sftp(self) -> FakeSFTPClient:
        return self.sftp_client

    def close(self) -> None:
        self.close_called = True


def test_scp_file_downloader_writes_downloaded_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    settings = load_file_transfer_settings_for_test()
    downloader = SCPFileDownloader(settings)
    destination = tmp_path / "artifacts" / "router.backup"

    downloader.download_file("backups/router.backup", destination)

    assert destination.read_bytes() == b"backup-data"
    assert ssh_client.connected_to == ("router.test", 22)
    assert ssh_client.logged_in_as == ("admin", "secret")
    assert ssh_client.close_called is True


def test_scp_file_downloader_check_connection_logs_in_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    result = downloader.check_connection()

    assert ssh_client.connected_to == ("router.test", 22)
    assert ssh_client.logged_in_as == ("admin", "secret")
    assert ssh_client.close_called is True
    assert result == {
        "working_directory": "/",
        "listing_count": 3,
        "listing_sample": ["backups", "flash", "skins"],
        "operation": "normalize+listdir_attr",
    }


def test_scp_file_downloader_wraps_local_write_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    with pytest.raises(RouterFileDownloadError, match="Failed to write local file"):
        downloader.download_file("backups/router.backup", tmp_path)


def test_scp_file_downloader_check_connection_wraps_connect_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mikrotik_mcp.downloads.paramiko.SSHClient",
        lambda: FakeSSHClient(fail_on_connect=True),
    )

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    with pytest.raises(RouterFileDownloadError, match="Failed to connect to SCP service"):
        downloader.check_connection()


def test_scp_file_downloader_check_connection_wraps_directory_probe_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient(sftp_client=FakeSFTPClient(fail_on_listdir=True))
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    with pytest.raises(RouterFileDownloadError, match="directory probe failed"):
        downloader.check_connection()

    assert ssh_client.close_called is True


def load_file_transfer_settings_for_test():
    class Settings:
        host = "router.test"
        username = "admin"
        password = "secret"
        port = 22
        timeout = 5.0

    return Settings()
