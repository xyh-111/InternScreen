"""LangGraph 节点实现。

原则：节点只负责编排与状态写入；规则判定一律交给 services.rule_engine。
"""

from langgraph.types import interrupt

from app.graph.state import InputType, Rating, ScreeningState
from app.services.rule_engine import (
    precheck_hard,
    resolve_school_tier,
    run_rules,
    validation_config,
)
from app.tools.extract_tools import llm_extract
from app.tools.parse_tools import parse_pdf_tool, parse_text_tool


def parse_node(state: ScreeningState) -> dict:
    """解析节点：根据 input_type 选择解析方式"""
    input_type = state["input_type"]
    raw = state["raw_input"]

    if input_type == InputType.pdf:
        parsed = parse_pdf_tool.invoke({"file_path": raw})
        method = "pdfplumber"
        confidence = 0.85
    else:
        parsed = parse_text_tool.invoke({"text": raw})
        method = "text"
        confidence = 0.95

    return {
        "parsed_text": parsed,
        "parse_method": method,
        "parse_confidence": confidence,
        "trace": [
            {
                "node": "parse_node",
                "input_type": InputType(input_type).value,
                "method": method,
                "output_length": len(parsed),
            }
        ],
    }


def extract_node(state: ScreeningState) -> dict:
    """抽取节点：使用 LLM 结构化输出抽取字段"""
    result = llm_extract(state["parsed_text"] or "")
    dumped = result.model_dump()

    return {
        "fields": dumped,
        "field_evidence": result.evidence,
        "field_confidence": result.confidence,
        "trace": [
            {
                "node": "extract_node",
                "method": "llm_structured_output",
                "confidence": result.confidence,
                "missing_fields": [k for k, v in dumped.items() if v is None],
            }
        ],
    }


def validate_node(state: ScreeningState) -> dict:
    """验证节点：字段完整性 + 院校层次冲突 + 硬性条件预判。

    路由策略（按优先级）：
    1. **硬性条件确定性失败**（已抽到值但不满足）→ 跳过 review，直接进 screen_node
       例：duration=2 而 min=3、degree_level=other、chengdu_onsite=False
    2. 否则如果有 review_reasons（院校层次冲突 / 字段缺失 / 置信度低等）→ 进 review_node
       注：字段缺失走 review；确定性失败不走 review
    3. 全部通过 → 进 screen_node
    """
    cfg = validation_config()
    fields = state["fields"] or {}
    reasons: list[str] = []

    # —— 硬性条件预判：区分确定性失败 vs 字段缺失 ——
    precheck = precheck_hard(fields)
    deterministic_failures = precheck["deterministic_failures"]
    missing_fields = precheck["missing_fields"]

    # 字段缺失也列入 review reasons（等人工补）
    if "internship_duration_months" in missing_fields:
        reasons.append("可实习时长缺失")
    if "days_per_week" in missing_fields:
        reasons.append("每周到岗天数缺失")
    if "chengdu_onsite" in missing_fields:
        reasons.append("是否成都线下缺失")

    # —— 其他需要复核的原因 ——
    if state["field_confidence"] < cfg["min_field_confidence"]:
        reasons.append(f"抽取置信度过低：{state['field_confidence']}")

    if fields.get("ai_tool_experience") == "project" and not fields.get(
        "ai_tool_evidence"
    ):
        reasons.append("AI工具项目经历缺少证据")

    school_review = resolve_school_tier(fields)["review_reason"]
    if school_review:
        reasons.append(school_review)

    # —— 最终路由判定 ——
    hard_already_failed = len(deterministic_failures) > 0
    need_review = (not hard_already_failed) and len(reasons) > 0

    return {
        "validation_passed": not need_review,
        "validation_reasons": reasons,
        "need_review": need_review,
        "hard_already_failed": hard_already_failed,
        "trace": [
            {
                "node": "validate_node",
                "need_review": need_review,
                "hard_already_failed": hard_already_failed,
                "deterministic_failures": deterministic_failures,
                "missing_fields": missing_fields,
                "reasons": reasons,
            }
        ],
    }


def screen_node(state: ScreeningState) -> dict:
    """筛选节点：调用规则引擎，硬性过滤 → 评分 → 加分 → 评级"""
    fields = state["fields"] or {}
    if state.get("review_result"):
        fields = {**fields, **state["review_result"]}

    outcome = run_rules(fields)
    hard = outcome["hard_filter"]
    score = outcome["score"]
    rating = outcome["rating"]

    if not hard["passed"]:
        trace_step = {
            "node": "screen_node",
            "hard_filter": "rejected",
            "reasons": hard["reasons"],
        }
    else:
        trace_step = {
            "node": "screen_node",
            "hard_filter": "passed",
            "raw_score": score["raw_score"],
            "bonus": score["bonus"],
            "final_score": score["final_score"],
            "rating": rating,
        }

    return {
        "fields": fields,
        "hard_filter": hard,
        "score": score,
        "rating": rating,
        "trace": [trace_step],
    }


def review_node(state: ScreeningState) -> dict:
    """复核节点：使用 interrupt() 暂停，等待人工输入"""
    review_payload = {
        "candidate_id": state["candidate_id"],
        "reasons": state["validation_reasons"],
        "fields": state["fields"],
        "field_confidence": state["field_confidence"],
        "suggestion": _generate_review_suggestion(state),
    }

    human_input = interrupt(review_payload)

    return {
        "review_result": human_input,
        "review_resolved": True,
        "fields": {**(state["fields"] or {}), **(human_input or {})},
        "need_review": False,
        "trace": [
            {
                "node": "review_node",
                "action": "human_resolved",
                "review_input": human_input,
            }
        ],
    }


def explain_node(state: ScreeningState) -> dict:
    """解释节点：生成人类可读的筛选说明"""
    score = state.get("score")
    rating = state.get("rating")
    hard = state.get("hard_filter")

    if hard and not hard["passed"]:
        explanation = (
            f"候选人 {state['candidate_id']} 未通过硬性条件："
            f"{'；'.join(hard['reasons'])}"
        )
    elif score:
        explanation = (
            f"候选人 {state['candidate_id']} 通过硬性条件。"
            f"学历{score['degree']}分 + 院校{score['school']}分 + "
            f"AI工具{score['ai_tool']}分 + 到岗稳定性{score['stability']}分 + "
            f"每周到岗{score['days_per_week']}分 = 原始分{score['raw_score']}分，"
            f"加分{score['bonus']}分，最终分{score['final_score']}分。"
            f"评级：{rating}。"
        )
    else:
        explanation = f"候选人 {state['candidate_id']} 待人工复核。"

    return {
        "explanation": explanation,
        "trace": [{"node": "explain_node", "explanation": explanation}],
    }


def _generate_review_suggestion(state: ScreeningState) -> str:
    """生成复核建议"""
    reasons = state["validation_reasons"]
    suggestions: list[str] = []

    for reason in reasons:
        if "时长" in reason:
            suggestions.append("请确认候选人可实习的具体月数")
        if "到岗天数" in reason:
            suggestions.append("请确认候选人每周可到岗天数")
        if "成都" in reason:
            suggestions.append("请确认候选人是否可成都线下")
        if "AI工具" in reason:
            suggestions.append("请核实AI工具项目经历的真实性")
        if "院校" in reason:
            suggestions.append("请人工确认候选人的院校层次（本科 / 研究生）")
        if "置信度" in reason:
            suggestions.append("请人工核对抽取字段是否准确")

    return "；".join(suggestions) if suggestions else "请人工复核"


__all__ = [
    "parse_node",
    "extract_node",
    "validate_node",
    "screen_node",
    "review_node",
    "explain_node",
    "Rating",
]
