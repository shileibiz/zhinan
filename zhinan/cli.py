#!/usr/bin/env python3
"""命令行入口 — 数据库初始化、数据采集、API 启动。"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("zhinan.cli")


def main():
    parser = argparse.ArgumentParser(
        description="志愿指南 — 高考志愿填报数据平台",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init-db
    init_parser = sub.add_parser("init-db", help="初始化数据库（建表）")
    init_parser.add_argument("--db-path", default="data/zhinan.db", help="数据库路径")

    # collect
    collect_parser = sub.add_parser("collect", help="执行数据采集")
    collect_parser.add_argument(
        "source", nargs="?", default="all",
        choices=["all", "schools", "majors", "scores", "examiners", "macro", "enrollment", "gender"],
        help="采集源",
    )
    collect_parser.add_argument(
        "--province", default=None,
        help="指定省份（仅对 scores 有效）",
    )

    # serve
    serve_parser = sub.add_parser("serve", help="启动 API 服务")
    serve_parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    serve_parser.add_argument("--port", type=int, default=8000, help="监听端口")
    serve_parser.add_argument("--reload", action="store_true", help="热重载")

    args = parser.parse_args()

    if args.command == "init-db":
        _init_db(args.db_path)
    elif args.command == "collect":
        _run_collect(args.source, args.province)
    elif args.command == "serve":
        _run_server(args.host, args.port, args.reload)


def _init_db(db_path: str) -> None:
    """初始化数据库。"""
    import asyncio
    from zhinan.db import get_backend
    from zhinan.schemas import get_ddl

    async def _init():
        backend = get_backend("sqlite", db_path=db_path)
        await backend.connect()
        await backend.run_migrations(get_ddl())
        await backend.close()
        logger.info("Database initialized at %s", db_path)

    asyncio.run(_init())


def _get_db_backend(db_path: str = "data/zhinan.db"):
    """获取数据库后端实例。"""
    from zhinan.db import get_backend
    return get_backend("sqlite", db_path=db_path)


def _run_collect(source: str, province: str | None = None) -> None:
    """执行数据采集。"""
    import asyncio
    from zhinan.collector.majors import MajorCollector
    from zhinan.collector.schools import SchoolCollector, EnrollmentCollector
    from zhinan.collector.scores import ScoreCollector
    from zhinan.collector.examiners import ExaminerCollector
    from zhinan.collector.macro import MacroCollector
    from zhinan.collector.gender import MajorGenderCollector

    collectors = {
        "schools": SchoolCollector(db_backend=_get_db_backend()),
        "majors": MajorCollector(db_backend=_get_db_backend()),
        "scores": ScoreCollector(db_backend=_get_db_backend()),
        "examiners": ExaminerCollector(),
        "macro": MacroCollector(),
        "enrollment": EnrollmentCollector(db_backend=_get_db_backend()),
        "gender": MajorGenderCollector(db_backend=_get_db_backend()),
    }

    async def run():
        if source == "all":
            for name, col in collectors.items():
                logger.info("Starting collector: %s", name)
                if hasattr(col, 'db') and col.db:
                    await col.db.connect()
                if province and hasattr(col, 'collect_province'):
                    count = await col.collect_province(province)
                else:
                    count = await col.collect()
                logger.info("Collector %s done: %d records", name, count)
        else:
            col = collectors[source]
            if hasattr(col, 'db') and col.db:
                await col.db.connect()
            if province and hasattr(col, 'collect_province'):
                count = await col.collect_province(province)
            else:
                count = await col.collect()
            logger.info("Collector %s done: %d records", source, count)

    asyncio.run(run())


def _run_server(host: str, port: int, reload: bool) -> None:
    """启动 FastAPI 服务。"""
    import uvicorn
    uvicorn.run(
        "zhinan.api:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
