"""元数据相关 service — API 层调用的查询/聚合。

跟 ``app.business.bi.metadata.sync`` 的差异：
- ``sync`` 负责把数据源里真实的 schema 写入 bi_table/bi_column
- 本文件负责按 datasource/表名查 / 详情 / demo 库生成
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.business.bi.models import (
    BiColumn,
    BiTable,
    Datasource,
    DatasourceType,
    Tenant,
)
from app.business.bi.services.datasource import create_datasource
from app.system.services.init_helper import _safe_update_or_create


def _now_naive() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


async def list_tables(
    *,
    datasource_id: int | None = None,
    name: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[int, list[BiTable]]:
    """分页查询表清单（含每张表的列数）。"""
    qs = BiTable.all().prefetch_related("columns")
    if datasource_id is not None:
        qs = qs.filter(datasource_id=datasource_id)
    if name:
        qs = qs.filter(name__icontains=name)
    total = await qs.count()
    tables = await qs.order_by("-id").offset(offset).limit(limit)
    # 列出每张表的列数（prefetch 后无 count 属性，手动统计）
    for t in tables:
        t.column_count = len(t.columns) if t.columns else 0
    return total, list(tables)


async def get_datasource_by_id(ds_id: int) -> Datasource | None:
    """按 id 取数据源（带状态过滤：仅启用）。"""
    from app.core.base_model import StatusType

    return await Datasource.filter(id=ds_id, status_type=StatusType.enable).first()


async def get_table_detail(table_id: int) -> BiTable:
    """获取表 + 全部列。"""
    table = await BiTable.filter(id=table_id).prefetch_related("columns").first()
    if table is None:
        from tortoise.exceptions import DoesNotExist

        raise DoesNotExist(f"BiTable<{table_id}> not found")
    if not table.columns:
        # prefetch 异常时降级
        cols = await BiColumn.filter(table_id=table_id).order_by("ordinal")
        await table.fetch_related("columns")  # 确保反向关系就绪
        for c in cols:  # noqa: PERF102  prefetch 失败的兜底
            pass
    return table


# ---- demo 库生成 ----

DEMO_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category_id INTEGER NOT NULL,
  price REAL NOT NULL,
  stock INTEGER NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  tenant_id INTEGER NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  tenant_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  amount REAL NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  price REAL NOT NULL
);
"""

_PRODUCT_LINE_NAMES = [
    "手机数码",
    "电脑办公",
    "家用电器",
    "服饰内衣",
    "美妆个护",
    "母婴玩具",
    "食品生鲜",
    "运动户外",
    "家居家具",
    "图书音像",
]

_CUSTOMER_NAMES = [
    "张三",
    "李四",
    "王五",
    "赵六",
    "钱七",
    "孙八",
    "周九",
    "吴十",
]


async def _generate_demo_data(db_path: str, *, force: bool = False) -> dict:
    """在给定的 SQLite 文件里灌入电商示例数据。"""
    path = Path(db_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", echo=False, future=True)
    try:
        async with engine.begin() as conn:
            for stmt in DEMO_TABLES_SQL.strip().split(";"):
                sql = stmt.strip()
                if sql:
                    await conn.execute(text(sql))

        async with engine.begin() as conn:
            existing = (await conn.execute(text("SELECT COUNT(*) FROM categories"))).scalar() or 0
            if existing and not force:
                return {"created": False, "rows": int(existing)}

            # 类别 10 个
            from datetime import datetime, timedelta

            now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
            for i, name in enumerate(_PRODUCT_LINE_NAMES, start=1):
                await conn.execute(
                    text("INSERT INTO categories (id, name, created_at) VALUES (:id, :name, :ts)"),
                    {"id": i, "name": name, "ts": (now - timedelta(days=180)).isoformat()},
                )

            # 商品 50 个（每类别 5 个）
            product_id = 1
            products: list[dict] = []
            for cat_id in range(1, 11):
                for j in range(5):
                    pname = f"{_PRODUCT_LINE_NAMES[cat_id - 1]}商品{cat_id}-{j + 1}"
                    price = round(20 + (cat_id * 7 + j * 11) % 480 + 0.99, 2)
                    stock = 100 + (cat_id * 13 + j * 7) % 900
                    products.append({
                        "id": product_id,
                        "name": pname,
                        "category_id": cat_id,
                        "price": price,
                        "stock": stock,
                        "created_at": (now - timedelta(days=150 - j)).isoformat(),
                    })
                    product_id += 1
            for p in products:
                await conn.execute(
                    text("INSERT INTO products (id, name, category_id, price, stock, created_at) VALUES (:id, :name, :category_id, :price, :stock, :created_at)"),
                    p,
                )

            # 客户 8 个（2 个租户各 4 个）
            for i, name in enumerate(_CUSTOMER_NAMES, start=1):
                tenant_id = 1 if i % 2 == 0 else 2
                await conn.execute(
                    text("INSERT INTO customers (id, name, tenant_id, created_at) VALUES (:id, :name, :tenant_id, :created_at)"),
                    {
                        "id": i,
                        "name": name,
                        "tenant_id": tenant_id,
                        "created_at": (now - timedelta(days=200)).isoformat(),
                    },
                )

            # 订单 5000 条（最近 60 天内随机）
            import random

            random.seed(42)
            statuses = ["paid", "paid", "paid", "paid", "cancelled", "refunded"]
            order_id = 1
            item_id = 1
            for _ in range(5000):
                customer_id = random.randint(1, len(_CUSTOMER_NAMES))
                tenant_id = 1 if customer_id % 2 == 0 else 2
                status = random.choice(statuses)
                days_ago = random.randint(0, 60)
                order_date = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat()
                # 订单 1-3 个商品
                items = random.sample(products, k=random.randint(1, 3))
                order_amount = sum(it["price"] * random.randint(1, 3) for it in items)
                await conn.execute(
                    text("INSERT INTO orders (id, customer_id, tenant_id, status, amount, created_at) VALUES (:id, :customer_id, :tenant_id, :status, :amount, :created_at)"),
                    {
                        "id": order_id,
                        "customer_id": customer_id,
                        "tenant_id": tenant_id,
                        "status": status,
                        "amount": order_amount,
                        "created_at": order_date,
                    },
                )
                for it in items:
                    qty = random.randint(1, 3)
                    await conn.execute(
                        text("INSERT INTO order_items (id, order_id, product_id, quantity, price) VALUES (:id, :order_id, :product_id, :quantity, :price)"),
                        {
                            "id": item_id,
                            "order_id": order_id,
                            "product_id": it["id"],
                            "quantity": qty,
                            "price": it["price"] * qty,
                        },
                    )
                    item_id += 1
                order_id += 1
        return {
            "created": True,
            "rows": {
                "categories": len(_PRODUCT_LINE_NAMES),
                "products": len(products),
                "customers": len(_CUSTOMER_NAMES),
                "orders": 5000,
            },
        }
    finally:
        await engine.dispose()


async def ensure_demo_data() -> dict:
    """确保默认 demo 数据源 + demo SQLite 库就绪。

    1. 找到 ``default`` 租户
    2. 找到 / 创建 ``默认演示数据源`` 指向 ``bi_demo.db``
    3. 写表 + 灌数据
    4. 触发一次元数据同步
    """
    tenant, _ = await _safe_update_or_create(
        Tenant,
        {"code": "default"},
        {"name": "默认租户", "is_active": True},
    )

    # 取/建数据源
    ds = await Datasource.filter(name="默认演示数据源").first()
    if ds is None:
        ds = await create_datasource(
            user_id=0,
            tenant=tenant,
            name="默认演示数据源",
            type=DatasourceType.sqlite.value,
            database="bi_demo.db",
            username=None,
            password=None,
            host=None,
            port=None,
            is_default=True,
            remark="Phase 1 演示用电商 demo 库",
        )
    else:
        # 强制对齐到默认租户（避免早期数据被分到不存在的租户）
        if ds.tenant_id != tenant.id:
            ds.tenant_id = tenant.id
            await ds.save(update_fields=["tenant_id"])

    # 生成数据
    db_path = ds.database or "bi_demo.db"
    generated = await _generate_demo_data(db_path)

    # 同步元数据
    from app.business.bi.metadata.sync import sync_datasource

    sync_result = await sync_datasource(ds)

    return {
        "datasourceId": ds.id,
        "datasourceName": ds.name,
        "generated": generated,
        "synced": {"tables": sync_result.tables, "columns": sync_result.columns, "errors": sync_result.errors},
    }


__all__ = [
    "list_tables",
    "get_datasource_by_id",
    "get_table_detail",
    "ensure_demo_data",
    "DEMO_TABLES_SQL",
]
