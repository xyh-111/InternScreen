"""运行统计接口：/api/stats"""

from fastapi import APIRouter

from app.services import storage
from app.services.rule_engine import load_rules

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def get_stats():
    """统计卡所需的 4 个数字。

    - total     总简历数（runs 行数，每次运行一份简历）
    - recommend 推荐简历 = 推荐进入笔试 + 备选
    - pending   待复核简历 = status 为 WAITING_REVIEW
    - reject    暂不推进
    """
    labels = load_rules()["labels"]
    recommend_labels = {labels["recommend"], labels["backup"]}

    total = pending = recommend = reject = 0
    for bucket in storage.run_buckets():
        count = bucket["count"]
        total += count
        if bucket["status"] == "WAITING_REVIEW":
            pending += count
        elif bucket["rating"] in recommend_labels:
            recommend += count
        elif bucket["rating"] == labels["reject"]:
            reject += count

    return {
        "total": total,
        "recommend": recommend,
        "pending": pending,
        "reject": reject,
    }
