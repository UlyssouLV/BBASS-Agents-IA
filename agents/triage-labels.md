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

## Lifecycle

GitHub issues are **Open** or **Closed**. There is **no** `awaiting-merge` label.

When `/implement` finishes green: skill `encadrer-implement` commits, pushes, **removes `ready-for-agent`**, then **`gh issue close`** on that **child**. Closing the blocker updates GitHub **Blocking** / **Blocked by** so the next tickets can start.

The **parent** spec stays Open until squash-merge (`Fixes #<parent>`). Once children exist it is **Blocked by** each of them (no `ready-for-agent` on the parent). Code can still exist only on the feature branch until « Finalise la version ».

Edit the right-hand column of the triage table to match whatever vocabulary you actually use.
