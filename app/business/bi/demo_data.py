"""AgenticBI 演示数据生成器 — 电商 schema。

生成 5 张表 + 1 张视图，足够覆盖 Phase 1 演示场景：
- categories（产品线 / 分类）
- products（商品）
- customers（客户，含 phone / email 用于脱敏演示）
- orders（订单，含 tenant_id 字段）
- order_items（订单明细，可选）

设计原则：
- 函数式 — 接 db_path，零隐式全局状态
- 幂等 — drop_first=True 时重建（默认）；False 时只补缺失
- 可复用 — e2e_smoke / scripts/dev.py / ``just bi-demo`` 都从这里调
- 仅依赖 SQLAlchemy 异步 + sqlite，无需启动 Tortoise / 业务模型
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Schema DDL（全部 IF NOT EXISTS，方便 drop_first=False 场景）
# ---------------------------------------------------------------------------

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        tenant_id INTEGER NOT NULL,
        phone TEXT,
        email TEXT,
        id_card TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        tenant_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        amount REAL NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL
    )
    """,
    # 视图：各部门销售额（脱敏列必须在 SELECT 列表里手动调用，本视图不脱敏）
    """
    CREATE VIEW IF NOT EXISTS v_product_line_sales AS
    SELECT
        c.id   AS category_id,
        c.name AS product_line,
        SUM(o.amount) AS total_amount,
        COUNT(o.id)   AS order_count
    FROM orders o
    JOIN products p ON p.id IN (SELECT product_id FROM order_items WHERE order_id = o.id)
    JOIN categories c ON c.id = p.category_id
    WHERE o.status = 'paid'
    GROUP BY c.id, c.name
    """,
]

# 业务数据词典 — 与 SPEC §7.1 演示场景一致
CATEGORIES: list[tuple[int, str]] = [
    (1, "手机数码"),
    (2, "电脑办公"),
    (3, "家用电器"),
    (4, "服饰鞋帽"),
    (5, "美妆个护"),
]

PRODUCTS: list[tuple[int, str, int, float, int]] = [
    # id, name, category_id, price, stock
    (1, "iPhone 15 Pro", 1, 8999, 100),
    (2, "Mate 60 Pro", 1, 6999, 80),
    (3, "小米 14 Ultra", 1, 5999, 120),
    (4, "MacBook Pro 14", 2, 14999, 50),
    (5, "ThinkPad X1", 2, 12999, 60),
    (6, "戴尔 XPS 15", 2, 11999, 40),
    (7, "海尔空调", 3, 3299, 200),
    (8, "美的冰箱", 3, 4999, 100),
    (9, "格力洗衣机", 3, 3999, 150),
    (10, "Nike 跑鞋", 4, 899, 300),
    (11, "Adidas T 恤", 4, 299, 500),
    (12, "优衣库外套", 4, 599, 400),
    (13, "兰蔻小黑瓶", 5, 1280, 200),
    (14, "雅诗兰黛小棕瓶", 5, 1080, 180),
    (15, "SK-II 神仙水", 5, 1690, 150),
]

# 客户（name, phone, email, id_card 前缀 → 自动补全数字）
CUSTOMER_PRESETS: list[tuple[str, str, str, str]] = [
    ("张三", "13800000001", "zhangsan@example.com", "1101011990"),
    ("李四", "13800000002", "lisi@example.com", "1101011991"),
    ("王五", "13800000003", "wangwu@example.com", "1101011992"),
    ("赵六", "13800000004", "zhaoliu@example.com", "1101011993"),
    ("钱七", "13800000005", "qianqi@example.com", "1101011994"),
    ("孙八", "13800000006", "sunba@example.com", "1101011995"),
    ("周九", "13800000007", "zhoujiu@example.com", "1101011996"),
    ("吴十", "13800000008", "wushi@example.com", "1101011997"),
]


@dataclass(slots=True)
class DemoSummary:
    """生成结果摘要。"""

    db_path: str
    tenant_id: int
    categories: int = 0
    products: int = 0
    customers: int = 0
    orders: int = 0
    order_items: int = 0
    dropped_tables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": self.db_path,
            "tenant_id": self.tenant_id,
            "categories": self.categories,
            "products": self.products,
            "customers": self.customers,
            "orders": self.orders,
            "order_items": self.order_items,
            "dropped_tables": list(self.dropped_tables),
        }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat(sep=" ")


def _date_offset(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).replace(microsecond=0).isoformat(sep=" ")


def _build_url(db_path: str) -> str:
    """构造异步 SQLite URL。"""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{p}"


def _random_phone(rng: random.Random, base: str = "139") -> str:
    return base + "".join(rng.choices("0123456789", k=8))


def _random_id_card(rng: random.Random) -> str:
    region = "110101"
    year = rng.randint(1985, 2000)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    seq = rng.randint(100, 999)
    return f"{region}{year:04d}{month:02d}{day:02d}{seq}"


async def seed_demo_db(
    db_path: str,
    *,
    tenant_id: int = 1,
    order_count: int = 80,
    seed: int = 42,
    drop_first: bool = True,
    extra_tenants: int = 0,
) -> DemoSummary:
    """在指定 SQLite 文件里灌入电商演示数据。

    Args:
        db_path: SQLite 文件路径（不存在会自动创建）。
        tenant_id: 主租户 id（默认 1，与 init_data 的默认租户一致）。
        order_count: 本租户下的订单数量（决定 SQL "本月" 范围的数据体量）。
        seed: 随机种子，保证可复现。
        drop_first: True 时先 DROP 全部表再重建（适合演示 / CI）；
                    False 时保留已有数据（适合增量补数据）。
        extra_tenants: 额外生成 N 个租户的零散客户 + 订单（用于演示行级隔离），
                       每个额外租户 = 5 客户 + 5 订单。

    Returns:
        ``DemoSummary`` 摘要。
    """
    rng = random.Random(seed)
    url = _build_url(db_path)
    summary = DemoSummary(db_path=db_path, tenant_id=tenant_id)
    engine = create_async_engine(url, echo=False, future=True)
    try:
        async with engine.begin() as conn:
            if drop_first:
                # DROP 顺序：依赖 → 被依赖
                drop_order = [
                    "v_product_line_sales",
                    "order_items",
                    "orders",
                    "customers",
                    "products",
                    "categories",
                ]
                for tbl in drop_order:
                    await conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
                    if not tbl.startswith("v_"):
                        summary.dropped_tables.append(tbl)

            for ddl in _DDL:
                await conn.execute(text(ddl))

            # 1. categories
            await conn.execute(text("INSERT INTO categories (id, name, created_at) VALUES " + ",".join(f"({cid}, '{name}', '{_date_offset(180)}')" for cid, name in CATEGORIES)))
            summary.categories = len(CATEGORIES)

            # 2. products
            await conn.execute(
                text(
                    "INSERT INTO products (id, name, category_id, price, stock, created_at) VALUES "
                    + ",".join(f"({pid}, '{name}', {cat}, {price}, {stock}, '{_date_offset(150)}')" for pid, name, cat, price, stock in PRODUCTS)
                )
            )
            summary.products = len(PRODUCTS)

            # 3. customers
            all_tenants = [tenant_id] + [tenant_id + i + 1 for i in range(extra_tenants)]
            customers: list[tuple[int, int, str, str, str, str, str]] = []  # id, tid, name, phone, email, id_card, created_at
            cid = 1
            for tid in all_tenants:
                for name, phone_prefix, email_prefix, _id_prefix in CUSTOMER_PRESETS:
                    phone = phone_prefix if tid == tenant_id else _random_phone(rng)
                    email = email_prefix if tid == tenant_id else f"user{cid}@example.com"
                    id_card = _random_id_card(rng) if tid != tenant_id else _id_prefix + "0001"
                    customers.append((cid, tid, name, phone, email, id_card, _date_offset(120)))
                    cid += 1
            await conn.execute(
                text(
                    "INSERT INTO customers (id, tenant_id, name, phone, email, id_card, created_at) VALUES "
                    + ",".join(f"({c[0]}, {c[1]}, '{c[2]}', '{c[3]}', '{c[4]}', '{c[5]}', '{c[6]}')" for c in customers)
                )
            )
            summary.customers = len(customers)

            # 4. orders + order_items
            statuses = ["paid", "paid", "paid", "paid", "pending", "refunded"]  # 4/6 paid
            # 集中在最近 30 天，"本月各产品线" 问题应当能 GROUP BY 出多条结果
            order_rows: list[tuple[int, int, int, str, float, str]] = []
            item_rows: list[tuple[int, int, int, int, float]] = []
            item_id = 1
            oid = 1
            tenant_customers: dict[int, list[int]] = {}
            for c in customers:
                tenant_customers.setdefault(c[1], []).append(c[0])

            for _ in range(order_count):
                tid = tenant_id
                customer_pool = tenant_customers.get(tid) or [1]
                cust = rng.choice(customer_pool)
                # 选 1-3 个商品
                picked = rng.sample(PRODUCTS, k=rng.randint(1, 3))
                total = sum(price for _id, _n, _c, price, _s in picked)
                days_ago = rng.randint(0, 29)  # 0~29 天前 = 本月
                created_at = _date_offset(days_ago)
                status = rng.choice(statuses)
                order_rows.append((oid, cust, tid, status, total, created_at))
                for pid, _name, _cat, price, _stock in picked:
                    qty = rng.randint(1, 2)
                    item_rows.append((item_id, oid, pid, qty, price))
                    item_id += 1
                oid += 1

            # 额外租户的零散订单（演示行级隔离）
            for tid in all_tenants[1:]:
                for _ in range(5):
                    customer_pool = tenant_customers.get(tid) or [1]
                    cust = rng.choice(customer_pool)
                    picked = rng.sample(PRODUCTS, k=1)
                    total = picked[0][3]
                    days_ago = rng.randint(0, 29)
                    order_rows.append((oid, cust, tid, "paid", total, _date_offset(days_ago)))
                    for pid, _n, _c, price, _s in picked:
                        item_rows.append((item_id, oid, pid, 1, price))
                        item_id += 1
                    oid += 1

            # 批量 insert
            await conn.execute(
                text("INSERT INTO orders (id, customer_id, tenant_id, status, amount, created_at) VALUES " + ",".join(f"({o[0]}, {o[1]}, {o[2]}, '{o[3]}', {o[4]}, '{o[5]}')" for o in order_rows))
            )
            summary.orders = len(order_rows)
            await conn.execute(text("INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES " + ",".join(f"({i[0]}, {i[1]}, {i[2]}, {i[3]}, {i[4]})" for i in item_rows)))
            summary.order_items = len(item_rows)
    finally:
        await engine.dispose()
    return summary


async def drop_demo_db(db_path: str) -> None:
    """删除 demo.db 的全部业务表（保留文件本身）。"""
    url = _build_url(db_path)
    engine = create_async_engine(url, echo=False, future=True)
    try:
        async with engine.begin() as conn:
            for tbl in ("v_product_line_sales", "order_items", "orders", "customers", "products", "categories"):
                await conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Schema 描述（给 LLM prompt 用）
# ---------------------------------------------------------------------------

SCHEMA_DESCRIPTION = """\
可用数据源 schema（sqlite）：

categories(id, name, created_at)  -- 产品线 / 分类
products(id, name, category_id, price, stock, created_at)  -- 商品
customers(id, name, tenant_id, phone, email, id_card, created_at)  -- 客户（注意 phone/email/id_card 会被自动脱敏）
orders(id, customer_id, tenant_id, status, amount, created_at)  -- 订单（status 取值 'paid' | 'pending' | 'refunded'）
order_items(id, order_id, product_id, quantity, unit_price)  -- 订单明细
v_product_line_sales(category_id, product_line, total_amount, order_count)  -- 部门销售汇总视图
"""


__all__ = [
    "CATEGORIES",
    "PRODUCTS",
    "CUSTOMER_PRESETS",
    "DemoSummary",
    "SCHEMA_DESCRIPTION",
    "seed_demo_db",
    "drop_demo_db",
]
