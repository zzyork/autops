"""兼容项目根目录下的 uvicorn main:app 启动方式。"""

from backend.app.main import app

__all__ = ["app"]
