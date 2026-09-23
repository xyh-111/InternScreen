"""规则配置接口。"""

from fastapi import APIRouter

from app.services.rule_engine import load_rules

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
def get_rules():
    return load_rules()
