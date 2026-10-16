from sqlalchemy import Engine, inspect, text

from ...connection_models import IdentityChallengeRecord, KnownHostKey
from ...models import utc_now


def migrate_ssh_connections(engine: Engine) -> None:
    """保留身份及信任记录，移除旧测试历史。"""
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        KnownHostKey.__table__.create(connection, checkfirst=True)
        IdentityChallengeRecord.__table__.create(connection, checkfirst=True)
        challenge_columns = {column["name"] for column in inspect(connection).get_columns("ssh_identity_challenges")}
        missing_states = {"previous_state", "jump_state"} - challenge_columns
        for column in sorted(missing_states):
            connection.execute(text(f"ALTER TABLE ssh_identity_challenges ADD COLUMN {column} JSON"))
        if missing_states:
            # 旧挑战缺少探测时的信任快照，必须重新检查身份，不能将空值视为可信快照。
            now = utc_now()
            connection.execute(text("""
                UPDATE ssh_identity_challenges SET expires_at = :now
                WHERE consumed_at IS NULL AND expires_at > :now
            """), {"now": now})
        if inspect(connection).has_table("hosts"):
            columns = {column["name"] for column in inspect(connection).get_columns("hosts")}
            if "connection_status" not in columns:
                connection.execute(text("ALTER TABLE hosts ADD COLUMN connection_status VARCHAR(20) NOT NULL DEFAULT 'untested'"))
            connection.execute(text("UPDATE hosts SET connection_status = 'interrupted' WHERE connection_status = 'running'"))
        connection.execute(text("DROP TABLE IF EXISTS ssh_connection_tests"))
