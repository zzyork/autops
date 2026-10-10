from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models import Host


def host_body(group_id: int) -> dict:
    return {
        "name": "测试服务器", "address": "192.0.2.10", "group_id": group_id,
        "username": "root", "port": 22, "auth_type": "password",
        "password": "test-secret-only", "remark": "示例资产",
    }


def test_asset_crud_and_encryption(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        group = client.post("/api/v1/host-groups", json={"name": "测试组"})
        assert group.status_code == 201
        group_id = group.json()["id"]
        assert client.post("/api/v1/host-groups", json={"name": "测试组"}).status_code == 409
        body = host_body(group_id)
        body.update(proxy_address="192.0.2.20", proxy_username="jump", proxy_port=22,
                    proxy_auth_type="password", proxy_password="jump-secret-only")
        response = client.post("/api/v1/hosts", json=body)
        assert response.status_code == 201
        host_id = response.json()["id"]
        assert response.json()["has_password"] is True
        assert response.json()["has_proxy_password"] is True
        assert "secret-only" not in response.text
        assert "password_encrypted" not in response.text
        with app.state.sessions() as session:
            host = session.get(Host, host_id)
            original_token = host.password_encrypted
            assert original_token != body["password"]
            assert app.state.cipher.decrypt(original_token.encode()).decode() == body["password"]
            assert app.state.cipher.decrypt(host.proxy_password_encrypted.encode()).decode() == body["proxy_password"]
        assert client.post("/api/v1/hosts", json=body).status_code == 409
        assert client.delete(f"/api/v1/host-groups/{group_id}").status_code == 409
        assert client.get("/api/v1/host-groups").json()[0]["host_count"] == 1
        assert len(client.get("/api/v1/hosts", params={"q": "测试"}).json()) == 1
        assert client.get("/api/v1/hosts", params={"q": "%"}).json() == []
        body.pop("password")
        body.pop("proxy_password")
        body["name"] = "修改后的服务器"
        body["version"] = response.json()["version"]
        assert client.put(f"/api/v1/hosts/{host_id}", json=body).status_code == 200
        assert client.put(f"/api/v1/hosts/{host_id}", json=body).status_code == 409
        with app.state.sessions() as session:
            assert session.get(Host, host_id).password_encrypted == original_token
        key_before = (tmp_path / "secrets/fernet.key").read_bytes()

    with TestClient(create_app(settings)) as client:
        assert (tmp_path / "secrets/fernet.key").read_bytes() == key_before
        assert client.get(f"/api/v1/hosts/{host_id}").json()["name"] == "修改后的服务器"
        current = client.get(f"/api/v1/hosts/{host_id}").json()
        assert current["updated_at"].endswith("Z")
        body["version"] = current["version"]
        body.update(auth_type="key", key_path="/home/example/.ssh/id_ed25519",
                    proxy_address=None, proxy_username=None, proxy_port=None,
                    proxy_auth_type=None, proxy_key_path=None)
        result = client.put(f"/api/v1/hosts/{host_id}", json=body)
        assert result.status_code == 200
        assert result.json()["has_password"] is False
        assert result.json()["has_proxy_password"] is False
        assert client.delete(f"/api/v1/hosts/{host_id}").status_code == 204
        assert client.get(f"/api/v1/hosts/{host_id}").status_code == 404
        assert client.put(f"/api/v1/host-groups/{group_id}", json={"name": "新组名"}).status_code == 200
        assert client.delete(f"/api/v1/host-groups/{group_id}").status_code == 204


@pytest.mark.parametrize("damage", ["missing", "invalid", "wrong"])
def test_key_damage_does_not_replace_key(tmp_path: Path, damage: str) -> None:
    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        group_id = client.post("/api/v1/host-groups", json={"name": "示例"}).json()["id"]
        assert client.post("/api/v1/hosts", json=host_body(group_id)).status_code == 201
    key = tmp_path / "secrets/fernet.key"
    if damage == "missing":
        key.unlink()
    else:
        key.write_bytes(b"invalid" if damage == "invalid" else Fernet.generate_key())
    before = key.read_bytes() if key.exists() else None
    with pytest.raises(RuntimeError, match="密钥"):
        with TestClient(create_app(settings)):
            pass
    assert (key.read_bytes() if key.exists() else None) == before


def test_validation_and_credential_switch(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    with TestClient(app) as client:
        group_id = client.post("/api/v1/host-groups", json={"name": "示例"}).json()["id"]
        body = host_body(group_id)
        invalid = {**body, "port": 0, "password": {"secret": "must-not-echo"}}
        response = client.post("/api/v1/hosts", json=invalid)
        assert response.status_code == 422
        assert "must-not-echo" not in response.text
        assert all("input" not in item for item in response.json()["detail"])
        for invalid_address in ("999.999.999.999", "host;rm -rf /", "bad host"):
            assert client.post("/api/v1/hosts", json={**body, "address": invalid_address}).status_code == 422
        assert client.post("/api/v1/hosts", json={**body, "group_id": 999}).status_code == 404
        body.pop("password")
        assert client.post("/api/v1/hosts", json=body).status_code == 422
        body.update(auth_type="key", key_path="/example/key")
        host_id = client.post("/api/v1/hosts", json=body).json()["id"]
        body["version"] = 1
        body.update(auth_type="password", key_path=None)
        assert client.put(f"/api/v1/hosts/{host_id}", json=body).status_code == 422
        with app.state.sessions() as session:
            assert session.scalar(select(Host.auth_type)) == "key"
