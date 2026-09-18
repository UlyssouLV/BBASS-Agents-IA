---
name: prochaine-etape
description: >-
  After /clear or a new chat, run the saved next command from
  `.claude/prochaine-etape.md` (usually `/implement #<n>`). User-invoked only.
disable-model-invocation: true
---

# Relais après reset de contexte

The previous chat is gone. **Do not ask the user which ticket.** Read the disk file, then run it.

File (gitignored): `.claude/prochaine-etape.md`

```
commande: /implement #42
issue: 42
parent: 13
branche: v1.2.1-identite-visuelle
sha: abcdef0
```

`commande` is the only required field. `issue` / `parent` / `branche` / `sha` are hints.

## Steps

1. Read `.claude/prochaine-etape.md`. If it is missing or has no `commande:` line, recover with `gh`: parent of the current feature-branch PR → lowest Open `ready-for-agent` child with `blocked_by` 0. If that child exists, treat `commande` as `/implement #<n>`. If none, treat `commande` as `Finalise la version`.
2. **`/implement #<n>`** — run the Matt Pocock `/implement` plugin on that child now, same as if the user had typed it. Then skill `encadrer-implement` as usual. Leave the file on disk until `encadrer-implement` overwrites it.
3. **`Finalise la version`** — tell the user, in French, to test functionally then say « Finalise la version ». Do not run `finaliser-la-version` from here.

## Not this skill

- Writing the file (that is `encadrer-implement` / `ouvrir-la-version`).
- Starting `/implement` in the same compacted window that just finished a ticket.
