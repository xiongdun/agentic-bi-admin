"""列脱敏引擎 — 按规则对查询结果中的敏感字段脱敏。

支持手机号 / 身份证 / 邮箱 / 银行卡等敏感字段脱敏。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.business.bi.models import BiMaskingRule

# 脱敏类型 -> 处理函数映射
_MASKERS = {}


def mask_phone(value: str, mask_char: str = "*", keep_prefix: int = 3, keep_suffix: int = 4) -> str:
    """手机号脱敏：保留前 3 后 4，中间用 **** 替代。"""
    if not value or len(value) < keep_prefix + keep_suffix:
        return mask_char * len(value) if value else ""
    masked_len = len(value) - keep_prefix - keep_suffix
    return value[:keep_prefix] + mask_char * masked_len + value[-keep_suffix:]


def mask_idcard(value: str, mask_char: str = "*", keep_prefix: int = 6, keep_suffix: int = 4) -> str:
    """身份证脱敏：保留前 6 后 4。"""
    if not value or len(value) < keep_prefix + keep_suffix:
        return mask_char * len(value) if value else ""
    masked_len = len(value) - keep_prefix - keep_suffix
    return value[:keep_prefix] + mask_char * masked_len + value[-keep_suffix:]


def mask_email(value: str, mask_char: str = "*", keep_prefix: int = 2, keep_suffix: int = 0) -> str:
    """邮箱脱敏：保留用户名前 2 位 + 完整域名。"""
    if not value or "@" not in value:
        return value
    local, domain = value.split("@", 1)
    if len(local) <= keep_prefix:
        masked_local = mask_char * len(local)
    else:
        masked_local = local[:keep_prefix] + mask_char * (len(local) - keep_prefix)
    return f"{masked_local}@{domain}"


def mask_bankcard(value: str, mask_char: str = "*", keep_prefix: int = 4, keep_suffix: int = 4) -> str:
    """银行卡脱敏：保留前 4 后 4。"""
    if not value or len(value) < keep_prefix + keep_suffix:
        return mask_char * len(value) if value else ""
    masked_len = len(value) - keep_prefix - keep_suffix
    return value[:keep_prefix] + mask_char * masked_len + value[-keep_suffix:]


def mask_custom(value: str, mask_char: str = "*", keep_prefix: int = 0, keep_suffix: int = 0) -> str:
    """自定义脱敏：按 keep_prefix / keep_suffix 保留。"""
    if not value:
        return ""
    if len(value) <= keep_prefix + keep_suffix:
        return mask_char * len(value)
    masked_len = len(value) - keep_prefix - keep_suffix
    return value[:keep_prefix] + mask_char * masked_len + value[-keep_suffix:] if keep_suffix else value[:keep_prefix] + mask_char * masked_len


_MASKERS = {
    "phone": mask_phone,
    "idcard": mask_idcard,
    "email": mask_email,
    "bankcard": mask_bankcard,
    "custom": mask_custom,
}


def mask_value(value: str, mask_type: str, mask_char: str = "*", keep_prefix: int = 0, keep_suffix: int = 0) -> str:
    """对单个值脱敏。"""
    if value is None:
        return None
    masker = _MASKERS.get(mask_type, mask_custom)
    return masker(str(value), mask_char=mask_char, keep_prefix=keep_prefix, keep_suffix=keep_suffix)


def mask_columns(rows: list[dict], rules: list["BiMaskingRule"]) -> list[dict]:
    """对查询结果中的列进行脱敏。

    Args:
        rows: 查询结果行列表（每行是 dict，key 是列名）
        rules: 脱敏规则列表（BiMaskingRule 模型实例）

    Returns:
        脱敏后的行列表（不修改原数据）
    """
    if not rules or not rows:
        return rows

    # 预编译规则（列名匹配模式）
    compiled_rules = []
    for rule in rules:
        try:
            pattern = re.compile(rule.column_pattern, re.IGNORECASE)
        except re.error:
            # 模式编译失败跳过
            continue
        compiled_rules.append((pattern, rule))

    if not compiled_rules:
        return rows

    result = []
    for row in rows:
        masked_row = dict(row)
        for col_name, value in masked_row.items():
            if value is None:
                continue
            for pattern, rule in compiled_rules:
                if pattern.search(col_name):
                    masked_row[col_name] = mask_value(
                        str(value),
                        mask_type=rule.mask_type,
                        mask_char=rule.mask_char,
                        keep_prefix=rule.keep_prefix,
                        keep_suffix=rule.keep_suffix,
                    )
                    break  # 一个列只应用第一个匹配的规则
        result.append(masked_row)

    return result
