"""SQLite 业务数据存储。

LangGraph 图状态由 MemorySaver 负责；这里只落库候选人信息与运行记录，
用于前端历史列表与 trace 回放。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "internscreen.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
  candidate_id TEXT PRIMARY KEY,
  name         TEXT,
  source_type  TEXT,
  raw_input    TEXT,
  created_at   TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  thread_id    TEXT PRIMARY KEY,
  candidate_id TEXT,
  status       TEXT,
  rating       TEXT,
  final_score  INTEGER,
  hard_passed  INTEGER,
  explanation  TEXT,
  score_json   TEXT,
  trace_json   TEXT,
  payload_json TEXT,
  fields_json  TEXT,
  created_at   TEXT,
  updated_at   TEXT
);
"""


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        # fields_json 是后加的列，老库需要补上（CREATE TABLE IF NOT EXISTS 不会改已存在的表）
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        if "fields_json" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN fields_json TEXT")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def next_candidate_id() -> str:
    """生成 CYYYYMMDD-NNN 形式的候选人编号（当日序号递增）。"""
    prefix = f"C{datetime.now().strftime('%Y%m%d')}-"
    with _connect() as conn:
        row = conn.execute(
            "SELECT candidate_id FROM candidates WHERE candidate_id LIKE ? "
            "ORDER BY candidate_id DESC LIMIT 1",
            (prefix + "%",),
        ).fetchone()
    seq = int(row["candidate_id"].rsplit("-", 1)[1]) + 1 if row else 1
    return f"{prefix}{seq:03d}"


def upsert_candidate(
    candidate_id: str, name: str | None, source_type: str, raw_input: str
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO candidates (candidate_id, name, source_type, raw_input, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
              name = excluded.name,
              source_type = excluded.source_type,
              raw_input = excluded.raw_input
            """,
            (candidate_id, name, source_type, raw_input, _now()),
        )


def save_run(
    thread_id: str,
    candidate_id: str,
    status: str,
    rating: str | None = None,
    final_score: int | None = None,
    hard_passed: bool | None = None,
    explanation: str | None = None,
    score: dict | None = None,
    trace: list | None = None,
    payload: dict | None = None,
    fields: dict | None = None,
) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
              thread_id, candidate_id, status, rating, final_score, hard_passed,
              explanation, score_json, trace_json, payload_json, fields_json,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
              status = excluded.status,
              rating = excluded.rating,
              final_score = excluded.final_score,
              hard_passed = excluded.hard_passed,
              explanation = excluded.explanation,
              score_json = excluded.score_json,
              trace_json = excluded.trace_json,
              payload_json = excluded.payload_json,
              fields_json = excluded.fields_json,
              updated_at = excluded.updated_at
            """,
            (
                thread_id,
                candidate_id,
                status,
                rating,
                final_score,
                None if hard_passed is None else int(hard_passed),
                explanation,
                json.dumps(score, ensure_ascii=False) if score is not None else None,
                json.dumps(trace, ensure_ascii=False) if trace is not None else None,
                json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                json.dumps(fields, ensure_ascii=False) if fields is not None else None,
                now,
                now,
            ),
        )


def run_buckets() -> list[dict]:
    """按 (status, rating) 聚合运行记录数，供统计接口使用。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, rating, COUNT(*) AS count FROM runs GROUP BY status, rating"
        ).fetchall()
    return [
        {"status": row["status"], "rating": row["rating"], "count": row["count"]}
        for row in rows
    ]


def list_runs(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT r.*, c.name AS candidate_name, c.source_type
            FROM runs r
            LEFT JOIN candidates c ON c.candidate_id = r.candidate_id
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_run(row) for row in rows]


def get_run(thread_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT r.*, c.name AS candidate_name, c.source_type, c.raw_input
            FROM runs r
            LEFT JOIN candidates c ON c.candidate_id = r.candidate_id
            WHERE r.thread_id = ?
            """,
            (thread_id,),
        ).fetchone()
    return _row_to_run(row) if row else None


def delete_run(thread_id: str) -> bool:
    """删除指定运行记录。返回是否删除了至少一行。

    只删 runs 表；candidates 表保留（历史列表用 LEFT JOIN，缺 runs 行就自然消失）。
    """
    with _connect() as conn:
        cur = conn.execute("DELETE FROM runs WHERE thread_id = ?", (thread_id,))
    return cur.rowcount > 0


def list_pending_reviews() -> list[dict]:
    return [run for run in list_runs() if run["status"] == "WAITING_REVIEW"]


def _row_to_run(row: sqlite3.Row) -> dict:
    def _load(key: str):
        raw = row[key]
        return json.loads(raw) if raw else None

    return {
        "thread_id": row["thread_id"],
        "candidate_id": row["candidate_id"],
        "candidate_name": row["candidate_name"],
        "source_type": row["source_type"],
        "raw_input": row["raw_input"] if "raw_input" in row.keys() else None,
        "status": row["status"],
        "rating": row["rating"],
        "final_score": row["final_score"],
        "hard_passed": None if row["hard_passed"] is None else bool(row["hard_passed"]),
        "explanation": row["explanation"],
        "score": _load("score_json"),
        "trace": _load("trace_json") or [],
        "payload": _load("payload_json"),
        "fields": _load("fields_json"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
