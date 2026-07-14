"""AgenticBI 端到端测试（不依赖 Web Server）— 验证单 turn：Mock LLM → SQL 生成 → 沙箱执行 → 解释。

流程：
1. 起临时 SQLite + demo_data.py 灌入电商数据
2. 元数据同步（写入 bi_table / bi_column）
3. 设置 default 角色对 phone / email 的脱敏规则（bi_column_masking）
4. 在 app_system.db 里创建 default Tenant + Datasource 记录
5. 调 ``run_chat_turn`` 跑完整 5 节点
6. 校验：intent、final_sql、tenant 注入、行级隔离、列脱敏、explanation

用法::

    PYTHONPATH=. uv run python scripts/bi_e2e_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

# 把项目根加进 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


async def _init_tortoise() -> None:
    """初始化 Tortoise ORM（连接 app_system.sqlite3），让模型可查询。"""
    from tortoise import Tortoise

    from app.core.config import APP_SETTINGS
    from app.core.config import TORTOISE_ORM as _  # noqa: F401  触发 model_validator

    await Tortoise.init(config=APP_SETTINGS.TORTOISE_ORM)


async def _ensure_datasource(db_path: str, *, tenant_id: int = 1) -> int:
    """创建/取默认 SQLite 数据源，返回 id。"""
    from app.business.bi.models import Datasource, DatasourceType, Tenant
    from app.system.services.init_helper import _safe_update_or_create

    tenant, _ = await _safe_update_or_create(
        Tenant, {"code": "default"}, {"name": "默认租户", "is_active": True}
    )
    ds, _ = await _safe_update_or_create(
        Datasource,
        {"name": "e2e_smoke"},
        {
            "type": DatasourceType.sqlite,
            "database": db_path,
            "tenant_id": tenant.id,
            "is_default": False,
            "remark": "e2e smoke (demo_data.py)",
        },
    )
    return ds.id


async def _ensure_metadata_and_masking(datasource_id: int) -> dict[str, int]:
    """同步元数据 + 设置默认脱敏规则。返回 ``{column_name: column_id}``。"""
    from app.business.bi.metadata.sync import sync_datasource
    from app.business.bi.models import BiColumn, BiTable, Datasource, MaskType
    from app.business.bi.services.masking import upsert_masking

    ds = await Datasource.filter(id=datasource_id).first()
    assert ds is not None
    result = await sync_datasource(ds)
    print(f"  metadata sync: tables={result.tables} columns={result.columns}")

    # 给 customers.phone / customers.email 设置脱敏规则（role=default）
    cust_table = await BiTable.filter(datasource_id=ds.id, name="customers").first()
    assert cust_table is not None, "customers 表未同步"

    masking_targets: dict[str, tuple[str, str]] = {
        "phone": (MaskType.phone.value, "phone"),
        "email": (MaskType.email.value, "email"),
        "id_card": (MaskType.id_card.value, "id_card"),
    }
    column_ids: dict[str, int] = {}
    for col_name, (mask_val, role) in masking_targets.items():
        col = await BiColumn.filter(table_id=cust_table.id, name=col_name).first()
        if col is None:
            continue
        await upsert_masking(column_id=col.id, role_code="default", mask_type=mask_val, user_id=1)
        column_ids[col_name] = col.id
    print(f"  masking rules: {len(column_ids)} columns protected for role 'default'")
    return column_ids


async def _run_chat_turn_for_tenant(
    *,
    user_id: int,
    tenant_id: int,
    question: str,
    datasource_id: int,
    schema_text: str,
    role_code: str = "default",
) -> dict:
    from app.business.bi.agent import run_chat_turn

    result = await run_chat_turn(
        user_id=user_id,
        tenant_id=tenant_id,
        question=question,
        datasource_id=datasource_id,
        schema_text=schema_text,
        dialect="sqlite",
        role_code=role_code,
    )

    print()
    print(f"---- intent ---- [tenant_id={tenant_id}]")
    print(f"  {result.intent}")
    print()
    print("---- final_sql ----")
    print(f"  {result.final_sql}")
    print()
    print("---- row_count / cost_ms ----")
    print(f"  rows={result.row_count}  cost={result.cost_ms}ms")
    if result.rows:
        print()
        print(f"---- top 5 rows (tenant_id={tenant_id}) ----")
        for row in result.rows[:5]:
            print(f"  {row}")
    print()
    print("---- explanation ----")
    print(f"  {result.explanation[:400]}")
    print()
    if result.error:
        print(f"---- error ----\n  {result.error}")
    return {
        "intent": result.intent,
        "final_sql": result.final_sql,
        "row_count": result.row_count,
        "rows": result.rows,
        "error": result.error,
    }


async def _check_masking(datasource_id: int) -> None:
    """验证 phone 列脱敏。"""
    from app.business.bi.agent import run_chat_turn

    result = await run_chat_turn(
        user_id=1,
        tenant_id=1,
        question="客户列表",
        datasource_id=datasource_id,
        schema_text="customers(id, name, tenant_id, phone, email, id_card)",
        dialect="sqlite",
        role_code="default",
    )
    print()
    print("---- masking 验证 ----")
    print(f"  final_sql: {result.final_sql}")
    if result.rows:
        print(f"  sample row: {result.rows[0]}")
    assert "SUBSTR" in result.final_sql.upper() or "SUBSTRING" in result.final_sql.upper(), (
        f"应改写为脱敏表达式，实际: {result.final_sql}"
    )
    if result.rows:
        masked = any("****" in str(cell) or "***" in str(cell) for cell in result.rows[0])
        assert masked, f"结果中应有脱敏后的 phone: {result.rows[0]}"
    print("  PASS: phone 列已脱敏")


async def main() -> None:
    print("=" * 60)
    print("AgenticBI 端到端冒烟（NL → SQL → 沙箱 → 解释）")
    print("=" * 60)
    await _init_tortoise()

    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "e2e.db")
        from app.business.bi.demo_data import SCHEMA_DESCRIPTION, seed_demo_db

        summary = await seed_demo_db(db, tenant_id=1, order_count=20, extra_tenants=1, drop_first=True)
        print()
        print("---- demo_data 灌入结果 ----")
        for k, v in summary.to_dict().items():
            print(f"  {k}: {v}")

        ds_id = await _ensure_datasource(db)
        print(f"  datasource id: {ds_id}")

        # 元数据同步 + 默认脱敏规则
        print()
        print("---- 元数据同步 + 脱敏规则 ----")
        await _ensure_metadata_and_masking(ds_id)

        # 场景 1：本月各产品线销售额排名（默认租户 1）
        r1 = await _run_chat_turn_for_tenant(
            user_id=1,
            tenant_id=1,
            question="本月各产品线销售额排名",
            datasource_id=ds_id,
            schema_text=SCHEMA_DESCRIPTION,
        )
        assert r1["row_count"] > 0, f"tenant 1 应有结果: {r1}"
        assert "tenant_id" in r1["final_sql"].lower(), f"final_sql 应注入 tenant_id: {r1['final_sql']}"
        t1_rows = r1["row_count"]

        # 场景 2：同一 SQL 在额外租户 2 跑，验证行级隔离
        r2 = await _run_chat_turn_for_tenant(
            user_id=2,
            tenant_id=2,
            question="本月各产品线销售额排名",
            datasource_id=ds_id,
            schema_text=SCHEMA_DESCRIPTION,
        )
        assert r2["row_count"] > 0, f"tenant 2 应有结果: {r2}"
        assert "tenant_id = 2" in r2["final_sql"] or "tenant_id=2" in r2["final_sql"]
        # 行级隔离：tenant 1 应该有更多订单
        assert t1_rows > r2["row_count"], (
            f"行级隔离失败：tenant 1 看到 {t1_rows} 行 ≥ tenant 2 看到的 {r2['row_count']} 行"
        )
        print(f"\n  PASS: tenant 隔离 — tenant 1 ({t1_rows} 行) > tenant 2 ({r2['row_count']} 行)")

        # 场景 3：列脱敏
        await _check_masking(ds_id)

    from tortoise import Tortoise
    await Tortoise.close_connections()
    print()
    print("=" * 60)
    print("E2E PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
