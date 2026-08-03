# pyright: reportIncompatibleVariableOverride=false
"""BiDashboard schemas — 仪表盘的请求/响应 Schema。

约定（与 bi 模块其他 schema 一致）：
- SQID 参数在 request schema 中定义为 ``str`` 类型，API/service 层用 ``decode_id()`` 解码
- Update schema 用 ``make_optional`` 生成
- 分页 schema 继承 ``PageQueryBase``
- 响应不返回 ``sql_text``（仪表盘卡片不展示 SQL），仅承载图表元信息 + 快照
"""

from datetime import datetime

from pydantic import Field

from app.utils import PageQueryBase, SchemaBase, make_optional

# ============================================================
# layout 子结构
# ============================================================


class DashboardItemSchema(SchemaBase):
    """layout.items[] 单元素。

    ``chartId`` 是 BiChart 的 SQID 编码字符串（前端透传，后端 ``decode_id`` 后查 BiChart）。
    """

    chartId: str = Field(title="BiChart 的 SQID 编码")
    x: int = Field(ge=0, le=11, title="列位置 0-11")
    y: int = Field(ge=0, title="行位置 0-N")
    w: int = Field(ge=1, le=12, title="宽度 1-12")
    h: int = Field(ge=1, le=6, title="高度 1-6")


class DashboardLayoutSchema(SchemaBase):
    """layout JSON 结构。"""

    items: list[DashboardItemSchema] = Field(default_factory=list, title="图表项列表")


# ============================================================
# CRUD
# ============================================================


class BiDashboardCreateSchema(SchemaBase):
    """创建仪表盘请求。"""

    name: str = Field(max_length=100, title="仪表盘名称")
    description: str | None = Field(None, title="说明")
    layout: DashboardLayoutSchema = Field(default_factory=DashboardLayoutSchema, title="布局")


BiDashboardUpdateSchema = make_optional(BiDashboardCreateSchema, "BiDashboardUpdateSchema")


class BiDashboardSearchSchema(PageQueryBase):
    """仪表盘分页查询。"""

    name: str | None = Field(None, title="按名称模糊搜索")


# ============================================================
# 响应
# ============================================================


class BiChartMetaSchema(SchemaBase):
    """图表元信息（刷新/预览响应中携带，即使刷新失败也能展示卡片标题）。"""

    name: str = Field(title="图表标题")
    chart_type: str = Field(title="图表类型")
    x_col: str | None = Field(None, title="X 轴字段")
    y_col: str | None = Field(None, title="Y 轴字段")


class BiDashboardRefreshItemSchema(SchemaBase):
    """刷新响应中的单项结果。

    ``status``:
    - ``success`` —— 刷新成功，返回 ``resultSnapshot`` + ``chartMeta`` + ``snapshotAt``
    - ``failed`` —— 刷新失败，返回 ``errorMessage`` + ``chartMeta``，**不返回** ``resultSnapshot``
    - ``deleted`` —— 引用的 BiChart 已软删，``chartMeta`` 为 None
    """

    chartId: str = Field(title="BiChart 的 SQID 编码")
    status: str = Field(title="状态：success/failed/deleted")
    result_snapshot: dict | None = Field(None, title="结果快照（仅 success 有）")
    chart_meta: BiChartMetaSchema | None = Field(None, title="图表元信息（deleted 时为 None）")
    error_message: str | None = Field(None, title="错误信息（仅 failed 有）")
    snapshot_at: datetime | None = Field(None, title="快照时间（仅 success 有）")


class BiDashboardRefreshResultSchema(SchemaBase):
    """刷新响应聚合。"""

    items: list[BiDashboardRefreshItemSchema] = Field(default_factory=list, title="各图表刷新结果")
    total_elapsed_ms: int = Field(0, title="总耗时（毫秒）")


class BiDashboardPreviewItemSchema(SchemaBase):
    """预览响应中的单项（不刷新，用 BiChart 已有快照）。"""

    chartId: str = Field(title="BiChart 的 SQID 编码")
    chart_meta: BiChartMetaSchema | None = Field(None, title="图表元信息（deleted 时为 None）")
    result_snapshot: dict | None = Field(None, title="BiChart 已有快照（不重跑）")
    status: str | None = Field(None, title="状态：deleted（图表已删时）")


class BiDashboardPreviewSchema(SchemaBase):
    """预览响应（编辑模式用，不刷新）。"""

    id: str = Field(title="仪表盘 ID（sqid）")
    name: str = Field(title="仪表盘名称")
    description: str | None = Field(None, title="说明")
    layout: dict = Field(title="布局")
    items: list[BiDashboardPreviewItemSchema] = Field(default_factory=list, title="各图表预览结果")
