"""数据采集 — 基类与工具函数。"""

from __future__ import annotations

import abc
import json
import logging
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 多个 User-Agent 轮换
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class BaseCollector(abc.ABC):
    """所有采集器的基类。

    内置代理轮换、慢速采集、随机化、重试机制。
    """

    name: str = "base"

    def __init__(self, delay: float = 3.0, max_retries: int = 5,
                 use_proxy: bool = True, db_backend=None):
        self.delay = delay           # 基础延迟（秒）
        self.max_retries = max_retries
        self.use_proxy = use_proxy
        self.db = db_backend
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._proxy_list = []
        self._proxy_index = 0

    def _random_delay(self):
        """随机延迟 2x-5x 基础值，避免固定频率被检测"""
        jitter = random.uniform(self.delay * 2, self.delay * 5)
        time.sleep(jitter)

    def _rotate_ua(self):
        """轮换 User-Agent"""
        self.session.headers["User-Agent"] = random.choice(USER_AGENTS)

    def _load_proxies(self):
        """加载代理列表。
        优先级：1. 本地缓存 2. 从公开代理源获取
        """
        if self._proxy_list:
            return

        # 从公开免费代理 API 获取（多个源，一个挂了用另一个）
        proxy_sources = [
            "https://proxylist.geonode.com/api/proxy-list?limit=20&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps",
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        ]

        for source in proxy_sources:
            try:
                resp = requests.get(source, timeout=10)
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    # Try JSON first (by content-type or detect), fall back to text
                    if "json" in ct or resp.text.strip().startswith("{"):
                        data = resp.json()
                        if isinstance(data, dict) and "data" in data:
                            self._proxy_list = [
                                f"{p['ip']}:{p['port']}"
                                for p in data["data"]
                                if p.get("protocols", [])
                            ]
                        elif isinstance(data, list):
                            # Some APIs return a flat list ["ip:port", ...]
                            self._proxy_list = [str(x).strip() for x in data if ":" in str(x)]
                    else:
                        # Plain text, one proxy per line
                        self._proxy_list = [
                            line.strip() for line in resp.text.split("\n")
                            if line.strip() and ":" in line
                        ]
                    if self._proxy_list:
                        random.shuffle(self._proxy_list)
                        logger.info("Loaded %d proxies from %s", len(self._proxy_list), source.split("/")[2])
                        return
            except Exception as e:
                logger.warning("Proxy source %s failed: %s", source.split("/")[2], e)

        # 内建几个备用代理源
        logger.warning("No proxies loaded from remote sources, will try direct connection fallback")

    def _get_proxy(self) -> Optional[dict]:
        """轮换获取下一个代理"""
        if not self.use_proxy:
            return None
        self._load_proxies()
        if not self._proxy_list:
            return None
        proxy = self._proxy_list[self._proxy_index % len(self._proxy_list)]
        self._proxy_index += 1
        return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

    def _direct_fallback(self, url: str, encoding: str = "utf-8",
                         use_custom_parser: bool = False) -> Optional[BeautifulSoup]:
        """代理全部失败后的直连回退。"""
        try:
            logger.info("Trying direct connection as last resort for %s", url)
            resp = self.session.get(url, timeout=60)
            resp.encoding = encoding
            resp.raise_for_status()
            self._random_delay()
            return BeautifulSoup(resp.text, "html.parser" if not use_custom_parser else "lxml")
        except Exception as e:
            logger.error("Direct connection also failed for %s: %s", url, e)
            return None

    def fetch_html(self, url: str, encoding: str = "utf-8",
                   use_custom_parser: bool = False) -> Optional[BeautifulSoup]:
        """获取网页并解析为 BeautifulSoup 对象。

        支持：代理轮换、UA 随机化、慢速采集、自动重试。
        """
        for attempt in range(1, self.max_retries + 1):
            self._rotate_ua()
            proxy = self._get_proxy()

            try:
                resp = self.session.get(
                    url, timeout=60,
                    proxies=proxy,
                )
                resp.encoding = encoding
                resp.raise_for_status()
                # 成功后随机延迟
                self._random_delay()
                return BeautifulSoup(resp.text, "html.parser" if not use_custom_parser else "lxml")

            except requests.exceptions.ProxyError as e:
                logger.warning("Proxy failed on attempt %d/%d for %s: %s",
                               attempt, self.max_retries, url, e)
                # 代理不行就标记移除
                if proxy and self._proxy_list:
                    bad_idx = self._proxy_index % len(self._proxy_list)
                    self._proxy_list.pop(bad_idx)
                if attempt < self.max_retries:
                    # 指数退避
                    time.sleep(self.delay * (2 ** attempt))
                else:
                    # 最后一次，用直连试试
                    return self._direct_fallback(url, encoding, use_custom_parser)

            except requests.RequestException as e:
                logger.warning("Attempt %d/%d failed for %s: %s (proxy=%s)",
                               attempt, self.max_retries, url, e,
                               proxy.get("http", "none") if proxy else "none")
                if attempt < self.max_retries:
                    time.sleep(self.delay * (2 ** attempt))
                else:
                    return self._direct_fallback(url, encoding, use_custom_parser)

        logger.error("All %d attempts failed for %s", self.max_retries, url)
        return None

    @abc.abstractmethod
    async def collect(self) -> int:
        ...

    def __del__(self):
        self.session.close()
