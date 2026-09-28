# WHY benchmark results — 2026-09-28T13:54:47+00:00

Judge/baseline model `gpt-oss-120b` · assumption extraction `openai/gpt-oss-120b (cached in data/extracted/)` · B3 uses Hindsight's own reflect model · commit `dc5eca1` · 26 cases · one run per condition · pilot scale; intervals are Wilson 95%.

## All cases

| Condition | Verdict acc. | Precedent hit@1 | False reuse ↓ | False reconsider ↓ | Repeat error ↓ | Premise acc. | Flip acc. | Assumption F1 | Median ms |
|---|---|---|---|---|---|---|---|---|---|
| C | 23/26 (0.89) | 23/23 (1.00) | 1/16 (0.06) | 0/7 (0.00) | 0/3 (0.00) | 5/6 (0.83) | 3/3 (1.00) | 0.837 | 13358 |
| C-oracle | 25/26 (0.96) | 23/23 (1.00) | 0/16 (0.00) | 0/7 (0.00) | 0/3 (0.00) | 6/6 (1.00) | 2/3 (0.67) | 0.978 | 13287 |
| B3 | 17/26 (0.65) | 23/23 (1.00) | 0/16 (0.00) | 0/7 (0.00) | 0/3 (0.00) | 3/6 (0.50) | 0/3 (0.00) | — | 8786 |
| B2 | 13/26 (0.50) | 20/23 (0.87) | 4/16 (0.25) | 0/7 (0.00) | 0/3 (0.00) | 1/6 (0.17) | 1/3 (0.33) | — | 13233 |
| A | 8/26 (0.31) | 0/23 (0.00) | 4/16 (0.25) | 1/7 (0.14) | 1/3 (0.33) | 1/6 (0.17) | 0/3 (0.00) | — | 13286 |
| ALWAYS-R | 10/26 (0.39) | 0/23 (0.00) | 0/16 (0.00) | 7/7 (1.00) | 0/3 (0.00) | 4/6 (0.67) | 0/3 (0.00) | 0.0 | 0 |
| C-1stage | 23/26 (0.89) | 23/23 (1.00) | 0/16 (0.00) | 0/7 (0.00) | 0/3 (0.00) | 5/6 (0.83) | 3/3 (1.00) | 0.884 | 13347 |

## Test split only (excludes demo questions used in development)

| Condition | Verdict acc. | Precedent hit@1 | False reuse ↓ | False reconsider ↓ | Repeat error ↓ | Premise acc. | Flip acc. | Assumption F1 | Median ms |
|---|---|---|---|---|---|---|---|---|---|
| C | 18/21 (0.86) | 19/19 (1.00) | 1/14 (0.07) | 0/5 (0.00) | 0/2 (0.00) | 2/3 (0.67) | 1/1 (1.00) | 0.857 | 13370 |
| C-oracle | 20/21 (0.95) | 19/19 (1.00) | 0/14 (0.00) | 0/5 (0.00) | 0/2 (0.00) | 3/3 (1.00) | 1/1 (1.00) | 0.973 | 13274 |
| B3 | 15/21 (0.71) | 19/19 (1.00) | 0/14 (0.00) | 0/5 (0.00) | 0/2 (0.00) | 2/3 (0.67) | 0/1 (0.00) | — | 8786 |
| B2 | 11/21 (0.52) | 16/19 (0.84) | 3/14 (0.21) | 0/5 (0.00) | 0/2 (0.00) | 1/3 (0.33) | 0/1 (0.00) | — | 13207 |
| A | 6/21 (0.29) | 0/19 (0.00) | 2/14 (0.14) | 0/5 (0.00) | 0/2 (0.00) | 0/3 (0.00) | 0/1 (0.00) | — | 13290 |
| ALWAYS-R | 8/21 (0.38) | 0/19 (0.00) | 0/14 (0.00) | 5/5 (1.00) | 0/2 (0.00) | 2/3 (0.67) | 0/1 (0.00) | 0.0 | 0 |
| C-1stage | 18/21 (0.86) | 19/19 (1.00) | 0/14 (0.00) | 0/5 (0.00) | 0/2 (0.00) | 2/3 (0.67) | 1/1 (1.00) | 0.914 | 13368 |

## Paired comparison with WHY (C), exact McNemar on verdict correctness

| vs | other right, C wrong | C right, other wrong | p |
|---|---|---|---|
| C-oracle | 3 | 1 | 0.625 |
| B3 | 3 | 9 | 0.146 |
| B2 | 1 | 11 | 0.0063 |
| A | 1 | 16 | 0.0003 |
| ALWAYS-R | 0 | 13 | 0.0002 |
| C-1stage | 0 | 0 | 1.0 |

## Tripwire

Precision 0.5 · recall 0.833 (5 correct of 10 raised, 6 expected)
