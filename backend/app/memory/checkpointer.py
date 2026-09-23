"""Checkpointer 单例。

必须模块级共享：若每次 build_screening_graph() 都新建 MemorySaver，
则 /api/agent/resume 用同一 thread_id 恢复时会找不到状态，Command(resume=...) 必然失败。
"""

from langgraph.checkpoint.memory import MemorySaver

CHECKPOINTER = MemorySaver()


def get_checkpointer() -> MemorySaver:
    return CHECKPOINTER
