# Gateway survey — 2026-10-31

Input to OQ-3 (gateway) and OQ-4 (Node C model). Snapshot only; prices change.
Prices are USD per 1M tokens (input / output).

## Sources

| Gateway | How checked | Coverage |
|---------|-------------|----------|
| OpenRouter | Public feed `https://openrouter.ai/api/v1/models` (452 models) | Complete |
| Hopscotch AI | Public catalog page `https://hopscotchlabs.ai/models`; the API list (`api.hopscotchlabs.ai/v1/models`) needs a key | Partial — may list more once signed in |
| Hugging Face Inference Providers (bonus) | Public feed `https://router.huggingface.co/v1/models` (135 models), OpenAI-compatible | Complete |

## Spec models vs what exists

| Node (spec) | OpenRouter | Hopscotch (public page) | HF router |
|-------------|-----------|-------------------------|-----------|
| A — Qwen 3–4B | ✗ smallest: `qwen/qwen-2.5-7b-instruct` 0.10/0.20, `qwen/qwen3.5-9b` 0.17/0.25 | ✗ smallest: Qwen3.5-9B, Qwen3-14B | ✓ `Qwen/Qwen3-4B-Instruct-2507` 0.01/0.03 (nscale) |
| B — SmolLM3 3B | ✗ | ✗ | ✗ |
| C — Llama 8B | ✓ `meta-llama/llama-3.1-8b-instruct` 0.05/0.08 | ✓ Meta-Llama-3.1-8B-Instruct(-Turbo) | ✓ `meta-llama/Llama-3.1-8B-Instruct` 0.02/0.05 |
| D — Mistral 7B | ✗ closest: `mistralai/ministral-8b-2512` 0.15/0.15, `mistralai/mistral-nemo` (12B) 0.029/0.03 | ✗ only Mistral-Nemo (12B) seen | ✗ |

**Free tiers:** OpenRouter lists 17 free models; none are Qwen, SmolLM, Llama or Mistral. Hopscotch has no free tier (list price, no markup; optional prepaid "passes", e.g. $20/seat → $40 usage, capped at $3 per 5 h and $10/week on Starter).

## Small models from other families (Node B replacement candidates)

| Model | OpenRouter | Hopscotch |
|-------|-----------|-----------|
| `google/gemma-3-4b-it` (Google) | 0.05/0.10 | ✓ |
| `ibm-granite/granite-4.2-8b` (IBM) | 0.06/0.15 | ✓ (also 3B) |
| `liquid/lfm-2.5-2.6b` (Liquid AI) | free variant exists; paid 0.35/0.50 | ✗ |
| `cohere/command-r7b-12-2024` (Cohere) | 0.037/0.15 | not checked |

## Monolith candidates (OpenRouter feed)

| Role | Model | Price | Batch |
|------|-------|-------|-------|
| Claude (D7) | `anthropic/claude-sonnet-5.5` | 2.00/10.00 | 1.00/5.00 |
| OpenAI, same price as Sonnet | `openai/gpt-6.1-sol` | 2.00/10.00 | 1.00/5.00 |
| OpenAI, "terra" tier | `openai/gpt-6.1-terra` | 1.00/5.00 | 0.50/2.50 |

## Rough compound-arm cost if all nodes are paid

Per row-run ≈ 4.6k input + 0.6k output tokens across Nodes B, C, D (with ~20% retries); Node A is per variant and negligible.
Full matrix (7,500 row-runs) ≈ 34M input + 4.4M output → **about $2–7** at the prices above. Pilot ≈ $0.50.
