"""工序卡（recipe-sheet）常量：页面上的工序编号与批注文案。

UI 用它们渲染左侧工序编号，后端 /meta 也返回同一份，保证前后端工序号一致。
"""
OPERATION_STEPS = [
    {"code": "01", "key": "features", "title": "特征配方", "hint": "定义实体键、事件源、聚合窗口"},
    {"code": "02", "key": "samples", "title": "样本炼制", "hint": "选标签集与特征版本，生成参数快照"},
    {"code": "03", "key": "pit", "title": "点时间校验", "hint": "泄漏矩阵 + 边界探针"},
    {"code": "04", "key": "backfill", "title": "回填一致性", "hint": "full vs incremental checksum"},
    {"code": "05", "key": "versions", "title": "版本与发布", "hint": "版本轨迹与审计"},
]

MARGIN_NOTES = {
    "features": "窗口右端必须排除标签时刻；inclusive 会吞掉同一时刻事件，离线 AUC 会虚高。",
    "samples": "参数快照一经运行不可变；重跑会重建样本，但快照留痕。",
    "pit": "泄漏检测口径：窗口内任意事件 ts >= 标签时间即泄漏，越界毫秒 = ts - 标签时间。",
    "backfill": "不变量：full == incremental；否则必须给出差异样本数与首个差异位置。",
    "versions": "发布后的定义冻结，修改需新建版本；审计轨迹不可改。",
}
