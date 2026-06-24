# Result Auditor As Offline Package Audit

AI-VulnAtlas will add a standalone `audit-results` command that audits a completed **Result Package** instead of extending `audit-output` or embedding the logic into `run`. We chose this because the new auditor judges task-level trustworthiness rather than output-format completeness: it consumes package artifacts such as `summary.csv`, audit reports, runtime logs, and any packaged task evidence, then emits one deduplicated **Audit Result** row per `(project, canonical_id)` with rule-based `yes/no` judgements and normalized review reasons.

## Considered Options

- Extend `audit-output`: rejected because `audit-output` already means markdown-contract and leakage checks against a live output directory, and reusing the name would hide a materially different responsibility.
- Reconstruct evidence by re-reading repos, advisories, or git history during auditing: rejected for the first version because a **Result Auditor** must be able to judge an exported **Result Package** offline; when evidence is absent, the package should fail with `evidence_missing` rather than silently re-enter analysis mode.

## Consequences

The first version of `audit-results` will be deterministic and package-bounded: it will deduplicate duplicate summary rows, mark conflicts explicitly, treat `needs_manual_review` as the final operational decision, and produce separate auditor outputs such as `audit_results.csv` and `audit_results_report.md` without changing the meaning of existing `audit-output` reports.
