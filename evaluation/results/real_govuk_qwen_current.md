# Real-data track — GOV.UK architecture decisions (2017–2022)

Source: [alphagov/govuk-aws](https://github.com/alphagov/govuk-aws) (MIT). Judge model `qwen-3.8-27b`; assumptions extracted with `qwen/qwen3.8-27b` (cached in data/extracted_govuk). Evaluated as of 2022-12-01. Evidence for each decision = only ADRs dated after it. Pilot scale.

## 1. Assumption extraction on real prose

- ADRs: 38 · grounded assumptions kept: 109 (71 marked critical) · dropped because the quote was not verbatim in the source: 3
- ADRs with no extractable assumption: 0 (none)

## 2. Retrospective: does WHY flag the decisions GOV.UK later changed?

- Changed later (targets): flagged **2/3**, citing the record that changed it **3/3**
- Never revisited (controls): left as REUSE **1/5**

- Hindsight `reflect` (baseline): targets flagged 3/3, mentions the changing record 1/3; controls left as REUSE 5/5

| Decision | Date | What actually happened | WHY | Cited | reflect |
|---|---|---|---|---|---|
| GOVUK-0004 DNS definitions for hosts and services | 2017-07-14 | explicitly superseded by ADR 15 (DNS infrastructure) | REUSE | GOVUK-0015, GOVUK-0016 | ADAPT |
| GOVUK-0003 Networking Outline | 2017-06-30 | explicitly, in part, superseded by ADR 33 (IP ranges conflict with the Carrenza VPN) | RECONSIDER | GOVUK-0012, GOVUK-0029, GOVUK-0033 | RECONSIDER |
| GOVUK-0028 Combine api-mongo cluster into mongo cluster | 2017-09-14 | implicitly reversed: ADR 38 moves Mongo apps, naming Content Store, to DocumentDB | RECONSIDER | GOVUK-0038 | RECONSIDER |
| GOVUK-0021 Use ACM for SSL purchases and terminate certificates on ELBs | 2017-08-14 | not revisited in the record | REUSE | GOVUK-0023, GOVUK-0025, GOVUK-0026, GOVUK-0030, GOVUK-0031, GOVUK-0035 | REUSE |
| GOVUK-0022 Remove the Elasticsearch proxy | 2017-08-16 | not revisited in the record | ADAPT | GOVUK-0027, GOVUK-0028, GOVUK-0037 | REUSE |
| GOVUK-0024 AMI Lookups | 2017-08-29 | not revisited in the record | ADAPT | GOVUK-0015, GOVUK-0030, GOVUK-0038 | REUSE |
| GOVUK-0025 Use Elasticache for Redis | 2017-09-04 | not revisited in the record | ADAPT | GOVUK-0029 | REUSE |
| GOVUK-0029 Combine api-redis into backend-redis | 2017-09-14 | not revisited in the record | ADAPT | GOVUK-0033 | INSUFFICIENT_EVIDENCE |

## 3. What WHY said about the changed decisions

**GOVUK-0004 — DNS definitions for hosts and services** → REUSE

**GOVUK-0003 — Networking Outline** → RECONSIDER
- BROKEN: The current IP layout is a viable reference point that can be closely approximated to ease the migration process. — *“We will attempt to keep the new IP layout as close as possible to the current one in order to ease migration.”* — GOVUK-0033 (2018-09-26) states that GOVUK-0003’s staging and production IP ranges matched Carrenza as far as possible, but the chosen IP addresses conflict with the VPN to Carrenza, so the VPCs were assigned new IP ranges; the old layout is no longer a viable close reference. (GOVUK-0033)

**GOVUK-0028 — Combine api-mongo cluster into mongo cluster** → RECONSIDER
- BROKEN: Content Store is the sole consumer of the api-mongo cluster, meaning no other applications depend on it. — *“The only application that uses the api-mongo cluster is Content Store.”* — GOVUK-0038 lists the current MongoDB topology as five clusters: Licensify, performance monitoring, router, and one per cloud provider for all other apps including content. It does not include a separate api-mongo cluster, so the condition that Content Store is the sole consumer of an api-mongo cluster no longer describes the current architecture. (GOVUK-0038)
