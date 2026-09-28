# Real-data track — GOV.UK architecture decisions (2017–2022)

Source: [alphagov/govuk-aws](https://github.com/alphagov/govuk-aws) (MIT). Model `qwen/qwen3.8-27b`. Evaluated as of 2022-12-01. Evidence for each decision = only ADRs dated after it. Pilot scale.

## 1. Assumption extraction on real prose

- ADRs: 38 · grounded assumptions kept: 109 (71 marked critical) · dropped because the quote was not verbatim in the source: 3
- ADRs with no extractable assumption: 0 (none)

## 2. Retrospective: does WHY flag the decisions GOV.UK later changed?

- Changed later (targets): flagged **3/3**, citing the record that changed it **3/3**
- Never revisited (controls): left as REUSE **4/5**

- Hindsight `reflect` (baseline): targets flagged 3/3, mentions the changing record 1/3; controls left as REUSE 3/5

| Decision | Date | What actually happened | WHY | Cited | reflect |
|---|---|---|---|---|---|
| GOVUK-0004 DNS definitions for hosts and services | 2017-07-14 | explicitly superseded by ADR 15 (DNS infrastructure) | ADAPT | GOVUK-0015, GOVUK-0016, GOVUK-0033 | ADAPT |
| GOVUK-0003 Networking Outline | 2017-06-30 | explicitly, in part, superseded by ADR 33 (IP ranges conflict with the Carrenza VPN) | RECONSIDER | GOVUK-0012, GOVUK-0026, GOVUK-0033, GOVUK-0038 | ADAPT |
| GOVUK-0028 Combine api-mongo cluster into mongo cluster | 2017-09-14 | implicitly reversed: ADR 38 moves Mongo apps, naming Content Store, to DocumentDB | RECONSIDER | GOVUK-0038 | RECONSIDER |
| GOVUK-0021 Use ACM for SSL purchases and terminate certificates on ELBs | 2017-08-14 | not revisited in the record | REUSE | GOVUK-0023, GOVUK-0025, GOVUK-0030, GOVUK-0031, GOVUK-0037 | REUSE |
| GOVUK-0022 Remove the Elasticsearch proxy | 2017-08-16 | not revisited in the record | REUSE | GOVUK-0037, GOVUK-0038 | REUSE |
| GOVUK-0024 AMI Lookups | 2017-08-29 | not revisited in the record | RECONSIDER | GOVUK-0015, GOVUK-0025, GOVUK-0030, GOVUK-0033, GOVUK-0037, GOVUK-0038 | RECONSIDER |
| GOVUK-0025 Use Elasticache for Redis | 2017-09-04 | not revisited in the record | REUSE | GOVUK-0029, GOVUK-0030 | REUSE |
| GOVUK-0029 Combine api-redis into backend-redis | 2017-09-14 | not revisited in the record | REUSE | GOVUK-0031, GOVUK-0033 | RECONSIDER |

## 3. What WHY said about the changed decisions

**GOVUK-0004 — DNS definitions for hosts and services** → ADAPT

**GOVUK-0003 — Networking Outline** → RECONSIDER
- BROKEN: The current IP layout is a viable reference point that can be closely approximated to ease the migration process. — *“We will attempt to keep the new IP layout as close as possible to the current one in order to ease migration.”* — The assumption that the new IP layout could closely approximate the current one to ease migration is no longer true. Evidence [GOVUK-0033] (2018-09-26) states that the IP addresses chosen in GOVUK-0003 'conflict' with the Carrenza environment due to the need for a VPN, and explicitly supersedes GOVUK-0003 by assigning new IP ranges that do not match the original plan. (GOVUK-0033)

**GOVUK-0028 — Combine api-mongo cluster into mongo cluster** → RECONSIDER
- BROKEN: The main application mongo cluster has sufficient capacity to handle the additional load from Content Store without becoming a single point of failure for the entire stack. — *“All other applications use the mongo cluster.”* — Evidence [GOVUK-0038] (2019-10-17) indicates that the architectural strategy has shifted to replacing MongoDB with AWS DocumentDB. It states that GOV.UK uses MongoDB for a number of apps and outlines a strategy to use AWS services. This implies that the long-term viability of relying on a standard 'main application mongo cluster' for capacity and SPOF concerns is superseded by the migration to DocumentDB, which changes the capacity and failure domain characteristics assumed in 2017. (GOVUK-0038)
