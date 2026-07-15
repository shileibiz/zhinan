"""基本导入测试 — 验证项目结构完整性。"""

import pytest


def test_imports():
    """验证所有主要模块可以正常导入。"""
    from zhinan import __version__
    assert __version__ == "0.1.0"

    from zhinan.db import DatabaseBackend, SQLiteBackend, get_backend, open_db, register_backend
    assert issubclass(SQLiteBackend, DatabaseBackend)

    from zhinan.schemas import get_ddl, DDL
    ddl = get_ddl()
    assert "CREATE TABLE IF NOT EXISTS schools" in ddl
    assert "CREATE TABLE IF NOT EXISTS admission_scores" in ddl

    from zhinan.models import (
        School, Campus, Major, AdmissionScore, AdmissionPlan,
        RankScoreTable, GenderStats, NationalMajorStats,
        EmploymentStats, IndustryStats,
        RecommendByScoreRequest, RecommendByMajorRequest, RecommendResponse,
    )
    assert School is not None
    assert RecommendByScoreRequest is not None

    from zhinan.api import app, router
    assert app.title == "志愿指南 API"

    from zhinan.collector import BaseCollector
    from zhinan.collector.schools import SchoolCollector
    from zhinan.collector.scores import ScoreCollector
    from zhinan.collector.examiners import ExaminerCollector
    from zhinan.collector.macro import MacroCollector
    assert issubclass(SchoolCollector, BaseCollector)

    from zhinan.recommender.rank import RankConverter
    from zhinan.recommender.engine import RecommendEngine
    assert RankConverter is not None
    assert RecommendEngine is not None

    from zhinan.cli import main
    assert callable(main)


def test_schemas_ddl_includes_all_tables():
    """验证 DDL 包含所有必需的表。"""
    from zhinan.schemas import get_ddl
    ddl = get_ddl()
    required_tables = [
        "schools", "campuses", "majors", "school_major_offerings",
        "admission_plans", "admission_scores", "rank_score_tables",
        "gender_stats", "national_major_stats", "employment_stats",
        "industry_stats",
    ]
    for table in required_tables:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in ddl, f"Missing table: {table}"


def test_models_serialization():
    """验证 Pydantic 模型序列化。"""
    from zhinan.models import RecommendItem, RecommendResponse

    item = RecommendItem(
        school_name="清华大学",
        major_name="计算机科学与技术",
        probability="冲",
        min_score=680.0,
        avg_score=685.0,
        min_rank=100,
        year=2024,
    )
    data = item.model_dump()
    assert data["school_name"] == "清华大学"
    assert data["probability"] == "冲"

    response = RecommendResponse(items=[item], total=1)
    assert response.total == 1


@pytest.mark.asyncio
async def test_sqlite_backend_lifecycle(tmp_path):
    """验证 SQLite 后端可以连接和执行 DDL。"""
    from zhinan.db import get_backend
    from zhinan.schemas import get_ddl

    db_path = tmp_path / "test.db"
    backend = get_backend("sqlite", db_path=str(db_path))
    await backend.connect()
    try:
        await backend.run_migrations(get_ddl())
        # 验证表已创建
        tables = await backend.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = {r["name"] for r in tables}
        assert "schools" in table_names
        assert "majors" in table_names
        assert "admission_scores" in table_names
    finally:
        await backend.close()
