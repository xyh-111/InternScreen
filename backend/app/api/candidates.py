"""候选人记录接口。"""

from fastapi import APIRouter, HTTPException

from app.services import storage

router = APIRouter(prefix="/api", tags=["candidates"])


@router.get("/candidates")
def list_candidates():
    return storage.list_runs()


@router.get("/candidates/{thread_id}")
def get_candidate_run(thread_id: str):
    run = storage.get_run(thread_id)
    if run is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return run


@router.delete("/candidates/{thread_id}")
def delete_candidate_run(thread_id: str):
    deleted = storage.delete_run(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}
