# Result files

**Current results** (what the README and the app's Evaluation page report):

| File | What it is | Produced by |
|---|---|---|
| `results.json`, `results.md` | Controlled benchmark: 26 questions × 7 contestants, tripwire | `python -m evaluation.run_benchmark` |
| `rows.jsonl` | One line per (contestant, question) answer; the checkpoint the report is built from | same |
| `tripwire.json` | Tripwire scenarios T1–T5 (single-call tripwire) | same |
| `real_govuk.json`, `real_govuk.md` | GOV.UK retrospective, judged by gpt-oss-120b (same model as the benchmark) | `python -m evaluation.run_real` |
| `real_govuk_runs.json` | Summary of every GOV.UK run, shown side by side on the Evaluation page | built from the three GOV.UK runs |
| `perf.json` | Latency, throughput and cost per question on Cerebras gpt-oss-120b | `python -m evaluation.run_perf --pace 14 --rpm 5` |

**Earlier runs, kept for transparency** (not reported as results):

| File | Why it's kept |
|---|---|
| `real_govuk_qwen_current.json/md` | GOV.UK run on qwen-3.8-27b with the current code: part of the model-sensitivity comparison |
| `real_govuk_qwen.json/md` | First GOV.UK run (qwen, before the uncited-UNKNOWN rule). It showed 3/3 caught; that didn't survive re-running, so it isn't quoted as the result |
| `real_govuk_gpt-oss-120b.json/md` | Copy of the current GOV.UK run |
| `rows_before_uncited_rule.jsonl` | WHY's answers before the rule that settles uncited UNKNOWNs (21/26) |
| `rows_groq_gpt-oss-20b.jsonl` | Partial run on Groq gpt-oss-20b, abandoned when the free-tier quota ran out; mixing models would have made rows incomparable |
| `tripwire_percandidate.json` | Tripwire with one LLM call per candidate decision (precision 0.385), before it was batched into one call (0.5) |
| `perf_groq_qwen.json` | Latency measured earlier on Groq qwen |
