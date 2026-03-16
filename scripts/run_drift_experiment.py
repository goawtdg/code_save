#!/usr/bin/env python3
"""
多轮漂移实验：同一个 FastAPI TODO 项目上连续加功能，
比较基线组（每轮重写全项目） vs safe-codegen（复用 foundation）。

轮次与 prompt：
  1. 生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）
  2. 在现有 TODO 项目基础上添加 JWT 认证中间件（不硬编码密钥）
  3. 在现有 TODO 项目基础上添加安全的文件上传接口（防路径穿越 + 大小限制）
  4. 在现有 TODO 项目基础上添加导出 Excel 功能
  5. 在现有 TODO 项目基础上添加 Webhook 回调（包含签名校验）
  6. 在现有 TODO 项目基础上添加审计日志记录（记录关键操作）

用法（项目根目录）：
  python scripts/run_drift_experiment.py --out drift_results.csv
  python scripts/analyze_experiment.py drift_results.csv
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

# 确保可导入 safe_codegen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DRIFT_PROMPTS = [
    "生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）",
    "在现有 TODO 项目基础上添加 JWT 认证中间件（不硬编码密钥）",
    "在现有 TODO 项目基础上添加安全的文件上传接口（防路径穿越 + 大小限制）",
    "在现有 TODO 项目基础上添加导出 Excel 功能",
    "在现有 TODO 项目基础上添加 Webhook 回调（包含签名校验）",
    "在现有 TODO 项目基础上添加审计日志记录（记录关键操作）",
]


def _run_baseline(prompt: str, previous_code: str | None) -> tuple[int, int, int, str]:
    """基线：先生成基座，后续每轮在已有代码基础上做增量更新。

    previous_code 为 None 时表示首轮：生成完整项目作为基座。
    之后每轮会把上一轮完整代码连同本轮需求一起喂给模型，让其更新代码。
    """
    from safe_codegen.llm import get_llm_client

    client = get_llm_client()
    if previous_code is None:
        full = (
            f"Task: {prompt}\n\n"
            "Generate the complete FastAPI TODO project code (CRUD + SQLite). "
            "Output only code or code blocks."
        )
    else:
        full = (
            "You are updating an existing FastAPI TODO project in an incremental way.\n\n"
            "Here is the current full project code (do not discard existing behavior):\n"
            f"{previous_code}\n\n"
            f"New task (apply on top of the existing project, without breaking previous features):\n{prompt}\n\n"
            "Update the project to implement ONLY this new task while preserving all previous behavior. "
            "Output the full updated code."
        )
    resp = client.generate_text(full)
    in_t = getattr(resp, "input_tokens", 0) or 0
    out_t = getattr(resp, "output_tokens", 0) or 0
    return in_t, out_t, in_t + out_t, resp.content


def _run_safe_codegen(
    prompt: str,
    clear_data: bool,
    mode: str,
) -> tuple[int, int, int, str, str]:
    """safe-codegen：第一轮清 data，后续复用 foundation。

    mode:
      - \"full\": 跑三层（L1/L2/L3），用于首轮和最后一轮的全面校验与验收；
      - \"light\": 只跑 L1/L2，通过后直接结束，用于中间迭代轮的轻量模式。
    """
    from safe_codegen.config import get_settings
    from safe_codegen.graph.builder import InitialStateConfig, build_graph

    settings = get_settings()
    data_dir = Path(settings.data_dir).resolve()
    if clear_data and data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    initial = InitialStateConfig(user_request=prompt, foundation_codebase="").to_state()
    app = build_graph(mode=mode)
    state = app.invoke(
        initial,
        config={"configurable": {"thread_id": f"drift-{hash(prompt) & 0x7FFFFFFF}"}},
    )
    usage = state.get("token_usage") or {}
    in_t = int(usage.get("input_tokens", 0))
    out_t = int(usage.get("output_tokens", 0))
    status = state.get("status", "")
    messages = state.get("messages") or []
    if any("loaded existing immutable foundation from cache" in str(m) for m in messages):
        foundation_changed = "否"
    else:
        foundation_changed = "是" if (data_dir / "foundation.json").exists() else "否"
    return in_t, out_t, in_t + out_t, status, foundation_changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-round drift experiment.")
    parser.add_argument("--out", type=str, default="drift_results.csv")
    args = parser.parse_args()

    rows: list[dict] = []
    baseline_code: str | None = None
    total_rounds = len(DRIFT_PROMPTS)
    for i, prompt in enumerate(DRIFT_PROMPTS):
        round_idx = i + 1
        # 基线：首轮生成基座，后续在已有代码基础上做增量更新。
        in_b, out_b, tot_b, baseline_code = _run_baseline(prompt, baseline_code)
        rows.append({
            "任务": "TODO漂移",
            "轮次": round_idx,
            "组别": "基线组",
            "输入tokens": in_b,
            "输出tokens": out_b,
            "总tokens": tot_b,
            "安全违规数": "N/A",
            "foundation是否变": "-",
            "备注": "",
        })
        # 实验组：首轮和最后一轮使用 full 模式，中间轮使用 light 模式。
        if i == 0:
            mode = "full"
            clear_data = True
        elif i == total_rounds - 1:
            mode = "full"
            clear_data = False
        else:
            mode = "light"
            clear_data = False
        in_e, out_e, tot_e, status, f_changed = _run_safe_codegen(
            prompt,
            clear_data=clear_data,
            mode=mode,
        )
        rows.append({
            "任务": "TODO漂移",
            "轮次": round_idx,
            "组别": "实验组(safe-codegen)",
            "输入tokens": in_e,
            "输出tokens": out_e,
            "总tokens": tot_e,
            "安全违规数": "N/A",
            "foundation是否变": f_changed,
            "备注": f"status={status}",
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["任务", "轮次", "组别", "输入tokens", "输出tokens", "总tokens",
                  "安全违规数", "foundation是否变", "备注"]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=fieldnames).writeheader()
        csv.DictWriter(f, fieldnames=fieldnames).writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
