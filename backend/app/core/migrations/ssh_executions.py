from sqlalchemy import Engine, select

from ...execution_models import SSHExecution, SSHExecutionEvent, SSHExecutionRequest, SSHExecutionStep


def migrate_ssh_executions(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        for table in (SSHExecutionRequest.__table__, SSHExecution.__table__, SSHExecutionStep.__table__, SSHExecutionEvent.__table__):
            table.create(connection, checkfirst=True)
        missing = select(SSHExecution.id).where(~select(SSHExecutionRequest.id).where(
            SSHExecutionRequest.id == SSHExecution.id).exists())
        connection.execute(SSHExecutionRequest.__table__.insert().from_select(["id"], missing))
