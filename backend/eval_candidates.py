"""评估脚本：用 test/ 下 10 份 PDF 简历跑一遍 InternScreen。

用法：
    1. 先启动后端：uvicorn app.main:app --reload （在 backend/ 目录）
    2. 再运行：    .\.venv\Scripts\python.exe eval_candidates.py

产出：
    - 控制台 Markdown 汇总表
    - backend/eval_result.json 结构化留底
"""

import json
import sys
import time
from pathlib import Path

import requests

BACKEND = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "test"
OUTPUT = Path(__file__).resolve().parent / "eval_result.json"

# 关心的抽取字段
KEY_FIELDS = [
    "name",
    "degree_level",
    "bachelor_school",
    "bachelor_school_tier",
    "master_school",
    "master_school_tier",
    "ai_tool_experience",
    "duration_months",
    "days_per_week",
    "onsite_chengdu",
]


def health_check() -> None:
    try:
        r = requests.get(f"{BACKEND}/api/health", timeout=3)
        r.raise_for_status()
        print("✅ 后端健康检查通过\n")
    except Exception as exc:
        print(f"❌ 后端未启动：{exc}")
        print(f"   请先在 backend/ 目录运行：.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload")
        sys.exit(1)


def run_one(pdf_path: Path) -> dict:
    """上传 PDF → 跑 agent → 返回结构化结果（不自动 resume）。"""
    result = {
        "filename": pdf_path.name,
        "rating": None,
        "score": None,
        "hard_filter": None,
        "explanation": None,
        "status": None,
        "reasons": None,
        "fields": {},
        "error": None,
    }

    # 1) 上传 PDF
    try:
        with open(pdf_path, "rb") as fh:
            upload = requests.post(
                f"{BACKEND}/api/agent/upload",
                files={"file": fh},
                timeout=10,
            )
        upload.raise_for_status()
        file_path = upload.json()["file_path"]
    except Exception as exc:
        result["error"] = f"上传失败：{exc}"
        return result

    # 2) 跑 agent
    try:
        run = requests.post(
            f"{BACKEND}/api/agent/run",
            json={"input_type": "pdf", "raw_input": file_path},
            timeout=120,
        )
        run.raise_for_status()
        data = run.json()
    except Exception as exc:
        result["error"] = f"运行失败：{exc}"
        return result

    result["status"] = data["status"]

    if data["status"] == "WAITING_REVIEW":
        result["reasons"] = (data.get("interrupt_payload") or {}).get("reasons")
        result["fields"] = (data.get("interrupt_payload") or {}).get("fields") or {}
    else:
        result["rating"] = data.get("rating")
        result["score"] = data.get("score")
        result["hard_filter"] = data.get("hard_filter")
        result["explanation"] = data.get("explanation")
        result["fields"] = data.get("fields") or {}

    return result


def fmt_score(score: dict | None) -> str:
    if not score:
        return "-"
    return (
        f"{score.get('degree', '-')}/{score.get('school', '-')}/"
        f"{score.get('ai_tool', '-')}/{score.get('stability', '-')}/"
        f"{score.get('days_per_week', '-')}"
        f" = {score.get('final_score', '-')}"
        f" (加分+{score.get('bonus', 0)})"
    )


def fmt_hard(hf: dict | None) -> str:
    if hf is None:
        return "通过"
    if hf.get("passed"):
        return "通过"
    reasons = hf.get("reasons") or []
    return "不通过：" + "；".join(reasons)


def main() -> None:
    health_check()

    pdfs = sorted(TEST_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"❌ 未找到 PDF：{TEST_DIR}")
        sys.exit(1)
    print(f"📄 发现 {len(pdfs)} 份 PDF")
    print(f"⏱ 预估耗时：~{len(pdfs) * 15}s\n")

    all_results: list[dict] = []
    t0 = time.time()

    for i, pdf in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] 处理 {pdf.name} ...")
        r = run_one(pdf)
        all_results.append(r)

        if r["error"]:
            print(f"  ❌ {r['error']}")
        elif r["status"] == "WAITING_REVIEW":
            print(f"  ⏸  待复核 reasons={r['reasons']}")
        else:
            print(f"  ✅ {r['rating']}  score={fmt_score(r['score'])}  hard={fmt_hard(r['hard_filter'])}")

        # 打印关键字段（方便人工 review）
        f = r["fields"] or {}
        keys_shown = [k for k in KEY_FIELDS if f.get(k) not in (None, "")]
        if keys_shown:
            print(f"  📋 字段：{', '.join(f'{k}={f[k]}' for k in keys_shown)}")
        print()

    elapsed = time.time() - t0

    # ==== Markdown 汇总表 ====
    print("=" * 90)
    print("📊 汇总")
    print("=" * 90)
    print()
    print("| # | 文件名 | 评级 | 硬性格 | 最终分 | 关键信息 |")
    print("|---|--------|------|--------|--------|----------|")
    for i, r in enumerate(all_results, 1):
        if r["error"]:
            print(f"| {i} | {r['filename']} | ❌ ERROR | - | - | {r['error'][:40]} |")
            continue
        if r["status"] == "WAITING_REVIEW":
            reasons = "；".join(r["reasons"] or [])
            f = r["fields"] or {}
            info = f"复核：{reasons[:50]} | tier={f.get('bachelor_school_tier', '?')}"
            print(f"| {i} | {r['filename']} | ⏸ 待复核 | - | - | {info} |")
        else:
            f = r["fields"] or {}
            tier = f.get("bachelor_school_tier") or f.get("master_school_tier") or "?"
            school = f.get("master_school") or f.get("bachelor_school") or "-"
            ai = f.get("ai_tool_experience") or "-"
            info = f"{school}/{tier} | ai={ai} | dur={f.get('duration_months', '-')}d={f.get('days_per_week', '-')} onsite={f.get('onsite_chengdu', '-')}"
            score = (r["score"] or {}).get("final_score", "-")
            print(
                f"| {i} | {r['filename']} | {r['rating'] or '-'} | "
                f"{fmt_hard(r['hard_filter'])} | {score} | {info} |"
            )

    # 统计
    total = len(all_results)
    completed = sum(1 for r in all_results if r["status"] == "COMPLETED")
    waiting = sum(1 for r in all_results if r["status"] == "WAITING_REVIEW")
    errors = sum(1 for r in all_results if r["error"])
    recommends = sum(
        1 for r in all_results
        if r["status"] == "COMPLETED" and r["rating"] in ("推荐进入笔试", "备选")
    )
    rejects = sum(
        1 for r in all_results
        if r["status"] == "COMPLETED" and r["rating"] == "暂不推进"
    )

    print()
    print(f"📈 统计：总计 {total} | 完成 {completed} | 待复核 {waiting} | 错误 {errors}")
    print(f"   其中：推荐/备选 {recommends} | 暂不推进 {rejects}")
    print(f"   总耗时：{elapsed:.1f}s")

    # 留底
    OUTPUT.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 结果已保存到：{OUTPUT}")


if __name__ == "__main__":
    main()
