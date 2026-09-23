# AI 变更记忆索引

> 用途：记录每次代码变更的决策与踩坑，避免重复劳动。编码前先读本索引匹配历史记录。

## 变更索引

| 日期 | 变更文档 | 涉及模块 | 摘要 |
|---|---|---|---|
| 2026-09-21 | [changes/20260921-初始搭建.md](changes/20260921-初始搭建.md) | backend / frontend | 从零搭建 InternScreen LangGraph Demo 前后端工程 |
| 2026-09-22 | [changes/20260922-移除Trace与样例快填.md](changes/20260922-移除Trace与样例快填.md) | backend / frontend | Trace 改终端日志、删样例快填、候选人 ID 自动生成、姓名改由简历抽取 |
| 2026-09-22 | [changes/20260922-双一流名单确定性判定.md](changes/20260922-双一流名单确定性判定.md) | backend / frontend | 院校层次改为双一流名单确定性匹配（147 所 + 别名），不一致转人工复核 |
| 2026-09-22 | [changes/20260922-异地校区与独立学院判定.md](changes/20260922-异地校区与独立学院判定.md) | backend | 双一流校名 + 校区/研究生院后缀 → 双一流；+ 学院后缀 → 独立学院；修复括号归一化缺陷 |
| 2026-09-22 | [changes/20260922-DashScope兼容模式接入.md](changes/20260922-DashScope兼容模式接入.md) | backend | LLM 入口由 `ChatTongyi`（原生）改为 `ChatOpenAI`（兼容模式），`qwen3.8-max` 真正可用；关闭思考模式并收紧超时重试 |
| 2026-09-22 | [changes/20260922-复核弹窗补齐字段选项.md](changes/20260922-复核弹窗补齐字段选项.md) | frontend | 复核弹窗补齐「在读状态」「学历层次」两类选项（**已被下一条回滚**） |
| 2026-09-22 | [changes/20260922-收窄复核触发条件.md](changes/20260922-收窄复核触发条件.md) | backend / frontend | 复核不再由「在读状态缺失」「学历层次缺失」触发，弹窗对应选项回滚；缺失改为由硬性条件直接淘汰 |
| 2026-09-22 | [changes/20260922-在读状态时间推导.md](changes/20260922-在读状态时间推导.md) | backend | 新增 `education_end` 抽取与 `resolve_in_school()`：简历明示优先，时间推导兜底 |
| 2026-09-22 | [changes/20260922-前端看板重布局.md](changes/20260922-前端看板重布局.md) | backend / frontend | 前端改为单列看板：4 张统计卡（可点击出名单）+ 3 行状态分布 + 底部输入；历史与结果改弹窗；新增 `/api/stats` 聚合接口 |
| 2026-09-22 | [changes/20260922-评分卡展示抽取依据.md](changes/20260922-评分卡展示抽取依据.md) | backend / frontend | `runs` 表新增 `fields_json`，抽取字段随接口返回并落库；评分卡下方显示打分依据（学历→硕士、院校→校名等） |
| 2026-09-22 | [changes/20260922-移除在读状态判定.md](changes/20260922-移除在读状态判定.md) | backend | 业务前提：默认进入系统的简历已通过初筛都是在读。删 `require_in_school`、`resolve_in_school()` 整套、LLM 抽取字段 `in_school` + `education_end`、提示词 + 17 个测试用例 |
| 2026-09-22 | [changes/20260922-新增删除简历.md](changes/20260922-新增删除简历.md) | backend / frontend | 新增 `DELETE /api/candidates/{thread_id}`；`HistoryList` 加垃圾桶按钮 + Popconfirm；权限由前端控制（`listKey === 'all'` 才传 `deletable`，统计卡弹窗一律不可删） |
| 2026-09-22 | [changes/20260922-硬性条件预判跳过复核.md](changes/20260922-硬性条件预判跳过复核.md) | backend | `validate_node` 预跑硬性条件，区分「确定性失败」（已抽到值但不满足 → 直接暂不推进，跳过 review）与「字段缺失」（None → 仍走 review）。新增 `precheck_hard()` 辅助函数；`route_after_validate` 按 `hard_already_failed` 优先路由；新增 7 个测试（含端到端样本丁） |
| 2026-09-22 | [changes/20260922-校名禁止tier标签.md](changes/20260922-校名禁止tier标签.md) | backend | 简历只写"双一流/非双一流/普通高校"等 tier 标签没给具体校名时，LLM 会把标签塞进 school 字段。修复两层：①提示词显式禁止 tier 标签当校名（只提层次时 school 填 null，层次写 tier 字段）②后处理 `_sanitize_school_names()` 确定性纠错：按长度降序剥 tier 关键词、清孤立括号、剩余文本为泛指词时置空 school + 推断 tier。7 个兜底 case 全绿 |
| 2026-09-22 | [changes/20260922-无校名时信任tier.md](changes/20260922-无校名时信任tier.md) | backend | `resolve_school_tier` 加前置分支：所有校名字段都为空时，名单无输入可查 → 直接信任 LLM tier（llm_hit→double_first_class / llm_says_other→other / 都空→仍复核）。避免「无校名 + llm_hit 被判名单冲突」的错误复核 |

## 已验证的关键决策

| 决策 | 结论 | 出处 |
|---|---|---|
| Checkpointer 生命周期 | `MemorySaver` 必须模块级单例，图只编译一次；否则 `Command(resume=...)` 找不到 thread | changes/20260921-初始搭建.md |
| 规则外置 | 分数与阈值全部来自 `app/config/rules.yaml`，节点零硬编码 | changes/20260921-初始搭建.md |
| 图状态持久化 | LangGraph 用 `MemorySaver`；业务数据（候选人/运行记录）落 SQLite | changes/20260921-初始搭建.md |
| `school_tier` 缺失口径 | 非双一流一律 8 分（含 `unknown` / `null`），不得静默得 0 分 | changes/20260921-初始搭建.md §7 |
| 院校层次判定 | LLM 只抽校名，层次由 `app/config/school_tiers.yaml` 名单 + 后缀词确定性匹配；**不做任意位置的包含匹配** | changes/20260922-双一流名单确定性判定.md §1-2 |
| 异地校区 / 独立学院 | 双一流校名 + 后缀含「校区/研究生院/研究院/分校/学部」→ 双一流；后缀含「学院」→ 独立学院（非双一流）；前缀取**最长匹配** | changes/20260922-异地校区与独立学院判定.md §2 |
| 校名归一化 | **保留括号**再匹配，另尝试剥离括号形式；不要无条件剥离（会漏掉「中国石油大学（华东）」） | changes/20260922-异地校区与独立学院判定.md §1 |
| 不改 LLM 提示词的原因 | 把后缀规则也写进提示词会让 LLM 判断与本地规则同源，一致性校验失去独立性 | changes/20260922-异地校区与独立学院判定.md §3 |
| 校内学院假阴性 | 「北京大学光华管理学院」等后缀含「学院」会被判 8 分，靠 LLM 冲突校验兜底 | changes/20260922-异地校区与独立学院判定.md §4 |
| 多学历口径 | 本科 / 研究生**任一段命中名单即算双一流** | changes/20260922-双一流名单确定性判定.md §1 |
| 名单与 LLM 不一致 | 不一致或两边都无结论 → 转人工复核；`fields["school_tier"]` 为人工结论，**优先级最高** | changes/20260922-双一流名单确定性判定.md §1 |
| 复核弹窗字段推导 | 前端 `ReviewModal.buildFields()` 靠 `reasons` 关键词决定渲染哪些表单项，当前映射：时长 / 到岗天数 / 成都 / 院校；后端加新复核原因需同步此处，否则弹窗会变成空表单 | changes/20260922-复核弹窗补齐字段选项.md §根因 |
| 复核触发条件 | 只有「院校层次冲突 / 无法确认」会触发复核；字段缺失直接落到硬性条件淘汰，无兜底 | changes/20260922-收窄复核触发条件.md §1 + changes/20260922-移除在读状态判定.md |
| 缺失 ≠ 不符合 | `degree_level` 抽成 `None` 会被硬性条件「非本科或研究生」静默淘汰且无人工兜底。实测无日期简历约 1/4 概率抽空，属已知脆弱性 | changes/20260922-移除在读状态判定.md §残留问题 |
| 在读状态 | **已整体移除**。业务前提变化：默认进入本系统的简历已通过上游初筛、都是在读。删掉了 `require_in_school` 配置、`resolve_in_school()` 整套函数、LLM 抽取字段 `in_school` / `education_end`、提示词、17 个测试 | changes/20260922-移除在读状态判定.md |
| DashScope 入口 | 统一走 **OpenAI 兼容模式** `https://dashscope.aliyuncs.com/compatible-mode/v1`（`ChatOpenAI`）。`ChatTongyi` 走的原生 `text-generation/generation` 入口不路由 `qwen3.8-max`，报 `400 InvalidParameter: url error`——**该文案不代表模型不存在** | changes/20260922-DashScope兼容模式接入.md §1 §2 |
| 思考模式 | `get_llm()` 无条件传 `extra_body={"enable_thinking": False}`。qwen3 系列默认开思考，抽取任务不需要，实测 completion tokens 翻倍、耗时抖动到几十秒。四个已验证模型都接受该参数，无需按模型名分支 | changes/20260922-DashScope兼容模式接入.md 后续调整 |
| LLM 超时与重试 | 必须显式设 `timeout=60` + `max_retries=1`。不设时生效的是 openai SDK 默认 `timeout=600s` + `max_retries=2`，一次卡顿最坏放大成 20~30 分钟（实测撞到过 18 分钟无响应） | changes/20260922-DashScope兼容模式接入.md 后续调整 |
| DashScope 模型名 | `qwen3.8-max` **存在**且已在兼容模式下实测可用；判断模型是否存在必须在**两个入口**各打一次真实请求 | changes/20260922-DashScope兼容模式接入.md §2 |
| 依赖版本 | 实际解析到 langchain 1.4.2 + langgraph 1.2.11，核心 API 与 0.x 一致 | changes/20260921-初始搭建.md §5 |
| LLM 依赖 | `langchain-openai>=1.0,<2.0`（会连带把 `langchain-core` 提到 1.6.4 补丁位）；`dashscope` 保留但 `llm.py` 已不再直接使用 | changes/20260922-DashScope兼容模式接入.md §4 |
| Python 依赖安装 | 全局 site-packages 被沙箱拦截，必须用项目内 venv | changes/20260921-初始搭建.md §4 |
| 流式驱动图 + 取中断 | `astream(stream_mode="updates")` 只用于逐节点日志；状态与中断必须用 `graph.aget_state(config)` 的 `.values` / `.interrupts`，不要自行合并分片 | changes/20260922-移除Trace与样例快填.md §1 |
| candidate_id 生成时机 | 图运行**前**生成（`explain_node` 要用）；`upsert_candidate()` 在图运行**后**调用（姓名来自 `extract_node`） | changes/20260922-移除Trace与样例快填.md §2 |
| uvicorn 日志 | uvicorn 不配置 root logger，`app/main.py` 里 `logging.basicConfig()` 即可让应用日志进终端 | changes/20260922-移除Trace与样例快填.md §3 |
| 后端改动不生效排查 | 先查进程命令行是否带 `--reload`；无 reload 的旧进程需重启 | changes/20260922-移除Trace与样例快填.md §4 |
| 统计口径不能基于 `list_runs()` | 该函数硬限 50 条，前端自己 count 会偏小。统计一律走后端 `run_buckets()` 聚合（`GET /api/stats`） | changes/20260922-前端看板重布局.md §关键决策 3 |
| 「待复核」判定字段 | 必须用 `status = 'WAITING_REVIEW'`，**不能用 `rating`**——`rating` 只在完成后写入，中断期间为 `null` | changes/20260922-前端看板重布局.md §关键决策 5 |
| 统计卡口径 | 总=`runs` 行数；推荐=`推荐进入笔试`+`备选`（备选算进推荐，保证三项之和=总数）；待复核=`WAITING_REVIEW`；暂不推进=`暂不推进`。评级文案从 `load_rules()["labels"]` 取 | changes/20260922-前端看板重布局.md §关键决策 1 §6 |
| 弹窗叠加而非互斥 | 「筛选结果」弹窗叠在「运行历史」弹窗之上，关掉结果即回到历史列表，无需额外状态协调 | changes/20260922-前端看板重布局.md §关键决策 7 |
| 列表组件不带外壳 | `HistoryList` 返回纯列表（无 `Card`），外壳交给调用方；`loading` 只在「加载中且列表为空」时显示 `Spin`，避免刷新时把已有列表闪没 | changes/20260922-前端看板重布局.md §踩坑与注意 |
| 复核后仍中断的处理 | `handleResume` 必须按返回的 `status` 分支：仍为 `WAITING_REVIEW` 时保持 `ReviewModal` 打开，不能无条件关闭 | changes/20260922-前端看板重布局.md §踩坑与注意 |
| 统计卡点击出名单 | 复用 `HistoryModal`（加可选 `title`），不新建组件；名单在**前端过滤**历史记录，过滤口径与 `/api/stats` 严格对齐 | changes/20260922-前端看板重布局.md §关键决策 12-14 |
| 前端评级文案硬编码点 | 评级中文文案在**三处**硬编码：`HistoryList.RATING_COLOR`、`ResultCard.RATING_COLOR`、`Dashboard.RECOMMEND_RATINGS`。改 `rules.yaml` 的 `labels` 必须同步这三处，否则统计卡名单会静默变空 | changes/20260922-前端看板重布局.md §残留问题 |
| 名单条数受 50 条上限 | 名单走 `GET /api/candidates`（`list_runs(limit=50)`），卡上数字走 `/api/stats` 聚合。记录超 50 条后两者会不一致——是已知缺口，非 bug | changes/20260922-前端看板重布局.md §残留问题 |
| 抽取字段原本不在接口里 | `_completed_response()` 不返回 `fields`，`trace` 里 `extract_node` 只记 `missing_fields` 不含值。要展示抽取结果必须改后端，前端推不出来 | changes/20260922-评分卡展示抽取依据.md §关键事实 |
| `runs` 表加列必须写迁移 | `CREATE TABLE IF NOT EXISTS` **不会**改已存在的表。加列要在 `init_db()` 里查 `PRAGMA table_info` 后 `ALTER TABLE`，否则老库静默缺列 | changes/20260922-评分卡展示抽取依据.md §关键决策 2 |
| 展示依据要走落库而非只加响应 | 结果弹窗既能从「刚跑完」打开也能从「历史」打开，只加响应会导致同一弹窗两种表现 | changes/20260922-评分卡展示抽取依据.md §关键决策 1 |
| 依据不进 `trace` | `trace` 是终端日志用的逐节点流水，语义不同；塞 `fields` 会因 `evidence` 原文导致体积翻倍 | changes/20260922-评分卡展示抽取依据.md §关键决策 3 |
| 前端枚举文案硬编码点 | `ResultCard.tsx` 的 `DEGREE_LABEL` / `AI_TOOL_LABEL` 与后端 `DegreeLevel` / `AIToolExperience` 枚举同源，改枚举需同步 | changes/20260922-评分卡展示抽取依据.md §残留问题 |
| 删除权限前端控制 | HistoryModal 被「历史记录」按钮和四张统计卡共用，用 `deletable={listKey === 'all'}` 区分，统计卡弹窗一律不可删；后端 DELETE 接口开放（本地开发无需鉴权） | changes/20260922-新增删除简历.md §关键决策 2 |
| 删除只清 runs 表 | `storage.delete_run()` 只删 runs 行，candidates 表保留孤立行无害，也避免万一想 restore；历史列表用 LEFT JOIN，删掉 runs 就自然消失 | changes/20260922-新增删除简历.md §关键决策 1 |
| 硬性条件预判 → 跳过 review | `validate_node` 里用 `precheck_hard()` 区分「确定性失败」和「字段缺失」。确定性失败（如 `duration=2 < 3`、`degree_level=other`）直接进 screen_node 判暂不推进，**不进 review**；只有字段缺失/院校冲突等不确定项才进 review_node。避免了「一条已死 + 一条待审 → 白跑复核」的浪费 | changes/20260922-硬性条件预判跳过复核.md §1 §2 |
| `precheck_hard` 与 `run_rules` 职责边界 | `precheck_hard` 只做**预判、分类**（deterministic_failures / missing_fields），不返回评级；`run_rules` 做最终判定 + 评分。两者共享同一份 `load_rules()` 配置，阈值永远一致 | changes/20260922-硬性条件预判跳过复核.md §2 |
| route_after_validate 优先级 | `hard_already_failed=True` 时**无论 `need_review` 是什么**都进 screen_node。这样即便 reasons 里既有"院校层次需要复核"又有"duration=2 确定性失败"，也不会被 review 干扰 | changes/20260922-硬性条件预判跳过复核.md §关键决策 |
| 无真实校名时名单逻辑短路 | `resolve_school_tier` 前置分支：所有校名字段都为空时（`has_real_school=False`），名单无输入可查 → 直接信任 LLM tier，不做冲突校验。只有 tier 也空才复核。**有任一**真实校名（哪怕另一段为空）都走名单路径 | changes/20260922-无校名时信任tier.md |

## 已知环境阻塞

| 项 | 现象 | 处理 |
|---|---|---|
| `in_school` / `degree_level` 抽取非确定性 | 二者会在**同一次运行里一起抽空**（整批质量下降，疑走 JSON 回退路径）。缺失不再转人工，改为硬性条件直接淘汰。`education_end` 兜底**只对有日期的简历有效**：乙/丙只有「2024 级」没有日期，实测 4 次跑出 1 次误淘汰 | 见 changes/20260922-在读状态时间推导.md §残留问题；`test_yi_completes_with_80`、`test_bing_interrupts_then_resumes_to_80` 因此偶发失败 |
| 院校层次复核率 | 已由后缀规则消化掉异地校区 / 独立学院两类误报；剩余复核来自校名抽带杂质、校内学院假阴性、名单外院校无 LLM 结论 | 见 changes/20260922-异地校区与独立学院判定.md §2 §4 |
| LLM 回退 JSON 路径偶发畸形 | `with_structured_output` 失败后回退 `_JSON_PROMPT`，模型偶尔返回非法 JSON（如 `evidence` 被塞成对象），`ExtractedFields.model_validate_json` 抛 ValidationError | 非本次引入；表现为 `test_bing_interrupts_then_resumes_to_80` 偶发失败，重跑即过 |
| 项目非 git 仓库 | 目录下无 `.git`，用户规则里的 `git diff` 检测不可用 | 改为按「本轮是否改动代码」直接写变更文档 |
| 历史列表 50 条上限 | 历史弹窗走 `GET /api/candidates`（`list_runs(limit=50)`），记录超 50 条后列表会截断。统计数字不受影响（走 `/api/stats` 聚合） | 见 changes/20260922-前端看板重布局.md §残留问题；需分页或提高上限，本次未做 |
| 老记录无抽取字段 | `fields_json` 是新增列，此前 43 条记录该列为 `NULL`，无法从 `trace` 反推（trace 不含字段值），表现为评分卡下方无依据小字 | 见 changes/20260922-评分卡展示抽取依据.md §残留问题；如需补齐只能重跑 |



