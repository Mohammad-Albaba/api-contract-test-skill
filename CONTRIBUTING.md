# Contributing

Thanks for improving `api-contract-test`. This is a Markdown-defined, agent-agnostic skill — keep it portable and free of any dependency on a specific agent runtime.

## Ground rules

- **No secrets, ever.** Don't commit tokens, keys, or real request/response captures. CI fails on obvious secret patterns; `runs/` and `.env` are gitignored.
- **Stay agent-agnostic.** Don't hardcode one runtime's tool names into `SKILL.md`. Refer to "the host's HTTP/MCP request capability."
- **Plain-language impact.** Every finding example should state who is harmed in business terms, not just the technical diff.
- **Keep the frontmatter intact.** `SKILL.md` must start with YAML frontmatter containing `name: api-contract-test` and a `description:`.

## Local checks before a PR

```bash
# JSON valid
find . -name '*.json' -not -path './.git/*' -exec python3 -c "import json,sys;json.load(open(sys.argv[1]))" {} \;

# Markdown lint (optional)
npx markdownlint-cli2 "**/*.md"
```

CI runs the same validations on every push and PR.

## What's welcome

- More worked examples under `references/`
- Additional contract dimensions or edge cases in `references/contract-dimensions.md`
- Clearer wording in `SKILL.md`
