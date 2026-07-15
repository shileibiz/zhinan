"""高校信息采集器 — 从阳光高考平台采集高校名单。"""

from __future__ import annotations

import logging
import re
from typing import Optional

from zhinan.collector import BaseCollector

logger = logging.getLogger(__name__)


class SchoolCollector(BaseCollector):
    """高校信息采集器。"""

    name = "schools"

    # 阳光高考高校名单页
    BASE_URL = "https://gaokao.chsi.com.cn/sch/search.do"

    async def collect(self) -> int:
        """采集所有高校基本信息。"""
        count = 0
        page = 1
        while True:
            soup = self.fetch_html(f"{self.BASE_URL}?page={page}")
            if soup is None:
                break

            schools = self._parse_school_list(soup)
            if not schools:
                break

            # TODO: 保存到数据库
            logger.info("Page %d: found %d schools", page, len(schools))
            count += len(schools)
            page += 1

            import time
            time.sleep(self.delay)

        logger.info("School collection done: %d schools total", count)
        return count

    def _parse_school_list(self, soup) -> list[dict]:
        """解析高校列表页，返回学校信息列表。"""
        schools = []
        # 解析逻辑 - 根据实际页面结构调整
        for item in soup.select("table.chsitable tr")[1:]:
            cols = item.find_all("td")
            if len(cols) < 3:
                continue
            schools.append({
                "name": cols[0].get_text(strip=True),
                "province": cols[1].get_text(strip=True),
                "level": self._extract_level(cols[2]),
            })
        return schools

    def _extract_level(self, td) -> str:
        """提取学校层次标签。"""
        text = td.get_text(strip=True)
        levels = []
        if "985" in text:
            levels.append("985")
        if "211" in text:
            levels.append("211")
        if "双一流" in text:
            levels.append("双一流")
        return "/".join(levels) if levels else ""
