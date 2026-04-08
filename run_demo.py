"""
run_demo.py — Talent-Audit-Env
CLI demonstration: runs all three tasks with hand-crafted agent actions
and prints a coloured reward summary table.

Usage:
    python run_demo.py
    python run_demo.py --task pii_easy
    python run_demo.py --task pii_medium
    python run_demo.py --task audit_hard
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Tuple

from env import TalentAuditEnv
from models import Action, TechCategory, RiskLevel

# ANSI colours
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

def _c(text: str, color: str) -> str:
    return f"{color}{text}{_RESET}"


# ---------------------------------------------------------------------------
# Pre-scripted "oracle" agents — demonstrate correct behaviour per task
# ---------------------------------------------------------------------------

def run_easy_task(env: TalentAuditEnv) -> float:
    print(_c("\n══════════  TASK: pii_easy (Easy)  ══════════", _BOLD))
    obs = env.reset("pii_easy")
    print(f"  Records   : {[r.record_id for r in obs.records]}")
    print(f"  Step      : {obs.step}")

    # Single Sanitize — remove phone only
    action = Action.sanitize_action("r001", ["phone"])
    obs, reward, done, info = env.step(action)
    _print_step(1, action, reward, info)

    summary = env.state()
    _print_summary(summary)
    return summary["total_reward"]


def run_medium_task(env: TalentAuditEnv) -> float:
    print(_c("\n══════════  TASK: pii_medium (Medium)  ══════════", _BOLD))
    obs = env.reset("pii_medium")
    records = {r.record_id: r for r in obs.records}
    print(f"  Records   : {list(records.keys())}")

    pii_fields = ["name", "email", "phone", "address"]
    # Correct category map (matches ground truth)
    categories = {
        "r001": TechCategory.BACKEND,
        "r002": TechCategory.FRONTEND,
        "r003": TechCategory.DEVOPS,
        "r004": TechCategory.DATA,
        "r005": TechCategory.FULLSTACK,
    }
    step_n = 0
    for rid, cat in categories.items():
        # Categorize first
        step_n += 1
        action = Action.categorize_action(rid, cat)
        obs, reward, done, info = env.step(action)
        _print_step(step_n, action, reward, info)

        # Then sanitize PII
        step_n += 1
        action = Action.sanitize_action(rid, pii_fields)
        obs, reward, done, info = env.step(action)
        _print_step(step_n, action, reward, info)

        if done:
            break

    summary = env.state()
    _print_summary(summary)
    return summary["total_reward"]


def run_hard_task(env: TalentAuditEnv) -> float:
    print(_c("\n══════════  TASK: audit_hard (Hard)  ══════════", _BOLD))
    obs = env.reset("audit_hard")
    print(f"  Records   : {[r.record_id for r in obs.records]}")

    actions: List[Action] = [
        # Correctly flag Frank — employment date vs graduation mismatch
        Action.flag_action(
            "r006", RiskLevel.HIGH,
            reason="Claims 8 years experience but graduated only 4 years ago — impossible timeline."
        ),
        # Correctly flag Grace — overlapping concurrent roles
        Action.flag_action(
            "r007", RiskLevel.HIGH,
            reason="Two simultaneous 4-year roles overlap; total claims 8 years but profile shows 5."
        ),
        # Henry is clean — flag Low (safe)
        Action.flag_action(
            "r008", RiskLevel.LOW,
            reason="Consistent dates, skills, and certifications — no conflicts detected."
        ),
    ]

    for i, action in enumerate(actions, 1):
        obs, reward, done, info = env.step(action)
        _print_step(i, action, reward, info)
        if done:
            break

    summary = env.state()
    _print_summary(summary)
    return summary["total_reward"]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _print_step(
    n: int, action: Action, reward, info: dict
) -> None:
    sign  = "+" if reward.total >= 0 else ""
    color = _GREEN if reward.total > 0 else (_RED if reward.total < 0 else _YELLOW)
    print(
        f"  Step {n:02d}  "
        f"[{_c(action.action_type.value, _CYAN)}] "
        f"reward={_c(f'{sign}{reward.total:.2f}', color)}  "
        f"→ {reward.feedback}"
    )


def _print_summary(summary: dict) -> None:
    r = summary["total_reward"]
    sign  = "+" if r >= 0 else ""
    color = _GREEN if r > 0 else _RED
    print(f"\n  {'─'*50}")
    print(f"  Steps taken  : {summary['step_count']}")
    print(f"  Total reward : {_c(f'{sign}{r:.4f}', color + _BOLD)}")
    print(f"  Categorized  : {summary['categorized']}")
    print(f"  Flagged      : {summary['flagged']}")
    print(f"  Elapsed      : {summary['elapsed_s']}s")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

TASK_RUNNERS = {
    "pii_easy":   run_easy_task,
    "pii_medium": run_medium_task,
    "audit_hard": run_hard_task,
}

def main() -> None:
    parser = argparse.ArgumentParser(description="Talent-Audit-Env demo runner.")
    parser.add_argument(
        "--task",
        choices=list(TASK_RUNNERS.keys()) + ["all"],
        default="all",
        help="Which task to run (default: all).",
    )
    args = parser.parse_args()

    env = TalentAuditEnv()
    totals = {}

    tasks_to_run = list(TASK_RUNNERS.keys()) if args.task == "all" else [args.task]
    for task_id in tasks_to_run:
        totals[task_id] = TASK_RUNNERS[task_id](env)

    print(_c("\n══════════  FINAL SCORE SUMMARY  ══════════", _BOLD))
    for task_id, score in totals.items():
        sign  = "+" if score >= 0 else ""
        color = _GREEN if score > 0 else _RED
        print(f"  {task_id:<15}  {_c(f'{sign}{score:.4f}', color)}")

    overall = sum(totals.values())
    print(f"  {'─'*32}")
    print(f"  {'OVERALL':<15}  {_c(f'{overall:+.4f}', _BOLD)}")


if __name__ == "__main__":
    main()
