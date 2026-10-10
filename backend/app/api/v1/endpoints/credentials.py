from fastapi import HTTPException, Request

from ....models import Host, JumpHost
from ....schemas.assets import HostInput
from ....schemas.jump_hosts import JumpHostInput


def apply_connection(data: HostInput | JumpHostInput, record: Host | JumpHost, request: Request, password_message: str) -> None:
    values = data.model_dump(exclude={"password", "version"})
    if data.auth_type == "password":
        if data.password is not None:
            record.password_encrypted = request.app.state.cipher.encrypt(data.password.get_secret_value().encode()).decode()
        else:
            if record.id is not None and any(
                getattr(record, field) != getattr(data, field) for field in ("address", "username", "port")
            ):
                raise HTTPException(422, "连接信息已变更，请重新填写对应密码")
            if record.password_encrypted is None:
                raise HTTPException(422, password_message)
        values["key_path"] = None
    else:
        record.password_encrypted = None
    for field, value in values.items():
        setattr(record, field, value)
