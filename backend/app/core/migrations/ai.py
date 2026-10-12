from sqlalchemy import Engine, inspect, text

from ...ai_models import AIConnection, AIMessage, AIProposal, AISession, AIToolHistory


def migrate_ai(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in (AIConnection.__table__, AISession.__table__, AIMessage.__table__,
                      AIProposal.__table__, AIToolHistory.__table__):
            table.create(connection, checkfirst=True)
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
