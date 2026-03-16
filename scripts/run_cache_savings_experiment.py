#!/usr/bin/env python3
"""
验证「命中缓存省 token」的专用实验：
同一 prompt 跑 3 轮，基线组每轮一次 LLM；实验组第 1 轮建基座+模块（多 LLM），
第 2、3 轮命中 L1+L2 缓存，仅 L3 调用，总 token 应显著低于基线或至少第 2/3 轮骤降。

环境：建议单后端（智谱），关闭验证后端，便于对比。
  .env 中注释掉 SAFE_CODEGEN_VALIDATION_BACKEND 等。

用法（项目根目录）：
  python scripts/run_cache_savings_experiment.py --out cache_savings.csv
  python scripts/analyze_experiment.py cache_savings.csv
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROMPT = "生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）"


def _run_baseline() -> tuple[int, int, int]:
    from safe_codegen.llm import get_llm_client
    client = get_llm_client()
    full = f"Task: {PROMPT}\n\nGenerate the complete code. Output only code or code blocks."
    r = client.generate_text(full)
    return (
        getattr(r, "input_tokens", 0) or 0,
        getattr(r, "output_tokens", 0) or 0,
        (getattr(r, "input_tokens", 0) or 0) + (getattr(r, "output_tokens", 0) or 0),
    )


def _run_safe_codegen(clear_data: bool) -> dict:
    from safe_codegen.config import get_settings
    from safe_codegen.graph.builder import InitialStateConfig, build_graph

    settings = get_settings()
    data_dir = Path(settings.data_dir).resolve()
    if clear_data and data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    app = build_graph()
    state = app.invoke(
        InitialStateConfig(user_request=PROMPT, foundation_codebase="").to_state(),
        config={"configurable": {"thread_id": "cache-savings-exp"}},
    )
    return state


def main() -> None:
    ap = argparse.ArgumentParser(description="Cache savings experiment: same prompt 3 rounds.")
    ap.add_argument("--out", default="cache_savings.csv", help="Output CSV")
    args = ap.parse_args()

    rows = []
    task_name = PROMPT[:48] + ".." if len(PROMPT) > 50 else PROMPT

    # 基线：同一 prompt 3 次，每次 1 次 LLM
    for r in range(3):
        in_t, out_t, total = _run_baseline()
        rows.append({
            "任务": task_name,
            "轮次": r + 1,
            "组别": "基线组",
            "输入tokens": in_t,
            "输出tokens": out_t,
            "总tokens": total,
            "安全违规数": "N/A",
            "foundation是否变": "-",
            "备注": "",
        })

    # 实验组：第 1 轮清 data 全流程，第 2/3 轮复用 L1+L2 缓存
    for r in range(3):
        state = _run_safe_codegen(clear_data=(r == 0))
        usage = state.get("token_usage") or {}
        in_t = usage.get("input_tokens", 0)
        out_t = usage.get("output_tokens", 0)
        total = in_t + out_t
        messages = state.get("messages") or []
        foundation_changed = "否" if any("loaded existing immutable foundation" in str(m) for m in messages) else "是"
        status = state.get("status", "")
        rows.append({
            "任务": task_name,
            "轮次": r + 1,
            "组别": "实验组(safe-codegen)",
            "输入tokens": in_t,
            "输出tokens": out_t,
            "总tokens": total,
            "安全违规数": "N/A",
            "foundation是否变": foundation_changed,
            "备注": f"status={status}",
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fn = ["任务", "轮次", "组别", "输入tokens", "输出tokens", "总tokens",
          "安全违规数", "foundation是否变", "备注"]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")
    print("Run: python scripts/analyze_experiment.py", out_path)


if __name__ == "__main__":
    main()
