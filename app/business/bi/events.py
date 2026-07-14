"""AgenticBI typed events — Phase 1 暂用空 stub。

后续任务会在 chat / execution 完成后 emit 事件；本文件先占位确保 manifest
引用合法。Phase 1 MVP 阶段不强依赖其他业务模块订阅，先不暴露 payload。
"""

from app.utils import EventSpec

# 占位事件：业务模块 manifest 要求 events 是 EventSpec 列表；
# Phase 1 先放一个最小可观测事件，等 chat 链路接通后扩充。
BI_QUERY_EXECUTED = EventSpec(name="bi.query.executed")

BI_EVENTS = [BI_QUERY_EXECUTED]

__all__ = ["BI_QUERY_EXECUTED", "BI_EVENTS"]
