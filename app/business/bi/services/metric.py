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
    rows = await Metric.filter(
        datasource_id=datasource_id, status_type=StatusType.enable,
    ).order_by("id").values("id", "name", "description", "sql_template")
    return list(rows)


__all__ = [
    "list_metrics", "get_metric", "create_metric",
    "update_metric", "delete_metric", "list_for_intent",
]
