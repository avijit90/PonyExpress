# CI publishing

The CI runner needs network access to the upstream URL and write access to the capsule destination repository. It does not need to expose a GitLab/GitHub API to the restricted machine.

## GitHub Actions

Create a workflow-dispatch workflow in the capsule repository. It checks out that repository, installs PonyExpress, runs `publish` with `inputs.source_url` and `inputs.ref`, then commits `capsules/` with `GITHUB_TOKEN` configured for contents write.

Creating a brand-new destination repository is a separate provisioning action and requires a GitHub App or token with repository-creation permission. A long-lived capsule repository avoids that extra permission.

## GitLab CI

Use a manual job with `SOURCE_URL` and `SOURCE_REF` variables. The job checks out the capsule project, runs `publish`, and pushes its generated commit using a project access token or deploy token with write access.

## Publish policy

Only publish source URLs and refs your organization permits. Record the upstream URL, exact commit, and license/provenance information alongside the capsule when required by policy.
