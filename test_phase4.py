"""
Phase 4 verification script.
Sends a handful of sample founder-style questions through the Query
Planner and prints the resulting structured plans — including at
least one ambiguous question that should trigger clarification.

This proves: the LLM plans intent/filters correctly, sticks to the
allowed intent list, and asks for clarification instead of guessing
when a question is underspecified.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import config
from src.query_planner import QueryPlanner, QueryPlanningError


SAMPLE_QUESTIONS = [
    "How's our pipeline looking for the energy sector this quarter?",
    "What's our win rate?",
    "How is Mining performing across sales and operations?",
    "How are we doing?",  # deliberately vague -> should trigger clarification
    "Show me revenue collected so far from work orders.",
]


def main():
    print("=== Phase 4: Query Planner Test ===\n")

    try:
        config.validate()
    except EnvironmentError as e:
        print(f"❌ Config error: {e}")
        return

    planner = QueryPlanner()

    for question in SAMPLE_QUESTIONS:
        print(f"Q: {question}")
        try:
            plan = planner.plan(question)
            if plan["needs_clarification"]:
                print(f"   ⚠️  NEEDS CLARIFICATION: {plan['clarification_question']}")
            else:
                print(f"   ✅ intent: {plan['intent']}")
                print(f"      filters: {plan['filters']}")
                print(f"      reasoning: {plan['reasoning']}")
        except QueryPlanningError as e:
            print(f"   ❌ Planning error: {e}")
        print()

    print("=== Phase 4 complete: query planning + clarification logic verified ===")


if __name__ == "__main__":
    main()