# FeatPoint · 特征平台点时间正确性与回填（`featpoint`）

岚舟科技 · 风控算法组的特征工艺卡：把「按天写 SQL 拼特征」改造成可审计的配方单流程——
每个特征定义一张工艺卡（事件源 / 窗口 / 边界 / 聚合口径），每条训练样本一份点时间校验记录，
每次回填给出一份 `full == incremental` 的一致性证明。

一句话：**用 Python 真算的 point-in-time join + 回填一致性校验，堵住离线 AUC 0.89 / 线上 0.71 的特征泄漏。**

## 1. 真实场景

* **模拟客户**：岚舟科技（杭州，消费贷风控）· 风控算法组 9 人。
* **现有工作流**：算法同学每天写离线 SQL 跑特征（Hive + 调度平台），训练样本直接 join
  「当天最新值」；特征口径散落在 SQL 与 Confluence 文档里。
* **三个痛点**：
  1. 特征窗口越过标签时间 → 训练集泄漏，离线 AUC 0.89 而线上 0.71，排查两周；
  2. 特征回填（backfill）后无法证明与全量重算一致，只能抽样对数；
  3. 口径散落、版本不可追溯，两个人对同一特征给出不同窗口。
* **上下游**：上游 = 账户事件表（申请 / 还款 / 登录，1200 条 demo 事件）+ 标签集（2 × 400 样本键）；
  本系统替代「手写 SQL + 人工检查泄漏」这一段；下游 = 训练平台读样本表、风控审计复核口径与版本。

## 2. 角色与演示账号（密码统一 `Demo@2026`）

| 角色（enum） | 账号 | 主要页面 | 权限 | 典型动作 |
|---|---|---|---|---|
| `owner` 特征负责人 | owner@featpoint.demo | 全部 | 全部写 + 发布 + 回填 | 建/改特征定义、发布、发起回填 |
| `analyst` 算法工程师 | analyst@featpoint.demo | 样本 / 校验 | 读写样本，特征定义只读 | 建样本任务、看泄漏报告（改定义 → **403**） |
| `viewer` 风控审计 | viewer@featpoint.demo | 校验报告 / 版本 | 只读 | 复核泄漏与版本轨迹 |

## 3. 两个核心算法（Python 真算，结果落库，前端只展示）

### A. 点时间 join 与泄漏检测 —— `backend/src/services/pit_engine.py`

* **输入**：标签集 `(entity_id, label_time, label)`、特征定义 `(窗口 W、边界 strict|inclusive、聚合口径、过滤条件)`、事件表。
* **窗口口径**：
  * `strict` = `[label_time − W, label_time)`（右端开区间，正确口径）
  * `inclusive` = `(label_time − W, label_time]`（右端含标签时刻，**泄漏来源**）
* **聚合**：`sum` / `count` / `max` / `last`，另有 `recency_days`（last 的派生：距最近一条匹配事件的天数，无事件记 −1）。
* **泄漏检测**：样本某特征窗口内任意事件 `event_ts >= label_time` 即为泄漏；
  `overflow_ms = round((event_ts − label_time) × 1000)`，并记录 `kind`
  （`boundary_equal` 越界 0ms / `boundary_over` 越界 > 0ms）与特征名。
* **边界探针**：对首个特征合成 `−1ms / 0ms / +1ms` 三个事件，用同一个 `includes_event()`
  输出 strict / inclusive 判定表（off-by-one 探针）。
* **失败态**：时间戳无法归一 → job `failed`，`reason=bad_timestamp`；
  窗口内没有任何事件 → 特征记 0（recency 记 −1），样本标 `no_event`（不 fail 整个 job）；
  范围内无标签样本 → `insufficient_samples`。

### B. 多窗口聚合 + 全量/增量一致性 —— `backend/src/services/agg_engine.py`

* **窗口**：`1d` / `7d` / `30d`，每窗口统计 `cnt` / `amount_sum` / `amount_max` / `last_ts`。
* **两遍计算**：
  * full = 范围内全部事件重算；
  * incremental = 基准快照（事件时间 ≤ 基准水位）+ 新增事件（> 水位，含迟到事件）按窗口合并。
* **校验**：逐样本把特征 JSON 规范化（`json.dumps(sort_keys=True)`）后取 `md5`，
  比较两遍的 md5；输出**差异样本数**、**首个差异位置**、**不一致原因分类**
  （`window_boundary` / `out_of_order` / `duplicate_event`）。
* **不变量**：`full == incremental`（不成立时 `invariant_hold=false` 并标 `inconsistent`）。
* **负例对照**：把窗口右端人为放宽 60s 重算一遍，用同一个比对器必须报出差异并归因
  `window_boundary`——证明「相等」不是比对器空转。

两个算法都能独立自测：

```bash
docker compose exec -T backend python -m src.services.pit_engine
docker compose exec -T backend python -m src.services.agg_engine
```

## 4. 快速启动

```bash
cp .env.example .env
docker compose up -d --build          # 5 个服务：frontend / backend / worker / db / redis
docker compose ps                     # 等 5/5 healthy
# seed 已由 SEED_DEMO=true 在 backend 启动时自动执行一次；也可手动：
docker compose exec -T backend python -m scripts.seed_demo
```

访问：<http://localhost:18227>（前端）· <http://localhost:19227/health>（后端健康检查）·
PostgreSQL 映射在宿主机 `17727`。

> 端口来自 `.env`：`FRONTEND_PORT=18227` / `BACKEND_PORT=19227` / `DB_PORT=17727`。

## 5. 页面（6）

| 路由 | 工序 | 内容 |
|---|---|---|
| `/login` | 00 | 工艺卡封面登录（手输账号，无快捷切换按钮） |
| `/features` | 01 | 特征定义列表 + 配方单编辑（DSL 预览、窗口/边界校验，共用 `FeatureDefinitionCard`） |
| `/features/:id/versions` | 05 | 版本轨迹 + 审计轨迹 + 最近一次泄漏矩阵（复用 `LeakMatrix`） |
| `/samples/new` | 02 | 样本构建（标签集/特征多选、参数快照预览，复用 `FeatureDefinitionCard` 口径摘要） |
| `/samples/:id` | 03 | 点时间校验报告：泄漏矩阵 + 边界探针 + 泄漏明细 + 样本预览 |
| `/backfills` | 04 | 回填任务：full vs incremental checksum 对照 + 差异明细 + 负例对照 |

## 6. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3.4 + TypeScript 5.6 + Vite 5（Nginx 1.27 托管构建产物） |
| 后端 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 |
| 异步 | Celery 5.4 + Redis 7（样本构建 / 回填任务在 worker 真跑） |
| 数据库 | PostgreSQL 16 |
| 鉴权 | PyJWT（HS256）+ 三角色 RBAC + 审计日志 + 限流/配额中间件 |
| 密码 | 标准库 PBKDF2-SHA256（12 万轮），无原生依赖 |

## 7. 目录

```
gb-554/
├── docker-compose.yml         # 5 服务 + 命名卷 + healthcheck，顶层 name: featpoint
├── .env / .env.example        # 端口、DB、JWT、SEED_DEMO
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── migrations/            # 0001_initial.sql 参考 DDL + 说明
│   ├── scripts/seed_demo.py   # 幂等 seed，打印一行 SEED_SUMMARY
│   └── src/
│       ├── config/            # settings / database / celery_app
│       ├── constants/         # enums（共享枚举）/ error_codes / recipes（工序卡）
│       ├── models/            # user, feature(+version), event, label(+row), sample(+row), backfill, audit_log
│       ├── schemas/           # pydantic DTO
│       ├── services/          # pit_engine ★ / agg_engine ★ / feature / sample / backfill / catalogue / auth
│       ├── controllers/       # 处理函数（被 routes 调用）
│       ├── routes/            # FastAPI APIRouter 装配
│       ├── middlewares/       # auth / rbac / quota（限流+配额）/ audit_logger / error_handler
│       ├── utils/             # jwt / password / logger / timefmt / serialize
│       └── tasks/             # Celery：sample_job / backfill
├── worker/                    # Dockerfile + entrypoint.sh + healthy.py（心跳 healthcheck）
└── frontend/
    ├── Dockerfile / nginx.conf / vite.config.ts / tsconfig.json
    └── src/{api,stores,types,components/{common,feature,sample,backfill},hooks,pages,router,utils,constants,styles}
```

## 8. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `FRONTEND_PORT` / `BACKEND_PORT` / `DB_PORT` | 18227 / 19227 / 17727 | 宿主机端口 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | featpoint / featpoint / featpoint_pwd | PostgreSQL |
| `JWT_SECRET` / `JWT_EXPIRE_HOURS` | demo 值 / 8 | 令牌 |
| `SEED_DEMO` | true | 启动时自动执行一次 seed（失败只记日志） |
| `RATE_WINDOW_SECONDS` / `RATE_WINDOW_MAX` | 60 / 60 | 每用户每分钟写请求限流 |
| `DAILY_RUN_QUOTA` | 20 | 每用户每日运行配额（viewer 为 0） |

## 9. 共享枚举出现位置（≥2 组，前后端各一份）

| 枚举组 | 后端定义 | 前端定义 | 主要使用点 |
|---|---|---|---|
| 角色 `Role` | `src/constants/enums.py` | `src/constants/enums.ts` | `middlewares/rbac.py`、`utils/serialize.py`、`stores/auth.ts`、各页面权限提示 |
| 边界策略 `BoundaryPolicy` | `src/constants/enums.py` | `src/constants/enums.ts` | `services/pit_engine.py`、`services/feature_service.py`、`components/feature/WindowEditor.vue`、`FeatureDefinitionCard.vue` |
| 聚合口径 `AggregateKind` | 同上 | 同上 | `pit_engine.aggregate()`、`WindowEditor.vue` |
| 事件类型 `EventType` | 同上 | 同上 | seed、`schemas/feature.py`、`catalogue_service.py` |
| 任务状态 `JobStatus` / `BackfillStatus` | 同上 | 同上 | `sample_service.py`、`backfill_service.py`、`StatusTag.vue` |
| 泄漏类型 `LeakKind` | 同上 | 同上 | `pit_engine.detect_leak()`、`SampleDetailPage.vue` |
| 错误码 `ErrorCode` | `src/constants/error_codes.py` | `src/constants/errorCodes.ts` | 后端 `AppError`；前端 `describeError()` |

共享前端组件：`FeatureDefinitionCard`（/features 与 /samples/new）、`LeakMatrix`
（/samples/:id 与 /features/:id/versions）、`PageHeader`、`AppShell`、`ErrorNotice`、`StatusTag`、`QuotaMeter`、`PermitNotice`。
Hooks/utils：`hooks/useApi.ts`、`hooks/useLeakMatrix.ts`、`utils/format.ts`、`utils/leakTone.ts`。
后端中间件：`auth.py`、`rbac.py`、`quota.py`、`audit_logger.py`、`error_handler.py`。

## 10. 视觉方向

车间工艺卡 / 配方单：牛皮纸底 `oklch(0.94 0.02 80)`、油墨蓝黑 `oklch(0.30 0.03 250)`、
批注红 `oklch(0.55 0.18 30)`；双字体 **Fraunces**（标题/正文衬线）+ **Space Mono**（数字/表格/工号）；
左工序编号栏 + 中央配方单 + 右侧批注栏的非对称三栏、虚线撕线（`.tear`）、工序编号 00–05；
1 个高价值动效：泄漏矩阵逐格点亮（`opacity/transform` + 指数缓动 `cubic-bezier(0.16,1,0.3,1)`）。
响应式断点 ≥1280 / ≥768 / <768。

## 11. Docker 说明

* 恰好 5 个服务，全部有 healthcheck：`db`（pg_isready）、`redis`（redis-cli ping）、
  `backend`（`/health`）、`worker`（心跳文件 `/tmp/featpoint-worker-heartbeat`）、`frontend`（`/healthz`）。
* `backend` / `worker` 依赖 `db`、`redis` 的 `service_healthy`；`frontend` 依赖 `backend` healthy。
* Nginx：`location /api/ { proxy_pass http://backend:8000/; }` + SPA 回落（`try_files ... /index.html`）。
* 命名卷：`pg_data`、`redis_data`。

## 12. License

内部演示项目（demo），随批次评测使用，不对外发布。
