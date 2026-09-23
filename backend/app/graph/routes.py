"""条件路由函数。"""

from app.graph.state import ScreeningState


def route_after_validate(state: ScreeningState) -> str:
    """验证后的条件路由。

    优先级：
    1. 硬性条件已确定性失败 → 跳过 review 直接进 screen_node 判暂不推进
    2. 硬性条件通过 + need_review → 进 review_node（人工复核院校层次等）
    3. 硬性条件通过 + 无需复核 → 进 screen_node
    """
    if state.get("hard_already_failed"):
        return "screen_node"
    if state["need_review"]:
        return "review_node"
    return "screen_node"
