# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

`/code-review` **Standards** starts at role **`agent-adapter`**, which points here. Load this file, then roles **`glossary`** and **`adr`** from `agents/roles.yml`, instead of reporting “no conventions”. The Claude adapter (hook, `/implement` close) is not the Standards entry.

## Before exploring, read these

Resolve paths from **`agents/roles.yml`** (lookup/stop lives in that file):

- Role **`glossary`**: the terms file. If it is a map to several glossaries, read each one relevant to the topic.
- Role **`adr`**: ADRs that touch the area you're about to work in.

If either role is unresolved: **stop**. Do not proceed silently.

## File structure

This repo’s paths are only in `agents/roles.yml`.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the glossary. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-\<n\> (\<title\>), but worth reopening because…_
