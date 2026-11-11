/** 工序卡常量：与后端 app/constants/recipes.py 保持一致。 */
export const OPERATION_STEPS = [
  { code: '01', key: 'features', title: '特征配方', to: '/features' },
  { code: '02', key: 'samples', title: '样本炼制', to: '/samples/new' },
  { code: '03', key: 'pit', title: '点时间校验', to: '/samples/new' },
  { code: '04', key: 'backfill', title: '回填一致性', to: '/backfills' },
  { code: '05', key: 'versions', title: '版本与发布', to: '/features' },
]

export const MARGIN_NOTES: Record<string, string> = {
  features: '窗口右端必须排除标签时刻。inclusive 会把「标签时刻当刻」的事件算进特征，离线 AUC 会虚高。',
  samples: '参数快照冻结创建时的口径与版本，重跑用当前已发布定义——所以修正边界后重跑立即生效。',
  pit: '泄漏口径：窗口内任意事件 ts ≥ 标签时间即泄漏，越界毫秒 = ts − 标签时间。',
  backfill: '不变量：full == incremental。不成立时必须给出差异样本数与首个差异位置。',
  versions: '发布后的定义冻结，修改需新建版本；审计轨迹不可改。',
}
