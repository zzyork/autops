import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from ..schemas.inspections import MAX_LOG_QUERY_DAYS, InspectionConfig


def load_rules(data_dir: Path) -> InspectionConfig:
    path = data_dir / "inspection-rules.json"
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return InspectionConfig()
    try:
        config = InspectionConfig.model_validate_json(content)
    except ValidationError as exc:
        raise RuntimeError("巡检规则文件损坏") from exc
    # 旧规则仍可读取，新任务与表单看到的范围和实际执行一致；不改写历史快照。
    config.logs.days = min(config.logs.days, MAX_LOG_QUERY_DAYS)
    return config


def save_rules(data_dir: Path, config: InspectionConfig) -> InspectionConfig:
    path = data_dir / "inspection-rules.json"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=data_dir, delete=False) as output:
            temporary = Path(output.name)
            output.write(config.model_dump_json())
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return config
