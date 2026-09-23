"""LLM 工厂：统一走通义千问 DashScope。

DashScope 提供两个入口：

- 原生 ``text-generation/generation``（``langchain_community`` 的 ``ChatTongyi`` 走这里）
- OpenAI 兼容模式 ``https://dashscope.aliyuncs.com/compatible-mode/v1``

部分模型（如 ``qwen3.8-max``）只在兼容模式提供，走原生入口会报
``400 InvalidParameter: url error`` —— 该文案有误导性，**不代表模型不存在**。
因此这里统一走兼容模式，两条入口的模型都能用。

抽取任务是确定性字段抽取，不需要推理过程，因此显式关闭思考模式
（``enable_thinking=False``）：qwen3 系列默认开思考，实测 completion tokens 翻倍、
耗时抖动到几十秒。同时显式收紧超时与重试，避免默认的 600s × 3 次把一次卡顿
放大成几十分钟。
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# DashScope 的 OpenAI 兼容入口（大陆区）
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 单次请求超时（秒）与重试次数。
# ChatOpenAI 不传这两项时，生效的是 openai SDK 默认值 timeout=600s、max_retries=2，
# 一次卡住的请求最坏能耗掉 20~30 分钟，必须显式收紧。
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 1


@lru_cache(maxsize=1)
def get_llm():
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "缺少 DASHSCOPE_API_KEY，请在 backend/.env 中配置后再运行抽取节点。"
        )

    from langchain_openai import ChatOpenAI

    model = os.getenv("DASHSCOPE_MODEL", "qwen-plus").strip()
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=DASHSCOPE_BASE_URL,
        temperature=0,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
        extra_body={"enable_thinking": False},
    )
