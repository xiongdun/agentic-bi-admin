"""AgenticBI Metric 业务服务层。"""

from __future__ import annotations

from app.business.bi.models.semantic import Metric
from app.core.base_model import StatusType


async def list_metrics(
    *,
    datasource_id: int | None = None,
    name: str | None = None,
    status_type: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[int, list[Metric]]:
    qs = Metric.all()
    if datasource_id is not None:
        qs = qs.filter(datasource_id=datasource_id)
    if name:
        qs = qs.filter(name__icontains=name)
    if status_type:
        qs = qs.filter(status_type=status_type)
    total = await qs.count()
    rows = await qs.order_by("-id").offset((page - 1) * size).limit(size)
    return total, list(rows)


async def get_metric(metric_id: int) -> Metric | None:
    return await Metric.get_or_none(id=metric_id)


async def create_metric(
    *,
    name: str,
    display_name: str,
    sql_template: str,
    datasource_id: int,
    owner_id: int,
    description: str | None = None,
    unit: str | None = None,
) -> Metric:
    return await Metric.create(
        name=name,
        display_name=display_name,
        sql_template=sql_template,
        datasource_id=datasource_id,
        owner_id=owner_id,
        description=description,
        unit=unit,
        status_type=StatusType.enable,
    )


async def update_metric(metric_id: int, **fields) -> Metric:
    m = await Metric.get(id=metric_id)
    for k, v in fields.items():
        if v is not None and hasattr(m, k):
            setattr(m, k, v)
    await m.save()
    return m


async def delete_metric(metric_id: int) -> None:
    await Metric.filter(id=metric_id).delete()


async def list_for_intent(datasource_id: int) -> list[dict]:
    """供 LLM intent router 用的精简列表。"""
    rows = (
        await Metric
        .filter(
            datasource_id=datasource_id,
            status_type=StatusType.enable,
        )
        .order_by("id")
        .values("id", "name", "description", "sql_template")
    )
    return list(rows)


async def validate_template(metric_id: int) -> dict:  # noqa: ANN201
    """校验 sql_template 的语法合法性 + 占位符检查 + 白名单。

    模板本质是 SQL 片段,只验证它能否被 sqlglot 解析 + 通过沙箱白名单,不直接执行。

    原名 ``test_metric_template`` 会触发 pytest 自动收集(全模块扫 ``test_`` 前缀),
    故改名为 ``validate_template``。
    """
    import re

    from app.business.bi.sandbox.whitelist import validate_tree
    from app.business.bi.services.datasource import get_datasource
    from app.utils import safe_parse

    m = await get_metric(metric_id)
    if m is None:
        return {"success": False, "error": "metric not found"}
    ds = await get_datasource(m.datasource_id)
    if ds is None:
        return {"success": False, "error": "datasource not found"}

    placeholders = re.findall(r"\{(\w+)\}", m.sql_template)
    if not placeholders:
        return {
            "success": False,
            "error": "模板缺少占位符(如 {order}),无法被 sql_gen 替换",
        }

    # 1) 用 t<index> 替换所有占位符,得到纯 SQL 片段
    placeholder_to_alias: dict[str, str] = {}
    for i, name in enumerate(dict.fromkeys(placeholders)):
        placeholder_to_alias[name] = f"t{i}"
    substituted = re.sub(
        r"\{(\w+)\}",
        lambda m: placeholder_to_alias[m.group(1)],
        m.sql_template,
    )

    # 2) 拼成完整 SELECT:把 FROM 注入到 WHERE / GROUP BY / ORDER BY / LIMIT / HAVING 之前
    #    这些子句在裸 SELECT 里必须有前置 FROM,不能直接放在 SELECT-list 后面
    inject_token = " FROM " + " ".join(f"{a} AS {a}" for a in placeholder_to_alias.values())
    upper = substituted.upper()
    cut_markers = (" WHERE ", " GROUP BY ", " ORDER BY ", " HAVING ", " LIMIT ", " UNION ", " INTERSECT ", " EXCEPT ")
    cut_at = -1
    for marker in cut_markers:
        idx = upper.find(marker)
        if idx != -1 and (cut_at == -1 or idx < cut_at):
            cut_at = idx
    if cut_at == -1:
        test_sql = f"SELECT {substituted}{inject_token}"
    else:
        test_sql = f"SELECT {substituted[:cut_at]}{inject_token}{substituted[cut_at:]}"

    tree = safe_parse(test_sql, dialect=ds.type.value)
    if tree is None:
        return {
            "success": False,
            "error": f"sqlglot 解析失败,请检查模板语法({ds.type.value})",
        }
    ok, reason = validate_tree(tree, dialect=ds.type.value)
    if not ok:
        return {"success": False, "error": f"whitelist_denied: {reason}"}

    return {
        "success": True,
        "placeholders": list(dict.fromkeys(placeholders)),
        "datasource": ds.name,
        "dialect": ds.type.value,
    }


__all__ = [
    "list_metrics",
    "get_metric",
    "create_metric",
    "update_metric",
    "delete_metric",
    "list_for_intent",
    "validate_template",
]
