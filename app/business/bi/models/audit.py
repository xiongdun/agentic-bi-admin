"""AgenticBI 数据模型 — 审计 SQL 文本存储。

1 张表：
- BiAuditSql（与 AuditLog 1:1，独立存储避免列表查询加载大 SQL 文本）
"""

from __future__ import annotations

from tortoise import fields

from app.core.base_model import BaseModel


class BiAuditSql(BaseModel):
    """原始 SQL 文本存储（与 AuditLog 1:1）。

    独立表避免审计列表查询加载大 SQL 文本；
    保留期清理时按 AuditLog.created_at 级联（on_delete=CASCADE）。
    """

    id = fields.BigIntField(primary_key=True, description="ID")
    audit_log_id: int
    audit_log: fields.OneToOneRelation = fields.OneToOneField(
        "app_system.AuditLog",
        related_name="audit_sql",
        on_delete=fields.CASCADE,
        description="关联审计日志",
    )
    sql_text = fields.TextField(description="原始 SQL 文本")
    sql_hash = fields.CharField(max_length=64, db_index=True, description="SQL 哈希")

    class Meta:
        table = "bi_audit_sql"
        table_description = "BI 审计原始 SQL"


__all__ = ["BiAuditSql"]
