"""AgenticBI DataPolicy — Phase 1 占位。

后续任务会在 policies 中加入：
- DATASOURCE_READ — 跨租户过滤
- QUERY_EXEC_READ — 按 tenant_id / role_codes 限缩
- AUDIT_LOG_READ — 仅 admin / super 看全量

本文件先提供空列表让 manifest 引用合法。
"""

from app.utils import DataPolicy

BI_DATA_POLICIES: list[DataPolicy] = []

__all__ = ["BI_DATA_POLICIES"]
