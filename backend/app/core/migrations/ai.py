from sqlalchemy import Engine, inspect, text

from ...ai_models import AIConnection, AIMessage, AIProposal, AISession, AIToolHistory


def migrate_ai(engine: Engine) -> None:
    with engine.begin() as connection:
        # SQLite defers BEGIN otherwise; hold the write transaction across column and constraint installation.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        for table in (AIConnection.__table__, AISession.__table__, AIMessage.__table__,
                      AIProposal.__table__, AIToolHistory.__table__):
            table.create(connection, checkfirst=True)
        connection_columns = {item["name"] for item in inspect(connection).get_columns("ai_connections")}
        if "is_backup" not in connection_columns:
            connection.execute(text("ALTER TABLE ai_connections ADD COLUMN is_backup BOOLEAN NOT NULL DEFAULT 0"))
        if connection.scalar(text("SELECT id FROM ai_connections WHERE is_default = 1 AND is_backup = 1 LIMIT 1")) is not None:
            raise RuntimeError("模型连接历史数据同时指定主模型和备用模型，请人工修正后重启")
        for field, role in (("is_default", "主模型"), ("is_backup", "备用模型")):
            if connection.scalar(text(f"SELECT COUNT(*) FROM ai_connections WHERE {field} = 1 "
                                      "HAVING COUNT(*) > 1")) is not None:
                raise RuntimeError(f"模型连接历史数据存在多个{role}，请人工修正后重启")
        for index in AIConnection.__table__.indexes:
            index.create(connection, checkfirst=True)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS ai_connections_distinct_roles_insert
            BEFORE INSERT ON ai_connections
            WHEN NEW.is_default = 1 AND NEW.is_backup = 1
            BEGIN SELECT RAISE(ABORT, '同一连接不能同时作为主模型和备用模型'); END
        """))
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS ai_connections_distinct_roles_update
            BEFORE UPDATE OF is_default, is_backup ON ai_connections
            WHEN NEW.is_default = 1 AND NEW.is_backup = 1
            BEGIN SELECT RAISE(ABORT, '同一连接不能同时作为主模型和备用模型'); END
        """))
        message_columns = {item["name"] for item in inspect(connection).get_columns("ai_messages")}
        if "in_flight" not in message_columns:
            connection.execute(text("ALTER TABLE ai_messages ADD COLUMN in_flight BOOLEAN NOT NULL DEFAULT 0"))
        columns = {item["name"] for item in inspect(connection).get_columns("ai_tool_history")}
        if "round_index" not in columns:
            connection.execute(text("ALTER TABLE ai_tool_history ADD COLUMN round_index INTEGER NOT NULL DEFAULT 0"))
            connection.execute(text("UPDATE ai_tool_history SET round_index = id"))
        if "call_index" not in columns:
            connection.execute(text("ALTER TABLE ai_tool_history ADD COLUMN call_index INTEGER NOT NULL DEFAULT 0"))
        if "assistant_text" not in columns:
            connection.execute(text("ALTER TABLE ai_tool_history ADD COLUMN assistant_text TEXT NOT NULL DEFAULT ''"))
