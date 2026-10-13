"""在同一终端运行开发服务，合并日志并管理服务进程树。"""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_LOCK = threading.Lock()
FRONTEND_URL = "http://127.0.0.1:5173/"
BACKEND_HEALTH_URL = "http://127.0.0.1:8000/api/v1/health"
READY_MARKER = "AUTOPS_READY"


def output(label: str, text: str) -> None:
    with OUTPUT_LOCK:
        print(f"[{label}] {text}", flush=True)


def forward(label: str, process: subprocess.Popen[str], ready: threading.Event) -> None:
    assert process.stdout is not None
    with process.stdout:
        for line in process.stdout:
            output(label, line.rstrip("\r\n"))
            if ((label == "后端" and "Application startup complete." in line)
                    or (label == "前端" and "Local:" in line and FRONTEND_URL in line)):
                ready.set()


def responds(url: str) -> bool:
    # 本机开发探测不经过系统代理；未响应表示仍未就绪，不触发浏览器。
    try:
        with build_opener(ProxyHandler({})).open(url, timeout=0.5) as response:
            return response.status == 200
    except (URLError, TimeoutError, ConnectionError):
        return False


def stop(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        if process.poll() is None:
            process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        output("启动器", f"进程 {process.pid} 未在 10 秒内退出，强制停止。")
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, check=False,
            )
            if result.returncode and process.poll() is None:
                raise RuntimeError(f"清理服务进程树 {process.pid} 失败")
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def main() -> int:
    node = shutil.which("node")
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if node is None or not vite.is_file():
        output("启动器", "缺少 Node.js 或前端依赖，请先运行平台启动脚本安装依赖。")
        return 1
    env = os.environ.copy()
    env.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", NO_COLOR="1")
    services = [
        ("后端", [sys.executable, "-u", "-m", "uvicorn", "backend.app.main:app",
                  "--reload", "--host", "127.0.0.1", "--port", "8000"], ROOT),
        ("前端", [node, str(vite)], ROOT / "frontend"),
    ]
    processes: list[tuple[str, subprocess.Popen[str]]] = []
    readers: list[threading.Thread] = []
    interrupted = threading.Event()
    readiness = {label: threading.Event() for label, _, _ in services}
    announced = False

    def interrupt(_signum: int, _frame: object) -> None:
        interrupted.set()

    signals = [signal.SIGINT, signal.SIGTERM]
    if os.name == "nt":
        signals.append(signal.SIGBREAK)
    previous = {sig: signal.signal(sig, interrupt) for sig in signals}
    try:
        for label, command, cwd in services:
            process = subprocess.Popen(
                command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
            processes.append((label, process))
            reader = threading.Thread(target=forward, args=(label, process, readiness[label]), daemon=True)
            readers.append(reader)
            reader.start()
        output("启动器", "按 Ctrl+C 停止前后端；API 文档：http://127.0.0.1:8000/docs")
        while not interrupted.wait(0.2):
            for label, process in processes:
                code = process.poll()
                if code is not None:
                    output("启动器", f"{label}已退出（退出码 {code}），正在停止其他服务。")
                    return code if code else 1
            if (not announced and all(event.is_set() for event in readiness.values())
                    and responds(BACKEND_HEALTH_URL) and responds(FRONTEND_URL)):
                if all(process.poll() is None for _, process in processes):
                    output("启动器", f"{READY_MARKER} {FRONTEND_URL}")
                    announced = True
        output("启动器", "正在停止前后端。")
        return 0
    except OSError as exc:
        output("启动器", f"启动失败：{exc}")
        return 1
    finally:
        for _, process in processes:
            stop(process)
        for reader in readers:
            reader.join(timeout=2)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
