# Decision Log — Skylark Drones Monday.com Live BI Agent

## 1. Key Assumptions Made

- **Read-Only Monday.com Data Source**: The agent interacts strictly via read operations over the Monday.com GraphQL API (`boards`, `items_page`, `next_items_page`). No write mutations or schema alterations are executed.
- **Dynamic Live Reads over Persistence**: In accordance with the prompt's hard constraint ("do not hardcode CSV data"), zero deals or work orders are stored in a database or local cache. All normalization and BI metric aggregations are executed dynamically in-memory per request.
- **Strict Separation of Math and Language**: LLMs cannot be trusted with multi-row arithmetic or financial aggregations. Therefore, the LLM is strictly restricted to (1) extracting structured query plans and (2) synthesizing executive narratives from verified numbers calculated by deterministic Python functions.
- **Messy Data as the Norm**: Business data in production contains missing deal values, non-standardized sector labels (e.g. `"powerline"`, `"power line"`, `"oil and gas"`), and varied date/currency formats. Rather than discarding records with defects, the agent standardizes what it can, computes metrics over available fields, and logs explicit caveats.

---

## 2. Trade-Offs Chosen and Why

| Trade-Off | Alternative Considered | Why Chosen |
| :--- | :--- | :--- |
| **Deterministic Python BI Engine + 2-Stage LLM** | Single-prompt end-to-end LLM arithmetic | **Zero hallucination guarantee.** Isolating calculations to pure Python functions in `bi_engine.py` ensures 100% mathematical precision for executive reporting. |
| **Direct Dynamic GraphQL Queries** | Periodic database syncing (e.g. Postgres / SQLite) | **Live freshness & zero stale data.** Complies strictly with the assignment constraint against static CSV / hardcoded storage while keeping latency sub-second. |
| **Linear Pipeline Orchestrator** | Multi-agent frameworks (CrewAI, AutoGen) | **Predictable latency & reliability.** A deterministic orchestrator pipeline eliminates agent loops, reduces token overhead, and simplifies debugging. |
| **Groq API Inference Backend** | Local models or slower cloud endpoints | **Sub-500ms TTFT.** Groq's high-speed inference delivers an interactive, conversational user experience without long delays. |
| **FastAPI with Static UI Mount** | Heavy React/Next.js single-page application | **Zero-build cloud deployment.** Allows instant deployment on Render/Railway as a single Python service without npm build steps or dual-host complexity. |

---

## 3. How We Interpreted "Leadership Updates"

The prompt states: *"The agent should help prepare data for leadership updates. How you interpret and implement this is up to you."*

**Our Interpretation & Implementation**:
1. **First-Class Cross-Board Intent**: We designed a dedicated `leadership_update` intent in `query_planner.py` and `bi_engine.py` that automatically pulls and combines data from **both Deals and Work Orders** boards.
2. **Three-Pillar Executive Structure**:
   - **Sales Pipeline & Win Rate**: Total pipeline value, active deal count, stage distribution, and closed-won win rate.
   - **Operational Execution**: Total active work orders grouped by operational status across all sectors.
   - **Financial Health**: Total contracted revenue (excl. GST), billed revenue, collected revenue (incl. GST), and outstanding receivables.
3. **Data Quality & Caveat Transparency**: Leadership summaries automatically disclose missing deal values or uncollected invoice gaps so founders know the exact reliability of their metrics.

---

## 4. What We'd Do Differently With More Time

1. **Short-Lived Ephemeral In-Memory Caching (TTL 30-60s)**: While adhering to dynamic queries, adding a 30-second TTL cache for board schemas and active items would dramatically reduce API round-trips for rapid back-to-back questions.
2. **Token Streaming (Server-Sent Events / WebSockets)**: Implement streaming responses from Groq directly into the frontend chat bubble for instantaneous character-by-character rendering.
3. **Interactive Charting & Visualizations**: Embed dynamic interactive charts (Chart.js / Plotly) directly inside chat bubbles for stage breakdowns and revenue trends.
4. **Role-Based Access Control (RBAC)**: Support founder vs. manager view permissions to mask sensitive client codes and deal values based on user authentication.
