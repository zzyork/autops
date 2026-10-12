from sqlalchemy import Engine, inspect, text

from ...connection_models import ConnectionTest, KnownHostKey


def migrate_ssh_connections(engine: Engine) -> None:
    """创建连接相关表并补充错误文本列，保留既有记录。"""
    with engine.begin() as connection:
        KnownHostKey.__table__.create(connection, checkfirst=True)
        ConnectionTest.__table__.create(connection, checkfirst=True)
        columns = {column["name"] for column in inspect(connection).get_columns("ssh_connection_tests")}
        if "failure_message" not in columns:
            connection.execute(text("ALTER TABLE ssh_connection_tests ADD COLUMN failure_message VARCHAR"))
