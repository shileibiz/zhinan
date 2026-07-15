"""宏观数据采集器 — 全国专业统计数据。"""

from __future__ import annotations

import logging

from zhinan.collector import BaseCollector

logger = logging.getLogger(__name__)


class MacroCollector(BaseCollector):
    """宏观数据采集器 — 就业数据、全国专业统计。"""

    name = "macro"

    async def collect(self) -> int:
        """采集宏观就业数据。"""
        logger.info("Macro data collection started")
        # TODO: 从国家统计局/教育部网站采集
        # 1. 全国专业在读人数
        # 2. 就业率数据
        # 3. 行业薪资数据
        return 0
