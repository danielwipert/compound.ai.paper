# Compound AI Architecture Benchmark — Product Spec

**Version:** 1.0 · **Date:** 2026-10-29 · **Owner:** Daniel Wipert, Chorus AI Systems
**Status:** Locked through decisions D1–D9 (see `decisions.md`). Open questions OQ-1 to OQ-5 outstanding.

This is the short, human-readable spec. The full engineering detail is in `tech-spec.md`.

---

## 1. What we're trying to prove

**One sentence:** A compound AI system — several small open-weight models wired together by a deterministic Python bus — can match a frontier model on accuracy for enterprise data work while costing a fraction as much to run.

**Why anyone should care:** Enterprises are paying frontier-model prices for tasks that are mostly parsing, joining, and arithmetic. If small models plus deterministic code do the job as well, the economics of AI operations change. If they don't, that's worth knowing too.

**What makes this honest:** We are *not* comparing against a frontier model used badly. The control is a frontier model given structured output and a code tool — the way a competent team would actually deploy it. We also commit our predictions to the repo before running anything.

## 2. The task

Take a messy supply-chain export and produce a clean, verified exception report.

Each row is an order. The system must:

1. Figure out what each column is, even when headers have been renamed
2. Pull facts out of free-text carrier notes (e.g. delay causes and durations)
3. Compute the financial figures exactly
4. Write a short exception report that only states things it can back up

Real exports have all of these problems. We simulate them deliberately so we have ground truth for every row.

## 3. What we're comparing

Three ways of doing the same task.

### 3.1 Arm A — Naive monolith *(secondary)*
One frontier model, one prompt, does everything in a single pass — including the arithmetic. This is how a lot of first prototypes are built. We expect it to fail in interesting ways.

### 3.2 Arm B — Tooled monolith *(the control)*
Same frontier model, but given a JSON schema for its output and a code-execution tool for the math. This is the fair comparison. If the compound system can't tie this on accuracy, the cost argument doesn't matter.

Frontier models: Claude Sonnet 5.5 and OpenAI's current mid-tier equivalent. (D7)

### 3.3 Arm C — Compound system *(the thing we're testing)*
Four small hosted models, each with one narrow job, connected by plain Python:

| Node | Job | Model family |
|------|-----|--------------|
| A — Ingestion | Map noisy column headers to a strict typed schema | Qwen (3–4B) |
| B — Extraction | Turn carrier free text into structured facts | SmolLM3 (3B) |
| Python bus | Join, compute financials, build an immutable FactList | No model — pure Python |
| C — Synthesis | Draft the exception report, citing only the FactList | Llama (8B) |
| D — Verifier | Independent critic; halts the output if C says anything not in the FactList | Mistral (7B) |

All nodes run in the cloud through a model gateway. No local inference. (D4)

Four different model families are used on purpose: models from the same family share blind spots.

## 4. What we measure

| Metric | What it answers | How it's scored |
|--------|-----------------|-----------------|
| **Field-mapping accuracy** | Did the system correctly identify renamed columns? | Exact match vs. known mapping, per column |
| **Extraction accuracy** | Did it pull the right facts from carrier notes? | Precision / recall vs. labelled facts |
| **Coverage** | How often did it refuse (hard halt) instead of answering? | Halt rate, reported next to accuracy — never hidden inside it |
| **Financial accuracy** | Are the computed numbers right? | Exact match vs. deterministic ground truth |
| **Groundedness** | Does the report say only what the facts support? | Claims in report traced to FactList |
| **Cost** | What does it cost per 1,000 rows? | Two columns for Arm C: actual spend, and the same models at paid list rates |
| **Latency** | How long per row? | Wall-clock, median and p95 |

The two metrics at the top are the primary ones. (D2) They're where small models can genuinely fail, so they're where the result is interesting.

## 5. How big, how much

**Pilot** — 100 rows, one noise level, 5 repeat runs. Purpose: prove the pipeline works end to end. Not for publication. Cash cost ≈ $20–25.

**Full matrix** — 500 rows × 3 noise levels (5%, 15%, 30% of headers renamed) × 5 repeat runs. Purpose: the paper. Produces a degradation curve — accuracy vs. noise — for each arm. Cash cost ≈ $140–160 using batch pricing (including a small groundedness-judge line); Claude-side usage covered by Max plan API credits across two monthly cycles. (D3)

Compound-arm API spend is near zero (free tiers), which is why the second cost column exists. (D5)

## 6. Keeping ourselves honest

Before the pilot runs, we commit and tag:

- `HYPOTHESES.md` — the direction we expect each metric to go, per arm
- The analysis script that will produce every table and figure

After that, the hypotheses don't change. If the result goes the other way, the paper says so. (D6)

## 7. What comes out

1. **A GitHub repository** — code, schemas, data, every execution trace, specs, decision log. Fully reproducible.
2. **A paper** — arXiv preprint (cs.AI / cs.SE), with Zenodo as fallback. Core content: the cost–accuracy trade-off, the degradation curves, and the deterministic-guardrail method. (D8)
3. **Launch posts** — Hacker News, Reddit, LinkedIn, all pointing at the repository.

## 8. Where things live

```
/docs       product-spec.md · tech-spec.md · decisions.md · HYPOTHESES.md
/src        pipeline, arms, noise injector, metrics, analysis
/data       raw DataCo export · golden test set · noised variants
/results    traces, metrics, figures — one folder per run
/paper      manuscript source
```
(D9)

## 9. Phases

| Phase | What happens | Done when |
|-------|--------------|-----------|
| 0 — Spec | This document, tech spec, decisions D1–D9, open questions resolved | OQ-1 to OQ-5 closed in `decisions.md` |
| 1 — Build | Golden set, noise injector, three arms, metrics, analysis script | Dry run on 5 rows passes all gates |
| 2 — Pre-register | `HYPOTHESES.md` + analysis script committed and tagged | Tag `prereg-v1` exists |
| 3 — Pilot | 100 × 1 × 5 across all arms | Bugs fixed; preliminary numbers posted as work-in-progress |
| 4 — Full run | 500 × 3 × 5, batch pricing | All traces and metrics in `/results` |
| 5 — Paper | Draft, figures, endorsement, submit | arXiv ID or Zenodo DOI |
| 6 — Launch | HN / Reddit / LinkedIn | Posted |

## 10. Risks

| Risk | What we do about it |
|------|---------------------|
| Free-tier throttling stalls the full run | Fallback model per node; retry with backoff; run in chunks |
| Compound system ties but doesn't beat the tooled monolith on accuracy | That's a fine result — the claim is "ties on accuracy, wins on cost." Pre-registered as such. |
| Compound system *loses* on accuracy | Report it. Still a useful finding about where small models break. |
| Model names change before build | Lock exact IDs in `tech-spec.md` at build time; record them in the decision log |
| arXiv endorsement not secured | Zenodo DOI, same PDF |

## 11. Theoretical framing (one paragraph)

The architecture follows Chorus AI Systems' standing thesis that trust is a property of the system, not of any one model. In cybernetic terms: the Python bus is the regulator with fixed variety; each small model handles one bounded slice of the input's variety (Ashby); the verifier node is an independent observer of the synthesizer, not a self-check (second-order cybernetics). The benchmark tests whether that structure buys anything measurable.
