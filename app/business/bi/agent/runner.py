"""Agent 流水线编排 — LangGraph StateGraph DAG。

固定 5 节点 DAG：intent → sql_gen → sql_validate → executor → explain → END
条件边：executor 成功 → explain；失败 → END

项目历史教训：
1. SSE error paths must still persist assistant messages（_persist_error_message）。
2. 不要用 asyncio.wait_for 包 __anext__ — 这里用 LangGraph astream，不需要手动包。
"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, cast

from app.business.bi.agent.state import AgentState


async def _persist_error_message(session_id: int, error: str, user_msg_id: int) -> None:
    """持久化错误消息到 bi_chat_message。

    项目历史教训：SSE error paths must still persist assistant messages。
    没有这个，用户看到"无结果"（空 detail）但实际有错误。
    """
    try:
        from app.business.bi.models import BiChatMessage

        await BiChatMessage.create(
            session_id=session_id,
            role="assistant",
            content=f"查询失败: {error}",
            status="failed",
            error_message=error,
            agent_steps_json=[
                {
                    "node": "runner",
                    "status": "failed",
                    "error": error,
                }
            ],
        )
    except Exception:
        pass  # 持久化失败不阻断错误返回


async def _persist_success_message(
    session_id: int,
    question: str,
    sql_text: str,
    sql_result: dict,
    explanation: str,
    chart_type: str,
    steps: list,
    token_usage: dict,
    intent_type: str,
) -> int:
    """持久化成功消息，返回 assistant 消息 ID。"""
    try:
        from app.business.bi.models import BiChatMessage

        msg = await BiChatMessage.create(
            session_id=session_id,
            role="assistant",
            content=explanation,
            sql_text=sql_text,
            sql_result=sql_result,
            agent_steps_json=steps,
            intent_type=intent_type,
            status="success",
            token_usage=token_usage,
        )
        return msg.id
    except Exception:
        return 0


async def run_chat_turn(state: AgentState) -> AsyncGenerator[dict, None]:
    """运行一次对话流水线，流式产出 step 事件。

    使用 LangGraph StateGraph DAG 编排。

    Yields:
        SSE 事件 dict（含 type / node / status / data）
    """
    start = time.time()
    session_id = state.get("session_id", 0)
    user_msg_id = state.get("user_msg_id", 0)

    try:
        # 延迟导入 LangGraph（避免模块加载时失败）
        from langgraph.graph import END, StateGraph

        # 构建图
        workflow = StateGraph(AgentState)

        # 添加节点
        from app.business.bi.agent.nodes.executor import executor_node
        from app.business.bi.agent.nodes.explain import explain_node
        from app.business.bi.agent.nodes.intent import intent_node
        from app.business.bi.agent.nodes.sql_gen import sql_gen_node
        from app.business.bi.agent.nodes.sql_validate import sql_validate_node

        workflow.add_node("intent", intent_node)
        workflow.add_node("sql_gen", sql_gen_node)
        workflow.add_node("sql_validate", sql_validate_node)
        workflow.add_node("executor", executor_node)
        workflow.add_node("explain", explain_node)

        # 添加边
        workflow.set_entry_point("intent")
        workflow.add_edge("intent", "sql_gen")
        workflow.add_edge("sql_gen", "sql_validate")
        workflow.add_edge("sql_validate", "executor")

        # 条件边：executor 成功 → explain；失败 → END
        def _after_executor(state: AgentState) -> str:
            if state.get("error"):
                return END
            return "explain"

        workflow.add_conditional_edges("executor", _after_executor)
        workflow.add_edge("explain", END)

        # 编译
        app = workflow.compile()

        # 流式执行
        current_state: dict[str, Any] = dict(state)
        current_state["steps"] = []
        current_state["token_usage"] = {}

        async for event in app.astream(cast(AgentState, current_state), stream_mode="updates"):
            # event 是 {node_name: node_output} 格式
            for node_name, node_output in event.items():
                # 推送 step 事件
                steps = node_output.get("steps", [])
                if steps:
                    latest_step = steps[-1]
                    yield {
                        "type": "step",
                        "node": node_name,
                        "status": latest_step.get("status", "success"),
                        "data": latest_step.get("data", {}),
                        "elapsedMs": latest_step.get("elapsed_ms", 0),
                    }

                # 合并状态
                # 注：节点已返回完整累积值（steps / token_usage 在节点内手动累加），
                # 这里直接覆盖，避免双重累加。
                for k, v in node_output.items():
                    current_state[k] = v

                # 检查是否有错误
                if node_output.get("error"):
                    error_msg = node_output["error"]
                    # 项目历史教训：持久化错误消息
                    await _persist_error_message(session_id, error_msg, user_msg_id)
                    yield {
                        "type": "error",
                        "node": node_name,
                        "error": error_msg,
                    }
                    return

        # 流程成功完成
        elapsed_ms = int((time.time() - start) * 1000)

        # 持久化成功消息
        assistant_msg_id = await _persist_success_message(
            session_id=session_id,
            question=state.get("question", ""),
            sql_text=current_state.get("validated_sql", ""),
            sql_result=current_state.get("sql_result", {}),
            explanation=current_state.get("explanation", ""),
            chart_type=current_state.get("chart_type", "table"),
            steps=current_state.get("steps", []),
            token_usage=current_state.get("token_usage", {}),
            intent_type=current_state.get("intent_type", "query"),
        )

        yield {
            "type": "final",
            "data": {
                "sqlText": current_state.get("validated_sql", ""),
                "sqlResult": current_state.get("sql_result", {}),
                "explanation": current_state.get("explanation", ""),
                "chartType": current_state.get("chart_type", "table"),
                "steps": current_state.get("steps", []),
                "tokenUsage": current_state.get("token_usage", {}),
                "assistantMsgId": assistant_msg_id,
                "totalElapsedMs": elapsed_ms,
            },
        }

    except Exception as e:
        # 整个流程异常
        elapsed_ms = int((time.time() - start) * 1000)
        error_msg = f"Agent 流水线异常: {e}"
        # 项目历史教训：持久化错误消息
        await _persist_error_message(session_id, error_msg, user_msg_id)
        yield {
            "type": "error",
            "node": "runner",
            "error": error_msg,
            "elapsedMs": elapsed_ms,
        }
