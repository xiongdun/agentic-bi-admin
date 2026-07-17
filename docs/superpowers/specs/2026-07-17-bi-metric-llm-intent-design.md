# Metric 模板系统 + LLM 意图识别 — 设计文档

> 状态：approved by user 2026-07-17
> 范围：`app/business/bi/` 业务模块的 Phase 1.x 增强
> 目标：把 sql_gen 节点的"裸 LLM 生成 SQL"升级为"LLM 意图路由 + Metric 模板约束 + LLM 拼装"模式，提高对话工作台 SQL 生成准确率。

---

## 1. 背景与目标

### 1.1 现状问题

1. **`bi_metric` / `bi_dataset` / `bi_chart` 三张表在 DB 落灰**：模型存在但无 API、无 Service、无 UI、Agent 全程不消费。
2. **`intent_node` 是纯规则**（`< 1ms` 关键词匹配），写完的 `state.intent` **没有任何下游节点读取** —— 等于死代码。
3. **sql_gen 直接让 LLM "裸写" SQL**：每次从 0 拼，遇到"销售额 = SUM(paid orders)"这种业务口径容易漂移（不同天可能写出不同 SQL）。
4. **存在 mock 兜底**：LLM 调失败时悄悄回退到 `MockChatModel`，用户看不到错误，不利于真实联调。

### 1.2 目标

| 目标 | 度量 |
|---|---|
| **Metric 模板落地** | CRUD 可用 + 预置 5 个电商 metric + 至少 1 个 UI 路径供管理员增删改 |
| **LLM 意图识别必走** | 每次 send 都有 `intent` 节点的 LLM 调用（mock 路径外必走） |
| **Metric 模板强约束** | `intent=metric` 选中的模板必须以原表达式出现在最终 SQL |
| **去掉 mock 兜底** | 任何 LLM 失败 → 业务错误码 4001，前端明确提示 |
| **chat 用户无感** | ChatWorkbench 界面不暴露"指标"概念 |
| **可观测性** | `agent_steps_json` 包含 `intent + metric_ids + reasoning` |

### 1.3 非目标

- 不实装 Dataset 管理 UI（保留模型，Phase 2 再说）
- 不重写完整 LangGraph DAG（仍用 5 节点 chain）
- 不接入 Embedding 向量检索（规模未到）
- 不接 multi-agent（schema_select / chart_recommend 节点）

---

## 2. 关键决策（已与用户对齐）

| # | 决策 | 选择 |
|---|---|---|
| 1 | Metric 模板语义 | **SQL 片段 + LLM 拼装完整 SELECT**（LLM 强约束，原表达式必须出现） |
| 2 | Metric 匹配 | **LLM 一次返回 `{intent, metrics: [{id, reason}]}`**（30 个以内 metric 直接全量给 LLM 选） |
| 3 | Metric 范围 | **预置 5 个 + 完整 CRUD UI**（管理员后台用，chat 用户无感） |
| 4 | 多选 / 0 选 | **metrics 数组可空**，空时降级为 `intent=table` 走老路径 |
| 5 | 无 LLM | **报错** `code=4001`「未配置 LLM Provider」，**去掉所有 mock 兜底** |
| 6 | Dataset | **本轮不参与**，模型保留 |
| 7 | UI 可见性 | **CRUD 页面有、Chat 不显示** |

---

## 3. 整体架构

### 3.1 数据流（改造后）

```
用户输入 "本月各产品线销售额排名"
  ↓
[POST /business/bi/chat/sessions/{id}/messages]  (require_buttons B_BI_CHAT_SEND)
  ↓
chat.py send_message() event_gen()
  ↓
┌─ ① intent_node (LLM 必走) ─────────────────────────────────┐
│  输入: {question, schema_text, dialect, datasource_id}     │
│  1) 查 datasource_id 下所有 enabled Metric                  │
│  2) 检查 router.has_real_provider() —— 否则 raise 4001     │
│  3) LLM 一次调用: response_format=json_object               │
│     返回 JSON {intent, metrics:[{id, reason}], reasoning}  │
│  4) 校验: 解析失败 / id 不在 valid set → 降级 table+[]     │
│  5) 降级: intent=metric && metrics=[] → 降级 table+[]      │
│  6) 写 state.intent / state.metric_ids / state.metric_templates │
│  7) 写 step trace → SSE event "step" node=intent            │
└────────────────────────────────────────────────────────────┘
  ↓
┌─ ② sql_gen_node (LLM, prompt 分支) ───────────────────────┐
│  若 metric_templates 非空 → SQL_GEN_WITH_METRIC_USER prompt │
│  否则 → 原 SQL_GEN_PROMPT (老 prompt 不变)                 │
│  调 LLM，无 mock 兜底                                       │
│  写 step trace → SSE event "step" node=sql_gen             │
└────────────────────────────────────────────────────────────┘
  ↓
┌─ ③ sql_validate_node (本地 sqlglot AST 白名单) ──────────────┐
│  失败 → execution_error → 跳 executor                       │
│  写 step trace → SSE event "step" node=validate             │
└────────────────────────────────────────────────────────────┘
  ↓
┌─ ④ executor_node (sandbox 4 闸) ────────────────────────────┐
│  whitelist → tenant_inject → masking → execute+quota       │
│  写 step trace → SSE event "step" node=executor            │
└────────────────────────────────────────────────────────────┘
  ↓
┌─ ⑤ explain_node (LLM, 无 mock 兜底) ────────────────────────┐
│  写 step trace → SSE event "step" node=explain              │
└────────────────────────────────────────────────────────────┘
  ↓
落库 ChatMessage (role=assistant, sql=final_sql, error=err,
      agent_steps_json=完整 5 个 step)
  ↓
SSE event "final" {userMessageId, assistantMessageId, intent,
      finalSql, explanation, error, columns, rows, ...}
```

### 3.2 关键不变量

- **状态机**：5 节点顺序执行，state 在节点间以 `TypedDict` 传递（不持久化）
- **失败语义**：任何 LLM 失败 → 上抛 `NoLLMProviderError` / 业务异常 → SSE `event: error` 终结
- **降级语义**：`intent=metric` + `metrics=[]` → 自动降 `intent=table`（不报错）
- **mock 路径**：本轮**完全去掉**。`MockChatModel` 类保留仅供单元测试

### 3.3 模块依赖（保证边界）

```
intent_node (新) → app.business.bi.services.metric.list_for_intent
sql_gen_node    → app.business.bi.models.Metric (只读)
chat.py         → app.business.bi.api.metric (CRUD)
前端            → /business/bi/metrics/* (CRUD)
                → /business/bi/chat/sessions/{id}/messages (SSE)
```

不引入新依赖（`httpx` 已经在；`json` / `re` 标准库）。

---

## 4. 后端实现

### 4.1 `app/business/bi/models/semantic.py`（改）

```python
class Metric(BaseModel, AuditMixin):
    id = fields.IntField(primary_key=True, description="度量ID")
    name = fields.CharField(max_length=200, db_index=True, description="业务名")
    display_name = fields.CharField(max_length=200, description="展示名")
    description = fields.CharField(max_length=500, null=True, blank=True)
    sql_template = fields.CharField(max_length=2000, description="SQL 表达式片段")
    datasource_id: int   # ★ 新增：FK→Datasource
    datasource: fields.ForeignKeyRelation["Datasource"] = fields.ForeignKeyField(
        "app_system.Datasource",
        on_delete=fields.CASCADE,
        related_name="metrics",
        description="所属数据源",
    )
    unit = fields.CharField(max_length=50, null=True, blank=True)
    owner_id = fields.IntField(db_index=True)
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable)

    class Meta:
        table = "bi_metric"
        table_description = "BI 业务度量"
```

> Dataset / Chart 模型**不动**。

### 4.2 `app/business/bi/llm/router.py`（改）

```python
from app.core.exceptions import BizError


class NoLLMProviderError(BizError):
    """未配置可用 LLM Provider 时抛出的业务异常（code=4001）。"""

    def __init__(self, available: list[str] = [], requested: str | None = None):
        super().__init__(code=4001, msg="未配置 LLM Provider，请先在 /bi/models 添加")
        self.data = {"available": available, "requested": requested}


class LLMRouter:
    @classmethod
    def build_default(cls) -> "LLMRouter":
        router = cls(_models={})
        router.default_provider = ""        # ★ 空：未配置
        api_key = getattr(APP_SETTINGS, "DEEPSEEK_API_KEY", "")
        if api_key:
            router._models["deepseek"] = DeepSeekChatModel(api_key=api_key)
            router.default_provider = "deepseek"
        # ★ 不再默认注册 mock
        return router

    def has_real_provider(self) -> bool:
        return bool(self._models) and self.default_provider != ""

    def get(self, name: str | None = None) -> BaseChatModel:
        if name is None:
            name = self.default_provider
        m = self._models.get(name)
        if m is None:
            raise NoLLMProviderError(
                available=list(self._models.keys()),
                requested=name,
            )
        return m
```

`MockChatModel` 类**保留**（不删除），仅供 `tests/` 用，**不再被任何业务路径自动注册**。

### 4.3 `app/business/bi/agent/prompts/__init__.py`（新增 prompt）

```python
INTENT_ROUTER_SYSTEM = "你是数据分析意图路由器，输出严格 JSON。"

INTENT_ROUTER_USER = """可用数据源方言: {dialect}

Schema:
{schema_text}

可用指标（{metric_count} 个）:
{metric_list}

用户问题: {question}

请只返回 JSON（不要任何 markdown/代码块/注释）:
{{
  "intent": "metric" | "table" | "freeform",
  "metrics": [{{"id": <int>, "reason": "<20字内原因>"}}],
  "reasoning": "<50字内整体判断>"
}}

规则：
1. 能用 1+ 指标直接回答 → intent="metric"，metrics 列出 id
2. 聚合/排名/分桶/总数 → intent="table"
3. 开放探索/选品类 → intent="freeform"
4. 问候/与数据无关 → intent="freeform", metrics=[]
5. metrics 可为 []"""


SQL_GEN_WITH_METRIC_USER = """{schema_header}

用户问题: {question}

【必须使用】的指标模板（{metric_count} 个，必须在最终 SQL 中以原表达式出现）:
{metric_templates}

要求：
- 必返回 ```sql ... ``` 块
- 每个【必须使用】模板中的表达式必须原样出现在 SQL 中（可包在子查询/CTE/SELECT 里）
- 时间用 strftime 或 >= 'YYYY-MM-DD'
- LIMIT 100"""
```

### 4.4 `app/business/bi/agent/nodes/intent.py`（重写）

```python
import json
import re
import time

from app.business.bi.agent.prompts import INTENT_ROUTER_SYSTEM, INTENT_ROUTER_USER
from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.llm import ChatMessage, ChatRequest, get_router
from app.business.bi.llm.router import NoLLMProviderError
from app.business.bi.models.semantic import Metric
from app.core.exceptions import BizError
from app.core.log import log


class IntentRouter:
    """LLM 意图路由 + 选 metric。"""

    def __init__(self) -> None:
        self.prompt = INTENT_ROUTER_USER
        self.system = INTENT_ROUTER_SYSTEM

    async def __call__(self, state: AgentState) -> AgentState:
        started = time.perf_counter()

        # 1) 取该 datasource 下所有 enabled metric
        metrics: list[Metric] = await Metric.filter(
            datasource_id=state["datasource_id"],
            status_type="enable",
        ).order_by("id")

        metric_list = "\n".join(
            f"  - id={m.id} name={m.name} desc={m.description or ''} "
            f"template=`{m.sql_template}`"
            for m in metrics
        ) or "  (无)"

        # 2) LLM 调用
        router = get_router()
        try:
            resp = await router.achat(
                state.get("_llm_provider"),
                ChatRequest(
                    messages=[
                        ChatMessage(role="system", content=self.system),
                        ChatMessage(
                            role="user",
                            content=self.prompt.format(
                                dialect=state["dialect"],
                                schema_text=state["schema_text"],
                                metric_count=len(metrics),
                                metric_list=metric_list,
                                question=state["question"],
                            ),
                        ),
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                ),
            )
        except NoLLMProviderError:
            raise BizError(code=4001, msg="未配置 LLM Provider，请先访问 /bi/models 添加")

        # 3) 解析 + 校验
        try:
            parsed = json.loads(resp.content)
        except json.JSONDecodeError as e:
            log.warning(f"intent LLM returned non-JSON: {resp.content[:200]}")
            parsed = {"intent": "table", "metrics": [], "reasoning": "parse_failed"}

        intent = parsed.get("intent", "table")
        if intent not in ("metric", "table", "freeform"):
            intent = "table"

        valid_ids = {m.id for m in metrics}
        chosen: list[dict] = []
        for c in parsed.get("metrics", []) or []:
            try:
                mid = int(c.get("id"))
            except (TypeError, ValueError):
                continue
            if mid in valid_ids:
                chosen.append({"id": mid, "reason": str(c.get("reason", ""))[:50]})

        # 4) 降级
        if intent == "metric" and not chosen:
            intent = "table"

        # 5) 写 state
        state["intent"] = intent
        state["metric_ids"] = [c["id"] for c in chosen]
        id2template = {m.id: m.sql_template for m in metrics}
        state["metric_templates"] = [id2template[mid] for mid in state["metric_ids"]]
        state.setdefault("tokens_used", 0)
        state["tokens_used"] += resp.usage.total_tokens

        state.setdefault("steps", []).append(
            StepTrace(
                node="intent",
                started_at=started,
                ended_at=time.perf_counter(),
                input={
                    "question": state["question"],
                    "available_metrics": len(metrics),
                },
                output={
                    "intent": intent,
                    "metric_ids": state["metric_ids"],
                    "metric_names": [
                        m.name for m in metrics if m.id in state["metric_ids"]
                    ],
                    "reasoning": str(parsed.get("reasoning", ""))[:100],
                },
                tokens=resp.usage.total_tokens,
            ).to_dict()
        )
        return state


intent_node = IntentRouter()
```

### 4.5 `app/business/bi/agent/nodes/sql_gen.py`（改）

```python
async def sql_gen_node(state: AgentState) -> AgentState:
    started = time.perf_counter()
    question = state.get("question", "")
    schema_text = state.get("schema_text", "(no schema)")
    dialect = state.get("dialect", "sqlite")
    metric_templates = state.get("metric_templates", [])

    schema_header = SCHEMA_HEADER.format(dialect=dialect, schema_text=schema_text)

    if metric_templates:
        user_prompt = SQL_GEN_WITH_METRIC_USER.format(
            schema_header=schema_header,
            question=question,
            metric_count=len(metric_templates),
            metric_templates="\n".join(
                f"  {i+1}. {t}" for i, t in enumerate(metric_templates)
            ),
        )
    else:
        user_prompt = SQL_GEN_PROMPT.format(
            schema_header=schema_header, question=question,
        )

    messages = [
        ChatMessage(role="system", content=SYSTEM_BASE),
        ChatMessage(role="user", content=user_prompt),
    ]
    request = ChatRequest(messages=messages, temperature=0.1)

    router = get_router()
    # ★ 无 mock 兜底；NoLLMProviderError 直接上抛
    resp = await router.achat(state.get("_llm_provider"), request)

    draft = _extract_sql(resp.content) or resp.content.strip()
    parsed = safe_parse(draft, dialect)  # type: ignore[arg-type]
    if parsed is not None:
        draft = parsed.sql(dialect=dialect)  # type: ignore[arg-type]

    state["draft_sql"] = draft
    state.setdefault("steps", []).append(
        StepTrace(
            node="sql_gen",
            started_at=started,
            ended_at=time.perf_counter(),
            input={
                "question": question,
                "schema_chars": len(schema_text),
                "metric_templates": len(metric_templates),
            },
            output={"draft_sql": draft, "raw_excerpt": resp.content[:200]},
            tokens=resp.usage.total_tokens,
        ).to_dict()
    )
    state.setdefault("tokens_used", 0)
    state["tokens_used"] += resp.usage.total_tokens
    return state
```

### 4.6 `app/business/bi/agent/nodes/explain.py`（改）

删除 `try/except → mock` 兜底块，让异常上抛：

```python
# 删除
# try:
#     resp = await router.achat(provider, request)
# except Exception:
#     resp = await router.achat("mock", request)
#     state["fallback_used"] = state.get("fallback_used") or "mock"

# 改为
resp = await router.achat(state.get("_llm_provider"), request)
```

### 4.7 `app/business/bi/services/metric.py`（新增）

```python
from app.business.bi.models.semantic import Metric


async def list_metrics(
    *, datasource_id: int | None = None, name: str | None = None,
    status_type: str | None = None, page: int = 1, size: int = 20,
) -> tuple[int, list[Metric]]:
    qs = Metric.all()
    if datasource_id is not None:
        qs = qs.filter(datasource_id=datasource_id)
    if name:
        qs = qs.filter(name__icontains=name)
    if status_type:
        qs = qs.filter(status_type=status_type)
    total = await qs.count()
    rows = await qs.order_by("-id").offset((page - 1) * size).limit(size)
    return total, list(rows)


async def get_metric(metric_id: int) -> Metric | None:
    return await Metric.get_or_none(id=metric_id)


async def create_metric(
    *, name: str, display_name: str, sql_template: str, datasource_id: int,
    description: str | None = None, unit: str | None = None, owner_id: int,
) -> Metric:
    return await Metric.create(
        name=name, display_name=display_name, sql_template=sql_template,
        datasource_id=datasource_id, description=description, unit=unit,
        owner_id=owner_id, status_type="enable",
    )


async def update_metric(metric_id: int, **fields) -> Metric:
    m = await Metric.get(id=metric_id)
    for k, v in fields.items():
        if v is not None and hasattr(m, k):
            setattr(m, k, v)
    await m.save()
    return m


async def delete_metric(metric_id: int) -> None:
    await Metric.filter(id=metric_id).delete()


async def list_for_intent(datasource_id: int) -> list[dict]:
    """供 LLM intent router 用的精简列表。"""
    metrics = await Metric.filter(
        datasource_id=datasource_id, status_type="enable",
    ).order_by("id").values("id", "name", "description", "sql_template")
    return list(metrics)


async def test_metric_template(metric_id: int) -> dict:
    """校验 sql_template 的语法合法性 + 试渲染占位符 + 沙箱 dry-run。

    模板本质是 SQL 片段（不是完整 SQL），所以 /test 不直接执行模板，
    而是用 sqlglot 解析验证语法正确性，并报告"是否包含必需占位符"。
    执行层面的验证留给 sql_gen_node 在真实 chain 里跑。
    """
    from app.business.bi.services.datasource import get_datasource
    from app.business.bi.sandbox.whitelist import validate_tree
    from app.utils import safe_parse

    m = await get_metric(metric_id)
    if m is None:
        return {"success": False, "error": "metric not found"}
    ds = await get_datasource(m.datasource_id)
    if ds is None:
        return {"success": False, "error": "datasource not found"}

    # 1) 占位符必填检查
    import re
    placeholders = re.findall(r"\{(\w+)\}", m.sql_template)
    if not placeholders:
        return {
            "success": False,
            "error": "模板缺少占位符（如 {order}），无法被 sql_gen 替换",
        }

    # 2) 语法校验：把模板包成合法 SELECT 看 sqlglot 能否解析
    #    用 ds 关联的第一张表名做 dry-run 替换（仅验证语法，不执行）
    test_sql = f"SELECT {m.sql_template} FROM dual"
    tree = safe_parse(test_sql, dialect=ds.type.value)
    if tree is None:
        return {
            "success": False,
            "error": f"sqlglot 解析失败，请检查模板语法（{ds.type.value}）",
        }
    ok, reason = validate_tree(tree, dialect=ds.type.value)
    if not ok:
        return {"success": False, "error": f"whitelist_denied: {reason}"}

    return {
        "success": True,
        "placeholders": placeholders,
        "datasource": ds.name,
        "dialect": ds.type.value,
    }
```

### 4.8 `app/business/bi/api/metric.py`（新增）

```python
router = APIRouter(prefix="/metrics")


@router.post("/search", name="bi.metrics.search", dependencies=[require_buttons("B_BI_METRIC_VIEW")])
async def search(obj_in: MetricPageQuery = Depends()):
    total, rows = await list_metrics(
        datasource_id=_decode_ds_id(obj_in.datasource_id) if obj_in.datasource_id else None,
        name=obj_in.name, status_type=obj_in.status_type,
        page=obj_in.current, size=obj_in.size,
    )
    return SuccessExtra(
        data={"records": [_to_out(m) for m in rows]},
        total=total, current=obj_in.current, size=obj_in.size,
    )


@router.post("", name="bi.metrics.create", dependencies=[require_buttons("B_BI_METRIC_MANAGE")])
async def create(obj_in: MetricCreate):
    user_id = _user_id_or_fail()
    m = await create_metric(
        name=obj_in.name, display_name=obj_in.display_name,
        sql_template=obj_in.sql_template,
        datasource_id=_decode_ds_id(obj_in.datasource_id),
        description=obj_in.description, unit=obj_in.unit, owner_id=user_id,
    )
    return Success(data={"createdId": encode_id(m.id)})


@router.patch("/{item_id}", name="bi.metrics.update", dependencies=[require_buttons("B_BI_METRIC_MANAGE")])
async def update(item_id: str, obj_in: MetricUpdate):
    mid = decode_id(item_id)
    await update_metric(mid, **obj_in.model_dump(exclude_unset=True))
    return Success(data={"updatedId": item_id})


@router.delete("/{item_id}", name="bi.metrics.delete", dependencies=[require_buttons("B_BI_METRIC_MANAGE")])
async def delete(item_id: str):
    mid = decode_id(item_id)
    await delete_metric(mid)
    return Success(msg="deleted")


@router.post("/{item_id}/test", name="bi.metrics.test", dependencies=[require_buttons("B_BI_METRIC_MANAGE")])
async def test(item_id: str):
    mid = decode_id(item_id)
    result = await test_metric_template(mid)
    return Success(data=result)
```

### 4.9 `app/business/bi/api/chat.py`（改 SSE 错误处理）

```python
async def event_gen():
    try:
        ...  # 5 节点流程不变
    except NoLLMProviderError as e:
        yield _sse("error", {"code": 4001, "message": e.msg})
    except BizError as e:
        yield _sse("error", {"code": e.code, "message": e.msg})
    except Exception:
        log.exception("chat send_message SSE failed")
        yield _sse("error", {"code": 1500, "message": "internal error"})
```

### 4.10 `app/business/bi/init_data.py`（改）

```python
BI_MENU_CHILDREN = [
    ...,
    {
        "menu_name": "指标管理",
        "route_name": "bi_metrics",         # ★ 无连字符
        "route_path": "/bi/metrics",
        "component": "view.bi_metrics",
        "icon": "mdi:sigma",
        "order": 4,                          # 调到审计前
        "buttons": [
            {"button_code": "B_BI_METRIC_VIEW", "button_desc": "查看指标"},
            {"button_code": "B_BI_METRIC_MANAGE", "button_desc": "管理指标"},
        ],
    },
    {"menu_name": "审计面板", ..., "order": 5},  # 顺序后挪
]

# 4 个角色都加上 B_BI_METRIC_VIEW；BI_ADMIN 额外加 B_BI_METRIC_MANAGE
BI_ADMIN_ROLE["buttons"] = [..., "B_BI_METRIC_VIEW", "B_BI_METRIC_MANAGE"]
BI_AUDITOR_ROLE["buttons"] = [..., "B_BI_METRIC_VIEW"]


# 预置 5 个电商 metric
DEFAULT_METRICS = [
    {
        "name": "销售额", "display_name": "销售额",
        "description": "已支付订单的总金额（人民币）",
        "sql_template": "SUM({order}.amount) WHERE {order}.status='paid'",
        "unit": "元",
    },
    {
        "name": "订单数", "display_name": "订单数",
        "description": "已支付订单总数",
        "sql_template": "COUNT({order}.id) WHERE {order}.status='paid'",
        "unit": "单",
    },
    {
        "name": "退款额", "display_name": "退款额",
        "description": "已审核通过的退款总金额",
        "sql_template": "SUM({return}.refunded_amount) WHERE {return}.status='approved'",
        "unit": "元",
    },
    {
        "name": "客单价", "display_name": "客单价",
        "description": "平均每单金额（销售额 ÷ 订单数）",
        "sql_template": "CAST(SUM(CASE WHEN {order}.status='paid' THEN {order}.amount ELSE 0 END) AS REAL) / NULLIF(COUNT(CASE WHEN {order}.status='paid' THEN 1 END), 0)",
        "unit": "元/单",
    },
    {
        "name": "月活客户", "display_name": "月活客户",
        "description": "当月有过成交的客户数",
        "sql_template": "COUNT(DISTINCT {order}.customer_id) WHERE {order}.status='paid'",
        "unit": "人",
    },
]


async def _ensure_default_metrics(datasource_id: int) -> list[Metric]:
    out = []
    for m in DEFAULT_METRICS:
        obj, _ = await _safe_update_or_create(
            Metric,
            {"name": m["name"], "datasource_id": datasource_id},
            {**m, "datasource_id": datasource_id, "owner_id": 1, "status_type": "enable"},
        )
        out.append(obj)
    return out


async def init():
    # 1. 旧 route_name 迁移 (已有)
    ...
    # 2. 菜单 / 角色
    await apply_init_data(INIT_DATA)
    # 3. 默认租户
    tenant = await _ensure_default_tenant()
    # 4. 默认数据源
    ds = await _ensure_default_datasource(tenant.id)
    # 5. ★ 预置 metric（必须在数据源后）
    await _ensure_default_metrics(ds.id)
    # 6. 绑回填
    await _bind_tenant_default_datasource(tenant, ds)
    # 7. LLM router 刷新
    try:
        await refresh_router()
    except Exception:
        pass
    # 8. ★ 检查 LLM 配置，缺则 warn
    if not get_router().has_real_provider():
        log.warning("=" * 60)
        log.warning("BI 模块：未配置 LLM Provider")
        log.warning("对话工作台将返回 4001 错误")
        log.warning("请访问 /bi/models 添加至少 1 个启用的 Provider")
        log.warning("=" * 60)
    # 9. 审计清理
    try:
        from app.business.bi.services.audit import cleanup_old_audit_logs
        await cleanup_old_audit_logs(int(getattr(APP_SETTINGS, "BI_AUDIT_RETENTION_DAYS", 90)))
    except Exception:
        pass
```

### 4.11 错误码扩展 `app/core/code.py`

```python
NO_LLM_PROVIDER = 4001
INTENT_PARSE_FAILED = 4002
```

---

## 5. 前端实现

### 5.1 新增 `web/src/service/api/bi-metric.ts`

```typescript
import { request } from '../request';

export function fetchBiMetricList(data: Api.Bi.MetricSearchParams) {
  return request<Api.Bi.MetricList>({
    url: '/business/bi/metrics/search', method: 'post', data,
  });
}
export function fetchCreateBiMetric(data: Api.Bi.MetricCreateParams) {
  return request<{ createdId: string }>({
    url: '/business/bi/metrics', method: 'post', data,
  });
}
export function fetchUpdateBiMetric(id: string, data: Api.Bi.MetricUpdateParams) {
  return request<{ updatedId: string }>({
    url: `/business/bi/metrics/${id}`, method: 'patch', data,
  });
}
export function fetchDeleteBiMetric(id: string) {
  return request({ url: `/business/bi/metrics/${id}`, method: 'delete' });
}
export function fetchTestBiMetric(id: string) {
  return request<Api.Bi.MetricTestResult>({
    url: `/business/bi/metrics/${id}/test`, method: 'post',
  });
}
```

在 `web/src/service/api/index.ts` 重新导出。

### 5.2 新增 `web/src/views/bi/metrics/index.vue`

参照 `web/src/views/bi/models/index.vue` 模式：

- 顶部：搜索框（name）+ 数据源 select + 状态 select + [新增] 按钮
- 中部：NDataTable
  - 列：ID / 名称 / 展示名 / 描述 / SQL 模板（缩略）/ 单位 / 数据源 / 状态 / 操作
  - 操作：[编辑] [测试] [启用/禁用] [删除]
- 新增/编辑 Modal：NInput / NSelect / NInput type="textarea" rows=4
- 测试 Modal：显示 success / row_count / cost_ms / error

### 5.3 类型定义 `web/src/typings/api/bi.d.ts`

```typescript
declare namespace Api.Bi {
  interface Metric {
    id: string;
    name: string;
    displayName: string;
    description: string | null;
    sqlTemplate: string;
    datasourceId: string | null;
    datasourceName?: string;
    unit: string | null;
    statusType: 'enable' | 'disable';
    createdAt: string;
    updatedAt: string;
  }
  interface MetricSearchParams {
    current: number; size: number;
    name?: string | null;
    datasourceId?: string | null;
    statusType?: string | null;
  }
  interface MetricList extends Api.Common.PaginatingQueryRecord<Metric> {}
  interface MetricCreateParams {
    name: string; displayName: string;
    description?: string | null;
    sqlTemplate: string;
    datasourceId: string;
    unit?: string | null;
  }
  interface MetricUpdateParams {
    displayName?: string;
    description?: string | null;
    sqlTemplate?: string;
    unit?: string | null;
    statusType?: 'enable' | 'disable';
  }
  interface MetricTestResult {
    success: boolean;
    placeholders?: string[];          // 模板中提取的占位符，如 ['order']
    datasource?: string;              // 关联的数据源名
    dialect?: string;                 // 关联的方言
    error?: string | null;
  }
}
```

### 5.4 路由注册

按现有 elegant-router 模式，在自动生成的路由源里加：
```
name: bi_metrics
path: /bi/metrics
component: view.bi_metrics
meta: { title: page.bi.metrics.title, icon: mdi:sigma }
```

**警告**：`route_name` 必须严格 `bi_metrics`（无连字符），匹配后端 `init_data.py`。

### 5.5 i18n

`zh-CN.ts` / `en-US.ts`：
```typescript
'page.bi.metrics.title': '指标管理',
'page.bi.metrics.searchPlaceholder': '搜索指标名称',
'page.bi.metrics.columns.name': '名称',
'page.bi.metrics.columns.displayName': '展示名',
'page.bi.metrics.columns.description': '描述',
'page.bi.metrics.columns.datasource': '数据源',
'page.bi.metrics.columns.unit': '单位',
'page.bi.metrics.columns.status': '状态',
'page.bi.metrics.columns.actions': '操作',
'page.bi.metrics.create': '新增指标',
'page.bi.metrics.edit': '编辑指标',
'page.bi.metrics.test': '测试模板',
'page.bi.metrics.test.success': '执行成功',
'page.bi.metrics.test.failed': '执行失败',
'page.bi.metrics.fields.sqlTemplate.tip': '使用 {table_alias} 引用表，如 {order}.amount。系统会自动注入租户过滤。',
```

### 5.6 ChatWorkbench 改动（极小）

**两个文件改**：
1. `web/src/service/api/bi-chat.ts` 改 `onError` handler —— 把 code 也传出去
2. `web/src/views/bi/chat/index.vue` 改 onError 处理 —— 用 code 路由错误

`bi-chat.ts` `parseSse` 改：
```typescript
if (event === 'error' && parsed && typeof parsed === 'object') {
  const obj = parsed as { code?: number; message?: string };
  handlers.onError(obj.message ?? String(obj), obj.code);
}
```

`bi-chat.ts` `openBiChatSend` 类型加 `code?: number`：
```typescript
handlers: {
  onStep: ...;
  onFinal: ...;
  onError: (msg: string, code?: number) => void;  // ★ 加 code
  onDone: ...;
}
```

`bi-chat.ts` `openBiChatSend` 内部调 `onError` 时同步传 code（HTTP 错误时 code=0）：
```typescript
if (!resp.ok || !resp.body) {
  handlers.onError(`HTTP ${resp.status}`, resp.status);
  handlers.onDone();
  return;
}
```

`chat/index.vue` 改 onError：
```typescript
onError: (msg, code) => {
  if (code === 4001) {
    window.$message?.error('请先在「模型管理」中配置 LLM Provider');
    router.push({ name: 'bi_models' });
    return;
  }
  if (code === 4002) {
    window.$message?.error('意图识别失败，请重试或换种问法');
    return;
  }
  if (currentStream.value) currentStream.value.error = msg;
}
```

**其余 chat UI 完全不动**。

### 5.7 前端文件清单

| 文件 | 改动 |
|---|---|
| `web/src/service/api/bi-metric.ts` | 新增 |
| `web/src/service/api/index.ts` | re-export |
| `web/src/views/bi/metrics/index.vue` | 新增 |
| `web/src/views/bi/metrics/modules/...` | (按需) 拆分子组件 |
| `web/src/typings/api/bi.d.ts` | 新增类型 |
| `web/src/locales/langs/zh-CN.ts` | 新增文案 |
| `web/src/locales/langs/en-US.ts` | 新增文案 |
| 路由源 | 注册 `bi_metrics` |
| `web/src/views/bi/chat/index.vue` | onError 加 LLM 缺失跳 /bi/models |

---

## 6. LLM Prompt（完整版）

### 6.1 Intent Router Prompt

**System**:
```
你是数据分析意图路由器，输出严格 JSON。
```

**User** (动态填):
```
可用数据源方言: {dialect}

Schema:
{schema_text}

可用指标（{metric_count} 个）:
{metric_list}

用户问题: {question}

请只返回 JSON（不要任何 markdown/代码块/注释）:
{
  "intent": "metric" | "table" | "freeform",
  "metrics": [{"id": <int>, "reason": "<20字内原因>"}],
  "reasoning": "<50字内整体判断>"
}

规则：
1. 能用 1+ 指标直接回答 → intent="metric"，metrics 列出 id
2. 聚合/排名/分桶/总数 → intent="table"
3. 开放探索/选品类 → intent="freeform"
4. 问候/与数据无关 → intent="freeform", metrics=[]
5. metrics 可为 []
```

`response_format={"type": "json_object"}` 强制 JSON。

### 6.2 SQL Gen with Metric Prompt

```
{schema_header}

用户问题: {question}

【必须使用】的指标模板（{metric_count} 个，必须在最终 SQL 中以原表达式出现）:
{metric_templates}

要求：
- 必返回 ```sql ... ``` 块
- 每个【必须使用】模板中的表达式必须原样出现在 SQL 中（可包在子查询/CTE/SELECT 里）
- 时间用 strftime 或 >= 'YYYY-MM-DD'
- LIMIT 100
```

---

## 7. 测试策略

### 7.1 单元测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_metric_crud.py` | Metric CRUD：list / create / update / delete / soft delete / datasource filter |
| `tests/test_intent_router.py` | IntentRouter：mock LLM 返回各种 JSON（合法/非法/空 metrics/不存在的 id），验证降级逻辑 |
| `tests/test_llm_router.py` | LLMRouter：`has_real_provider()` 正确性；无 provider 时 `get()` 抛 NoLLMProviderError |
| `tests/test_sql_gen_metric.py` | sql_gen_node：metric_templates 非空时使用新 prompt；空时用老 prompt；无 mock 兜底 |

### 7.2 集成测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_chat_sse.py` | SSE 端到端：mock LLM 全套；5 节点 step 顺序；metric 选中后 step trace 包含 metric 信息；code=4001 错误流 |
| `tests/test_metric_api.py` | API 6 路由：B_BI_METRIC_VIEW / B_BI_METRIC_MANAGE 权限；Sqid 编码；空列表/分页 |
| `tests/test_chat_with_no_llm.py` | 不配置 LLM 时 chat send 返 4001；前端 SSE 收到 error event |

### 7.3 E2E 烟测

`scripts/bi_e2e_smoke.py` 扩展：
```
1. 登录
2. POST /business/bi/metrics/search 验证预置 5 个 metric
3. POST /business/bi/metrics 创建测试 metric
4. PATCH /business/bi/metrics/{id} 验证更新
5. POST /business/bi/metrics/{id}/test 验证模板测试
6. POST /business/bi/chat/sessions 创建会话
7. POST /business/bi/chat/sessions/{id}/messages 问"本月销售额"
8. 验证 SSE 流中：intent step 包含 metric_ids
9. 验证最终落库的 agent_steps_json[0].output.metric_ids 非空
10. DELETE /business/bi/metrics/{id} 验证删除
```

### 7.4 回归

- 现有 `tests/test_business_slots.py` 全过
- 现有 `tests/test_chat.py`（如存在）调整 mock LLM 行为
- 旧 demo 电商数据下，问"本月各产品线销售额排名"必须仍能跑通

### 7.5 手动验证清单

- [ ] `/bi/metrics` 列表显示 5 个预置 metric
- [ ] 新建 metric → 在 `/bi/chat` 问对应问题 → SQL 中包含 `SUM(...amount) WHERE status='paid'`
- [ ] 关闭 LLM provider → `/bi/chat` 问问题 → 弹窗提示"请先在 /bi/models 配置"
- [ ] 删除全部 metric → 问"销售额" → 仍能跑（降级为 table 路径，老 SQL 生成）
- [ ] 多 metric 问题"销售概况" → 选 2 个 metric → SQL 同时包含 2 个表达式
- [ ] 错误 SQL 模板（`DROP TABLE`）→ /test 返回 whitelist_denied

---

## 8. 数据迁移

### 8.1 已有 `bi_metric` 表

旧表无 `datasource_id` 字段，需要：

1. 改 model 加 `datasource_id: int` (FK, on_delete=CASCADE, db_index=True)
2. `just mm` 生成迁移（add column bi_metric.datasource_id + FK + index）
3. 启动时若发现旧 metric 的 `datasource_id IS NULL`：自动用默认 datasource 回填（demo 场景）

### 8.2 启动顺序

```
init() 顺序保证：
1. 默认租户
2. 默认数据源 (id 固定)
3. 预置 metric（带 datasource_id=默认数据源.id）
```

幂等：用 `_safe_update_or_create(Metric, {"name", "datasource_id"}, {...})`，重启不重复创建。

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM 返回非合法 JSON | `try/except json.JSONDecodeError` → fallback `intent=table, metrics=[]` + warn log + step trace 记录 `parse_failed` |
| LLM 把 id 当 string 返回 | `int(...)` 强转 + id 必须在 valid set |
| `metric.sql_template` 语法错误 | `/test` 端点 + 管理员界面提示 |
| 模板引用的表在 datasource 中不存在 | `/test` 用 sandbox 验证；`sql_gen_node` 依赖 schema_text 上下文 |
| 删 mock 后本地无 key 起不来 | warn 而非 panic，chat 端返 4001 引导配置 |
| 多 metric 拼接时字段冲突 | prompt 强调"原样出现一次"；`sql_validate` 失败 → explain 报错 |
| `bi_metric` 表已有数据加 FK 失败 | 迁移前 SQL 回填 NULL → 默认 datasource_id |
| 前端 i18n route_name 错位 | 历史坑：必须 `bi_metrics`（无连字符），后端先于前端定 |

---

## 10. 实施顺序

```
Step 1: Metric 模型加 datasource_id + 迁移
Step 2: service/metric.py + api/metric.py（CRUD + /test，先不接 SSE）
Step 3: 前端 bi-metric.ts + bi.d.ts 类型
Step 4: 前端 views/bi/metrics/index.vue CRUD 页面
Step 5: 路由注册 + i18n + 按钮权限
Step 6: llm/router.py 去掉 mock 默认 + NoLLMProviderError
Step 7: intent_node 改 LLM + prompt
Step 8: sql_gen_node 加 metric 模板注入分支
Step 9: explain_node 去掉 mock 兜底
Step 10: chat.py SSE 增加错误码 + 前端 onError 跳转
跨步骤：
- init_data.py 预置 5 个 metric + 新菜单/按钮
- 单元测试 + 集成测试
- 回归 + just check
```

每步独立提交、独立验证。

---

## 11. 提交门禁

- `just check` 全过
- `app/cli/commands/check_boundaries.py` 通过（依赖方向 core ← system ← bi 不变）
- 前端 `vue-tsc` 通过
- 至少 1 个 E2E 烟测脚本全过
- 手动验证清单（7.5）所有勾完成

---

## 12. 文档更新

- `docs/agentic-bi/SPEC.md` 追加 "Phase 1.x: 指标模板 + LLM 意图" 章节
- `web/CHANGELOG.zh_CN.md` 写改动条目
- `CHANGELOG.md` 同步
- `docs/standard/backend.md`（如有）补充新业务错误码段位说明
