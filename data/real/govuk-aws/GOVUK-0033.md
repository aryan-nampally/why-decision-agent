---
id: GOVUK-0033
kind: adr
title: Networking Outline
date: 2018-09-26
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0033-ip-ranges.md
---

# GOVUK-0033: Networking Outline

## Context

This ADR in part supersedes [0003](0003-aws-networking-outline.md).

In [ADR 0003](0003-aws-networking-outline.md), we specified
some IP address ranges for staging and production - ones that matched
Carrenza as far as possible.

As part of the gradual migration of Staging and Production to AWS, we
need to use a VPN to talk to Carrenza, so the chosen IP addresses conflict.

## Decision

The VPCs will be assigned the following IP ranges:
 
|Environment|IP Range|
|-----------|--------|
|Integration|10.1.0.0/16|
|Staging|10.12.0.0/16|
|Production|10.13.0.0/16|
|Test|10.200.0.0/16|

That is:

- Integration and Test do not change.
- Staging moves from 10.2.0.0/16 to 10.12.0.0/16.
- Production moves from 10.3.0.0/16 to 10.13.0.0/16.

## Consequences

We can now set up short-lived VPNs between Carrenza Staging and Production
environments and AWS Staging and Production environments.
