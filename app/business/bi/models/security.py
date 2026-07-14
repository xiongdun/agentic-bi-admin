# pyright: reportIncompatibleVariableOverride=false
"""AgenticBI 数据模型 — 权限与审计子模块。

4 张表：
- DatasourceGrant
- ColumnMasking
- AuditLog
"""

from __future__ import annotations

from enum import Enum

from tortoise import fields

from app.business.bi.models.metadata import BiColumn, Datasource
from app.core.base_model import AuditMixin, BaseModel


class DataScopeType(str, Enum):
    """数据源授权范围（与全局 DataScopeType 复用为子集）。

    - ``all`` — 全部数据
    - ``scope`` — 仅当前租户
    - ``self`` — 仅创建者
    """

    all = "all"
    scope = "scope"
    self_ = "self"


class DatasourceGrant(BaseModel, AuditMixin):
    """数据源授权：把数据源按角色代码授权给一组用户。

    ``allow_write`` 默认 False（只读）；只有显式开启的授权才允许执行写 SQL。
    """

    id = fields.IntField(primary_key=True, description="授权ID")
    role_code = fields.CharField(max_length=64, db_index=True, description="角色编码")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[Datasource] = fields.ForeignKeyField(
        "app_system.Datasource",
        related_name="grants",
        on_delete=fields.CASCADE,
        description="被授权的数据源",
    )
    scope = fields.CharEnumField(enum_type=DataScopeType, default=DataScopeType.all, description="数据范围")
    allow_export = fields.BooleanField(default=False, description="是否允许导出")
    allow_write = fields.BooleanField(default=False, description="是否允许写 SQL（默认只读）")

    class Meta:
        table = "bi_datasource_grant"
        table_description = "BI 数据源授权"
        unique_together = (("role_code", "datasource_id"),)


class MaskType(str, Enum):
    """列脱敏策略。"""

    full = "full"  # 全部掩码
    partial = "partial"  # 中间掩码（首 1 尾 1）
    email = "email"
    phone = "phone"
    id_card = "id_card"
    bank_card = "bank_card"
    hash = "hash"


class ColumnMasking(BaseModel, AuditMixin):
    """列脱敏策略：某个角色看某列时按规则脱敏。"""

    id = fields.IntField(primary_key=True, description="脱敏策略ID")
    column_id: int
    column: fields.ForeignKeyRelation[BiColumn] = fields.ForeignKeyField(
        "app_system.BiColumn",
        related_name="maskings",
        on_delete=fields.CASCADE,
        description="被脱敏的列",
    )
    role_code = fields.CharField(max_length=64, db_index=True, description="角色编码")
    mask_type = fields.CharEnumField(enum_type=MaskType, description="脱敏类型")

    class Meta:
        table = "bi_column_masking"
        table_description = "BI 列脱敏"
        unique_together = (("column_id", "role_code"),)


class AuditLog(BaseModel):
    """审计日志。

    不复用 AuditMixin（避免和日志表字段冲突）；自管 created_at。
    """

    id = fields.BigIntField(primary_key=True, description="日志ID")
    user_id = fields.IntField(db_index=True, description="操作用户")
    tenant_id = fields.IntField(db_index=True, description="租户")
    action = fields.CharField(max_length=64, db_index=True, description="操作类型：query / export / metadata_update 等")
    datasource_id: int | None
    datasource: fields.ForeignKeyNullableRelation[Datasource] = fields.ForeignKeyField(
        "app_system.Datasource",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="audit_logs",
        description="相关数据源",
    )
    sql_hash = fields.CharField(max_length=64, null=True, blank=True, db_index=True, description="SQL 哈希")
    row_count = fields.IntField(null=True, description="受影响行数")
    cost_ms = fields.IntField(null=True, description="耗时（毫秒）")
    ip = fields.CharField(max_length=64, null=True, blank=True, description="客户端 IP")
    user_agent = fields.CharField(max_length=500, null=True, blank=True, description="UA")
    detail = fields.JSONField(null=True, description="附加结构化信息")
    created_at = fields.DatetimeField(auto_now_add=True, db_index=True, description="创建时间")

    class Meta:
        table = "bi_audit_log"
        table_description = "BI 审计日志"


__all__ = ["DataScopeType", "DatasourceGrant", "MaskType", "ColumnMasking", "AuditLog"]
