from sqlalchemy import Engine, inspect, text

from ...connection_models import IdentityChallengeRecord, KnownHostKey


def migrate_ssh_connections(engine: Engine) -> None:
    """保留身份及信任记录，移除旧测试历史。"""
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        KnownHostKey.__table__.create(connection, checkfirst=True)
        IdentityChallengeRecord.__table__.create(connection, checkfirst=True)
        if inspect(connection).has_table("hosts"):
            columns = {column["name"] for column in inspect(connection).get_columns("hosts")}
            if "connection_status" not in columns:
                connection.execute(text("ALTER TABLE hosts ADD COLUMN connection_status VARCHAR(20) NOT NULL DEFAULT 'untested'"))
            connection.execute(text("UPDATE hosts SET connection_status = 'interrupted' WHERE connection_status = 'running'"))
        connection.execute(text("DROP TABLE IF EXISTS ssh_connection_tests"))
