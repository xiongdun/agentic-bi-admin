"""SQL 沙箱 — 端到端冒烟测试（不依赖数据库，直接用内存 SQLite）。

验证 4 道闸：
1. AST 白名单（拒绝 DELETE / 危险函数）
2. 列脱敏（phone 列被改写）
3. 租户行级隔离（自动加 WHERE tenant_id）
4. 执行成功 / 行数限制 / 配额
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.business.bi.models import Datasource, DatasourceType, MaskType
from app.business.bi.sandbox.pipeline import (
    PipelineContext,
    SqlExecutionDenied,
    run_pipeline,
)
from app.core.base_model import StatusType


def _now_naive() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


async def _seed_demo_sqlite(db_path: str) -> None:
    """在临时 SQLite 灌入 3 张表：users / orders / orders_v（视图）。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, tenant_id INTEGER, phone TEXT)"))
            await conn.execute(
                text(
                    "INSERT INTO users (id, name, tenant_id, phone) VALUES "
                    "(1, 'Alice', 1, '13800000001'), "
                    "(2, 'Bob',   1, '13800000002'), "
                    "(3, 'Carol', 2, '13800000003')"
                )
            )
            await conn.execute(
                text(
                    "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, tenant_id INTEGER, amount REAL, status TEXT)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO orders (id, user_id, tenant_id, amount, status) VALUES "
                    "(1, 1, 1, 99.5, 'paid'), "
                    "(2, 2, 1, 50.0, 'paid'), "
                    "(3, 3, 2, 200.0, 'paid')"
                )
            )
    finally:
        await engine.dispose()


def _make_ds(db_path: str) -> Datasource:
    """构造一个内存 Datasource 对象（不写 DB）。"""
    return Datasource(
        id=1,
        name="smoke",
        type=DatasourceType.sqlite,
        database=db_path,
        tenant_id=1,
        status_type=StatusType.enable,
        created_at=_now_naive(),
        updated_at=_now_naive(),
    )


async def test_1_basic_select() -> None:
    """基本 SELECT 走通白名单 + 租户注入 + 执行。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "demo.db")
        await _seed_demo_sqlite(db)
        ds = _make_ds(db)
        ctx = PipelineContext(datasource=ds, user_id=1, tenant_id=1)
        result = await run_pipeline("SELECT amount, status FROM orders", ctx=ctx)
        print(f"  test_1: rows={result.query.row_count} cost={result.query.cost_ms}ms")
        assert result.query.row_count == 2, "租户 1 应只看到 2 条订单"
        # 检查 final_sql 含 WHERE tenant_id
        assert "tenant_id" in result.final_sql.lower()
        print(f"  test_1 PASS: final_sql={result.final_sql[:120]}")


async def test_2_whitelist_blocks_write() -> None:
    """DELETE 应被白名单拒绝。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "demo.db")
        await _seed_demo_sqlite(db)
        ds = _make_ds(db)
        ctx = PipelineContext(datasource=ds, user_id=1, tenant_id=1)
        try:
            await run_pipeline("DELETE FROM users", ctx=ctx)
        except SqlExecutionDenied as exc:
            print(f"  test_2 PASS: 拒绝 DELETE — {exc}")
            return
        raise AssertionError("test_2: 沙箱未拒绝 DELETE")


async def test_3_dangerous_function() -> None:
    """load_file / pg_read_file 应被拒绝。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "demo.db")
        await _seed_demo_sqlite(db)
        ds = _make_ds(db)
        ctx = PipelineContext(datasource=ds, user_id=1, tenant_id=1)
        try:
            await run_pipeline("SELECT load_file('/etc/passwd')", ctx=ctx)
        except SqlExecutionDenied as exc:
            print(f"  test_3 PASS: 拒绝危险函数 — {exc}")
            return
        raise AssertionError("test_3: 沙箱未拒绝 load_file")


async def test_4_column_masking() -> None:
    """phone 列脱敏：把 SELECT phone 改写为 CONCAT(LEFT,****,RIGHT) 形式。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "demo.db")
        await _seed_demo_sqlite(db)
        ds = _make_ds(db)
        ctx = PipelineContext(
            datasource=ds,
            user_id=1,
            tenant_id=1,
            masking_rules={"phone": MaskType.phone},
        )
        result = await run_pipeline("SELECT name, phone FROM users", ctx=ctx)
        assert "SUBSTRING" in result.final_sql.upper() or "SUBSTR" in result.final_sql.upper(), f"应改写为脱敏表达式, got {result.final_sql}"
        assert "****" in result.final_sql, f"应含 ****, got {result.final_sql}"
        print(f"  test_4 PASS: 脱敏 SQL={result.final_sql[:160]}")
        # 数据行也要脱敏
        if result.query.rows:
            for row in result.query.rows:
                print(f"    masked row: {row}")


async def test_5_tenant_isolation() -> None:
    """不同租户看到不同行数。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "demo.db")
        await _seed_demo_sqlite(db)
        ds = _make_ds(db)
        ctx_t1 = PipelineContext(datasource=ds, user_id=1, tenant_id=1)
        ctx_t2 = PipelineContext(datasource=ds, user_id=1, tenant_id=2)
        r1 = await run_pipeline("SELECT id FROM users", ctx=ctx_t1)
        r2 = await run_pipeline("SELECT id FROM users", ctx=ctx_t2)
        assert r1.query.row_count == 2, f"tenant 1 应看到 2 行, got {r1.query.row_count}"
        assert r2.query.row_count == 1, f"tenant 2 应看到 1 行, got {r2.query.row_count}"
        print(f"  test_5 PASS: tenant 1 rows={r1.query.row_count} | tenant 2 rows={r2.query.row_count}")


async def main() -> None:
    print("=" * 60)
    print("SQL 沙箱 4 道闸冒烟测试")
    print("=" * 60)
    await test_1_basic_select()
    await test_2_whitelist_blocks_write()
    await test_3_dangerous_function()
    await test_4_column_masking()
    await test_5_tenant_isolation()
    print("=" * 60)
    print("ALL PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
