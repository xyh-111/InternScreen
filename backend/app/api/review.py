"""人工复核队列接口。"""

from fastapi import APIRouter

from app.services import storage

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/pending")
def list_pending():
    return storage.list_pending_reviews()
