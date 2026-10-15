# Assignment delivery checklist

This maps the supplied FreightTiger case-study brief to executable code and evidence.

| Requirement | Implementation / evidence |
|---|---|
| Group directional routes and supplied route_type | `freightwatch/engine.py`; no inferred distance buckets |
| Monday–Sunday weeks, Monday week_of | `engine.py`, unit tests |
| Weekly total freight / sum(quantity × distance) | `engine.py`; independent Decimal reference for all 728 rows |
| Trailing eight-week history excluding current week | `engine.py`; available weeks only, no padding; counts in audit |
| Same-week same-type peers excluding self | `engine.py`; independent reference and unit tests |
| Flag rising, unusual costs | Explicit configurable thresholds in README and audit policy |
| Notes retrieval and grounded explanations (bonus) | `evidence.py`: TF-IDF vectors plus route/time/effect/magnitude checks |
| Exact note ID and applicable note for justified rows | `matched_note_id`, source text, eligibility checks in `results/audit.json` |
| No applicable evidence means unexplained | Tests for wrong route, expired/future dates, negation and abstention |
| Evaluation | `results/test_results.txt` (44 tests), `evaluation.json` (728 reference rows and 9 regression cases) |
| Three untouched runs | `results/reproducibility.json`: three fresh-process runs with identical hashes |
| Token/call/cost accounting | `results/cost_log.json`: 0 calls, 0 tokens, $0 provider spend; no model rate applies |
| Working code | `freightwatch/`, `scripts/`, `tests/`, `data/`, Python 3.10+ |
| Exact sample CSV schema | `results/output.csv`; original sample preserved in `data/` |
| README and design explanation | Root README, `docs/METHODOLOGY.md`, `docs/DESIGN.md` |
| Ten-minute walkthrough | `docs/WALKTHROUGH.md`; must be rehearsed and delivered by the candidate |
| Natural-language questions (stretch) | `python -m freightwatch ask ...`; hosted `results/dashboard.html#assistant` |

## Reproduce

From the repository root:

```bash
python -m freightwatch run
python scripts/verify.py
python scripts/prepare_submission.py
python -m freightwatch ask "Why did Chennai-Bangalore get pricier in March 2025?"
python -m http.server 8000
```

Open http://localhost:8000 for the 3D dashboard. The question-answering dashboard is at `/results/dashboard.html#assistant` and also opens directly as a local file.

## Scope and limits

The brief suggests vector databases/RAG as a bonus, not a mandatory dependency. Retrieval here uses deterministic sparse TF-IDF vectors in memory. Explanations are templates grounded in exact notes. The optional Ollama query planner is mock-tested, not live-benchmarked, and is not needed for the submitted batch or browser demo. Browser Q&A accepts supported route/month/verdict questions; it is not a general chatbot.

GitHub Pages serves the computed results and demos. Python recomputation runs locally; it is not a hosted backend. The truck motion is simulated. The supplied shipment data is sample data. Thresholds are documented design choices, not prescribed by the brief. Nine selected regression cases do not establish held-out accuracy.
