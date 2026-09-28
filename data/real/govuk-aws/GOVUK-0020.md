---
id: GOVUK-0020
kind: adr
title: Merge API PostgreSQL instance into main PostgreSQL instance
date: 2017-08-07
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0020-merge-api-postgresql-instance-into-main-postgresql-instance.md
---

# GOVUK-0020: Merge API PostgreSQL instance into main PostgreSQL instance

## Context

The only database that runs on API PostgreSQL instances is Stagecraft, which is
for the Performance Platform.

This is able to run on the main PostgreSQL instance as we do not have the split
of "vDCs" that we have in our current hosting provider.

Work is ongoing to migrate the Performance Platform away from our infrastructure
and to The Government PaaS, so the long term plan is not have this database in
our infrastructure at all.

## Decision

We should merge the API PostgreSQL instance into the main PostgreSQL instance.

## Consequences

The application configuration will need to be updated to connect to the correct database.

We are able to reduce the amount of database instances we maintain.
