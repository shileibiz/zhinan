"""历年录取分数采集器。

数据来源：各省教育考试院官网（历年投档分数线/一分一段表）
参考URL模式：
  广东: https://www.eeagd.edu.cn/  → 历年分数 https://www.eeagd.edu.cn/ptgk/zxdt/
  北京: https://www.bjeea.cn/  → 录取分数
  上海: https://www.shmeea.edu.cn/  → 招生录取
  浙江: https://www.zjzs.net/  → 录取投档
  江苏: https://www.jseea.cn/  → 投档线
  山东: https://www.sdzk.cn/  → 录取分数
  河南: https://www.haeea.cn/  → 招生录取
  湖北: https://www.hbea.edu.cn/  → 录取信息
  四川: https://www.sceea.cn/  → 录取查询
  湖南: https://www.hneeb.cn/  → 录取状态
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from zhinan.collector import BaseCollector

logger = logging.getLogger(__name__)

# 各省教育考试院官网配置
# URL 模式、编码、页面结构各不相同，需要逐省调试适配
PROVINCE_CONFIGS = {
    "广东": {
        "name": "广东省教育考试院",
        "base_url": "https://www.eeagd.edu.cn",
        "score_page": "/ptgk/zxdt/",  # 历年分数列表
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [  # 不同页面可能的表格选择器
            "table.table_list",
            "table.ks-table",
            "table",
        ],
        "row_pattern": {  # 表格列匹配模式（需根据实际页面调整）
            "year": 0,
            "province": 1,
            "batch": 2,
            "min_score": 3,
            "min_rank": 4,
        },
    },
    "北京": {
        "name": "北京教育考试院",
        "base_url": "https://www.bjeea.cn",
        "score_page": "/html/gkgq/",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": ["table", ".list-table table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2, "min_rank": 3},
    },
    "上海": {
        "name": "上海市教育考试院",
        "base_url": "https://www.shmeea.edu.cn",
        "score_page": "/page/08000/",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": ["table", ".main table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
    },
    "浙江": {
        "name": "浙江省教育考试院",
        "base_url": "https://www.zjzs.net",
        "score_page": "/col/col131/index.html",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".list_table table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2, "min_rank": 3},
    },
    "江苏": {
        "name": "江苏省教育考试院",
        "base_url": "https://www.jseea.cn",
        "score_page": "/webfile/index.html",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".list_content table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
    },
    "山东": {
        "name": "山东省教育招生考试院",
        "base_url": "https://www.sdzk.cn",
        "score_page": "/NewsList.aspx?BCID=2",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".news-list table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
    },
    "河南": {
        "name": "河南省教育考试院",
        "base_url": "https://www.haeea.cn",
        "score_page": "/main_gaokao.html",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".list_table table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2, "min_rank": 3},
    },
    "湖北": {
        "name": "湖北省教育考试院",
        "base_url": "https://www.hbea.edu.cn",
        "score_page": "/html/zwgk/",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".list table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
    },
    "四川": {
        "name": "四川省教育考试院",
        "base_url": "https://www.sceea.cn",
        "score_page": "/list/lists.html",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".list_table table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2, "min_rank": 3},
    },
    "湖南": {
        "name": "湖南省教育考试院",
        "base_url": "https://www.hneeb.cn",
        "score_page": "/gk/",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": ["table", ".content table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
    },
}


def parse_html_table(soup: BeautifulSoup, config: dict) -> list[dict]:
    """尝试从 HTML 页面解析分数表格。

    这是通用框架，实际解析格式需要逐省调试适配：
    - 不同省份表格列数、顺序不同
    - 有些省份使用 PDF 而非 HTML
    - 有些省份需要先选择年份/批次

    Args:
        soup: BeautilfulSoup 解析的页面
        config: 省份配置字典

    Returns:
        解析到的录取分数记录列表
    """
    records = []
    row_pattern = config.get("row_pattern", {})

    for selector in config.get("table_selectors", ["table"]):
        table = soup.select_one(selector)
        if not table:
            continue

        rows = table.find_all("tr")
        for row in rows[1:]:  # 跳过表头
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            try:
                record = {}
                for field, col_idx in row_pattern.items():
                    if col_idx < len(cells):
                        text = cells[col_idx].get_text(strip=True)
                        record[field] = text

                if record.get("year") and record.get("min_score"):
                    records.append(record)
            except (ValueError, IndexError):
                continue

        if records:
            break  # 找到有效数据就停止

    return records


def parse_pdf_table(pdf_path_or_url: str) -> list[dict]:
    """解析 PDF 格式的分数文件。

    许多省份发布 PDF 格式的投档线文件（如广东、浙江等）。
    需要安装 pdfplumber 或 PyMuPDF 来解析。

    TODO:
        pip install pdfplumber
        import pdfplumber
        with pdfplumber.open(pdf_path_or_url) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                ...

    返回：
        解析后的记录列表（同 HTML 解析格式）
    """
    logger.warning(
        "PDF parsing is a stub — install pdfplumber and implement "
        "extract_table() logic for the specific province layout"
    )
    return []


class ScoreCollector(BaseCollector):
    """录取分数采集器 — 从各省教育考试院采集历年投档分数线。

    采集流程：
    1. 遍历已入库的学校列表（从 schools 表获取）
    2. 对每所学校的省份，访问对应考试院的分数页面
    3. 解析 HTML/PDF 表格
    4. 写入 admission_scores 表

    注意：这是框架实现，实际解析格式需要逐个省调试适配。
        - 不同省考试院页面结构差异大
        - 有的省使用 PDF 格式投档线
        - 有的省需要模拟查询表单
        - 建议逐步测试各重点省份后再扩展
    """

    name = "scores"

    def __init__(self, **kwargs):
        kwargs.setdefault("delay", 5.0)  # 分数采集要更慢，防封IP
        super().__init__(**kwargs)

    async def collect(self) -> int:
        """采集历年录取分数数据。

        当前为框架实现，可分阶段推进：

        阶段1（当前）：验证连接和页面解析
        阶段2：对每个省份抓取分数页面，解析表格
        阶段3：关联学校 ID（通过学校名称模糊匹配）
        阶段4：写入 admission_scores 表
        """
        logger.info("Score collection started (stub implementation)")

        if not self.db:
            logger.error("No database backend set, cannot save scores")
            return 0

        # 阶段1：验证考试院站点可访问性
        accessible = 0
        for province, config in PROVINCE_CONFIGS.items():
            url = config["base_url"]
            logger.info("Checking %s at %s (%s)", province, url, config["encoding"])
            try:
                soup = self.fetch_html(
                    url, encoding=config["encoding"],
                    use_custom_parser=(config.get("parser") == "lxml"),
                )
                if soup:
                    accessible += 1
                    logger.info("  ✅ %s is accessible", province)
                else:
                    logger.warning("  ⚠️  %s not accessible", province)
            except Exception as e:
                logger.error("  ❌ %s connection failed: %s", province, e)

        logger.info(
            "阶段1完成: %d/%d 省考试院可访问", accessible, len(PROVINCE_CONFIGS)
        )

        # 阶段2-4（TODO）：需要逐个省编写解析逻辑
        # 由于各省页面结构不同，建议在独立脚本中分省测试

        logger.info(
            "注意: 分数采集是框架实现，实际HTML/PDF解析需要逐省调试。"
            "参考 PROVINCE_CONFIGS 中的 URL 模式和 table_selectors。"
        )
        return 0

    async def collect_province(self, province: str, year: Optional[int] = None) -> int:
        """采集指定省份的录取分数（单省模式，便于逐省调试）。"""
        config = PROVINCE_CONFIGS.get(province)
        if not config:
            logger.error("Unknown province: %s", province)
            return 0

        logger.info("Collecting scores for %s (%s)", province, year or "all years")

        full_url = config["base_url"].rstrip("/") + config["score_page"]
        soup = self.fetch_html(
            full_url, encoding=config["encoding"],
            use_custom_parser=(config.get("parser") == "lxml"),
        )
        if not soup:
            logger.error("Failed to fetch score page for %s", province)
            return 0

        records = parse_html_table(soup, config)
        logger.info("Parsed %d records for %s", len(records), province)

        # TODO: 关联学校 ID 后写入数据库
        return len(records)

    def _parse_score_value(self, text: str) -> Optional[float]:
        """从文本中提取分数值。"""
        if not text or text.strip() in ("-", "—", "／", ""):
            return None
        # 移除可能的单位/说明文字
        cleaned = re.sub(r"[^\d.]", "", text)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _parse_rank_value(self, text: str) -> Optional[int]:
        """从文本中提取位次值。"""
        if not text or text.strip() in ("-", "—", "／", ""):
            return None
        cleaned = re.sub(r"[^\d]", "", text)
        try:
            return int(cleaned) if cleaned else None
        except ValueError:
            return None
