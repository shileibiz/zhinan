"""各省教育考试院数据采集器 — 一分一段表、投档线等。"""

from __future__ import annotations

import logging

from zhinan.collector import BaseCollector

logger = logging.getLogger(__name__)


class ExaminerCollector(BaseCollector):
    """教育考试院采集器 — 一分一段表、投档线。"""

    name = "examiners"

    # 各省教育考试院URL映射
    PROVINCE_SITES = {
        "北京": "https://www.bjeea.cn",
        "上海": "https://www.shmeea.edu.cn",
        "广东": "https://eea.gd.gov.cn",
        # TODO: 补充更多省份
    }

    async def collect(self) -> int:
        """采集各省考试院数据。"""
        logger.info("Examiner collection started")
        # TODO: 实现各省考试院数据采集
        # 1. 访问各省考试院网站
        # 2. 查找一分一段表页面
        # 3. 解析PDF或HTML表格
        # 4. 写入 rank_score_tables 表
        return 0
