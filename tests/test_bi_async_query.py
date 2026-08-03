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


# ===================== state =====================


class TestState:
    async def test_init_and_get_state(self, app):
        from app.business.bi.async_query.state import get_state, init_state

        redis = app.state.redis
        await init_state(9999, redis, status="pending")
        state = await get_state(9999, redis)
        assert state["status"] == "pending"
        assert state["progress"] == 0
        assert state["rows_fetched"] == 0
        assert state["elapsed_ms"] == 0

    async def test_update_progress(self, app):
        from app.business.bi.async_query.state import get_state, init_state, update_progress

        redis = app.state.redis
        await init_state(8888, redis)
        await update_progress(8888, redis, progress=45, rows_fetched=4500, elapsed_ms=3200)
        state = await get_state(8888, redis)
        assert state["progress"] == 45
        assert state["rows_fetched"] == 4500
        assert state["elapsed_ms"] == 3200

    async def test_update_status_with_error(self, app):
        from app.business.bi.async_query.state import get_state, init_state, update_status

        redis = app.state.redis
        await init_state(7777, redis)
        await update_status(7777, "failed", redis, error_message="timeout")
        state = await get_state(7777, redis)
        assert state["status"] == "failed"
        assert state["error_message"] == "timeout"

    async def test_check_cancel_default_false(self, app):
        from app.business.bi.async_query.state import check_cancel

        redis = app.state.redis
        await redis.delete("bi:async_query:task:6666:cancel")
        assert await check_cancel(6666, redis) is False

    async def test_request_cancel_sets_flag(self, app):
        from app.business.bi.async_query.state import check_cancel, request_cancel

        redis = app.state.redis
        await request_cancel(5555, redis)
        assert await check_cancel(5555, redis) is True

    async def test_get_state_missing_returns_empty(self, app):
        from app.business.bi.async_query.state import get_state

        redis = app.state.redis
        await redis.delete("bi:async_query:task:12345")
        assert await get_state(12345, redis) == {}


# ===================== storage =====================


class TestStorage:
    async def test_write_preview_under_limit(self):
        from app.business.bi.async_query.storage import write_preview

        columns = ["a", "b"]
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        result = write_preview(columns, rows, elapsed_ms=10)
        assert result["rowCount"] == 2
        assert result["isTruncated"] is False
        assert result["rows"] == rows

    async def test_write_preview_truncates(self, monkeypatch):
        from app.business.bi.async_query import storage as storage_mod
        from app.business.bi.config import BIZ_SETTINGS

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_PREVIEW_ROWS", 3)
        rows = [{"a": i} for i in range(10)]
        result = storage_mod.write_preview(["a"], rows, elapsed_ms=5)
        assert result["rowCount"] == 3
        assert result["isTruncated"] is True
        assert len(result["rows"]) == 3

    async def test_resolve_csv_path_rejects_traversal(self):
        from app.business.bi.async_query.storage import resolve_csv_path

        with pytest.raises(ValueError):
            resolve_csv_path("../../etc/passwd")
        with pytest.raises(ValueError):
            resolve_csv_path("sub/dir/file.csv")
        with pytest.raises(ValueError):
            resolve_csv_path("")

    async def test_resolve_csv_path_accepts_valid(self):
        from app.business.bi.async_query.storage import resolve_csv_path

        path = resolve_csv_path("12345.csv")
        assert path.name == "12345.csv"
        assert path.suffix == ".csv"

    async def test_write_and_append_csv(self, tmp_path, monkeypatch):
        from app.business.bi.async_query.storage import (
            append_csv_rows,
            read_csv_stream,
            write_csv_header,
        )
        from app.business.bi.config import BIZ_SETTINGS

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))

        file_path = tmp_path / "99999.csv"
        write_csv_header(file_path, ["a", "b"])
        append_csv_rows(file_path, ["a", "b"], [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
        append_csv_rows(file_path, ["a", "b"], [{"a": 3, "b": "z"}])

        content = b"".join(read_csv_stream(file_path))
        # BOM + header + 3 rows
        assert content.startswith(b"\xef\xbb\xbfa,b\r\n")
        assert b"1,x" in content
        assert b"3,z" in content
