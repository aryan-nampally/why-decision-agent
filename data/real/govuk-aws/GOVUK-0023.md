---
id: GOVUK-0023
kind: adr
title: Use separate data repository
date: 2017-08-18
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0023-use-separate-data-repository.md
---

# GOVUK-0023: Use separate data repository

## Context

We have a large amount of data which is needed to run the Terraform projects.

Some of the data we need to use is sensitive (e.g. RDS passwords). It is considered best practice to keep sensitive information encrypted in private repositories. This means that access can be controlled and the that the data will remain secure, even if it is accidentally published.

## Decision

The `terraform/data` directory will be split out into its own repository that will be kept private and all sensitive data within it will be encrypted using [sops](https://github.com/mozilla/sops).

## Consequences

Sensitive data will not be publicly available. Should it leak it will still be cryptographically protected.

The terraform build tool will need to be extended to deal with an external data directory.

Building the terraform project will require access to both the terraform and the data repositories.
