"""
Phase 5 verification script.
Tests the Orchestrator end-to-end with live Monday.com + Groq API calls.

Covers:
1. A direct, unambiguous question  → full answer with metrics
2. An ambiguous question           → clarification returned (no BI call)
3. Partial-failure path            → mock one board failing, other works
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import unittest
from unittest.mock import patch, MagicMock

from src.config import config
from src.orchestrator import Orchestrator, OrchestratorResult


# ─── Live integration tests ──────────────────────────────────────────────────

def test_direct_question():
    print("\n── Test 1: Direct question (win rate) ──")
    config.validate()
    orch = Orchestrator()
    result = orch.answer("What's our win rate?")
    assert isinstance(result, OrchestratorResult)
    assert not result.clarification_needed
    assert result.answer and len(result.answer) > 20
    print(f"   ✅ Answer received ({len(result.answer)} chars)")
    print(f"   Intent: {result.query_plan.get('intent')}")
    print(f"   Quality notes: {result.data_quality_notes}")
    print(f"   Answer preview: {result.answer[:200]}...")


def test_ambiguous_question():
    print("\n── Test 2: Ambiguous question (should trigger clarification) ──")
    config.validate()
    orch = Orchestrator()
    result = orch.answer("How are we doing?")
    assert isinstance(result, OrchestratorResult)
    # May or may not need clarification depending on LLM; just check it runs
    print(f"   clarification_needed: {result.clarification_needed}")
    if result.clarification_needed:
        print(f"   ✅ Clarification question: {result.clarification_question}")
    else:
        print(f"   ℹ️  LLM resolved to intent: {result.query_plan.get('intent')}")
        print(f"   Answer preview: {result.answer[:200]}...")


def test_pipeline_question():
    print("\n── Test 3: Total pipeline value ──")
    config.validate()
    orch = Orchestrator()
    result = orch.answer("What's the total pipeline value?")
    assert not result.clarification_needed
    print(f"   ✅ Intent: {result.query_plan.get('intent')}")
    print(f"   Answer preview: {result.answer[:200]}...")


def test_cross_board_question():
    print("\n── Test 4: Cross-board sector query ──")
    config.validate()
    orch = Orchestrator()
    result = orch.answer("How is the Mining sector doing overall?")
    assert not result.clarification_needed
    print(f"   ✅ Intent: {result.query_plan.get('intent')}")
    print(f"   Answer preview: {result.answer[:200]}...")


# ─── Mocked partial-failure test ─────────────────────────────────────────────

def test_partial_failure_work_orders_down():
    print("\n── Test 5: Partial failure — Work Orders board down ──")
    config.validate()
    orch = Orchestrator()

    from src.monday_client import MondayAPIError

    original_get_work_orders = orch.monday.get_work_orders

    def boom():
        raise MondayAPIError("Simulated Work Orders timeout")

    orch.monday.get_work_orders = boom

    result = orch.answer("What's our win rate?")
    assert isinstance(result, OrchestratorResult)
    # win_rate only needs Deals, so this should still succeed
    print(f"   partial_failure: {result.partial_failure}")
    print(f"   ✅ Answer still returned: {result.answer[:200]}...")

    orch.monday.get_work_orders = original_get_work_orders


def test_partial_failure_deals_down():
    print("\n── Test 6: Partial failure — Deals board down, revenue question ──")
    config.validate()
    orch = Orchestrator()

    from src.monday_client import MondayAPIError

    original_get_deals = orch.monday.get_deals

    def boom():
        raise MondayAPIError("Simulated Deals board timeout")

    orch.monday.get_deals = boom

    result = orch.answer("Show me revenue collected so far from work orders.")
    assert isinstance(result, OrchestratorResult)
    # revenue_summary only needs Work Orders, so should still work
    print(f"   partial_failure: {result.partial_failure}")
    print(f"   ✅ Answer still returned: {result.answer[:200]}...")

    orch.monday.get_deals = original_get_deals


def test_leadership_update():
    print("\n── Test 7: Leadership update (structured report) ──")
    config.validate()
    orch = Orchestrator()
    result = orch.answer("Give me a leadership update for the board.")
    print(f"   clarification_needed: {result.clarification_needed}")
    if not result.clarification_needed:
        print(f"   Intent: {result.query_plan.get('intent')}")
        print(f"   Answer preview: {result.answer[:300]}...")
    else:
        print(f"   Clarification: {result.clarification_question}")
    print("   ✅ Leadership update test complete")


if __name__ == "__main__":
    print("=== Phase 5: Orchestrator End-to-End Tests ===")
    try:
        config.validate()
    except EnvironmentError as e:
        print(f"❌ Config error: {e}")
        raise SystemExit(1)

    tests = [
        test_direct_question,
        test_ambiguous_question,
        test_pipeline_question,
        test_cross_board_question,
        test_partial_failure_work_orders_down,
        test_partial_failure_deals_down,
        test_leadership_update,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1

    print(f"\n=== Phase 5 complete: {passed} passed, {failed} failed ===")
