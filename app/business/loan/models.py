# pyright: reportIncompatibleVariableOverride=false
"""网贷业务模块 Tortoise ORM 模型。

10 个模型，表名统一 ``biz_loan_*`` 前缀：

- 客户与产品：LoanCustomer / LoanProduct
- 申请与合同：LoanApplication / LoanContract
- 还款：LoanRepaymentPlan / LoanPayment
- 风控与催收：LoanRiskEvaluation / LoanCollection
- 资金：LoanFunder / LoanFundMatching

FK 关联引用本模块内模型时使用 ``app_system.<Model>`` 字符串
（业务模块默认注册到 ``app_system`` app label，与 ``app/system`` 共享连接）。
"""

from enum import Enum

from tortoise import fields

from app.utils import AuditMixin, BaseModel, SoftDeleteManager, SoftDeleteMixin, StatusType

# ==================== 枚举 ====================


class LoanStatus(str, Enum):
    """借款申请/合同状态枚举。"""

    pending = "pending"  # 申请待审核
    approved = "approved"  # 已批准
    rejected = "rejected"  # 已拒绝
    active = "active"  # 合同生效中
    overdue = "overdue"  # 逾期
    settled = "settled"  # 已结清
    canceled = "canceled"  # 已取消


class RepaymentStatus(str, Enum):
    """还款状态枚举。"""

    unpaid = "unpaid"  # 未还款
    partial = "partial"  # 部分还款
    paid = "paid"  # 已还清
    overdue = "overdue"  # 逾期


class RiskDecision(str, Enum):
    """风控决策枚举。"""

    approve = "approve"  # 通过
    reject = "reject"  # 拒绝
    manual = "manual"  # 人工复审


class CollectionResult(str, Enum):
    """催收结果枚举。"""

    success = "success"  # 已还款
    partial = "partial"  # 部分还款
    failed = "failed"  # 未还款
    unreachable = "unreachable"  # 联系不上


# ==================== 客户与产品 ====================


class LoanCustomer(BaseModel, AuditMixin, SoftDeleteMixin):
    """借款客户"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=50, description="客户姓名")
    id_card = fields.CharField(max_length=20, unique=True, description="身份证号")
    phone = fields.CharField(max_length=20, index=True, description="手机号")
    email = fields.CharField(max_length=100, null=True, blank=True, description="邮箱")
    gender = fields.CharField(max_length=10, null=True, blank=True, description="性别（male/female）")
    birth_date = fields.DatetimeField(null=True, description="出生日期")
    credit_score = fields.IntField(default=600, description="信用分（350-950）")
    employment = fields.CharField(max_length=100, null=True, blank=True, description="就业单位")
    monthly_income = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="月收入")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "biz_loan_customer"
        manager = SoftDeleteManager()


class LoanProduct(BaseModel, AuditMixin):
    """借款产品"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="产品名称")
    code = fields.CharField(max_length=50, unique=True, description="产品编码")
    product_type = fields.CharField(max_length=30, description="产品类型（信用贷/抵押贷/消费贷/经营贷）")
    min_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=1000, description="最小借款金额")
    max_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=100000, description="最大借款金额")
    min_term = fields.IntField(default=1, description="最短期限（月）")
    max_term = fields.IntField(default=36, description="最长期限（月）")
    annual_rate = fields.DecimalField(max_digits=6, decimal_places=4, default=0.1000, description="年化利率（小数，0.1=10%）")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "biz_loan_product"


# ==================== 申请与合同 ====================


class LoanApplication(BaseModel, AuditMixin):
    """借款申请"""

    id = fields.IntField(primary_key=True, description="主键ID")
    application_no = fields.CharField(max_length=50, unique=True, description="申请单号")
    customer_id: int
    customer: fields.ForeignKeyRelation[LoanCustomer] = fields.ForeignKeyField("app_system.LoanCustomer", related_name="applications", on_delete=fields.CASCADE, description="借款客户")
    product_id: int
    product: fields.ForeignKeyRelation[LoanProduct] = fields.ForeignKeyField("app_system.LoanProduct", related_name="applications", on_delete=fields.RESTRICT, description="申请产品")
    amount = fields.DecimalField(max_digits=12, decimal_places=2, description="申请金额")
    term_months = fields.IntField(description="申请期限（月）")
    purpose = fields.CharField(max_length=500, null=True, blank=True, description="借款用途")
    status = fields.CharEnumField(enum_type=LoanStatus, default=LoanStatus.pending, index=True, description="申请状态")
    applied_at = fields.DatetimeField(auto_now_add=True, description="申请时间")

    class Meta:
        table = "biz_loan_application"


class LoanContract(BaseModel, AuditMixin):
    """借款合同"""

    id = fields.IntField(primary_key=True, description="主键ID")
    contract_no = fields.CharField(max_length=50, unique=True, description="合同编号")
    application_id: int
    application: fields.ForeignKeyRelation[LoanApplication] = fields.ForeignKeyField("app_system.LoanApplication", related_name="contracts", on_delete=fields.RESTRICT, description="关联申请")
    customer_id: int
    customer: fields.ForeignKeyRelation[LoanCustomer] = fields.ForeignKeyField("app_system.LoanCustomer", related_name="contracts", on_delete=fields.CASCADE, description="借款客户")
    product_id: int
    product: fields.ForeignKeyRelation[LoanProduct] = fields.ForeignKeyField("app_system.LoanProduct", related_name="contracts", on_delete=fields.RESTRICT, description="借款产品")
    principal = fields.DecimalField(max_digits=12, decimal_places=2, description="合同本金")
    annual_rate = fields.DecimalField(max_digits=6, decimal_places=4, description="年化利率")
    term_months = fields.IntField(description="期限（月）")
    start_date = fields.DatetimeField(description="起贷日期")
    end_date = fields.DatetimeField(description="到期日期")
    status = fields.CharEnumField(enum_type=LoanStatus, default=LoanStatus.active, index=True, description="合同状态")

    class Meta:
        table = "biz_loan_contract"


# ==================== 还款 ====================


class LoanRepaymentPlan(BaseModel, AuditMixin):
    """还款计划（每期一条）"""

    id = fields.IntField(primary_key=True, description="主键ID")
    contract_id: int
    contract: fields.ForeignKeyRelation[LoanContract] = fields.ForeignKeyField("app_system.LoanContract", related_name="repayment_plans", on_delete=fields.CASCADE, description="所属合同")
    period_no = fields.IntField(description="期次（1-based）")
    due_date = fields.DatetimeField(description="应还日期")
    principal = fields.DecimalField(max_digits=12, decimal_places=2, description="应还本金")
    interest = fields.DecimalField(max_digits=12, decimal_places=2, description="应还利息")
    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, description="应还总额")
    paid_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="已还金额")
    status = fields.CharEnumField(enum_type=RepaymentStatus, default=RepaymentStatus.unpaid, index=True, description="还款状态")

    class Meta:
        table = "biz_loan_repayment_plan"


class LoanPayment(BaseModel, AuditMixin):
    """还款记录"""

    id = fields.IntField(primary_key=True, description="主键ID")
    contract_id: int
    contract: fields.ForeignKeyRelation[LoanContract] = fields.ForeignKeyField("app_system.LoanContract", related_name="payments", on_delete=fields.CASCADE, description="所属合同")
    plan_id = fields.IntField(null=True, description="关联还款计划ID（可空，代表提前还款）")
    amount = fields.DecimalField(max_digits=12, decimal_places=2, description="还款金额")
    paid_at = fields.DatetimeField(auto_now_add=True, description="还款时间")
    payment_method = fields.CharField(max_length=30, description="还款方式（bank/alipay/wechat/offset）")
    transaction_no = fields.CharField(max_length=64, unique=True, description="交易流水号")
    status = fields.CharField(max_length=20, default="success", description="状态（success/failed/refunded）")

    class Meta:
        table = "biz_loan_payment"


# ==================== 风控与催收 ====================


class LoanRiskEvaluation(BaseModel, AuditMixin):
    """风控评估记录"""

    id = fields.IntField(primary_key=True, description="主键ID")
    application_id: int
    application: fields.ForeignKeyRelation[LoanApplication] = fields.ForeignKeyField("app_system.LoanApplication", related_name="risk_evaluations", on_delete=fields.CASCADE, description="关联申请")
    customer_id: int
    customer: fields.ForeignKeyRelation[LoanCustomer] = fields.ForeignKeyField("app_system.LoanCustomer", related_name="risk_evaluations", on_delete=fields.CASCADE, description="客户")
    risk_score = fields.IntField(description="风控评分（0-100，越高越安全）")
    decision = fields.CharEnumField(enum_type=RiskDecision, default=RiskDecision.manual, description="风控决策")
    model_version = fields.CharField(max_length=30, default="v1.0", description="风控模型版本")
    evaluator = fields.CharField(max_length=50, null=True, blank=True, description="评估人")
    remark = fields.CharField(max_length=500, null=True, blank=True, description="评估备注")

    class Meta:
        table = "biz_loan_risk_evaluation"


class LoanCollection(BaseModel, AuditMixin):
    """催收记录"""

    id = fields.IntField(primary_key=True, description="主键ID")
    contract_id: int
    contract: fields.ForeignKeyRelation[LoanContract] = fields.ForeignKeyField("app_system.LoanContract", related_name="collections", on_delete=fields.CASCADE, description="所属合同")
    customer_id: int
    customer: fields.ForeignKeyRelation[LoanCustomer] = fields.ForeignKeyField("app_system.LoanCustomer", related_name="collections", on_delete=fields.CASCADE, description="客户")
    overdue_days = fields.IntField(description="逾期天数")
    collection_method = fields.CharField(max_length=30, description="催收方式（sms/phone/letter/visit/legal）")
    collection_result = fields.CharEnumField(enum_type=CollectionResult, default=CollectionResult.failed, description="催收结果")
    collected_at = fields.DatetimeField(auto_now_add=True, description="催收时间")
    collector = fields.CharField(max_length=50, null=True, blank=True, description="催收员")
    remark = fields.CharField(max_length=500, null=True, blank=True, description="催收备注")

    class Meta:
        table = "biz_loan_collection"


# ==================== 资金 ====================


class LoanFunder(BaseModel, AuditMixin):
    """资金方"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, unique=True, description="资金方名称")
    funder_type = fields.CharField(max_length=30, description="类型（bank/trust/individual/institution）")
    capital_pool = fields.DecimalField(max_digits=15, decimal_places=2, default=0, description="资金池余额")
    contact_person = fields.CharField(max_length=50, null=True, blank=True, description="联系人")
    contact_phone = fields.CharField(max_length=20, null=True, blank=True, description="联系电话")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "biz_loan_funder"


class LoanFundMatching(BaseModel, AuditMixin):
    """资金匹配记录"""

    id = fields.IntField(primary_key=True, description="主键ID")
    contract_id: int
    contract: fields.ForeignKeyRelation[LoanContract] = fields.ForeignKeyField("app_system.LoanContract", related_name="fund_matchings", on_delete=fields.CASCADE, description="所属合同")
    funder_id: int
    funder: fields.ForeignKeyRelation[LoanFunder] = fields.ForeignKeyField("app_system.LoanFunder", related_name="matchings", on_delete=fields.RESTRICT, description="资金方")
    matched_amount = fields.DecimalField(max_digits=12, decimal_places=2, description="匹配金额")
    matched_at = fields.DatetimeField(auto_now_add=True, description="匹配时间")
    status = fields.CharField(max_length=20, default="matched", description="状态（matched/canceled/settled）")

    class Meta:
        table = "biz_loan_fund_matching"
