"""规则引擎：所有阈值与分数均来自 app/config/rules.yaml。

本模块是唯一的规则真源，LangGraph 节点只调用它，不持有任何分数常量。
院校层次不走 LLM 判断，而是用 school_tiers.yaml 的名单 + 后缀词做确定性匹配：
精确/别名命中 → 双一流；双一流校名 + 「校区/研究生院」后缀 → 双一流；
双一流校名 + 「学院」后缀 → 独立学院（非双一流）。名单结论再与 LLM 判断做一致性校验。
"""

import re
from functools import lru_cache
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"
SCHOOL_TIERS_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "school_tiers.yaml"
)

TIER_DOUBLE = "double_first_class"
TIER_OTHER = "other"

# 参与院校层次判定的字段：任一段命中名单即视为双一流
_SCHOOL_FIELDS = ("bachelor_school", "graduate_school")
# LLM 给出的分段层次判断，仅用于与名单结论做一致性校验
_TIER_FIELDS = ("bachelor_school_tier", "graduate_school_tier")


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_school_tiers() -> dict:
    with SCHOOL_TIERS_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def normalize_school(name: str | None) -> str | None:
    """归一化校名：去空白、去首尾标点。**保留括号内容**。

    括号可能是有效信息（如「哈尔滨工业大学（威海）」「中国石油大学（华东）」），
    是否剥离交给 classify_school() 分两次尝试，这里不丢信息。
    """
    if not name:
        return None
    text = re.sub(r"\s+", "", str(name))
    return text.strip("，,。.；;：:、") or None


def _strip_parens(text: str) -> str:
    """剥离括号及其内容：「哈尔滨工业大学（威海）」→「哈尔滨工业大学」。"""
    return re.sub(r"[（(][^)）]*[)）]", "", text)


def classify_school(name: str | None) -> str | None:
    """判定单个校名层次，返回 TIER_DOUBLE / TIER_OTHER / None（无结论）。

    判定顺序：
    1. 归一化后精确命中名单 → 双一流
    2. 剥离括号后精确命中名单 → 双一流（「哈尔滨工业大学（威海）」这类写法）
    3. 别名表命中 → 双一流
    4. 以某双一流校名为前缀时看后缀：
       - 含 campus_suffixes → 双一流（异地校区 / 研究生院）
       - 含 college_suffixes → 非双一流（挂靠的独立学院）
       - 都不含 → 无结论
    5. 其余 → 无结论

    刻意不做任意位置的包含匹配：「四川大学锦江学院」不会被当成「四川大学」，
    而是由「学院」后缀规则判为独立学院。
    """
    normalized = normalize_school(name)
    if not normalized:
        return None

    tiers = load_school_tiers()
    roster = set(tiers.get("double_first_class") or [])
    aliases = tiers.get("aliases") or {}

    def _hit(text: str) -> bool:
        if text in roster:
            return True
        return aliases.get(text) in roster

    for candidate in (normalized, _strip_parens(normalized)):
        if candidate and _hit(candidate):
            return TIER_DOUBLE

    # 前缀取最长匹配，避免「中国矿业大学」抢先匹配「中国矿业大学（北京）」
    parent = max(
        (r for r in roster if normalized.startswith(r) and normalized != r),
        key=len,
        default=None,
    )
    if parent:
        suffix = normalized[len(parent):]
        if any(word in suffix for word in tiers.get("campus_suffixes") or []):
            return TIER_DOUBLE
        if any(word in suffix for word in tiers.get("college_suffixes") or []):
            return TIER_OTHER

    return None


def resolve_school_tier(fields: dict) -> dict:
    """按双一流名单判定院校层次，名单是最高权威。

    返回 {"tier": "double_first_class" | "other", "review_reason": str | None}

    优先级：名单 > LLM。名单一旦命中，直接用名单结论，忽略 LLM。

    判定表：
    | 名单结论       | LLM 结论 | tier               | 复核？ | 理由 |
    |----------------|---------|--------------------|-------|------|
    | 命中双一流      | 任意     | double_first_class | 否    | 名单权威 |
    | 判独立学院      | 任意     | other              | 否    | 名单权威 |
    | 未命中          | 双一流   | double_first_class | 否    | 名单遗漏可能性大，信任 LLM |
    | 未命中          | 非双一流 | other              | 否    | 名单 + LLM 一致 |
    | 未命中          | 无结论   | other              | 是    | 名单未命中且无 LLM 兜底 |
    | 无真实校名      | 双一流   | double_first_class | 否    | 名单无输入，信任 LLM |
    | 无真实校名      | 非双一流 | other              | 否    | 名单无输入，信任 LLM |
    | 无真实校名      | 无结论   | other              | 是    | 两边都没有 |

    fields["school_tier"] 存在时视为人工复核结论，优先级最高。
    """
    override = fields.get("school_tier")
    if override in (TIER_DOUBLE, TIER_OTHER):
        return {"tier": override, "review_reason": None}

    # —— 有真实校名：名单是最高权威 ——
    list_verdicts = [classify_school(fields.get(f)) for f in _SCHOOL_FIELDS]
    list_hit = any(v == TIER_DOUBLE for v in list_verdicts)
    list_other = any(v == TIER_OTHER for v in list_verdicts)

    verdicts = [fields.get(f) for f in _TIER_FIELDS]
    llm_hit = any(v == TIER_DOUBLE for v in verdicts)
    llm_says_other = any(v == TIER_OTHER for v in verdicts)

    # 名单命中 → 直接用名单，忽略 LLM
    if list_hit:
        return {"tier": TIER_DOUBLE, "review_reason": None}
    if list_other:
        return {"tier": TIER_OTHER, "review_reason": None}

    # 名单未命中 → 看 LLM
    if llm_hit:
        return {"tier": TIER_DOUBLE, "review_reason": None}
    if llm_says_other:
        return {"tier": TIER_OTHER, "review_reason": None}

    # 两边都没有 → 复核
    has_real_school = any(
        fields.get(f) and str(fields.get(f)).strip()
        for f in _SCHOOL_FIELDS
    )
    if has_real_school:
        reason = "院校层次无法确认：名单未命中且抽取未给出判断"
    else:
        reason = "院校层次无法确认：无真实校名且抽取未给出判断"
    return {"tier": TIER_OTHER, "review_reason": reason}


def precheck_hard(fields: dict) -> dict:
    """预判硬性条件，区分「确定性失败」和「字段缺失」。

    用于 validate_node 在进入 review 之前快速淘汰：
    - **确定性失败**：字段有值，但值不满足规则（如 duration=2 而 min=3）
      → 这种情况简历已死，无论其他硬性条件还是院校层次要不要复核，
        最终都会被 run_rules() 判暂不推进 → 跳过 review 直接进 screen_node
    - **字段缺失**：字段为 None（LLM 没抽到）
      → 不确定，走 review 让人工补全

    返回 {"deterministic_failures": [str], "missing_fields": [str]}。
    两者都为空 → 硬性条件预检查通过。
    """
    rules = load_rules()
    hard = rules["hard_filter"]

    deterministic: list[str] = []
    missing: list[str] = []

    degree = fields.get("degree_level")
    if degree is None:
        missing.append("degree_level")
    elif degree not in hard["allowed_degrees"]:
        deterministic.append("非本科或研究生")

    duration = fields.get("internship_duration_months")
    if duration is None:
        missing.append("internship_duration_months")
    elif duration < hard["min_internship_months"]:
        deterministic.append(
            f"可实习时间不满{hard['min_internship_months']}个月（抽到 {duration}）"
        )

    days = fields.get("days_per_week")
    if days is None:
        missing.append("days_per_week")
    elif days < hard["min_days_per_week"]:
        deterministic.append(
            f"每周到岗不足{hard['min_days_per_week']}天（抽到 {days}）"
        )

    onsite = fields.get("chengdu_onsite")
    if onsite is None:
        missing.append("chengdu_onsite")
    elif hard["require_chengdu_onsite"] and not onsite:
        deterministic.append("无法成都线下到岗")

    return {
        "deterministic_failures": deterministic,
        "missing_fields": missing,
    }


def run_rules(fields: dict) -> dict:
    """执行硬性过滤 → 评分 → 加分 → 评级。

    返回 {"hard_filter": {...}, "score": {...} | None, "rating": str}
    """
    rules = load_rules()
    hard = rules["hard_filter"]
    scoring = rules["scoring"]
    labels = rules["labels"]

    # ===== 硬性条件 =====
    hard_reasons: list[str] = []

    degree = fields.get("degree_level")
    if degree not in hard["allowed_degrees"]:
        hard_reasons.append("非本科或研究生")

    duration = fields.get("internship_duration_months")
    if duration is None or duration < hard["min_internship_months"]:
        hard_reasons.append(f"可实习时间不满{hard['min_internship_months']}个月")

    days = fields.get("days_per_week")
    if days is None or days < hard["min_days_per_week"]:
        hard_reasons.append(f"每周到岗不足{hard['min_days_per_week']}天")

    if hard["require_chengdu_onsite"] and not fields.get("chengdu_onsite"):
        hard_reasons.append("无法成都线下到岗")

    if hard_reasons:
        return {
            "hard_filter": {"passed": False, "reasons": hard_reasons},
            "score": None,
            "rating": labels["reject"],
        }

    # ===== 评分 =====
    degree_score = scoring["degree"].get(degree, 0)
    school_score = scoring["school_tier"].get(resolve_school_tier(fields)["tier"], 0)
    ai_tool_score = scoring["ai_tool_experience"].get(
        fields.get("ai_tool_experience"), 0
    )

    stability_score = (
        scoring["stability"]["gte_6_months"]
        if duration >= 6
        else scoring["stability"]["else"]
    )
    days_score = (
        scoring["days_per_week"]["gte_5"]
        if days >= 5
        else scoring["days_per_week"]["else"]
    )

    raw_score = (
        degree_score + school_score + ai_tool_score + stability_score + days_score
    )

    # ===== 加分 =====
    bonus_cfg = scoring["bonus"]
    bonus = 0
    if (
        bonus_cfg["condition"] == "stability_and_days_full"
        and stability_score == scoring["stability"]["gte_6_months"]
        and days_score == scoring["days_per_week"]["gte_5"]
    ):
        bonus = bonus_cfg["value"]

    final_score = raw_score + bonus

    # ===== 评级 =====
    if final_score >= rules["rating"]["recommend"]:
        rating = labels["recommend"]
    elif final_score >= rules["rating"]["backup"]:
        rating = labels["backup"]
    else:
        rating = labels["reject"]

    return {
        "hard_filter": {"passed": True, "reasons": []},
        "score": {
            "degree": degree_score,
            "school": school_score,
            "ai_tool": ai_tool_score,
            "stability": stability_score,
            "days_per_week": days_score,
            "raw_score": raw_score,
            "bonus": bonus,
            "final_score": final_score,
        },
        "rating": rating,
    }


def validation_config() -> dict:
    """验证节点使用的阈值配置。"""
    return load_rules()["validation"]
