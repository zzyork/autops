import pytest

from backend.app.core.ssh_commands import CommandExecutionError, CommandResult
from backend.app.schemas.inspections import InspectionConfig, ServiceSpec, Thresholds
from backend.app.services.inspection_checks import (
    CHECK_DEFINITIONS, CHECK_TITLES, InspectionCheckError, collect,
)


def fake(outputs: dict[str, str | CommandResult]):
    def run(command: str) -> CommandResult:
        response = outputs[command]
        return response if isinstance(response, CommandResult) else CommandResult(response, "", 0)
    return run


IPV4 = "2: eth0    inet 192.0.2.10/24 brd 192.0.2.255 scope global eth0\n"
IPV6 = "2: eth0    inet6 2001:db8::10/64 scope global dynamic\n"
STAT = "cpu  100 0 100 800 0 0 0 0 0 0\ncpu  180 0 100 820 0 0 0 0 0 0\n"
PS = "USER PID %CPU %MEM COMMAND\nroot 10 120.0 3.0 worker\n"


def resource_outputs() -> dict[str, str | CommandResult]:
    return {
        "head -n 1 /proc/stat && sleep 1 && head -n 1 /proc/stat": STAT,
        "cat /proc/loadavg": "0.20 0.40 0.60 1/100 400\n",
        "cat /proc/meminfo": "MemTotal: 1000 kB\nMemAvailable: 200 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n",
        "df -PT -k": (
            "Filesystem Type 1024-blocks Used Available Capacity Mounted on\n"
            "/dev/sda1 ext4 1000 900 100 90% /mnt/data files\n"
            "overlay overlay 100 10 90 10% /container\n"
            "tmpfs tmpfs 100 90 10 90% /run\n"
        ),
        "ps -eo user,pid,pcpu,pmem,comm --sort=-pcpu | head -n 11": PS,
        "ps -eo user,pid,pcpu,pmem,comm --sort=-pmem | head -n 11": PS,
    }


def test_registry_and_basic_ipv4_ipv6() -> None:
    assert set(CHECK_TITLES) == {definition.id for definition in CHECK_DEFINITIONS} == {
        "server_info", "system_resources", "service_status", "network_info",
    }
    outputs = {
        "hostname": "node1\n", "cat /etc/os-release": 'NAME="Linux"\nPRETTY_NAME="Test Linux 1"\n',
        "uname -r": "6.0.0\n", "cat /proc/uptime": "1234.56 100.0\n",
        "ip -o -4 addr show": IPV4, "ip -o -6 addr show": IPV6,
    }
    payload = collect("server_info", fake(outputs), InspectionConfig())
    assert payload.conclusion == "normal"
    assert payload.metrics[1].value == "Test Linux 1"
    assert payload.metrics[3].value == 1235
    assert payload.tables[0].rows == [["eth0", "192.0.2.10/24"]]
    assert payload.tables[1].rows == [["eth0", "2001:db8::10/64"]]


def test_resources_boundary_swap_absent_disks_and_ps_command_only() -> None:
    config = InspectionConfig(thresholds=Thresholds(cpu_warning=80, cpu_critical=80, mem_warning=80, mem_critical=95))
    payload = collect("system_resources", fake(resource_outputs()), config)
    assert payload.conclusion == "critical"
    assert [(f.severity, f.message) for f in payload.findings] == [
        ("critical", "CPU 使用率 80.0% >= 严重阈值 80.0%"),
        ("warning", "内存使用率 80.0% >= 警告阈值 80.0%"),
        ("critical", "磁盘 /mnt/data files 使用率 90.0% >= 严重阈值 90%"),
    ]
    assert next(metric for metric in payload.metrics if metric.name == "Swap 使用率").value is None
    assert [row[2] for row in payload.tables[0].rows] == ["/mnt/data files", "/container"]
    assert payload.tables[1].rows == [["root", "10", "120.0", "3.0", "worker"]]


def test_resources_warning_at_boundary_and_normal_below() -> None:
    outputs = resource_outputs()
    config = InspectionConfig(thresholds=Thresholds(cpu_warning=80, cpu_critical=95, mem_warning=80, mem_critical=95,
                                                   disk_critical=95))
    assert collect("system_resources", fake(outputs), config).conclusion == "warning"
    config = InspectionConfig(thresholds=Thresholds(cpu_warning=81, mem_warning=81, disk_warning=91, disk_critical=95))
    assert collect("system_resources", fake(outputs), config).conclusion == "normal"
    outputs["head -n 1 /proc/stat && sleep 1 && head -n 1 /proc/stat"] = (
        "cpu 0 0 0 0 0 0 0 0\ncpu 79999 0 0 20001 0 0 0 0\n"
    )
    config = InspectionConfig(thresholds=Thresholds(mem_warning=81, disk_warning=91, disk_critical=95))
    payload = collect("system_resources", fake(outputs), config)
    assert payload.conclusion == "normal"
    assert payload.metrics[0].value == 79.999


@pytest.mark.parametrize(("command", "replacement"), [
    ("cat /proc/meminfo", "MemTotal: 1000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n"),
    ("head -n 1 /proc/stat && sleep 1 && head -n 1 /proc/stat", "cpu  1 2 3\n"),
    ("df -PT -k", "unexpected header\n"),
    ("cat /proc/loadavg", "nan 0 0 1/2 42\n"),
])
def test_resources_rejects_malformed_sources(command: str, replacement: str) -> None:
    outputs = resource_outputs()
    outputs[command] = replacement
    with pytest.raises(InspectionCheckError, match="invalid_output"):
        collect("system_resources", fake(outputs), InspectionConfig())


def test_resources_all_pseudo_filesystems_fail_without_monitored_disks() -> None:
    outputs = resource_outputs()
    outputs["df -PT -k"] = (
        "Filesystem Type 1024-blocks Used Available Capacity Mounted on\n"
        "tmpfs tmpfs 100 10 90 10% /run\n"
        "devtmpfs devtmpfs 100 5 95 5% /dev\n"
        "proc proc 100 0 100 0% /proc\n"
    )
    with pytest.raises(InspectionCheckError) as caught:
        collect("system_resources", fake(outputs), InspectionConfig())
    assert caught.value.code == "no_monitored_disks"


def test_nonzero_exit_and_empty_are_failures() -> None:
    outputs = resource_outputs()
    outputs["df -PT -k"] = CommandResult("secret", "private error", 1)
    with pytest.raises(InspectionCheckError) as caught:
        collect("system_resources", fake(outputs), InspectionConfig())
    assert caught.value.code == "command_failed"
    assert "private" not in str(caught.value)
    outputs["df -PT -k"] = ""
    with pytest.raises(InspectionCheckError, match="invalid_output"):
        collect("system_resources", fake(outputs), InspectionConfig())
    outputs["df -PT -k"] = CommandResult("", "not found", 127)
    with pytest.raises(InspectionCheckError, match="tool_missing"):
        collect("system_resources", fake(outputs), InspectionConfig())


def test_service_required_missing_optional_missing_and_inactive() -> None:
    config = InspectionConfig(services=[
        ServiceSpec(name="required", candidates=["missing"], required=True),
        ServiceSpec(name="optional", candidates=["optional"]),
        ServiceSpec(name="web", candidates=["nginx", "web"]),
    ])
    missing = "ActiveState=inactive\nLoadState=not-found\n"
    outputs = {
        "systemctl show -p LoadState -p ActiveState -- missing": missing,
        "systemctl show -p LoadState -p ActiveState -- optional": missing,
        "systemctl show -p LoadState -p ActiveState -- nginx": missing,
        "systemctl show -p LoadState -p ActiveState -- web": "ActiveState=inactive\nLoadState=loaded\n",
    }
    payload = collect("service_status", fake(outputs), config)
    assert payload.conclusion == "warning"
    assert len(payload.findings) == 2
    assert payload.tables[0].rows == [["web", "web", "loaded", "inactive", "否"]]
    assert collect("service_status", fake({"systemctl show -p LoadState -p ActiveState -- optional": missing}),
                   InspectionConfig(services=[ServiceSpec(name="optional", candidates=["optional"])])).conclusion == "not_applicable"


@pytest.mark.parametrize(("required", "conclusion"), [(False, "not_applicable"), (True, "warning")])
def test_service_exit_one_not_found_is_missing(required: bool, conclusion: str) -> None:
    config = InspectionConfig(services=[ServiceSpec(name="web", candidates=["nginx"], required=required)])
    command = "systemctl show -p LoadState -p ActiveState -- nginx"
    payload = collect("service_status", fake({
        command: CommandResult("LoadState=not-found\nActiveState=inactive\n", "unit not found", 1),
    }), config)
    assert payload.conclusion == conclusion
    assert payload.tables[0].rows == []
    assert len(payload.findings) == int(required)


@pytest.mark.parametrize(("result", "code"), [
    (CommandResult("LoadState=loaded\nActiveState=active\n", "error", 1), "command_failed"),
    (CommandResult("", "error", 1), "invalid_output"),
    (CommandResult("LoadState=not-found\nActiveState=inactive\n", "not found", 127), "tool_missing"),
    (CommandResult("", "not found", 127), "tool_missing"),
])
def test_service_nonzero_exit_rejects_non_missing_results(result: CommandResult, code: str) -> None:
    config = InspectionConfig(services=[ServiceSpec(name="ssh", candidates=["sshd"], required=True)])
    command = "systemctl show -p LoadState -p ActiveState -- sshd"
    with pytest.raises(InspectionCheckError) as caught:
        collect("service_status", fake({command: result}), config)
    assert caught.value.code == code


def test_service_validation_and_query_failure_not_missing() -> None:
    with pytest.raises(ValueError):
        ServiceSpec(name="bad", candidates=["nginx; id"])
    name = "safe'unit"
    with pytest.raises(ValueError):
        ServiceSpec(name="bad", candidates=[name])
    config = InspectionConfig(services=[ServiceSpec(name="ssh", candidates=["sshd"], required=True)])
    command = "systemctl show -p LoadState -p ActiveState -- sshd"
    for output in (CommandResult("", "denied", 1), CommandResult("", "", 0)):
        with pytest.raises(InspectionCheckError) as caught:
            collect("service_status", fake({command: output}), config)
        assert caught.value.code in {"command_failed", "invalid_output"}


def test_service_loaded_active_is_normal() -> None:
    config = InspectionConfig(services=[ServiceSpec(name="ssh", candidates=["sshd"], required=True)])
    payload = collect("service_status", fake({
        "systemctl show -p LoadState -p ActiveState -- sshd": "LoadState=loaded\nActiveState=active\n",
    }), config)
    assert payload.conclusion == "normal"
    assert payload.findings == []
    assert payload.tables[0].rows == [["ssh", "sshd", "loaded", "active", "是"]]


def test_network_listeners_ipv6_and_missing_ss() -> None:
    outputs = {
        "ip -o -4 addr show": IPV4, "ip -o -6 addr show": IPV6,
        "ss -H -l -t -u -n": "tcp LISTEN 0 128 [::]:443 [::]:*\nudp UNCONN 0 0 0.0.0.0:53 0.0.0.0:*\n",
    }
    payload = collect("network_info", fake(outputs), InspectionConfig())
    assert payload.tables[2].rows == [["TCP", "LISTEN", "[::]:443"], ["UDP", "UNCONN", "0.0.0.0:53"]]
    assert payload.tables[1].rows == [["eth0", "2001:db8::10/64"]]
    outputs["ss -H -l -t -u -n"] = CommandResult("", "not found", 127)
    payload = collect("network_info", fake(outputs), InspectionConfig())
    assert payload.conclusion == "not_applicable"
    assert payload.metrics[0].value == "tool_missing"
    outputs["ss -H -l -t -u -n"] = CommandResult("", "denied", 1)
    with pytest.raises(InspectionCheckError, match="command_failed"):
        collect("network_info", fake(outputs), InspectionConfig())
    outputs["ss -H -l -t -u -n"] = "tcp LISTEN 0 128 [::1:443 [::]:*\n"
    with pytest.raises(InspectionCheckError, match="invalid_output"):
        collect("network_info", fake(outputs), InspectionConfig())


def test_network_excludes_only_loopback_listeners() -> None:
    endpoints = ["127.0.0.1:80", "127.255.0.1:81", "[::1]:82", "[::ffff:127.2.3.4]:83",
                 "0.0.0.0:84", "[::]:85", "192.0.2.10:86", "[2001:db8::1]:87",
                 "[::ffff:192.0.2.2]:88"]
    outputs = {"ip -o -4 addr show": IPV4, "ip -o -6 addr show": IPV6,
               "ss -H -l -t -u -n": "".join(f"tcp LISTEN 0 128 {item} *:*\n" for item in endpoints)}
    payload = collect("network_info", fake(outputs), InspectionConfig())
    assert [row[2] for row in payload.tables[2].rows] == endpoints[4:]
    assert payload.metrics[0].value == 5


def test_network_scoped_ipv6_listeners_filter_only_loopback() -> None:
    endpoints = ["[::1%lo]:80", "[::ffff:127.0.0.1%lo]:81", "[fe80::1%eth0]:82", "[::%lo]:83",
                 "[2001:db8::1%eth0]:84"]
    outputs = {"ip -o -4 addr show": IPV4, "ip -o -6 addr show": IPV6,
               "ss -H -l -t -u -n": "".join(f"tcp LISTEN 0 128 {item} *:*\n" for item in endpoints)}
    payload = collect("network_info", fake(outputs), InspectionConfig())
    assert [row[2] for row in payload.tables[2].rows] == endpoints[2:]
    assert payload.metrics[0].value == 3


def test_output_limits_and_execution_errors_propagate() -> None:
    outputs = {"ip -o -4 addr show": IPV4 * 257, "ip -o -6 addr show": IPV6,
               "ss -H -l -t -u -n": ""}
    with pytest.raises(InspectionCheckError, match="output_limit"):
        collect("network_info", fake(outputs), InspectionConfig())
    outputs["ip -o -4 addr show"] = IPV4
    outputs["ss -H -l -t -u -n"] = "tcp LISTEN 0 128 0.0.0.0:80 0.0.0.0:*\n" * 257
    with pytest.raises(InspectionCheckError, match="output_limit"):
        collect("network_info", fake(outputs), InspectionConfig())
    outputs["ss -H -l -t -u -n"] = ""
    outputs["ip -o -4 addr show"] = f"2: {'a' * 501} inet 192.0.2.1/24 scope global\n"
    with pytest.raises(InspectionCheckError, match="output_limit"):
        collect("network_info", fake(outputs), InspectionConfig())

    def failed_runner(command: str) -> CommandResult:
        raise CommandExecutionError("timeout", True)

    with pytest.raises(CommandExecutionError) as caught:
        collect("server_info", failed_runner, InspectionConfig())
    assert caught.value.code == "timeout"
