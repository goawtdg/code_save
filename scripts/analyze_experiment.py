#!/usr/bin/env python3
"""
读取实验 CSV，汇总基线组 vs 实验组的 tokens、安全违规数、foundation 是否变化，
并计算 Token 节省率，用于写报告证明预期效果。

用法（项目根目录）：
  python scripts/analyze_experiment.py experiment_results.csv
  python scripts/analyze_experiment.py experiment_results.csv --rounds 3
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _safe_int(v) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze experiment CSV: token savings, security violations, foundation stability.",
    )
    parser.add_argument(
        "csv_path",
        type=str,
        help="Path to experiment_results.csv",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=None,
        help="If set, only use first N rounds per task per group for averaging.",
    )
    args = parser.parse_args()

    path = Path(args.csv_path)
    if not path.exists():
        print(f"File not found: {path}")
        return

    rows_baseline = []
    rows_experiment = []

    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            group = (row.get("组别") or "").strip()
            if "基线" in group:
                rows_baseline.append(row)
            elif "实验" in group or "safe-codegen" in group.lower():
                rows_experiment.append(row)

    if args.rounds is not None:
        # 按 (任务, 轮次) 保留前 N 轮（这里简化：按行顺序每任务每组取前 rounds 条）
        by_task_b = {}
        by_task_e = {}
        for r in rows_baseline:
            t = r.get("任务", "")
            by_task_b.setdefault(t, []).append(r)
        for r in rows_experiment:
            t = r.get("任务", "")
            by_task_e.setdefault(t, []).append(r)
        rows_baseline = []
        for v in by_task_b.values():
            rows_baseline.extend(v[: args.rounds])
        rows_experiment = []
        for v in by_task_e.values():
            rows_experiment.extend(v[: args.rounds])

    def avg_tokens(rows: list) -> tuple[float, float, float]:
        if not rows:
            return 0.0, 0.0, 0.0
        in_sum = out_sum = total_sum = 0
        n = 0
        for r in rows:
            in_t = _safe_int(r.get("输入tokens", 0))
            out_t = _safe_int(r.get("输出tokens", 0))
            total = r.get("总tokens")
            if total != "" and total != "N/A":
                total_sum += _safe_int(total)
            else:
                total_sum += in_t + out_t
            in_sum += in_t
            out_sum += out_t
            n += 1
        return in_sum / n, out_sum / n, total_sum / n

    def violations_summary(rows: list) -> str:
        nums = []
        for r in rows:
            v = r.get("安全违规数", "N/A")
            if v in ("N/A", "", None):
                continue
            nums.append(_safe_int(v))
        if not nums:
            return "N/A (bandit not run or no numeric values)"
        return f"min={min(nums)}, max={max(nums)}, avg={sum(nums)/len(nums):.1f}"

    def foundation_changed_summary(rows: list) -> str:
        changed = sum(1 for r in rows if (r.get("foundation是否变") or "").strip() == "是")
        total = len(rows)
        return f"{changed}/{total} runs had foundation change"

    in_b, out_b, total_b = avg_tokens(rows_baseline)
    in_e, out_e, total_e = avg_tokens(rows_experiment)

    print("=" * 60)
    print("Experiment summary (baseline vs safe-codegen)")
    print("=" * 60)
    print(f"CSV: {path}")
    print(f"Baseline rows: {len(rows_baseline)}  |  Experiment rows: {len(rows_experiment)}")
    print()
    print("--- Token usage (average) ---")
    print(f"  Baseline:   input={in_b:.0f}, output={out_b:.0f}, total={total_b:.0f}")
    print(f"  Experiment: input={in_e:.0f}, output={out_e:.0f}, total={total_e:.0f}")
    print()
    if total_b > 0:
        saving = (total_b - total_e) / total_b
        print("--- Token saving rate ---")
        print(f"  (baseline_total - experiment_total) / baseline_total = {saving:.1%}")
        if saving > 0:
            print("  -> Experiment uses FEWER tokens (expected in later rounds).")
        else:
            print("  -> Experiment uses more tokens (expected in round 1 due to layers).")
    print()
    print("--- Security violations (Bandit) ---")
    print(f"  Baseline:   {violations_summary(rows_baseline)}")
    print(f"  Experiment: {violations_summary(rows_experiment)}")
    print()
    print("--- Foundation stability (experiment only) ---")
    print(f"  {foundation_changed_summary(rows_experiment)}")
    print("  (Expected: later rounds show 否 = foundation unchanged)")
    print("=" * 60)


if __name__ == "__main__":
    main()
