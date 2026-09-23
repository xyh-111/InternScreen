# 2026-09-22 DashScope 切换 OpenAI 兼容模式

## 目标

`backend/.env` 的 `DASHSCOPE_MODEL=qwen3.8-max` 在 `ChatTongyi` 下报
`400 InvalidParameter: url error`，此前被误判为「模型不存在」。

实测确认：**模型存在**，只是 `ChatTongyi` 走的 DashScope **原生**
`text-generation/generation` 服务不路由该模型，它只在 **OpenAI 兼容模式**
（`https://dashscope.aliyuncs.com/compatible-mode/v1`）提供。

用户选择方案 A：换成兼容模式入口，真正用上 `qwen3.8-max`。

## 变更范围

| 文件 | 变更 |
|---|---|
| `backend/requirements.txt` | 新增 `langchain-openai>=1.0,<2.0` |
| `backend/app/services/llm.py` | `get_llm()` 由 `ChatTongyi` 换成 `ChatOpenAI`，固定 `base_url` 指向兼容模式；并显式关闭思考模式、收紧超时与重试（见「后续调整」） |
| `backend/.env` | 第 3 行注释补全，说明入口限制与兼容入口可用模型（模型值 `qwen3.8-max` 未动） |

### 未改动

- `app/tools/extract_tools.py`：`with_structured_output` + JSON 回退的调用方式不变
- `app/graph/*`、前端：均无改动
- `dashscope` 依赖保留（不再被 `llm.py` 使用，但仍是社区包的传递依赖）

## 关键决策与踩坑

### 1. 统一走兼容模式，而不是双入口分支

`ChatTongyi` 与 `ChatOpenAI` 的模型覆盖面是**包含关系**：兼容模式同时支持
`qwen-plus` / `qwen-max` / `qwen-turbo` / `qwen3-max` / `qwen3.8-max`。
因此不需要按模型名分流，直接全部走兼容模式，代码更简单。

### 2. 报错文案不可信（本轮最重要教训）

DashScope 按模型名解析服务地址，解析不到时返回的是
`InvalidParameter: url error` 而**不是** `model not exist`。
据此推断「模型不存在」是错的——判断模型是否存在，必须在**两个入口**各打一次真实请求。

### 3. `base_url` 写死为大陆区常量

`.env` 里只有 API key 与模型名，未新增 `DASHSCOPE_BASE_URL` 配置项——
当前只有大陆区 key，加配置项属于为不存在的需求留口子。
国际站（`dashscope-intl.aliyuncs.com`）实测返回 401，大陆区 key 不适用。

### 4. `langchain-core` 被连带升级

安装 `langchain-openai 1.6.3` 时，`langchain-core` 由 `1.6.3` 升到 `1.6.4`（补丁位）。
全量测试通过，无 API 破坏。

## 已验证

- 真实调用（`DASHSCOPE_MODEL=qwen3.8-max`，不再需要环境变量覆盖）：
  ```
  class : ChatOpenAI
  model : qwen3.8-max
  base  : https://dashscope.aliyuncs.com/compatible-mode/v1
  structured OK -> 甲 | 电子科技大学 | bachelor
  ```
  `with_structured_output(ExtractedFields)` 在兼容模式下**直接可用**，未走 JSON 回退
- `pytest -q`（全量）→ **25 passed**（含此前偶发失败的
  `test_jia_completes_with_105`、`test_bing_interrupts_then_resumes_to_80`）

## 后续调整：关闭思考模式 + 收紧超时重试

切换入口后发现链路耗时从秒级涨到分钟级，实测定位到三个叠加原因。

### 实测数据

同一模型比入口，几乎无差别 —— **不是入口的锅**：

| 配置 | 耗时 |
|---|---|
| `ChatTongyi` + qwen-plus | 2.28s |
| `ChatOpenAI` + qwen-plus | 2.36s |

换 `qwen3.8-max` 后才变慢（真实长度简历 + `with_structured_output`）：

| 配置 | 耗时 |
|---|---|
| qwen-plus | 6.81s |
| qwen3.8-max（默认） | **33.29s / 83.70s**（抖动极大） |
| qwen3.8-max + `timeout=60` | 60.10s → `OpenAITimeoutError` |

思考模式开关对比（同一提示词）：

| 模型 | completion_tokens | 是否含思考 |
|---|---|---|
| qwen3-max | 388 | 否 |
| qwen3.8-max（默认） | 782 | 是 |
| qwen3.8-max + `enable_thinking=False` | 506 | 否 |

### 三个原因

1. **`qwen3.8-max` 默认开思考模式**：抽取是确定性字段抽取，不需要推理过程，
   思考链让 completion tokens 翻倍，耗时抖动到几十秒
2. **`timeout=None` / `max_retries=None` 让 openai SDK 默认值兜底**：
   实际生效 `timeout=600s` + `max_retries=2`，一次卡住的请求最坏耗 20~30 分钟。
   实测撞到过一次「发出请求后 18 分钟无任何 HTTP 响应、进程 CPU 为 0」
3. **`ChatTongyi` 走 dashscope SDK，默认超时短得多**：慢请求很快暴露，
   于是体感上像是「换了入口才变慢」

### 改法

```python
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 1

return ChatOpenAI(
    model=model,
    api_key=api_key,
    base_url=DASHSCOPE_BASE_URL,
    temperature=0,
    timeout=REQUEST_TIMEOUT_SECONDS,
    max_retries=MAX_RETRIES,
    extra_body={"enable_thinking": False},
)
```

`enable_thinking=False` **无条件传**：实测 `qwen-plus` / `qwen-max` / `qwen3-max` /
`qwen3.8-max` 四个模型都接受该参数（不支持的模型会忽略，不会 400），
所以不需要按模型名分支。

### 效果

| 指标 | 改前 | 改后 |
|---|---|---|
| 单次抽取（qwen3.8-max，真实简历） | 33s / 83s / 偶发挂起 18min | **9.30s / 9.71s / 9.46s** |
| `pytest -q` 全量 | 318.52s | **30.68s** |

抽取字段结果一致（`甲|电子科技大学|bachelor|6.0|5`），无回归。

### 注意

`timeout=60` 是**硬失败**而非降级：真实长简历若确实需要 >60s，会抛
`OpenAITimeoutError`，随后走 `llm_extract` 的 JSON 回退路径（再等最多 120s）。
当前实测稳定在 10s 以内，60s 余量充足。

## 遗留风险

- 兼容模式对 `response_format` / function calling 的支持随模型不同可能有差异；
  若将来换更冷门的模型，`with_structured_output` 失败仍会回退 JSON 路径
  （见 `docs/ai/INDEX.md` 已知环境阻塞表）
