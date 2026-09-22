---
name: message-de-commit
description: >-
  Propose a git commit subject from the uncommitted diff on the current
  branch. Use when the user says « trouve un message de commit », « message
  de commit », or `/mc`. Add a body only when the message also has `-d`
  (e.g. `/mc -d`). Do not commit.
---

# Propose a commit message

Look at **HEAD vs the working tree** on the current branch. Propose a message. Do **not** `git commit`.

`/` = this skill’s trigger. `-` = options. Treat `/mc` and `-d` as whole tokens (not substrings).

- **`/mc`** or a phrase like **« trouve un message de commit »** (also « comit », « commit message ») → this skill, **subject only**.
- **`-d`** also present (`/mc -d`, or the phrase plus `-d`) → subject **and** body.

Default without `-d`: subject only.

## 1. Diff

From the repo root:

1. `git status --short`
2. `git diff HEAD` (staged + unstaged vs last commit)
3. `git log -8 --format='%s'` — match this repo’s subject style

Include untracked files named by status (summarize them; don’t invent their contents if unread). If there is nothing to commit: say so and stop.

## 2. Write the message

French. The **subject** is one line, the **why** (not a file list). Same shape as recent `git log` subjects.

- Without `-d`: print only the subject, in a copy-pasteable fenced block.
- With `-d`: print **three** copy-pasteable fenced blocks, in this order:
  1. Subject only
  2. Body only
  3. Subject, then a blank line, then body (one block)

  Label them `1.`, `2.`, `3.`. Body is one or two sentences of why / context. Not a dump of `git diff --stat`.

Done when the user can copy the proposed text. Wait if they want a tweak. Still do not commit unless they explicitly ask in this turn.
