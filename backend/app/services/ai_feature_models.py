import os
import tempfile
import threading
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..ai_models import AIConnection
from ..repositories import ai
from ..schemas.ai import FeatureModels

# 配置写入和连接删除共用锁，避免检查引用与修改之间出现竞争。
config_guard = threading.RLock()
Feature = Literal["chat", "inspection_report"]


def load_feature_models(data_dir: Path) -> FeatureModels:
    try:
        content = (data_dir / "ai-feature-models.json").read_text(encoding="utf-8")
    except FileNotFoundError:
        return FeatureModels(chat_connection_id=None, inspection_report_connection_id=None)
    except (OSError, UnicodeError):
        raise HTTPException(503, "AI 功能模型配置不可读") from None
    try:
        return FeatureModels.model_validate_json(content)
    except ValidationError:
        raise HTTPException(503, "AI 功能模型配置文件损坏") from None


def save_feature_models(data_dir: Path, config: FeatureModels, session: Session) -> FeatureModels:
    with config_guard:
        for connection_id in (config.chat_connection_id, config.inspection_report_connection_id):
            if connection_id is not None and ai.connection(session, connection_id) is None:
                raise HTTPException(409, "指定的模型连接不存在")
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=data_dir, delete=False) as output:
                temporary = Path(output.name)
                output.write(config.model_dump_json())
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, data_dir / "ai-feature-models.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return config


def feature_connection(session: Session, data_dir: Path, feature: Feature) -> AIConnection | None:
    config = load_feature_models(data_dir)
    connection_id = getattr(config, f"{feature}_connection_id")
    # 只有用户明确选择沿用主模型时才读取主模型；指定连接失效不得切换。
    return ai.primary_connection(session) if connection_id is None else ai.connection(session, connection_id)
