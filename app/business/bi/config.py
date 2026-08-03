"""
BI 业务模块配置。

从 .env 文件加载 BI 模块专属配置。使用方式：

    from app.business.bi.config import BIZ_SETTINGS

    key = BIZ_SETTINGS.BI_CRYPTO_KEY

在 .env 中覆盖：

    BI_CRYPTO_KEY=...
    BI_QUERY_MAX_ROWS=10000
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class BusinessSettings(BaseSettings):
    """BI 模块配置（从 .env 加载）。"""

    # Fernet 加密密钥，用于加密数据源密码 / LLM API Key
    # 生成命令: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    BI_CRYPTO_KEY: str = ""

    # 查询配额
    BI_QUERY_MAX_ROWS: int = 10000
    BI_QUERY_TIMEOUT: int = 30
    BI_QUERY_BREAKER_THRESHOLD: int = 10

    # 元数据采集
    BI_METADATA_SAMPLE_ROWS: int = 5
    BI_METADATA_BATCH_SIZE: int = 100

    # 图表保存
    BI_CHART_SNAPSHOT_MAX_ROWS: int = 1000

    # 异步大查询
    # 总开关：False 时 /sql/async-run 与软超时转异步都直接拒绝
    BI_ASYNC_QUERY_ENABLED: bool = True
    # 异步查询行数上限（远大于同步的 1 万）
    BI_ASYNC_QUERY_MAX_ROWS: int = 1_000_000
    # 异步查询执行超时上限（秒，10 分钟）
    BI_ASYNC_QUERY_TIMEOUT: int = 600
    # 每用户最大并发异步任务数
    BI_ASYNC_QUERY_USER_MAX_CONCURRENCY: int = 2
    # 全局最大并发异步任务数
    BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY: int = 20
    # 结果预览行数（JSON 存储上限）
    BI_ASYNC_QUERY_PREVIEW_ROWS: int = 10_000
    # 任务记录保留天数（过期由清理任务软删 + CSV 物理删除）
    BI_ASYNC_QUERY_TTL_DAYS: int = 7
    # 同步查询软超时（秒，比硬超时 30s 早 5s 触发转异步）
    BI_SYNC_SOFT_TIMEOUT: int = 25
    # CSV 落盘目录（相对项目根）
    BI_ASYNC_QUERY_CSV_DIR: str = "data/async_query"
    # runner BLPOP 超时（秒，控制 shutdown 检查频率）
    BI_ASYNC_QUEUE_BLPOP_TIMEOUT: int = 5
    # 流式 fetchmany 批大小
    BI_ASYNC_QUERY_BATCH_SIZE: int = 1000

    model_config = {"env_file": ".env", "extra": "ignore"}


BIZ_SETTINGS = BusinessSettings()
