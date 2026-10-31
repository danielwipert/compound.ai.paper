---
title: Compound AI Architecture Benchmark — Technical Specification
version: 1.0
date: 2026-10-29
owner: Daniel Wipert / Chorus AI Systems
status: draft-locked-through-D9
decisions: docs/decisions.md
product_spec: docs/product-spec.md
section_id_prefix: TS
---

# Compound AI Architecture Benchmark — Technical Specification

Every section carries a stable ID (`TS-n` / `TS-n.m`). Code, tests, and the paper reference these IDs. Changes to a locked section require a new entry in `decisions.md`.

Legend: `LOCKED` = decided (see Dn) · `OPEN` = pending (see OQ-n) · `BUILD` = to be fixed at build time and recorded.

---

## TS-1 Scope and claims

### TS-1.1 Research question `LOCKED D1 D2`

Does a compound system of small open-weight models bounded by a deterministic Python bus (Arm C) match a tooled frontier model (Arm B) on component accuracy under input noise, while costing less per 1,000 rows?

### TS-1.2 Claims the paper may make

| Claim ID | Statement | Required evidence |
|----------|-----------|-------------------|
| C1 | Arm C field-mapping accuracy is within the 95% CI of Arm B at every drift level | TS-7.1, TS-8 |
| C2 | Arm C extraction accuracy is within the 95% CI of Arm B at every drift level | TS-7.2, TS-8 |
| C3 | Arm C list-price cost per 1,000 rows is lower than Arm B by a factor reported with CI | TS-7.6 |
| C4 | Arm A degrades faster than Arm B and Arm C as drift increases | TS-7.1, TS-7.4, TS-8.3 |
| C5 | Arm C groundedness violations are zero or reported exactly | TS-7.5 |

Claims not in this table are not made. Claims are stated as pre-registered hypotheses in `HYPOTHESES.md` (TS-9).

### TS-1.3 Non-claims

- No claim about local/on-prem deployment (all nodes hosted, D4).
- No claim that the compound system generalizes beyond the task in TS-2.
- No claim of novelty for individual components (LLM-as-judge, Pydantic gating, cross-family verification are known); the claim is about the measured system behaviour.

---

## TS-2 Dataset

### TS-2.1 Source

- **Name:** DataCo Smart Supply Chain Dataset
- **Host:** Mendeley Data
- **File:** `DataCoSupplyChainDataset.csv` (~180k rows, 53 columns)
- **Encoding:** latin-1 (known quirk; normalise to UTF-8 on ingest)
- **Licence:** `BUILD` — record licence text in `data/LICENSE-dataco.txt`

### TS-2.2 Columns used

| Canonical field | DataCo header | Type | Role |
|-----------------|---------------|------|------|
| `order_id` | `Order Id` | int | join key |
| `order_item_id` | `Order Item Id` | int | row identity |
| `sales` | `Sales` | float | financial |
| `benefit_per_order` | `Benefit per order` | float | financial (profit) |
| `order_item_profit_ratio` | `Order Item Profit Ratio` | float | financial reconciliation |
| `order_item_quantity` | `Order Item Quantity` | int | financial |
| `days_shipping_real` | `Days for shipping (real)` | int | delay |
| `days_shipping_scheduled` | `Days for shipment (scheduled)` | int | delay |
| `delivery_status` | `Delivery Status` | enum | delay |
| `late_delivery_risk` | `Late_delivery_risk` | bool(0/1) | delay |
| `shipping_mode` | `Shipping Mode` | enum | context |
| `order_status` | `Order Status` | enum | context |
| `category_name` | `Category Name` | str | context |
| `order_region` | `Order Region` | str | context |
| `order_date` | `order date (DateOrders)` | datetime | context |
| `shipping_date` | `shipping date (DateOrders)` | datetime | context |

Sixteen columns. All other DataCo columns are dropped at ingest. `BUILD`: verify header strings byte-for-byte against the download.

### TS-2.3 Golden Test Set `LOCKED D3`

**Size:** 500 rows (full matrix). The pilot uses the first 100 rows of the same set in a fixed order.

**Stratification** (target shares, sampled with `seed=20261029`):

| Stratum | Selection rule | Share |
|---------|----------------|-------|
| S1 negative profit | `benefit_per_order < 0` | 20% |
| S2 severe delay | `days_shipping_real - days_shipping_scheduled >= 3` | 20% |
| S3 risk flag contradicts delay (D14) | `delay_days > 0 AND late_delivery_risk == 0` | 10% |
| S4 cancelled / suspected fraud | `order_status IN ('CANCELED','SUSPECTED_FRAUD')` | 10% |
| S5 high-value | `sales >= p95(sales)` | 10% |
| S6 baseline | none of the above | 30% |

Strata are disjoint; rows matching multiple rules are assigned to the first matching stratum in table order. Row order (D14): 5 blocks of 100, each holding the exact stratum shares (20/20/10/10/10/30), shuffled within the block; the pilot uses block 1. Resulting file: `data/golden/golden_500.csv` plus `data/golden/golden_500.strata.json`.

### TS-2.4 Ground truth

Ground truth is computed once by `src/ground_truth.py` from the clean golden set and frozen as `data/golden/ground_truth.parquet`. Fields:

```
order_item_id            int
header_map               dict[noisy_header -> canonical_field]   (per drift variant, TS-3.2)
delay_facts              list[DelayFact]                           (per row, TS-3.3)
cost_basis               float    = sales - benefit_per_order       (OQ-2, see note)
profit_ratio_recomputed  float    = benefit_per_order / sales
profit_ratio_delta       float    = profit_ratio_recomputed - order_item_profit_ratio
delay_days               int      = days_shipping_real - days_shipping_scheduled
risk_class               enum     {NONE, LATE, SEVERE_LATE, LOSS_MAKING, FRAUD_HOLD}
```

*Storage (build note):* `ground_truth.parquet` holds the per-row fields (`order_item_id`, `cost_basis`, `profit_ratio_recomputed`, `profit_ratio_delta`, `delay_days`, `risk_class`). `header_map` and `delay_facts` vary per `(level, seed)` and are written by the noise injector to `data/noised/{level}/{seed}/` (TS-3.2, TS-3.3).

`risk_class` rule (deterministic, in this order): `FRAUD_HOLD` if `order_status == 'SUSPECTED_FRAUD'`; `LOSS_MAKING` if `benefit_per_order < 0`; `SEVERE_LATE` if `delay_days >= 3`; `LATE` if `delay_days > 0`; else `NONE`.

> **Note on OQ-2.** The original spec's "financial variance" is `Sales − Benefit per order`. In DataCo, `Benefit per order` is profit, so that quantity is cost basis, not margin variance. This spec computes it under the correct name (`cost_basis`) and adds `profit_ratio_delta` as the reconciliation check. Which one headlines "financial accuracy" is OQ-2.
>
> **Note on D13.** DataCo's `Order Item Profit Ratio` is computed from post-discount `Order Item Total`, not `Sales`, so `profit_ratio_delta` mostly reflects the discount. It is kept as defined and described as such; it is not a reconciliation check.

---

## TS-3 Noise injection

### TS-3.1 Principle

Noise is applied by `src/noise/inject.py` to the clean golden set, producing one variant per `(drift_level, seed)`. Because every corruption is generated from a known rule, ground truth is available for every corrupted cell at zero labelling cost.

### TS-3.2 Schema drift `LOCKED D3`

**Levels:** 5%, 15%, 30% of the 16 canonical headers renamed → 1, 2–3, 5 headers respectively (rounded: 1 / 2 / 5). Rounding locked by D15: `round(0.05*16)=1`, `round(0.15*16)=2`, `round(0.30*16)=5`.

**Rename pool** (`src/noise/rename_pool.yaml`): for each canonical field, ≥5 plausible alternates in three styles — abbreviated snake_case, vendor-style camelCase, and semantic paraphrase. Example for `benefit_per_order`:

```yaml
benefit_per_order:
  - net_ord_margin_usd
  - orderProfit
  - "Profit (per order)"
  - ben_per_ord
  - margin_contribution
```

Selection of which headers to rename and which alternate to use is seeded. The mapping is written to `data/noised/{level}/{seed}/header_map.json` and is ground truth for TS-7.1.

**Rule:** `order_id` and `order_item_id` are never renamed (the join key must survive, or the task is ill-posed). `BUILD`: revisit under OQ-1 if duplicate-ID noise is added.

### TS-3.3 Unstructured carrier notes `LOCKED D3`

For every row with `delay_days > 0`, a free-text `carrier_notes` column is appended. Notes are generated from templates in `src/noise/note_templates.yaml`, each template carrying its structured facts:

```yaml
- template: "Port congestion at terminal {terminal}; customs release delayed {hours} hrs"
  facts:
    cause: PORT_CONGESTION
    secondary_cause: CUSTOMS
    delay_hours: "{hours}"
- template: "Driver shortage on {route} lane. ETA pushed {days}d."
  facts:
    cause: LABOUR
    delay_days: "{days}"
```

Fact schema (`DelayFact`):

```python
class DelayFact(BaseModel):
    cause: Literal["PORT_CONGESTION","CUSTOMS","WEATHER","LABOUR","MECHANICAL","ADDRESS_ISSUE","CAPACITY","UNKNOWN"]
    secondary_cause: Optional[...] = None
    delay_hours: Optional[int] = None
    delay_days: Optional[int] = None
    location: Optional[str] = None
```

Rows with `delay_days <= 0` get `carrier_notes = ""` in 80% of cases and a benign note (`"Delivered. No exceptions."` → facts: none) in 20%, so that "empty note" is not a perfect predictor of "no facts."

Templates: ≥25. Each note instantiation is seeded. Ground truth per row written to `data/noised/{level}/{seed}/delay_facts.jsonl`.

### TS-3.4 Additional noise axes `OPEN OQ-1`

Candidates, not yet gated: null injection (2–5% of numeric cells), duplicate `order_item_id` rows (1%), currency symbol / thousands separator in `sales` (`"$1,234.50"`), column reordering. If adopted, each gets its own ground-truth file and metric row.

---

## TS-4 Experimental arms `LOCKED D1`

### TS-4.1 Common task contract

Every arm receives the same input and must produce the same output shape.

**Input per row:** one CSV line (noised headers), plus the header row.
**Output per row:** `ExceptionRecord`:

```python
class ExceptionRecord(BaseModel):
    order_item_id: int
    header_map: dict[str, str]          # noisy header -> canonical field
    delay_facts: list[DelayFact]
    cost_basis: float
    profit_ratio_recomputed: float
    delay_days: int
    risk_class: RiskClass
    report: str                          # <= 120 words
    citations: list[str]                 # FactList keys referenced by `report`
    status: Literal["OK","HALT"]
    halt_reason: Optional[str] = None
```

Arms may internally decompose this however they like; the comparison is on `ExceptionRecord`.

### TS-4.2 Arm A — Naive monolith

- One call per row (batched in groups of 10 rows per request to amortise the header; `BUILD`: confirm batch size).
- Prompt: `src/arms/a_naive/prompt.md`. Few-shot (3 examples from a held-out set, not from the golden 500). Asks for a JSON object matching `ExceptionRecord`.
- No tool use. No structured-output mode. Model does the arithmetic in-context.
- Output parsed with `json.loads`; on parse failure → `status=HALT, halt_reason="PARSE_FAIL"`.

### TS-4.3 Arm B — Tooled monolith (control)

- Same models, same batch size, same few-shot examples.
- `response_format` / structured-output mode bound to the `ExceptionRecord` JSON schema.
- Code-execution tool enabled (provider-native code interpreter where available; otherwise a sandboxed Python tool exposed via function calling — `BUILD` per provider, record choice).
- Prompt instructs: compute all numeric fields with the tool, never in-context.
- Schema violation at the provider level → `HALT, "SCHEMA_FAIL"`.

### TS-4.4 Arm C — Compound system

See TS-5.

### TS-4.5 Fairness constraints

| Constraint | Rule |
|------------|------|
| Same few-shot examples | Arms A, B, and Nodes A/B/C use the same 3 held-out examples, adapted to each node's sub-task |
| Same output schema | All arms produce `ExceptionRecord`; metrics never read arm-internal state |
| Same halt vocabulary | `halt_reason ∈ {PARSE_FAIL, SCHEMA_FAIL, MAP_UNRESOLVED, EXTRACT_FAIL, VERIFY_REJECT, PROVIDER_ERROR}` |
| Temperature | 0.0 everywhere where the provider allows; otherwise provider minimum; recorded per run |
| Seeds | Provider seed parameter set where supported; the experiment seed also governs noise, stratification order, and bootstrap |

---

## TS-5 Compound pipeline (Arm C)

### TS-5.1 Topology

```
CSV row ──► Node A (ingest) ──► Gate 1 (Pydantic) ──┐
                                                    ├──► Python bus ──► FactList ──► Node C (synth) ──► Node D (verify) ──► ExceptionRecord
carrier_notes ─► Node B (extract) ─► Gate 2 (Pydantic) ┘                                    │                    │
                                                                                            └──── reject ◄───────┘
```

Nodes A and B run in parallel. The bus runs only after both gates pass. Node D may reject at most twice; a third rejection → `HALT, VERIFY_REJECT`.

### TS-5.2 Node A — Ingestion (header mapping)

- **Input:** the noisy header row only (not the data), plus the canonical field list with one-line descriptions.
- **Output:** `HeaderMap`:
  ```python
  class HeaderMap(BaseModel):
      mapping: dict[str, CanonicalField]      # noisy -> canonical
      unresolved: list[str]
      confidence: dict[str, float]
  ```
- **Gate 1 rules:** all 16 canonical fields must be present exactly once in `mapping.values()`; `order_id` and `order_item_id` must map to themselves; otherwise `HALT, MAP_UNRESOLVED`.
- Node A is called **once per (level, seed) variant**, not per row — the header row is the same for all 500 rows. Its cost is amortised accordingly (TS-7.6).
- Model: Qwen 3–4B class. `BUILD`: exact gateway model ID.

### TS-5.3 Node B — Extraction (carrier notes)

- **Input:** `carrier_notes` string for one row; the `DelayFact` schema with enum definitions.
- **Output:** `list[DelayFact]` (may be empty).
- **Gate 2 rules:** Pydantic validation; unknown enum value → `HALT, EXTRACT_FAIL`. Empty list is valid.
- Model: SmolLM3 3B class. `BUILD`: exact gateway model ID.

### TS-5.4 Python bus

`src/compound/bus.py`. No model calls. Steps, in order:

1. Rename columns using `HeaderMap.mapping`.
2. Cast types per TS-2.2; cast failure → `HALT, SCHEMA_FAIL`.
3. Compute `cost_basis`, `profit_ratio_recomputed`, `profit_ratio_delta`, `delay_days`, `risk_class` per TS-2.4 — identical code path to `ground_truth.py` (shared module `src/finance.py`), so Arm C financial accuracy is by construction 100% whenever Gates 1–2 pass. This is stated explicitly in the paper (D2).
4. Assemble `FactList`:
   ```python
   class Fact(BaseModel):
       key: str          # e.g. "F3"
       field: str
       value: str | float | int
       source: Literal["BUS","NODE_B"]
   class FactList(BaseModel):
       order_item_id: int
       facts: list[Fact]
       digest: str       # sha256 of canonical JSON; immutable after creation
   ```
5. Freeze: `FactList` is hashed; downstream nodes receive it read-only.

### TS-5.5 Node C — Synthesis

- **Input:** `FactList` only. No raw row, no carrier note text.
- **Output:** `report` (≤120 words) and `citations: list[str]` of `Fact.key` values used.
- **Prompt rule:** every sentence must reference ≥1 fact key in brackets, e.g. `[F3]`.
- Model: Llama 8B class (`OPEN OQ-4`).

### TS-5.6 Node D — Verifier

- **Input:** `FactList` + Node C output.
- **Output:**
  ```python
  class Verdict(BaseModel):
      accept: bool
      unsupported_claims: list[str]
      missing_citations: list[str]
  ```
- **Rule:** `accept=False` if any sentence in `report` contains a numeric value, cause, or classification not present in `FactList`, or cites a key that does not exist.
- On reject: Node C is re-run with the `Verdict` appended (max 2 retries). Third reject → `HALT, VERIFY_REJECT`.
- Model: Mistral 7B class — must be a different family from Node C (observer-diversity rule).
- **Independent check:** in addition to Node D, `src/compound/lint.py` does a deterministic regex/number check that every number in `report` appears in `FactList`. Discrepancies between lint and Node D are logged (TS-7.5 secondary metric: verifier recall vs lint).

### TS-5.7 Family diversity

| Node | Family | Must differ from |
|------|--------|------------------|
| A | Alibaba / Qwen | — |
| B | HuggingFace / SmolLM | — |
| C | Meta / Llama | D |
| D | Mistral | C |

Four distinct families. Same-family substitution in a fallback (TS-6.3) is allowed only if logged, and the affected rows are flagged in results.

---

## TS-6 Models, gateway, and resilience `LOCKED D4 D7`

### TS-6.1 Model table

| Role | Model | Provider path | Pricing mode | Status |
|------|-------|---------------|--------------|--------|
| Monolith 1 (Arms A, B) | Claude Sonnet 5.5 | Anthropic API direct (Max-plan credits) — batch API for full run | list / batch 50% | LOCKED D7 |
| Monolith 2 (Arms A, B) | OpenAI mid-tier equivalent | OpenAI API direct — batch API for full run | list / batch 50% | ID: BUILD |
| Node A | Qwen 3–4B | gateway | free tier | ID: BUILD |
| Node B | SmolLM3 3B | gateway | free tier | ID: BUILD |
| Node C | Llama 8B | gateway | free tier | OQ-4 |
| Node D | Mistral 7B | gateway | free tier | ID: BUILD |

`BUILD`: at build time, record the exact model ID string, provider, context length, and list price (input/output per 1M tokens) for every row in `results/model_manifest.json`. Lock via decision entry D10.

### TS-6.2 Gateway `OPEN OQ-3`

Candidates: Hopscotch AI (`https://hopscotchlabs.ai/v1`, OpenAI-compatible, zero markup, BYOK) or OpenRouter. Requirements either way:

- OpenAI-compatible chat completions endpoint
- Per-request usage object (prompt / completion tokens) returned
- Per-key spend limit configurable
- Model fallback list (native or implemented in `src/gateway/client.py`)

Single client class `GatewayClient` with provider adapters; all arms call through it so traces have one shape.

### TS-6.3 Resilience

| Condition | Handling |
|-----------|----------|
| HTTP 429 / 5xx | Exponential backoff: 2s, 4s, 8s, 16s, 32s; then fallback model |
| Fallback model | Declared per node in `config/models.yaml`; must respect TS-5.7 |
| Fallback exhausted | `HALT, PROVIDER_ERROR` — counted in coverage, excluded from accuracy denominators, reported separately |
| Run chunking | Full matrix executed in chunks of 50 rows; each chunk checkpointed to `results/{run_id}/chunks/`; resumable |
| Daily free-tier caps | Scheduler spreads compound-arm calls across days if cap reached; recorded in run log |

### TS-6.4 Secrets

`.env` only; never committed. `config/models.yaml` references env var names.

---

## TS-7 Metrics `LOCKED D2 D5`

All metrics computed by `src/metrics/compute.py` from `ExceptionRecord` outputs and ground truth. Denominators are explicit in every table.

### TS-7.1 Field-mapping accuracy (primary)

- **Unit:** one renamed header.
- **Score:** 1 if `header_map[noisy] == ground_truth_map[noisy]`, else 0.
- **Aggregate:** mean over renamed headers, per (arm, level, seed). Un-renamed headers are reported separately as a sanity check (should be ~1.0).
- **Denominator:** renamed headers in rows with `status == OK`. Halted rows excluded here and counted in TS-7.3.

### TS-7.2 Extraction accuracy (primary)

- **Unit:** one `DelayFact` (matched on `cause`; numeric fields must match exactly).
- **Score:** precision, recall, F1 against ground-truth facts per row; micro-averaged per (arm, level, seed).
- **Denominator:** rows with non-empty ground-truth facts and `status == OK`.

### TS-7.3 Coverage

- `coverage = OK_rows / total_rows` per (arm, level, seed).
- Halt breakdown by `halt_reason`.
- **Reporting rule:** every accuracy figure in the paper is printed adjacent to its coverage. A combined "accuracy × coverage" column is permitted only as a secondary figure, labelled as such.

### TS-7.4 Financial accuracy

- Match within half a unit of the rounded value (D12): ±0.005 on `cost_basis` (money, 2 dp); ±0.00005 on `profit_ratio_recomputed` (ratio, 4 dp); exact match on `delay_days` and `risk_class`. *(Originally: tolerance 1e-6; superseded by D12.)*
- Reported per field. For Arm C this is 100% by construction on OK rows (TS-5.4); the paper states this and directs the reader to TS-7.1/7.2.
- `OPEN OQ-2`: which field headlines.

### TS-7.5 Groundedness

- **Unit:** one sentence of `report`.
- **Score:** 1 if every number, cause, and classification in the sentence is present in ground truth for that row (not merely in the arm's own FactList — this catches an arm grounding itself in its own wrong facts); else 0.
- Scored by `src/metrics/ground.py` (deterministic lint) plus a cross-family LLM judge (model not used in any arm; `BUILD`). Disagreements adjudicated by the deterministic rule; judge used only for cause/classification paraphrase.
- Secondary: Node D recall vs deterministic lint on Arm C.

### TS-7.6 Cost

Per (arm, level, seed):

```
cost_actual_usd        = Σ provider-reported charges (0 for free-tier)
cost_list_usd          = Σ (prompt_tokens × list_in + completion_tokens × list_out) / 1e6
cost_per_1k_rows_*     = cost_* / rows × 1000
```

- Arm C reports **both** columns (D5). Monolith arms report list and batch-rate (50%) columns.
- Node A amortised: its per-variant cost divided across the 500 rows of that variant.
- Tool-execution charges (Arm B code tool) included where the provider bills them.

### TS-7.7 Latency

Wall-clock per row, median and p95, per arm. Reported but not a claim; Arm C's parallel A/B nodes and retries make it a secondary observation.

---

## TS-8 Statistics

### TS-8.1 Resampling

- Bootstrap over **rows** (1,000 resamples) within each (arm, level, seed) → per-seed CI.
- Then aggregate over **seeds** (5) → reported point estimate = mean of seed means; CI = percentile bootstrap over the pooled row×seed resamples.

### TS-8.2 Comparisons

- Primary: Arm C vs Arm B on TS-7.1 and TS-7.2, per level. Report difference with 95% CI. "Within CI" (C1, C2) means the CI of the difference includes 0.
- Secondary: Arm A vs Arm B, Arm A vs Arm C.
- No p-values in headline tables; CIs only. p-values in appendix if a reviewer wants them.

### TS-8.3 Degradation curve

For each arm and primary metric: plot vs drift level (5/15/30) with CI bands. Slope reported as (metric at 30%) − (metric at 5%).

### TS-8.4 Pilot handling

Pilot results are reported in the repo README as "preliminary, n=100, one level" and are **not** used in the paper's tables. They may be used to sanity-check the analysis script.

---

## TS-9 Pre-registration `LOCKED D6`

### TS-9.1 Contents of `docs/HYPOTHESES.md`

For each claim C1–C5: predicted direction, the metric and comparison it maps to, and the decision rule ("supported / not supported / inconclusive"). Magnitudes are not predicted.

### TS-9.2 Freeze procedure

1. `HYPOTHESES.md` finalised.
2. `src/analysis/run_analysis.py` finalised — it must be able to run end-to-end on the 5-row dry-run output.
3. Commit; tag `prereg-v1`; record tag hash in `decisions.md` as D11.
4. Pilot runs only after the tag exists.

### TS-9.3 Permitted changes after freeze

- Bug fixes in the analysis script that do not change a metric definition (logged in `decisions.md`).
- Additional *exploratory* analyses, clearly labelled as post-hoc in the paper.
- Nothing else.

---

## TS-10 Run protocol `LOCKED D3`

### TS-10.1 Dry run

5 rows × 1 level (15%) × 1 seed × all arms. Purpose: every code path exercised, every file in TS-11 produced. Gate: `run_analysis.py` completes without error.

### TS-10.2 Pilot

| Parameter | Value |
|-----------|-------|
| Rows | 100 (first 100 of golden_500, fixed order) |
| Drift levels | 15% |
| Seeds | 5 |
| Arms | A, B, C |
| Monolith pricing | standard (not batch — speed matters here) |
| Expected cash | ≈ $20 (OpenAI side); Claude side on Max credits |
| Output | `results/pilot-v1/` |

Exit criteria: no `PROVIDER_ERROR` halts attributable to the harness; metrics script produces every table; at least one bug fixed and logged.

### TS-10.3 Full matrix

| Parameter | Value |
|-----------|-------|
| Rows | 500 |
| Drift levels | 5%, 15%, 30% |
| Seeds | 5 |
| Arms | A, B, C |
| Row-runs per arm | 7,500 |
| Monolith pricing | batch API (both providers) |
| Expected cash | ≈ $140 (OpenAI side, batch); Claude side on Max credits across 2 monthly cycles |
| Output | `results/full-v1/` |

### TS-10.4 Run identity

Every run has `run_id = {phase}-{yyyymmdd}-{short_git_sha}`. `results/{run_id}/manifest.json` records: git SHA, model manifest, config hash, seeds, start/end timestamps, total cost actual and list.

---

## TS-11 Repository layout and traces `LOCKED D9`

### TS-11.1 Tree

```
.
├── README.md
├── LICENSE                          # code: MIT (BUILD: confirm)
├── pyproject.toml
├── config/
│   ├── models.yaml                  # model IDs, fallbacks, list prices
│   └── experiment.yaml              # levels, seeds, rows, batch sizes
├── docs/
│   ├── product-spec.md
│   ├── tech-spec.md                 # this file
│   ├── decisions.md
│   └── HYPOTHESES.md
├── data/
│   ├── raw/                         # DataCo CSV (git-lfs or download script)
│   ├── golden/                      # golden_500.csv, strata, ground_truth.parquet
│   ├── noised/{level}/{seed}/       # noised CSV, header_map.json, delay_facts.jsonl
│   └── fewshot/                     # 3 held-out examples
├── src/
│   ├── ground_truth.py
│   ├── finance.py                   # shared deterministic financial functions
│   ├── noise/                       # inject.py, rename_pool.yaml, note_templates.yaml
│   ├── gateway/                     # client.py, adapters/
│   ├── arms/
│   │   ├── a_naive/
│   │   ├── b_tooled/
│   │   └── c_compound/              # nodes/, bus.py, lint.py
│   ├── metrics/                     # compute.py, ground.py
│   ├── analysis/                    # run_analysis.py, figures.py
│   └── runner.py                    # chunking, checkpoints, resume
├── results/
│   ├── dryrun-*/ pilot-*/ full-*/
│   └── model_manifest.json
├── paper/
│   ├── main.tex (or main.md → pandoc)
│   └── figures/
└── tests/
```

### TS-11.2 Trace format

One markdown file per row per arm: `results/{run_id}/traces/{arm}/{level}/{seed}/{order_item_id}.md`. Sections, in order:

```
# {arm} · level={level} · seed={seed} · order_item_id={id}
## Input            (noised row, headers)
## Calls            (one subsection per model call: model id, prompt hash, tokens in/out, latency ms, cost actual/list)
## Intermediate     (Arm C only: HeaderMap, DelayFacts, FactList + digest, Verdicts)
## Output           (ExceptionRecord as JSON)
## Ground truth     (relevant fields)
## Scores           (per-metric)
```

Plus a machine copy: `.../{order_item_id}.json` with the same content. Prompts are stored once by hash in `results/{run_id}/prompts/{hash}.md` to keep traces small.

### TS-11.3 Reproducibility

- `make dryrun`, `make pilot`, `make full` targets.
- `make analysis RUN=full-v1` regenerates every table and figure from traces.
- `results/` committed for pilot and full runs (traces are text; expected size < 200 MB; git-lfs if larger).

---

## TS-12 Paper `LOCKED D8`

| Item | Value |
|------|-------|
| Venue | arXiv cs.AI (primary) or cs.SE; Zenodo fallback |
| Length | 8–10 pages + appendix |
| Sections | Introduction · Related work (compound AI, LLM-as-judge, structured-output evaluation, cost benchmarking) · Task & data (TS-2, TS-3) · Arms (TS-4, TS-5) · Metrics & statistics (TS-7, TS-8) · Pre-registration (TS-9) · Results · Threats to validity · Conclusion |
| Figures | F1 degradation curves (×2 primary metrics); F2 cost per 1k rows (log scale, actual + list); F3 coverage/halt breakdown; F4 pipeline diagram |
| Endorsement | sought at Phase 1 start; contact list in `paper/endorsement.md` (not committed publicly) |

---

## TS-13 Budget

| Line | Pilot | Full | Notes |
|------|-------|------|-------|
| OpenAI monolith (Arms A+B) | ~$20 | ~$140 | batch rate for full |
| Claude monolith (Arms A+B) | ~$20 → credits | ~$140 → credits | Max 5x plan: $100/mo API credits; full run spans 2 cycles |
| Compound nodes | ~$0 | ~$0 | free tiers; list-equivalent reported ≈ $1–3 total |
| Groundedness judge | <$5 | <$20 | cross-family, cheap model |
| **Cash out of pocket** | **≈ $25** | **≈ $160** | |

Assumptions: ~1,500 prompt + ~500 completion tokens per row for Arm A; ~2× for Arm B. `BUILD`: replace with measured dry-run token counts.

---

## TS-14 Open questions and build-time locks

| ID | Resolves in | Blocking? |
|----|-------------|-----------|
| OQ-1 extra noise axes | decisions.md | No — can ship v1 without |
| OQ-2 headline financial field | decisions.md | Yes — before HYPOTHESES.md |
| OQ-3 gateway | decisions.md | Yes — before dry run |
| OQ-4 Node C model | decisions.md | Yes — before dry run |
| OQ-5 MARL-EVAL naming | paper | No |
| BUILD model IDs / prices | D10 | Yes — before pre-registration tag |
| BUILD prereg tag hash | D11 | Yes — before pilot |

---

## TS-15 Glossary

| Term | Definition |
|------|------------|
| Arm | One complete pipeline under test (A naive, B tooled, C compound) |
| Node | One model-backed stage inside Arm C |
| Bus | The deterministic Python stage inside Arm C; no model calls |
| Gate | A Pydantic validation boundary; failure → HALT |
| FactList | Immutable, hashed list of facts produced by the bus and Node B; sole input to Nodes C and D |
| Halt | A row the arm declines to answer; counted in coverage, excluded from accuracy denominators |
| Drift level | Share of canonical headers renamed in a noised variant |
| Variant | One `(level, seed)` noised copy of the golden set |
| Row-run | One row processed by one arm in one variant |
