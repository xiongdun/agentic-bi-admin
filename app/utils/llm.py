"""LLM 抽象层入口 — Phase 1 占位。

实际 LLM 客户端在 `app.business.bi.llm.*` 中按 Phase 1 Week 2（T35-T37）实现。

本模块的职责：
1. 为业务模块提供统一 import 入口（`from app.utils.llm import ...`）
2. 等 T35 完成后，再 re-export `BaseChatModel` / `LLMResponse` / `LLMRouter`
3. 业务模块 import 路径在 LLM 客户端实现前后保持不变

Phase 1 Week 1 期间本模块仅占位，不导出任何符号。
"""

from __future__ import annotations

__all__: list[str] = []
