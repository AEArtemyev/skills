# Agent guidance

This repository contains reusable skills. Keep article workspaces and generated
outputs outside it.

## pdf-article-translation

The goal is to create a complete article translation project: original English
Markdown, a Russian translation, verified figures, reproducible extraction
records, a Russian README, and both compiled PDFs.

Work in the user's current directory by default and reuse the input PDF under
its existing name. Keep PDFs and intermediate extraction files out of Git.
The agent reconstructs and translates the article; scripts automate repeatable
operations. Read [SKILL.md](pdf-article-translation/SKILL.md) before changing
this workflow.

## Changes

- Keep agent instructions in SKILL.md and human usage instructions in README.md.
- Update scripts, templates, and documentation together when behavior changes.
- Prefer simple procedural code. Run relevant tests after code changes.
- Write concise documentation and preserve unrelated user changes.
- Commit only when requested, using Conventional Commits.
