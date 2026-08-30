"""
Query Planner
--------------
Takes a founder's natural-language question and turns it into a
structured Query Plan: which BI function to call, on which data
source(s), with which filters. The LLM's ONLY job here is planning —
it never sees raw deal/work-order records and never does arithmetic.

If the question is ambiguous (e.g. "how's the pipeline?" with no
sector/timeframe), the plan comes back with needs_clarification=True
and a specific clarifying question to ask the user, rather than
guessing at intent.

Output contract (the plan) is intentionally rigid JSON so it can be
mechanically dispatched to bi_engine.py functions in Phase 5.

LLM backend: Groq (llama-3.3-70b-versatile) — fast, free-tier friendly.
"""

import json
import re
import os
from typing import Optional, Dict, Any
from groq import Groq

from src.config import config


# The fixed set of metrics the BI engine actually supports (Phase 3).
# The planner MUST choose from this list — it cannot invent new metrics.
AVAILABLE_INTENTS = {
    "total_pipeline_value": "Total value of deals in the pipeline (optionally filtered by sector/stage/status).",
    "deal_count_by_stage": "Count of deals grouped by sales stage.",
    "win_rate": "Percentage of resolved deals that were won.",
    "sector_performance": "Deal count and pipeline value grouped by sector (Deals board).",
    "operational_status_summary": "Count of work orders grouped by execution status.",
    "revenue_summary": "Billed, collected, and receivable amounts across work orders.",
    "sector_operational_performance": "Work order count and revenue grouped by sector (Work Orders board).",
    "cross_board_sector_view": "Combined sales pipeline + operations + revenue view for one sector — use this for questions that span both boards, e.g. 'how is X sector doing overall'.",
    "leadership_update": "Comprehensive executive summary covering overall sales pipeline, win rate, operations status, and billing/revenue across all sectors.",
}

SYSTEM_PROMPT = f"""You are a query planning component inside a business intelligence agent for Skylark Drones.

Your ONLY job is to read a founder's question and output a structured JSON query plan. You do NOT answer the question, you do NOT calculate any numbers, and you NEVER invent data. A separate deterministic engine will execute your plan against live data.

Available intents (you must pick exactly one, or ask for clarification):
{json.dumps(AVAILABLE_INTENTS, indent=2)}

Rules:
1. If the question clearly maps to one intent, output a plan with needs_clarification=false.
2. If the question is ambiguous, vague, or could map to multiple intents (e.g. missing sector, missing timeframe, missing which board), output needs_clarification=true with a specific, short clarifying question. Do NOT guess.
3. Filters may include: sector (string), status (string), deal_stage (string). Only include filters actually implied by the question. Omit filters not mentioned.
4. If the question spans both sales and operations for a sector (e.g. "how's Energy doing overall"), use cross_board_sector_view.
5. Output ONLY valid JSON matching this exact schema, nothing else — no prose, no markdown fences:

{{
  "needs_clarification": boolean,
  "clarification_question": string or null,
  "intent": string or null,
  "filters": {{}},
  "reasoning": string
}}
"""


class QueryPlanningError(Exception):
    """Raised when the LLM fails to produce a valid, parseable query plan."""
    pass


class QueryPlanner:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.client = Groq(api_key=api_key or config.GROQ_API_KEY)
        self.model = model or config.GROQ_MODEL

    def plan(self, user_question: str) -> Dict[str, Any]:
        """
        Sends the user's question to the LLM and returns a parsed,
        validated query plan dict.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=500,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_question},
            ],
        )

        raw_text = response.choices[0].message.content.strip()

        plan = self._parse_json(raw_text)
        self._validate_plan(plan)
        return plan

    def _parse_json(self, raw_text: str) -> Dict[str, Any]:
        """Strips markdown fences if present and parses JSON, with a clear error on failure."""
        cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise QueryPlanningError(
                f"Query planner returned non-JSON output: {raw_text[:200]}... ({e})"
            )

    def _validate_plan(self, plan: Dict[str, Any]):
        """Ensures the plan matches the expected contract before it's dispatched."""
        required_keys = {"needs_clarification", "clarification_question", "intent", "filters", "reasoning"}
        missing = required_keys - plan.keys()
        if missing:
            raise QueryPlanningError(f"Query plan missing required keys: {missing}")

        if not plan["needs_clarification"]:
            if plan["intent"] not in AVAILABLE_INTENTS:
                raise QueryPlanningError(
                    f"Query plan selected unknown intent '{plan['intent']}'. "
                    f"Must be one of: {list(AVAILABLE_INTENTS.keys())}"
                )