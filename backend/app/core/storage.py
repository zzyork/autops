import os
import subprocess
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Base, Host


def protect_key(path: Path) -> None:
    if os.name == "nt":
        # 替换整个 ACL，避免保留其他账号的显式授权。
        script = """
$ErrorActionPreference = 'Stop'
$path = $env:AUTOPS_PROTECTED_PATH
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = Get-Acl -LiteralPath $path
$acl.SetAccessRuleProtection($true, $false)
foreach ($existing in @($acl.Access)) { $acl.RemoveAccessRuleSpecific($existing) }
if (Test-Path -LiteralPath $path -PathType Container) {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
} else {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
}
$acl.AddAccessRule($rule)
if (Test-Path -LiteralPath $path -PathType Container) {
    [System.IO.Directory]::SetAccessControl($path, $acl)
} else {
    [System.IO.File]::SetAccessControl($path, $acl)
}
"""
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, "AUTOPS_PROTECTED_PATH": str(path.resolve())},
            check=True, capture_output=True, text=True,
        )
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def initialize_storage(data_dir: Path) -> tuple[Engine, sessionmaker[Session], Fernet]:
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{(data_dir / 'assets.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine)
        with sessions() as session:
            encrypted = [
                token for pair in session.execute(select(
                    Host.password_encrypted, Host.proxy_password_encrypted
                )) for token in pair if token is not None
            ]
        key_path = data_dir / "secrets" / "fernet.key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        protect_key(key_path.parent)
        if not key_path.exists():
            if encrypted:
                raise RuntimeError("已有加密凭据，但密钥文件丢失；请恢复对应密钥。")
            # 在受保护的目录中完成写入，再原子创建最终路径，绝不覆盖已有密钥。
            with tempfile.NamedTemporaryFile(dir=key_path.parent, delete=False) as key_file:
                temporary = Path(key_file.name)
                key_file.write(Fernet.generate_key())
                key_file.flush()
                os.fsync(key_file.fileno())
            try:
                os.link(temporary, key_path)
            finally:
                temporary.unlink()
        protect_key(key_path)
        try:
            cipher = Fernet(key_path.read_bytes())
            for token in encrypted:
                cipher.decrypt(token.encode())
        except (ValueError, InvalidToken) as exc:
            raise RuntimeError("密钥损坏或与已有凭据不匹配；请恢复对应密钥。") from exc
        return engine, sessions, cipher
    except Exception:
        engine.dispose()
        raise
