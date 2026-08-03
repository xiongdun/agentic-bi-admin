"""BI 异步大查询子包。

组件：
- ``queue`` —— Redis List 队列（BLPOP）
- ``state`` —— Redis Hash 任务状态机
- ``storage`` —— 结果存储（JSON 预览 + CSV 流式）
- ``quota`` —— Redis 共享配额 + 熔断
- ``runner`` —— worker 协程（拉任务 → 执行 → 写结果）
"""

from __future__ import annotations
