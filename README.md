# InternScreen — AI 实习生筛选系统

基于 **LangGraph Agent + FastAPI + React** 的实习简历智能筛选系统 Demo。

前端看板（http://localhost:5173）输入简历文本或 PDF，后端 LangGraph Agent 自动完成 **解析 → 结构化抽取 → 规则校验 → 硬性过滤 / 评分 → 解释** 全链路；遇到字段缺失或院校层次冲突时，自动暂停等待人工复核（`interrupt()`），恢复后继续执行。

## 功能一览

- ✅ 文本粘贴 / PDF 上传两种简历输入方式
- ✅ LLM 结构化抽取 12+ 字段（学历、院校、AI 工具经历、到岗稳定性等）
- ✅ 硬性条件过滤（学历层次、可实习时长、每周到岗天数、成都线下）—— 在读状态已在上游初筛环节把关
- ✅ 分数卡（学历 30/25/18 + 院校 20/8 + AI 工具 25/12/0 + 稳定性 + 到岗天数，最高 105 分）
- ✅ 评级（推荐进入笔试 / 备选 / 暂不推进）
- ✅ 双一流名单确定性判定（147 所 + 109 别名），异地校区 / 独立学院后缀规则
- ✅ 人工复核弹窗（`Command(resume=...)` 恢复执行）
- ✅ 前端统计看板：4 张可点击的统计卡 + 状态分布占比条 + 底部简历输入
- ✅ 历史记录弹窗 + 筛选结果弹窗（叠加打开，互不打断）
- ✅ 评分卡下方显示打分依据（如「硕士」「电子科技大学 / 四川大学」）

## 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 后端框架 | FastAPI | ≥0.141.1 |
| 图编排 | LangGraph | ≥1.2.11,<2.0 |
| LLM 调用 | LangChain + DashScope OpenAI 兼容模式 | langchain ≥1.4.2 / langchain-openai ≥1.0 |
| 模型 | qwen-plus / qwen-max / qwen3-max / qwen3.8-max（`enable_thinking=False`） | — |
| PDF 解析 | pdfplumber | ≥0.11.10 |
| 数据存储 | SQLite（Python 内置） | — |
| 前端框架 | React + TypeScript + Vite | React ^18.3 / Vite ^5.4 / TS ^5.6 |
| UI 组件 | Ant Design + @ant-design/icons | antd ^5.21 |
| 网络 | axios | ^1.7 |

## 架构

### 数据流

```
简历文本 / PDF
      │
      ▼
┌── parse_node ──┐   pdfplumber / 文本直传
└────────────────┘
      │
      ▼
┌── extract_node ──┐   ChatOpenAI(qwen-xxx) + with_structured_output
└───────────────────┘
      │  fields (12+ 字段)
      ▼
┌── validate_node ──┐   字段完整性 + 边界 + 院校名单冲突
└────────────────────┘
      │
      ├─ need_review=false ──▶ screen_node ──▶ explain_node ──▶ END
      │
      └─ need_review=true  ──▶ review_node (interrupt ⏸)
                                    │
                               人工提交 Command(resume=...)
                                    │
                                    ▼
                                 screen_node ──▶ explain_node ──▶ END
```

- `MemorySaver`（LangGraph 内置）负责图状态持久化；每次 `/agent/run` 新生成 `thread_id`
- 业务数据（候选人、运行记录、抽取字段）落 SQLite，与图状态解耦
- `app/config/rules.yaml` / `school_tiers.yaml` 为规则外置文件，节点代码不硬编码任何阈值

### 后端目录结构

```
backend/
├── requirements.txt
├── pytest.ini
├── .env.example          ← 复制为 .env 后填写 DASHSCOPE_API_KEY
├── run.py
├── .venv/                ← 必须使用项目内 venv（全局 site-packages 被沙箱拦截）
├── data/
│   ├── internscreen.db    ← SQLite（首次启动自动创建）
│   ├── uploads/           ← PDF 上传目录
│   └── samples/           ← 示例简历
└── app/
    ├── main.py            ← FastAPI 入口
    ├── api/
    │   ├── agent.py       ← /api/agent/run /resume /upload
    │   ├── stats.py       ← /api/stats
    │   ├── candidates.py  ← /api/candidates /candidates/{thread_id}
    │   ├── review.py      ← /api/review/pending
    │   └── rules.py       ← /api/rules
    ├── graph/
    │   ├── builder.py     ← StateGraph 单例 + lru_cache
    │   ├── state.py       ← ScreeningState / ExtractedFields 类型
    │   ├── nodes.py       ← 6 个节点实现
    │   └── routes.py      ← validate 后的条件路由
    ├── tools/
    │   ├── parse_tools.py     ← parse_text_tool / parse_pdf_tool
    │   ├── extract_tools.py   ← llm_extract 结构化抽取（8 条规则）
    │   └── rule_tools.py
    ├── services/
    │   ├── llm.py         ← get_llm() / ChatOpenAI + DashScope 兼容模式
    │   ├── rule_engine.py ← run_rules() + resolve_school_tier() + classify_school()
    │   └── storage.py     ← SQLite 存取 + init_db 列迁移
    ├── memory/
    │   └── checkpointer.py ← MemorySaver 单例
    └── config/
        ├── rules.yaml         ← 硬性条件 / 评分权重 / 评级阈值 / 文案
        └── school_tiers.yaml  ← 双一流名单（147 所 + 别名 + 后缀规则）
```

### 前端目录结构

```
frontend/
├── package.json          ← v0.3.0
├── vite.config.ts        ← dev server 5173，/api 代理到 127.0.0.1:8000
└── src/
    ├── main.tsx / App.tsx
    ├── styles.css        ← --is-primary #2563eb，纯白底 + 蓝点缀
    ├── pages/Dashboard.tsx   ← 单列看板
    ├── types/index.ts        ← RunStats / RunView / RunFields / RunRecord ...
    ├── api/
    │   ├── client.ts         ← axios instance
    │   └── agent.ts          ← runAgent / resumeAgent / getStats / getCandidates ...
    └── components/
        ├── CandidateInput.tsx    ← 文本/PDF 输入 + 简历筛选按钮
        ├── StatsCards.tsx        ← 4 张可点击统计卡
        ├── StatusDistribution.tsx ← 3 行占比条
        ├── ResultCard.tsx        ← 评分卡（含打分依据小字）
        ├── ResultModal.tsx        ← 筛选结果弹窗
        ├── HistoryList.tsx       ← 纯列表组件（被 HistoryModal / Dashboard 复用）
        ├── HistoryModal.tsx       ← 历史记录 / 名单弹窗（通用标题）
        └── ReviewModal.tsx       ← 人工复核弹窗
```

## 安装与启动

### 前置要求

- Python 3.11（仅在 3.11 上验证过）
- Node.js ≥ 18（Vite 5 需要）
- DashScope API Key（阿里云百炼平台）

### 1. 后端

```bash
cd backend

# 创建项目内 venv（全局 site-packages 在某些环境下会被拦截）
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
# 可选：DASHSCOPE_MODEL=qwen-plus（默认 qwen-plus；已验证 qwen-plus / qwen-max / qwen3-max / qwen3.8-max 均可用）

# 启动
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- 首次启动时 SQLite 库会自动创建在 `backend/data/internscreen.db`
- `runs` 表新增列时，`init_db()` 会自动 `ALTER TABLE` 补齐

### 2. 前端（另一个终端）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 **http://localhost:5173**。Vite dev server 已配置 `/api` 代理到 `http://127.0.0.1:8000`。

生产构建：`npm run build`（输出到 `frontend/dist/`）。

### 3. 运行测试

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

当前测试覆盖：规则引擎（`test_rule_engine.py`）+ 图编排（`test_graph.py`），共 37 个用例。

> ⚠️ 图编排端到端测试有偶发失败，原因是 LLM 抽取非确定性（`degree_level` / `ai_tool_experience` 会抽空），与代码无关，重跑即过。

## API 接口

所有接口前缀 `/api`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent/run` | 开始一次筛选，返回 `RunResponse` |
| POST | `/api/agent/resume` | 人工复核后恢复执行 |
| POST | `/api/agent/upload` | 上传 PDF，返回临时文件路径 |
| GET | `/api/candidates` | 历史运行记录列表（最多 50 条，按创建时间倒序） |
| GET | `/api/candidates/{thread_id}` | 单条运行记录详情（含抽取字段） |
| DELETE | `/api/candidates/{thread_id}` | 删除一条运行记录（只删 runs 表），删不到抛 404 |
| GET | `/api/stats` | 统计卡数据源：`{ total, recommend, pending, reject }` |
| GET | `/api/review/pending` | 当前所有状态为 `WAITING_REVIEW` 的记录 |
| GET | `/api/rules` | 返回 `rules.yaml` 完整内容 |
| GET | `/api/health` | 健康检查 |

### `/api/agent/run` 示例

请求：
```json
{
  "input_type": "text",
  "raw_input": "姓名：陈某\n现为电子科技大学计算机科学与技术专业 2023 级硕士研究生..."
}
```

完成态响应（`status=COMPLETED`）：
```json
{
  "status": "COMPLETED",
  "thread_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "candidate_id": "C20260922-044",
  "rating": "推荐进入笔试",
  "score": {
    "degree": 25,
    "school": 20,
    "ai_tool": 25,
    "stability": 15,
    "days_per_week": 15,
    "raw_score": 100,
    "bonus": 5,
    "final_score": 105
  },
  "hard_filter": { "passed": true, "reasons": [] },
  "explanation": "...",
  "fields": {
    "degree_level": "master",
    "graduate_school": "电子科技大学",
    "bachelor_school": "四川大学",
    "ai_tool_experience": "project",
    "internship_duration_months": 6.0,
    "days_per_week": 5,
    "chengdu_onsite": true,
    ...
  },
  "trace": [...]
}
```

中断态响应（`status=WAITING_REVIEW`）会额外带 `interrupt_payload`，前端弹出复核弹窗。复核后调用 `/api/agent/resume` 提交 `human_input` 字典（含需要人工确认的字段，如 `school_tier`）。

### `/api/stats`

```json
{ "total": 43, "recommend": 31, "pending": 9, "reject": 3 }
```

口径：`recommend = 推荐进入笔试 + 备选`，`pending` 按 `status = WAITING_REVIEW` 判定，`reject` 按 `rating = 暂不推进` 判定。

## 打分规则（冻结 v1.0）

来自 [app/config/rules.yaml](backend/app/config/rules.yaml)。

### 硬性条件（任一不满足直接淘汰）

| 条件 | 规则 |
|---|---|
| 学历层次 | 本科 / 硕士 / 博士 |
| 可实习时长 | ≥ 3 个月 |
| 每周到岗天数 | ≥ 4 天 |
| 成都线下 | `chengdu_onsite = true` |

### 评分（满分 110 + 加分 5 = 115）

| 维度 | 分数 |
|---|---|
| 学历 | 博士 30 / 硕士 25 / 本科 18 |
| 院校 | 双一流 20 / 其他 8（含 unknown） |
| AI 工具 | 项目经历 25 / 日常对话 12 / 无 0 |
| 到岗稳定性 | ≥ 6 个月 15 / 否则 10 |
| 每周到岗 | ≥ 5 天 15 / 否则 12 |
| **加分** | 稳定性与到岗均拿满分 +5 分 |

### 评级

- `final_score ≥ 75` → 推荐进入笔试
- `65 ≤ final_score < 75` → 备选
- 其余 → 暂不推进

### 院校层次判定（名单优先，v0.4.2）

见 [app/config/school_tiers.yaml](backend/app/config/school_tiers.yaml)：

1. **名单是最高权威**（2022 教育部官方 147 所 + 109 别名）——一旦命中直接采用，忽略 LLM 判断
2. 名单命中 + 「校区 / 研究生院 / 研究院 / 分校 / 学部」后缀 → 双一流（异地校区）
3. 名单命中 + 「学院」后缀 → 独立学院（非双一流）
4. 名单未命中 → 看 LLM 兜底（名单可能有遗漏）
5. 只有名单未命中 **且** LLM 也没给 tier → 转人工复核

## 已知限制

| 项 | 说明 |
|---|---|
| 历史列表 50 条上限 | `list_runs(limit=50)` 硬限，超过后前端弹窗会截断。**统计卡数字不受影响**（走 `/api/stats` 聚合） |
| 老记录无抽取字段 | `fields_json` 是后加列，此前记录该列为 NULL，评分卡下方不显示依据小字。无法从 trace 反推，补齐需重跑 |
| LLM 抽取非确定性 | `degree_level` 有约 10-25% 概率抽空（走 JSON 回退路径），表现为硬性条件「非本科或研究生」直接淘汰且无复核兜底 |
| 校内学院假阴性 | 「北京大学光华管理学院」等后缀含「学院」会被独立学院后缀规则判 8 分。若名单真有该校名（如「四川大学」），后缀规则优先触发不会进名单匹配——这是后缀规则的固有限制 |
| 提交时请勿 force-add `.env` | `.env` 已被根目录 `.gitignore` 忽略，但如果用 `git add -f` 强行加入仍会被提交 |

## 常见问题

### `qwen3.8-max` 报 `400 InvalidParameter: url error`？

不要用 `ChatTongyi`（DashScope 原生 SDK 入口）。必须走 **OpenAI 兼容模式**：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="qwen3.8-max",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ["DASHSCOPE_API_KEY"],
    extra_body={"enable_thinking": False},
    timeout=60,
    max_retries=1,
)
```

原生入口不路由 `qwen3.8-max` 这类模型，报 `url error` 不代表模型不存在。

### 为什么必须关掉 `enable_thinking`？

qwen3 系列默认开启思考模式，completion tokens 翻倍，单次抽取从 10 秒抖动到 30-80 秒。所有已验证模型（qwen-plus / qwen-max / qwen3-max / qwen3.8-max）都接受 `extra_body={"enable_thinking": False}`。

### 为什么必须设 `timeout=60, max_retries=1`？

openai SDK 默认 `timeout=600s` + `max_retries=2`。一次卡顿最坏会放大成 20-30 分钟。已显式收紧。

### 为什么一定要用项目内 venv？

Windows 沙箱下全局 site-packages 会被拦截，`pip install` 看似成功但运行时报 `No module named langgraph`。项目目录下 `.venv` 不受影响。

### `Command(resume=...)` 找不到 thread 状态？

`build_screening_graph()` 用了 `@lru_cache(maxsize=1)`，图进程内只编译一次；checkpointer 也是模块级单例。如果每次请求都重新编译图或新建 checkpointer，恢复会失败。不要改 `builder.py` 里的单例模式。

### 后端改动不生效？

先查 uvicorn 进程命令行是否带 `--reload`。无 reload 的旧进程需重启。

### 为什么有些评分卡下面没有依据小字？

`fields_json` 列是后加的。以下两种情况不会显示依据小字（代码逻辑：字段缺失 → 返回 null → 整行不渲染，不会出现 `—` 占位）：

1. **老记录** —— 新增 `fields_json` 列之前创建的运行，该列为 NULL，无法从 trace 反推；
2. **LLM 抽取该字段为 null** —— 非确定性，偶发。

两种都不会报错，静默不显示。如需补齐老记录的依据，只能重跑。

## 变更记忆

项目运行过程中积累的工程决策、踩坑记录与已验证的硬约束，全部落在 `docs/ai/` 下：

- **`docs/ai/INDEX.md`** —— 索引，列出每份变更文档的摘要 + 已验证的关键决策表格（如「双一流名单判定必须是确定性匹配、不能做包含匹配」「openai SDK timeout/max_retries 必须显式收紧」等），编码前先读此文件可避免重复踩坑
- **`docs/ai/changes/YYYYMMDD-XXX.md`** —— 每次实质性改动一份，包含需求、改动清单、关键决策、验证结果、残留问题

## 版本历史

| 日期 | 版本 | 主要变化 |
|---|---|---|
| 2026-09-21 | v0.1 | 从零搭建：LangGraph Agent + FastAPI + React + 基础评分 |
| 2026-09-22 | v0.2 | 移除 Trace 面板 + 样例快填；候选人 ID 自动生成 |
| 2026-09-22 | v0.2.1 | 双一流名单确定性判定 + 异地校区 / 独立学院后缀规则 |
| 2026-09-22 | v0.2.2 | DashScope OpenAI 兼容模式接入 + 思考模式关闭 + 超时收紧（10 倍提速） |
| 2026-09-22 | v0.2.3 | 复核只由院校层次触发 |
| 2026-09-22 | **v0.4** | **移除在读状态判定**：默认进入系统的简历已通过初筛，都是在读状态。删掉硬性条件、LLM 抽取字段、resolve_in_school 整套函数 |
| 2026-09-22 | v0.4.1 | 新增删除简历功能：后端 DELETE /api/candidates/{thread_id}；前端 HistoryModal 里红色垃圾桶 + Popconfirm；权限前端控制（统计卡弹窗不可删） |
| 2026-09-22 | **v0.3** | **前端看板重布局**：单列看板 + 统计卡（可点击出名单）+ 结果/历史改弹窗；评分卡展示抽取依据 |
| 2026-09-23 | **v0.4.2** | **名单优先于 LLM**：院校层次判定改为名单最高权威（命中直接用、忽略 LLM），只有两边都无结论时才触发复核。消除「名单命中 + LLM 说 other → 误复核」问题。新增评估脚本 + 10 份测试简历样本 |
