---
id: GOVUK-0026
kind: adr
title: Remove load balancer tier
date: 2017-08-16
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0026-remove-load-balancer-tier.md
---

# GOVUK-0026: Remove load balancer tier

## Context

We currently have a dedicated tier of load balancers for the backend, frontend and api
VDCs. In the Amazon world these are less useful as we also have ELBs in place to handle
the autoscaling of instances. We want to reduce the networking complexity and remove these machines.

## Decision

We will not change the current vcloud based platforms.

In the AWS environment we will remove the load balancer hosts / ELBs and instead add external
ELBs to a number of other autoscaling groups (such as the frontend / backend hosts themselves) 
to make them directly available, but security group restricted.

We have also decided to split the domains we use to an internal and external one. That
is discussed in ADR TODO: TBC.

## Consequences

3 classes of machines, and the instances running them, will be removed from our architecture
in this environment. Some of the LBs processing, such as trace ids, will be pushed down
the stack to the application servers themselves. We will have more ELBs running for a period of time.

All traffic will go to the external domain names at this phase of the move. The ADR TODO: TBC will
explain the risks and remediations for this change.
