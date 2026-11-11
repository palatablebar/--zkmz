"""Shared enumerations — the single source of truth for the backend.

frontend/src/constants/enums.ts mirrors every value here (README lists all
occurrence sites). Anything that is persisted or compared across the stack
MUST come from this module.
"""
from enum import Enum


class Role(str, Enum):
    OWNER = "owner"        # 特征负责人：全部写 + 发布 + 回填
    ANALYST = "analyst"    # 算法工程师：建样本任务、看报告；特征定义只读
    VIEWER = "viewer"      # 风控审计：只读


class BoundaryPolicy(str, Enum):
    """Right edge of the lookback window."""

    STRICT = "strict"        # [label_time - W, label_time)
    INCLUSIVE = "inclusive"  # (label_time - W, label_time]  <- 会吞掉同一时刻事件


class AggregateKind(str, Enum):
    SUM = "sum"
    COUNT = "count"
    MAX = "max"
    LAST = "last"
    RECENCY_DAYS = "recency_days"  # last 的派生：距最近匹配事件的天数


class EventType(str, Enum):
    APPLY = "apply"    # 申请
    REPAY = "repay"    # 还款
    LOGIN = "login"    # 登录


class FeatureStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class JobKind(str, Enum):
    SAMPLE_BUILD = "sample_build"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureReason(str, Enum):
    BAD_TIMESTAMP = "bad_timestamp"
    NO_EVENT = "no_event"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    NO_FEATURE = "no_feature"


class LeakKind(str, Enum):
    BOUNDARY_EQUAL = "boundary_equal"       # 事件时间戳 == 标签时间
    BOUNDARY_OVER = "boundary_over"         # 事件时间戳 > 标签时间
    POLICY_MISMATCH = "policy_mismatch"     # 声明 strict 却按 inclusive 执行


class BackfillMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class BackfillStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MismatchReason(str, Enum):
    WINDOW_BOUNDARY = "window_boundary"
    OUT_OF_ORDER = "out_of_order"
    DUPLICATE_EVENT = "duplicate_event"
    NONE = "none"


class AuditAction(str, Enum):
    LOGIN = "login"
    FEATURE_CREATE = "feature_create"
    FEATURE_UPDATE = "feature_update"
    FEATURE_BOUNDARY_FIX = "feature_boundary_fix"
    FEATURE_PUBLISH = "feature_publish"
    JOB_CREATE = "job_create"
    JOB_RUN = "job_run"
    BACKFILL_CREATE = "backfill_create"
    BACKFILL_RUN = "backfill_run"


ROLE_LABELS = {
    Role.OWNER: "特征负责人",
    Role.ANALYST: "算法工程师",
    Role.VIEWER: "风控审计",
}

BOUNDARY_LABELS = {
    BoundaryPolicy.STRICT: "开区间（右端排除标签时刻）",
    BoundaryPolicy.INCLUSIVE: "闭区间（右端含标签时刻）",
}
