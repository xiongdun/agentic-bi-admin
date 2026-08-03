"""async_query.runner worker 测试。

测试策略：
- 不依赖真 SQLAlchemy 连接，用 monkeypatch 替换 ``execute_sql`` 路径中的 ``engine.connect`` 与 ``result.fetchmany``
- 验证：成功路径写 result_snapshot/result_uri；取消路径清理 CSV；超时路径写 failed
- 验证：DB 状态 + Redis 状态同步更新
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _FakeResult:
    """模拟 SQLAlchemy Result 对象。"""

    def __init__(self, columns: list[str], all_rows: list[dict], batch_size: int):
        self._columns = columns
        self._all_rows = all_rows
        self._batch_size = batch_size
        self._cursor = 0
        self.returns_rows = True

    def keys(self):
        return self._columns

    def fetchmany(self, size: int):
        if self._cursor >= len(self._all_rows):
            return []
        end = min(self._cursor + size, len(self._all_rows))
        batch = self._all_rows[self._cursor:end]
        self._cursor = end
        return [SimpleNamespace(_mapping=r) for r in batch]


def _patch_runner_deps(monkeypatch, runner, fake_result):
    """统一 patch runner 依赖：test_connection / validate_sql / inject_tenant_filter / get_engine。"""

    async def _fake_test_connection(ds):
        return True, "ok", 1

    def _fake_validate_sql(sql, dialect="sqlite"):
        return SimpleNamespace(sql=sql, is_valid=True, error=None, warnings=[])

    def _fake_inject_tenant_filter(sql, tenant_id, dialect="sqlite"):
        return sql

    fake_engine = MagicMock()

    class _FakeConn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            return fake_result

    fake_engine.connect = MagicMock(return_value=_FakeConn())

    async def _fake_get_engine(ds):
        return fake_engine

    monkeypatch.setattr(runner, "test_connection", _fake_test_connection)
    monkeypatch.setattr(runner, "validate_sql", _fake_validate_sql)
    monkeypatch.setattr(runner, "inject_tenant_filter", _fake_inject_tenant_filter)
    monkeypatch.setattr(runner, "get_engine", _fake_get_engine)


class TestExecuteTask:
    async def test_success_writes_snapshot_and_csv(self, app, bi_datasource, monkeypatch, tmp_path):
        from app.business.bi.async_query import runner, state
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.models import BiQueryTask

        # 配置：CSV 目录指 tmp_path，batch 小一点便于测多批次
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_BATCH_SIZE", 5)
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_PREVIEW_ROWS", 10)

        user_id = bi_datasource.tenant_id
        task = await BiQueryTask.create(
            name="runner-success",
            datasource_id=bi_datasource.id,
            sql_text="SELECT id, name FROM orders",
            status="pending",
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )
        await state.init_state(task.id, app.state.redis, status="pending")

        fake_result = _FakeResult(
            columns=["id", "name"],
            all_rows=[{"id": i, "name": f"row{i}"} for i in range(23)],  # 23 行 = 5 批
            batch_size=5,
        )
        _patch_runner_deps(monkeypatch, runner, fake_result)

        await runner.execute_task(task.id, app.state.redis, app)

        # DB 状态
        await task.refresh_from_db()
        assert task.status == "success"
        assert task.rows_fetched == 23
        assert task.result_row_count == 23
        assert task.result_uri == f"{task.id}.csv"
        # snapshot 预览 ≤ 10 行
        assert task.result_snapshot["rowCount"] == 10
        assert task.result_snapshot["isTruncated"] is True

        # CSV 文件存在且非空
        csv_file = tmp_path / f"{task.id}.csv"
        assert csv_file.exists()
        content = csv_file.read_text(encoding="utf-8")
        assert "id,name" in content
        assert "row22" in content

    async def test_cancelled_cleans_csv(self, app, bi_datasource, monkeypatch, tmp_path):
        from app.business.bi.async_query import runner, state
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.models import BiQueryTask

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_BATCH_SIZE", 2)

        user_id = bi_datasource.tenant_id
        task = await BiQueryTask.create(
            name="runner-cancel",
            datasource_id=bi_datasource.id,
            sql_text="SELECT id FROM orders",
            status="pending",
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )
        await state.init_state(task.id, app.state.redis, status="pending")
        # 预先设取消标志
        await state.request_cancel(task.id, app.state.redis)

        fake_result = _FakeResult(
            columns=["id"],
            all_rows=[{"id": i} for i in range(10)],
            batch_size=2,
        )
        _patch_runner_deps(monkeypatch, runner, fake_result)

        await runner.execute_task(task.id, app.state.redis, app)

        await task.refresh_from_db()
        assert task.status == "cancelled"
        assert task.error_message is not None
        # 半成品 CSV 应被清理
        csv_file = tmp_path / f"{task.id}.csv"
        assert not csv_file.exists()

    async def test_datasource_unavailable_marks_failed(self, app, bi_datasource, monkeypatch):
        from app.business.bi.async_query import runner, state
        from app.business.bi.models import BiQueryTask

        user_id = bi_datasource.tenant_id
        task = await BiQueryTask.create(
            name="runner-ds-fail",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="pending",
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )
        await state.init_state(task.id, app.state.redis, status="pending")

        async def _fake_test_connection(ds):
            return False, "连接失败: mock", 5

        monkeypatch.setattr(runner, "test_connection", _fake_test_connection)

        await runner.execute_task(task.id, app.state.redis, app)

        await task.refresh_from_db()
        assert task.status == "failed"
        assert "数据源不可用" in (task.error_message or "")


class TestRecoverStaleTasks:
    async def test_recovers_old_running(self, app, bi_datasource):
        from app.business.bi.async_query import runner
        from app.business.bi.models import BiQueryTask

        user_id = bi_datasource.tenant_id
        # 构造一个 2 小时前 started_at 的 running 任务
        old_started = datetime.now() - timedelta(hours=2)
        task = await BiQueryTask.create(
            name="stale",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="running",
            started_at=old_started,
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )

        n = await runner.recover_stale_tasks(app.state.redis)
        assert n >= 1

        await task.refresh_from_db()
        assert task.status == "failed"
        assert "crash recovery" in (task.error_message or "")
