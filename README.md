# Personal skills

A collection of agent skills. Each skill lives in its own directory with a
`SKILL.md` entry point and any supporting resources. The repository can be
stored in any local directory.

## Available skills

| Skill | Purpose |
| --- | --- |
| [pdf-article-translation](pdf-article-translation/README.md) | Reconstruct PDF articles as Markdown, translate into Russian, revise figure crops, and build PDFs. |

## Structure

```text
skills/
  README.md                     Repository overview and installation
  .gitignore                    Shared ignore rules
  pdf-article-translation/
    SKILL.md                    Instructions for the agent
    README.md                   Usage and dependencies for the human
    agents/openai.yaml          Codex UI metadata
    scripts/article.py          Repeatable operations
    tests/test_article.py       Behavior checks
```

Add future skills as sibling directories. Use `scripts/`, `tests/`,
`references/`, and `assets/` only when the skill needs them. Keep source
articles, translations, and generated PDFs outside this repository.

## Install in Codex

Run these commands from the repository root to expose the skill with a
symlink. The source path is derived from the current directory:

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/pdf-article-translation" \
  ~/.codex/skills/pdf-article-translation
```

If the destination already exists, inspect it before replacing it. After
installation, start a new agent session and invoke `$pdf-article-translation`.
Other agents have their own discovery locations; keep one source directory
per skill and link it into the locations used by those agents.

See each skill's README for its dependencies, examples, and validation commands.
