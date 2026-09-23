"""图端到端测试：甲乙丙三份简历 + 人工复核恢复。

需要 backend/.env 中配置 DASHSCOPE_API_KEY；未配置时整体跳过。
"""

import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langgraph.types import Command

from app.graph.builder import build_screening_graph
from app.graph.state import initial_state

load_dotenv()

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"

pytestmark = pytest.mark.skipif(
    not os.getenv("DASHSCOPE_API_KEY", "").strip(),
    reason="未配置 DASHSCOPE_API_KEY，跳过 LLM 端到端测试",
)


def _read(name: str) -> str:
    return (SAMPLES_DIR / name).read_text(encoding="utf-8")


def _config() -> dict:
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


async def _run_text(candidate_id: str, text: str):
    graph = build_screening_graph()
    config = _config()
    result = await graph.ainvoke(
        initial_state(candidate_id, "text", text), config
    )
    return result, config


async def test_jia_completes_with_105():
    result, _ = await _run_text("C001", _read("jia_chen.txt"))

    assert "__interrupt__" not in result
    assert result["score"]["final_score"] == 105
    assert result["rating"] == "推荐进入笔试"
    assert [step["node"] for step in result["trace"]] == [
        "parse_node",
        "extract_node",
        "validate_node",
        "screen_node",
        "explain_node",
    ]


async def test_yi_completes_with_80():
    result, _ = await _run_text("C002", _read("yi_liu.txt"))

    assert "__interrupt__" not in result
    assert result["score"]["final_score"] == 80
    assert result["rating"] == "推荐进入笔试"


async def test_bing_interrupts_then_resumes_to_80():
    graph = build_screening_graph()
    config = _config()

    result = await graph.ainvoke(
        initial_state("C003", "text", _read("bing_zhang.txt")), config
    )

    interrupts = result.get("__interrupt__")
    assert interrupts, "丙应触发 interrupt"
    payload = interrupts[0].value
    assert payload["candidate_id"] == "C003"
    assert any("时长" in r for r in payload["reasons"])
    assert any("到岗天数" in r for r in payload["reasons"])
    assert payload["suggestion"]

    resumed = await graph.ainvoke(
        Command(
            resume={
                "days_per_week": 4,
                "chengdu_onsite": True,
                "internship_duration_months": 3,
            }
        ),
        config,
    )

    assert "__interrupt__" not in resumed
    assert resumed["score"]["final_score"] == 80
    assert resumed["rating"] == "推荐进入笔试"
    assert any(
        step.get("node") == "review_node" and step.get("action") == "human_resolved"
        for step in resumed["trace"]
    )


async def test_ding_hard_fail_skips_review():
    """丁某：可实习 2 个月（确定性 < min=3）+ 独立学院（名单判 other）
    一条硬性条件确定性失败 + 院校层次无需复核（名单和 LLM 都可能判 other）
    → 直接暂不推进，不触发 interrupt。"""
    result, _ = await _run_text("C004", _read("ding_wei.txt"))

    assert "__interrupt__" not in result, "应直接暂不推进，不触发 interrupt"
    assert result["hard_filter"]["passed"] is False
    assert "可实习时间不满3个月" in result["hard_filter"]["reasons"]
    assert result["rating"] == "暂不推进"
    assert result["score"] is None

    # trace 应跳过 review_node
    nodes = [step["node"] for step in result["trace"]]
    assert "review_node" not in nodes
    assert nodes == [
        "parse_node",
        "extract_node",
        "validate_node",
        "screen_node",
        "explain_node",
    ]
