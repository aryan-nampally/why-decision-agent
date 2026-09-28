---
id: GOVUK-0022
kind: adr
title: Remove the Elasticsearch proxy
date: 2017-08-16
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0022-remove-the-elasticsearch-proxy.md
---

# GOVUK-0022: Remove the Elasticsearch proxy

## Context

We currently have a local nginx based proxy for Elasticsearch connections
on a number of our machines. The original reason for this was:

```
Load balance connections to Elasticsearch by creating a loopback-only
vhost in Nginx which will forward to a set of Elasticsearch servers.

This is for the benefit of applications with client libraries that don't
support native cluster awareness or load balancing.
```

In the AWS environments these services are behind an ELB so this layer may
no longer be required.

## Decision

We've tested the instances in AWS without the local proxies and we have not discovered any
degradation of service when using the ELBs. In light of this we will remove the configuration and
exclude this puppet code from running in AWS and accept the ELBs as its replacement.

## Consequences

There will be a slight difference, considered by the team to be an improvement,
between the current environments and the new, AWS ones. This means we won't be
testing the exact same thing but will simplify the networking and application 
data flow paths.
