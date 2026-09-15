# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| --------------------------- | --------------------- | ----------------------------------------- |
| `needs-triage`              | `needs-triage`        | Maintainer needs to evaluate this issue   |
| `needs-info`                | `needs-info`          | Waiting on reporter for more information  |
| `ready-for-agent`           | `ready-for-agent`     | Fully specified, ready for an AFK agent   |
| `ready-for-human`           | `ready-for-human`     | Requires human implementation             |
| `wontfix`                   | `wontfix`             | Will not be actioned                      |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

## Lifecycle (not a Matt Pocock triage role)

GitHub issues are only **Open** or **Closed**. This extra label marks work that is **coded on a feature branch** but **not yet in `main`**. Do not `gh issue close` for that.

| Label in our tracker | Meaning |
| -------------------- | ------- |
| `awaiting-merge`     | Implemented on the feature branch. Issue stays **Open**. Remove `ready-for-agent` / `ready-for-human` so agents do not re-implement it. GitHub closes the issue at PR merge via `Fixes #n`. |

When `/implement` finishes green: skill `encadrer-implement` commits, pushes, adds `awaiting-merge` and removes the ready-* labels.

Edit the right-hand column of the triage table to match whatever vocabulary you actually use.
