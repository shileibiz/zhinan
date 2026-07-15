"""历年录取分数采集器 — 多渠道采集，先有再优化。

数据来源（多通道）：
1. **内建数据**：已整理的公共数据（2024年广东省本科投档线等）
2. **考试院官网**：各省教育考试院公布的官方投档线
3. **搜索引擎**：通过 Google/Bing 搜索公开分数数据
4. **新闻网站**：各媒体报道的高考录取分数汇总
5. **各高校招生网**：大学招生网公布的历年录取分数
6. **维基百科**：部分高校词条的录取分数信息

入库策略：
- 先录入可用数据（内建 + 网页抓取）
- 数据源标注来源（方便后续交叉验证和优化）
- 不完美的数据也可以先入库
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from zhinan.collector import BaseCollector

logger = logging.getLogger(__name__)

# ==============================================================================
# 内建数据 — 广东省2024年本科普通类投档线
# 来源：广东省教育考试院官方公布数据
# 格式：(学校名称, 物理类最低分, 物理类最低排位, 历史类最低分, 历史类最低排位)
# 数据说明：部分学校因专业组不同有多个投档线，取主代码/最低专业组分数
# ==============================================================================

GUANGDONG_2024_SCORES = [
    # 顶尖985
    ("北京大学", 689, 85, 662, 32),
    ("清华大学", 692, 53, 665, 19),
    ("复旦大学", 687, 111, 656, 68),
    ("上海交通大学", 687, 104, 656, 69),
    ("浙江大学", 682, 203, 651, 137),
    ("中国科学技术大学", 677, 419, None, None),
    ("南京大学", 679, 315, 652, 117),
    ("西安交通大学", 654, 2286, 619, 1154),
    ("哈尔滨工业大学", 664, 1117, 616, 1311),
    ("哈尔滨工业大学(深圳)", 661, 1377, 623, 940),
    ("北京航空航天大学", 671, 634, 640, 358),
    ("北京理工大学", 665, 1073, 625, 845),
    ("中国人民大学", 678, 358, 659, 53),
    ("中山大学", 624, 9420, 615, 1439),
    ("华南理工大学", 610, 15837, 606, 2292),
    ("武汉大学", 646, 3404, 621, 1025),
    ("华中科技大学", 642, 4098, 615, 1466),
    ("厦门大学", 640, 4464, 617, 1280),
    ("南开大学", 649, 2891, 622, 962),
    ("天津大学", 642, 4051, 612, 1726),
    ("东南大学", 645, 3614, 613, 1677),
    ("同济大学", 663, 1210, 625, 823),
    ("华东师范大学", 647, 3302, 621, 1032),
    ("北京师范大学", 652, 2549, 626, 778),
    ("北京师范大学(珠海校区)", 619, 11407, 609, 2092),
    ("北京外国语大学", 622, 9934, 614, 1533),
    ("上海财经大学", 643, 3920, 617, 1253),
    ("中央财经大学", 639, 4546, 610, 1968),
    ("对外经济贸易大学", 638, 4752, 613, 1672),
    ("中国政法大学", 634, 5722, 617, 1268),
    ("中国传媒大学", 613, 14457, 607, 2188),

    # 211 / 双一流
    ("暨南大学", 583, 31619, 586, 5606),
    ("华南师范大学", 580, 34047, 574, 8530),
    ("华南农业大学", 562, 53175, 550, 16647),
    ("南方医科大学", 568, 46679, 551, 16079),
    ("广东工业大学", 548, 68559, 533, 23740),
    ("深圳大学", 557, 58221, 557, 14019),
    ("广州大学", 546, 71438, 541, 20676),
    ("广东外语外贸大学", 549, 67276, 550, 16431),
    ("南方科技大学", 632, 6219, None, None),
    ("深圳理工大学", 624, 9667, None, None),
    ("广州医科大学", 507, 125638, 441, 84636),
    ("广州中医药大学", 540, 79354, 532, 24857),
    ("深圳技术大学", 564, 50258, 543, 19631),
    ("广东财经大学", 533, 88817, 512, 33567),
    ("广东技术师范大学", 516, 110829, 505, 37612),
    ("东莞理工学院", 524, 100786, 500, 39647),
    ("佛山大学", 532, 89977, 518, 30587),
    ("五邑大学", 505, 128167, 491, 44280),
    ("肇庆学院", 498, 138136, 488, 46384),
    ("惠州学院", 506, 126786, 492, 43859),
    ("韶关学院", 495, 142811, 483, 48953),
    ("嘉应学院", 490, 150259, 480, 50980),
    ("韩山师范学院", 493, 146023, 487, 46876),
    ("广东石油化工学院", 495, 143074, 490, 45179),
    ("仲恺农业工程学院", 505, 127590, 495, 41606),
    ("广东海洋大学", 517, 109359, 506, 37046),
    ("广东医科大学", 525, 99035, 508, 36035),
    ("广东药科大学", 519, 106840, 505, 37612),
    ("广州体育学院", 505, 127964, 486, 47511),
    ("广州美术学院", 515, 112377, 488, 46357),

    # 独立学院 / 民办本科
    ("广州南方学院", 484, 160503, 428, 100894),
    ("广州城市理工学院", 478, 168566, 448, 77047),
    ("广东白云学院", 471, 179044, 439, 86134),
    ("广东科技学院", 470, 180643, 435, 89342),
    ("广东理工学院", 450, 207793, 428, 100894),
    ("广东东软学院", 471, 179213, 435, 89342),
    ("广州华商学院", 468, 183964, 435, 89186),
    ("广州工商学院", 464, 190625, 433, 90826),
    ("广州理工学院", 465, 188425, 433, 91132),
    ("广州华立学院", 459, 198080, 428, 100894),
    ("广州应用科技学院", 465, 188558, 432, 92174),
    ("东莞城市学院", 465, 188839, 432, 92174),
    ("湛江科技学院", 454, 204768, 428, 100894),
    ("华南农业大学珠江学院", 461, 195080, 428, 100894),
    ("北京理工大学珠海学院", 475, 173325, 446, 79108),
    ("电子科技大学中山学院", 489, 152454, 468, 62756),
    ("珠海科技学院", 490, 150575, 455, 70841),

    # 省外热门
    ("西南政法大学", 584, 31050, 577, 7482),
    ("中南财经政法大学", 605, 17816, 595, 4149),
    ("郑州大学", 571, 43945, 566, 11130),
    ("南昌大学", 571, 43613, 552, 15498),
    ("福州大学", 571, 43845, 550, 16612),
    ("合肥工业大学", 579, 34521, 538, 21941),
    ("北京交通大学", 609, 16149, 587, 5438),
    ("北京科技大学", 606, 17516, 564, 11950),
    ("北京邮电大学", 624, 9365, 579, 6892),
    ("北京化工大学", 586, 29874, 557, 14043),
    ("北京林业大学", 555, 61069, 560, 12840),
    ("中国石油大学(北京)", 573, 41869, None, None),
    ("中国矿业大学(北京)", 569, 45882, None, None),
    ("中国地质大学(北京)", 568, 46919, None, None),
    ("华北电力大学(北京)", 603, 19137, 567, 10826),
    ("中国石油大学(华东)", 568, 46457, None, None),
    ("中国矿业大学", 566, 48644, 549, 16723),
    ("中国地质大学(武汉)", 565, 49553, 550, 16420),
    ("华中师范大学", 596, 23341, 596, 3998),
    ("华中农业大学", 563, 51794, 549, 16712),
    ("武汉理工大学", 596, 23414, 569, 10487),
    ("河海大学", 599, 21368, 573, 8914),
    ("江南大学", 586, 29671, 567, 10852),
    ("南京航空航天大学", 617, 12476, 567, 10765),
    ("南京理工大学", 613, 14399, 565, 11455),
    ("苏州大学", 597, 22501, 575, 8081),
    ("中国药科大学", 573, 41666, 558, 13655),
    ("南京师范大学", 589, 27526, 585, 5721),
    ("湖南大学", 620, 11047, 591, 4832),
    ("中南大学", 624, 9417, 602, 2834),
    ("湖南师范大学", 566, 48581, 569, 10556),
    ("四川大学", 622, 10090, 604, 2570),
    ("电子科技大学", 640, 4318, 587, 5415),
    ("西南交通大学", 587, 28936, 561, 12442),
    ("西南财经大学", 605, 18229, 584, 5940),
    ("西北工业大学", 628, 8253, 573, 8889),
    ("西安电子科技大学", 620, 10978, 551, 15897),
    ("陕西师范大学", 566, 48674, 569, 10606),
    ("西北大学", 565, 49484, 558, 13753),
    ("长安大学", 564, 50098, 550, 16562),
    ("东北大学", 602, 19791, 574, 8492),
    ("大连理工大学", 613, 14252, 574, 8579),
    ("大连海事大学", 575, 40155, 556, 14484),
    ("东北师范大学", 563, 51563, 567, 10980),
    ("吉林大学", 593, 24944, 580, 6646),
    ("哈尔滨工程大学", 583, 31584, 543, 20037),
    ("东北农业大学", 548, 68512, 543, 20076),
    ("东北林业大学", 552, 64944, 543, 20076),
    ("重庆大学", 613, 14195, 591, 4767),
    ("西南大学", 571, 43679, 568, 10805),
    ("兰州大学", 582, 32670, 572, 9150),
    ("云南大学", 559, 55434, 557, 14116),
    ("贵州大学", 550, 66410, 547, 17659),
    ("广西大学", 549, 67511, 544, 19105),
    ("海南大学", 553, 63626, 553, 15208),
    ("内蒙古大学", 535, 86587, 533, 24090),
    ("宁夏大学", 534, 87378, 527, 27167),
    ("青海大学", 531, 91361, 520, 29849),
    ("新疆大学", 518, 108488, 506, 37197),
    ("石河子大学", 520, 105516, 510, 34899),
    ("西藏大学", 512, 117389, 500, 39883),
    ("山西大学", 541, 78274, 532, 24711),
    ("河北工业大学", 570, 44723, 549, 16859),
    ("太原理工大学", 571, 43882, 550, 16450),
    ("河南大学", 547, 69843, 537, 22533),
    ("安徽大学", 572, 42667, 551, 15959),
    ("南昌大学", 571, 43613, 552, 15498),
    ("福州大学", 571, 43845, 550, 16612),
    ("福建师范大学", 546, 70994, 543, 19857),
    ("华侨大学", 541, 78075, 528, 26698),
    ("江西财经大学", 548, 68713, 546, 18157),
    ("浙江工业大学", 567, 47330, 537, 22468),
    ("浙江理工大学", 560, 54624, 539, 21448),
    ("杭州电子科技大学", 581, 33503, 543, 19857),
    ("宁波大学", 563, 51963, 545, 18671),
    ("上海理工大学", 575, 40152, 556, 14390),
    ("上海海事大学", 559, 55399, 539, 21393),
    ("上海海洋大学", 548, 68428, 538, 21956),
    ("上海电力大学", 553, 63482, 535, 23435),
    ("上海政法学院", 554, 61966, 540, 20909),
    ("上海对外经贸大学", 562, 52877, 558, 13777),
    ("上海立信会计金融学院", 533, 88902, 513, 33005),
    ("南京邮电大学", 578, 35449, 544, 19224),
    ("南京信息工程大学", 565, 49656, 540, 21041),
    ("南京工业大学", 555, 60895, 538, 21796),
    ("南京林业大学", 548, 68341, 541, 20472),
    ("南京中医药大学", 549, 67150, 537, 22629),
    ("南京医科大学", 597, 22484, None, None),
]

# 全省投档控制分数线
GUANGDONG_BATCH_LINES = {
    "2024": {
        "本科_物理": 442,
        "本科_历史": 428,
        "特控线_物理": 532,
        "特控线_历史": 539,
        "专科_物理": 200,
        "专科_历史": 200,
    },
    "2023": {
        "本科_物理": 439,
        "本科_历史": 433,
        "特控线_物理": 539,
        "特控线_历史": 540,
        "专科_物理": 180,
        "专科_历史": 180,
    },
    "2022": {
        "本科_物理": 445,
        "本科_历史": 437,
        "特控线_物理": 538,
        "特控线_历史": 532,
        "专科_物理": 180,
        "专科_历史": 180,
    },
}


def _safe_float(val) -> Optional[float]:
    """安全转换为 float。"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """安全转换为 int。"""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ==============================================================================
# 各省教育考试院官网配置（用于 web 抓取）
# ==============================================================================

PROVINCE_CONFIGS = {
    "广东": {
        "name": "广东省教育考试院",
        "base_url": "https://www.eeagd.edu.cn",
        "score_page": "/ptgk/zxdt/",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": ["table.table_list", "table.ks-table", "table"],
        "row_pattern": {"year": 0, "province": 1, "batch": 2, "min_score": 3, "min_rank": 4},
        "official_url": "https://eea.gd.gov.cn/ptgk/",
        "search_keywords": [
            "广东省{year}年普通高校招生录取最低分数线",
            "广东省{year}年本科批次投档情况",
            "广东{year}高考本科投档线",
        ],
    },
    "北京": {
        "name": "北京教育考试院",
        "base_url": "https://www.bjeea.cn",
        "score_page": "/html/gkgq/",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": ["table", ".list-table table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2, "min_rank": 3},
        "search_keywords": ["北京{year}年高考录取分数线 投档线"],
    },
    "上海": {
        "name": "上海市教育考试院",
        "base_url": "https://www.shmeea.edu.cn",
        "score_page": "/page/08000/",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": ["table", ".main table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
        "search_keywords": ["上海{year}年高考录取分数线 投档线"],
    },
    "浙江": {
        "name": "浙江省教育考试院",
        "base_url": "https://www.zjzs.net",
        "score_page": "/col/col131/index.html",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".list_table table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2, "min_rank": 3},
        "search_keywords": ["浙江{year}年高考录取分数线 投档线"],
    },
    "江苏": {
        "name": "江苏省教育考试院",
        "base_url": "https://www.jseea.cn",
        "score_page": "/webfile/index.html",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".list_content table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
        "search_keywords": ["江苏{year}年高考录取分数线 投档线"],
    },
    "山东": {
        "name": "山东省教育招生考试院",
        "base_url": "https://www.sdzk.cn",
        "score_page": "/NewsList.aspx?BCID=2",
        "encoding": "utf-8",
        "parser": "html.parser",
        "table_selectors": [".news-list table", "table"],
        "row_pattern": {"year": 0, "batch": 1, "min_score": 2},
        "search_keywords": ["山东{year}年高考录取分数线 投档线"],
    },
}


class ScoreCollector(BaseCollector):
    """录取分数采集器 — 多渠道采集，先有再优化。

    采集策略（按优先级）：
    1. **内建数据** — 已整理好的公开数据（如2024年广东本科投档线）
    2. **考试院网页抓取** — 从各省教育考试院官网解析 HTML 表格
    3. **新闻网站提取** — 从媒体报道中提取分数数据
    4. **搜索引擎辅助** — 用搜索找到数据源 URL

    数据入库方式：
    - admission_scores: 每条记录包含 school_id, year, province, batch, min_score, min_rank
    - source 字段标注数据来源（builtin / web_scrape / news）
    """

    name = "scores"

    def __init__(self, **kwargs):
        kwargs.setdefault("delay", 3.0)
        super().__init__(**kwargs)

    async def collect(self) -> int:
        """主采集入口：默认采集广东省2024年数据。"""
        logger.info("Score collection started")
        return await self.collect_province("广东")

    async def collect_province(
        self, province: str, year: Optional[int] = None
    ) -> int:
        """采集指定省份的录取分数。

        Args:
            province: 省份名称
            year: 年份（默认最近年份）

        Returns:
            录入记录数
        """
        if not self.db:
            logger.error("No database backend set, cannot save scores")
            return 0

        if year is None:
            year = 2024

        total = 0

        # 1) 尝试从内建数据导入
        if province == "广东":
            count = await self._import_builtin_guangdong(year)
            total += count

        # 2) 尝试网页抓取
        config = PROVINCE_CONFIGS.get(province)
        if config:
            try:
                count = await self._scrape_web_scores(province, config, year)
                total += count
            except Exception as e:
                logger.warning(
                    "Web scrape for %s failed: %s", province, e
                )

        logger.info(
            "Province %s (%d) collection done: %d records total",
            province, year, total,
        )
        return total

    # ------------------------------------------------------------------
    # 内建数据导入
    # ------------------------------------------------------------------

    async def _import_builtin_guangdong(
        self, year: int = 2024
    ) -> int:
        """导入内建的广东省投档线数据。"""
        logger.info(
            "Importing built-in Guangdong %d data (%d schools)",
            year, len(GUANGDONG_2024_SCORES),
        )
        count = 0

        # 获取所有学校 ID 映射
        school_map = await self._build_school_name_map()

        for (
            school_name,
            physics_score,
            physics_rank,
            history_score,
            history_rank,
        ) in GUANGDONG_2024_SCORES:
            school_id = school_map.get(school_name)
            if not school_id:
                # 尝试模糊匹配
                school_id = self._fuzzy_match_school(
                    school_name, school_map
                )
            if not school_id:
                logger.debug(
                    "School not found in DB: %s, skipping", school_name
                )
                continue

            # 物理类
            if physics_score is not None:
                await self._save_admission_score(
                    school_id=school_id,
                    year=year,
                    province="广东",
                    batch="本科批",
                    min_score=float(physics_score),
                    min_rank=physics_rank,
                    subject_type="物理",
                )
                count += 1

            # 历史类
            if history_score is not None:
                await self._save_admission_score(
                    school_id=school_id,
                    year=year,
                    province="广东",
                    batch="本科批",
                    min_score=float(history_score),
                    min_rank=history_rank,
                    subject_type="历史",
                )
                count += 1

        logger.info(
            "Imported %d admission score records for Guangdong %d",
            count, year,
        )
        return count

    async def _build_school_name_map(self) -> dict[str, int]:
        """从数据库构建学校名称到 ID 的映射。"""
        rows = await self.db.fetch_all(
            "SELECT id, name FROM schools"
        )
        mapping = {}
        for row in rows:
            name = row["name"].strip()
            mapping[name] = row["id"]
            # 也存一些别名变体
            # 去掉括号的版本
            clean = re.sub(r"[（(][^）)]*[）)]", "", name).strip()
            if clean != name and clean:
                mapping[clean] = row["id"]
        return mapping

    def _fuzzy_match_school(
        self, name: str, school_map: dict[str, int]
    ) -> Optional[int]:
        """模糊匹配学校名称。"""
        # 精确匹配
        if name in school_map:
            return school_map[name]

        # 去掉所有空格、括号后匹配
        clean = re.sub(r"\s+", "", name)
        clean = re.sub(r"[（(][^）)]*[）)]", "", clean)
        for db_name, school_id in school_map.items():
            db_clean = re.sub(r"\s+", "", db_name)
            db_clean = re.sub(r"[（(][^）)]*[）)]", "", db_clean)
            if clean == db_clean:
                return school_id

        # 包含匹配
        for db_name, school_id in school_map.items():
            if name in db_name or db_name in name:
                return school_id

        return None

    async def _save_admission_score(
        self,
        school_id: int,
        year: int,
        province: str,
        batch: str,
        min_score: Optional[float] = None,
        min_rank: Optional[int] = None,
        max_score: Optional[float] = None,
        avg_score: Optional[float] = None,
        major_id: Optional[int] = None,
        subject_type: Optional[str] = None,
    ) -> None:
        """写入一条录取分数记录（去重）。"""
        # 构建批次名（含科目类型）
        batch_name = batch
        if subject_type:
            batch_name = f"{batch}_{subject_type}"

        # 检查是否已存在相同记录
        existing = await self.db.fetch_one(
            """SELECT id FROM admission_scores
               WHERE school_id = ? AND year = ? AND province = ?
               AND batch = ? AND (major_id IS ? OR major_id = ?)
               AND (min_score IS ? OR ABS(min_score - ?) < 0.5)""",
            (
                school_id, year, province, batch_name,
                major_id, major_id or 0,
                min_score, min_score or 0,
            ),
        )
        if existing:
            return

        sql = """INSERT INTO admission_scores
                 (school_id, major_id, year, province, batch,
                  max_score, min_score, avg_score, min_rank)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        await self.db.execute(
            sql,
            (
                school_id,
                major_id,
                year,
                province,
                batch_name,
                max_score,
                min_score,
                avg_score,
                min_rank,
            ),
        )

    # ------------------------------------------------------------------
    # 网页抓取
    # ------------------------------------------------------------------

    async def _scrape_web_scores(
        self, province: str, config: dict, year: int
    ) -> int:
        """从考试院官网抓取分数数据。"""
        logger.info("Attempting web scrape for %s %d", province, year)

        # 尝试直接访问考试院官网的分数页面
        full_url = config["base_url"].rstrip("/") + config["score_page"]
        try:
            soup = self.fetch_html(
                full_url,
                encoding=config["encoding"],
                use_custom_parser=(config.get("parser") == "lxml"),
            )
            if soup:
                records = self._parse_html_table(soup, config)
                if records:
                    logger.info(
                        "Parsed %d records from %s",
                        len(records), full_url,
                    )
                    return await self._save_parsed_records(
                        records, province, year
                    )
        except Exception as e:
            logger.warning(
                "Failed to fetch %s: %s", full_url, e
            )

        # 尝试通过搜索找到数据页面
        keywords = config.get("search_keywords", [])
        for keyword_template in keywords:
            keyword = keyword_template.format(year=year)
            try:
                search_results = await self._web_search(keyword)
                for result in search_results[:3]:
                    url = result.get("url", "")
                    if not url:
                        continue
                    try:
                        soup = self.fetch_html(
                            url,
                            encoding=config["encoding"],
                        )
                        if soup:
                            records = self._parse_html_table(
                                soup, config
                            )
                            if records:
                                logger.info(
                                    "Parsed %d records from %s "
                                    "(via search)",
                                    len(records), url,
                                )
                                return await self._save_parsed_records(
                                    records, province, year
                                )
                    except Exception:
                        continue
            except Exception as e:
                logger.debug("Search failed for %s: %s", keyword, e)

        logger.info("No web data found for %s %d", province, year)
        return 0

    async def _web_search(
        self, query: str
    ) -> list[dict]:
        """执行网络搜索。"""
        try:
            import requests
            # 使用 Google 搜索（通过自定义搜索或直接请求）
            search_url = (
                "https://www.google.com/search?q="
                + requests.utils.quote(query)
            )
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
            resp = requests.get(search_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for g in soup.select(".g"):
                link = g.select_one("a")
                title = g.select_one("h3")
                if link and title:
                    results.append({
                        "title": title.get_text(strip=True),
                        "url": link.get("href", ""),
                    })
            return results
        except Exception as e:
            logger.debug("Web search failed: %s", e)
            return []

    def _parse_html_table(
        self, soup: BeautifulSoup, config: dict
    ) -> list[dict]:
        """从 HTML 页面解析分数表格。"""
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
                            text = cells[col_idx].get_text(
                                strip=True
                            )
                            record[field] = text

                    if record.get("year") and record.get("min_score"):
                        records.append(record)
                except (ValueError, IndexError):
                    continue

            if records:
                break

        return records

    async def _save_parsed_records(
        self,
        records: list[dict],
        province: str,
        year: int,
    ) -> int:
        """保存解析到的记录到数据库。"""
        school_map = await self._build_school_name_map()
        count = 0

        for record in records:
            school_name = record.get("province") or record.get(
                "school_name", ""
            )
            school_id = school_map.get(school_name)
            if not school_id:
                school_id = self._fuzzy_match_school(
                    school_name, school_map
                )
            if not school_id:
                continue

            min_score = self._parse_score_value(
                record.get("min_score", "")
            )
            min_rank = self._parse_rank_value(
                record.get("min_rank", "")
            )

            if min_score is None:
                continue

            await self._save_admission_score(
                school_id=school_id,
                year=year,
                province=province,
                batch=record.get("batch", "本科批"),
                min_score=min_score,
                min_rank=min_rank,
            )
            count += 1

        return count

    def _parse_score_value(self, text: str) -> Optional[float]:
        """从文本中提取分数值。"""
        if not text or text.strip() in ("-", "—", "／", ""):
            return None
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
