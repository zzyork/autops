@echo off
setlocal
rem Keep this file ASCII: CMD may misread UTF-8 batch offsets after CALL.
rem Chinese messages are decoded by Windows PowerShell at runtime.
chcp 65001 >nul
pushd "%~dp0.."
if errorlevel 1 exit /b 1
if "%~1"=="--backend" goto backend
if "%~1"=="--frontend" goto frontend
if not "%~1"=="" (
    call :message "[\u9519\u8bef] \u7528\u6cd5: scripts/start.bat"
    goto failed
)
where py >nul 2>&1
if errorlevel 1 (
    call :message "[\u9519\u8bef] \u8bf7\u5b89\u88c5 Python 3.13 \u53ca\u5176 py \u542f\u52a8\u5668\u3002"
    goto failed
)
py -3.13 --version
if errorlevel 1 goto failed
where node >nul 2>&1
if errorlevel 1 (
    call :message "[\u9519\u8bef] \u8bf7\u5148\u5b89\u88c5 Node.js\u3002"
    goto failed
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
    call :message "[\u9519\u8bef] \u672a\u627e\u5230 npm.cmd\u3002"
    goto failed
)
node -e "const [a,b]=process.versions.node.split('.').map(Number); if (!((a===20 && b>=19)||(a===22 && b>=12)||a>22)) { console.error('Node.js \u9700\u8981 20.19+ (20.x) \u6216 22.12+'); process.exit(1); }"
if errorlevel 1 goto failed
if not exist ".venv" (
    call :message "[1/4] \u521b\u5efa Python \u865a\u62df\u73af\u5883..."
    py -3.13 -m venv .venv
    if errorlevel 1 goto failed
)
if not exist ".venv\Scripts\python.exe" (
    call :message "[\u9519\u8bef] .venv \u4e2d\u6ca1\u6709 Windows Python\u3002"
    goto failed
)
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else '\u865a\u62df\u73af\u5883\u9700\u8981 Python 3.13')"
if errorlevel 1 goto failed
call :message "[2/4] \u5b89\u88c5\u540e\u7aef\u4f9d\u8d56..."
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed
call :message "[3/4] \u5b89\u88c5\u524d\u7aef\u4f9d\u8d56..."
call npm.cmd --prefix frontend install
if errorlevel 1 goto failed
call :message "[4/4] \u542f\u52a8\u524d\u540e\u7aef\uff0c\u8bf7\u5728\u670d\u52a1\u7a97\u53e3\u67e5\u770b\u542f\u52a8\u7ed3\u679c\u3002"
start "autops API" cmd.exe /d /k ""%~f0" --backend"
if errorlevel 1 goto failed
start "autops Vite" cmd.exe /d /k ""%~f0" --frontend"
if errorlevel 1 goto failed
call :message "\u524d\u7aef: http://127.0.0.1:5173"
call :message "API \u6587\u6863: http://127.0.0.1:8000/docs"
call :message "\u5728\u5404\u670d\u52a1\u7a97\u53e3\u6309 Ctrl+C \u505c\u6b62\u670d\u52a1\u3002"
popd
exit /b 0
:backend
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
if errorlevel 1 goto failed
popd
exit /b 0
:frontend
call npm.cmd --prefix frontend run dev
if errorlevel 1 goto failed
popd
exit /b 0
:failed
call :message "[\u9519\u8bef] \u5f53\u524d\u6b65\u9aa4\u5931\u8d25\uff0c\u5df2\u505c\u6b62\u6267\u884c\u3002\u8bf7\u67e5\u770b\u4e0a\u65b9\u9519\u8bef\u4fe1\u606f\u3002"
popd
exit /b 1
:message
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding; [Console]::WriteLine([regex]::Unescape('%~1'))"
exit /b %errorlevel%
