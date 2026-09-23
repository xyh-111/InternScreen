"""Agent 运行接口：/api/agent/run | /resume | /upload"""

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from langgraph.types import Command
from pydantic import BaseModel

from app.graph.builder import build_screening_graph
from app.graph.state import initial_state
from app.services import storage

logger = logging.getLogger("internscreen.agent")

router = APIRouter(prefix="/api/agent", tags=["agent"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


class RunRequest(BaseModel):
    input_type: str  # "text" | "pdf"
    raw_input: str


class ResumeRequest(BaseModel):
    thread_id: str
    human_input: dict


def _log_trace(update: dict) -> None:
    """把某个节点产出的 trace step 实时打印到终端，供开发人员观察。"""
    for step in update.get("trace") or []:
        detail = {k: v for k, v in step.items() if k != "node"}
        logger.info(
            "trace | %s | %s",
            step.get("node"),
            json.dumps(detail, ensure_ascii=False, default=str),
        )


async def _drive(graph, payload, config) -> dict:
    """以 updates 模式驱动图：逐节点实时打印 trace，结束后取 checkpoint 快照。

    图的执行语义与 ainvoke 一致；用快照而非自行合并分片，是为了让
    interrupt 信息与合并后的 state 都取自 LangGraph 的权威来源。
    """
    async for chunk in graph.astream(payload, config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if node_name == "__interrupt__" or not isinstance(update, dict):
                continue
            _log_trace(update)

    snapshot = await graph.aget_state(config)
    result = dict(snapshot.values)
    if snapshot.interrupts:
        result["__interrupt__"] = snapshot.interrupts
    return result


def _completed_response(result: dict, thread_id: str) -> dict:
    return {
        "status": "COMPLETED",
        "thread_id": thread_id,
        "candidate_id": result.get("candidate_id"),
        "rating": result.get("rating"),
        "score": result.get("score"),
        "hard_filter": result.get("hard_filter"),
        "explanation": result.get("explanation"),
        "fields": result.get("fields"),
        "trace": result.get("trace", []),
    }


def _persist(result: dict, thread_id: str, status: str) -> None:
    storage.save_run(
        thread_id=thread_id,
        candidate_id=result.get("candidate_id", ""),
        status=status,
        rating=result.get("rating"),
        final_score=(result.get("score") or {}).get("final_score"),
        hard_passed=(result.get("hard_filter") or {}).get("passed"),
        explanation=result.get("explanation"),
        score=result.get("score"),
        trace=result.get("trace"),
        payload=result.get("__interrupt_payload__"),
        fields=result.get("fields"),
    )


@router.post("/run")
async def run_agent(req: RunRequest):
    graph = build_screening_graph()
    thread_id = str(uuid.uuid4())
    candidate_id = storage.next_candidate_id()
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(
        "run start | thread_id=%s | candidate_id=%s | input_type=%s",
        thread_id,
        candidate_id,
        req.input_type,
    )

    result = await _drive(
        graph, initial_state(candidate_id, req.input_type, req.raw_input), config
    )

    # 姓名来自图内 extract_node 的抽取结果，因此入库放在图运行之后。
    storage.upsert_candidate(
        candidate_id=candidate_id,
        name=(result.get("fields") or {}).get("name") or None,
        source_type=req.input_type,
        raw_input=req.raw_input,
    )

    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        result["__interrupt_payload__"] = payload
        _persist(result, thread_id, "WAITING_REVIEW")
        logger.info("run end   | thread_id=%s | status=WAITING_REVIEW", thread_id)
        return {
            "status": "WAITING_REVIEW",
            "thread_id": thread_id,
            "candidate_id": candidate_id,
            "interrupt_payload": payload,
            "trace": result.get("trace", []),
        }

    _persist(result, thread_id, "COMPLETED")
    logger.info(
        "run end   | thread_id=%s | status=COMPLETED | rating=%s",
        thread_id,
        result.get("rating"),
    )
    return _completed_response(result, thread_id)


@router.post("/resume")
async def resume_agent(req: ResumeRequest):
    graph = build_screening_graph()
    config = {"configurable": {"thread_id": req.thread_id}}

    logger.info("resume start | thread_id=%s", req.thread_id)

    try:
        result = await _drive(graph, Command(resume=req.human_input), config)
    except Exception as exc:  # noqa: BLE001 - 恢复失败多为 thread_id 无效
        raise HTTPException(
            status_code=404, detail=f"恢复失败，thread_id 可能已失效：{exc}"
        ) from exc

    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        result["__interrupt_payload__"] = payload
        _persist(result, req.thread_id, "WAITING_REVIEW")
        logger.info(
            "resume end | thread_id=%s | status=WAITING_REVIEW", req.thread_id
        )
        return {
            "status": "WAITING_REVIEW",
            "thread_id": req.thread_id,
            "candidate_id": result.get("candidate_id"),
            "interrupt_payload": payload,
            "trace": result.get("trace", []),
        }

    _persist(result, req.thread_id, "COMPLETED")
    logger.info(
        "resume end | thread_id=%s | status=COMPLETED | rating=%s",
        req.thread_id,
        result.get("rating"),
    )
    return _completed_response(result, req.thread_id)


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """接收 PDF 简历，落盘后返回路径，供 /api/agent/run 使用。"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / f"{uuid.uuid4()}.pdf"
    target.write_bytes(await file.read())

    return {"file_path": str(target), "filename": file.filename}
