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

    model_config = {"env_file": ".env", "extra": "ignore"}


BIZ_SETTINGS = BusinessSettings()
