from __future__ import annotations

from pathlib import Path

import pytest

from mikrotik_mcp.downloads import SCPFileDownloader, RouterFileDownloadError, load_file_transfer_settings


def test_load_file_transfer_settings_uses_scp_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_USER", "api-user")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "api-pass")
    monkeypatch.setenv("MIKROTIK_SCP_HOST", "files.router.test")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "scp-user")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")
    monkeypatch.delenv("MIKROTIK_SCP_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_PORT", "2222")
    monkeypatch.setenv("MIKROTIK_SCP_TIMEOUT", "12.5")

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "files.router.test"
    assert settings.username == "scp-user"
    assert settings.password == "scp-pass"
    assert settings.private_key is None
    assert settings.port == 2222
    assert settings.timeout == 12.5


def test_load_file_transfer_settings_falls_back_to_api_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.delenv("MIKROTIK_SCP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_HOST", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PORT", raising=False)

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "router.test"
    assert settings.username == "admin"
    assert settings.password == "secret"
    assert settings.private_key is None
    assert settings.port == 22


def test_load_file_transfer_settings_uses_explicit_private_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    private_key = tmp_path / "router-key"
    private_key.write_text("private-key", encoding="utf-8")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "mcprw")
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(private_key))
    monkeypatch.setenv("MIKROTIK_SCP_KEY_PASSPHRASE", "phrase")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "ignored-pass")

    settings = load_file_transfer_settings("router.test")

    assert settings.username == "mcprw"
    assert settings.private_key == str(private_key)
    assert settings.key_passphrase == "phrase"
    assert settings.password is None


def test_load_file_transfer_settings_does_not_use_default_router_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "router-key").write_text("private-key", encoding="utf-8")
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "mcprw")
    monkeypatch.delenv("MIKROTIK_SCP_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")

    settings = load_file_transfer_settings("router.test")

    assert settings.username == "mcprw"
    assert settings.private_key is None
    assert settings.password == "scp-pass"


def test_load_file_transfer_settings_requires_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.delenv("MIKROTIK_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", "/definitely/missing/key")

    with pytest.raises(RuntimeError, match="SCP private key file"):
        load_file_transfer_settings("router.test")


def test_load_file_transfer_settings_requires_auth_when_no_key_or_password(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.delenv("MIKROTIK_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "mcprw")
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(tmp_path / "missing-key"))

    with pytest.raises(RuntimeError, match="SCP private key file"):
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
        self.connect_kwargs: dict[str, object] | None = None
        self.close_called = False
        self.policy = None
        self.fail_on_connect = fail_on_connect
        self.sftp_client = sftp_client or FakeSFTPClient()

    def set_missing_host_key_policy(self, policy) -> None:
        self.policy = policy

    def connect(self, **kwargs) -> None:
        if self.fail_on_connect:
            raise OSError("connect failed")
        self.connected_to = (kwargs["hostname"], kwargs["port"])
        self.connect_kwargs = kwargs

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
    assert ssh_client.connect_kwargs == {
        "hostname": "router.test",
        "port": 22,
        "username": "admin",
        "password": "secret",
        "timeout": 5.0,
    }
    assert ssh_client.close_called is True


def test_scp_file_downloader_check_connection_logs_in_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    result = downloader.check_connection()

    assert ssh_client.connected_to == ("router.test", 22)
    assert ssh_client.connect_kwargs == {
        "hostname": "router.test",
        "port": 22,
        "username": "admin",
        "password": "secret",
        "timeout": 5.0,
    }
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


def test_scp_file_downloader_prefers_private_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_key_transfer_settings_for_test())

    downloader.check_connection()

    assert ssh_client.connect_kwargs == {
        "hostname": "router.test",
        "port": 22,
        "username": "mcprw",
        "key_filename": "/workspace/certs/router-key",
        "passphrase": "phrase",
        "timeout": 5.0,
    }


def load_file_transfer_settings_for_test():
    class Settings:
        host = "router.test"
        username = "admin"
        password = "secret"
        private_key = None
        key_passphrase = None
        port = 22
        timeout = 5.0

    return Settings()


def load_key_transfer_settings_for_test():
    class Settings:
        host = "router.test"
        username = "mcprw"
        password = "secret"
        private_key = "/workspace/certs/router-key"
        key_passphrase = "phrase"
        port = 22
        timeout = 5.0

    return Settings()
