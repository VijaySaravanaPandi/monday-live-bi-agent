"""
Orchestrator
-------------
The single wiring layer for the BI agent. Receives a founder's
natural-language question + conversation history and returns a
fully-formed answer (or a clarification request).

Flow:
  1. QueryPlanner (Groq LLM call #1) → structured JSON query plan
  2. If needs_clarification → return clarification question immediately
  3. MondayClient → fetch live data for required board(s)
  4. Normalizer → clean data + DataQualityReports
  5. BIEngine → deterministic metric computation
  6. Groq (LLM call #2) → narrative synthesis from verified numbers

Design rules:
- LLM #1 ONLY plans (structured JSON, no arithmetic).
- LLM #2 ONLY narrates pre-computed numbers (no arithmetic).
- If one board fails, the orchestrator continues with the other
  and surfaces a clear caveat — it never crashes silently.
- Data quality caveats are injected into the synthesis prompt so
  the founder sees them inline, not buried in logs.
"""

import json
import logging
from typing import Optional, List, Dict, Any

from groq import Groq

from src.config import config
from src.query_planner import QueryPlanner, QueryPlanningError
from src.monday_client import MondayClient, MondayAPIError
from src.normalizer import normalize_deals_board, normalize_work_orders_board
import src.bi_engine as bi

logger = logging.getLogger("orchestrator")


# ---------------------------------------------------------------------------
# Synthesis prompt template
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """You are a sharp, concise business intelligence analyst for Skylark Drones.

Your job is to synthesise pre-computed metrics into a clear, founder-level answer.

Rules:
1. You NEVER perform arithmetic. Every number in your answer must come directly from the metrics JSON provided.
2. Write 2-5 short paragraphs or bullet points. Be crisp — founders read fast.
3. If data quality caveats are provided, weave them in naturally (e.g. "Note: 3 deals had no value recorded.")
4. If the question asks for a 'leadership update' or 'board summary', structure the answer as labelled bullet sections: Sales Pipeline, Operations, Revenue.
5. End with ONE actionable insight or suggested next question if it naturally follows from the data.
6. Do NOT reveal that you are an AI or reference the metrics JSON directly.
"""


class OrchestratorError(Exception):
    """Raised when the orchestrator hits an unrecoverable error."""
    pass


class OrchestratorResult:
    """Structured result returned by the orchestrator."""

    def __init__(
        self,
        answer: str,
        clarification_needed: bool = False,
        clarification_question: Optional[str] = None,
        query_plan: Optional[Dict[str, Any]] = None,
        data_quality_notes: Optional[List[str]] = None,
        partial_failure: bool = False,
        partial_failure_reason: Optional[str] = None,
    ):
        self.answer = answer
        self.clarification_needed = clarification_needed
        self.clarification_question = clarification_question
        self.query_plan = query_plan or {}
        self.data_quality_notes = data_quality_notes or []
        self.partial_failure = partial_failure
        self.partial_failure_reason = partial_failure_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "query_plan": self.query_plan,
            "data_quality_notes": self.data_quality_notes,
            "partial_failure": self.partial_failure,
            "partial_failure_reason": self.partial_failure_reason,
        }


class Orchestrator:
    def __init__(self, groq_api_key: Optional[str] = None, model: Optional[str] = None):
        self.groq_client = Groq(api_key=groq_api_key or config.GROQ_API_KEY)
        self.planner = QueryPlanner(api_key=groq_api_key or config.GROQ_API_KEY, model=model or config.GROQ_MODEL)
        self.monday = MondayClient()
        self.synthesis_model = model or config.GROQ_MODEL

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def answer(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> OrchestratorResult:
        """
        Main entry point. Returns an OrchestratorResult for any question.
        Never raises — all errors are surfaced as human-readable answers.
        """
        history = history or []

        # ── Step 1: Query Planning ──────────────────────────────────────
        try:
            plan = self.planner.plan(question)
        except QueryPlanningError as e:
            logger.error("Query planning failed: %s", e)
            return OrchestratorResult(
                answer=f"I had trouble understanding that question. Could you rephrase it? (Detail: {e})",
                clarification_needed=True,
                clarification_question="Could you rephrase your question?",
            )

        # ── Step 2: Clarification loop ──────────────────────────────────
        if plan.get("needs_clarification"):
            return OrchestratorResult(
                answer=plan["clarification_question"],
                clarification_needed=True,
                clarification_question=plan["clarification_question"],
                query_plan=plan,
            )

        intent = plan["intent"]
        filters = plan.get("filters") or {}

        # ── Step 3: Fetch data (with per-board partial-failure handling) ─
        deals, deal_report = [], None
        work_orders, wo_report = [], None
        partial_failure = False
        partial_failure_reasons = []

        needs_deals = intent in {
            "total_pipeline_value",
            "deal_count_by_stage",
            "win_rate",
            "sector_performance",
            "cross_board_sector_view",
            "leadership_update",
        }
        needs_work_orders = intent in {
            "operational_status_summary",
            "revenue_summary",
            "sector_operational_performance",
            "cross_board_sector_view",
            "leadership_update",
        }

        if needs_deals:
            try:
                raw_deals = self.monday.get_deals()
                deals, deal_report = normalize_deals_board(raw_deals)
            except MondayAPIError as e:
                logger.warning("Deals board fetch failed: %s", e)
                partial_failure = True
                partial_failure_reasons.append(f"Deals board unavailable: {e}")

        if needs_work_orders:
            try:
                raw_wo = self.monday.get_work_orders()
                work_orders, wo_report = normalize_work_orders_board(raw_wo)
            except MondayAPIError as e:
                logger.warning("Work Orders board fetch failed: %s", e)
                partial_failure = True
                partial_failure_reasons.append(f"Work Orders board unavailable: {e}")

        # If we need data but got nothing at all, bail gracefully
        if needs_deals and not deals and needs_work_orders and not work_orders:
            return OrchestratorResult(
                answer="I couldn't reach either Monday.com board right now. Please try again in a moment.",
                partial_failure=True,
                partial_failure_reason="; ".join(partial_failure_reasons),
                query_plan=plan,
            )

        # ── Step 4: Compute metrics (deterministic) ─────────────────────
        try:
            metrics = self._compute_metrics(intent, filters, deals, work_orders)
        except Exception as e:
            logger.error("Metric computation failed: %s", e)
            return OrchestratorResult(
                answer="I computed the query plan but ran into an issue calculating the metrics. Please try again.",
                query_plan=plan,
            )

        # ── Step 5: Collect data quality caveats ───────────────────────
        quality_notes = []
        if deal_report and deal_report.has_issues():
            quality_notes.append(deal_report.summary_text())
        if wo_report and wo_report.has_issues():
            quality_notes.append(wo_report.summary_text())
        if partial_failure_reasons:
            quality_notes.extend(partial_failure_reasons)

        # ── Step 6: LLM Narrative Synthesis ────────────────────────────
        answer_text = self._synthesise(
            question=question,
            intent=intent,
            metrics=metrics,
            quality_notes=quality_notes,
            history=history,
        )

        return OrchestratorResult(
            answer=answer_text,
            query_plan=plan,
            data_quality_notes=quality_notes,
            partial_failure=partial_failure,
            partial_failure_reason="; ".join(partial_failure_reasons) if partial_failure_reasons else None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        intent: str,
        filters: Dict[str, Any],
        deals: list,
        work_orders: list,
    ) -> Dict[str, Any]:
        """Dispatches to the correct BIEngine function based on intent."""
        sector = filters.get("sector")

        dispatch = {
            "total_pipeline_value": lambda: bi.total_pipeline_value(deals, filters),
            "deal_count_by_stage": lambda: bi.deal_count_by_stage(deals, filters),
            "win_rate": lambda: bi.win_rate(deals, filters=filters),
            "sector_performance": lambda: bi.sector_performance(deals, filters),
            "operational_status_summary": lambda: bi.operational_status_summary(work_orders, filters),
            "revenue_summary": lambda: bi.revenue_summary(work_orders, filters),
            "sector_operational_performance": lambda: bi.sector_operational_performance(work_orders, filters),
            "cross_board_sector_view": lambda: bi.cross_board_sector_view(deals, work_orders, sector),
            "leadership_update": lambda: bi.leadership_update(deals, work_orders),
        }

        fn = dispatch.get(intent)
        if fn is None:
            raise OrchestratorError(f"Unknown intent: {intent}")
        return fn()

    def _synthesise(
        self,
        question: str,
        intent: str,
        metrics: Dict[str, Any],
        quality_notes: List[str],
        history: List[Dict[str, str]],
    ) -> str:
        """Second LLM call: turns verified numbers into a founder-level narrative."""

        caveats_block = ""
        if quality_notes:
            caveats_block = "\n\nData quality caveats (mention these naturally in your answer):\n" + "\n".join(
                f"- {n}" for n in quality_notes
            )

        user_message = (
            f"The founder asked: {question}\n\n"
            f"Intent resolved: {intent}\n\n"
            f"Pre-computed metrics (all arithmetic is already done — do NOT recalculate):\n"
            f"{json.dumps(metrics, indent=2)}"
            f"{caveats_block}"
        )

        # Build message list: system + optional history (last 6 turns) + current
        messages = [{"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT}]
        for turn in history[-6:]:  # bounded context window
            messages.append(turn)
        messages.append({"role": "user", "content": user_message})

        response = self.groq_client.chat.completions.create(
            model=self.synthesis_model,
            max_tokens=600,
            temperature=0.3,  # slight creativity for narrative, but grounded
            messages=messages,
        )
        return response.choices[0].message.content.strip()
