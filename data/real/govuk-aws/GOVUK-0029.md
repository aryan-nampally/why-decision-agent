---
id: GOVUK-0029
kind: adr
title: Combine api-redis into backend-redis
date: 2017-09-14
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0029-combine-api-redis-into-backend-redis.md
---

# GOVUK-0029: Combine api-redis into backend-redis

## Context

We currently have 3 Redis instances that we run in Elasticache:

 - backend-redis
 - logs-redis
 - api-redis

Most applications use backend-redis, the logging cluster uses logs-redis (which should
soon be replaced), and Rummager uses api-redis.

This was traditionally the case because Rummager lived in a different vDC to redis-1/redis-2,
but this is no longer a concern in AWS.

## Decision

Update Rummager configuration so it uses backend-redis, and remove api-redis.

## Consequences

Everything relying on a single redis instance could potentially have impact if there is
an issue with that Elasticache instance.

We will save money on not running multiple Elasticache instances.
