"""chat.py SSE 错误事件测试。

- NoLLMProviderError 透传为 SSE error 事件,code=4001
- BizError 透传 code
- 通用 Exception → code=1500
- _sse 工具函数 event / data 格式正确
"""

import pytest

from app.business.bi.api.chat import _sse
from app.core.exceptions import BizError
from app.business.bi.llm.router import NoLLMProviderError


def test_sse_format():
    """SSE 事件格式:event: <name>\\ndata: <payload>\\n\\n。"""
    out = _sse("error", {"code": 4001, "message": "未配置"})
    assert "event: error" in out
    assert "data: " in out
    assert "4001" in out
    assert "未配置" in out


def test_sse_done_format():
    out = _sse("done", "[DONE]")
    assert "event: done" in out
    assert "data: [DONE]" in out


def test_no_llm_provider_error_serializable_to_dict():
    """NoLLMProviderError 应当可序列化为 dict(含 code=4001)。"""
    e = NoLLMProviderError(available=[], requested="x")
    assert e.code == 4001
    # BizError 的 data 属性
    assert e.data == {"available": [], "requested": "x"}


def test_sse_emits_error_event_on_no_llm():
    """NoLLMProviderError 经 _sse 序列化后能被前端 onError 捕获到 code。"""
    e = NoLLMProviderError(available=[], requested="x")
    out = _sse("error", {"code": e.code, "message": e.msg})
    # 前端解析 data 字段后能拿到 {code: 4001, message: '...'}
    import json
    import re
    m = re.search(r"data: (.+)\n", out)
    assert m is not None
    payload = json.loads(m.group(1))
    assert payload["code"] == 4001
    assert "未配置" in payload["message"]


@pytest.mark.asyncio
async def test_event_gen_error_includes_code_for_no_llm():
    """event_gen 捕获 NoLLMProviderError → SSE error 事件含 code=4001。"""
    from app.business.bi.api.chat import _event_gen_with_error_handling

    # 用真实 NoLLMProviderError 替换节点,让 event_gen 走完 5 节点前就抛
    class _BoomIntentNode:
        async def __call__(self, state):
            raise NoLLMProviderError(available=[], requested="x")

    from app.business.bi.api import chat as chat_api

    orig_intent = chat_api.intent_node
    chat_api.intent_node = _BoomIntentNode()  # type: ignore[assignment]
    try:
        chunks = []
        async for c in _event_gen_with_error_handling(
            schema_text="- orders(id, amount)",
            dialect="sqlite",
            ds_id=1,
            sid=1,
            user_id=1,
            question="x",
        ):
            chunks.append(c)
    finally:
        chat_api.intent_node = orig_intent  # type: ignore[assignment]

    # 找到 error 事件
    import json
    import re
    error_payloads = []
    for c in chunks:
        if "event: error" in c:
            m = re.search(r"data: (.+)\n", c)
            if m:
                error_payloads.append(json.loads(m.group(1)))
    assert error_payloads, "expected at least one error event"
    assert error_payloads[0]["code"] == 4001


@pytest.mark.asyncio
async def test_event_gen_error_includes_code_for_bizerror():
    """event_gen 捕获 BizError → SSE error 事件含 BizError.code。"""
    from app.business.bi.api.chat import _event_gen_with_error_handling

    class _BoomIntentNode:
        async def __call__(self, state):
            raise BizError(code=2401, msg="some business error")

    from app.business.bi.api import chat as chat_api

    orig_intent = chat_api.intent_node
    chat_api.intent_node = _BoomIntentNode()  # type: ignore[assignment]
    try:
        chunks = []
        async for c in _event_gen_with_error_handling(
            schema_text="x", dialect="sqlite", ds_id=1, sid=1,
            user_id=1, question="x",
        ):
            chunks.append(c)
    finally:
        chat_api.intent_node = orig_intent  # type: ignore[assignment]

    import json
    import re
    found = False
    for c in chunks:
        if "event: error" in c:
            m = re.search(r"data: (.+)\n", c)
            if m:
                p = json.loads(m.group(1))
                if p.get("code") == 2401:
                    found = True
    assert found, f"expected code=2401 in error event, got chunks={[c[:60] for c in chunks]}"
