"""Central error-code catalogue + AppError.

FP-3001 .. FP-3016 are referenced by services/controllers and by
frontend/src/constants/errorCodes.ts.
"""
from enum import Enum


class ErrorCode(str, Enum):
    UNAUTHORIZED = "FP-3001"
    FORBIDDEN = "FP-3002"
    RATE_LIMITED = "FP-3003"
    QUOTA_EXHAUSTED = "FP-3004"
    FEATURE_NOT_FOUND = "FP-3005"
    FEATURE_CODE_DUPLICATED = "FP-3006"
    FEATURE_WINDOW_INVALID = "FP-3007"
    FEATURE_PUBLISHED_LOCKED = "FP-3008"
    LABEL_SET_NOT_FOUND = "FP-3009"
    JOB_NOT_FOUND = "FP-3010"
    JOB_STATE_INVALID = "FP-3011"
    BACKFILL_NOT_FOUND = "FP-3012"
    BACKFILL_RANGE_INVALID = "FP-3013"
    BAD_TIMESTAMP = "FP-3014"
    NO_EVENT = "FP-3015"
    VALIDATION_FAILED = "FP-3016"


ERROR_MESSAGES = {
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    ErrorCode.FORBIDDEN: "当前角色无权执行该操作",
    ErrorCode.RATE_LIMITED: "请求过于频繁",
    ErrorCode.QUOTA_EXHAUSTED: "今日样本构建配额已用尽",
    ErrorCode.FEATURE_NOT_FOUND: "特征定义不存在",
    ErrorCode.FEATURE_CODE_DUPLICATED: "特征编码已存在",
    ErrorCode.FEATURE_WINDOW_INVALID: "特征窗口或聚合口径非法",
    ErrorCode.FEATURE_PUBLISHED_LOCKED: "已发布版本不可直接修改，请新建版本",
    ErrorCode.LABEL_SET_NOT_FOUND: "标签集不存在",
    ErrorCode.JOB_NOT_FOUND: "样本任务不存在",
    ErrorCode.JOB_STATE_INVALID: "样本任务状态不允许该操作",
    ErrorCode.BACKFILL_NOT_FOUND: "回填任务不存在",
    ErrorCode.BACKFILL_RANGE_INVALID: "回填时间范围非法",
    ErrorCode.BAD_TIMESTAMP: "事件或标签时间戳无法解析",
    ErrorCode.NO_EVENT: "样本在窗口内没有任何事件",
    ErrorCode.VALIDATION_FAILED: "请求参数校验失败",
}

ERROR_STATUS = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.QUOTA_EXHAUSTED: 429,
    ErrorCode.FEATURE_NOT_FOUND: 404,
    ErrorCode.FEATURE_CODE_DUPLICATED: 409,
    ErrorCode.FEATURE_WINDOW_INVALID: 400,
    ErrorCode.FEATURE_PUBLISHED_LOCKED: 409,
    ErrorCode.LABEL_SET_NOT_FOUND: 404,
    ErrorCode.JOB_NOT_FOUND: 404,
    ErrorCode.JOB_STATE_INVALID: 409,
    ErrorCode.BACKFILL_NOT_FOUND: 404,
    ErrorCode.BACKFILL_RANGE_INVALID: 400,
    ErrorCode.BAD_TIMESTAMP: 400,
    ErrorCode.NO_EVENT: 409,
    ErrorCode.VALIDATION_FAILED: 400,
}


class AppError(Exception):
    def __init__(self, code, message=None, detail=None, context=None, status_code=None):
        self.code = code.value if isinstance(code, ErrorCode) else str(code)
        try:
            enum_code = ErrorCode(self.code)
        except ValueError:
            enum_code = None
        self.message = message or (ERROR_MESSAGES.get(enum_code, "请求处理失败") if enum_code else "请求处理失败")
        if context:
            self.message = f"{self.message}（{context}）"
        self.detail = detail
        self.status_code = status_code or (ERROR_STATUS.get(enum_code, 400) if enum_code else 400)
        super().__init__(self.message)
