---
id: GOVUK-0004
kind: adr
title: DNS definitions for hosts and services
date: 2017-07-14
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0004-dns-definitions-for-hosts-and-services.md
---

# GOVUK-0004: DNS definitions for hosts and services

## Context

For our current monitoring to work we need Icinga to be able to communicate with hosts and services.

## Decision

Each stack will have an internal, private, zone for internal services such as the puppetmaster. These
will be in the following format:

    $servicename.$stackname.internal

    puppet.perftesting.internal
    monitoring.mystack.internal

## Consequences

TBC
