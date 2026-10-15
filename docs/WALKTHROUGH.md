# Ten-minute walkthrough

Keep `results/dashboard.html`, `results/output.csv`, and a terminal in the project folder ready. Rehearse these steps; do not make the untested optional local-model path a live-demo dependency.

| Time | Show | Explain |
|---|---|---|
| 0:00–0:45 | Dashboard overview | Find unexplained increases with inspectable evidence. 2,940 shipments become 728 route-weeks. |
| 0:45–2:15 | Chart and methodology | Weighted weekly rate; exact prior-eight-calendar-week history; same-week self-excluded peers. |
| 2:15–3:15 | Delhi-Jaipur, 2024-11-11 | +35.5% versus history. No adverse note; do not invent a cause. |
| 3:15–4:15 | Justified queue; Ahmedabad-Mumbai, 2025-01-20 | N002 has the correct route, time, and surcharge mechanism. Open the exact source. |
| 4:15–5:45 | Ask: Why did Chennai-Bangalore get pricier in March 2025? | March 3 overlaps the flood; March 10 does not. A restored-normal note cannot become a new excuse. |
| 5:45–6:30 | Mumbai-Pune, 2025-09-15 | Peer breach catches a smaller history rise. N006 is later and says stable conditions. |
| 6:30–7:30 | Run `python scripts/verify.py` | Independent numeric reference, regression cases, shuffle and no-look-ahead checks. |
| 7:30–8:15 | Reproducibility and cost JSONs | Three fresh processes, identical hashes, no LLM calls in batch. |
| 8:15–9:15 | engine.py, evidence.py, qa.py | Separate math, policy, evidence validation, and language interface. TF-IDF is not a transformer. |
| 9:15–10:00 | Limits and next steps | Reviewed labels, time holdouts, composition controls, and broader semantic/temporal evaluation. |

## Rehearsal commands

```bash
python -m freightwatch run
python -m freightwatch ask "Why did Chennai-Bangalore get pricier in March 2025?"
python -m freightwatch ask "Show unexplained routes"
python -m freightwatch ask "Why was Ahmedabad-Mumbai justified in January 2025?"
python scripts/verify.py
```

## Interview questions

**Why not an LLM for everything?** Graded numbers and evidence eligibility need determinism. Ten notes do not require expensive infrastructure. The optional model is restricted to query planning. Richer semantic extraction needs unseen-language evaluation before controlling decisions.

**Is this actually AI?** The default uses classical NLP vectors plus explicit rules, not a neural classifier or generative RAG. A real local-model adapter is implemented but only mock-tested here. Be precise: trust and reproducibility are demonstrated; broad semantic understanding is not.

**Why those thresholds?** They are transparent screening defaults, not an optimum established by labels. The sensitivity report shows 20, 14, and 7 unexplained flags. Production calibration requires reviewed labels, false-negative analysis, and review-capacity constraints.

**Can a note explain only part of a rise?** Yes. It establishes an applicable mechanism, not an exact impact. Quantified notes get a magnitude guard; qualitative evidence is weaker. The explanation explicitly discloses partial-week overlap and lack of quantitative causal allocation.

**Cold starts and missing weeks?** Use available weeks within 56 days, without padding. Show the count. No historical rise can be established in a first week. Missing peers do not prevent a history-based candidate.

**What about material or transporter mix?** Tonne-km controls transport work, not every cost driver. Those mix changes are legitimate confounders and future covariates. The prescribed baselines must remain unchanged even if a richer residual model is added.

**Why not use the diesel note for later weeks?** Its start is known but its duration and later incremental effect are not. Conservative onset-only attribution avoids a blanket excuse. This may increase false positives; the trade-off is visible.

**What did you actually test?** State the layers separately: 44 unit tests, all-row reference calculation, nine development cases, three byte-identical runs, and shuffle/prefix invariants. Do not convert nine selected cases into “100% anomaly accuracy.” UI/model availability have separate validation status.

**What next with another week?** Annotate an independent temporal holdout, measure retrieval recall and evidence precision, test semantic/date extraction and abstention, then address mix shifts before scaling infrastructure.

## Before submitting

- Rebuild on your laptop and visually inspect the dashboard, filters, chart, and CSV export.
- Read the numerical core and evidence module until you can explain each branch.
- Preserve the original data and actual logs in your repository/ZIP.
- If enabling Ollama, run it yourself and record its real model/version and usage.
- Personalize and rehearse the walkthrough. Follow the assessment rules.
