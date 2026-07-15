"""Pydantic 数据模型 — 对应数据库表结构。"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

class SchoolLevel(str, Enum):
    NONE = ""
    PROJECT_211 = "211"
    PROJECT_985 = "985"
    DOUBLE_FIRST_CLASS = "双一流"


class MajorStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class SubjectType(str, Enum):
    PHYSICS = "物理"
    HISTORY = "历史"
    COMPREHENSIVE = "综合"


# ---------------------------------------------------------------------------
# 学校 & 校区
# ---------------------------------------------------------------------------

class School(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    level: Optional[str] = None          # 985/211/双一流
    province: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    total_enrollment: Optional[int] = None  # 全校总人数


class Campus(BaseModel):
    id: int
    school_id: int
    name: str
    address: Optional[str] = None
    function: Optional[str] = None       # 功能描述
    lat: Optional[float] = None
    lng: Optional[float] = None


# ---------------------------------------------------------------------------
# 专业
# ---------------------------------------------------------------------------

class Major(BaseModel):
    id: int
    standard_code: Optional[str] = None
    name: str
    category: Optional[str] = None       # 学科门类
    degree_type: Optional[str] = None


class SchoolMajorOffering(BaseModel):
    id: int
    school_id: int
    major_id: int
    campus_id: Optional[int] = None
    start_year: int
    end_year: Optional[int] = None       # None = 在办
    status: MajorStatus = MajorStatus.ACTIVE


# ---------------------------------------------------------------------------
# 招生 & 录取
# ---------------------------------------------------------------------------

class AdmissionPlan(BaseModel):
    id: int
    school_id: int
    major_id: int
    year: int
    province: str
    batch: Optional[str] = None
    plan_count: Optional[int] = None
    class_count: Optional[int] = None
    students_per_class: Optional[int] = None


class AdmissionScore(BaseModel):
    id: int
    school_id: int
    major_id: int
    year: int
    province: str
    batch: Optional[str] = None
    max_score: Optional[float] = None
    min_score: Optional[float] = None
    avg_score: Optional[float] = None
    min_rank: Optional[int] = None


class RankScoreTable(BaseModel):
    id: int
    year: int
    province: str
    subject_type: str                   # 物理/历史/综合
    score: int
    rank: int


# ---------------------------------------------------------------------------
# 性别统计
# ---------------------------------------------------------------------------

class GenderStats(BaseModel):
    id: int
    school_id: int
    major_id: Optional[int] = None      # None = 全校
    year: int
    male_count: Optional[int] = None
    female_count: Optional[int] = None
    male_pct: Optional[float] = None
    female_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# 宏观数据
# ---------------------------------------------------------------------------

class NationalMajorStats(BaseModel):
    id: int
    major_id: int
    year: int
    total_students: Optional[float] = None      # 全国在读（万人）
    male_pct: Optional[float] = None
    female_pct: Optional[float] = None
    job_market_gap: Optional[float] = None       # 就业缺口（万人）
    employment_difficulty_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# 就业 & 薪资
# ---------------------------------------------------------------------------

class EmploymentStats(BaseModel):
    id: int
    major_id: int
    year: int
    grad_count: Optional[int] = None
    employed_pct: Optional[float] = None
    industry_distribution: Optional[dict] = None  # JSON
    avg_start_salary: Optional[float] = None


class IndustryStats(BaseModel):
    id: int
    industry_name: str
    year: int
    avg_salary: Optional[float] = None
    hire_count: Optional[int] = None


# ---------------------------------------------------------------------------
# API 请求 / 响应
# ---------------------------------------------------------------------------

class RecommendByScoreRequest(BaseModel):
    score: int
    province: str
    year: int
    subject_type: str = "物理"
    top_n: int = 20


class RecommendByMajorRequest(BaseModel):
    score: int
    province: str
    year: int
    major_name: str
    subject_type: str = "物理"
    top_n: int = 20


class RecommendItem(BaseModel):
    school_name: str
    major_name: str
    probability: str                     # 冲/稳/保
    min_score: Optional[float] = None
    avg_score: Optional[float] = None
    min_rank: Optional[int] = None
    year: int


class RecommendResponse(BaseModel):
    items: list[RecommendItem]
    total: int
