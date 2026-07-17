"""Agent 提示词模板。"""

SYSTEM_BASE = """你是一个严谨的 SQL 生成助手。
- 只能基于提供的 schema 生成 SELECT / WITH 语句
- 输出必须用 ```sql ... ``` 包裹
- 不要使用危险函数（load_file / pg_read_file / xp_cmdshell 等）
- 租户隔离由系统自动注入，不要在 SQL 中手写 WHERE tenant_id
- 时间相关问题优先用 ``strftime('%Y-%m', now)`` 或 DATE() 这类方言函数
"""


SCHEMA_HEADER = """可用数据源 schema（{dialect}）：

{schema_text}
"""


INTENT_PROMPT = """判断用户问题属于以下哪类：
- table：标准事实表查询（销售额、订单数、用户数等）
- metric：业务指标查询（复用 Metric 模板的）
- freeform：探索性问题（"哪类商品卖得最好" 等开放式问题）

用户问题：{question}

只返回一个单词：table / metric / freeform
"""


SQL_GEN_PROMPT = """根据以下 schema 和用户问题，生成一条 SQL：

{schema_header}

用户问题：{question}

要求：
- 必返回 ```sql ... ``` 块
- 时间范围用 ``strftime('%Y-%m', created_at)`` 或 ``created_at >= 'YYYY-MM-DD'``
- GROUP BY / ORDER BY 用业务列（产品线、月份等）
- LIMIT 100 防止返回太多行
"""


EXPLAIN_PROMPT = """你是 SQL 解释助手。基于以下信息给业务用户讲清楚这条 SQL 在做什么。

用户问题：{question}

生成的 SQL：
```sql
{final_sql}
```

执行结果：{row_count} 行, 耗时 {cost_ms}ms

要求：
- 用 1-2 句中文讲清楚 SQL 的执行步骤（哪些表、哪些过滤、怎么聚合）
- 给出 2-3 句结果解读（数字意味着什么 / 业务上值得注意的点）
- 不要再次输出 SQL 或重复数字
"""


# ---- Intent Router (Phase 1.x) ----
# 升级后的 intent 节点：LLM 必走，一次返回 {intent, metrics, reasoning}。
# sql_gen 节点根据 metrics 是否非空切换 prompt（强约束 vs 自由生成）。

INTENT_ROUTER_SYSTEM = """你是数据分析意图路由器，输出严格 JSON。"""

INTENT_ROUTER_USER = """可用数据源方言: {dialect}

Schema:
{schema_text}

可用指标（{metric_count} 个）:
{metric_list}

用户问题: {question}

请只返回 JSON（不要任何 markdown / 代码块 / 注释）:
{{
  "intent": "metric" | "table" | "freeform",
  "metrics": [{{"id": <int>, "reason": "<20字内原因>"}}],
  "reasoning": "<50字内整体判断>"
}}

规则：
1. 能用 1+ 指标直接回答 → intent="metric"，metrics 列出 id
2. 聚合 / 排名 / 分桶 / 总数 → intent="table"
3. 开放探索 / 选品类 → intent="freeform"
4. 问候 / 与数据无关 → intent="freeform", metrics=[]
5. metrics 可为 []"""


# ---- SQL Gen with Metric Constraint ----
# 当 intent 节点选出了 1+ metric,sql_gen 必须把模板表达式原样写进最终 SQL。

SQL_GEN_WITH_METRIC_USER = """{schema_header}

用户问题: {question}

【必须使用】的指标模板（{metric_count} 个，必须在最终 SQL 中以原表达式出现）:
{metric_templates}

要求：
- 必返回 ```sql ... ``` 块
- 每个【必须使用】模板中的表达式必须原样出现在 SQL 中（可包在子查询 / CTE / SELECT 里）
- 时间用 strftime 或 >= 'YYYY-MM-DD'
- LIMIT 100"""


__all__ = [
    "SYSTEM_BASE",
    "SCHEMA_HEADER",
    "INTENT_PROMPT",
    "SQL_GEN_PROMPT",
    "EXPLAIN_PROMPT",
    "INTENT_ROUTER_SYSTEM",
    "INTENT_ROUTER_USER",
    "SQL_GEN_WITH_METRIC_USER",
]
