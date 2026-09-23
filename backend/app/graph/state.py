"""ScreeningState 与相关枚举 / 结构化抽取模型定义。"""

from enum import Enum
from typing import Annotated, Literal, Optional

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class InputType(str, Enum):
    text = "text"
    pdf = "pdf"


class DegreeLevel(str, Enum):
    phd = "phd"
    master = "master"
    bachelor = "bachelor"
    other = "other"


class SchoolTier(str, Enum):
    double_first_class = "double_first_class"
    other = "other"
    unknown = "unknown"


class AIToolExperience(str, Enum):
    project = "project"
    daily_chat = "daily_chat"
    none = "none"
    unknown = "unknown"


class Rating(str, Enum):
    recommend = "推荐进入笔试"
    backup = "备选"
    reject = "暂不推进"
    review = "待人工复核"


class ExtractedFields(BaseModel):
    """LLM 结构化抽取输出"""

    name: Optional[str] = Field(None, description="候选人姓名")
    degree_level: Optional[Literal["phd", "master", "bachelor", "other"]] = Field(
        None, description="学历层次"
    )
    major: Optional[str] = Field(None, description="专业")
    bachelor_school: Optional[str] = Field(None, description="本科院校名称")
    bachelor_school_tier: Optional[
        Literal["double_first_class", "other", "unknown"]
    ] = Field(None, description="本科院校层次：双一流/其他/未知")
    graduate_school: Optional[str] = Field(None, description="研究生（硕士/博士）院校名称")
    graduate_school_tier: Optional[
        Literal["double_first_class", "other", "unknown"]
    ] = Field(None, description="研究生院校层次：双一流/其他/未知")
    ai_tool_experience: Optional[
        Literal["project", "daily_chat", "none", "unknown"]
    ] = Field(None, description="AI工具使用经历")
    ai_tool_evidence: Optional[str] = Field(None, description="AI工具使用的证据原文")
    internship_duration_months: Optional[float] = Field(
        None, description="可实习时长（月）"
    )
    days_per_week: Optional[int] = Field(None, description="每周到岗天数")
    chengdu_onsite: Optional[bool] = Field(None, description="是否成都线下")
    evidence: dict = Field(default_factory=dict, description="每个字段的原文证据")
    confidence: float = Field(0.0, description="整体抽取置信度 0-1")


class ScreeningState(TypedDict):
    """LangGraph 筛选流程的全局状态"""

    # 输入
    candidate_id: str
    input_type: InputType
    raw_input: str

    # 解析结果
    parsed_text: Optional[str]
    parse_confidence: float
    parse_method: Optional[str]

    # 抽取字段
    fields: Optional[dict]
    field_evidence: Optional[dict]
    field_confidence: float

    # 验证结果
    validation_passed: bool
    validation_reasons: list[str]
    need_review: bool

    # 人工复核
    review_result: Optional[dict]
    review_resolved: bool

    # 评分与评级
    hard_filter: Optional[dict]
    score: Optional[dict]
    rating: Optional[str]

    # 解释
    explanation: Optional[str]

    # Trace
    trace: Annotated[list[dict], lambda x, y: x + y]

    # 消息（LangGraph 标准）
    messages: Annotated[list, add_messages]


def initial_state(candidate_id: str, input_type: str, raw_input: str) -> ScreeningState:
    """构造图的初始状态"""
    return {
        "candidate_id": candidate_id,
        "input_type": InputType(input_type),
        "raw_input": raw_input,
        "parsed_text": None,
        "parse_confidence": 0.0,
        "parse_method": None,
        "fields": None,
        "field_evidence": None,
        "field_confidence": 0.0,
        "validation_passed": False,
        "validation_reasons": [],
        "need_review": False,
        "review_result": None,
        "review_resolved": False,
        "hard_filter": None,
        "score": None,
        "rating": None,
        "explanation": None,
        "trace": [],
        "messages": [],
    }
