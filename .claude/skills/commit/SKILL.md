---
name: commit
description: >-
  Commit the current branch (HEAD vs working tree) using message-de-commit
  `/mc -d` block 3. Use when the user types `/c`, or after this skill asked
  « Êtes-vous sûr » for a force-push and they reply oui or non. `-a` stages
  the whole working tree; `-p` pushes; `-p -f` force-with-lease only after
  oui on the next turn. Not `/mc` (message only). Not on main except
  `/init` / « Initialise le repo ».
---

# Commit the current branch

`/c` **is** permission to `git commit` on the **current** branch. `/c -p` **is** permission to `git push`. `/c -p -f` **is** permission to `git push --force-with-lease` **only** after **oui** on the following turn. Never `.env`, `*.db`, `.venv/`, secrets. Do not switch branch.

`/` = this skill’s trigger. `-` = options. Treat `/c`, `-a`, `-p`, `-f` as whole tokens. Order of options does not matter.

## Follow-up (force-push pending)

If the previous turn of **this** skill asked « Êtes-vous sûr » for a force-push:

- The reply contains the whole word **oui** (any case) → `git push --force-with-lease` to the existing upstream (or `origin HEAD` if you must set upstream). Still refuse `main` / `master`. Then stop.
- Anything else → no push. Say the force-push is cancelled. Stop.

Do not commit again on this turn.

## 1. Guards

1. `git branch --show-current` is `main` or `master` → stop, **except** when the current user message is **`/init`** or **« Initialise le repo »** (that skill is the only allowed commit on `main`). Still refuse force-push to `main` / `master`.
2. `-f` without `-p` → stop. Say `-f` only exists as `/c -p -f`.
3. Without `-a`: if the index is empty (`git diff --cached --quiet`) → stop. Say to stage files or pass `-a`.
4. Always unstage secrets (`.env`, `*.db`, `.venv/`, credential files) before committing, even if the user had staged them.

## 2. Message

Run skill **`message-de-commit`** as if the user had typed **`/mc -d`**. Use **block 3** (subject, blank line, body) as the commit message. Do not wait for a tweak. Do not print the three blocks.

If that skill says there is nothing to commit: stop.

## 3. Stage

- Without `-a`: leave the index as it is (after the secret unstage).
- With `-a`: `git add` the rest of the working tree (tracked modifications and untracked files), still excluding secrets.

## 4. Commit

```bash
git commit -m "$(cat <<'EOF'
<block 3>
EOF
)"
```

Done when `git status` shows the commit on HEAD. Reply with the short SHA and the subject.

## 5. Push

- No `-p`: stop after the commit.
- `-p` without `-f`: `git push` the current branch (`-u origin HEAD` if it has no upstream). No force. Then stop.
- `-p` with `-f`: **do not push**. Ask in French: **Êtes-vous sûr ?** Then one short paragraph of what will run: `git push --force-with-lease` to `origin/<current-branch>`, which rewrites remote history. Tell them to reply **oui** to proceed. Wait.

## Not this skill

- Propose a message without committing: skill `message-de-commit` (`/mc`).
- Ticket wrap (next child / Finalise): skill `encadrer-implement`.
