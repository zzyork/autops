from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.ai_models import AIConnection, AISession
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models import Host, HostGroup, JumpHost, SSHKey
from backend.app.schemas.pagination import MAX_PAGE

PREFIX = "/api/v1"
LISTS = ("hosts", "host-groups", "jump-hosts", "ssh-keys", "ai/connections", "ai/sessions")


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(Settings(data_dir=tmp_path / "data", _env_file=None))
    with TestClient(app) as test_client:
        yield test_client


def test_asset_pages_filters_and_legacy_arrays(client: TestClient) -> None:
    with client.app.state.sessions() as db:
        groups = [HostGroup(name=f"group-{index}") for index in range(12)]
        db.add_all(groups)
        db.flush()
        db.add_all(Host(name=f"host-{index}" if index != 22 else "needle-host",
                        address=f"192.0.2.{index + 1}", group_id=groups[index % 2].id,
                        username="admin", port=22, auth_type="password", key_path=None,
                        password_encrypted="host-secret" if index == 22 else None, vip=None,
                        jump_host_id=None) for index in range(23))
        db.add_all(JumpHost(name=f"jump-{index}" if index != 11 else "needle-jump",
                            address=f"jump-{index}.example", username="admin", port=22,
                            auth_type="password", key_path=None, password_encrypted="jump-secret")
                   for index in range(12))
        db.add_all(SSHKey(name=f"key-{index}" if index != 11 else "needle-key",
                          private_key_encrypted="key-secret", public_key="ssh-ed25519 public",
                          key_type="ed25519", fingerprint=f"fingerprint-{index}") for index in range(12))
        db.commit()

    for name, total, ascending in (("hosts", 23, False), ("host-groups", 12, True),
                                   ("jump-hosts", 12, False), ("ssh-keys", 12, False)):
        url = f"{PREFIX}/{name}"
        legacy = client.get(url).json()
        assert isinstance(legacy, list) and len(legacy) == total
        assert client.get(url, params={"page_size": 10}).json() == legacy
        paged_items = [{field: value for field, value in item.items() if field != "public_key"}
                       for item in legacy] if name == "ssh-keys" else legacy
        first = client.get(url, params={"page": 1}).json()
        assert first == {"items": paged_items[:10], "total": total}
        second = client.get(url, params={"page": 2, "page_size": 10}).json()
        assert second == {"items": paged_items[10:20], "total": total}
        assert client.get(url, params={"page": 1, "page_size": 20}).json() == {
            "items": paged_items[:20], "total": total,
        }
        assert client.get(url, params={"page": 1, "page_size": 50}).json() == {"items": paged_items, "total": total}
        assert client.get(url, params={"page": 1, "page_size": 100}).json() == {
            "items": paged_items, "total": total,
        }
        assert client.get(url, params={"page": 999, "page_size": 50}).json() == {"items": [], "total": total}
        assert [item["id"] for item in legacy] == sorted((item["id"] for item in legacy), reverse=not ascending)
        assert "secret" not in str(first)
        assert "secret" not in str(legacy)
        if name == "ssh-keys":
            assert all("public_key" not in item for item in first["items"])
            assert legacy[0]["public_key"] == "ssh-ed25519 public"
            assert client.get(f"{url}/{legacy[0]['id']}").json() == legacy[0]

    hosts = f"{PREFIX}/hosts"
    group_id = client.get(f"{PREFIX}/host-groups").json()[0]["id"]
    filtered = client.get(hosts, params={"page": 1, "group_id": group_id, "q": " host- "}).json()
    expected = client.get(hosts, params={"group_id": group_id, "q": " host- "}).json()
    assert filtered == {"items": expected[:10], "total": len(expected)}
    assert client.get(hosts, params={"page": 2, "page_size": 10, "group_id": group_id, "q": " host- "}).json() == {
        "items": expected[10:], "total": len(expected),
    }
    other_group_id = client.get(f"{PREFIX}/host-groups").json()[1]["id"]
    assert client.get(hosts, params={"page": 1, "q": " needle ", "group_id": other_group_id}).json() == {
        "items": [], "total": 0,
    }
    assert client.get(hosts, params={"page": 1, "q": "needle"}).json()["total"] == 1
    for name in ("jump-hosts", "ssh-keys"):
        url = f"{PREFIX}/{name}"
        expected = client.get(url, params={"q": "needle"}).json()
        if name == "ssh-keys":
            expected = [{field: value for field, value in item.items() if field != "public_key"}
                        for item in expected]
        assert client.get(url, params={"page": 1, "q": "needle"}).json() == {
            "items": expected, "total": 1,
        }
    assert client.get(f"{PREFIX}/host-groups", params={"page": 1}).json()["items"][0]["host_count"] == 12
    assert client.get(f"{PREFIX}/jump-hosts", params={"page": 1}).json()["items"][0]["host_count"] == 0
    assert client.get(f"{PREFIX}/ssh-keys", params={"page": 1}).json()["items"][0]["host_count"] == 0


def test_ai_pages_keep_legacy_session_cap(client: TestClient) -> None:
    with client.app.state.sessions() as db:
        connections = [AIConnection(name=f"model-{index}", protocol="anthropic", base_url="https://example.com",
                                    model="test", api_key_encrypted="api-secret") for index in range(12)]
        db.add_all(connections)
        db.flush()
        now = datetime.now(timezone.utc)
        db.add_all(AISession(id=str(uuid4()), title=f"chat-{index}", connection_id=connections[0].id,
                             connection_version=1, created_at=now,
                             updated_at=now + timedelta(seconds=index)) for index in range(105))
        db.commit()

    connections_url = f"{PREFIX}/ai/connections"
    legacy_connections = client.get(connections_url).json()
    assert len(legacy_connections) == 12
    assert client.get(connections_url, params={"page_size": 10}).json() == legacy_connections
    assert client.get(connections_url, params={"page": 1}).json() == {
        "items": legacy_connections[:10], "total": 12,
    }
    assert client.get(connections_url, params={"page": 1, "page_size": 20}).json() == {
        "items": legacy_connections, "total": 12,
    }
    assert client.get(connections_url, params={"page": 1, "page_size": 100}).json() == {
        "items": legacy_connections, "total": 12,
    }
    assert client.get(connections_url, params={"page": 2, "page_size": 10}).json() == {
        "items": legacy_connections[10:], "total": 12,
    }
    assert "api-secret" not in str(legacy_connections)
    assert "api_key_encrypted" not in str(client.get(connections_url, params={"page": 1}).json())

    sessions_url = f"{PREFIX}/ai/sessions"
    legacy_sessions = client.get(sessions_url).json()
    assert len(legacy_sessions) == 100
    assert client.get(sessions_url, params={"page_size": 10}).json() == legacy_sessions
    assert client.get(sessions_url, params={"page": 1}).json() == {
        "items": legacy_sessions[:10], "total": 105,
    }
    assert client.get(sessions_url, params={"page": 1, "page_size": 20}).json() == {
        "items": legacy_sessions[:20], "total": 105,
    }
    hundred = client.get(sessions_url, params={"page": 1, "page_size": 100}).json()
    assert hundred == {"items": legacy_sessions, "total": 105}
    assert len(client.get(sessions_url, params={"page": 2, "page_size": 100}).json()["items"]) == 5
    first = client.get(sessions_url, params={"page": 1, "page_size": 50}).json()
    third = client.get(sessions_url, params={"page": 3, "page_size": 50}).json()
    assert first == {"items": legacy_sessions[:50], "total": 105}
    assert len(third["items"]) == 5 and third["total"] == 105
    assert not {item["id"] for item in third["items"]} & {item["id"] for item in legacy_sessions}
    assert client.get(sessions_url, params={"page": 999}).json() == {"items": [], "total": 105}
    assert set(first["items"][0]) == {"id", "title", "connection_id", "created_at", "updated_at"}


@pytest.mark.parametrize("name", LISTS)
@pytest.mark.parametrize("page", [MAX_PAGE + 1, 2**63])
def test_page_above_limit_is_rejected(client: TestClient, name: str, page: int) -> None:
    response = client.get(f"{PREFIX}/{name}", params={"page": page, "page_size": 50})
    assert response.status_code == 422
    assert any(error["loc"] == ["query", "page"] for error in response.json()["detail"])


@pytest.mark.parametrize("name", LISTS)
def test_maximum_page_is_valid(client: TestClient, name: str) -> None:
    assert client.get(f"{PREFIX}/{name}", params={"page": MAX_PAGE, "page_size": 50}).json() == {
        "items": [], "total": 0,
    }


@pytest.mark.parametrize("name", LISTS)
@pytest.mark.parametrize("params,field", [({"page": 0}, "page"), ({"page": -1}, "page"),
                                          ({"page": "oops"}, "page"), ({"page": 1, "page_size": 15}, "page_size"),
                                          ({"page_size": 0}, "page_size"), ({"page_size": 101}, "page_size")])
def test_invalid_list_parameters(client: TestClient, name: str, params: dict, field: str) -> None:
    response = client.get(f"{PREFIX}/{name}", params=params)
    assert response.status_code == 422
    assert any(error["loc"] == ["query", field] for error in response.json()["detail"])
