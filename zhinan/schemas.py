"""SQLite DDL — 所有表结构与索引定义。

所有表统一使用 INTEGER PRIMARY KEY 自增 ID。
"""

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """
-- 学校
CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT,
    level TEXT,
    province TEXT,
    city TEXT,
    address TEXT,
    website TEXT,
    total_enrollment INTEGER
);

-- 校区
CREATE TABLE IF NOT EXISTS campuses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    name TEXT NOT NULL,
    address TEXT,
    function TEXT,
    lat REAL,
    lng REAL
);

-- 专业
CREATE TABLE IF NOT EXISTS majors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_code TEXT,
    name TEXT NOT NULL,
    category TEXT,
    degree_type TEXT
);

-- 学校-专业关系（开设记录）
CREATE TABLE IF NOT EXISTS school_major_offerings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    major_id INTEGER NOT NULL REFERENCES majors(id),
    campus_id INTEGER REFERENCES campuses(id),
    start_year INTEGER NOT NULL,
    end_year INTEGER,
    status TEXT NOT NULL DEFAULT 'active'
);

-- 招生计划
CREATE TABLE IF NOT EXISTS admission_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    major_id INTEGER NOT NULL REFERENCES majors(id),
    year INTEGER NOT NULL,
    province TEXT NOT NULL,
    batch TEXT,
    plan_count INTEGER,
    class_count INTEGER,
    students_per_class INTEGER
);

-- 录取分数
CREATE TABLE IF NOT EXISTS admission_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    major_id INTEGER NOT NULL REFERENCES majors(id),
    year INTEGER NOT NULL,
    province TEXT NOT NULL,
    batch TEXT,
    max_score REAL,
    min_score REAL,
    avg_score REAL,
    min_rank INTEGER
);

-- 一分一段表
CREATE TABLE IF NOT EXISTS rank_score_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    province TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    score INTEGER NOT NULL,
    rank INTEGER NOT NULL
);

-- 性别统计
CREATE TABLE IF NOT EXISTS gender_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    major_id INTEGER REFERENCES majors(id),
    year INTEGER NOT NULL,
    male_count INTEGER,
    female_count INTEGER,
    male_pct REAL,
    female_pct REAL
);

-- 全国专业宏观数据
CREATE TABLE IF NOT EXISTS national_major_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    major_id INTEGER NOT NULL REFERENCES majors(id),
    year INTEGER NOT NULL,
    total_students REAL,
    male_pct REAL,
    female_pct REAL,
    job_market_gap REAL,
    employment_difficulty_pct REAL
);

-- 就业统计
CREATE TABLE IF NOT EXISTS employment_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    major_id INTEGER NOT NULL REFERENCES majors(id),
    year INTEGER NOT NULL,
    grad_count INTEGER,
    employed_pct REAL,
    industry_distribution TEXT,
    avg_start_salary REAL
);

-- 行业薪资统计
CREATE TABLE IF NOT EXISTS industry_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    industry_name TEXT NOT NULL,
    year INTEGER NOT NULL,
    avg_salary REAL,
    hire_count INTEGER
);

-- ===== 索引 =====
CREATE INDEX IF NOT EXISTS idx_schools_province ON schools(province);
CREATE INDEX IF NOT EXISTS idx_schools_level ON schools(level);
CREATE INDEX IF NOT EXISTS idx_campuses_school ON campuses(school_id);

CREATE INDEX IF NOT EXISTS idx_majors_name ON majors(name);
CREATE INDEX IF NOT EXISTS idx_majors_code ON majors(standard_code);

CREATE INDEX IF NOT EXISTS idx_smo_school ON school_major_offerings(school_id);
CREATE INDEX IF NOT EXISTS idx_smo_major ON school_major_offerings(major_id);

CREATE INDEX IF NOT EXISTS idx_as_year_province ON admission_scores(year, province);
CREATE INDEX IF NOT EXISTS idx_as_school ON admission_scores(school_id);
CREATE INDEX IF NOT EXISTS idx_as_major ON admission_scores(major_id);

CREATE INDEX IF NOT EXISTS idx_ap_school ON admission_plans(school_id);
CREATE INDEX IF NOT EXISTS idx_ap_year_province ON admission_plans(year, province);

CREATE INDEX IF NOT EXISTS idx_rst_key ON rank_score_tables(year, province, subject_type);
CREATE INDEX IF NOT EXISTS idx_rst_score ON rank_score_tables(score);

CREATE INDEX IF NOT EXISTS idx_gs_school ON gender_stats(school_id);
CREATE INDEX IF NOT EXISTS idx_nms_major ON national_major_stats(major_id);
CREATE INDEX IF NOT EXISTS idx_es_major ON employment_stats(major_id);
CREATE INDEX IF NOT EXISTS idx_is_industry ON industry_stats(industry_name, year);
"""


def get_ddl() -> str:
    """返回完整的建表 DDL。"""
    return DDL
