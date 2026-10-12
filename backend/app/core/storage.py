import os
import subprocess
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Engine, create_engine, event, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from ..models import Base, Host, JumpHost, SSHKey, utc_now
from .migrations.ssh_connections import migrate_ssh_connections


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
        migrate_ssh_connections(engine)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine)
        with engine.connect() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("hosts")}
            encrypted = list(connection.scalars(select(Host.password_encrypted).where(Host.password_encrypted.is_not(None))))
            encrypted.extend(connection.scalars(select(JumpHost.password_encrypted).where(JumpHost.password_encrypted.is_not(None))))
            encrypted.extend(connection.scalars(select(SSHKey.private_key_encrypted)))
            if "proxy_password_encrypted" in columns:
                encrypted.extend(connection.scalars(text("SELECT proxy_password_encrypted FROM hosts WHERE proxy_password_encrypted IS NOT NULL")))
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
        with engine.begin() as connection:
            # sqlite3 不会在 SQLAlchemy 的逻辑事务开始时立即发出 BEGIN；先开启真实写事务以覆盖 DDL。
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            key_columns = {column["name"] for column in inspect(connection).get_columns("ssh_keys")}
            if "public_key" not in key_columns:
                connection.execute(text("ALTER TABLE ssh_keys ADD COLUMN public_key TEXT"))
            for table in ("hosts", "jump_hosts"):
                table_columns = {column["name"] for column in inspect(connection).get_columns(table)}
                if "ssh_key_id" not in table_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN ssh_key_id INTEGER REFERENCES ssh_keys(id) ON DELETE RESTRICT"))
            if "jump_host_id" not in columns:
                connection.execute(text("ALTER TABLE hosts ADD COLUMN jump_host_id INTEGER REFERENCES jump_hosts(id) ON DELETE RESTRICT"))
            if "proxy_address" in columns:
                legacy_hosts = connection.execute(text("""
                    SELECT id, name, proxy_address, proxy_username, proxy_port, proxy_auth_type,
                           proxy_key_path, proxy_password_encrypted
                    FROM hosts WHERE proxy_address IS NOT NULL AND jump_host_id IS NULL ORDER BY id
                """))
                for host in legacy_hosts.mappings():
                    now = utc_now()
                    result = connection.execute(JumpHost.__table__.insert().values(
                        name=host["name"],
                        address=host["proxy_address"], username=host["proxy_username"],
                        port=host["proxy_port"], auth_type=host["proxy_auth_type"],
                        key_path=host["proxy_key_path"], password_encrypted=host["proxy_password_encrypted"],
                        remark="", created_at=now, updated_at=now, version=1,
                    ))
                    connection.execute(text("UPDATE hosts SET jump_host_id = :jump_host_id WHERE id = :host_id"), {
                        "jump_host_id": result.inserted_primary_key[0], "host_id": host["id"],
                    })
                connection.execute(text("""
                    UPDATE hosts SET proxy_address = NULL, proxy_username = NULL, proxy_port = NULL,
                        proxy_auth_type = NULL, proxy_key_path = NULL, proxy_password_encrypted = NULL
                    WHERE proxy_address IS NOT NULL OR proxy_username IS NOT NULL OR proxy_port IS NOT NULL
                        OR proxy_auth_type IS NOT NULL OR proxy_key_path IS NOT NULL
                        OR proxy_password_encrypted IS NOT NULL
                """))
        return engine, sessions, cipher
    except Exception:
        engine.dispose()
        raise
