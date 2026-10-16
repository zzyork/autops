from sqlalchemy import Engine, inspect, text

from ...operation_models import OperationHost, OperationStepRun, OperationTask


def migrate_operations(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in (OperationTask.__table__, OperationHost.__table__, OperationStepRun.__table__):
            table.create(connection, checkfirst=True)
        columns = {column["name"] for column in inspect(connection).get_columns("operation_hosts")}
        if "resolution_note" not in columns:
            connection.execute(text("ALTER TABLE operation_hosts ADD COLUMN resolution_note VARCHAR"))
        if "resolved_at" not in columns:
            connection.execute(text("ALTER TABLE operation_hosts ADD COLUMN resolved_at DATETIME"))
        if "identity_required" not in columns:
            connection.execute(text("ALTER TABLE operation_hosts ADD COLUMN identity_required BOOLEAN NOT NULL DEFAULT 0"))
        task_columns = {column["name"] for column in inspect(connection).get_columns("operation_tasks")}
        if "sudo" in task_columns:
            connection.execute(text("ALTER TABLE operation_tasks DROP COLUMN sudo"))
        if "use_sudo" in columns:
            connection.execute(text("ALTER TABLE operation_hosts DROP COLUMN use_sudo"))
