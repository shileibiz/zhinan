"""FastAPI 路由定义。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from zhinan.db import DatabaseBackend, get_backend
from zhinan.models import (
    RecommendByMajorRequest,
    RecommendByScoreRequest,
    RecommendItem,
    RecommendResponse,
    School,
)

# ---------------------------------------------------------------------------
# FastAPI 应用 & 路由
# ---------------------------------------------------------------------------

app = FastAPI(
    title="志愿指南 API",
    description="高考志愿填报数据平台",
    version="0.1.0",
)

# CORS — allow frontend from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/v1", tags=["志愿指南"])


# ---------------------------------------------------------------------------
# 依赖：数据库后端
# ---------------------------------------------------------------------------

async def get_db() -> DatabaseBackend:
    db = get_backend("sqlite", db_path="data/zhinan.db")
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# 学校相关
# ---------------------------------------------------------------------------

@router.get("/schools")
async def list_schools(
    province: Optional[str] = Query(None, description="省份筛选"),
    level: Optional[str] = Query(None, description="学校层次: 985/211/双一流"),
    keyword: Optional[str] = Query(None, description="学校名称关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: DatabaseBackend = Depends(get_db),
):
    """学校列表／搜索。"""
    conditions = []
    params: list = []

    if province:
        conditions.append("province = ?")
        params.append(province)
    if level:
        conditions.append("level = ?")
        params.append(level)
    if keyword:
        conditions.append("name LIKE ?")
        params.append(f"%{keyword}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    count_sql = f"SELECT COUNT(*) as total FROM schools {where}"
    count_row = await db.fetch_one(count_sql, tuple(params))
    total = count_row["total"] if count_row else 0

    data_sql = f"SELECT * FROM schools {where} ORDER BY id LIMIT ? OFFSET ?"
    rows = await db.fetch_all(data_sql, tuple(params) + (page_size, offset))

    return {"total": total, "page": page, "page_size": page_size, "items": rows}


@router.get("/schools/{school_id}/campuses")
async def get_school_campuses(
    school_id: int,
    db: DatabaseBackend = Depends(get_db),
):
    """校区信息。"""
    rows = await db.fetch_all("SELECT * FROM campuses WHERE school_id = ?", (school_id,))
    return {"school_id": school_id, "campuses": rows}


@router.get("/schools/{school_id}/majors")
async def get_school_majors(
    school_id: int,
    db: DatabaseBackend = Depends(get_db),
):
    """专业列表（含开设／关闭记录）。"""
    sql = """
    SELECT
        sm.id,
        m.id AS major_id,
        m.name AS major_name,
        m.standard_code,
        m.category,
        sm.start_year,
        sm.end_year,
        sm.status
    FROM school_major_offerings sm
    JOIN majors m ON m.id = sm.major_id
    WHERE sm.school_id = ?
    ORDER BY sm.status, m.name
    """
    rows = await db.fetch_all(sql, (school_id,))
    return {"school_id": school_id, "majors": rows}


# ---------------------------------------------------------------------------
# 一分一段表查询
# ---------------------------------------------------------------------------

@router.get("/rank-score")
async def query_rank_score(
    score: Optional[int] = Query(None, description="分数"),
    rank: Optional[int] = Query(None, description="位次"),
    year: Optional[int] = Query(None, description="年份"),
    province: Optional[str] = Query(None, description="省份"),
    subject_type: Optional[str] = Query(None, description="物理/历史/综合"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: DatabaseBackend = Depends(get_db),
):
    """一分一段表查询：按分数查位次，或按位次查分数。"""
    conditions = []
    params: list = []
    if score is not None:
        conditions.append("score = ?")
        params.append(score)
    if rank is not None:
        conditions.append("rank = ?")
        params.append(rank)
    if year:
        conditions.append("year = ?")
        params.append(year)
    if province:
        conditions.append("province = ?")
        params.append(province)
    if subject_type:
        conditions.append("subject_type = ?")
        params.append(subject_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    count_sql = f"SELECT COUNT(*) as total FROM rank_score_tables {where}"
    count_row = await db.fetch_one(count_sql, tuple(params))
    total = count_row["total"] if count_row else 0

    data_sql = f"SELECT * FROM rank_score_tables {where} ORDER BY year DESC, score DESC LIMIT ? OFFSET ?"
    rows = await db.fetch_all(data_sql, tuple(params) + (page_size, offset))
    return {"total": total, "page": page, "page_size": page_size, "items": rows}


@router.get("/rank-score/convert")
async def convert_score_to_rank(
    score: int = Query(..., description="分数"),
    year: int = Query(..., description="年份"),
    province: str = Query(..., description="省份"),
    subject_type: str = Query("物理", description="物理/历史/综合"),
    db: DatabaseBackend = Depends(get_db),
):
    """按分数查位次。"""
    from zhinan.recommender.rank import RankConverter
    converter = RankConverter(db)
    rank_val = await converter.score_to_rank(score, year, province, subject_type)
    return {"score": score, "year": year, "province": province, "subject_type": subject_type, "rank": rank_val}


# ---------------------------------------------------------------------------
# 分数查询
# ---------------------------------------------------------------------------

@router.get("/admission/scores")
async def query_admission_scores(
    school_id: Optional[int] = Query(None),
    major_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    province: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: DatabaseBackend = Depends(get_db),
):
    """历年分数查询。"""
    conditions = []
    params: list = []
    if school_id:
        conditions.append("as_.school_id = ?")
        params.append(school_id)
    if major_id:
        conditions.append("as_.major_id = ?")
        params.append(major_id)
    if year:
        conditions.append("as_.year = ?")
        params.append(year)
    if province:
        conditions.append("as_.province = ?")
        params.append(province)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    count_sql = f"SELECT COUNT(*) as total FROM admission_scores as_ {where}"
    count_row = await db.fetch_one(count_sql, tuple(params))
    total = count_row["total"] if count_row else 0

    data_sql = f"""
    SELECT as_.*, s.name AS school_name, m.name AS major_name
    FROM admission_scores as_
    LEFT JOIN schools s ON s.id = as_.school_id
    LEFT JOIN majors m ON m.id = as_.major_id
    {where}
    ORDER BY as_.year DESC, as_.min_score DESC
    LIMIT ? OFFSET ?
    """
    rows = await db.fetch_all(data_sql, tuple(params) + (page_size, offset))
    return {"total": total, "page": page, "page_size": page_size, "items": rows}


# ---------------------------------------------------------------------------
# 推荐
# ---------------------------------------------------------------------------

@router.post("/recommend/by-score")
async def recommend_by_score(
    req: RecommendByScoreRequest,
    db: DatabaseBackend = Depends(get_db),
):
    """分数 → 院校专业推荐（冲稳保）。"""
    from zhinan.recommender.engine import RecommendEngine
    engine = RecommendEngine(db)
    items = await engine.recommend_by_score(
        score=req.score,
        province=req.province,
        year=req.year,
        subject_type=req.subject_type,
        top_n=req.top_n,
    )
    return RecommendResponse(items=items, total=len(items))


@router.post("/recommend/by-major")
async def recommend_by_major(
    req: RecommendByMajorRequest,
    db: DatabaseBackend = Depends(get_db),
):
    """分数 + 意向专业 → 院校推荐。"""
    from zhinan.recommender.engine import RecommendEngine
    engine = RecommendEngine(db)
    items = await engine.recommend_by_major(
        score=req.score,
        province=req.province,
        year=req.year,
        major_name=req.major_name,
        subject_type=req.subject_type,
        top_n=req.top_n,
    )
    return RecommendResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# 趋势
# ---------------------------------------------------------------------------

@router.get("/trends/major/{major_id}")
async def get_major_trends(
    major_id: int,
    db: DatabaseBackend = Depends(get_db),
):
    """专业趋势（分数／人数／就业）。"""
    # 近5年分数趋势
    scores_sql = """
    SELECT year, province, AVG(avg_score) as avg_score,
           AVG(min_score) as min_score, AVG(max_score) as max_score
    FROM admission_scores
    WHERE major_id = ? AND year >= (SELECT MAX(year) - 4 FROM admission_scores)
    GROUP BY year, province
    ORDER BY year
    """
    score_trends = await db.fetch_all(scores_sql, (major_id,))

    # 就业趋势
    emp_sql = """
    SELECT year, grad_count, employed_pct, avg_start_salary
    FROM employment_stats
    WHERE major_id = ?
    ORDER BY year
    """
    emp_trends = await db.fetch_all(emp_sql, (major_id,))

    # 宏观
    macro_sql = """
    SELECT year, total_students, male_pct, female_pct, job_market_gap
    FROM national_major_stats
    WHERE major_id = ?
    ORDER BY year
    """
    macro = await db.fetch_all(macro_sql, (major_id,))

    major_row = await db.fetch_one("SELECT * FROM majors WHERE id = ?", (major_id,))

    return {
        "major": major_row,
        "score_trends": score_trends,
        "employment_trends": emp_trends,
        "national_stats": macro,
    }


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------

@router.get("/stats/gender")
async def get_gender_stats(
    school_id: Optional[int] = Query(None),
    major_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: DatabaseBackend = Depends(get_db),
):
    """性别比例查询。"""
    conditions = []
    params: list = []
    if school_id:
        conditions.append("school_id = ?")
        params.append(school_id)
    if major_id:
        conditions.append("major_id = ?")
        params.append(major_id)
    if year:
        conditions.append("year = ?")
        params.append(year)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM gender_stats {where} ORDER BY year DESC"
    rows = await db.fetch_all(sql, tuple(params))
    return {"items": rows}


@router.get("/stats/employment")
async def get_employment_stats(
    major_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: DatabaseBackend = Depends(get_db),
):
    """就业数据查询。"""
    conditions = []
    params: list = []
    if major_id:
        conditions.append("major_id = ?")
        params.append(major_id)
    if year:
        conditions.append("year = ?")
        params.append(year)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM employment_stats {where} ORDER BY year DESC"
    rows = await db.fetch_all(sql, tuple(params))
    return {"items": rows}


# ---------------------------------------------------------------------------
# 注册路由到应用
# ---------------------------------------------------------------------------

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
