"""结果存储 — JSON 预览 + CSV 流式落盘。

策略（spec §3.2 / §5.3）：
- ``write_preview``：取前 ``max_rows`` 行构造 JSON snapshot，标记 isTruncated
- ``write_csv_header``：写入 CSV 表头，调用方分批 fetchmany 后逐批 append 行
- ``resolve_csv_path``：拼接绝对路径 + 防目录穿越校验
- ``read_csv_stream``：下载用，按 chunk 读
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path
from typing import Any, Iterator

from app.business.bi.config import BIZ_SETTINGS

# result_uri 只允许 ``<task_id>.csv`` 形式，防目录穿越
_URI_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+\.csv$")


def write_preview(columns: list[str], rows: list[dict[str, Any]], elapsed_ms: int) -> dict:
    """构造结果预览 JSON。超过 ``BI_ASYNC_QUERY_PREVIEW_ROWS`` 的行被截断。"""
    max_rows = BIZ_SETTINGS.BI_ASYNC_QUERY_PREVIEW_ROWS
    total = len(rows)
    truncated = total > max_rows
    preview_rows = rows[:max_rows]
    return {
        "columns": columns,
        "rows": preview_rows,
        "rowCount": len(preview_rows),
        "elapsedMs": elapsed_ms,
        "isTruncated": truncated,
    }


def _csv_dir() -> Path:
    """CSV 落盘目录（绝对路径）。"""
    csv_dir = BIZ_SETTINGS.BI_ASYNC_QUERY_CSV_DIR
    # 相对路径基于项目根（cwd）
    p = Path(csv_dir)
    if not p.is_absolute():
        p = Path.cwd() / csv_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_result_uri(task_id: int) -> str:
    """生成 result_uri（相对路径）。"""
    return f"{task_id}.csv"


def resolve_csv_path(result_uri: str) -> Path:
    """把 result_uri 解析为绝对路径，并校验不逃逸 CSV 目录。

    Raises:
        ValueError: result_uri 格式非法或路径逃逸
    """
    if not _URI_PATTERN.match(result_uri):
        raise ValueError(f"非法 result_uri: {result_uri}")
    base = _csv_dir().resolve()
    target = (base / result_uri).resolve()
    # 防穿越：target 必须在 base 之内
    if base not in target.parents and target != base:
        raise ValueError(f"路径逃逸 CSV 目录: {result_uri}")
    return target


def write_csv_header(file_path: Path, columns: list[str]) -> None:
    """写 CSV 表头（覆盖写）。"""
    with file_path.open("w", newline="", encoding="utf-8") as f:
        # UTF-8 BOM 头方便 Excel 直接打开
        f.write("\ufeff")
        writer = csv.writer(f)
        writer.writerow(columns)


def append_csv_rows(file_path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    """追加写 CSV 行。"""
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])


def read_csv_stream(file_path: Path, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    """按 chunk 流式读 CSV（FastAPI StreamingResponse 用）。"""
    with file_path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def delete_csv(result_uri: str) -> None:
    """删除 CSV 文件（任务删除时调用）。不存在则静默。"""
    try:
        path = resolve_csv_path(result_uri)
        path.unlink(missing_ok=True)
    except ValueError:
        # 非法 result_uri 直接忽略
        pass
