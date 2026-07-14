# pyright: reportIncompatibleVariableOverride=false
"""AgenticBI 数据模型 — 元数据子模块。

5 张表：
- Tenant
- Datasource
- Table
- Column
- Relation
- Synonym
"""

from __future__ import annotations

from enum import Enum

from tortoise import fields

from app.core.base_model import AuditMixin, BaseModel, StatusType
from app.core.fields import DelimitedListField


class Tenant(BaseModel, AuditMixin):
    """租户。

    AgenticBI 的多租户隔离单元。每个 Datasource / ChatSession / QueryExecution
    都通过 ``tenant_id`` 关联到本表。

    注：当前系统表（``users`` / ``roles``）无租户字段。Phase 1 演示场景下
    ``tenant_id`` 主要用于数据范围过滤，不强制要求每个系统用户绑定租户。
    """

    id = fields.IntField(primary_key=True, description="租户ID")
    code = fields.CharField(max_length=64, unique=True, description="租户编码（如 tenant_a）")
    name = fields.CharField(max_length=100, description="租户名")
    description = fields.CharField(max_length=500, null=True, blank=True, description="租户描述")
    is_active = fields.BooleanField(default=True, description="是否启用")
    default_datasource_id: int | None
    default_datasource: fields.ForeignKeyNullableRelation["Datasource"] = fields.ForeignKeyField(
        "app_system.Datasource",
        null=True,
        on_delete=fields.SET_NULL,
        related_name="default_for_tenants",
        description="默认数据源",
    )
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "bi_tenant"
        table_description = "BI 租户表"


class DatasourceType(str, Enum):
    """数据源类型。"""

    postgresql = "postgresql"
    mysql = "mysql"
    clickhouse = "clickhouse"
    trino = "trino"
    sqlite = "sqlite"


class Datasource(BaseModel, AuditMixin):
    """数据源。

    业务名 + 类型 + 连接信息。``password_enc`` 用 Fernet 加密（见 ``app.utils.encrypt``）。
    """

    id = fields.IntField(primary_key=True, description="数据源ID")
    name = fields.CharField(max_length=100, unique=True, description="数据源业务名")
    type = fields.CharEnumField(enum_type=DatasourceType, db_index=True, description="数据源类型")
    host = fields.CharField(max_length=255, null=True, blank=True, description="主机（SQLite 可为空）")
    port = fields.IntField(null=True, blank=True, description="端口")
    database = fields.CharField(max_length=200, description="库名 / SQLite 文件名 / 文件路径")
    username = fields.CharField(max_length=100, null=True, blank=True, description="用户名")
    password_enc = fields.CharField(max_length=1024, null=True, blank=True, description="Fernet 加密的密码")
    tenant_id = fields.IntField(db_index=True, description="所属租户")
    is_default = fields.BooleanField(default=False, description="租户默认数据源")
    extra = fields.JSONField(null=True, description="驱动特定配置（如 sslmode / 字符集）")
    last_synced_at = fields.DatetimeField(null=True, description="最近一次元数据同步时间")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, db_index=True, description="状态")
    remark = fields.CharField(max_length=500, null=True, blank=True, description="备注")

    class Meta:
        table = "bi_datasource"
        table_description = "BI 数据源表"


class BiTable(BaseModel, AuditMixin):
    """数据源中的物理表 / 视图。

    一个 Datasource 下可有多个 Table；Table 包含若干 Column。
    """

    id = fields.IntField(primary_key=True, description="表ID")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[Datasource] = fields.ForeignKeyField(
        "app_system.Datasource",
        related_name="tables",
        on_delete=fields.CASCADE,
        description="所属数据源",
    )
    columns: fields.ReverseRelation["BiColumn"]
    schema_name = fields.CharField(max_length=100, null=True, blank=True, description="schema（PG/CH 多 schema）")
    name = fields.CharField(max_length=200, db_index=True, description="表名")
    description = fields.CharField(max_length=500, null=True, blank=True, description="业务描述（供 LLM 检索）")
    tags = DelimitedListField(max_length=500, null=True, blank=True, description="业务标签")
    version = fields.IntField(default=1, description="同步次数 / 版本号")
    last_synced_at = fields.DatetimeField(null=True, description="本表最近一次元数据同步时间")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "bi_table"
        table_description = "BI 数据源表清单"
        unique_together = (("datasource_id", "schema_name", "name"),)


class BiColumn(BaseModel, AuditMixin):
    """数据源表 / 视图的列。

    同步时由 ``metadata.sync`` 写入。LLM 生成 SQL 时只参考本表已登记的列。
    """

    id = fields.IntField(primary_key=True, description="列ID")
    table_id: int
    table: fields.ForeignKeyRelation[BiTable] = fields.ForeignKeyField(
        "app_system.BiTable",
        related_name="columns",
        on_delete=fields.CASCADE,
        description="所属表",
    )
    name = fields.CharField(max_length=200, db_index=True, description="列名")
    data_type = fields.CharField(max_length=100, description="物理数据类型（如 varchar(64) / int8）")
    nullable = fields.BooleanField(default=True, description="是否可空")
    description = fields.CharField(max_length=500, null=True, blank=True, description="业务描述（供 LLM 检索）")
    is_dimension = fields.BooleanField(default=False, db_index=True, description="是否维度（可 group by）")
    is_metric = fields.BooleanField(default=False, db_index=True, description="是否度量（可聚合）")
    enum_values = fields.JSONField(null=True, description="枚举值列表（若适用）")
    sample_values = fields.JSONField(null=True, description="采样值（最多 10 个）")
    ordinal = fields.IntField(default=0, description="列在表中的位置")

    class Meta:
        table = "bi_column"
        table_description = "BI 数据源列清单"
        unique_together = (("table_id", "name"),)


class JoinType(str, Enum):
    """自动发现的连接类型。"""

    inner = "inner"
    left = "left"
    right = "right"
    full = "full"


class Relation(BaseModel, AuditMixin):
    """表与表之间的连接关系（自动发现或人工编辑）。

    ``confidence`` 0-1，1 表示手工登记，< 1 表示自动推断。
    """

    id = fields.IntField(primary_key=True, description="关系ID")
    src_table_id: int
    src_table: fields.ForeignKeyRelation[BiTable] = fields.ForeignKeyField(
        "app_system.BiTable",
        related_name="outgoing_relations",
        on_delete=fields.CASCADE,
        description="源表",
    )
    src_column = fields.CharField(max_length=200, description="源列")
    dst_table_id: int
    dst_table: fields.ForeignKeyRelation[BiTable] = fields.ForeignKeyField(
        "app_system.BiTable",
        related_name="incoming_relations",
        on_delete=fields.CASCADE,
        description="目标表",
    )
    dst_column = fields.CharField(max_length=200, description="目标列")
    join_type = fields.CharEnumField(enum_type=JoinType, default=JoinType.inner, description="连接类型")
    confidence = fields.FloatField(default=1.0, description="置信度 0-1，1=人工登记")

    class Meta:
        table = "bi_relation"
        table_description = "BI 表关系"


class SynonymKind(str, Enum):
    """同义词类型。"""

    column = "column"
    table = "table"
    metric = "metric"
    concept = "concept"


class Synonym(BaseModel, AuditMixin):
    """业务用语与库内真实列 / 表 / 指标 / 概念的映射。

    用于 LLM prompt 拼装时把用户问题里的业务术语翻译成准确字段名。
    """

    id = fields.IntField(primary_key=True, description="同义词ID")
    term = fields.CharField(max_length=200, db_index=True, description="业务用语")
    mapped_term = fields.CharField(max_length=200, description="映射到的真实名（列名 / 表名）")
    kind = fields.CharEnumField(enum_type=SynonymKind, default=SynonymKind.column, db_index=True, description="类型")
    datasource_id: int | None
    datasource: fields.ForeignKeyNullableRelation[Datasource] = fields.ForeignKeyField(
        "app_system.Datasource",
        null=True,
        blank=True,
        on_delete=fields.CASCADE,
        related_name="synonyms",
        description="数据源（空表示全局）",
    )
    description = fields.CharField(max_length=500, null=True, blank=True, description="补充说明")

    class Meta:
        table = "bi_synonym"
        table_description = "BI 业务同义词"
        unique_together = (("datasource_id", "term", "kind"),)


__all__ = [
    "Tenant",
    "DatasourceType",
    "Datasource",
    "BiTable",
    "BiColumn",
    "JoinType",
    "Relation",
    "SynonymKind",
    "Synonym",
]
