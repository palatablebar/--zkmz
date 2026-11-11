/** 与后端 app/constants/error_codes.py 一一对应。 */
export const ERROR_MESSAGES: Record<string, string> = {
  'FP-3001': '未登录或登录已过期',
  'FP-3002': '当前角色无权执行该操作',
  'FP-3003': '请求过于频繁',
  'FP-3004': '今日样本构建配额已用尽',
  'FP-3005': '特征定义不存在',
  'FP-3006': '特征编码已存在',
  'FP-3007': '特征窗口或聚合口径非法',
  'FP-3008': '已发布版本不可直接修改',
  'FP-3009': '标签集不存在',
  'FP-3010': '样本任务不存在',
  'FP-3011': '样本任务状态不允许该操作',
  'FP-3012': '回填任务不存在',
  'FP-3013': '回填时间范围非法',
  'FP-3014': '事件或标签时间戳无法解析',
  'FP-3015': '样本在窗口内没有任何事件',
  'FP-3016': '请求参数校验失败',
}

export function describeError(code: string | undefined, fallback: string): string {
  if (!code) return fallback
  return ERROR_MESSAGES[code] ? `${ERROR_MESSAGES[code]}（${code}）` : `${fallback}（${code}）`
}
