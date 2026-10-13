#!/usr/bin/env bash
# 用法：bash scripts/start.sh。需预先安装 Python 3.13、Node.js 和 npm。
# 创建或复用 .venv，安装开发依赖，前后台日志共用当前终端；Ctrl+C 停止两个服务。
# 本脚本不安装 Python 或 Node.js 本身。
set -Eeuo pipefail

trap 'printf "[错误] 启动步骤失败（第 %s 行），已停止执行。\n" "$LINENO" >&2' ERR
if [[ $# -ne 0 ]]; then
    printf '[错误] 用法：bash scripts/start.sh\n' >&2
    exit 1
fi
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$ROOT_DIR"

for tool in python3.13 node npm; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf '[错误] 未找到 %s，请先安装并加入 PATH。\n' "$tool" >&2
        exit 1
    fi
done
python3.13 --version
node -e "const [a,b]=process.versions.node.split('.').map(Number); if (!((a===20 && b>=19)||(a===22 && b>=12)||a>22)) { console.error('Node.js 需要 20.19+（20.x）或 22.12+'); process.exit(1); }"

if [[ ! -e .venv ]]; then
    printf '[1/4] 创建 Python 虚拟环境...\n'
    python3.13 -m venv .venv
fi
if [[ ! -x .venv/bin/python ]]; then
    printf '[错误] .venv 中没有可执行的 Unix Python，请检查虚拟环境。\n' >&2
    exit 1
fi
.venv/bin/python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else '虚拟环境需要 Python 3.13')"

printf '[2/4] 安装后端依赖...\n'
.venv/bin/python -m pip install -r requirements-dev.txt
printf '[3/4] 安装前端依赖...\n'
npm --prefix frontend install

# 独立进程组确保停止 npm 时也能停止其 Vite 子进程，以及 Uvicorn 的重载进程。
set -m
backend_pid=''
frontend_pid=''
cleanup() {
    trap - EXIT INT TERM
    local service_pid
    for service_pid in "$backend_pid" "$frontend_pid"; do
        if [[ -n "$service_pid" ]] && kill -0 -- "-$service_pid" 2>/dev/null; then
            kill -TERM -- "-$service_pid"
        fi
    done
    # 服务收到终止信号后通常返回非零；回收所有由脚本启动的子进程。
    wait || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '[4/4] 启动前后端...\n'
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000 &
backend_pid=$!
npm --prefix frontend run dev &
frontend_pid=$!
printf '前端：http://127.0.0.1:5173\nAPI 文档：http://127.0.0.1:8000/docs\n按 Ctrl+C 停止两个服务。\n'

# 兼容 macOS 自带 Bash 3.2，不使用较新版本才提供的 wait -n。
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
    sleep 1
done
printf '[错误] 一个服务已退出，正在停止另一个服务，请查看上方日志。\n' >&2
exit 1
