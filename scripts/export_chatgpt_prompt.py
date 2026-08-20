#!/usr/bin/env python3
"""
ChatGPT Desktop Context & Prompt Packager
Generates structured context packages for pasting into ChatGPT Desktop.
"""
import argparse
import sys
from pathlib import Path

def generate_context_prompt(task_type: str, symbol: str = "NVDA", output_file: str = "chatgpt_outbox.md"):
    header = f"""# Prompt for ChatGPT Desktop
You are assisting an institutional quantitative hedge fund development team.

## Platform Context
- Architecture: 7-Layer Institutional Quantitative Hedge Fund
- Core Subpackages: `core/`, `data/`, `quant/`, `intelligence/`, `runtime/`, `execution/`, `api/`
- Target Asset: {symbol}
- Safety: Long-only paper trading, Hard 8% position limits, 2% daily loss kill-switch, 1-Day 95% Parametric VaR.

## Your Task
Task Type: {task_type}
Please provide clean, production-grade Python/TypeScript code or mathematical alpha formulations conforming to these architectural constraints.
"""
    out_path = Path(output_file)
    out_path.write_text(header, encoding="utf-8")
    print(f"ChatGPT prompt packaged and saved to {output_file}!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Package context for ChatGPT Desktop")
    parser.add_argument("--task", default="alpha_research", help="Task type")
    parser.add_argument("--symbol", default="NVDA", help="Target symbol")
    parser.add_argument("--out", default="chatgpt_outbox.md", help="Output file")
    args = parser.parse_args()
    generate_context_prompt(args.task, args.symbol, args.out)
