# FreightWatch

**A freight-cost assistant that shows the evidence behind every decision.**

Submission for the FreightTiger Software Engineering Intern (AI) case study. Runs offline with Python's standard library. No API key, package installation, server, or database service is required for the submitted batch analysis and dashboard.

## Start here

1. Extract the ZIP. Open **`results/dashboard.html`** in a browser for the precomputed interactive demo.
2. See **`results/output.csv`** for the exact submission contract.
3. To rebuild and verify, run these commands **inside the `freightwatch` folder** with Python 3.10+:

```bash
python -m freightwatch run
python scripts/verify.py
python -m freightwatch ask "Why did Chennai-Bangalore get pricier in March 2025?"
```

On Windows, double-click `run_demo.bat` to regenerate and open the demo. On macOS/Linux, use `python3` if `python` is unavailable, then open `results/dashboard.html`. The dashboard is a local review artifact, not a hosted website.

## What the supplied data shows

| Measure | Default-policy result |
|---|---:|
| Shipments | 2,940 |
| Directional routes | 7 |
| Monday-based route-weeks | 728 |
| Unexplained elevated route-weeks | 14 |
| Evidence-backed elevated route-weeks | 3 |
| Below thresholds / no established rise | 711 |
| Unexplained excess cost versus historical rate | INR 88,318.43 |

Excess cost = max(0, current weekly rate minus historical mean) × current tonne-km. **This is neither a causal loss estimate nor recoverable savings.** Counts depend on the openly documented thresholds below; there are no provided anomaly labels establishing an optimal threshold.

Examples:

| Route / week | vs history | Decision | Evidence |
|---|---:|---|---|
| Delhi-Jaipur / 2024-11-11 | +35.5% | Unexplained | No applicable adverse-cost note |
| Ahmedabad-Mumbai / 2025-01-20 | +29.5% | Justified | N002, festival surcharge in that week |
| Chennai-Bangalore / 2025-02-24 | +31.5% | Justified | N001, flood window |
| Chennai-Bangalore / 2025-03-10 | +22.1% | Unexplained | N001 ended March 8; it cannot explain this week |
| Mumbai-Pune / 2025-09-15 | +9.2% | Unexplained | Peer breach; N006 is later and describes stable conditions |

## Exact calculations

Group on **origin, destination, provided route_type, and Monday of shipment_date**. Routes are directional; provided length categories are never inferred from distance. Materials and transporters remain inside the route group, as requested.

**Weekly rate:** `sum(freight_cost_inr) / sum(quantity_tonnes * distance_km)`. This is a tonne-km-weighted rate, not an unweighted average of shipment rates and not a product of separately summed quantities and distances.

**History:** arithmetic mean of this route/type's observed weekly rates in `[current Monday - 56 days, current Monday)`. Only strictly prior weeks count. If fewer than eight are present, use those available; no padding, interpolation, or carrying older observations across a missing calendar week. The export reason explicitly states when 1–7 weeks were available. No prior weeks → `N/A`, with no fabricated baseline.

**Peers:** arithmetic mean of the other directional routes' weekly rates with the same provided route_type in the same week. The subject route is excluded. Each other route has equal weight, irrespective of shipment volume. No peers → `N/A`.

**Comparisons:** `100 * (current_rate / baseline - 1)`. Calculations retain full float precision; output rate is formatted to two decimals and comparisons to one decimal, consistent with the sample. All numbers and baseline counts are also available unrounded in `audit.json`.

## Flagging policy, separate from the graded baselines

A candidate must be **at least 5% above its historical mean**, and meet either:

- At least **15% above history**, or
- At least **20% above current same-type peers**.

The rising-cost gate avoids flagging a route solely because it is persistently more expensive than its peers. A persistent elevation may remain a candidate even when it stops increasing week over week. A first observed week is not flagged without a historical basis for a rise. Low shipment counts are disclosed, not silently suppressed.

These are interpretable screening choices, not learned anomaly probabilities. They are not claimed as hidden evaluation criteria. Change them explicitly:

```bash
python -m freightwatch run --history-threshold 10 --peer-threshold 15 --rising-floor 3 --out results_sensitive
```

The verification report compares three policies: sensitive **20** unexplained, default **14**, strict **7**. Each has **3** supported justifications. No threshold search over an alleged ground-truth label set was performed.

## Retrieval and hallucination controls

`evidence.py` builds an in-memory **sparse TF-IDF vector index**, retrieves by cosine similarity, and uses stable note-ID tie-breaking. All ten notes are retained in each audit trail rather than dropping a potentially applicable note through an arbitrary top-k cutoff. Similarity is a retrieval ranking, never a confidence score or causal verdict.

Each retrieved note must pass all applicable gates:

1. Exact directional route match, or explicit `All Routes`.
2. Publication date no later than the end of the week. This is an end-of-week retrospective analysis, not an intra-day alert simulation.
3. A supported active window that overlaps an actual shipment day, not merely an empty part of the calendar week.
4. An explicit cost-increasing mechanism. Negative, unaffected, improved, or restored-normal statements are rejected.
5. Where a magnitude is stated, the historical rise must not exceed that maximum plus a disclosed **2 percentage point** tolerance. A 5–7% diesel rise cannot automatically excuse a 30% spike.

The supplied date expressions are interpreted conservatively. `Feb 24 to Mar 8` uses the note's year; `festival week` is seven days from the note date. For `starting this week` with no end date, only the onset week can receive automatic justification. Later effects may exist, but are not verified by that note alone. Unrecognized temporal or effect wording leads to abstention, not a guessed interval or cause.

Only a candidate that passes these checks receives `No (justified)` and a `matched_note_id`. Other candidates receive `Yes` and a blank note ID. Non-candidates receive `No` with a blank note ID. The exact source text is embedded in the justified explanation and stored with a SHA-256 hash in the audit. **“Justified” here means supported by applicable qualitative evidence, not proven to explain the entire monetary increase.** Partial-week overlap is disclosed; the note does not identify which shipments incurred which surcharge.

No note IDs, route IDs, or dates are hard-coded in decision logic. Regression tests deliberately reference known examples. The parser is intentionally constrained to recognizable language; extending it to arbitrary prose requires a broader temporal/negation evaluation set.

## Where AI is—and is not—used

The submitted default is **classical NLP retrieval + deterministic evidence reasoning + template explanations**. It is not a neural embedding system or LLM-generated RAG answer. That keeps the critical grading path inspectable and reproducible with ten short notes.

For an actual local language-model interaction, an **optional Ollama query planner** maps a question into a restricted JSON filter. It never writes final facts, computes baselines, or chooses a justification. The app validates the filter and renders the answer from computed rows. The offline dashboard and default CLI use a smaller deterministic parser with openly limited query coverage.

```bash
# Optional only: install Ollama separately and pull a model suited to your machine.
# Replace YOUR_INSTALLED_MODEL with a name shown by `ollama list`.
python -m freightwatch ask "Why did Chennai-Bangalore get pricier in March 2025?" --model YOUR_INSTALLED_MODEL
```

Ollama must be serving on `127.0.0.1:11434`. Temperature is 0 and seed is 42; this reduces variability but does not guarantee identical inference across model/hardware versions. **Batch verdicts are unaffected because the model is not in that path.** Adapter tests use mocked responses; a live model was not downloaded or benchmarked in the submission environment. Treat live-model integration as optional, not a demonstrated quality result. Route/month hallucinations are rejected; unsupported or ambiguous questions should be reformulated. It is a query assistant, not unrestricted conversation.

The integration follows the [official Ollama API reference](https://github.com/ollama/ollama/blob/main/docs/api.md): structured `format`, `/api/chat`, and measured token counters. A malformed or rejected response is not used to generate a factual answer. Successfully received responses log usage before filter validation; a network failure has unknown token usage and is surfaced as an error.

## Verification and reproducibility

Run `python scripts/verify.py`. It writes reviewable evidence under `results/`:

- **44 unit/contract tests**: weighted aggregation, Monday boundaries, exact historical window, missing data, direction and route-type keys, self-exclusion, rising-cost semantics, unsafe inputs, note scope/dates/negation, abstention, and optional model adapter checks.
- **Independent Decimal reference:** recalculates all 728 weekly rates and both baselines independently from raw CSV strings. Maximum differences must remain below `1e-10`.
- **9 explicit regression cases:** three sample examples plus flood boundaries, unknown-duration fuel attribution, and cold start. All expected verdicts and note IDs are checked. This small development set is not a held-out accuracy estimate.
- **Three fresh subprocess runs:** byte-identical `output.csv`, `audit.json`, `cost_log.json`, `dashboard.html`, and `manifest.json`, verified by SHA-256.
- **Metamorphic checks:** shuffling shipment/note order preserves output; truncating future shipments leaves all earlier results unchanged.
- **Threshold sensitivity:** reports the effect of changing screening choices without changing the required baselines.

`results/test_results.txt`, `evaluation.json`, and `reproducibility.json` contain the actual run evidence. The optional UI smoke test is described in `scripts/browser_smoke.cjs`; Playwright is a development-only dependency, never needed to run the submission.

## Cost of a full submitted run

`results/cost_log.json`: **0 LLM calls, 0 input tokens, 0 output tokens, USD 0 provider cost**. No model is invoked by `run`; no published per-token rate applies. CPU/electricity are not estimated or misrepresented as free. Sparse vector tokens are ordinary lexical features, not billed LLM tokens.

If the optional local-model question path is used, `results/qa_usage.jsonl` records actual `prompt_eval_count` / `eval_count`, the requested model, seed, temperature, and zero *provider* fee for local inference. Those interactive calls are separate from the submitted full batch run. Download/storage/compute costs still exist.

## Input and output integrity

Input files are preserved unchanged. The supplied template is named **`sample_output_format_v2.csv`**. Its third example reason has an unquoted comma, making that example row contain nine fields against an eight-field header. We use the **exact header as the schema contract**, without copying the broken example serialization. Our CSV uses proper quoting. Sample rows are illustrative; they are not copied into results.

Invalid dates, nonpositive or nonfinite quantities/distances/costs, duplicate shipment IDs, malformed records, and unsupported route types fail with a clear error. No records are silently discarded. Input hashes and output hashes are recorded in `manifest.json`.

The exact CSV has no route_type column, so multiple type assignments for the same route/week would be distinct internal rows sharing route/week in the export. The supplied dataset does not have that ambiguity. A production feed should enforce stable route types or extend the output key through an agreed schema change, not silently overwrite rows.

## Files to review

| Location | Purpose |
|---|---|
| `freightwatch/engine.py` | Validated ingestion, exact metrics, screening policy, CSV serializer |
| `freightwatch/evidence.py` | Vector retrieval, conservative evidence gates, grounded reasons |
| `freightwatch/qa.py` | Offline query parser and optional local-model planner |
| `freightwatch/dashboard.py` | Self-contained interactive review dashboard |
| `tests/` and `scripts/verify.py` | Unit, regression, numerical, and repeatability evidence |
| `results/output.csv` | Required deliverable; 728 rows, eight exact columns |
| `results/audit.json` | Full baselines, note rankings/rejections, source text, policy |
| `docs/WALKTHROUGH.md` | Ten-minute demo and interview discussion |
| `docs/DESIGN.md` | Architecture and production trade-offs |

## Known limits and next steps

This is an explainable prototype, not a causal attribution model. Route_type is a coarse peer grouping; material/transporter/load composition may cause legitimate differences. Small peer groups and contaminated rolling baselines reduce detection quality. Gradual creep can enter the eight-week baseline. Multiple overlapping events are not allocated quantitatively. Notes are assumed available at publication date; there is no supplied ingestion timestamp or event version history. The input is small and public/synthetic for this exercise; production access controls, scheduling, retention, monitoring, and incremental storage are out of scope.

Next steps would be operations-reviewed labels, holdout evaluation by time, shipment-level covariate controls, effect-duration metadata, and a tested semantic/temporal model with abstention. A vector database is unnecessary for ten notes; add one when persistence, scale, or multi-user ingestion makes it useful.

**Before submitting:** run the commands yourself, understand the assumptions, and personalize the walkthrough. Follow the assessment rules and explain only what you actually understand and ran.
