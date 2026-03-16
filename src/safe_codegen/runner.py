from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

# 确保 .env 中的 OPENAI_API_KEY 等被注入环境变量，供后续 Settings/LLM 使用
load_dotenv()

from .config import get_settings
from .graph.builder import InitialStateConfig, build_graph


def run_once(prompt: str, foundation_path: str | None = None) -> Dict[str, Any]:
    """Run the three-layer workflow once and return the final state."""

    foundation_code = ""
    if foundation_path:
        path = Path(foundation_path)
        if path.exists():
            foundation_code = path.read_text(encoding="utf-8")

    initial = InitialStateConfig(
        user_request=prompt,
        foundation_codebase=foundation_code,
    ).to_state()

    app = build_graph()
    # A fixed thread id is sufficient for CLI demo runs.
    final_state = app.invoke(
        initial,
        config={"configurable": {"thread_id": "cli-run"}},
    )
    return final_state


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the safe-codegen three-layer LangGraph workflow once.",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        required=True,
        help="User request / task description for the code generation pipeline.",
    )
    parser.add_argument(
        "--foundation-path",
        type=str,
        default=None,
        help="Optional path to an initial foundation codebase file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write the final state as JSON.",
    )

    args = parser.parse_args(argv)

    state = run_once(prompt=args.prompt, foundation_path=args.foundation_path)

    status = state.get("status", "pending")
    scores = state.get("scores", {})
    token_usage = state.get("token_usage") or {}

    print("=== safe-codegen run complete ===")
    print(f"Status: {status}")
    print("Scores:", json.dumps(scores, ensure_ascii=False))
    if token_usage:
        in_t = token_usage.get("input_tokens", 0)
        out_t = token_usage.get("output_tokens", 0)
        print(f"Token usage: input={in_t}, output={out_t}, total={in_t + out_t}")

    final_report = state.get("final_report") or ""
    if final_report:
        print("\n=== Final report ===")
        print(final_report)

    messages = state.get("messages") or []
    if messages:
        print("\n=== Trace messages (last 10) ===")
        for line in messages[-10:]:
            print("-", line)

    # 生成的模块代码：优先从 state 取，否则从缓存文件取最新一条
    proposal = state.get("latest_module_proposal") or {}
    generated_code = proposal.get("content", "").strip()
    data_dir = Path(get_settings().data_dir)
    modules_file = data_dir / "modules" / "core_module.json"
    if not generated_code and modules_file.exists():
        try:
            mod_data = json.loads(modules_file.read_text(encoding="utf-8"))
            if isinstance(mod_data, list) and mod_data:
                for entry in reversed(mod_data):
                    c = (entry.get("content") or "").strip()
                    if c:
                        generated_code = c
                        break
        except Exception:
            pass
    if generated_code:
        print("\n=== Generated module code ===")
        print(generated_code)
    print(f"\n(Module code is saved under: {modules_file})")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nFinal state written to: {out_path}")


if __name__ == "__main__":
    main()

