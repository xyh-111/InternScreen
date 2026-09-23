"""规则引擎工具封装：供 ToolNode 场景使用。"""

import json

from langchain_core.tools import tool

from app.services.rule_engine import run_rules


@tool
def rule_engine_tool(fields_json: str) -> str:
    """执行规则引擎评分"""
    fields = json.loads(fields_json)
    return json.dumps(run_rules(fields), ensure_ascii=False)
