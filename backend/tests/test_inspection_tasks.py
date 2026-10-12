"""Local, isolated API and persistence checks for the first inspection batch."""

import importlib
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Lock, current_thread
from types import SimpleNamespace
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from backend.app.core import config as app_config
from backend.app.core.ssh import HostKeyRequired, SSHConnectionError
from backend.app.core.ssh_commands import CommandExecutionError
from backend.app.core.storage import initialize_storage
from backend.app.inspection_models import InspectionCheckRun, InspectionHostRun, InspectionTask
from backend.app.models import Host, SSHKey
from backend.app.repositories import inspections as repository
from backend.app.schemas.inspections import CheckPayload, Finding, InspectionConfig, InspectionInput, Metric, ResultTable
from backend.app.services import inspection_tasks
from backend.app.services import inspection_rules
from backend.app.services.inspection_checks import InspectionCheckError

ROOT = "/api/v1/inspections"
CHECKS = ["server_info", "system_resources", "service_status", "network_info"]
SECRET = "only-in-encrypted-assets-9837"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = app_config.Settings(data_dir=tmp_path / "data", _env_file=None)
    # Importing main constructs its module-level app; prevent that import from reading backend/.env.
    monkeypatch.setattr(app_config, "get_settings", lambda: settings)
    main = importlib.import_module("backend.app.main")

    @contextmanager
    def no_network(*args, **kwargs):
        raise AssertionError("inspection test attempted a real SSH connection")
        yield

    monkeypatch.setattr(inspection_tasks, "open_ssh_connection", no_network)
    with TestClient(main.create_app(settings)) as test_client:
        yield test_client


def add_host(client: TestClient, index: int = 1, *, group_id: int | None = None,
             name: str | None = None, ssh_key_id: int | None = None) -> dict:
    if group_id is None:
        response = client.post("/api/v1/host-groups", json={"name": "production"})
        assert response.status_code == 201
        group_id = response.json()["id"]
    data = {"name": name or f"host-{index}", "address": f"192.0.2.{index}",
            "group_id": group_id, "username": "operator", "port": 22,
            "auth_type": "key" if ssh_key_id else "password"}
    if ssh_key_id:
        data["ssh_key_id"] = ssh_key_id
    else:
        data["password"] = SECRET
    response = client.post("/api/v1/hosts", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def submit(client: TestClient, hosts: list[dict], checks: list[str] | None = None,
           **options) -> dict:
    response = client.post(f"{ROOT}/tasks", json={
        "name": options.pop("name", "daily inspection"),
        "hosts": [{"id": host["id"], "version": host["version"]} for host in hosts],
        "checks": checks or CHECKS, **options,
    })
    assert response.status_code == 202, response.text
    return response.json()


def wait_for(client: TestClient, task_id: str, statuses: tuple[str, ...] = (
        "completed", "partial", "failed", "interrupted")) -> dict:
    until = time.monotonic() + 5
    while time.monotonic() < until:
        response = client.get(f"{ROOT}/tasks/{task_id}")
        assert response.status_code == 200, response.text
        detail = response.json()
        if detail["status"] in statuses:
            return detail
        time.sleep(0.02)
    pytest.fail(f"inspection {task_id} did not reach {statuses}")


def fake_connection(monkeypatch: pytest.MonkeyPatch, behavior=None):
    calls = []

    @contextmanager
    def open_mock(target, jump, *, timeout_seconds):
        calls.append((target, jump, timeout_seconds))
        if behavior is not None:
            behavior(target)
        yield object()

    monkeypatch.setattr(inspection_tasks, "open_ssh_connection", open_mock)
    return calls


def test_catalog_completed_critical_and_report_api(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = client.get(f"{ROOT}/catalog")
    assert catalog.status_code == 200
    assert [check["id"] for check in catalog.json()["checks"]] == CHECKS
    assert catalog.json()["defaults"]["thresholds"]["cpu_warning"] == 80
    host = add_host(client)
    connections = fake_connection(monkeypatch)
    observed = []

    def collect(check_id, runner, config):
        observed.append((check_id, config.command_timeout_seconds, config.thresholds.cpu_critical,
                         [service.name for service in config.services]))
        return CheckPayload(conclusion="critical" if check_id == "system_resources" else "normal",
                            metrics=[Metric(name="CPU", value=99, unit="%")],
                            findings=[Finding(severity="critical", message="CPU high")] if check_id == "system_resources" else [])

    monkeypatch.setattr(inspection_tasks, "collect", collect)
    created = submit(client, [host])
    defaults = catalog.json()["defaults"]
    assert created["config"] == defaults
    assert created["host_count"] == 1
    result = wait_for(client, created["id"])
    assert result["status"] == result["hosts"][0]["status"] == "completed"
    assert (result["completed_hosts"], result["failed_hosts"]) == (1, 0)
    assert [c["status"] for c in result["hosts"][0]["checks"]] == ["completed"] * 4
    assert [c["conclusion"] for c in result["hosts"][0]["checks"]] == ["normal", "critical", "normal", "normal"]
    assert result["config"] == defaults
    assert observed == [(check, defaults["command_timeout_seconds"], defaults["thresholds"]["cpu_critical"],
                         [service["name"] for service in defaults["services"]]) for check in CHECKS]
    assert connections[0][2] == 180
    assert connections[0][0].password == SECRET
    assert result["hosts"][0]["group_name"] == "production"
    assert result["created_at"].endswith("Z")
    assert SECRET not in str(result) and "asset_snapshot" not in str(result)
    report = client.get(f"{ROOT}/tasks/{created['id']}/report")
    assert report.status_code == 200
    assert report.json()["filename"] == f"inspection-{created['id']}.md"
    assert "严重" in report.json()["content"]
    assert SECRET not in report.text


def test_catalog_persists_and_tasks_keep_rule_snapshots(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    fake_connection(monkeypatch)
    observed = []

    def collect(_check_id, _runner, config):
        observed.append((config.command_timeout_seconds, config.services[0].name))
        return CheckPayload()

    monkeypatch.setattr(inspection_tasks, "collect", collect)
    url = f"{ROOT}/catalog"
    first = client.get(url).json()
    assert not (client.app.state.data_dir / "inspection-rules.json").exists()
    custom = {**first["defaults"], "command_timeout_seconds": 12, "services": [
        {"name": "web", "candidates": ["nginx"], "required": True}]}
    saved = client.put(url, json=custom)
    assert saved.status_code == 200
    assert saved.json() == {**first, "defaults": custom}
    assert client.get(url).json() == saved.json()
    old = submit(client, [host], ["service_status"])
    wait_for(client, old["id"])
    updated = {**custom, "command_timeout_seconds": 14}
    assert client.put(url, json=updated).status_code == 200
    new = submit(client, [host], ["service_status"])
    wait_for(client, new["id"])
    assert client.get(f"{ROOT}/tasks/{old['id']}").json()["config"] == custom
    assert client.get(f"{ROOT}/tasks/{new['id']}").json()["config"] == updated
    assert observed == [(12, "web"), (14, "web")]
    assert inspection_rules.load_rules(client.app.state.data_dir).model_dump(mode="json") == updated


@pytest.mark.parametrize("change", [
    {"thresholds": {"cpu_warning": 96, "cpu_critical": 95}},
    {"services": [{"name": "web", "candidates": ["nginx;id"]}]},
    {"host_timeout_seconds": 9},
    {"unknown": 1},
])
def test_catalog_rejects_invalid_rules(client: TestClient, change: dict) -> None:
    defaults = client.get(f"{ROOT}/catalog").json()["defaults"]
    assert client.put(f"{ROOT}/catalog", json={**defaults, **change}).status_code == 422
    assert client.get(f"{ROOT}/catalog").json()["defaults"] == defaults
    assert not (client.app.state.data_dir / "inspection-rules.json").exists()


def test_catalog_rejects_incomplete_save_without_overwriting_rules(client: TestClient) -> None:
    url = f"{ROOT}/catalog"
    defaults = client.get(url).json()["defaults"]
    saved = {**defaults, "command_timeout_seconds": 12, "services": [
        {"name": "web", "candidates": ["nginx"], "required": True}]}
    assert client.put(url, json=saved).status_code == 200
    path = client.app.state.data_dir / "inspection-rules.json"
    existing = path.read_bytes()

    incomplete = [{}]
    incomplete.extend({key: value for key, value in saved.items() if key != missing} for missing in saved)
    incomplete.extend({**saved, "thresholds": {key: value for key, value in saved["thresholds"].items()
                                               if key != missing}} for missing in saved["thresholds"])
    incomplete.append({**saved, "services": [{"name": "web", "candidates": ["nginx"]}]})
    for body in incomplete:
        response = client.put(url, json=body)
        assert response.status_code == 422, (body, response.text)
        assert path.read_bytes() == existing
        assert client.get(url).json()["defaults"] == saved
    assert client.put(url, content=b"", headers={"Content-Type": "application/json"}).status_code == 422
    assert path.read_bytes() == existing


def test_rules_corruption_and_atomic_write_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = client.app.state.data_dir
    path = data_dir / "inspection-rules.json"
    original = client.get(f"{ROOT}/catalog").json()["defaults"]
    assert client.put(f"{ROOT}/catalog", json=original).status_code == 200
    existing = path.read_bytes()

    def fail_replace(_source, _target):
        raise OSError("test-only disk failure")

    with monkeypatch.context() as injection:
        injection.setattr(inspection_rules.os, "replace", fail_replace)
        with pytest.raises(OSError, match="test-only disk failure"):
            client.put(f"{ROOT}/catalog", json={**original, "command_timeout_seconds": 15})
    assert path.read_bytes() == existing
    assert sorted(item.name for item in data_dir.iterdir()) == ["assets.db", "inspection-rules.json", "secrets"]
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="巡检规则文件损坏"):
        client.get(f"{ROOT}/catalog")
    host = add_host(client)
    with pytest.raises(RuntimeError, match="巡检规则文件损坏"):
        submit(client, [host], ["server_info"])
    assert client.get(f"{ROOT}/tasks").json()["total"] == 0
    path.write_text('{"host_timeout_seconds": 0}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="巡检规则文件损坏"):
        client.get(f"{ROOT}/catalog")


def test_delete_terminal_task_cascades_and_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    fake_connection(monkeypatch)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload())
    task = submit(client, [host], ["server_info", "network_info"])
    detail = wait_for(client, task["id"])
    run_id = detail["hosts"][0]["id"]
    url = f"{ROOT}/tasks/{task['id']}"
    deleted = client.delete(url)
    assert deleted.status_code == 204 and not deleted.content
    assert client.delete(url).status_code == 404
    assert client.get(url).status_code == 404
    assert client.get(f"{url}/report").status_code == 404
    assert client.get(f"{ROOT}/tasks").json()["total"] == 0
    with client.app.state.sessions() as session:
        assert session.get(InspectionTask, task["id"]) is None
        assert session.get(InspectionHostRun, run_id) is None
        assert session.scalars(select(InspectionCheckRun).where(InspectionCheckRun.host_run_id == run_id)).all() == []
    assert client.delete(f"{ROOT}/tasks/not-a-uuid").status_code == 422


@pytest.mark.parametrize("status", ["partial", "failed", "interrupted"])
def test_delete_other_terminal_statuses(client: TestClient, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    host = add_host(client)
    fake_connection(monkeypatch)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload())
    task = submit(client, [host], ["server_info"])
    wait_for(client, task["id"])
    with client.app.state.sessions() as session:
        repository.get_task(session, task["id"]).status = status
        session.commit()
    assert client.delete(f"{ROOT}/tasks/{task['id']}").status_code == 204
    assert client.get(f"{ROOT}/tasks").json()["total"] == 0


def test_delete_running_and_unavailable_task(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    entered, release = Event(), Event()
    fake_connection(monkeypatch, lambda _target: (entered.set(), release.wait(5)))
    task = submit(client, [host], ["server_info"])
    url = f"{ROOT}/tasks/{task['id']}"
    try:
        assert entered.wait(3)
        assert client.delete(url).status_code == 409
        assert client.get(url).status_code == 200
        client.app.state.inspections.persistence_failed.set()
        assert client.delete(url).status_code == 503
    finally:
        client.app.state.inspections.persistence_failed.clear()
        release.set()
    wait_for(client, task["id"])
    assert client.delete(url).status_code == 204


def test_history_display_filters_without_changing_stored_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    fake_connection(monkeypatch)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload())
    task = submit(client, [host], ["service_status", "network_info"])
    wait_for(client, task["id"])
    service = CheckPayload(conclusion="warning", findings=[Finding(severity="warning", message="必需服务 web 未安装")],
                           tables=[ResultTable(name="服务状态", columns=["服务", "匹配单元", "加载状态", "运行状态", "必需"],
                                               rows=[["web", "未安装", "not-found", "不适用", "是"],
                                                     ["ssh", "sshd", "loaded", "inactive", "否"]])]).model_dump(mode="json")
    network = CheckPayload(metrics=[Metric(name="本机监听数量", value=6)],
                           tables=[ResultTable(name="本机监听 TCP/UDP", columns=["协议", "状态", "本地地址"],
                                               rows=[["TCP", "LISTEN", "127.2.3.4:80"],
                                                     ["TCP", "LISTEN", "[::ffff:127.0.0.1]:81"],
                                                     ["TCP", "LISTEN", "[::1%lo]:83"],
                                                     ["TCP", "LISTEN", "[::ffff:127.0.0.1%lo]:84"],
                                                     ["TCP", "LISTEN", "[::]:82"],
                                                     ["UDP", "UNCONN", "192.0.2.1:53"]])]).model_dump(mode="json")
    with client.app.state.sessions() as session:
        checks = repository.get_task(session, task["id"]).hosts[0].checks
        checks[0].payload, checks[1].payload = service, network
        session.commit()
    url = f"{ROOT}/tasks/{task['id']}"
    detail = client.get(url).json()
    shown = detail["hosts"][0]["checks"]
    assert shown[0]["payload"]["tables"][0]["rows"] == [["ssh", "sshd", "loaded", "inactive", "否"]]
    assert shown[0]["payload"]["findings"] == service["findings"]
    assert [row[2] for row in shown[1]["payload"]["tables"][0]["rows"]] == ["[::]:82", "192.0.2.1:53"]
    assert shown[1]["payload"]["metrics"][0]["value"] == 2
    report = client.get(f"{url}/report").json()["content"]
    assert "未安装" in report and "inactive" in report
    assert "127.2.3.4" not in report and "127.0.0.1" not in report and "::1%lo" not in report
    with client.app.state.sessions() as session:
        stored = repository.get_task(session, task["id"]).hosts[0].checks
        assert stored[0].payload == service and stored[1].payload == network


def test_multi_host_partial_and_connection_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    good = add_host(client)
    bad = add_host(client, 2, group_id=good["group_id"])

    def connect(target):
        if target.address == bad["address"]:
            raise SSHConnectionError("connection", "target", "internal network detail")

    fake_connection(monkeypatch, connect)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload(conclusion="normal"))
    detail = wait_for(client, submit(client, [good, bad], ["server_info", "network_info"])["id"])
    assert detail["status"] == "partial"
    assert (detail["completed_hosts"], detail["failed_hosts"]) == (2, 1)
    assert [run["status"] for run in detail["hosts"]] == ["completed", "failed"]
    assert detail["hosts"][1]["failure_code"] == "connection"
    assert [c["status"] for c in detail["hosts"][1]["checks"]] == ["skipped", "skipped"]
    assert "internal network detail" not in str(detail)


def test_report_endpoint_uses_id_filename_for_untrusted_names(client: TestClient,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client, name="<img src=x onerror=alert(1)>")
    fake_connection(monkeypatch)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload(tables=[
        ResultTable(name="unsafe | table", columns=["key", "value"], rows=[["<script>alert(1)</script>", "a|b"]])]))
    task = submit(client, [host], ["server_info"], name="../../<script>alert(1)</script>")
    wait_for(client, task["id"])
    report = client.get(f"{ROOT}/tasks/{task['id']}/report")
    assert report.status_code == 200
    assert report.json()["filename"] == f"inspection-{task['id']}.md"
    content = report.json()["content"]
    assert "<script>" not in content and "<img" not in content
    assert "&lt;script&gt;" in content and "&lt;img" in content
    assert "\\|" in content


@pytest.mark.parametrize("failure,expected,remaining", [
    (InspectionCheckError("tool_missing"), "tool_missing", "completed"),
    (InspectionCheckError("no_monitored_disks"), "no_monitored_disks", "completed"),
    (CommandExecutionError("timeout", True), "timeout", "completed"),
    (CommandExecutionError("connection", False), "connection", "skipped"),
])
def test_independent_check_failure_and_disconnect(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                                   failure: Exception, expected: str, remaining: str) -> None:
    host = add_host(client)
    fake_connection(monkeypatch)
    called = []

    def collect(check_id, *_):
        called.append(check_id)
        if check_id == "system_resources":
            raise failure
        return CheckPayload(conclusion="normal")

    monkeypatch.setattr(inspection_tasks, "collect", collect)
    detail = wait_for(client, submit(client, [host], ["server_info", "system_resources", "network_info"])["id"])
    checks = detail["hosts"][0]["checks"]
    assert detail["status"] == detail["hosts"][0]["status"] == "partial"
    assert [c["status"] for c in checks] == ["completed", "failed", remaining]
    assert checks[1]["error_code"] == expected
    assert called == (["server_info", "system_resources", "network_info"] if remaining == "completed" else
                      ["server_info", "system_resources"])
    assert detail["hosts"][0]["failure_code"] == ("connection" if remaining == "skipped" else "check_failed")


def test_duplicate_queue_and_running_report(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    entered, release = Event(), Event()

    def block(_target):
        entered.set()
        assert release.wait(5)

    fake_connection(monkeypatch, block)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload())
    first = submit(client, [host], ["server_info"])
    try:
        assert entered.wait(3)
        assert client.get(f"{ROOT}/tasks/{first['id']}/report").status_code == 409
        duplicate = client.post(f"{ROOT}/tasks", json={"name": "duplicate", "hosts": [
            {"id": host["id"], "version": host["version"]}], "checks": ["server_info"]})
        assert duplicate.status_code == 409
        assert client.get(f"{ROOT}/tasks").json()["total"] == 1
    finally:
        release.set()
    assert wait_for(client, first["id"])["status"] == "completed"


@pytest.mark.parametrize("change", ["host", "credential"])
def test_queued_asset_or_credential_version_change(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                                   change: str) -> None:
    with client.app.state.sessions() as session:
        key = SSHKey(name="local test key", private_key_encrypted=client.app.state.cipher.encrypt(b"test-only-key").decode(),
                     public_key="test-only", key_type="ssh-ed25519", fingerprint="test-only")
        session.add(key)
        session.commit()
        key_id = key.id
    first = add_host(client)
    hosts = [first] + [add_host(client, i, group_id=first["group_id"]) for i in range(2, 5)]
    last = add_host(client, 5, group_id=first["group_id"], ssh_key_id=key_id)
    hosts.append(last)
    entered, release = Event(), Event()
    lock = Lock()
    count = [0]

    def block(_target):
        with lock:
            count[0] += 1
            if count[0] == 4:
                entered.set()
        assert release.wait(5)

    calls = fake_connection(monkeypatch, block)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload())
    task = submit(client, hosts, ["server_info"])
    try:
        assert entered.wait(3)
        if change == "host":
            with client.app.state.sessions() as session:
                record = session.get(Host, last["id"])
                record.name = "renamed while queued"
                session.commit()
        else:
            with client.app.state.sessions() as session:
                record = session.get(SSHKey, key_id)
                record.private_key_encrypted = client.app.state.cipher.encrypt(b"rotated-test-only-key").decode()
                session.commit()
    finally:
        release.set()
    detail = wait_for(client, task["id"])
    assert detail["status"] == "partial"
    assert (detail["completed_hosts"], detail["failed_hosts"]) == (5, 1)
    assert detail["hosts"][-1]["host_name"] == last["name"]
    assert detail["hosts"][-1]["failure_code"] == "asset_changed"
    assert detail["hosts"][-1]["checks"][0]["status"] == "skipped"
    assert len(calls) == 4
    assert SECRET not in str(detail) and "rotated-test-only-key" not in str(detail)


def test_unknown_host_key_is_not_trusted(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)

    def untrusted(target):
        raise HostKeyRequired(target, SimpleNamespace(get_base64=lambda: "untrusted-key-material-9837",
                                                       get_name=lambda: "ssh-ed25519",
                                                       asbytes=lambda: b"untrusted-key-material-9837"))

    fake_connection(monkeypatch, untrusted)
    task = submit(client, [host], ["server_info"])
    detail = wait_for(client, task["id"])
    assert detail["status"] == "failed"
    assert detail["hosts"][0]["failure_code"] == "host_key_required"
    assert detail["hosts"][0]["checks"][0]["status"] == "skipped"
    assert "untrusted-key-material-9837" not in str(detail)
    with client.app.state.sessions() as session:
        from backend.app.connection_models import KnownHostKey
        assert session.scalars(select(KnownHostKey)).all() == []


@pytest.mark.parametrize("config", [
    {},
    {"thresholds": {"cpu_warning": 70}},
    {"command_timeout_seconds": 12},
    {"services": [{"name": "web", "candidates": ["nginx"], "required": True}]},
    {"thresholds": {"cpu_warning": 96, "cpu_critical": 95}},
    {"thresholds": {"mem_warning": -1}},
    {"thresholds": {"disk_critical": "NaN"}},
    {"thresholds": {"swap_warning": "Infinity"}},
    {"services": [{"name": "web", "candidates": ["nginx;shutdown"]}]},
    {"services": [{"name": "web", "candidates": ["nginx", "nginx"]}]},
    {"services": [{"name": "web", "candidates": ["nginx"]}, {"name": "web", "candidates": ["httpd"]}]},
    {"command_timeout_seconds": 31, "host_timeout_seconds": 10},
    {"extra_option": True},
])
def test_task_config_override_rejected(client: TestClient, config: dict) -> None:
    host = add_host(client)
    response = client.post(f"{ROOT}/tasks", json={"name": "invalid", "hosts": [
        {"id": host["id"], "version": host["version"]}], "checks": ["service_status"], "config": config})
    assert response.status_code == 422
    assert client.get(f"{ROOT}/tasks").json()["total"] == 0


@pytest.mark.parametrize("changes", [
    {"name": "  "}, {"checks": ["server_info", "server_info"]}, {"checks": ["unknown"]},
    {"hosts": []}, {"hosts": [{"id": 1, "version": 1}, {"id": 1, "version": 1}]},
])
def test_invalid_selection_rejected(client: TestClient, changes: dict) -> None:
    host = add_host(client)
    data = {"name": "valid", "hosts": [{"id": host["id"], "version": host["version"]}], "checks": ["server_info"]}
    assert client.post(f"{ROOT}/tasks", json={**data, **changes}).status_code == 422
    assert client.get(f"{ROOT}/tasks").json()["total"] == 0


def test_missing_and_stale_host_and_page_bounds(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    data = {"name": "first", "hosts": [{"id": host["id"], "version": host["version"]}], "checks": ["server_info"]}
    for selected, code in [({"id": 999, "version": 1}, 404), ({"id": host["id"], "version": host["version"] + 1}, 409)]:
        assert client.post(f"{ROOT}/tasks", json={**data, "hosts": [selected]}).status_code == code
    fake_connection(monkeypatch)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload())
    for index in range(3):
        task = client.post(f"{ROOT}/tasks", json={**data, "name": f"task-{index}"})
        assert task.status_code == 202
        wait_for(client, task.json()["id"])
    page = client.get(f"{ROOT}/tasks", params={"limit": 1, "offset": 1})
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 1
    assert "hosts" not in page.json()["items"][0]
    empty = client.get(f"{ROOT}/tasks", params={"offset": 100001})
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "total": 3}
    for params in ({"limit": 0}, {"limit": 51}, {"offset": -1}):
        assert client.get(f"{ROOT}/tasks", params=params).status_code == 422
    assert client.get(f"{ROOT}/tasks/not-a-uuid").status_code == 422
    assert client.get(f"{ROOT}/tasks/00000000-0000-0000-0000-000000000001").status_code == 404
    assert client.get(f"{ROOT}/tasks/00000000-0000-0000-0000-000000000001/report").status_code == 404


def test_restart_interrupts_only_unfinished_checks(client: TestClient) -> None:
    host = add_host(client)
    data = InspectionInput(name="recover", hosts=[{"id": host["id"], "version": host["version"]}], checks=CHECKS[:3])
    with client.app.state.sessions() as session:
        task = repository.create_task(session, data, [{"host_id": host["id"], "host_name": host["name"],
            "address": host["address"], "port": 22, "username": host["username"], "group_name": "production",
            "asset_snapshot": "test-only-snapshot"}], InspectionConfig())
        task.status = "running"
        run = task.hosts[0]
        run.status = "running"
        run.checks[0].status = "completed"
        run.checks[0].conclusion = "critical"
        run.checks[0].payload = CheckPayload(conclusion="critical", metrics=[Metric(name="kept", value=1)]).model_dump(mode="json")
        run.checks[1].status = "running"
        task_id = task.id
        session.commit()
    restarted = inspection_tasks.InspectionManager(client.app.state.sessions, client.app.state.cipher)
    try:
        detail = client.get(f"{ROOT}/tasks/{task_id}").json()
        assert detail["status"] == detail["hosts"][0]["status"] == "interrupted"
        checks = detail["hosts"][0]["checks"]
        assert [item["status"] for item in checks] == ["completed", "interrupted", "interrupted"]
        assert checks[0]["conclusion"] == "critical"
        assert checks[0]["payload"]["metrics"][0]["name"] == "kept"
        assert all(item["error_code"] == "interrupted" for item in checks[1:])
        assert detail["completed_hosts"] == detail["failed_hosts"] == 1
    finally:
        restarted.close()


@pytest.mark.parametrize("failure_point", ["summarize", "commit"])
def test_persistence_failure_blocks_api_until_restart(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                                      failure_point: str) -> None:
    host = add_host(client)
    manager = client.app.state.inspections
    fault = Event()
    original_commit = Session.commit

    def fail_commit_once(session):
        if current_thread().name.startswith("inspection") and not fault.is_set():
            fault.set()
            raise RuntimeError("test-only persistence fault")
        return original_commit(session)

    def fail_summary_once(session, task_id):
        fault.set()
        raise RuntimeError("test-only summary fault")

    with monkeypatch.context() as injection:
        if failure_point == "commit":
            injection.setattr(Session, "commit", fail_commit_once)
        else:
            injection.setattr(repository, "summarize_task", fail_summary_once)
        task = submit(client, [host], ["server_info", "system_resources"])
        assert fault.wait(3)
        assert manager.persistence_failed.wait(3)
        until = time.monotonic() + 3
        while manager.active and time.monotonic() < until:
            time.sleep(0.01)
        assert not manager.active

    detail_url = f"{ROOT}/tasks/{task['id']}"
    for url in (f"{ROOT}/tasks", detail_url, f"{detail_url}/report"):
        response = client.get(url)
        assert response.status_code == 503, response.text
        assert "hosts" not in response.json()
    rejected = client.post(f"{ROOT}/tasks", json={"name": "after fault", "hosts": [
        {"id": host["id"], "version": host["version"]}], "checks": ["server_info"]})
    assert rejected.status_code == 503
    with client.app.state.sessions() as session:
        stored = repository.get_task(session, task["id"])
        assert stored.status in ("queued", "running")

    restarted = inspection_tasks.InspectionManager(client.app.state.sessions, client.app.state.cipher)
    client.app.state.inspections = restarted
    try:
        assert not restarted.persistence_failed.is_set()
        recovered = client.get(detail_url)
        assert recovered.status_code == 200
        detail = recovered.json()
        assert detail["status"] == detail["hosts"][0]["status"] == "interrupted"
        assert [check["status"] for check in detail["hosts"][0]["checks"]] == ["interrupted", "interrupted"]
        assert client.get(f"{ROOT}/tasks").json()["total"] == 1
        assert client.get(f"{detail_url}/report").status_code == 200
    finally:
        restarted.close()
        client.app.state.inspections = manager


def test_other_host_stops_checks_after_persistence_failure(client: TestClient,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    first = add_host(client)
    second = add_host(client, 2, group_id=first["group_id"])
    manager = client.app.state.inspections
    fault = Event()
    called = []
    fake_connection(monkeypatch, lambda _target: fault.wait(3))
    monkeypatch.setattr(inspection_tasks, "collect", lambda check_id, *_: called.append(check_id) or CheckPayload())
    original_summary = repository.summarize_task

    def fail_first_summary(session, task_id):
        if not fault.is_set():
            fault.set()
            raise RuntimeError("test-only summary fault")
        return original_summary(session, task_id)

    with monkeypatch.context() as injection:
        injection.setattr(repository, "summarize_task", fail_first_summary)
        task = submit(client, [first, second], ["server_info", "network_info"])
        assert manager.persistence_failed.wait(3)
        until = time.monotonic() + 3
        while manager.active and time.monotonic() < until:
            time.sleep(0.01)
        assert not manager.active
    assert called == []
    assert client.get(f"{ROOT}/tasks/{task['id']}").status_code == 503
    with client.app.state.sessions() as session:
        statuses = [host.status for host in repository.get_task(session, task["id"]).hosts]
        assert "interrupted" in statuses
    restarted = inspection_tasks.InspectionManager(client.app.state.sessions, client.app.state.cipher)
    try:
        with client.app.state.sessions() as session:
            recovered = repository.get_task(session, task["id"])
            assert recovered.status == "interrupted"
            assert all(host.status == "interrupted" for host in recovered.hosts)
            assert all(check.status == "interrupted" for host in recovered.hosts for check in host.checks)
    finally:
        restarted.close()


def test_check_commit_failure_poisoned_even_if_final_commit_succeeds(client: TestClient,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    manager = client.app.state.inspections
    fake_connection(monkeypatch)
    monkeypatch.setattr(inspection_tasks, "collect", lambda *_: CheckPayload())
    original_commit = Session.commit
    fault = Event()

    def fail_second_check_commit(session):
        if current_thread().name.startswith("inspection") and not fault.is_set() and any(
            isinstance(record, InspectionCheckRun) and record.check_id == "system_resources"
            and record.status == "completed" for record in session.dirty
        ):
            fault.set()
            raise RuntimeError("test-only check result commit fault")
        return original_commit(session)

    with monkeypatch.context() as injection:
        injection.setattr(Session, "commit", fail_second_check_commit)
        task = submit(client, [host], ["server_info", "system_resources", "network_info"])
        assert fault.wait(3)
        until = time.monotonic() + 3
        while manager.active and time.monotonic() < until:
            time.sleep(0.01)
        assert not manager.active
        with client.app.state.sessions() as session:
            stored = repository.get_task(session, task["id"])
            persisted = (stored.status, stored.hosts[0].status,
                         [check.status for check in stored.hosts[0].checks])
        assert manager.persistence_failed.is_set(), f"check commit failure was swallowed; persisted={persisted}"
    assert client.get(f"{ROOT}/tasks/{task['id']}").status_code == 503


def test_host_deadline_skips_remaining_checks(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    host = add_host(client)
    fake_connection(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(inspection_tasks, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    collected = []

    def collect(check_id, *_):
        collected.append(check_id)
        clock[0] += 181
        return CheckPayload()

    monkeypatch.setattr(inspection_tasks, "collect", collect)
    task = submit(client, [host], ["server_info", "network_info"])
    detail = wait_for(client, task["id"])
    assert detail["status"] == "partial"
    assert [c["status"] for c in detail["hosts"][0]["checks"]] == ["completed", "skipped"]
    assert detail["hosts"][0]["failure_code"] == "timeout"
    assert collected == ["server_info"]


def test_shutdown_rejects_new_work_and_releases_workers(client: TestClient) -> None:
    host = add_host(client)
    manager = client.app.state.inspections
    manager.close()
    assert manager.stopping.is_set() and not manager.active
    response = client.post(f"{ROOT}/tasks", json={"name": "after close", "hosts": [
        {"id": host["id"], "version": host["version"]}], "checks": ["server_info"]})
    assert response.status_code == 503
    assert client.get(f"{ROOT}/tasks").json()["total"] == 0


def test_existing_asset_database_gains_inspection_tables_without_data_loss(tmp_path: Path) -> None:
    data_dir = tmp_path / "old-install"
    engine, sessions, cipher = initialize_storage(data_dir)
    from backend.app.models import HostGroup
    with sessions() as session:
        group = HostGroup(name="existing", remark="unchanged")
        session.add(group)
        session.flush()
        host = Host(name="existing-host", address="192.0.2.33", group_id=group.id, username="operator",
                    port=22, auth_type="password", password_encrypted=cipher.encrypt(SECRET.encode()).decode())
        session.add(host)
        session.commit()
        host_id = host.id
    for table in (InspectionCheckRun.__table__, InspectionHostRun.__table__, InspectionTask.__table__):
        table.drop(engine)
    key_before = (data_dir / "secrets" / "fernet.key").read_bytes()
    engine.dispose()

    engine, sessions, cipher = initialize_storage(data_dir)
    try:
        assert all(inspect(engine).has_table(name) for name in (
            "inspection_tasks", "inspection_host_runs", "inspection_check_runs"))
        with sessions() as session:
            record = session.get(Host, host_id)
            assert record.name == "existing-host"
            assert cipher.decrypt(record.password_encrypted.encode()).decode() == SECRET
            assert session.scalar(select(HostGroup.name).where(HostGroup.id == record.group_id)) == "existing"
        assert (data_dir / "secrets" / "fernet.key").read_bytes() == key_before
        migrate = importlib.import_module("backend.app.core.migrations.inspections")
        migrate.migrate_inspections(engine)
        assert inspect(engine).has_table("inspection_tasks")
    finally:
        engine.dispose()
