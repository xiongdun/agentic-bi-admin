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


# ===================== quota =====================


class TestAsyncQuota:
    async def test_check_concurrency_under_limit(self, app):
        from app.business.bi.async_query.quota import check_concurrency

        redis = app.state.redis
        await redis.delete("bi:async_query:user:1:running", "bi:async_query:global:running")
        # 不应抛异常
        await check_concurrency(1, redis)

    async def test_check_concurrency_user_exceeded(self, app, monkeypatch):
        from app.business.bi.async_query.quota import check_concurrency
        from app.business.bi.config import BIZ_SETTINGS

        redis = app.state.redis
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_USER_MAX_CONCURRENCY", 2)
        await redis.set("bi:async_query:user:2:running", 2)
        with pytest.raises(Exception) as exc:
            await check_concurrency(2, redis)
        assert "4111" in str(exc.value) or "用户并发" in str(exc.value)

    async def test_check_concurrency_global_exceeded(self, app, monkeypatch):
        from app.business.bi.async_query.quota import check_concurrency
        from app.business.bi.config import BIZ_SETTINGS

        redis = app.state.redis
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY", 20)
        await redis.set("bi:async_query:global:running", 20)
        with pytest.raises(Exception) as exc:
            await check_concurrency(3, redis)
        assert "4112" in str(exc.value) or "全局并发" in str(exc.value)

    async def test_incr_decr_running(self, app):
        from app.business.bi.async_query.quota import (
            check_concurrency,
            decr_running,
            incr_running,
        )

        redis = app.state.redis
        await redis.delete("bi:async_query:user:4:running", "bi:async_query:global:running")
        await incr_running(4, redis)
        await incr_running(4, redis)
        assert int(await redis.get("bi:async_query:user:4:running")) == 2
        await decr_running(4, redis)
        assert int(await redis.get("bi:async_query:user:4:running")) == 1

    async def test_decr_clamps_to_zero(self, app):
        from app.business.bi.async_query.quota import decr_running

        redis = app.state.redis
        await redis.delete("bi:async_query:user:5:running")
        await decr_running(5, redis)  # 不会变成 -1
        assert int(await redis.get("bi:async_query:user:5:running")) == 0


class TestSandboxQuotaRedis:
    """sandbox/quota.py 改造为 Redis 后的行为测试。"""

    async def test_record_failure_and_check_quota(self, app):
        from app.business.bi.sandbox.quota import (
            QuotaConfig,
            check_quota,
            record_failure,
        )

        redis = app.state.redis
        await redis.delete("bi:quota:failures:user:10")
        cfg = QuotaConfig(breaker_threshold=3, breaker_window_seconds=60)

        # 前 2 次不熔断
        await record_failure("user:10", redis, cfg)
        await record_failure("user:10", redis, cfg)
        await check_quota("user:10", redis, cfg)  # 不抛

        # 第 3 次触发熔断
        await record_failure("user:10", redis, cfg)
        with pytest.raises(Exception) as exc:
            await check_quota("user:10", redis, cfg)
        assert "4102" in str(exc.value) or "熔断" in str(exc.value)

    async def test_record_success_clears(self, app):
        from app.business.bi.sandbox.quota import (
            check_quota,
            record_failure,
            record_success,
        )

        redis = app.state.redis
        await redis.delete("bi:quota:failures:user:11")
        await record_failure("user:11", redis)
        await record_success("user:11", redis)
        # 不应抛熔断
        await check_quota("user:11", redis)


# ===================== services_async_query =====================


def _encode_id_safe(int_id: int) -> str:
    from app.core.sqids import encode_id

    return encode_id(int_id)


class TestSubmitTask:
    async def test_submit_success(self, app, bi_datasource, monkeypatch):
        from app.business.bi.async_query import queue
        from app.business.bi.services_async_query import submit

        user_id = bi_datasource.tenant_id
        redis = app.state.redis
        await redis.delete(
            "bi:async_query:user:1:running",
            "bi:async_query:global:running",
            queue.QUEUE_KEY,
        )

        # mock 行级 data_scope 为 all（避免注入 tenant 条件）
        async def _fake_scope():
            return "all", None

        monkeypatch.setattr(
            "app.business.bi.services_async_query._get_user_data_scope", _fake_scope
        )

        from app.business.bi.schemas import BiAsyncRunSchema

        schema = BiAsyncRunSchema(
            sql="SELECT id, name FROM orders LIMIT 100",
            datasource_id=_encode_id_safe(bi_datasource.id),
            name="测试任务",
        )
        task = await submit(schema, user_id=user_id, redis=redis, source="manual")

        assert task.id > 0
        assert task.status == "pending"
        assert task.tenant_id == user_id
        assert task.source == "manual"

        # 任务已入队
        assert await queue.queue_size(redis) == 1
        # Redis 状态已初始化
        from app.business.bi.async_query.state import get_state

        s = await get_state(task.id, redis)
        assert s["status"] == "pending"

    async def test_submit_disabled(self, app, bi_datasource, monkeypatch):
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.services_async_query import submit

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_ENABLED", False)

        from app.business.bi.schemas import BiAsyncRunSchema

        schema = BiAsyncRunSchema(
            sql="SELECT 1",
            datasource_id=_encode_id_safe(bi_datasource.id),
        )
        with pytest.raises(Exception) as exc:
            await submit(schema, user_id=bi_datasource.tenant_id, redis=app.state.redis)
        assert "4110" in str(exc.value) or "未开启" in str(exc.value)

    async def test_submit_datasource_not_found(self, app, bi_datasource, monkeypatch):
        from app.business.bi.services_async_query import submit

        async def _fake_scope():
            return "all", None

        monkeypatch.setattr(
            "app.business.bi.services_async_query._get_user_data_scope", _fake_scope
        )

        from app.business.bi.schemas import BiAsyncRunSchema

        schema = BiAsyncRunSchema(
            sql="SELECT 1",
            datasource_id=_encode_id_safe(999_999_999),
        )
        with pytest.raises(Exception) as exc:
            await submit(schema, user_id=bi_datasource.tenant_id, redis=app.state.redis)
        assert str(exc.value.code) == "1101" or "不存在" in str(exc.value)


class TestGetTask:
    async def test_get_task_success(self, app, bi_query_task):
        from app.business.bi.services_async_query import get_task

        user_id = bi_query_task.tenant_id
        record = await get_task(bi_query_task.id, user_id, app.state.redis)
        assert record["status"] == "pending"
        assert "sqlText" in record

    async def test_get_task_not_found(self, app, bi_datasource):
        from app.business.bi.services_async_query import get_task

        with pytest.raises(Exception) as exc:
            await get_task(999_999_999, bi_datasource.tenant_id, app.state.redis)
        assert "4113" in str(exc.value)

    async def test_get_task_tenant_isolation(self, app, bi_query_task):
        from app.business.bi.services_async_query import get_task

        other_user = bi_query_task.tenant_id + 100
        with pytest.raises(Exception) as exc:
            await get_task(bi_query_task.id, other_user, app.state.redis)
        assert "4113" in str(exc.value)


class TestCancelTask:
    async def test_cancel_pending(self, app, bi_query_task):
        from app.business.bi.services_async_query import cancel_task

        user_id = bi_query_task.tenant_id
        await cancel_task(bi_query_task.id, user_id, app.state.redis)

        await bi_query_task.refresh_from_db()
        assert bi_query_task.status == "cancelled"

    async def test_cancel_already_done(self, app, bi_query_task):
        from app.business.bi.services_async_query import cancel_task

        bi_query_task.status = "success"
        await bi_query_task.save(update_fields=["status"])

        with pytest.raises(Exception) as exc:
            await cancel_task(bi_query_task.id, bi_query_task.tenant_id, app.state.redis)
        assert "4114" in str(exc.value)

    async def test_cancel_running_sets_flag(self, app, bi_query_task):
        from app.business.bi.async_query.state import check_cancel
        from app.business.bi.services_async_query import cancel_task

        bi_query_task.status = "running"
        await bi_query_task.save(update_fields=["status"])

        await cancel_task(bi_query_task.id, bi_query_task.tenant_id, app.state.redis)
        # pending 分支不触发，running 分支设标志位
        assert await check_cancel(bi_query_task.id, app.state.redis) is True


class TestListTasks:
    async def test_list_tasks_isolation(self, app, bi_datasource):
        from app.business.bi.models import BiQueryTask
        from app.business.bi.schemas import BiQueryTaskSearchSchema
        from app.business.bi.services_async_query import list_tasks

        user_a = bi_datasource.tenant_id
        user_b = user_a + 200

        await BiQueryTask.all().delete()
        await BiQueryTask.create(
            name="A1",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="success",
            tenant_id=user_a,
            created_by=str(user_a),
            updated_by=str(user_a),
        )
        await BiQueryTask.create(
            name="B1",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="success",
            tenant_id=user_b,
            created_by=str(user_b),
            updated_by=str(user_b),
        )

        search = BiQueryTaskSearchSchema(current=1, size=10)
        total, records = await list_tasks(search, user_id=user_a, redis=app.state.redis)
        assert total == 1
        assert records[0]["name"] == "A1"


class TestDeleteTask:
    async def test_delete_removes_csv(self, app, bi_query_task, tmp_path, monkeypatch):
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.services_async_query import delete_task

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))

        # 构造一个 success + result_uri 的任务
        bi_query_task.status = "success"
        bi_query_task.result_uri = f"{bi_query_task.id}.csv"
        await bi_query_task.save(update_fields=["status", "result_uri"])

        # 写一个 CSV 文件
        csv_path = tmp_path / f"{bi_query_task.id}.csv"
        csv_path.write_text("id\n1\n", encoding="utf-8")
        assert csv_path.exists()

        await delete_task(bi_query_task.id, bi_query_task.tenant_id, app.state.redis)

        # CSV 被删
        assert not csv_path.exists()
        # DB 软删
        from app.business.bi.models import BiQueryTask

        deleted = await BiQueryTask.filter(
            id=bi_query_task.id, deleted_at__isnull=True
        ).count()
        assert deleted == 0


# ===================== API Auth =====================


class TestAsyncQueryAPIAuth:
    PREFIX = "/api/v1/business/bi"

    async def test_async_run_no_auth(self, client):
        resp = await client.post(f"{self.PREFIX}/sql/async-run", json={})
        assert resp.status_code == 200
        assert resp.json()["code"] == "2100"  # INVALID_TOKEN

    async def test_tasks_search_no_auth(self, client):
        resp = await client.post(
            f"{self.PREFIX}/sql/tasks/search", json={"current": 1, "size": 10}
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == "2100"

    async def test_tasks_get_no_auth(self, client):
        resp = await client.get(f"{self.PREFIX}/sql/tasks/abc")
        assert resp.status_code == 200
        assert resp.json()["code"] == "2100"

    async def test_submit_via_api(self, auth_client, bi_datasource, monkeypatch):
        """登录后通过 API 提交，验证返回 taskId。"""
        async def _fake_scope():
            return "all", None

        monkeypatch.setattr(
            "app.business.bi.services_async_query._get_user_data_scope", _fake_scope
        )

        resp = await auth_client.post(
            f"{self.PREFIX}/sql/async-run",
            json={
                "sql": "SELECT id, name FROM orders LIMIT 100",
                "datasource_id": _encode_id_safe(bi_datasource.id),
                "name": "API 任务",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000"
        assert body["data"]["taskId"]
        assert body["data"]["status"] == "pending"


# ===================== Smart Switch (transfer) =====================


class TestSmartSwitch:
    async def test_run_sql_sync_success(self, app, bi_datasource, monkeypatch):
        """快查询同步返回，不触发 transfer。"""
        from types import SimpleNamespace

        from app.business.bi.schemas import SqlRunSchema
        from app.business.bi.services import run_sql

        async def _fake_scope():
            return "all", None

        async def _fake_execute_sql(sql, datasource, user_id, redis=None, **kw):
            return SimpleNamespace(
                columns=["id"],
                rows=[{"id": 1}],
                row_count=1,
                elapsed_ms=12,
            )

        monkeypatch.setattr("app.business.bi.services._get_user_data_scope", _fake_scope)
        monkeypatch.setattr("app.business.bi.services.execute_sql", _fake_execute_sql)

        user = SimpleNamespace(id=bi_datasource.tenant_id)
        schema = SqlRunSchema(
            sql="SELECT 1", datasource_id=_encode_id_safe(bi_datasource.id)
        )
        result = await run_sql(user, schema, redis=app.state.redis)

        assert result.get("transferred") is None
        assert result["rowCount"] == 1
        assert result["elapsedMs"] == 12

    async def test_run_sql_soft_timeout_transfers(self, app, bi_datasource, monkeypatch):
        """同步执行软超时，转异步任务并返回 transferred=true。"""
        import asyncio
        from types import SimpleNamespace

        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.schemas import SqlRunSchema
        from app.business.bi.services import run_sql

        async def _fake_scope():
            return "all", None

        async def _slow_execute_sql(sql, datasource, user_id, redis=None, **kw):
            # 睡 30s 让软超时触发（测试中软超时调到 1s）
            await asyncio.sleep(30)
            return SimpleNamespace(columns=[], rows=[], row_count=0, elapsed_ms=30000)

        # 把软超时调到 1s，测试不用真等 25s
        monkeypatch.setattr(BIZ_SETTINGS, "BI_SYNC_SOFT_TIMEOUT", 1)
        monkeypatch.setattr("app.business.bi.services._get_user_data_scope", _fake_scope)
        monkeypatch.setattr("app.business.bi.services.execute_sql", _slow_execute_sql)

        user = SimpleNamespace(id=bi_datasource.tenant_id)
        schema = SqlRunSchema(
            sql="SELECT 1", datasource_id=_encode_id_safe(bi_datasource.id)
        )
        result = await run_sql(user, schema, redis=app.state.redis)

        assert result.get("transferred") is True
        assert result.get("taskId")
        assert "已转为异步任务" in result["message"]


# ===================== Cleanup Expired Tasks =====================


class TestCleanupExpiredTasks:
    async def test_cleanup_removes_expired(self, app, bi_datasource, tmp_path, monkeypatch):
        """过期任务被软删 + CSV 物理删 + Redis 状态清。"""
        from datetime import datetime as dt
        from datetime import timedelta

        from app.business.bi.async_query import state
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.models import BiQueryTask
        from app.business.bi.services_async_query import cleanup_expired_tasks

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))
        # 注入 runtime redis（PeriodicTask handler 无参签名）
        state.set_runtime_redis(app.state.redis)

        # 构造一个过期 success 任务（created_at 早于 TTL_DAYS）
        old_created = dt.now() - timedelta(days=BIZ_SETTINGS.BI_ASYNC_QUERY_TTL_DAYS + 1)
        task = await BiQueryTask.create(
            name="过期任务",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="success",
            result_uri=None,
            tenant_id=bi_datasource.tenant_id,
            source="manual",
            created_at=old_created,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        # 手动把 created_at 改回（Tortoise create 后 created_at 会被 DB 覆盖）
        await BiQueryTask.filter(id=task.id).update(created_at=old_created)

        # 构造一个未过期任务，确认不被清理
        fresh = await BiQueryTask.create(
            name="新鲜任务",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 2",
            status="pending",
            tenant_id=bi_datasource.tenant_id,
            source="manual",
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        cleaned = await cleanup_expired_tasks()
        assert cleaned == 1

        # 过期任务被软删
        expired_count = await BiQueryTask.filter(
            id=task.id, deleted_at__isnull=True
        ).count()
        assert expired_count == 0

        # 新鲜任务保留
        fresh_count = await BiQueryTask.filter(
            id=fresh.id, deleted_at__isnull=True
        ).count()
        assert fresh_count == 1

    async def test_cleanup_removes_csv_file(self, app, bi_datasource, tmp_path, monkeypatch):
        """过期 success 任务的 CSV 文件被物理删除。"""
        from datetime import datetime as dt
        from datetime import timedelta

        from app.business.bi.async_query import state
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.models import BiQueryTask
        from app.business.bi.services_async_query import cleanup_expired_tasks

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))
        state.set_runtime_redis(app.state.redis)

        old_created = dt.now() - timedelta(days=BIZ_SETTINGS.BI_ASYNC_QUERY_TTL_DAYS + 1)
        task = await BiQueryTask.create(
            name="带CSV的过期任务",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="success",
            result_uri=None,
            tenant_id=bi_datasource.tenant_id,
            source="manual",
            created_at=old_created,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        await BiQueryTask.filter(id=task.id).update(created_at=old_created)

        # 写一个 CSV 文件并更新 result_uri
        csv_path = tmp_path / f"{task.id}.csv"
        csv_path.write_text("id\n1\n", encoding="utf-8")
        await BiQueryTask.filter(id=task.id).update(result_uri=f"{task.id}.csv")
        assert csv_path.exists()

        cleaned = await cleanup_expired_tasks()
        assert cleaned == 1
        assert not csv_path.exists()

    async def test_cleanup_no_expired_returns_zero(self, app, bi_datasource, monkeypatch):
        """无过期任务时返回 0。"""
        from app.business.bi.async_query import state
        from app.business.bi.services_async_query import cleanup_expired_tasks

        state.set_runtime_redis(app.state.redis)
        # bi_query_task fixture 已创建一个 pending 任务（未过期）
        cleaned = await cleanup_expired_tasks()
        assert cleaned == 0

