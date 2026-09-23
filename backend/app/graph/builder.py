"""图构建与编译。

checkpointer 使用模块级单例，且整图只编译一次（lru_cache），
否则 Command(resume=...) 无法在同一 thread_id 上恢复状态。
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    explain_node,
    extract_node,
    parse_node,
    review_node,
    screen_node,
    validate_node,
)
from app.graph.routes import route_after_validate
from app.graph.state import ScreeningState
from app.memory.checkpointer import get_checkpointer


@lru_cache(maxsize=1)
def build_screening_graph():
    """构建筛选 Agent 图（进程内单例）"""
    builder = StateGraph(ScreeningState)

    builder.add_node("parse_node", parse_node)
    builder.add_node("extract_node", extract_node)
    builder.add_node("validate_node", validate_node)
    builder.add_node("screen_node", screen_node)
    builder.add_node("review_node", review_node)
    builder.add_node("explain_node", explain_node)

    builder.add_edge(START, "parse_node")
    builder.add_edge("parse_node", "extract_node")
    builder.add_edge("extract_node", "validate_node")

    builder.add_conditional_edges(
        "validate_node",
        route_after_validate,
        {
            "screen_node": "screen_node",
            "review_node": "review_node",
        },
    )

    builder.add_edge("screen_node", "explain_node")
    builder.add_edge("review_node", "screen_node")
    builder.add_edge("explain_node", END)

    return builder.compile(checkpointer=get_checkpointer())
