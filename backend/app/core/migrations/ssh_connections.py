from sqlalchemy import Engine, inspect, text

from ...connection_models import ConnectionTest, IdentityChallengeRecord, KnownHostKey


def migrate_ssh_connections(engine: Engine) -> None:
    """创建连接相关表并补齐历史测试记录的新增字段。"""
    with engine.begin() as connection:
        KnownHostKey.__table__.create(connection, checkfirst=True)
        ConnectionTest.__table__.create(connection, checkfirst=True)
        IdentityChallengeRecord.__table__.create(connection, checkfirst=True)
        columns = {column["name"] for column in inspect(connection).get_columns("ssh_connection_tests")}
        if "failure_message" not in columns:
            connection.execute(text("ALTER TABLE ssh_connection_tests ADD COLUMN failure_message VARCHAR"))
        if "host_key_policy" not in columns:
            connection.execute(text("ALTER TABLE ssh_connection_tests ADD COLUMN host_key_policy VARCHAR(16) NOT NULL DEFAULT 'strict'"))
        if "auto_trusted_keys" not in columns:
            connection.execute(text("ALTER TABLE ssh_connection_tests ADD COLUMN auto_trusted_keys JSON NOT NULL DEFAULT '[]'"))
