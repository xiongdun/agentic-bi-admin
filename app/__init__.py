import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from starlette.staticfiles import StaticFiles
from tortoise.exceptions import OperationalError

from app.core.autodiscover import discover_business_data_policies, discover_business_init_data, discover_business_routers, discover_business_tasks
from app.core.cache import refresh_all_cache
from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    make_middlewares,
    register_db,
    register_exceptions,
    register_routers,
)
from app.core.log import log
from app.core.policy import register_data_policies
from app.core.redis import close_redis, init_redis
from app.core.tasks import BusinessTaskRunner
from app.system.api.utils import refresh_api_list
from app.system.init_data import init_menus, init_users
from app.system.radar import setup_radar, shutdown_radar, startup_radar

try:
    from app.core.config import APP_SETTINGS
except ImportError:
    raise SettingNotFound("Can not import settings")

# 用于协调多 worker 启动初始化的 Redis 键。
# 以 Granian 主进程 PID（所有 worker 的父进程）作为部署代次标识：
# 同一次部署下所有 worker 看到相同的 key，不同部署自然隔离。
_BOOT_ID = os.getppid()
_INIT_LOCK_KEY = f"app:init_lock:{_BOOT_ID}"
_INIT_DONE_KEY = f"app:init_done:{_BOOT_ID}"
_INIT_LOCK_TIMEOUT = 120  # 单位秒 — 单个 worker 持有锁的最长时间
_INIT_WAIT_TIMEOUT = 150  # 单位秒 — 其他 worker 等待初始化完成的最长时间


def create_app() -> FastAPI:
    if APP_SETTINGS.APP_DEBUG:
        _app = FastAPI(
            title=APP_SETTINGS.APP_TITLE, description=APP_SETTINGS.APP_DESCRIPTION, version=APP_SETTINGS.VERSION, openapi_url="/openapi.json", middleware=make_middlewares(), lifespan=lifespan
        )
    else:
        _app = FastAPI(title=APP_SETTINGS.APP_TITLE, description=APP_SETTINGS.APP_DESCRIPTION, version=APP_SETTINGS.VERSION, openapi_url=None, middleware=make_middlewares(), lifespan=lifespan)

    # guard_core 初始化��会添加自己的 StreamHandler（导致双��输出）并输出冗长的 pipeline 信息
    # 清掉其 handler（由根 logger 的 InterceptHandler 统一转发即可），并抑制 INFO 级别
    if APP_SETTINGS.GUARD_ENABLED:
        guard_logger = logging.getLogger("guard_core")
        guard_logger.handlers.clear()
        guard_logger.setLevel(logging.WARNING)

    register_db(_app)
    register_exceptions(_app)
    register_routers(_app, prefix="/api")

    # 自动发现并注册业务模块路由
    business_router, business_names = discover_business_routers()
    if business_router.routes:
        _app.include_router(business_router, prefix="/api/v1/business")
    _app.state.business_modules = business_names
    register_data_policies(discover_business_data_policies())
    _app.state.business_tasks = discover_business_tasks()

    if APP_SETTINGS.RADAR_ENABLED:
        setup_radar(_app)
    return _app


async def _run_init_data(_app: FastAPI) -> bool:
    """初始化种子数据和缓存。多 worker 下仅由一个进程执行，其余等待完成信号。

    若当前 worker 为主导者（执行了初始化），返回 True，否则返回 False。
    """
    redis = _app.state.redis

    acquired = await redis.set(_INIT_LOCK_KEY, "1", nx=True, ex=_INIT_LOCK_TIMEOUT)

    if acquired:
        try:
            try:
                await init_menus()
            except OperationalError as e:
                if "no such table" in str(e).lower() or "does not exist" in str(e).lower() or "doesn't exist" in str(e).lower():
                    await redis.delete(_INIT_LOCK_KEY)
                    sep = "=" * 60
                    log.error(
                        "\n" + sep + "\n"
                        "数据库尚未初始化：检测到基础表缺失（如 `menus`）。\n"
                        "首次启动请先执行以下命令初始化数据库：\n\n"
                        "    just db-init            # 全新项目首次建表 + 基础数据\n\n"
                        "若已有模型变更，请执行：\n\n"
                        "    just mm                # makemigrations + migrate\n\n"
                        "详见 CLAUDE.md / README 的 “数据库迁移” 一节。\n" + sep
                    )
                    # 通知 granian 主进程停止（避免持续 respawn），并静默退出当前 worker
                    try:
                        os.kill(os.getppid(), signal.SIGTERM)
                    except OSError:
                        pass
                    os._exit(1)
                raise
            await refresh_api_list()
            await init_users()

            for init_fn in discover_business_init_data():
                try:
                    await init_fn()
                except Exception as exc:
                    module_name = getattr(init_fn, "__module__", "unknown")
                    message = f"Business init_data failed for module '{module_name}': {exc}"
                    log.exception(message)
                    raise RuntimeError(message) from exc

            await refresh_all_cache(redis)
            await redis.set(_INIT_DONE_KEY, "1", ex=_INIT_LOCK_TIMEOUT)
            return True
        except Exception:
            await redis.delete(_INIT_LOCK_KEY)
            raise
    else:
        elapsed = 0.0
        while elapsed < _INIT_WAIT_TIMEOUT:
            if await redis.exists(_INIT_DONE_KEY):
                return False
            await asyncio.sleep(0.5)
            elapsed += 0.5
        log.warning("Init wait timed out — proceeding anyway")
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_time = datetime.now()
    task_runner = None
    _app.state.redis = await init_redis()
    FastAPICache.init(RedisBackend(_app.state.redis), prefix="fastapi-cache")
    try:
        is_leader = await _run_init_data(_app)

        if APP_SETTINGS.RADAR_ENABLED:
            await startup_radar()

        task_runner = BusinessTaskRunner(_app.state.business_tasks, redis=_app.state.redis)
        task_runner.start()
        _app.state.business_task_runner = task_runner

        # 启动 bi.async_query worker 协程（每个 granian worker 一个）
        try:
            from app.business.bi.config import BIZ_SETTINGS

            if BIZ_SETTINGS.BI_ASYNC_QUERY_ENABLED:
                from app.business.bi.async_query.runner import (
                    recover_stale_tasks,
                    set_shutdown_event,
                    worker_loop,
                )
                from app.business.bi.async_query.state import set_runtime_redis

                # 注入运行期 redis 单例，供 PeriodicTask handler（无参签名）使用
                set_runtime_redis(_app.state.redis)
                async_query_shutdown = asyncio.Event()
                set_shutdown_event(async_query_shutdown)
                # crash recovery：扫描上次未完成的任务
                try:
                    recovered = await recover_stale_tasks(_app.state.redis)
                    if recovered:
                        log.info("bi.async_query recovered {} stale tasks", recovered)
                except Exception:
                    log.exception("bi.async_query recover_stale_tasks failed")

                async_query_task = asyncio.create_task(worker_loop(_app.state.redis, _app), name="bi.async_query.worker")
                _app.state.async_query_worker = async_query_task
                _app.state.async_query_shutdown = async_query_shutdown
        except ImportError:
            pass

        if is_leader:
            if APP_SETTINGS.GUARD_ENABLED:
                log.info("fastapi-guard 已启动")
            for name in _app.state.business_modules:
                log.info(f"Business: registered routes from '{name}'")
            if APP_SETTINGS.RADAR_ENABLED:
                log.info("Radar: enabled")
            log.info("Init data completed")
        yield

    finally:
        # 优雅停止 bi.async_query worker
        async_query_shutdown = getattr(_app.state, "async_query_shutdown", None)
        async_query_worker = getattr(_app.state, "async_query_worker", None)
        if async_query_shutdown is not None:
            async_query_shutdown.set()
        if async_query_worker is not None:
            try:
                await asyncio.wait_for(async_query_worker, timeout=10)
            except asyncio.TimeoutError:
                log.warning("bi.async_query worker did not stop gracefully within 10s, cancelling")
                async_query_worker.cancel()
            except Exception:
                pass

        if task_runner is not None:
            await task_runner.stop()
        if APP_SETTINGS.RADAR_ENABLED:
            await shutdown_radar()
        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds() / 60
        log.info(f"App {_app.title} runtime: {runtime} min")  # noqa
        await close_redis(_app.state.redis)


fastapi_app = create_app()

fastapi_app.mount("/static", StaticFiles(directory=APP_SETTINGS.STATIC_ROOT), name="static")

# 反向代理支持 — 使用 granian 提供的 wrapper 从 X-Forwarded-* 还原真实客户端 IP / 协议。
# 仅在启用且受信任主机白名单配置正确时生效；必须放在路由挂载之后、最外层。
# 注意：wrapper 返回的是 ASGI 可调用对象，不再具有 FastAPI 属性（如 .routes）。
# 需要访问 FastAPI 实例的代码请从本模块导入 `fastapi_app`。
if APP_SETTINGS.PROXY_HEADERS_ENABLED:
    from granian.utils.proxies import wrap_asgi_with_proxy_headers

    app = wrap_asgi_with_proxy_headers(fastapi_app, trusted_hosts=APP_SETTINGS.TRUSTED_HOSTS)
else:
    app = fastapi_app
