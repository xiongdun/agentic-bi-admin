"""LLM 路由 — 根据 provider / model 选择具体实现。

提供全局单例 ``get_router()``，业务侧通过 ``router.achat(provider, request)``
统一调用。模型配置策略：

- **DB 优先** ：从 ``bi_model_provider`` / ``bi_model`` 加载启用的 provider，
  第一个 ``is_default=True`` 的 provider 作为默认。
- **env 兜底** ：DB 中没有可用的 provider 时，按 ``APP_SETTINGS`` 中的环境变量
  注入（保留向后兼容）。
- **不再有 mock 兜底** ：未配置 LLM provider 时 ``get()`` 抛 ``NoLLMProviderError``
  (code=4001)，由调用方决定如何处理（前端跳 ``/bi/models``，API 层 SSE error 事件）。
- **refresh()** ：provider 增删改后调用 ``refresh_router()`` 立即生效。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.business.bi.llm.base import BaseChatModel, ChatRequest, ChatResponse
from app.business.bi.llm.deepseek import DeepSeekChatModel
from app.business.bi.llm.mock import MockChatModel
from app.core.config import APP_SETTINGS
from app.core.exceptions import BizError
from app.core.log import log

# provider.type 与 chat model 类的映射（Phase 1：openai_compatible / mock；
# 后续接入 anthropic / ollama 只需在 _build_chat_model 里增加分支）。
_CHAT_MODEL_KEY = "deepseek"  # 注册到 router 的固定 key（兼容旧调用）


class NoLLMProviderError(BizError):
    """未配置可用 LLM Provider(code=4001)。

    业务侧应捕获此错误并提示用户前往 ``/bi/models`` 配置。
    """

    def __init__(
        self,
        *,
        available: list[str] | None = None,
        requested: str | None = None,
    ) -> None:
        super().__init__(code=4001, msg="未配置 LLM Provider，请先在 /bi/models 添加")
        self.data = {"available": available or [], "requested": requested}


def _build_chat_model(
    *,
    provider_type: str,
    base_url: str | None,
    api_key: str | None,
    default_model: str | None,
) -> BaseChatModel | None:
    """根据 provider.type 构建对应的 chat model。

    Phase 1：openai_compatible / custom 复用 DeepSeekChatModel（OpenAI 协议兼容）。
    """
    if provider_type in ("openai_compatible", "custom"):
        if not api_key:
            return None
        return DeepSeekChatModel(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com",
            default_model=default_model or "deepseek-chat",
        )
    if provider_type == "anthropic":
        # Phase 1 占位：未实装 Anthropic 协议客户端时回退到 mock
        log.warning("LLM router: anthropic provider not implemented yet, skipping")
        return None
    if provider_type == "ollama":
        # Phase 1 占位
        log.warning("LLM router: ollama provider not implemented yet, skipping")
        return None
    if provider_type == "mock":
        return MockChatModel(default_model=default_model or "mock-sandbox")
    return None


@dataclass(slots=True)
class LLMRouter:
    """多 provider 路由。

    支持：
    - register(name, model)
    - get(name) → BaseChatModel（找不到抛 NoLLMProviderError）
    - achat(provider, request) / astream(provider, request)
    - refresh() — 从 DB 重建
    - has_real_provider() — 是否至少配置了 1 个 provider
    """

    _models: dict[str, BaseChatModel] = field(default_factory=dict)
    default_provider: str = ""

    @classmethod
    def build_default(cls) -> "LLMRouter":
        """根据 APP_SETTINGS 构建默认路由器（仅 env 路径，DB 路径由 refresh 触发）。

        Phase 1.x：不再默认注册 mock。env 中 ``DEEPSEEK_API_KEY`` 存在时启用 deepseek；
        否则 router 是空的，调用方会收到 ``NoLLMProviderError``。
        """
        router = cls(_models={})
        router.default_provider = ""

        # env 兜底：DEEPSEEK_API_KEY
        api_key = getattr(APP_SETTINGS, "DEEPSEEK_API_KEY", "")
        if api_key:
            try:
                router._models[_CHAT_MODEL_KEY] = DeepSeekChatModel(api_key=api_key)
                router.default_provider = _CHAT_MODEL_KEY
                log.info("LLM router: deepseek provider enabled (from env)")
            except Exception as exc:  # noqa: BLE001
                log.warning(f"LLM router: failed to init deepseek from env: {exc}")

        return router

    def register(self, name: str, model: BaseChatModel) -> None:
        self._models[name] = model

    def has_real_provider(self) -> bool:
        """是否至少配置了 1 个可用的 LLM provider。"""
        return bool(self._models) and bool(self.default_provider)

    def get(self, name: str | None = None) -> "BaseChatModel":
        """获取指定 provider 的 chat model，找不到抛 :class:`NoLLMProviderError`。

        :param name: provider 名称，``None`` 时使用 :attr:`default_provider`。
        :raises NoLLMProviderError: 未配置任何 provider 或指定 provider 不存在。
        """
        if name is None:
            name = self.default_provider
        m = self._models.get(name)
        if m is None:
            raise NoLLMProviderError(
                available=list(self._models.keys()),
                requested=name,
            )
        return m

    async def achat(self, provider: str | None, request: ChatRequest) -> ChatResponse:
        m = self.get(provider)
        return await m.achat(request)

    async def astream(self, provider: str | None, request: ChatRequest):
        m = self.get(provider)
        async for chunk in m.astream(request):
            yield chunk

    async def refresh_from_db(self) -> None:
        """从 DB 重建 provider 注册表（每次 provider/model 变更后调用）。

        策略：
        - 清空旧的 provider；
        - 读取所有 ``is_enabled=True`` 的 provider，按其 type 注册；
        - 第一个 ``is_default=True`` 的 provider 作为 default_provider；
        - 若无 DB provider，则保留 env 兜底（不主动清掉 env provider）。
        """
        # 延迟 import 避免循环引用（service 依赖 llm，llm 又会读 service/model）
        from app.business.bi.models.llm import BiModel, BiModelProvider

        try:
            # 读取所有启用 provider
            providers = await BiModelProvider.filter(is_enabled=True).order_by("order", "-id")
        except Exception as exc:  # noqa: BLE001
            # 表还没 migrate / DB 不可用 — 静默保留 env 路径
            log.debug(f"LLM router.refresh: skip (db unavailable): {exc}")
            return

        # 计算每个 provider 下的 default model
        # 注意：fallback 排序必须与 app/business/bi/services/llm_api.py::test_provider_connection
        # 保持一致（``order_by("order", "id")``），否则同一个 provider 在 test 路径
        # 和 chat 路径会选出不同的 model，导致 "测试通过但用不起来"。
        default_model_codes: dict[int, str] = {}
        for p in providers:
            m = await BiModel.filter(provider_id=p.id, is_default=True, is_enabled=True).first()
            if m is not None:
                default_model_codes[p.id] = m.code
            else:
                # 没有 default 就取第一个启用的 model（order 升序, id 升序 = 早添加的优先）
                m = await BiModel.filter(provider_id=p.id, is_enabled=True).order_by("order", "id").first()
                if m is not None:
                    default_model_codes[p.id] = m.code

        # 清掉旧非 env provider（保留 env deepseek 兜底）
        preserve_keys = {_CHAT_MODEL_KEY}  # noqa: SIM401
        for k in list(self._models.keys()):
            if k not in preserve_keys:
                del self._models[k]

        # 注册 DB provider
        db_default: str | None = None
        first_db_provider: str | None = None
        for p in providers:
            default_model_code = default_model_codes.get(p.id)
            m = _build_chat_model(
                provider_type=p.type.value if hasattr(p.type, "value") else str(p.type),
                base_url=p.base_url,
                api_key=p.api_key,
                default_model=default_model_code,
            )
            if m is None:
                continue
            # DB provider 显式挂在 provider.code 上，便于按 code 寻址
            self._models[p.code] = m
            if p.is_default:
                db_default = p.code
            if first_db_provider is None:
                first_db_provider = p.code

        # 更新默认 provider 顺序：DB is_default > DB 第一个 > env deepseek > 空（让上层报错）
        if db_default is not None:
            self.default_provider = db_default
        elif first_db_provider is not None:
            # 没有显式标 default 的 provider 时，回退到第一个可用的
            self.default_provider = first_db_provider
        elif _CHAT_MODEL_KEY in self._models:
            self.default_provider = _CHAT_MODEL_KEY
        else:
            self.default_provider = ""

        # Phase 1.x：不再补 mock 兜底


_default_router: LLMRouter | None = None
_loading_lock: bool = False  # 简易防重入：避免并发 refresh 时反复 build


def get_router() -> LLMRouter:
    """获取全局 LLM 路由器（单例）。"""
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter.build_default()
    return _default_router


async def refresh_router() -> None:
    """从 DB 重建 router（provider/model 变更后调用）。"""
    global _loading_lock
    if _loading_lock:
        return
    _loading_lock = True
    try:
        r = get_router()
        await r.refresh_from_db()
        log.info(f"LLM router refreshed: default={r.default_provider}, providers={list(r._models.keys())}")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"LLM router refresh failed: {exc}")
    finally:
        _loading_lock = False


async def ensure_router() -> "LLMRouter":
    """惰性保证 router 已加载（每个 granian worker 独立缓存）。

    多 worker 部署下，启动时只有 leader 会跑 ``init_data.init()`` 并 ``refresh_router``。
    其他 worker 的 router 是空的。在用到 router 的入口前先调一次本函数，
    若当前 worker router 为空则从 DB 重新加载。
    """
    r = get_router()
    if r._models or r.default_provider:
        return r
    # 当前 worker 还没加载过；尝试从 DB 拉一次
    try:
        await refresh_router()
    except Exception:  # noqa: BLE001
        pass
    return r


def reset_router_for_testing() -> None:
    """重置单例（仅供测试）。"""
    global _default_router
    _default_router = None


__all__ = [
    "LLMRouter",
    "NoLLMProviderError",
    "get_router",
    "refresh_router",
    "reset_router_for_testing",
]
