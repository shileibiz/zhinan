# 志愿指南

高考志愿填报数据平台。核心是提供**历史事实依据**，预测仅作参考，不做玄学承诺。

## 技术栈

- **Python** 3.11+ + **FastAPI** + **SQLite** + **BeautifulSoup**
- 异步数据库访问（aiosqlite）
- 对接层抽象设计，可平滑迁移到 PostgreSQL

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -m zhinan.cli init-db

# 启动 API 服务
python -m zhinan.cli serve --reload

# 执行数据采集
python -m zhinan.cli collect schools
```

## 项目结构

```
zhinan/
├── zhinan/              # 主包
│   ├── api.py           # FastAPI 路由
│   ├── db.py            # 数据库抽象层
│   ├── models.py        # Pydantic 模型
│   ├── schemas.py       # DDL 定义
│   ├── cli.py           # 命令行入口
│   ├── collector/       # 数据采集模块
│   └── recommender/     # 推荐引擎
├── data/                # SQLite 数据库
├── scripts/             # 工具脚本
└── requirements.txt
```

## 核心 API

| 端点 | 说明 |
|------|------|
| `GET /api/v1/schools` | 学校列表 / 搜索 |
| `GET /api/v1/schools/{id}/campuses` | 校区信息 |
| `GET /api/v1/schools/{id}/majors` | 专业列表 |
| `GET /api/v1/admission/scores` | 历年分数查询 |
| `POST /api/v1/recommend/by-score` | 分数 → 院校推荐（冲稳保）|
| `POST /api/v1/recommend/by-major` | 分数 + 专业 → 院校推荐 |
| `GET /api/v1/trends/major/{id}` | 专业趋势 |
