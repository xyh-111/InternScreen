"""抽取工具：LLM 结构化抽取。"""

import json
import logging

from app.graph.state import ExtractedFields
from app.services.llm import get_llm

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """你是一个简历信息抽取助手。请从以下简历文本中抽取结构化字段。

要求：
1. 每个字段必须附上原文证据
2. 如果字段在原文中未明确提及，设为 null
3. 不要推测，只抽取原文明确的信息
4. name：候选人姓名，只取原文出现的姓名本身，不要带「姓名：」等前缀
5. bachelor_school：本科院校**完整校名**（如"四川大学"、"中国电子科技大学"、"四川大学锦江学院"），
   禁止填"双一流"、"非双一流"、"211"、"985"、"普通高校"、"重点大学"等层次标签。
   如果原文只提层次未提具体校名，此字段填 null，层次信息写入 bachelor_school_tier。
6. graduate_school：研究生（硕士/博士）院校名称，规则同上；未读研填 null。
7. bachelor_school_tier / graduate_school_tier：对应院校的层次，
   985/211/双一流院校填 double_first_class，其他院校填 other，无法判断填 unknown。
   注意：**不要从 tier 标签反推校名**，两者独立抽取。
8. 可实习时长如果写"6个月以上"，设为 6；"3个月"这类明确的写 3；"待定/面议/未提及"设为 null
9. ai_tool_experience：在项目/实习中实际使用 AI 工具开发填 project；
   仅用于日常聊天、写论文、查资料填 daily_chat；完全未提及填 none；无法判断填 unknown
10. ai_tool_evidence：若 ai_tool_experience 为 project，必须给出原文证据片段
11. days_per_week：每周到岗天数，必须是 1-7 的整数；"每周可到岗 5 天"填 5
12. confidence：你对本次抽取准确度的整体置信度，0-1 之间的小数

简历文本：
{text}
"""

_JSON_PROMPT = EXTRACT_PROMPT + """
只输出一个 JSON 对象，不要输出任何解释或 markdown 代码块。
JSON 的键为：name, degree_level, major, bachelor_school,
bachelor_school_tier, graduate_school, graduate_school_tier, ai_tool_experience,
ai_tool_evidence, internship_duration_months, days_per_week, chengdu_onsite, evidence, confidence
"""


def llm_extract(text: str) -> ExtractedFields:
    """调用 LLM 抽取字段。

    首选 with_structured_output；若 DashScope 的 function calling 不可用，
    回退到 JSON 模式解析（这是本工程唯一的外部边界兜底）。
    最终统一过一次校名清洗：LLM 偶尔会把「双一流 / 非双一流 / 普通高校」
    这类 tier 标签塞进 school 字段而不是 school_tier 字段，需要纠正。
    """
    llm = get_llm()

    try:
        structured_llm = llm.with_structured_output(ExtractedFields)
        raw = structured_llm.invoke(EXTRACT_PROMPT.format(text=text))
    except Exception as exc:  # noqa: BLE001 - 外部模型能力不可控
        logger.warning("with_structured_output 失败，回退 JSON 解析：%s", exc)
        raw_json = llm.invoke(_JSON_PROMPT.format(text=text))
        content = raw_json.content if hasattr(raw_json, "content") else str(raw_json)
        raw = ExtractedFields.model_validate_json(_strip_code_fence(content))

    return _sanitize_school_names(raw)


# —— 校名 ↔ tier 标签纠错 ——

_TIER_KEYWORDS = (
    "双一流", "世界一流", "非双一流", "211", "985", "普通高校",
    "普通本科", "重点高校", "重点大学", "名校", "知名高校", "双非",
)


def _sanitize_school_names(fields: ExtractedFields) -> ExtractedFields:
    """纠正 LLM 把 tier 标签塞进 school 字段的情况。

    规则：school 字段如果**只**含 tier 关键词、不含任何 2 字以上的真实校名，
    就把 tier 正确移到对应的 school_tier 字段，school 置空。
    反过来，如果 school_tier 是 unknown 但 school 里有明确的 tier 标签，
    也会反向纠正。
    """
    # 1. 清理 bachelor_school
    fields = _fix_one_school(fields, "bachelor_school", "bachelor_school_tier")
    # 2. 清理 graduate_school
    fields = _fix_one_school(fields, "graduate_school", "graduate_school_tier")
    return fields


def _fix_one_school(fields: ExtractedFields, school_field: str, tier_field: str) -> ExtractedFields:
    school = getattr(fields, school_field, None)
    tier = getattr(fields, tier_field, None)
    if not school:
        return fields

    school_str = str(school).strip()
    if not school_str:
        return fields

    # 检测校名里是否含 tier 关键词（按长度降序替换，避免子串问题：
    # 比如「非双一流」应在「双一流」之前替换）
    hit_keywords = [kw for kw in sorted(_TIER_KEYWORDS, key=len, reverse=True) if kw in school_str]

    # 检测是否有真实校名：把所有 tier 关键词 + 常见后缀词剥掉，看剩什么
    REMOVE_SUFFIXES = ("高校", "学校", "本科", "专科", "学院", "大学", "院校", "研究所")

    remaining = school_str
    for kw in hit_keywords:
        remaining = remaining.replace(kw, "")
    # 清孤立括号
    import re
    remaining = re.sub(r"[（()）]", "", remaining).strip()
    # 清泛指后缀词（但只在剩余文本很短时才剥，避免误杀真实校名的一部分）
    if len(remaining) <= 6:
        for suf in REMOVE_SUFFIXES:
            if remaining == suf:
                remaining = ""
                break

    has_real_school = len(remaining) >= 2 and _has_chinese(remaining)

    if hit_keywords and not has_real_school:
        # 校名里只有 tier 标签，没有真实校名 → 纠正
        if tier in (None, "unknown"):
            inferred = _infer_tier_from_keywords(hit_keywords)
            if inferred:
                setattr(fields, tier_field, inferred)
                logger.info(
                    "%s 从 tier 关键词推断为 %s（原 school=%r）",
                    tier_field, inferred, school_str,
                )
        setattr(fields, school_field, None)
        logger.info(
            "%s 含 tier 标签无真实校名，已置空（原=%r）",
            school_field, school_str,
        )
    elif hit_keywords and has_real_school:
        # 校名 + tier 标签都有 → 把 tier 标签从校名里剥掉
        setattr(fields, school_field, remaining)
        logger.info(
            "%s 含 tier 标签，已剥离（原=%r → 剩余=%r）",
            school_field, school_str, remaining,
        )
        if tier in (None, "unknown"):
            inferred = _infer_tier_from_keywords(hit_keywords)
            if inferred:
                setattr(fields, tier_field, inferred)

    return fields


def _infer_tier_from_keywords(keywords: list[str]) -> str | None:
    """从命中的 tier 关键词推断 school_tier 值。"""
    for kw in keywords:
        if kw in ("双一流", "世界一流", "211", "985", "重点高校", "重点大学", "名校", "知名高校"):
            return "double_first_class"
        if kw in ("非双一流", "普通高校", "普通本科", "双非"):
            return "other"
    return None


def _has_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -len("```")]
    return text.strip()
