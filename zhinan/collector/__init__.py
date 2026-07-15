"""数据采集 — 基类与工具函数。"""

from __future__ import annotations

import abc
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class BaseCollector(abc.ABC):
    """所有采集器的基类。

    子类需实现 collect() 方法。
    """

    name: str = "base"

    def __init__(self, delay: float = 1.0, max_retries: int = 3):
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch_html(self, url: str, encoding: str = "utf-8") -> Optional[BeautifulSoup]:
        """获取网页并解析为 BeautifulSoup 对象。"""
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=30)
                resp.encoding = encoding
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "html.parser")
            except requests.RequestException as e:
                logger.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt, self.max_retries, url, e,
                )
                if attempt < self.max_retries:
                    import time
                    time.sleep(self.delay * attempt)
        logger.error("All %d attempts failed for %s", self.max_retries, url)
        return None

    @abc.abstractmethod
    async def collect(self) -> int:
        """执行采集，返回采集记录数。"""
        ...

    def __del__(self):
        self.session.close()
