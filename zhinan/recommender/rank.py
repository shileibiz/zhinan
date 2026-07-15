"""位次换算工具 — 分数 → 位次 相互转换。"""

from __future__ import annotations

from typing import Optional

from zhinan.db import DatabaseBackend


class RankConverter:
    """基于一分一段表的位次换算器。"""

    def __init__(self, db: DatabaseBackend):
        self._db = db

    async def score_to_rank(
        self, score: int, year: int, province: str, subject_type: str
    ) -> Optional[int]:
        """分数 → 位次。"""
        row = await self._db.fetch_one(
            """SELECT rank FROM rank_score_tables
               WHERE year = ? AND province = ? AND subject_type = ? AND score = ?""",
            (year, province, subject_type, score),
        )
        return row["rank"] if row else None

    async def rank_to_score(
        self, rank: int, year: int, province: str, subject_type: str
    ) -> Optional[int]:
        """位次 → 分数（取该位次对应的最低分）。"""
        row = await self._db.fetch_one(
            """SELECT score FROM rank_score_tables
               WHERE year = ? AND province = ? AND subject_type = ? AND rank <= ?
               ORDER BY rank DESC LIMIT 1""",
            (year, province, subject_type, rank),
        )
        return row["score"] if row else None

    async def find_rank_range(
        self, score: int, year: int, province: str, subject_type: str,
        up_ratio: float = 0.1, down_ratio: float = 0.2,
    ) -> tuple[Optional[int], Optional[int]]:
        """根据分数计算位次区间（用于冲稳保判断）。

        Returns:
            (min_rank_for_chong, max_rank_for_bao)
        """
        rank = await self.score_to_rank(score, year, province, subject_type)
        if rank is None:
            return None, None

        chong_rank = max(1, int(rank * (1 - up_ratio)))   # 冲：更高位次
        bao_rank = int(rank * (1 + down_ratio))            # 保：更低位次
        return chong_rank, bao_rank
