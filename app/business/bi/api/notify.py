"""BiNotifyRecord API 路由 — 订阅推送消息（只读 + 标记已读）。

按钮码：
- ``B_BI_NOTIFY_VIEW`` —— 查看（list / unread_count / mark_read）

接口列表：
- ``POST /notify/search`` —— 分页查询当前用户的消息（按 created_at 倒序）
- ``GET /notify/unread-count`` —— 获取当前用户未读消息数（铃铛组件轮询）
- ``PUT /notify/{record_id}/read`` —— 标记指定消息为已读

行级隔离：所有查询带 ``user_id=current_user_id``，用户只能查看/操作自己的消息。

项目历史教训：
- ``/notify/search`` 和 ``/notify/unread-count`` 必须声明在
  ``/notify/{record_id}/read`` 之前，避免 ``search`` / ``unread-count``
  被当作 sqid 路径参数解析。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.models import BiNotifyRecord
from app.business.bi.schemas import BiNotifyRecordSearch
from app.core.exceptions import BizError
from app.utils import (
    Code,
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    encode_id,
    get_current_user_id,
    require_buttons,
)

router = APIRouter(prefix="/notify", tags=["BI订阅消息"])


def _record_brief(r: BiNotifyRecord) -> dict:
    """消息记录序列化（铃铛与列表页共用）。"""
    return {
        "id": encode_id(r.id),
        "subscriptionId": encode_id(r.subscription_id),
        "title": r.title,
        "content": r.content,
        "status": r.status,
        "isRead": r.is_read,
        "createdAt": int(r.created_at.timestamp() * 1000) if r.created_at else None,
        "fmtCreatedAt": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
    }


@router.post(
    "/search",
    summary="消息记录分页搜索",
    name="bi.notify.list",
    dependencies=[DependAuth, require_buttons("B_BI_NOTIFY_VIEW")],
)
async def list_notify_records(obj_in: BiNotifyRecordSearch):
    """分页查询当前用户的消息（按 id 倒序）。"""
    user_id = get_current_user_id()
    qs = BiNotifyRecord.filter(user_id=user_id)
    if obj_in.status:
        qs = qs.filter(status=obj_in.status)
    if obj_in.is_read is not None:
        qs = qs.filter(is_read=obj_in.is_read)

    total = await qs.count()
    records = await qs.order_by("-id").offset((obj_in.current - 1) * obj_in.size).limit(obj_in.size)
    return SuccessExtra(
        data={"records": [_record_brief(r) for r in records]},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.get(
    "/unread-count",
    summary="获取未读消息数",
    name="bi.notify.unread_count",
    dependencies=[DependAuth, require_buttons("B_BI_NOTIFY_VIEW")],
)
async def get_unread_count():
    """获取当前用户未读消息数（铃铛组件轮询）。"""
    user_id = get_current_user_id()
    count = await BiNotifyRecord.filter(user_id=user_id, is_read=False).count()
    return Success(data={"count": count})


@router.put(
    "/{record_id}/read",
    summary="标记消息已读",
    name="bi.notify.mark_read",
    dependencies=[DependAuth, require_buttons("B_BI_NOTIFY_VIEW")],
)
async def mark_read(record_id: SqidPath):
    """标记指定消息为已读（仅能操作自己的消息）。"""
    user_id = get_current_user_id()
    record = await BiNotifyRecord.get_or_none(id=record_id, user_id=user_id)
    if not record:
        raise BizError(Code.BI_NOTIFY_RECORD_NOT_FOUND, "消息记录不存在")
    if not record.is_read:
        record.is_read = True
        await record.save(update_fields=["is_read"])
    return Success(msg="已标记已读", data={"recordId": record_id, "record_id": record_id})
