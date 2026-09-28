---
id: GOVUK-0005
kind: adr
title: Terraform Module Location
date: 2017-07-04
team: GOV.UK Platform
authors: GOV.UK Technical Operations
status: accepted
source: https://github.com/alphagov/govuk-aws/blob/master/docs/architecture/decisions/0005-terraform-module-location.md
---

# GOVUK-0005: Terraform Module Location

## Context

Document structure and deployment of Terraform [modules](https://www.terraform.io/docs/modules/index.html).

Terraform can fetch modules from multiple [sources](https://www.terraform.io/docs/modules/sources.html) (e.g. Github, local files, S3).

## Decision

Whilst developing a module we will source it locally (within this repository). 

Once we feel our modules "ready" we will consider moving them to separate repositories.

## Consequences

Keeping modules locally will make them harder for others to use but make rapid iteration easier.

Once modules are separated we will need processes to propagate changes in dependent modules to our main Terraform projects.
