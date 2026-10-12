from sqlalchemy import Engine

from ...connection_models import ConnectionTest, KnownHostKey


def migrate_ssh_connections(engine: Engine) -> None:
    """新增连接测试与服务器身份表，不修改或删除既有资产和凭据。"""
    with engine.begin() as connection:
        KnownHostKey.__table__.create(connection, checkfirst=True)
        ConnectionTest.__table__.create(connection, checkfirst=True)
