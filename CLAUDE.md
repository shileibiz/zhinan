# 志愿指南 — CLAUDE.md

## 项目
志愿指南是一个高考志愿填报数据平台（zhinan），Python + FastAPI + SQLite 技术栈。

## 关键文件
- `zhinan/db.py` — 数据库抽象层（SQLite 实现，预留 PostgreSQL 接口）
- `zhinan/schemas.py` — 所有表的 DDL
- `zhinan/models.py` — Pydantic 数据模型
- `zhinan/api.py` — FastAPI 路由
- `zhinan/recommender/engine.py` — 冲稳保推荐算法
- `zhinan/collector/` — 数据采集模块

## 开发命令
```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -m zhinan.cli init-db

# 启动 API 服务 (开发模式)
python -m zhinan.cli serve --reload

# 运行测试
python -m pytest tests/
```

## 编码规范
- 异步优先：所有数据库操作使用 async/await
- 抽象接口：db.py 中 DatabaseBackend 作为抽象基类
- 类型标注：所有函数/方法必须有完整类型注解
- 文档字符串：公共 API 和复杂逻辑必须写 docstring
