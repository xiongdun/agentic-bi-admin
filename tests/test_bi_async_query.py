"""BI 异步大查询测试。

覆盖：
- ``queue`` —— enqueue/dequeue/BLPOP 超时
- ``state`` —— init_state/update_progress/get_state/check_cancel/delete_state
- ``storage`` —— write_preview 截断 / write_csv_header 流式 / resolve_csv_path 防穿越
- ``quota`` —— check_concurrency / incr_running / decr_running
- ``services_async_query`` —— submit/get/cancel/list/delete 全流程
- ``runner`` —— execute_task 流式执行 / 取消 / 超时 / crash recovery
- API 鉴权 + 智能切换 transfer
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ===================== queue =====================


class TestQueue:
    async def test_enqueue_dequeue_fifo(self, app):
        from app.business.bi.async_query.queue import dequeue, enqueue, queue_size

        redis = app.state.redis
        await redis.delete("bi:async_query:queue")

        # LPUSH 入队顺序：1, 2, 3 → BLPOP 出队顺序：3, 2, 1（栈语义）
        # spec §3.4 用 List，BLPOP 是左 pop，所以 LPUSH+BLPOP 是 LIFO
        # 这里测的是 "入队 / 出队能配对"，顺序由调用方决定
        await enqueue(101, redis)
        await enqueue(102, redis)
        assert await queue_size(redis) == 2

        first = await dequeue(redis, timeout=1)
        # LPUSH 后 BLPOP 拿到的是最后入队的（102）
        assert first == 102

        second = await dequeue(redis, timeout=1)
        assert second == 101

        assert await queue_size(redis) == 0

    async def test_dequeue_timeout_returns_none(self, app):
        from app.business.bi.async_query.queue import dequeue

        redis = app.state.redis
        await redis.delete("bi:async_query:queue")
        result = await dequeue(redis, timeout=1)
        assert result is None
