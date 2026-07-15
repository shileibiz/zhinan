"""推荐引擎 — 冲稳保推荐算法。

核心逻辑：
  冲：位次比考生高 0~10% 的院校专业（够一够有机会）
  稳：位次在考生位次 ±5% 以内的院校专业（较稳妥）
  保：位次比考生低 10~20% 的院校专业（确保有学上）
"""

from __future__ import annotations

from typing import Optional

from zhinan.db import DatabaseBackend
from zhinan.models import RecommendItem
from zhinan.recommender.rank import RankConverter


class RecommendEngine:
    """志愿推荐引擎。"""

    def __init__(self, db: DatabaseBackend):
        self._db = db
        self._converter = RankConverter(db)

    async def recommend_by_score(
        self,
        score: int,
        province: str,
        year: int,
        subject_type: str = "物理",
        top_n: int = 20,
    ) -> list[RecommendItem]:
        """根据分数推荐院校专业（冲稳保）。"""
        # 1. 获取考生位次
        rank = await self._converter.score_to_rank(score, year, province, subject_type)
        if rank is None:
            # 无法转换位次，直接按分数区间查
            return await self._recommend_by_score_fallback(
                score, province, year, top_n
            )

        # 2. 查往年该位次附近的录取数据
        chong_upper = max(1, int(rank * 0.90))     # 冲：位次更高（更难考）
        wen_lower = int(rank * 0.95)
        wen_upper = int(rank * 1.05)
        bao_lower = int(rank * 1.10)
        bao_upper = int(rank * 1.30)

        results = []

        # 冲 — 位次 90%~95%
        chong_rows = await self._db.fetch_all(
            """SELECT s.name AS school_name, m.name AS major_name,
                      a.min_score, a.avg_score, a.min_rank, a.year
               FROM admission_scores a
               JOIN schools s ON s.id = a.school_id
               JOIN majors m ON m.id = a.major_id
               WHERE a.year = ? AND a.province = ?
                 AND a.min_rank BETWEEN ? AND ?
               ORDER BY a.min_rank ASC
               LIMIT ?""",
            (year - 1, province, chong_upper, wen_lower - 1, top_n),
        )
        for r in chong_rows:
            results.append(RecommendItem(
                school_name=r["school_name"],
                major_name=r["major_name"],
                probability="冲",
                min_score=r["min_score"],
                avg_score=r["avg_score"],
                min_rank=r["min_rank"],
                year=r["year"],
            ))

        # 稳 — 位次 95%~105%
        wen_rows = await self._db.fetch_all(
            """SELECT s.name AS school_name, m.name AS major_name,
                      a.min_score, a.avg_score, a.min_rank, a.year
               FROM admission_scores a
               JOIN schools s ON s.id = a.school_id
               JOIN majors m ON m.id = a.major_id
               WHERE a.year = ? AND a.province = ?
                 AND a.min_rank BETWEEN ? AND ?
               ORDER BY a.min_rank ASC
               LIMIT ?""",
            (year - 1, province, wen_lower, wen_upper, top_n),
        )
        for r in wen_rows:
            results.append(RecommendItem(
                school_name=r["school_name"],
                major_name=r["major_name"],
                probability="稳",
                min_score=r["min_score"],
                avg_score=r["avg_score"],
                min_rank=r["min_rank"],
                year=r["year"],
            ))

        # 保 — 位次 110%~130%
        bao_rows = await self._db.fetch_all(
            """SELECT s.name AS school_name, m.name AS major_name,
                      a.min_score, a.avg_score, a.min_rank, a.year
               FROM admission_scores a
               JOIN schools s ON s.id = a.school_id
               JOIN majors m ON m.id = a.major_id
               WHERE a.year = ? AND a.province = ?
                 AND a.min_rank BETWEEN ? AND ?
               ORDER BY a.min_rank ASC
               LIMIT ?""",
            (year - 1, province, bao_lower, bao_upper, top_n),
        )
        for r in bao_rows:
            results.append(RecommendItem(
                school_name=r["school_name"],
                major_name=r["major_name"],
                probability="保",
                min_score=r["min_score"],
                avg_score=r["avg_score"],
                min_rank=r["min_rank"],
                year=r["year"],
            ))

        return results[:top_n]

    async def recommend_by_major(
        self,
        score: int,
        province: str,
        year: int,
        major_name: str,
        subject_type: str = "物理",
        top_n: int = 20,
    ) -> list[RecommendItem]:
        """分数 + 意向专业 → 院校推荐。"""
        rank = await self._converter.score_to_rank(score, year, province, subject_type)
        if rank is None:
            return await self._recommend_by_major_fallback(
                score, province, year, major_name, top_n
            )

        # 按位次 ±20% 查目标专业
        lower = max(1, int(rank * 0.85))
        upper = int(rank * 1.30)

        rows = await self._db.fetch_all(
            """SELECT s.name AS school_name, m.name AS major_name,
                      a.min_score, a.avg_score, a.min_rank, a.year
               FROM admission_scores a
               JOIN schools s ON s.id = a.school_id
               JOIN majors m ON m.id = a.major_id
               WHERE a.year = ? AND a.province = ?
                 AND m.name LIKE ?
                 AND a.min_rank BETWEEN ? AND ?
               ORDER BY ABS(a.min_rank - ?) ASC
               LIMIT ?""",
            (year - 1, province, f"%{major_name}%", lower, upper, rank, top_n),
        )

        results = []
        for r in rows:
            # 判断冲稳保
            rel_rank = r["min_rank"] / rank if rank > 0 else 1
            if rel_rank < 0.95:
                prob = "冲"
            elif rel_rank <= 1.05:
                prob = "稳"
            else:
                prob = "保"

            results.append(RecommendItem(
                school_name=r["school_name"],
                major_name=r["major_name"],
                probability=prob,
                min_score=r["min_score"],
                avg_score=r["avg_score"],
                min_rank=r["min_rank"],
                year=r["year"],
            ))

        return results

    async def _recommend_by_score_fallback(
        self, score: int, province: str, year: int, top_n: int
    ) -> list[RecommendItem]:
        """没有位次表时的降级推荐：直接按分数区间查询。"""
        rows = await self._db.fetch_all(
            """SELECT s.name AS school_name, m.name AS major_name,
                      a.min_score, a.avg_score, a.min_rank, a.year
               FROM admission_scores a
               JOIN schools s ON s.id = a.school_id
               JOIN majors m ON m.id = a.major_id
               WHERE a.year = ? AND a.province = ?
                 AND a.min_score BETWEEN ? AND ?
               ORDER BY a.min_score DESC
               LIMIT ?""",
            (year - 1, province, score - 10, score + 30, top_n),
        )
        return [
            RecommendItem(
                school_name=r["school_name"],
                major_name=r["major_name"],
                probability="参考",
                min_score=r["min_score"],
                avg_score=r["avg_score"],
                min_rank=r["min_rank"],
                year=r["year"],
            )
            for r in rows
        ]

    async def _recommend_by_major_fallback(
        self, score: int, province: str, year: int, major_name: str, top_n: int
    ) -> list[RecommendItem]:
        """没有位次表时的降级推荐：分数区间 + 专业名。"""
        rows = await self._db.fetch_all(
            """SELECT s.name AS school_name, m.name AS major_name,
                      a.min_score, a.avg_score, a.min_rank, a.year
               FROM admission_scores a
               JOIN schools s ON s.id = a.school_id
               JOIN majors m ON m.id = a.major_id
               WHERE a.year = ? AND a.province = ?
                 AND m.name LIKE ?
                 AND a.min_score BETWEEN ? AND ?
               ORDER BY a.min_score DESC
               LIMIT ?""",
            (year - 1, province, f"%{major_name}%", score - 10, score + 30, top_n),
        )
        return [
            RecommendItem(
                school_name=r["school_name"],
                major_name=r["major_name"],
                probability="参考",
                min_score=r["min_score"],
                avg_score=r["avg_score"],
                min_rank=r["min_rank"],
                year=r["year"],
            )
            for r in rows
        ]
