from sqlalchemy import Engine


def migrate_retired_features(engine: Engine) -> None:
    """删除已退役功能的专用表和历史数据，保留共享业务数据。"""
    with engine.begin() as connection:
        # 显式开启 SQLite 写事务，确保后续 DDL 失败时整批回滚。
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        for table in ("operation_steps", "operation_hosts", "operation_tasks"):
            connection.exec_driver_sql(f"DROP TABLE IF EXISTS {table}")
