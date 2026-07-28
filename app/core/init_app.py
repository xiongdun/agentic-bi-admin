import logging
import sys

import orjson
import pretty_errors
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from guard import SecurityConfig
from guard.middleware import SecurityMiddleware
from starlette.responses import Response
from tortoise.contrib.fastapi import register_tortoise

from app.core.autodiscover import discover_business_endpoint_rate_limits
from app.core.code import Code
from app.core.config import APP_SETTINGS
from app.core.log import log
from app.core.exceptions import (
    BizError,
    BizErrorHandle,
    DoesNotExist,
    DoesNotExistHandle,
    IntegrityError,
    IntegrityHandle,
    RequestValidationError,
    RequestValidationHandle,
    ResponseValidationError,
    ResponseValidationHandle,
)
from app.core.middlewares import BackGroundTaskMiddleware, PrettyErrorsMiddleware, RequestIDMiddleware
from app.system.api import system_router
from app.system.api.health import router as health_router
from app.system.radar.middleware import RadarMiddleware


async def _guard_response_modifier(response):
    """将 guard 的错误响应改写为项目统一的 JSON 格式。"""
    status = response.status_code
    if status < 400:
        return response
    if status in (404, 405):
        return response  # 正常路由错误直接透传，不伪装为安全拦截
    if status == 429:
        code, msg = Code.RATE_LIMITED, "请求过于频繁，请稍后再试"
    elif status == 403 and b"banned" in (response.body or b"").lower():
        code, msg = Code.IP_BANNED, "IP已被封禁，请稍后再试"
    elif status == 403:
        code, msg = Code.ACCESS_DENIED, "访问被拒绝"
    else:
        code, msg = Code.ACCESS_DENIED, "请求被安全策略拦截"
    body = orjson.dumps({"code": code, "msg": msg, "data": None})
    response._response = Response(content=body, status_code=200, media_type="application/json")
    return response


def _make_guard_config():
    """根据应用配置构建 fastapi-guard 的 SecurityConfig。"""
    endpoint_rate_limits = {
        "/api/v1/auth/login": (5, 60),  # 每 60 秒最多 5 次请求
        "/api/v1/auth/refresh-token": (10, 60),  # 每 60 秒最多 10 次请求
    }
    endpoint_rate_limits.update(discover_business_endpoint_rate_limits())

    # 工作台 / 沙箱的 body 内会带 SELECT / FROM 等 SQL 片段，会触发 fastapi-guard 的
    # "SQL 注入" 模式误判。沙箱自身已经在 pipeline.py 里做白名单 + 限流，这里把
    # /business/bi/sql/* 整段从安全策略里排除，避免误杀。
    # 模型管理 provider 的 baseUrl / extra 是 URL / JSON 字符串，会触发 fastapi-guard 的
    # "URL/可疑字符串" 模式误判；同样的策略里也整段排除 LLM 路径。
    excluded_paths = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/static",
        "/api/v1/business/bi/sql",
        "/api/v1/business/bi/llm",
        "/api/v1/business/bi/audit",
    ]

    # Windows + redis-py 4.6.0 + asyncio (ProactorEventLoop) 在 Guard 中间件的
    # 第一个请求里调用 `Redis.from_url(...).ping()` 会抛 `OSError(22)` (`WSAEINVAL`)，
    # 导致 Guard_redis_handler 初始化失败、所有受 Guard 保护的接口都返回 GuardRedisError。
    # 主应用 `app/core/redis.py` 用同样的 from_url 却能成功（lifespan 启动期 vs 中间件
    # task scope 的微妙差异，根因未定位）。Windows 开发环境下回退到内存限流即可；
    # Linux/Docker 部署不受影响，仍走 Redis。
    # 根治方案：`uv add "redis>=5.0"` 后改回 `enable_redis=True`。
    enable_redis = sys.platform != "win32"
    if not enable_redis:
        log.warning(
            "Guard: Redis 已禁用 (Windows + redis-py 4.6.0 asyncio 兼容性问题)，"
            "回退到进程内限流。升级 redis-py 到 5.0+ 后可恢复 Redis 分布式限流。"
        )

    return SecurityConfig(
        rate_limit=APP_SETTINGS.GUARD_RATE_LIMIT,
        rate_limit_window=APP_SETTINGS.GUARD_RATE_LIMIT_WINDOW,
        auto_ban_threshold=APP_SETTINGS.GUARD_AUTO_BAN_THRESHOLD,
        auto_ban_duration=APP_SETTINGS.GUARD_AUTO_BAN_DURATION,
        enable_redis=enable_redis,
        redis_url=APP_SETTINGS.REDIS_URL,
        enable_cors=False,  # CORS 已由 CORSMiddleware 处理
        enforce_https=False,
        security_headers=None,  # 安全响应头由 nginx 处理
        custom_log_file=str(APP_SETTINGS.LOGS_ROOT / "guard.log"),
        custom_response_modifier=_guard_response_modifier,
        exclude_paths=excluded_paths,
        endpoint_rate_limits=endpoint_rate_limits,
    )


def make_middlewares():
    # 中间件顺序：列表第一个为最外层。
    # - RequestIDMiddleware 需要最外，保证 x_request_id 在所有内层（包括 Radar）都可读。
    # - RadarMiddleware 必须在 PrettyErrorsMiddleware 外层，这样 PrettyErrors 把未捕获异常转换成 5001
    #   JSONResponse 后，响应体 / 状态码才会回流经 Radar 的 send_wrapper 被采集到。
    middleware = [
        Middleware(RequestIDMiddleware),
        Middleware(
            CORSMiddleware,
            allow_origins=APP_SETTINGS.CORS_ORIGINS,
            allow_credentials=APP_SETTINGS.CORS_ALLOW_CREDENTIALS,
            allow_methods=APP_SETTINGS.CORS_ALLOW_METHODS,
            allow_headers=APP_SETTINGS.CORS_ALLOW_HEADERS,
        ),
        Middleware(BackGroundTaskMiddleware),
    ]
    if APP_SETTINGS.RADAR_ENABLED:
        middleware.append(Middleware(RadarMiddleware))

    middleware.append(
        Middleware(
            PrettyErrorsMiddleware,
            line_number_first=True,
            lines_before=5,
            lines_after=2,
            line_color=pretty_errors.RED + "> " + pretty_errors.default_config.line_color,
            code_color="  " + pretty_errors.default_config.line_color,
            truncate_code=True,
            display_locals=True,
            filename_display=pretty_errors.FILENAME_EXTENDED,
        )
    )

    if APP_SETTINGS.GUARD_ENABLED:
        # 预先在 guard_core logger 上注入 filter，阻止初始化时输出冗长的 pipeline 信息
        # setup_custom_logging 只会 clear handlers，不会 clear filters
        _guard_logger = logging.getLogger("guard_core")
        _guard_logger.addFilter(lambda r: "Security pipeline initialized" not in r.getMessage())
        middleware.append(Middleware(SecurityMiddleware, config=_make_guard_config()))

    return middleware


def register_db(app: FastAPI):
    register_tortoise(
        app,
        config=APP_SETTINGS.TORTOISE_ORM,
        generate_schemas=False,
    )


def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(BizError, BizErrorHandle)  # type: ignore
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)  # type: ignore
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)  # type: ignore


def register_routers(app: FastAPI, prefix: str = "/api"):
    app.include_router(system_router, prefix=f"{prefix}/v1")
    app.include_router(health_router)
