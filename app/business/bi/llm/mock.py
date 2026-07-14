"""Mock LLM — 用于本地开发 / 冒烟测试。

支持两种模式：
1. 默认模式：基于 prompt 关键字做规则匹配，返回固定 SQL
2. echo 模式：把 user 内容原样作为 assistant 输出
3. scripted 模式：通过 ``set_response`` 预设下一条响应
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.business.bi.llm.base import (
    BaseChatModel,
    ChatRequest,
    ChatResponse,
    Usage,
)

_SQL_BLOCK_RE = re.compile(r"```sql\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_RANKING_KEYWORDS = ("排名", "排行", "排序", "ranking", "rank", "top")
_GROUP_BY_KEYWORDS = ("各", "每个", "by ", "group")


@dataclass(slots=True)
class _ScriptedResponse:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"


class MockChatModel(BaseChatModel):
    """离线 / 演示用 LLM，按关键字返回固定 SQL。"""

    name = "mock"

    def __init__(self, default_model: str = "mock-sandbox") -> None:
        self.default_model = default_model
        self._scripted_queue: list[_ScriptedResponse] = []

    def set_response(self, content: str, *, tool_calls: list[dict] | None = None) -> None:
        """预设下一条响应。"""
        self._scripted_queue.append(_ScriptedResponse(content=content, tool_calls=tool_calls or []))

    def set_responses(self, contents: list[str]) -> None:
        self._scripted_queue = [_ScriptedResponse(content=c) for c in contents]

    def reset(self) -> None:
        self._scripted_queue.clear()

    async def achat(self, request: ChatRequest) -> ChatResponse:
        await asyncio.sleep(0.05)  # 模拟网络延迟

        if self._scripted_queue:
            scripted = self._scripted_queue.pop(0)
            return ChatResponse(
                content=scripted.content,
                model=self.default_model,
                finish_reason=scripted.finish_reason,
                usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            )

        last_user = next((m for m in reversed(request.messages) if m.role == "user"), None)
        user_text = last_user.content if last_user else ""
        system_text = next((m.content for m in request.messages if m.role == "system"), "")

        content = self._mock_synthesize(user_text, system_text)
        return ChatResponse(
            content=content,
            model=self.default_model,
            finish_reason="stop",
            usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    async def astream(self, request: ChatRequest) -> AsyncIterator[str]:
        resp = await self.achat(request)
        # 按 token 模拟流式
        for i in range(0, len(resp.content), 8):
            await asyncio.sleep(0.02)
            yield resp.content[i : i + 8]

    @staticmethod
    def _mock_synthesize(user_text: str, system_text: str) -> str:
        """根据用户问题 + schema 描述返回固定 SQL。

        Phase 1 demo 数据模型：
        - categories / products / customers / orders / order_items
        - 业务上 products ↔ orders 通过 order_items 多对多关联
        - 客户级 PII 列（phone / email / id_card）会被自动脱敏
        """
        u = user_text.lower()

        # 解释类 prompt 识别（系统提示里写"解释"/"解读"）
        if any(kw in system_text for kw in ("解释", "解读", "explain")):
            return MockChatModel._mock_explain(user_text)

        # 销售额 / 销售排名类（按产品线汇总本月）
        if any(kw in user_text for kw in ("销售额", "营收", "销售")) and any(kw in user_text for kw in _RANKING_KEYWORDS + _GROUP_BY_KEYWORDS):
            return (
                "```sql\n"
                "SELECT c.name AS product_line, "
                "SUM(o.amount) AS total_amount, "
                "COUNT(o.id) AS order_count "
                "FROM orders o "
                "JOIN order_items oi ON oi.order_id = o.id "
                "JOIN products p ON p.id = oi.product_id "
                "JOIN categories c ON c.id = p.category_id "
                "WHERE o.status = 'paid' "
                "GROUP BY c.name "
                "ORDER BY total_amount DESC\n"
                "```"
            )

        if "本月" in user_text and ("销售" in user_text or "订单" in user_text):
            return "```sql\nSELECT DATE(o.created_at) AS d, SUM(o.amount) AS amount FROM orders o WHERE o.status = 'paid' AND o.created_at >= DATE('now', 'start of month') GROUP BY d ORDER BY d\n```"

        # 客户列表（触发 phone 脱敏）
        if "客户" in user_text or "customer" in u:
            return "```sql\nSELECT id, name, phone, email FROM customers\n```"

        # 通用 SELECT
        if "select" in u or "查询" in user_text:
            return "```sql\nSELECT 1\n```"

        return f"```sql\nSELECT '{user_text[:30]}' AS question\n```"

    @staticmethod
    def _mock_explain(user_text: str) -> str:
        """解释 prompt 的 mock 响应 — 输出中文解读。"""
        # 简单识别"按产品线排名"模板
        if "排名" in user_text or "排行" in user_text or "top" in user_text.lower():
            return (
                "这条 SQL 把 ``orders``（订单表）通过 ``order_items``（订单明细）"
                "关联到 ``products``（商品）和 ``categories``（产品线），"
                "按 ``status = 'paid'`` 过滤出已支付订单，按产品线分组求和金额并倒序排序，"
                "LIMIT 隐式由系统按配额控制。"
                "\n\n结果中数值最大的产品线就是本月销售冠军，"
                "建议在 BI 看板里突出展示前 3 名。"
            )
        if "客户" in user_text:
            return "这条 SQL 直接列出 customers 表，敏感字段（phone / email）已被沙箱自动脱敏为 ``138****0001`` 形式，不需要在 SQL 里写脱敏函数。"
        if "本月" in user_text:
            return "按天聚合本月每天的已支付订单金额，返回一张日销售趋势表，可用于折线图。"
        return "已按 schema 执行了查询并返回结果。"


__all__ = ["MockChatModel"]
