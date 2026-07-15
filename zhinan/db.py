"""数据库抽象层 — 定义统一接口，当前使用 SQLite 实现。

扩展方式：
  1. 继承 DatabaseBackend 实现所有抽象方法
  2. 在 get_backend() 中注册新后端
"""

from __future__ import annotations

import abc
import contextlib
import os
from pathlib import Path
from typing import Any, AsyncContextManager, AsyncIterator, Optional

# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------

class DatabaseBackend(abc.ABC):
    """所有数据库后端必须实现的接口。"""

    @abc.abstractmethod
    async def connect(self) -> None:
        """建立连接池／连接。"""
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """关闭所有连接。"""
        ...

    @abc.abstractmethod
    async def execute(self, sql: str, params: Optional[dict[str, Any]] | tuple = None) -> Any:
        """执行写操作 (INSERT / UPDATE / DELETE / DDL)，返回 cursor。"""
        ...

    @abc.abstractmethod
    async def fetch_all(self, sql: str, params: Optional[dict[str, Any]] | tuple = None) -> list[dict[str, Any]]:
        """查询多行，返回 list[dict]。"""
        ...

    @abc.abstractmethod
    async def fetch_one(self, sql: str, params: Optional[dict[str, Any]] | tuple = None) -> Optional[dict[str, Any]]:
        """查询单行，返回 dict 或 None。"""
        ...

    @abc.abstractmethod
    async def execute_many(self, sql: str, params_list: list[tuple]) -> Any:
        """批量写入（事务内）。"""
        ...

    @abc.abstractmethod
    async def run_migrations(self, ddl: str) -> None:
        """执行 DDL 建表／迁移。"""
        ...


# ---------------------------------------------------------------------------
# SQLite 实现
# ---------------------------------------------------------------------------

class SQLiteBackend(DatabaseBackend):
    """aiosqlite 异步 SQLite 后端。"""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: Any = None  # aiosqlite.Connection

    async def connect(self) -> None:
        import aiosqlite
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: Optional[dict[str, Any]] | tuple = None) -> Any:
        if isinstance(params, dict):
            cursor = await self._conn.execute(sql, params)
        else:
            cursor = await self._conn.execute(sql, params or ())
        await self._conn.commit()
        return cursor

    async def fetch_all(self, sql: str, params: Optional[dict[str, Any]] | tuple = None) -> list[dict[str, Any]]:
        if isinstance(params, dict):
            cursor = await self._conn.execute(sql, params)
        else:
            cursor = await self._conn.execute(sql, params or ())
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetch_one(self, sql: str, params: Optional[dict[str, Any]] | tuple = None) -> Optional[dict[str, Any]]:
        if isinstance(params, dict):
            cursor = await self._conn.execute(sql, params)
        else:
            cursor = await self._conn.execute(sql, params or ())
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def execute_many(self, sql: str, params_list: list[tuple]) -> Any:
        cursor = await self._conn.executemany(sql, params_list)
        await self._conn.commit()
        return cursor

    async def run_migrations(self, ddl: str) -> None:
        await self._conn.executescript(ddl)
        await self._conn.commit()


# ---------------------------------------------------------------------------
# 后端工厂
# ---------------------------------------------------------------------------

_BACKENDS: dict[str, type[DatabaseBackend]] = {
    "sqlite": SQLiteBackend,
}


def register_backend(name: str, cls: type[DatabaseBackend]) -> None:
    """注册新的数据库后端实现。"""
    _BACKENDS[name] = cls


def get_backend(name: str = "sqlite", **kwargs: Any) -> DatabaseBackend:
    """获取数据库后端实例。

    Args:
        name: 后端名称，默认 "sqlite"。
        **kwargs: 传递给后端构造函数的参数 (例如 db_path)。

    Returns:
        DatabaseBackend 实例。

    Raises:
        ValueError: 未知后端名称。
    """
    cls = _BACKENDS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown backend: {name!r}. Available: {list(_BACKENDS)}"
        )
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# 便捷上下文管理器
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def open_db(name: str = "sqlite", **kwargs: Any) -> AsyncIterator[DatabaseBackend]:
    """上下文管理器方式打开数据库，自动连接／关闭。"""
    db = get_backend(name, **kwargs)
    await db.connect()
    try:
        yield db
    finally:
        await db.close()
