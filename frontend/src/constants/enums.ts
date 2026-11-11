/** 与后端 app/constants/enums.py 一一对应（README 列出全部出现位置）。 */
export const ROLE = {
  OWNER: 'owner',
  ANALYST: 'analyst',
  VIEWER: 'viewer',
} as const

export const ROLE_LABEL: Record<string, string> = {
  owner: '特征负责人',
  analyst: '算法工程师',
  viewer: '风控审计',
}

export const BOUNDARY = {
  STRICT: 'strict',
  INCLUSIVE: 'inclusive',
} as const

export const BOUNDARY_LABEL: Record<string, string> = {
  strict: 'strict · 右端开区间',
  inclusive: 'inclusive · 右端含标签时刻',
}

export const AGGREGATE = ['sum', 'count', 'max', 'last', 'recency_days'] as const
export const WINDOWS = ['1d', '7d', '30d'] as const
export const EVENT_TYPES = ['apply', 'repay', 'login'] as const

export const EVENT_TYPE_LABEL: Record<string, string> = {
  apply: '申请',
  repay: '还款',
  login: '登录',
}

export const FEATURE_STATUS: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  deprecated: '已废弃',
}

export const JOB_STATUS: Record<string, string> = {
  pending: '待运行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

export const BACKFILL_STATUS: Record<string, string> = {
  pending: '待运行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

export const LEAK_KIND: Record<string, string> = {
  boundary_equal: '边界相同（越界 0ms）',
  boundary_over: '越过标签时间',
  policy_mismatch: '口径与声明不一致',
}

export const FAILURE_REASON: Record<string, string> = {
  bad_timestamp: '时间戳无法解析',
  no_event: '窗口内无事件',
  insufficient_samples: '样本不足',
  no_feature: '未选择特征',
}
