"""SQL 生成节点 — 注入 Schema + 替换占位符 + LLM 生成 SQL。"""

from __future__ import annotations

import re
import time
from typing import Any

from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.models import BiColumn, BiDatasource, BiTable

# {xxx} 占位符正则
_PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")

# 各方言函数差异提示（LLM 训练语料偏 MySQL，容易踩坑）
# 只列出常见差异，避免 prompt 过长
_DIALECT_HINTS: dict[str, str] = {
    "sqlite": """【SQLite 方言注意事项】（务必遵守，否则会运行时报错）：
- 当前日期: date('now') 或 CURRENT_DATE（不要用 CURDATE() / NOW() / GETDATE()）
- 当前时间: datetime('now') 或 CURRENT_TIMESTAMP
- 日期格式化: strftime('%Y-%m-%d', column)（不要用 DATE_FORMAT()）
- 日期差: julianday(a) - julianday(b)（不要用 DATEDIFF()）
- 字符串拼接: a || b（不要用 CONCAT()）
- 取子串: substr(x, start, len)（不要用 SUBSTRING()）""",
    "mysql": """【MySQL 方言注意事项】：
- 当前日期: CURDATE() 或 CURRENT_DATE
- 日期格式化: DATE_FORMAT(x, '%Y-%m-%d')
- 字符串拼接: CONCAT(a, b)""",
    "postgresql": """【PostgreSQL 方言注意事项】：
- 当前日期: CURRENT_DATE 或 CURRENT_TIMESTAMP
- 日期格式化: to_char(x, 'YYYY-MM-DD')
- 字符串拼接: a || b 或 CONCAT(a, b)""",
    "clickhouse": """【ClickHouse 方言注意事项】：
- 当前日期: today() 或 now()
- 日期格式化: formatDateTime(x, '%Y-%m-%d')
- 字符串拼接: concat(a, b)""",
    "trino": """【Trino 方言注意事项】：
- 当前日期: current_date 或 now()
- 日期格式化: format_datetime(x, 'yyyy-MM-dd')
- 字符串拼接: concat(a, b)""",
}


def _get_dialect_hint(db_type: str) -> str:
    """根据数据库类型返回方言提示文本。"""
    return _DIALECT_HINTS.get(db_type.lower(), "")


async def _resolve_placeholders(sql_template: str, tables: list[BiTable]) -> str:
    """替换 {xxx} 占位符为真实表名。

    项目历史教训：metric.sql_template 含 {order} 等占位符，LLM 会字面量复制，
    导致 sqlglot parse_failed。必须在调用 LLM 前替换。

    匹配策略（按优先级）：
    1. 精确匹配 BiTable.name
    2. 复数匹配（如 {order} -> orders 表）
    3. 子串匹配（如 {order_item} -> order_items 表）
    """
    if not sql_template or not tables:
        return sql_template

    # 构建表名映射
    table_names = {t.name.lower(): t.name for t in tables}

    def replace_match(m: re.Match) -> str:
        placeholder = m.group(1).lower()
        # 1. 精确匹配
        if placeholder in table_names:
            return table_names[placeholder]
        # 2. 复数匹配（order -> orders）
        plural = placeholder + "s"
        if plural in table_names:
            return table_names[plural]
        # 3. 单数匹配（orders -> order，如果 {orders} 但表名是 order）
        if placeholder.endswith("s") and placeholder[:-1] in table_names:
            return table_names[placeholder[:-1]]
        # 4. 子串匹配
        for name in table_names:
            if placeholder in name or name in placeholder:
                return table_names[name]
        # 未匹配，返回原占位符（后续校验会拒绝）
        return m.group(0)

    return _PLACEHOLDER_PATTERN.sub(replace_match, sql_template)


async def _build_schema_text(tables: list[BiTable]) -> str:
    """构建 Schema 文本（供 LLM 参考）。

    项目历史教训：BiTable 为空时返回提示文本。
    """
    if not tables:
        return "(empty schema, please sync metadata first)"

    lines = []
    for table in tables[:50]:  # 限制 50 张表（覆盖大多数业务库全表）
        # 获取列信息
        columns = await BiColumn.filter(table_id=table.id).limit(50)
        col_lines = []
        for col in columns:
            pk = "PK" if col.is_primary else ""
            nullable = "" if col.is_nullable else "NOT NULL"
            col_lines.append(f"  {col.name} {col.data_type} {pk} {nullable}".strip())

        lines.append(f"表: {table.name}")
        if table.comment:
            lines.append(f"注释: {table.comment}")
        if table.row_count:
            lines.append(f"行数: ~{table.row_count}")
        lines.append("字段:")
        lines.extend(col_lines)
        lines.append("")

    return "\n".join(lines)


async def sql_gen_node(state: AgentState) -> dict[str, Any]:
    """SQL 生成节点。

    支持**自纠错重试**：当 state 中存在 ``validate_error`` 时，把上次生成的
    SQL 和校验错误信息加入 prompt，引导 LLM 修正。
    """
    start = time.time()
    question = state.get("question", "")
    intent_type = state.get("intent_type", "query")

    # 重试上下文
    validate_error = state.get("validate_error")
    previous_sql = state.get("sql_text", "")
    retry_count = state.get("retry_count", 0)
    is_retry = bool(validate_error) and retry_count > 0

    # 获取表元数据 + 数据源方言
    datasource_id = state.get("datasource_id")
    datasource = None
    tables: list[BiTable] = []
    if datasource_id:
        datasource = await BiDatasource.filter(id=datasource_id).first()
        if datasource:
            tables = await BiTable.filter(datasource_id=datasource_id).limit(50)
    if not datasource:
        # 取第一个启用的数据源
        datasource = await BiDatasource.filter(status_type="1").first()  # StatusType.enable.value = "1"
        if datasource:
            tables = await BiTable.filter(datasource_id=datasource.id).limit(50)

    db_type = datasource.db_type if datasource else "sqlite"
    dialect_hint = _get_dialect_hint(db_type)

    schema_text = await _build_schema_text(tables)

    sql_text = ""
    token_usage = {}

    try:
        from app.business.bi.llm.router import BiLLMRouter

        provider = await BiLLMRouter.get_default_from_db()

        # 重试时追加纠错提示
        retry_hint = ""
        if is_retry:
            retry_hint = f"""

⚠️ 上次生成的 SQL 校验失败，请根据以下反馈修正：

上次 SQL:
{previous_sql}

校验错误:
{validate_error}

请仔细检查错误信息，修正后重新生成 SQL。"""

        prompt = f"""你是一个 SQL 专家。根据用户问题生成 {intent_type} 类型的 SQL。

目标数据库方言: {db_type}
{dialect_hint}

数据库 Schema（只能使用这些表，不要查询任何系统字典表）:
{schema_text}

用户问题: {question}

要求:
1. 只生成 SELECT 语句（禁止 INSERT/UPDATE/DELETE/DROP）
2. 只能使用上方 Schema 中列出的真实业务表名（不要用 {{xxx}} 占位符）
3. 禁止查询系统字典表/视图，包括但不限于：information_schema.*、sqlite_master、pg_catalog.*、sys.*、system.tables、SHOW TABLES、DESC 表名
   如果用户问"有哪些表/字段"等元数据问题，请直接从上方 Schema 列出的业务表中选取合适的表做 SELECT 查询来展示数据
4. 必须使用与目标数据库方言兼容的函数和语法（参考上方方言注意事项）
5. 适当添加 LIMIT
6. 只返回 SQL 语句，不要解释
{retry_hint}

SQL:"""

        result = await provider.chat(prompt, temperature=0.1)
        sql_text = result.content.strip()
        token_usage = result.token_usage

        # 防御性二次占位符替换
        if tables:
            sql_text = await _resolve_placeholders(sql_text, tables)

        # 提取 SQL（去掉 markdown 代码块）
        if "```" in sql_text:
            lines = sql_text.split("\n")
            sql_lines = [line for line in lines if not line.strip().startswith("```")]
            sql_text = "\n".join(sql_lines).strip()

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        step = {
            "node": "sql_gen",
            "status": "failed",
            "data": {},
            "elapsed_ms": elapsed_ms,
            "error": str(e),
        }
        return {
            "sql_text": "",
            "error": str(e),
            "steps": state.get("steps", []) + [step],
        }

    elapsed_ms = int((time.time() - start) * 1000)
    step: StepTrace = {
        "node": "sql_gen",
        "status": "success",
        "data": {"sql_text": sql_text},
        "elapsed_ms": elapsed_ms,
        "error": None,
    }

    # 合并 token_usage（防御性：value 非 int/float 时用新值覆盖）
    prev_usage = state.get("token_usage", {})
    merged_usage = {}
    for k in set(list(prev_usage.keys()) + list(token_usage.keys())):
        pv = prev_usage.get(k, 0)
        nv = token_usage.get(k, 0)
        if isinstance(pv, int | float) and isinstance(nv, int | float):
            merged_usage[k] = pv + nv
        else:
            merged_usage[k] = nv

    return {
        "sql_text": sql_text,
        "tables": [{"id": t.id, "name": t.name} for t in tables],
        "steps": state.get("steps", []) + [step],
        "token_usage": merged_usage,
    }
