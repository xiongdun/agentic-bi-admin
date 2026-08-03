"""业务表测试数据生成脚本（一次性）。

为现有业务表 + 网贷新表每张新增 100 条随机测试数据。
覆盖范围：
  - HR 模块（4张）：biz_department / biz_tag / biz_employee / biz_employee_status_log
  - BI 模块（13张）：biz_bi_*
  - Radar 模块（3张）：radar_requests / radar_queries / radar_user_logs
  - Loan 模块（10张）：biz_loan_*

注意：
  - 不修改系统核心表（users/roles/menus/apis/buttons/dictionary/event_outbox）
  - 测试数据用唯一标识前缀（T0001-T0100）避免与种子数据冲突
  - 幂等：重复执行会先清理同前缀测试数据再插入

用法：uv run python scripts/gen_test_data.py
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("APP_DEBUG", "false")
os.environ.setdefault("GUARD_ENABLED", "false")

from tortoise import Tortoise  # noqa: E402

from app.business.bi.models import (  # noqa: E402
    BiAuditLog,
    BiChatMessage,
    BiChatSession,
    BiColumn,
    BiDatasource,
    BiForeignKey,
    BiIndex,
    BiLLMModel,
    BiLLMProvider,
    BiMaskingRule,
    BiMetric,
    BiQuotaConfig,
    BiTable,
)
from app.business.hr.models import Department, Employee, EmployeeStatus, EmployeeStatusLog, Tag  # noqa: E402
from app.business.loan.models import (  # noqa: E402
    CollectionResult,
    LoanApplication,
    LoanCollection,
    LoanContract,
    LoanCustomer,
    LoanFundMatching,
    LoanFunder,
    LoanPayment,
    LoanProduct,
    LoanRepaymentPlan,
    LoanRiskEvaluation,
    LoanStatus,
    RepaymentStatus,
    RiskDecision,
)
from app.core.config import APP_SETTINGS  # noqa: E402
from app.system.radar.models import RadarQuery, RadarRequest, RadarUserLog  # noqa: E402
from app.utils import StatusType  # noqa: E402

# 测试数据条数（每张表）
COUNT = 100
# 唯一字段前缀，便于幂等清理
PREFIX = "T"


def _seq(n: int, width: int = 4) -> str:
    return f"{PREFIX}{n:0{width}d}"


# ==================== 随机数据生成工具 ====================

FIRST_NAMES = ["张", "王", "李", "赵", "刘", "陈", "杨", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡", "林", "郭", "何", "高", "罗"]
LAST_NAMES = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "霞", "平", "刚"]
PRODUCT_TYPES = ["信用贷", "抵押贷", "消费贷", "经营贷"]
PURPOSES = ["资金周转", "装修", "购车", "教育", "医疗", "旅游", "结婚", "进货", "扩展经营", "还信用卡"]
COLLECTION_METHODS = ["sms", "phone", "letter", "visit", "legal"]
PAYMENT_METHODS = ["bank", "alipay", "wechat", "offset"]
FUNDER_TYPES = ["bank", "trust", "individual", "institution"]


def rand_name() -> str:
    return random.choice(FIRST_NAMES) + random.choice(LAST_NAMES)


def rand_phone() -> str:
    return f"1{random.choice(['3', '5', '7', '8', '9'])}{random.randint(100000000, 999999999)}"


def rand_id_card() -> str:
    """生成 18 位身份证号（仅用于测试，非真实校验）。"""
    body = "".join([str(random.randint(0, 9)) for _ in range(17)])
    return f"110101{body[6:]}"[:17] + str(random.randint(0, 9))


def rand_email(seq: int) -> str:
    return f"user{_seq(seq)}@test.example.com"


def rand_datetime(days_back: int = 365) -> datetime:
    return datetime.now() - timedelta(days=random.randint(0, days_back), hours=random.randint(0, 23))


def rand_decimal(low: float, high: float, places: int = 2) -> Decimal:
    return Decimal(str(round(random.uniform(low, high), places)))


# ==================== HR 模块（4张表）====================


async def gen_hr(dept_ids: list[int], tag_ids: list[int]) -> tuple[list[int], list[int]]:
    """生成 HR 模块测试数据。返回 (employee_ids, tag_ids) 供其他逻辑使用。"""
    # Department: 已有5个种子，再加95个到100个测试数据（用唯一 code 前缀 T）
    existing_dept_count = await Department.all().count()
    target_dept_count = existing_dept_count + COUNT
    dept_seeds = []
    for i in range(1, COUNT + 1):
        code = f"{PREFIX}-DEPT-{i:04d}"
        dept_seeds.append(
            Department(
                name=f"测试部门-{i:04d}",
                code=code,
                description=f"测试部门描述 {i}",
                status=StatusType.enable,
                parent_id=0,
                level=1,
                order=i,
            )
        )
    await Department.bulk_create(dept_seeds)
    all_depts = await Department.all().limit(target_dept_count)
    dept_ids = [d.id for d in all_depts]

    # Tag: 已有8个种子，再加100个测试数据（unique name）
    tag_seeds = []
    for i in range(1, COUNT + 1):
        tag_seeds.append(
            Tag(
                name=f"测试标签-{i:04d}",
                category=random.choice(["working_style", "collaboration", "team_role", "business", "growth"]),
                description=f"测试标签描述 {i}",
            )
        )
    await Tag.bulk_create(tag_seeds)
    all_tags = await Tag.all()
    tag_ids = [t.id for t in all_tags]

    # Employee: 已有9个种子，再加100个测试数据（unique employee_no）
    emp_seeds = []
    for i in range(1, COUNT + 1):
        emp_seeds.append(
            Employee(
                name=rand_name(),
                employee_no=f"{PREFIX}-EMP-{i:04d}",
                email=rand_email(i),
                phone=rand_phone(),
                position=random.choice(["工程师", "主管", "专员", "经理", "助理", "总监"]),
                status=random.choice(list(EmployeeStatus)),
                department_id=random.choice(dept_ids),
            )
        )
    await Employee.bulk_create(emp_seeds)
    all_emps = await Employee.all()
    emp_ids = [e.id for e in all_emps]

    # EmployeeStatusLog: 100条（FK employee）
    log_seeds = []
    for i in range(COUNT):
        log_seeds.append(
            EmployeeStatusLog(
                employee_id=random.choice(emp_ids),
                from_status=random.choice(list(EmployeeStatus)),
                to_status=random.choice(list(EmployeeStatus)),
                remark=f"测试日志 {i+1}",
                operated_by=1,
            )
        )
    await EmployeeStatusLog.bulk_create(log_seeds)

    return emp_ids, tag_ids


# ==================== BI 模块（13张表）====================


async def gen_bi() -> None:
    # BiDatasource: 100条（unique name）
    ds_seeds = []
    for i in range(1, COUNT + 1):
        ds_seeds.append(
            BiDatasource(
                name=f"测试数据源-{i:04d}",
                db_type=random.choice(["postgresql", "mysql", "clickhouse", "sqlite"]),
                host=f"10.0.{i // 100}.{i % 100}",
                port=random.choice([5432, 3306, 8123, 1527]),
                username=f"ds_user_{i:04d}",
                password="encrypted_test_data",
                database=f"test_db_{i:04d}",
                status_type=StatusType.enable,
                tenant_id=random.randint(0, 10),
            )
        )
    await BiDatasource.bulk_create(ds_seeds)
    ds_ids = [d.id for d in await BiDatasource.all().order_by("-id").limit(COUNT)]

    # BiTable: 100条（FK datasource）
    table_seeds = []
    for i in range(1, COUNT + 1):
        table_seeds.append(
            BiTable(
                datasource_id=random.choice(ds_ids),
                name=f"test_table_{i:04d}",
                comment=f"测试表 {i} 注释",
                row_count=random.randint(0, 1000000),
                source_created_at=rand_datetime(),
                source_updated_at=rand_datetime(),
            )
        )
    await BiTable.bulk_create(table_seeds)
    table_ids = [t.id for t in await BiTable.all().order_by("-id").limit(COUNT)]

    # BiColumn: 100条（FK table）
    col_seeds = []
    for i in range(1, COUNT + 1):
        col_seeds.append(
            BiColumn(
                table_id=random.choice(table_ids),
                name=f"col_{i:04d}",
                data_type=random.choice(["INTEGER", "VARCHAR(255)", "TEXT", "TIMESTAMP", "BOOLEAN", "DECIMAL"]),
                is_primary=(i % 10 == 0),
                is_nullable=(i % 3 != 0),
                default_value=None,
                comment=f"测试列 {i}",
                sample_values=["sample1", "sample2"],
            )
        )
    await BiColumn.bulk_create(col_seeds)

    # BiIndex: 100条（FK table）
    idx_seeds = []
    for i in range(1, COUNT + 1):
        idx_seeds.append(
            BiIndex(
                table_id=random.choice(table_ids),
                name=f"idx_test_{i:04d}",
                index_type=random.choice(["btree", "hash", "gin", "gist"]),
                columns=[f"col_{i:04d}"],
                is_unique=(i % 5 == 0),
            )
        )
    await BiIndex.bulk_create(idx_seeds)

    # BiForeignKey: 100条（FK table）
    fk_seeds = []
    for i in range(1, COUNT + 1):
        fk_seeds.append(
            BiForeignKey(
                table_id=random.choice(table_ids),
                name=f"fk_test_{i:04d}",
                column_name=f"ref_id_{i:04d}",
                ref_table=f"ref_table_{i:04d}",
                ref_column="id",
            )
        )
    await BiForeignKey.bulk_create(fk_seeds)

    # BiMetric: 100条（unique code, FK datasource）
    metric_seeds = []
    for i in range(1, COUNT + 1):
        metric_seeds.append(
            BiMetric(
                name=f"测试指标-{i:04d}",
                code=f"test_metric_{i:04d}",
                description=f"测试指标描述 {i}",
                datasource_id=random.choice(ds_ids),
                sql_template=f"SELECT count(*) FROM test_table_{i:04d} WHERE id = {{id}}",
                chart_type=random.choice(["bar", "line", "pie", "scatter", "table"]),
                status_type=StatusType.enable,
            )
        )
    await BiMetric.bulk_create(metric_seeds)

    # BiChatSession: 100条
    session_seeds = []
    for i in range(1, COUNT + 1):
        session_seeds.append(
            BiChatSession(
                title=f"测试会话-{i:04d}",
                user_id=random.randint(1, 10),
                last_message_at=rand_datetime(30),
                tenant_id=random.randint(0, 10),
            )
        )
    await BiChatSession.bulk_create(session_seeds)
    session_ids = [s.id for s in await BiChatSession.all().order_by("-id").limit(COUNT)]

    # BiChatMessage: 100条（FK session）
    msg_seeds = []
    for i in range(COUNT):
        msg_seeds.append(
            BiChatMessage(
                session_id=random.choice(session_ids),
                role=random.choice(["user", "assistant", "system"]),
                content=f"测试消息内容 {i+1}",
                sql_text=f"SELECT * FROM test_table WHERE id = {i+1}",
                sql_result={"columns": ["id"], "rows": [{"id": i + 1}], "rowCount": 1, "elapsedMs": 10},
                agent_steps_json=[
                    {"node": "intent", "status": "success", "elapsedMs": 5},
                    {"node": "sql_gen", "status": "success", "elapsedMs": 50},
                ],
                intent_type=random.choice(["query", "aggregation", "join"]),
                execution_time_ms=random.randint(10, 5000),
                token_usage={"prompt": 100, "completion": 50},
                status=random.choice(["success", "failed"]),
                error_message=None,
            )
        )
    await BiChatMessage.bulk_create(msg_seeds)

    # BiLLMProvider: 100条（unique name）
    provider_seeds = []
    for i in range(1, COUNT + 1):
        provider_seeds.append(
            BiLLMProvider(
                name=f"测试Provider-{i:04d}",
                provider_type=random.choice(["deepseek", "ollama", "qwen", "openai", "mock", "custom"]),
                api_key="encrypted_test_key",
                base_url=f"https://api.test-{i:04d}.com/v1",
                default_model=f"model-{i:04d}",
                is_default=False,
                status_type=StatusType.enable,
                extra_config={"temperature": 0.7},
            )
        )
    await BiLLMProvider.bulk_create(provider_seeds)
    provider_ids = [p.id for p in await BiLLMProvider.all().order_by("-id").limit(COUNT)]

    # BiLLMModel: 100条（FK provider）
    model_seeds = []
    for i in range(1, COUNT + 1):
        model_seeds.append(
            BiLLMModel(
                provider_id=random.choice(provider_ids),
                name=f"test-model-{i:04d}",
                display_name=f"测试模型 {i}",
                context_length=random.choice([2048, 4096, 8192, 16384, 32768]),
                order=i,
                is_active=True,
            )
        )
    await BiLLMModel.bulk_create(model_seeds)

    # BiAuditLog: 100条
    audit_seeds = []
    for i in range(COUNT):
        audit_seeds.append(
            BiAuditLog(
                trace_id=f"trace-{i+1:04d}",
                event_type=random.choice(["USER_BEHAVIOR", "QUERY_OPERATION", "SYSTEM_OPERATION", "PERMISSION_CHANGE", "BUTTON_CLICK"]),
                action=random.choice(["login", "query", "export", "click", "update"]),
                user_id=random.randint(1, 10),
                username=f"test_user_{i+1}",
                ip_address=f"192.168.1.{i+1}",
                resource_type=random.choice(["datasource", "metric", "session"]),
                resource_id=str(i + 1),
                detail={"extra": "info"},
                status=random.choice(["success", "failed"]),
                error_message=None,
                execution_time_ms=random.randint(10, 1000),
            )
        )
    await BiAuditLog.bulk_create(audit_seeds)

    # BiMaskingRule: 100条（unique name）
    mask_seeds = []
    for i in range(1, COUNT + 1):
        mask_seeds.append(
            BiMaskingRule(
                name=f"测试脱敏规则-{i:04d}",
                column_pattern=random.choice(["phone", "id_card", "email", "bank_card"]),
                mask_type=random.choice(["phone", "idcard", "email", "bankcard", "custom"]),
                mask_char="*",
                keep_prefix=random.randint(0, 3),
                keep_suffix=random.randint(0, 4),
                status_type=StatusType.enable,
            )
        )
    await BiMaskingRule.bulk_create(mask_seeds)

    # BiQuotaConfig: 100条（unique name）
    quota_seeds = []
    for i in range(1, COUNT + 1):
        quota_seeds.append(
            BiQuotaConfig(
                name=f"测试配额-{i:04d}",
                max_rows=random.choice([1000, 5000, 10000, 50000, 100000]),
                timeout_seconds=random.choice([10, 30, 60, 120]),
                breaker_threshold=random.randint(5, 20),
                breaker_window_seconds=random.choice([30, 60, 120, 300]),
                scope_type=random.choice(["global", "user", "datasource"]),
                scope_id=None if i % 3 == 0 else i,
                status_type=StatusType.enable,
            )
        )
    await BiQuotaConfig.bulk_create(quota_seeds)


# ==================== Radar 模块（3张表）====================


async def gen_radar() -> None:
    # RadarRequest: 100条（unique x_request_id）
    req_seeds = []
    for i in range(1, COUNT + 1):
        req_seeds.append(
            RadarRequest(
                x_request_id=f"test-req-{i:04d}-{random.randint(1000, 9999)}",
                method=random.choice(["GET", "POST", "PUT", "DELETE"]),
                path=f"/api/v1/test/path/{i:04d}",
                client_ip=f"10.0.0.{i % 255}",
                client_port=random.randint(1024, 65535),
                user_id=random.randint(1, 10),
                user_name=f"test_user_{i}",
                query_params=f"page={i}&size=10",
                request_headers={"Content-Type": "application/json"},
                request_body=f'{{"id": {i}}}',
                response_status=random.choice([200, 201, 400, 401, 403, 404, 500]),
                response_headers={"Content-Type": "application/json"},
                response_body='{"code": 0}',
                duration_ms=round(random.uniform(1.0, 5000.0), 2),
                error_type=None,
                error_message=None,
                error_traceback=None,
                resolved=False,
            )
        )
    await RadarRequest.bulk_create(req_seeds)
    req_ids = [r.id for r in await RadarRequest.all().order_by("-id").limit(COUNT)]

    # RadarQuery: 100条（FK request）
    q_seeds = []
    for i in range(COUNT):
        q_seeds.append(
            RadarQuery(
                request_id=random.choice(req_ids),
                sql_text=f"SELECT * FROM test_table WHERE id = {i+1}",
                params=None,
                operation=random.choice(["SELECT", "INSERT", "UPDATE", "DELETE"]),
                duration_ms=round(random.uniform(0.5, 500.0), 2),
                connection_name="conn_test",
                start_offset_ms=round(random.uniform(0.0, 100.0), 2),
            )
        )
    await RadarQuery.bulk_create(q_seeds)

    # RadarUserLog: 100条（FK request nullable）
    log_seeds = []
    for i in range(COUNT):
        log_seeds.append(
            RadarUserLog(
                request_id=random.choice(req_ids) if i % 5 != 0 else None,
                level=random.choice(["INFO", "DEBUG", "WARNING", "ERROR"]),
                message=f"测试日志消息 {i+1}",
                data='{"key": "value"}',
                source=f"test_source_{i+1}",
                offset_ms=round(random.uniform(0.0, 1000.0), 2),
            )
        )
    await RadarUserLog.bulk_create(log_seeds)


# ==================== Loan 模块（10张表，网贷）====================


async def gen_loan() -> None:
    # LoanCustomer: 100条（unique id_card）
    cust_seeds = []
    for i in range(1, COUNT + 1):
        cust_seeds.append(
            LoanCustomer(
                name=rand_name(),
                id_card=rand_id_card(),
                phone=rand_phone(),
                email=rand_email(i),
                gender=random.choice(["male", "female"]),
                birth_date=rand_datetime(365 * 50),
                credit_score=random.randint(350, 950),
                employment=f"测试单位 {i:04d}",
                monthly_income=rand_decimal(3000, 50000),
                status_type=StatusType.enable,
            )
        )
    await LoanCustomer.bulk_create(cust_seeds)
    cust_ids = [c.id for c in await LoanCustomer.all().order_by("-id").limit(COUNT)]

    # LoanProduct: 100条（unique code）
    prod_seeds = []
    for i in range(1, COUNT + 1):
        prod_seeds.append(
            LoanProduct(
                name=f"测试产品-{i:04d}",
                code=f"TEST-PROD-{i:04d}",
                product_type=random.choice(PRODUCT_TYPES),
                min_amount=Decimal("1000"),
                max_amount=Decimal(str(random.randint(50000, 500000))),
                min_term=1,
                max_term=random.choice([12, 24, 36, 48, 60]),
                annual_rate=Decimal(str(round(random.uniform(0.05, 0.24), 4))),
                status_type=StatusType.enable,
            )
        )
    await LoanProduct.bulk_create(prod_seeds)
    prod_ids = [p.id for p in await LoanProduct.all().order_by("-id").limit(COUNT)]

    # LoanApplication: 100条（unique application_no, FK customer, FK product）
    app_seeds = []
    for i in range(1, COUNT + 1):
        app_seeds.append(
            LoanApplication(
                application_no=f"TEST-APP-{i:04d}",
                customer_id=random.choice(cust_ids),
                product_id=random.choice(prod_ids),
                amount=rand_decimal(1000, 100000),
                term_months=random.choice([3, 6, 12, 24, 36]),
                purpose=random.choice(PURPOSES),
                status=random.choice(list(LoanStatus)),
            )
        )
    await LoanApplication.bulk_create(app_seeds)
    app_ids = [a.id for a in await LoanApplication.all().order_by("-id").limit(COUNT)]

    # LoanContract: 100条（unique contract_no, FK application, FK customer, FK product）
    contract_seeds = []
    for i in range(1, COUNT + 1):
        start = rand_datetime(365)
        term = random.choice([3, 6, 12, 24, 36])
        end = start + timedelta(days=term * 30)
        contract_seeds.append(
            LoanContract(
                contract_no=f"TEST-CTR-{i:04d}",
                application_id=random.choice(app_ids),
                customer_id=random.choice(cust_ids),
                product_id=random.choice(prod_ids),
                principal=rand_decimal(1000, 100000),
                annual_rate=Decimal(str(round(random.uniform(0.05, 0.24), 4))),
                term_months=term,
                start_date=start,
                end_date=end,
                status=random.choice([LoanStatus.active, LoanStatus.overdue, LoanStatus.settled]),
            )
        )
    await LoanContract.bulk_create(contract_seeds)
    contract_ids = [c.id for c in await LoanContract.all().order_by("-id").limit(COUNT)]

    # LoanRepaymentPlan: 100条（FK contract）
    plan_seeds = []
    for i in range(COUNT):
        due = rand_datetime(180)
        principal = rand_decimal(100, 10000)
        interest = rand_decimal(10, 1000)
        plan_seeds.append(
            LoanRepaymentPlan(
                contract_id=random.choice(contract_ids),
                period_no=(i % 12) + 1,
                due_date=due,
                principal=principal,
                interest=interest,
                total_amount=principal + interest,
                paid_amount=Decimal("0"),
                status=random.choice(list(RepaymentStatus)),
            )
        )
    await LoanRepaymentPlan.bulk_create(plan_seeds)

    # LoanPayment: 100条（unique transaction_no, FK contract）
    pay_seeds = []
    for i in range(1, COUNT + 1):
        pay_seeds.append(
            LoanPayment(
                contract_id=random.choice(contract_ids),
                plan_id=None,
                amount=rand_decimal(100, 10000),
                payment_method=random.choice(PAYMENT_METHODS),
                transaction_no=f"TEST-TXN-{i:04d}",
                status=random.choice(["success", "failed", "refunded"]),
            )
        )
    await LoanPayment.bulk_create(pay_seeds)

    # LoanRiskEvaluation: 100条（FK application, FK customer）
    risk_seeds = []
    for i in range(COUNT):
        risk_seeds.append(
            LoanRiskEvaluation(
                application_id=random.choice(app_ids),
                customer_id=random.choice(cust_ids),
                risk_score=random.randint(0, 100),
                decision=random.choice(list(RiskDecision)),
                model_version=f"v{random.randint(1, 3)}.{random.randint(0, 9)}",
                evaluator=f"风控员 {i+1}",
                remark=f"测试评估备注 {i+1}",
            )
        )
    await LoanRiskEvaluation.bulk_create(risk_seeds)

    # LoanCollection: 100条（FK contract, FK customer）
    coll_seeds = []
    for i in range(COUNT):
        coll_seeds.append(
            LoanCollection(
                contract_id=random.choice(contract_ids),
                customer_id=random.choice(cust_ids),
                overdue_days=random.randint(1, 180),
                collection_method=random.choice(COLLECTION_METHODS),
                collection_result=random.choice(list(CollectionResult)),
                collector=f"催收员 {i+1}",
                remark=f"测试催收备注 {i+1}",
            )
        )
    await LoanCollection.bulk_create(coll_seeds)

    # LoanFunder: 100条（unique name）
    funder_seeds = []
    for i in range(1, COUNT + 1):
        funder_seeds.append(
            LoanFunder(
                name=f"测试资金方-{i:04d}",
                funder_type=random.choice(FUNDER_TYPES),
                capital_pool=rand_decimal(100000, 10000000),
                contact_person=f"联系人 {i}",
                contact_phone=rand_phone(),
                status_type=StatusType.enable,
            )
        )
    await LoanFunder.bulk_create(funder_seeds)
    funder_ids = [f.id for f in await LoanFunder.all().order_by("-id").limit(COUNT)]

    # LoanFundMatching: 100条（FK contract, FK funder）
    match_seeds = []
    for i in range(COUNT):
        match_seeds.append(
            LoanFundMatching(
                contract_id=random.choice(contract_ids),
                funder_id=random.choice(funder_ids),
                matched_amount=rand_decimal(1000, 100000),
                status=random.choice(["matched", "canceled", "settled"]),
            )
        )
    await LoanFundMatching.bulk_create(match_seeds)


# ==================== 幂等清理 ====================


async def cleanup() -> None:
    """清理之前生成的测试数据（按前缀识别）。

    SQLite 不支持 DELETE 中的跨表 JOIN，需要先查 ID 再按 ID 删除。
    """
    # Loan
    test_contract_ids = [c.id for c in await LoanContract.filter(contract_no__startswith="TEST-CTR-")]
    if test_contract_ids:
        await LoanFundMatching.filter(contract_id__in=test_contract_ids).delete()
        await LoanRepaymentPlan.filter(contract_id__in=test_contract_ids).delete()
        await LoanPayment.filter(contract_id__in=test_contract_ids).delete()
        await LoanCollection.filter(contract_id__in=test_contract_ids).delete()
    test_app_ids = [a.id for a in await LoanApplication.filter(application_no__startswith="TEST-APP-")]
    if test_app_ids:
        await LoanRiskEvaluation.filter(application_id__in=test_app_ids).delete()
    await LoanFunder.filter(name__startswith="测试资金方-").delete()
    await LoanCollection.filter(collector__startswith="催收员 ").delete()
    await LoanRiskEvaluation.filter(evaluator__startswith="风控员 ").delete()
    await LoanPayment.filter(transaction_no__startswith="TEST-TXN-").delete()
    await LoanContract.filter(contract_no__startswith="TEST-CTR-").delete()
    await LoanApplication.filter(application_no__startswith="TEST-APP-").delete()
    await LoanProduct.filter(code__startswith="TEST-PROD-").delete()
    await LoanCustomer.filter(email__endswith="@test.example.com").delete()

    # Radar
    test_req_ids = [r.id for r in await RadarRequest.filter(x_request_id__startswith="test-req-")]
    if test_req_ids:
        await RadarQuery.filter(request_id__in=test_req_ids).delete()
        await RadarUserLog.filter(request_id__in=test_req_ids).delete()
    await RadarUserLog.filter(source__startswith="test_source_").delete()
    await RadarQuery.filter(sql_text__contains="FROM test_table WHERE").delete()
    await RadarRequest.filter(x_request_id__startswith="test-req-").delete()

    # BI
    test_session_ids = [s.id for s in await BiChatSession.filter(title__startswith="测试会话-")]
    if test_session_ids:
        await BiChatMessage.filter(session_id__in=test_session_ids).delete()
    test_table_ids = [t.id for t in await BiTable.filter(name__startswith="test_table_")]
    if test_table_ids:
        await BiColumn.filter(table_id__in=test_table_ids).delete()
        await BiIndex.filter(table_id__in=test_table_ids).delete()
        await BiForeignKey.filter(table_id__in=test_table_ids).delete()
    await BiQuotaConfig.filter(name__startswith="测试配额-").delete()
    await BiMaskingRule.filter(name__startswith="测试脱敏规则-").delete()
    await BiAuditLog.filter(username__startswith="test_user_").delete()
    test_provider_ids = [p.id for p in await BiLLMProvider.filter(name__startswith="测试Provider-")]
    if test_provider_ids:
        await BiLLMModel.filter(provider_id__in=test_provider_ids).delete()
    await BiLLMModel.filter(name__startswith="test-model-").delete()
    await BiLLMProvider.filter(name__startswith="测试Provider-").delete()
    await BiChatMessage.filter(content__startswith="测试消息内容 ").delete()
    await BiChatSession.filter(title__startswith="测试会话-").delete()
    await BiMetric.filter(code__startswith="test_metric_").delete()
    await BiForeignKey.filter(name__startswith="fk_test_").delete()
    await BiIndex.filter(name__startswith="idx_test_").delete()
    await BiColumn.filter(name__startswith="col_").delete()
    await BiTable.filter(name__startswith="test_table_").delete()
    await BiDatasource.filter(name__startswith="测试数据源-").delete()

    # HR
    test_emp_ids = [e.id for e in await Employee.filter(employee_no__startswith=f"{PREFIX}-EMP-")]
    if test_emp_ids:
        await EmployeeStatusLog.filter(employee_id__in=test_emp_ids).delete()
    await EmployeeStatusLog.filter(remark__startswith="测试日志 ").delete()
    await Employee.filter(employee_no__startswith=f"{PREFIX}-EMP-").delete()
    await Tag.filter(name__startswith="测试标签-").delete()
    await Department.filter(code__startswith=f"{PREFIX}-DEPT-").delete()


# ==================== 主流程 ====================


async def main() -> None:
    print(f"[gen_test_data] 数据库: {APP_SETTINGS.DB_URL}")
    print("[gen_test_data] 清理旧的测试数据...")
    await cleanup()

    print(f"[gen_test_data] 开始生成 HR 模块数据（每表 {COUNT} 条）...")
    await gen_hr([], [])

    print(f"[gen_test_data] 开始生成 BI 模块数据（每表 {COUNT} 条）...")
    await gen_bi()

    print(f"[gen_test_data] 开始生成 Radar 模块数据（每表 {COUNT} 条）...")
    await gen_radar()

    print(f"[gen_test_data] 开始生成 Loan 模块数据（每表 {COUNT} 条）...")
    await gen_loan()

    print("[gen_test_data] 完成。")


if __name__ == "__main__":
    async def _run() -> None:
        await Tortoise.init(config=APP_SETTINGS.TORTOISE_ORM)
        try:
            await main()
        finally:
            await Tortoise.close_connections()

    asyncio.run(_run())
