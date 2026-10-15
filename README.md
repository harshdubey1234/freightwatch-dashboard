# FreightWatch

**Freight-cost monitoring with an inspectable reason behind every decision.**

FreightTiger Software Engineering Intern case study. Python 3.10+; **no runtime dependencies, API keys, or server**. Inputs are preserved unchanged.

## Submission links

- [Live India dashboard](https://harshdubey1234.github.io/freightwatch-dashboard/)
- [Offline analysis dashboard with question answering](https://harshdubey1234.github.io/freightwatch-dashboard/results/dashboard.html)
- [Complete submission ZIP](https://harshdubey1234.github.io/freightwatch-dashboard/FreightWatch_Submission.zip)
- [Required output CSV](results/output.csv)
- [Requirement checklist](docs/ASSIGNMENT_CHECKLIST.md)

The hosted site is a precomputed demo. Run the Python commands below to process the supplied or replacement input files. GitHub Pages does not run Python or Ollama. Truck motion is illustrative, not live GPS. This is an independent case-study prototype. Asset provenance is in [ASSET_SOURCES.md](ASSET_SOURCES.md).

## Run or demo

Open **`results/dashboard.html`** for the precomputed interactive demo. The submission CSV is **`results/output.csv`**. Rebuild from this folder:

```bash
python -m freightwatch run
python scripts/verify.py
python scripts/prepare_submission.py
python -m freightwatch ask "Why did Chennai-Bangalore get pricier in March 2025?"
```

Windows: `run_demo.bat` rebuilds and opens the dashboard. macOS/Linux: use `python3` if needed. See [the ten-minute walkthrough](docs/WALKTHROUGH.md).

## Supplied-data results

| Shipments | Routes | Route-weeks | Unexplained | Justified | Below thresholds |
|---:|---:|---:|---:|---:|---:|
| 2,940 | 7 | 728 | 14 | 3 | 711 |

Chennai-Bangalore's flood supports February 24 and March 3, 2025, **not March 10**, after the disruption ended. N002 supports Ahmedabad-Mumbai's January 20 surcharge. Delhi-Jaipur's November 11 rise and Mumbai-Pune's September 15 rise remain unexplained.

## Method

1. Validate records; fail on invalid dates, duplicate IDs, malformed rows, or nonpositive/nonfinite denominators and costs.
2. Group by directional route, provided `route_type`, and Monday–Sunday week. Weekly rate = **sum(freight) / sum(tonnes × km)**.
3. History = **arithmetic mean of available weekly rates in the preceding eight calendar weeks**, excluding the current week. With fewer than eight, use those available and disclose the count. No padding or look-ahead. Peers = **same-week arithmetic mean of all other routes of the same type**, excluding self.
4. Screen for **≥5% above history AND (≥15% above history OR ≥20% above peers)**. These configurable thresholds are explicit policy choices, not learned probabilities or prescribed grading thresholds. First-week observations cannot establish a rise; low-volume weeks remain visible.
5. Retrieve using **TF-IDF sparse vectors**, then require matching route, time window, shipment overlap, positive cost effect, and plausible stated magnitude. Similarity never decides justification. No eligible note → unexplained, with blank `matched_note_id`.

The CSV has exactly the eight sample columns in order. Exact source text, rejected-note reasons, full-precision baselines, counts, and hashes are in `audit.json` and `manifest.json`.

## Retrieval and runtime cost

Default: **classical NLP retrieval + deterministic explanations**, not neural embeddings or LLM-generated RAG. Full batch: **0 LLM calls, 0 input/output tokens, USD 0 provider cost** (`cost_log.json`). No published model rate applies; local compute is not claimed to be free.

An optional **Ollama local-model query planner** selects a validated filter; answers are rendered from computed results, so it cannot rewrite flags or explanatory prose:

```bash
python -m freightwatch ask "Why Chennai-Bangalore in March 2025?" --model YOUR_INSTALLED_MODEL
```

Requires an installed model and Ollama at `127.0.0.1:11434`. Uses temperature 0, seed 42, and measured token logging. **The adapter is mock-tested; live inference was not benchmarked here.** Dashboard Q&A uses a limited offline route/month/verdict parser.

## Validation

- **44 automated tests**, covering numerical edge cases, scope, expiry, negation, abstention, and model-filter validation.
- Independent high-precision Decimal check of **all 728 rates and both baselines** within `1e-10`.
- **9/9 regression cases**; a small development set, not held-out accuracy.
- **Three byte-identical fresh-process runs**, proved by SHA-256 for all five generated artifacts.
- Input shuffling preserves output; removing future shipments leaves prior results unchanged.
- Sensitive/default/strict policies yield **20/14/7 unexplained** route-weeks.

Evidence: `results/test_results.txt`, `evaluation.json`, `reproducibility.json`. UI validation has a separate report; browser rendering and live-model inference are not included in the numerical test claim.

## Trade-offs

Unknown-duration notes justify only their onset week. A stated 5–7% fuel rise cannot excuse a much larger spike (2 percentage point tolerance). “Justified” means evidence supports a plausible explanation, **not proof of full causality**. Partial-week overlap is disclosed; no-effects notes cannot suppress alerts.

Excess cost versus history is **not recoverable savings**. Peer groups are coarse, composition changes can confound flags, and gradual creep can enter the rolling baseline. Temporal/effect parsing is constrained; unfamiliar language abstains. Comprehensive anomaly labels were not supplied.

The sample's third example has an unquoted comma. Its **header** is the contract; our CSV correctly quotes prose. [Full methodology](docs/METHODOLOGY.md) covers assumptions and optional model details; [design](docs/DESIGN.md) covers architecture.


