from sqlalchemy import Engine

from ...inspection_models import InspectionAIReport, InspectionCheckRun, InspectionHostRun, InspectionTask


def migrate_inspections(engine: Engine) -> None:
    """幂等创建巡检表，保留既有资产、凭据和连接记录。"""
    with engine.begin() as connection:
        for table in (InspectionTask.__table__, InspectionHostRun.__table__, InspectionCheckRun.__table__, InspectionAIReport.__table__):
            table.create(connection, checkfirst=True)
