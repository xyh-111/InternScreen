"""规则引擎单测：纯函数，不需要 DASHSCOPE_API_KEY。"""

import pytest

from app.services.rule_engine import (
    classify_school,
    precheck_hard,
    resolve_school_tier,
    run_rules,
)

JIA_FIELDS = {
    "in_school": True,
    "degree_level": "master",
    "bachelor_school": "电子科技大学",
    "bachelor_school_tier": "double_first_class",
    "ai_tool_experience": "project",
    "ai_tool_evidence": "使用 LangChain 与 GPT-4 搭建简历解析助手",
    "internship_duration_months": 6,
    "days_per_week": 5,
    "chengdu_onsite": True,
}

YI_FIELDS = {
    "in_school": True,
    "degree_level": "master",
    "bachelor_school": "成都信息工程大学",
    "bachelor_school_tier": "other",
    "ai_tool_experience": "project",
    "ai_tool_evidence": "使用 ChatGPT 与 Copilot 开发校园二手交易平台",
    "internship_duration_months": 4,
    "days_per_week": 4,
    "chengdu_onsite": True,
}

# 丙：复核后补录的字段（时长 3 个月、每周 4 天、成都线下）
BING_RESOLVED_FIELDS = {
    "in_school": True,
    "degree_level": "master",
    "bachelor_school": "成都工业学院",
    "bachelor_school_tier": "other",
    "ai_tool_experience": "project",
    "ai_tool_evidence": "在实验室项目中使用 ChatGPT 与通义千问辅助开发数据标注平台",
    "internship_duration_months": 3,
    "days_per_week": 4,
    "chengdu_onsite": True,
}


def test_jia_scores_105():
    outcome = run_rules(JIA_FIELDS)

    assert outcome["hard_filter"]["passed"] is True
    assert outcome["score"]["raw_score"] == 100
    assert outcome["score"]["bonus"] == 5
    assert outcome["score"]["final_score"] == 105
    assert outcome["rating"] == "推荐进入笔试"


def test_yi_scores_80():
    outcome = run_rules(YI_FIELDS)

    assert outcome["hard_filter"]["passed"] is True
    assert outcome["score"]["raw_score"] == 80
    assert outcome["score"]["bonus"] == 0
    assert outcome["score"]["final_score"] == 80
    assert outcome["rating"] == "推荐进入笔试"


def test_bing_after_review_scores_80():
    outcome = run_rules(BING_RESOLVED_FIELDS)

    assert outcome["hard_filter"]["passed"] is True
    assert outcome["score"]["final_score"] == 80
    assert outcome["rating"] == "推荐进入笔试"


def test_hard_filter_rejects_short_duration():
    fields = {**YI_FIELDS, "internship_duration_months": 2}
    outcome = run_rules(fields)

    assert outcome["hard_filter"]["passed"] is False
    assert "可实习时间不满3个月" in outcome["hard_filter"]["reasons"]
    assert outcome["score"] is None
    assert outcome["rating"] == "暂不推进"


def test_hard_filter_rejects_non_onsite():
    fields = {**YI_FIELDS, "chengdu_onsite": False}
    outcome = run_rules(fields)

    assert outcome["hard_filter"]["passed"] is False
    assert "无法成都线下到岗" in outcome["hard_filter"]["reasons"]


def test_list_miss_without_llm_verdict_still_scores_8():
    """名单未命中且 LLM 未给出判断时，仍按非双一流计 8 分，不得静默得 0 分。"""
    fields = {**YI_FIELDS, "bachelor_school_tier": None, "graduate_school_tier": None}

    verdict = resolve_school_tier(fields)
    assert verdict["tier"] == "other"
    assert verdict["review_reason"] is not None

    outcome = run_rules(fields)
    assert outcome["score"]["school"] == 8
    assert outcome["score"]["final_score"] == 80


def test_list_hit_and_llm_agree_is_double_first_class():
    verdict = resolve_school_tier(
        {"bachelor_school": "电子科技大学", "bachelor_school_tier": "double_first_class"}
    )

    assert verdict == {"tier": "double_first_class", "review_reason": None}


def test_list_hit_without_llm_verdict_is_double_first_class():
    verdict = resolve_school_tier({"bachelor_school": "电子科技大学"})

    assert verdict == {"tier": "double_first_class", "review_reason": None}


def test_list_hit_but_llm_says_other_no_review():
    """名单命中双一流时忽略 LLM 的 other 判定（名单是最高权威）。"""
    verdict = resolve_school_tier(
        {"bachelor_school": "电子科技大学", "bachelor_school_tier": "other"}
    )

    assert verdict["tier"] == "double_first_class"
    assert verdict["review_reason"] is None


def test_list_miss_but_llm_says_double_no_review():
    """名单未命中但 LLM 说双一流 → 信任 LLM，不复核（名单可能有遗漏）。"""
    verdict = resolve_school_tier(
        {"bachelor_school": "成都工业学院", "bachelor_school_tier": "double_first_class"}
    )

    assert verdict["tier"] == "double_first_class"
    assert verdict["review_reason"] is None


def test_list_miss_and_llm_says_other_no_review():
    verdict = resolve_school_tier(
        {"bachelor_school": "成都工业学院", "bachelor_school_tier": "other"}
    )

    assert verdict == {"tier": "other", "review_reason": None}


def test_manual_override_wins():
    """人工复核结论优先于名单与 LLM。"""
    verdict = resolve_school_tier(
        {"bachelor_school": "成都工业学院", "school_tier": "double_first_class"}
    )

    assert verdict == {"tier": "double_first_class", "review_reason": None}


def test_alias_and_normalization_hit():
    assert (
        resolve_school_tier({"bachelor_school": "电子科大"})["tier"]
        == "double_first_class"
    )
    assert (
        resolve_school_tier({"bachelor_school": " 电子科技大学（在读）"})["tier"]
        == "double_first_class"
    )


def test_no_substring_match():
    """「四川大学锦江学院」不得因包含「四川大学」而误命中。"""
    verdict = resolve_school_tier({"bachelor_school": "四川大学锦江学院"})

    assert verdict["tier"] == "other"


def test_any_segment_hit_counts():
    """本科未命中、研究生命中，仍算双一流。"""
    verdict = resolve_school_tier(
        {
            "bachelor_school": "成都工业学院",
            "bachelor_school_tier": "other",
            "graduate_school": "四川大学",
            "graduate_school_tier": "double_first_class",
        }
    )

    assert verdict == {"tier": "double_first_class", "review_reason": None}


def test_offsite_campus_is_double_first_class():
    """双一流校名 + 校区/研究生院后缀 → 异地办学，仍算双一流。"""
    for name in (
        "清华大学深圳国际研究生院",
        "北京大学深圳研究生院",
        "山东大学威海校区",
        "中国人民大学苏州校区",
    ):
        assert classify_school(name) == "double_first_class", name
        assert resolve_school_tier({"bachelor_school": name})["review_reason"] is None


def test_paren_campus_hits_by_exact_match():
    """括号式异地校区走「剥离括号后精确匹配」。"""
    assert classify_school("哈尔滨工业大学（威海）") == "double_first_class"


def test_paren_roster_entry_hits():
    """回归：名单里带括号的校名必须能精确命中（归一化保留括号）。"""
    assert classify_school("中国石油大学（华东）") == "double_first_class"
    assert classify_school("中国地质大学（武汉）") == "double_first_class"
    assert classify_school("中国矿业大学（北京）") == "double_first_class"


def test_independent_college_is_other():
    """双一流校名 + 含「学院」后缀 → 挂靠的独立学院，非双一流。"""
    for name in (
        "四川大学锦江学院",
        "华南理工大学广州学院",
        "浙江大学城市学院",
        "成都理工大学工程技术学院",
        "电子科技大学成都学院",
    ):
        assert classify_school(name) == "other", name


def test_independent_college_no_review_when_llm_agrees():
    """独立学院 + 抽取也判非双一流 → 得 8 分且不转复核。"""
    fields = {
        **YI_FIELDS,
        "bachelor_school": "四川大学锦江学院",
        "bachelor_school_tier": "other",
    }

    verdict = resolve_school_tier(fields)
    assert verdict == {"tier": "other", "review_reason": None}

    outcome = run_rules(fields)
    assert outcome["score"]["school"] == 8
    assert outcome["score"]["final_score"] == 80


def test_independent_college_ignores_llm_double():
    """独立学院后缀规则判 other 时忽略 LLM 的 double 判定（名单权威）。"""
    verdict = resolve_school_tier(
        {
            "bachelor_school": "四川大学锦江学院",
            "bachelor_school_tier": "double_first_class",
        }
    )

    assert verdict["tier"] == "other"
    assert verdict["review_reason"] is None


def test_offsite_campus_scores_20():
    """异地校区按双一流计 20 分。"""
    fields = {
        **YI_FIELDS,
        "bachelor_school": "清华大学深圳国际研究生院",
        "bachelor_school_tier": "double_first_class",
    }

    outcome = run_rules(fields)

    assert outcome["score"]["school"] == 20
    assert outcome["score"]["final_score"] == 92


# ===== 硬性条件预判：确定性失败 vs 字段缺失 =====


def test_precheck_distinguishes_missing_vs_deterministic():
    """字段缺失进 missing_fields；已抽到值但不满足进 deterministic_failures。"""
    # 全缺失 → 只有 missing，无 deterministic
    result = precheck_hard({})
    assert result["deterministic_failures"] == []
    assert set(result["missing_fields"]) >= {
        "degree_level",
        "internship_duration_months",
        "days_per_week",
        "chengdu_onsite",
    }

    # 确定性失败：duration 有值但不够
    result = precheck_hard(
        {**YI_FIELDS, "internship_duration_months": 2}
    )
    assert any("可实习时间不满3个月" in r for r in result["deterministic_failures"])
    assert "internship_duration_months" not in result["missing_fields"]


def test_precheck_all_passing_has_empty_lists():
    """所有硬性条件都有值且满足 → 两个列表都空。"""
    result = precheck_hard(YI_FIELDS)
    assert result["deterministic_failures"] == []
    assert result["missing_fields"] == []


def test_precheck_chengdu_onsite_false_is_deterministic():
    """chengdu_onsite=False 是确定性失败，不是缺失。"""
    result = precheck_hard({**YI_FIELDS, "chengdu_onsite": False})
    assert "无法成都线下到岗" in result["deterministic_failures"]
    assert "chengdu_onsite" not in result["missing_fields"]


def test_precheck_degree_other_is_deterministic():
    """degree_level='other' 是确定性失败。"""
    result = precheck_hard({**YI_FIELDS, "degree_level": "other"})
    assert "非本科或研究生" in result["deterministic_failures"]


def test_hard_fail_then_review_should_be_skipped():
    """场景：duration 不够（确定性失败）+ 院校层次需要复核 → 应直接暂不推进，不走 review。

    这就是用户反映的场景：一条硬性条件不满足 + 另一条需要人工审核 → 错误地进了复核。
    """
    # duration=2（不够 3）+ 独立学院（名单判 other，但 LLM 可能说 double_first_class → 冲突）
    fields = {
        "degree_level": "master",
        "internship_duration_months": 2,  # 确定性失败
        "days_per_week": 4,
        "chengdu_onsite": True,
        "bachelor_school": "四川大学锦江学院",  # 名单判独立学院
        "bachelor_school_tier": "double_first_class",  # LLM 判 double_first_class → 冲突
        "ai_tool_experience": "project",
    }

    result = precheck_hard(fields)
    assert result["deterministic_failures"], "应有确定性失败"
    assert any("可实习时间不满" in r for r in result["deterministic_failures"])

    # 跑完整规则 → 必须 hard_filter.passed=False + rating=暂不推进
    outcome = run_rules(fields)
    assert outcome["hard_filter"]["passed"] is False
    assert outcome["rating"] == "暂不推进"
    assert outcome["score"] is None


def test_no_school_name_trusts_llm_tier_no_review():
    """无真实校名 + llm_hit → 直接信任 double_first_class，不触发复核。"""
    result = resolve_school_tier(
        {
            "bachelor_school": None,
            "graduate_school": None,
            "bachelor_school_tier": "double_first_class",
        }
    )
    assert result["tier"] == "double_first_class"
    assert result["review_reason"] is None


def test_no_school_name_llm_other_trusted():
    """无真实校名 + llm_says_other → 信任 other，不复核。"""
    result = resolve_school_tier(
        {
            "bachelor_school": None,
            "graduate_school": None,
            "bachelor_school_tier": "other",
        }
    )
    assert result["tier"] == "other"
    assert result["review_reason"] is None


def test_no_school_name_tier_also_empty_needs_review():
    """无真实校名 + tier 也空 → 仍需复核（两边都无结论）。"""
    result = resolve_school_tier(
        {
            "bachelor_school": None,
            "graduate_school": None,
        }
    )
    assert result["tier"] == "other"
    assert result["review_reason"] is not None
    assert "无真实校名" in result["review_reason"]


def test_any_school_triggers_list_path():
    """有任一真实校名 → 走名单判定逻辑（哪怕另一段为空）。"""
    result = resolve_school_tier(
        {
            "bachelor_school": "四川大学",
            "graduate_school": None,
            "bachelor_school_tier": "unknown",
        }
    )
    # 川大在名单里 → 应该是 double_first_class，无复核
    assert result["tier"] == "double_first_class"
    assert result["review_reason"] is None


def test_run_rules_no_school_llm_double_scores_20():
    """端到端：无真实校名 + llm_tier=double_first_class → 院校应得 20 分。"""
    fields = {
        "degree_level": "master",
        "internship_duration_months": 6,
        "days_per_week": 5,
        "chengdu_onsite": True,
        "ai_tool_experience": "project",
        "bachelor_school": None,
        "graduate_school": None,
        "bachelor_school_tier": "double_first_class",
    }
    outcome = run_rules(fields)
    assert outcome["hard_filter"]["passed"] is True
    assert outcome["score"]["school"] == 20
    assert outcome["score"]["final_score"] >= 100


def test_missing_fields_still_needs_review():
    """字段缺失时不会算 deterministic_failures，run_rules 虽然也会判失败，
    但 validate_node 应该让它走 review。"""
    result = precheck_hard(
        {
            "degree_level": "master",
            "internship_duration_months": None,  # 缺失
            "days_per_week": None,  # 缺失
            "chengdu_onsite": None,  # 缺失
            "bachelor_school": "成都工业学院",  # 名单未命中
            "ai_tool_experience": "project",
        }
    )

    # 三个缺失字段都应在 missing_fields 里，没有 deterministic_failures
    assert result["deterministic_failures"] == []
    assert "internship_duration_months" in result["missing_fields"]
    assert "days_per_week" in result["missing_fields"]
    assert "chengdu_onsite" in result["missing_fields"]

