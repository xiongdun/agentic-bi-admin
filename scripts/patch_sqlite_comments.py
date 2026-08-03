"""修补 SQLite 数据库中所有表/字段的中文注释。

SQLite 不支持 COMMENT ON 语法，注释以 ``/* ... */`` 形式嵌入在 DDL 中。
本脚本通过 ``PRAGMA writable_schema`` 直接修改 ``sqlite_master`` 表中的建表 SQL，
给缺失注释的字段补充中文注释，**不丢失任何数据**。

覆盖范围：
  - 所有业务表 / Radar 表的 ``id`` 主键字段 → 主键ID
  - 6 张 M2M 中间表的关联字段 → 对应中文名

用法：uv run python scripts/patch_sqlite_comments.py
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app_system.sqlite3"

# M2M 中间表字段的中文注释映射
M2M_FIELD_COMMENTS: dict[str, dict[str, str]] = {
    "biz_employee_biz_tag": {"biz_employee_id": "员工ID", "tag_id": "标签ID"},
    "menus_buttons": {"menus_id": "菜单ID", "button_id": "按钮ID"},
    "roles_apis": {"roles_id": "角色ID", "api_id": "API ID"},
    "roles_buttons": {"roles_id": "角色ID", "button_id": "按钮ID"},
    "roles_menus": {"roles_id": "角色ID", "menu_id": "菜单ID"},
    "users_roles": {"users_id": "用户ID", "role_id": "角色ID"},
}


def add_comment_to_field(line: str, field_name: str, comment: str) -> str:
    """给字段定义行追加 /* comment */ 注释（如果尚无注释）。

    保留行尾的逗号。
    """
    stripped = line.rstrip()
    # 检测并去掉行尾逗号
    trailing_comma = ""
    if stripped.endswith(","):
        trailing_comma = ","
        stripped = stripped[:-1].rstrip()
    # 已有注释则跳过
    if "/*" in stripped and "*/" in stripped:
        return line
    return f"{stripped}  /* {comment} */{trailing_comma}"


def patch_ddl(table_name: str, ddl: str) -> tuple[str, list[str]]:
    """给建表 SQL 中的字段补充注释。返回 (新DDL, 修改的字段列表)。"""
    # M2M 中间表的字段注释
    m2m_map = M2M_FIELD_COMMENTS.get(table_name, {})

    lines = ddl.split("\n")
    patched_fields: list[str] = []
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # 匹配字段定义行："field_name" TYPE ...
        m = re.match(r'^\s*"(\w+)"\s+', line)
        if not m:
            new_lines.append(line)
            continue

        field = m.group(1)

        # 跳过约束行（PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK, CONSTRAINT）
        if re.match(
            r'^\s*(PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|CHECK|CONSTRAINT)\b',
            stripped,
            re.IGNORECASE,
        ):
            new_lines.append(line)
            continue

        # 已有注释
        if "/*" in stripped and "*/" in stripped:
            new_lines.append(line)
            continue

        comment = None
        if field == "id":
            comment = "主键ID"
        elif field in m2m_map:
            comment = m2m_map[field]

        if comment:
            new_line = add_comment_to_field(line, field, comment)
            new_lines.append(new_line)
            patched_fields.append(field)
        else:
            new_lines.append(line)

    return "\n".join(new_lines), patched_fields


def main() -> int:
    if not DB_PATH.exists():
        print(f"[patch] 数据库文件不存在: {DB_PATH}", file=sys.stderr)
        return 1

    # 先停掉占用数据库的进程提示
    print(f"[patch] 数据库: {DB_PATH}")
    print("[patch] 通过 PRAGMA writable_schema 修改 DDL，不丢失数据")
    print()

    conn = sqlite3.connect(str(DB_PATH))
    conn.isolation_level = None
    cur = conn.cursor()

    # 获取所有表（排除 sqlite_ 系统表和 tortoise_migrations）
    cur.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'tortoise_%' "
        "ORDER BY name"
    )
    rows = cur.fetchall()

    total_patched = 0
    print(f"{'表名':<30} {'修补字段数':>10}")
    print("-" * 44)

    for table_name, ddl in rows:
        if not ddl:
            continue
        new_ddl, patched_fields = patch_ddl(table_name, ddl)
        if not patched_fields:
            print(f"{table_name:<30} {'0':>10}")
            continue

        # 用 PRAGMA writable_schema 直接更新 sqlite_master
        cur.execute("PRAGMA writable_schema = 1")
        try:
            cur.execute(
                "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = ?",
                (new_ddl, table_name),
            )
            cur.execute("PRAGMA writable_schema = 0")
            total_patched += len(patched_fields)
            print(f"{table_name:<30} {len(patched_fields):>10}  ← {', '.join(patched_fields)}")
        except Exception as e:
            cur.execute("PRAGMA writable_schema = 0")
            print(f"{table_name:<30} ERROR: {e}", file=sys.stderr)

    conn.commit()
    conn.close()

    print()
    print(f"[patch] 完成。共修补 {total_patched} 个字段的注释。")
    print("[patch] 建议重启后端服务以刷新连接缓存。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
