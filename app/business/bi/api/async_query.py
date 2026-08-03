"""BI 异步大查询路由 — submit / list / get / cancel / delete / result / download。

按钮码（spec §10.1）：
- ``B_BI_SQL_ASYNC_RUN`` —— 提交异步查询
- ``B_BI_SQL_TASK_VIEW`` —— 查看任务（list / get / result）
- ``B_BI_SQL_TASK_CANCEL`` —— 取消任务
- ``B_BI_SQL_TASK_DELETE`` —— 删除任务
- ``B_BI_SQL_TASK_DOWNLOAD`` —— 下载结果

接口列表：
- ``POST /sql/async-run`` —— 提交异步查询任务
- ``POST /sql/tasks/search`` —— 分页查询当前用户的任务
- ``GET /sql/tasks/{task_id}`` —— 查任务详情（含 sqlText + 实时进度，前端轮询用）
- ``GET /sql/tasks/{task_id}/result`` —— 获取结果预览（resultSnapshot）
- ``POST /sql/tasks/{task_id}/cancel`` —— 取消任务
- ``DELETE /sql/tasks/{task_id}`` —— 删除任务（软删 DB + 物理删 CSV + 清 Redis）
- ``GET /sql/tasks/{task_id}/download`` —— 流式下载 CSV

行级隔离：BiQueryTask.tenant_id 存 user.id，用户只能操作自己的任务。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.schemas import BiAsyncRunSchema, BiQueryTaskSearchSchema
from app.business.bi.services_async_query import (
    cancel_task,
    delete_task,
    get_download_stream,
    get_task,
    list_tasks,
    submit,
)
from app.core.redis import AioRedis
from app.utils import (
    BizError,
    Code,
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    encode_id,
    get_current_user_id,
    require_buttons,
)

router = APIRouter()


@router.post(
    "/sql/async-run",
    summary="提交异步查询",
    name="bi.tasks.run",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_ASYNC_RUN")],
)
async def submit_async_query_endpoint(obj_in: BiAsyncRunSchema, redis: AioRedis):
    """手动提交异步查询任务。"""
    user_id = get_current_user_id()
    task = await submit(obj_in, user_id=user_id, redis=redis, source="manual")
    return Success(
        msg="任务已提交",
        data={"taskId": encode_id(task.id), "status": "pending"},
    )


@router.post(
    "/sql/tasks/search",
    summary="查询任务列表",
    name="bi.tasks.list",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_VIEW")],
)
async def list_tasks_endpoint(obj_in: BiQueryTaskSearchSchema, redis: AioRedis):
    """分页查询当前用户的任务。"""
    user_id = get_current_user_id()
    total, records = await list_tasks(obj_in, user_id=user_id, redis=redis)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@router.get(
    "/sql/tasks/{task_id}",
    summary="查任务状态/详情（轮询用）",
    name="bi.tasks.get",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_VIEW")],
)
async def get_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """查任务详情（含 sqlText + 实时进度）。前端轮询用，2s 间隔。"""
    user_id = get_current_user_id()
    record = await get_task(task_id, user_id=user_id, redis=redis)
    return Success(data=record)


@router.get(
    "/sql/tasks/{task_id}/result",
    summary="获取结果预览",
    name="bi.tasks.result",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_VIEW")],
)
async def get_task_result_endpoint(task_id: SqidPath, redis: AioRedis):
    """获取任务结果预览（resultSnapshot）。"""
    user_id = get_current_user_id()
    record = await get_task(task_id, user_id=user_id, redis=redis)
    if record["status"] != "success":
        raise BizError(Code.BI_ASYNC_QUERY_RESULT_FILE_MISSING, "任务未完成")
    return Success(
        data={
            "resultSnapshot": record["resultSnapshot"],
            "resultRowCount": record["resultRowCount"],
            "resultIsTruncated": record["resultIsTruncated"],
        }
    )


@router.post(
    "/sql/tasks/{task_id}/cancel",
    summary="取消任务",
    name="bi.tasks.cancel",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_CANCEL")],
)
async def cancel_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """取消任务。pending 立即置 cancelled；running 设标志位等 worker 检测。"""
    user_id = get_current_user_id()
    await cancel_task(task_id, user_id=user_id, redis=redis)
    return Success(msg="取消请求已提交")


@router.delete(
    "/sql/tasks/{task_id}",
    summary="删除任务",
    name="bi.tasks.delete",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_DELETE")],
)
async def delete_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """删除任务（软删 DB + 物理删 CSV + 清 Redis）。"""
    user_id = get_current_user_id()
    await delete_task(task_id, user_id=user_id, redis=redis)
    return Success(msg="删除成功")


@router.get(
    "/sql/tasks/{task_id}/download",
    summary="下载结果 CSV",
    name="bi.tasks.download",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_DOWNLOAD")],
)
async def download_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """流式下载 CSV（支持 Range 断点续传）。"""
    user_id = get_current_user_id()
    return await get_download_stream(task_id, user_id=user_id, redis=redis)
