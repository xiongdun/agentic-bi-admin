"""BI Metric + LLM 意图 E2E 烟测。

需要后端服务运行在 ``http://127.0.0.1:9999``,并已 ``just db-init``。

执行流程:
1. 登录 admin
2. 预置 datasource(若已存在则跳过)
3. 验证默认 5 个 metric 已就绪
4. 新建 / 更新 / 测试模板 / 删除 1 个 metric
5. 触发 chat send 验证 SSE 流程:
   - 若已配置 LLM,期望至少一个 ``intent`` 步骤事件 + ``final`` 事件
   - 若未配置,期望 ``error`` 事件 code=4001

用法::

    uv run python scripts/bi_metrics_e2e.py [--base http://127.0.0.1:9999/api/v1]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx


DEFAULT_BASE = "http://127.0.0.1:9999/api/v1"
USERNAME = "Soybean"
PASSWORD = "123456"


class Step:
    def __init__(self, label: str) -> None:
        self.label = label
        self.ok = False
        self.detail = ""

    def passed(self, detail: str = "") -> None:
        self.ok = True
        self.detail = detail
        print(f"\u2713 {self.label}{(': ' + detail) if detail else ''}")

    def failed(self, detail: str) -> None:
        self.ok = False
        self.detail = detail
        print(f"\u2717 {self.label}: {detail}")


def _login(c: httpx.Client, base: str) -> dict[str, Any]:
    r = c.post(f"{base}/auth/login", json={"userName": USERNAME, "password": PASSWORD})
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0000":
        raise RuntimeError(f"login failed: {body}")
    token = body["data"]["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    return body["data"]


def _ensure_demo_datasource(c: httpx.Client, base: str) -> str:
    """确保存在至少一个 datasource;若没有,生成 demo。返回 datasource id(sqid)。"""
    r = c.post(f"{base}/business/bi/datasources/search", json={"current": 1, "size": 10})
    r.raise_for_status()
    body = r.json()
    records = body.get("data", {}).get("records", [])
    if records:
        return records[0]["id"]

    r = c.post(f"{base}/business/bi/datasources/demo")
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0000":
        raise RuntimeError(f"demo bootstrap failed: {body}")
    # bootstrap 后再查一次
    r = c.post(f"{base}/business/bi/datasources/search", json={"current": 1, "size": 10})
    r.raise_for_status()
    records = r.json().get("data", {}).get("records", [])
    if not records:
        raise RuntimeError("no datasource after demo bootstrap")
    return records[0]["id"]


def _list_metrics(c: httpx.Client, base: str) -> list[dict[str, Any]]:
    r = c.post(f"{base}/business/bi/metrics/search", json={"current": 1, "size": 50})
    r.raise_for_status()
    return r.json().get("data", {}).get("records", [])


def _create_metric(
    c: httpx.Client, base: str, *, ds_id: str, suffix: str
) -> str:
    payload = {
        "name": f"e2e_metric_{suffix}",
        "displayName": f"E2E Metric {suffix}",
        "sqlTemplate": "SUM({order}.amount) WHERE {order}.status = 'paid'",
        "datasourceId": ds_id,
        "unit": "元",
        "description": "E2E created metric",
    }
    r = c.post(f"{base}/business/bi/metrics", json=payload)
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0000":
        raise RuntimeError(f"create metric failed: {body}")
    return body["data"]["createdId"]


def _update_metric(c: httpx.Client, base: str, item_id: str) -> None:
    r = c.patch(
        f"{base}/business/bi/metrics/{item_id}",
        json={"displayName": "E2E updated"},
    )
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0000":
        raise RuntimeError(f"update metric failed: {body}")


def _test_metric(c: httpx.Client, base: str, item_id: str) -> dict[str, Any]:
    r = c.post(f"{base}/business/bi/metrics/{item_id}/test")
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0000":
        raise RuntimeError(f"test metric failed: {body}")
    return body["data"]


def _delete_metric(c: httpx.Client, base: str, item_id: str) -> None:
    r = c.delete(f"{base}/business/bi/metrics/{item_id}")
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0000":
        raise RuntimeError(f"delete metric failed: {body}")


def _chat_sse_smoke(
    c: httpx.Client, base: str, *, ds_id: str
) -> dict[str, Any]:
    """SSE 烟测:返回 {"event_counts": {...}, "saw_final": bool, "saw_error": bool, "error_code": int|None}。"""
    r = c.post(f"{base}/business/bi/chat/sessions", json={"title": "e2e chat smoke"})
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0000":
        raise RuntimeError(f"create session failed: {body}")
    sid = body["data"]["id"]

    counts: dict[str, int] = {}
    saw_final = False
    saw_error = False
    error_code: int | None = None

    with c.stream(
        "POST",
        f"{base}/business/bi/chat/sessions/{sid}/messages",
        json={"question": "本月销售额", "datasourceId": ds_id},
    ) as resp:
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                ev = line[7:].strip()
                counts[ev] = counts.get(ev, 0) + 1
                if ev == "error":
                    saw_error = True
                if ev == "final":
                    saw_final = True
            elif line.startswith("data: ") and saw_error and error_code is None:
                # 抓 error 事件后面的 data 行,尝试解析 code
                raw = line[6:].strip()
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict) and "code" in parsed:
                        error_code = parsed.get("code")
                except json.JSONDecodeError:
                    pass

    return {"counts": counts, "saw_final": saw_final, "saw_error": saw_error, "error_code": error_code}


def main(base: str) -> int:
    steps: list[Step] = []
    with httpx.Client(timeout=30) as c:
        try:
            s = Step("login admin")
            _login(c, base)
            s.passed()
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
            steps.append(s)
            return _report(steps)

        steps.append(s)

        s = Step("ensure datasource")
        try:
            ds_id = _ensure_demo_datasource(c, base)
            s.passed(f"ds={ds_id}")
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
            steps.append(s)
            return _report(steps)
        steps.append(s)

        s = Step("preset metrics >= 5")
        try:
            metrics = _list_metrics(c, base)
            if len(metrics) < 5:
                raise RuntimeError(f"expected >=5 preset metrics, got {len(metrics)}")
            s.passed(f"total={len(metrics)}")
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
            steps.append(s)
            return _report(steps)
        steps.append(s)

        s = Step("create metric")
        try:
            suffix = str(int(time.time()))
            new_id = _create_metric(c, base, ds_id=ds_id, suffix=suffix)
            s.passed(f"id={new_id}")
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
            steps.append(s)
            return _report(steps)
        steps.append(s)

        s = Step("update metric")
        try:
            _update_metric(c, base, new_id)
            s.passed()
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
        steps.append(s)

        s = Step("test metric template")
        try:
            test = _test_metric(c, base, new_id)
            if not test.get("success"):
                raise RuntimeError(f"template invalid: {test}")
            s.passed(f"placeholders={test.get('placeholders', [])}")
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
        steps.append(s)

        s = Step("chat SSE smoke (LLM may be unconfigured)")
        try:
            result = _chat_sse_smoke(c, base, ds_id=ds_id)
            ev_counts = result["counts"]
            if result["saw_error"] and result["error_code"] == 4001:
                s.passed("got expected 4001 (no LLM provider) - LLM not configured")
            elif result["saw_final"]:
                s.passed(f"got final: events={ev_counts}")
            else:
                raise RuntimeError(f"unexpected SSE flow: {ev_counts}")
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
        steps.append(s)

        s = Step("delete metric")
        try:
            _delete_metric(c, base, new_id)
            s.passed()
        except Exception as exc:  # noqa: BLE001
            s.failed(str(exc))
        steps.append(s)

    return _report(steps)


def _report(steps: list[Step]) -> int:
    print()
    if all(s.ok for s in steps):
        print("ALL PASS")
        return 0
    print("FAIL:")
    for s in steps:
        if not s.ok:
            print(f"  - {s.label}: {s.detail}")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BI Metric E2E smoke")
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    args = parser.parse_args()
    sys.exit(main(args.base))
