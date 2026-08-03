from tortoise import migrations
from tortoise.migrations import operations as ops
from orjson import loads
from tortoise.fields.data import JSON_DUMPS
from tortoise import fields
from tortoise.indexes import Index


class Migration(migrations.Migration):
    """只创建 biz_bi_dashboard 表。

    手写迁移：避免 aerich 误判其他表 id 字段需要重建
    （patch_sqlite_comments 修改 DDL 注释导致的状态漂移），
    与 0003_add_bi_chart / 0004_add_bi_query_task 同样的处理方式。
    """

    dependencies = [('app_system', '0004_add_bi_query_task')]

    initial = False

    operations = [
        ops.CreateModel(
            name='BiDashboard',
            fields=[
                ('created_by', fields.CharField(null=True, description='创建人', max_length=64)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_by', fields.CharField(null=True, description='更新人', max_length=64)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('deleted_at', fields.DatetimeField(null=True, description='软删除时间，NULL表示未删除', auto_now=False, auto_now_add=False)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True, description='主键ID')),
                ('name', fields.CharField(description='仪表盘名称', max_length=100)),
                ('description', fields.TextField(null=True, description='说明', unique=False)),
                ('layout', fields.JSONField(default={'items': []}, description='布局：{items: [{chartId, x, y, w, h}]}', encoder=JSON_DUMPS, decoder=loads)),
                ('tenant_id', fields.IntField(default=0, description='租户ID（行级 data_scope 作用域，存 user.id）')),
            ],
            options={'table': 'biz_bi_dashboard', 'app': 'app_system', 'indexes': [Index(fields=['tenant_id', 'created_at'])], 'pk_attr': 'id', 'table_description': '仪表盘：把多个 BiChart 组装成 12 列栅格布局。'},
            bases=['BaseModel', 'AuditMixin', 'SoftDeleteMixin'],
        ),
    ]
