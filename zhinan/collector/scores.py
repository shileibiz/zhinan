"""历年录取分数采集器。"""

from __future__ import annotations

import logging

from zhinan.collector import BaseCollector

logger = logging.getLogger(__name__)


class ScoreCollector(BaseCollector):
    """录取分数采集器 — 从各高校招生网／省考试院采集。"""

    name = "scores"

    async def collect(self) -> int:
        """采集历年录取分数数据。"""
        logger.info("Score collection started")
        # TODO: 实现具体的分数采集逻辑
        # 1. 遍历学校列表
        # 2. 对每所学校访问招生网历年分数页
        # 3. 解析表格数据
        # 4. 写入 admission_scores 表
        return 0
