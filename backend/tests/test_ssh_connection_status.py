import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import paramiko
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text, update
from starlette.requests import Request

from backend.app.api.v1.endpoints import hosts as host_endpoints
from backend.app.api.v1.endpoints import jump_hosts as jump_endpoints
from backend.app.api.v1.endpoints import ssh_keys as key_endpoints
from backend.app.core.config import Settings
from backend.app.core.ssh import HostKeyRequired
from backend.app.core.storage import initialize_storage
from backend.app.connection_models import IdentityChallengeRecord, KnownHostKey
from backend.app.main import create_app
from backend.app.models import Host, HostGroup, JumpHost, SSHKey, utc_now
from backend.app.schemas.assets import HostUpdate
from backend.app.schemas.jump_hosts import JumpHostUpdate
from backend.app.schemas.ssh_keys import SSHKeyUpdate
from backend.app.services import ssh_connections
from backend.app.services import ssh_identities
from backend.app.services.ssh_assets import resolve_plan

TEST_URL = "/api/v1/ssh/connection-tests"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(data_dir=tmp_path / "data", _env_file=None))) as api:
        yield api


def make_host(client: TestClient, address: str = "192.0.2.10", **changes) -> tuple[dict, dict]:
    group = client.post("/api/v1/host-groups", json={"name": address}).json()
    data = {"name": "server", "address": address, "group_id": group["id"],
            "username": "root", "auth_type": "password", "password": "secret", **changes}
    response = client.post("/api/v1/hosts", json=data)
    assert response.status_code == 201, response.text
    return response.json(), data


def test_result_contract_status_and_no_history(client: TestClient, monkeypatch) -> None:
    host, data = make_host(client)
    assert host["connection_status"] == "untested"

    @contextmanager
    def success(*args, **kwargs):
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", success)
    body = {"target_type": "host", "target_id": host["id"], "version": host["version"]}
    assert client.post(TEST_URL, json=body).json() == {"target_type": "host", "target_id": host["id"], "status": "succeeded"}
    current = client.get(f"/api/v1/hosts/{host['id']}").json()
    assert current["connection_status"] == "succeeded"
    assert current["version"] == host["version"] and current["updated_at"] == host["updated_at"]
    assert client.get("/api/v1/hosts").json()[0]["connection_status"] == "succeeded"
    assert client.get(TEST_URL).status_code == 405
    assert client.get(f"{TEST_URL}/123").status_code == 404
    assert client.post(f"{TEST_URL}/123/trust").status_code == 404
    assert client.post(TEST_URL, json={**body, "version": 999}).status_code == 409
    assert client.post(TEST_URL, json={**body, "target_id": 999}).status_code == 404
    assert client.post(TEST_URL, json={**body, "target_type": "other"}).status_code == 422

    renamed = client.put(f"/api/v1/hosts/{host['id']}", json={**data, "name": "renamed", "password": None, "version": host["version"]}).json()
    assert renamed["connection_status"] == "succeeded"
    changed = client.put(f"/api/v1/hosts/{host['id']}", json={**data, "username": "another", "password": "new", "version": renamed["version"]}).json()
    assert changed["connection_status"] == "untested"


def test_failure_and_identity_block_are_not_success(client: TestClient, monkeypatch) -> None:
    host, _ = make_host(client)
    body = {"target_type": "host", "target_id": host["id"], "version": host["version"]}

    @contextmanager
    def blocked(target, jump):
        raise HostKeyRequired(target, paramiko.RSAKey.generate(1024))
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", blocked)
    assert client.post(TEST_URL, json=body).json()["status"] == "awaiting_trust"
    assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "awaiting_trust"

    @contextmanager
    def broken(target, jump):
        raise RuntimeError("unexpected failure")
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", broken)
    assert client.post(TEST_URL, json=body).json()["status"] == "failed"
    assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "failed"


def test_inflight_change_cannot_overwrite_reset_or_reused_id(client: TestClient, monkeypatch) -> None:
    host, data = make_host(client)
    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def wait(target, jump):
        entered.set()
        assert release.wait(5)
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
    body = {"target_type": "host", "target_id": host["id"], "version": host["version"]}
    result = []
    worker = threading.Thread(target=lambda: result.append(client.post(TEST_URL, json=body)))
    worker.start()
    try:
        assert entered.wait(5)
        running = client.get(f"/api/v1/hosts/{host['id']}").json()
        assert running["connection_status"] == "running"
        assert running["version"] == host["version"] and running["updated_at"] == host["updated_at"]
        assert client.post(TEST_URL, json=body).status_code == 409
        edited = client.put(f"/api/v1/hosts/{host['id']}", json={**data, "username": "changed", "password": "new", "version": host["version"]}).json()
        assert edited["connection_status"] == "untested"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert result[0].json()["status"] == "interrupted"
    assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "untested"


def test_deleted_host_id_reuse_does_not_receive_old_result(client: TestClient, monkeypatch) -> None:
    host, data = make_host(client)
    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def wait(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
    response = []
    worker = threading.Thread(target=lambda: response.append(client.post(TEST_URL, json={
        "target_type": "host", "target_id": host["id"], "version": host["version"]})))
    worker.start()
    try:
        assert entered.wait(5)
        assert client.delete(f"/api/v1/hosts/{host['id']}").status_code == 204
        replacement = client.post("/api/v1/hosts", json=data).json()
        assert replacement["id"] == host["id"]
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert response[0].json()["status"] == "interrupted"
    assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "untested"


def test_running_metadata_edit_interrupts_without_resetting_completed_result(client: TestClient, monkeypatch) -> None:
    host, data = make_host(client)
    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def wait(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
    response = []
    worker = threading.Thread(target=lambda: response.append(client.post(TEST_URL, json={
        "target_type": "host", "target_id": host["id"], "version": host["version"]})))
    worker.start()
    try:
        assert entered.wait(5)
        edited = client.put(f"/api/v1/hosts/{host['id']}", json={**data, "name": "renamed",
            "password": None, "version": host["version"]}).json()
        assert edited["connection_status"] == "interrupted"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert response[0].json()["status"] == "interrupted"


@pytest.mark.parametrize("connection_changed", [False, True])
def test_host_edit_with_stale_loaded_status_uses_database_running(client: TestClient, monkeypatch,
                                                                    connection_changed: bool) -> None:
    host, data = make_host(client)

    @contextmanager
    def success(*args, **kwargs):
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", success)
    body = {"target_type": "host", "target_id": host["id"], "version": host["version"]}
    if not connection_changed:
        assert client.post(TEST_URL, json=body).json()["status"] == "succeeded"

    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def wait(*args, **kwargs):
        entered.set()
        assert release.wait(8)
        yield

    with client.app.state.sessions() as editing:
        loaded = editing.get(Host, host["id"])
        assert loaded.connection_status == ("untested" if connection_changed else "succeeded")
        monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(client.post(TEST_URL, json=body)))
        worker.start()
        try:
            assert entered.wait(8)
            assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "running"
            changes = {"username": "changed", "password": "new"} if connection_changed else {"name": "renamed", "password": None}
            edited = host_endpoints.update_host(host["id"], HostUpdate.model_validate({
                **data, **changes, "version": host["version"]}), Request({"type": "http", "app": client.app}), editing)
            assert edited.connection_status == ("untested" if connection_changed else "interrupted")
            assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == edited.connection_status
        finally:
            release.set()
            worker.join(8)
    assert not worker.is_alive()
    assert responses[0].json()["status"] == "interrupted"
    assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == (
        "untested" if connection_changed else "interrupted")


@pytest.mark.parametrize("change_kind", ["version", "jump_snapshot", "broken_config"])
def test_invalidated_test_closes_its_own_running_status(client: TestClient, monkeypatch, change_kind: str) -> None:
    jump = client.post("/api/v1/jump-hosts", json={"name": "jump", "address": "192.0.2.11",
        "username": "root", "auth_type": "password", "password": "secret"}).json()
    host, _ = make_host(client, jump_host_id=jump["id"])
    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def wait(*args, **kwargs):
        entered.set()
        assert release.wait(8)
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
    responses = []
    worker = threading.Thread(target=lambda: responses.append(client.post(TEST_URL, json={
        "target_type": "host", "target_id": host["id"], "version": host["version"]})))
    worker.start()
    try:
        assert entered.wait(8)
        with client.app.state.sessions() as db:
            if change_kind == "version":
                db.execute(update(Host).where(Host.id == host["id"]).values(version=Host.version + 1))
            elif change_kind == "jump_snapshot":
                db.execute(update(JumpHost).where(JumpHost.id == jump["id"]).values(version=JumpHost.version + 1))
            else:
                db.execute(update(JumpHost).where(JumpHost.id == jump["id"]).values(password_encrypted=None))
            db.commit()
        assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "running"
    finally:
        release.set()
        worker.join(8)
    assert not worker.is_alive()
    assert responses[0].json()["status"] == "interrupted"
    current = client.get(f"/api/v1/hosts/{host['id']}").json()
    assert current["connection_status"] == "interrupted"
    if change_kind == "version":
        assert current["version"] == host["version"] + 1
    else:
        assert current["version"] == host["version"] and current["updated_at"] == host["updated_at"]


def test_jump_edit_resets_hosts_but_jump_test_is_ephemeral(client: TestClient, monkeypatch) -> None:
    jump_data = {"name": "gateway", "address": "192.0.2.11", "username": "root",
                 "auth_type": "password", "password": "secret"}
    jump = client.post("/api/v1/jump-hosts", json=jump_data).json()
    host, _ = make_host(client, jump_host_id=jump["id"])

    @contextmanager
    def success(*args, **kwargs):
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", success)
    assert client.post(TEST_URL, json={"target_type": "host", "target_id": host["id"], "version": host["version"]}).json()["status"] == "succeeded"
    assert client.post(TEST_URL, json={"target_type": "jump_host", "target_id": jump["id"], "version": jump["version"]}).json() == {
        "target_type": "jump_host", "target_id": jump["id"], "status": "succeeded"}
    assert "connection_status" not in client.get(f"/api/v1/jump-hosts/{jump['id']}").json()
    edited = client.put(f"/api/v1/jump-hosts/{jump['id']}", json={**jump_data, "name": "renamed", "password": None, "version": jump["version"]})
    assert edited.status_code == 200
    assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "succeeded"
    changed = client.put(f"/api/v1/jump-hosts/{jump['id']}", json={**jump_data, "password": "new", "version": edited.json()["version"]})
    assert changed.status_code == 200
    assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "untested"


@pytest.mark.parametrize("connection_changed", [False, True])
def test_jump_edit_with_stale_loaded_asset_checks_database_running(client: TestClient, monkeypatch,
                                                                     connection_changed: bool) -> None:
    jump_data = {"name": "gateway", "address": "192.0.2.11", "username": "root",
                 "auth_type": "password", "password": "secret"}
    jump = client.post("/api/v1/jump-hosts", json=jump_data).json()
    host, _ = make_host(client, jump_host_id=jump["id"])

    @contextmanager
    def success(*args, **kwargs):
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", success)
    body = {"target_type": "host", "target_id": host["id"], "version": host["version"]}
    assert client.post(TEST_URL, json=body).json()["status"] == "succeeded"
    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def wait(*args, **kwargs):
        entered.set()
        assert release.wait(8)
        yield

    with client.app.state.sessions() as editing:
        editing.get(JumpHost, jump["id"])
        monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(client.post(TEST_URL, json=body)))
        worker.start()
        try:
            assert entered.wait(8)
            changes = {"password": "new"} if connection_changed else {"name": "renamed", "password": None}
            jump_endpoints.update_jump_host(jump["id"], JumpHostUpdate.model_validate({
                **jump_data, **changes, "version": jump["version"]}), Request({"type": "http", "app": client.app}), editing)
            assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == (
                "untested" if connection_changed else "interrupted")
        finally:
            release.set()
            worker.join(8)
    assert not worker.is_alive()
    assert responses[0].json()["status"] == "interrupted"


def test_key_replacement_resets_direct_and_jump_hosts(client: TestClient, monkeypatch) -> None:
    def key_material() -> tuple[str, str]:
        key = ed25519.Ed25519PrivateKey.generate()
        return (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode(),
                key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode())

    private, public = key_material()
    key = client.post("/api/v1/ssh-keys", json={"name": "shared", "private_key": private, "public_key": public}).json()
    jump = client.post("/api/v1/jump-hosts", json={"name": "gateway", "address": "192.0.2.11",
        "username": "root", "auth_type": "key", "ssh_key_id": key["id"]}).json()
    direct, _ = make_host(client, ssh_key_id=key["id"], auth_type="key", password=None)
    indirect, _ = make_host(client, "192.0.2.12", jump_host_id=jump["id"])

    @contextmanager
    def success(*args, **kwargs):
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", success)
    for host in (direct, indirect):
        assert client.post(TEST_URL, json={"target_type": "host", "target_id": host["id"], "version": host["version"]}).json()["status"] == "succeeded"
    renamed = client.put(f"/api/v1/ssh-keys/{key['id']}", json={"name": "renamed", "version": key["version"]})
    assert renamed.status_code == 200
    for host in (direct, indirect):
        assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == "succeeded"
    private, public = key_material()
    changed = client.put(f"/api/v1/ssh-keys/{key['id']}", json={"name": "renamed", "version": renamed.json()["version"],
        "private_key": private, "public_key": public})
    assert changed.status_code == 200, changed.text
    for host in (direct, indirect):
        current = client.get(f"/api/v1/hosts/{host['id']}").json()
        assert current["connection_status"] == "untested"
        assert current["version"] == host["version"] and current["updated_at"] == host["updated_at"]


@pytest.mark.parametrize("connection_changed", [False, True])
def test_key_edit_with_stale_loaded_asset_checks_database_running(client: TestClient, monkeypatch,
                                                                    connection_changed: bool) -> None:
    key = ed25519.Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()
    stored = client.post("/api/v1/ssh-keys", json={"name": "key", "private_key": private, "public_key": public}).json()
    host, _ = make_host(client, ssh_key_id=stored["id"], auth_type="key", password=None)

    @contextmanager
    def success(*args, **kwargs):
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", success)
    body = {"target_type": "host", "target_id": host["id"], "version": host["version"]}
    assert client.post(TEST_URL, json=body).json()["status"] == "succeeded"
    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def wait(*args, **kwargs):
        entered.set()
        assert release.wait(8)
        yield

    with client.app.state.sessions() as editing:
        editing.get(SSHKey, stored["id"])
        monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(client.post(TEST_URL, json=body)))
        worker.start()
        try:
            assert entered.wait(8)
            changes = {}
            if connection_changed:
                other = ed25519.Ed25519PrivateKey.generate()
                changes = {"private_key": other.private_bytes(serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
                    "public_key": other.public_key().public_bytes(serialization.Encoding.OpenSSH,
                    serialization.PublicFormat.OpenSSH).decode()}
            key_endpoints.update_key(stored["id"], SSHKeyUpdate.model_validate({
                "name": "renamed", "version": stored["version"], **changes}),
                Request({"type": "http", "app": client.app}), editing)
            assert client.get(f"/api/v1/hosts/{host['id']}").json()["connection_status"] == (
                "untested" if connection_changed else "interrupted")
        finally:
            release.set()
            worker.join(8)
    assert not worker.is_alive()
    assert responses[0].json()["status"] == "interrupted"


def test_independent_identity_trust_resets_host_status(client: TestClient, monkeypatch) -> None:
    host, _ = make_host(client)

    @contextmanager
    def success(*args, **kwargs):
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", success)
    assert client.post(TEST_URL, json={"target_type": "host", "target_id": host["id"], "version": host["version"]}).json()["status"] == "succeeded"
    key = paramiko.RSAKey.generate(1024)
    challenge_id = "00000000-0000-0000-0000-000000000001"
    with client.app.state.sessions() as db:
        plan = resolve_plan(db, client.app.state.cipher, "host", host["id"], identity_probe=True)
        challenge = IdentityChallengeRecord(id=challenge_id, target_type="host",
            target_id=host["id"], target_name=host["name"], address=plan.target.address, port=plan.target.port,
            key_type=key.get_name(), public_key=key.get_base64(), fingerprint="fingerprint",
            previous_fingerprint=None, previous_state=None, jump_state=None, requested_type="host",
            requested_id=host["id"], snapshot=plan.snapshot, expires_at=utc_now() + timedelta(minutes=5), consumed_at=None)
        db.add(challenge)
        db.commit()

    monkeypatch.setattr(ssh_identities, "_probe", lambda *args: (plan, plan.target, key.get_base64(), key.get_name(), "fingerprint"))
    result = client.post(f"/api/v1/ssh/identities/{challenge_id}/trust", json={"confirmed": True})
    assert result.status_code == 200, result.text
    current = client.get(f"/api/v1/hosts/{host['id']}").json()
    assert current["connection_status"] == "untested"
    assert current["version"] == host["version"] and current["updated_at"] == host["updated_at"]
    with client.app.state.sessions() as db:
        assert db.query(KnownHostKey).filter_by(target_type="host", target_id=host["id"]).one().public_key == key.get_base64()


def test_four_slots_duplicate_and_closed(client: TestClient, monkeypatch) -> None:
    entered = threading.Condition()
    release = threading.Event()
    count = 0

    @contextmanager
    def wait(*args, **kwargs):
        nonlocal count
        with entered:
            count += 1
            entered.notify_all()
        assert release.wait(8)
        yield

    monkeypatch.setattr(ssh_connections, "open_ssh_connection", wait)
    targets = []
    for index in range(5):
        jump = client.post("/api/v1/jump-hosts", json={"name": f"jump-{index}", "address": f"192.0.2.{index + 20}",
            "username": "root", "auth_type": "password", "password": "secret"}).json()
        targets.append({"target_type": "jump_host", "target_id": jump["id"], "version": jump["version"]})
    results = []
    workers = [threading.Thread(target=lambda body=body: results.append(client.post(TEST_URL, json=body))) for body in targets[:4]]
    for worker in workers:
        worker.start()
    try:
        with entered:
            assert entered.wait_for(lambda: count == 4, timeout=8)
        assert client.post(TEST_URL, json=targets[0]).status_code == 409
        assert client.post(TEST_URL, json=targets[4]).status_code == 503
    finally:
        release.set()
        for worker in workers:
            worker.join(8)
    assert all(not worker.is_alive() for worker in workers)
    assert len(results) == 4 and all(response.json()["status"] == "succeeded" for response in results)
    client.app.state.connection_tests.close()
    assert client.post(TEST_URL, json=targets[4]).status_code == 503


def test_migration_drops_history_and_interrupts_running(tmp_path: Path) -> None:
    data = tmp_path / "data"
    engine, sessions, cipher = initialize_storage(data)
    with sessions() as db:
        db.execute(text("CREATE TABLE ssh_connection_tests (id VARCHAR PRIMARY KEY)"))
        db.execute(text("INSERT INTO ssh_connection_tests (id) VALUES ('old')"))
        db.add(HostGroup(id=1, name="group"))
        db.flush()
        db.add(Host(name="server", address="192.0.2.10", group_id=1, username="root", port=22,
                    auth_type="password", password_encrypted=cipher.encrypt(b"secret").decode(), connection_status="running"))
        db.commit()
    engine.dispose()
    upgraded, sessions, _ = initialize_storage(data)
    try:
        assert "ssh_connection_tests" not in inspect(upgraded).get_table_names()
        assert {"known_host_keys", "ssh_identity_challenges"} <= set(inspect(upgraded).get_table_names())
        with sessions() as db:
            assert db.get(Host, 1).connection_status == "interrupted"
    finally:
        upgraded.dispose()


def test_migration_adds_status_to_legacy_hosts(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    legacy = create_engine(f"sqlite:///{(data / 'assets.db').as_posix()}")
    with legacy.begin() as db:
        db.execute(text("CREATE TABLE hosts (id INTEGER PRIMARY KEY, password_encrypted VARCHAR)"))
        db.execute(text("INSERT INTO hosts (id) VALUES (1)"))
    legacy.dispose()
    engine, sessions, _ = initialize_storage(data)
    try:
        assert "connection_status" in {column["name"] for column in inspect(engine).get_columns("hosts")}
        with engine.connect() as db:
            assert db.scalar(text("SELECT connection_status FROM hosts WHERE id = 1")) == "untested"
    finally:
        engine.dispose()
