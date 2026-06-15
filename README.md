# api-contract-test

A portable, agent-agnostic **skill** for testing an HTTP/JSON API layer *as a contract* — independent of any UI.

It validates live responses against an OpenAPI/JSON Schema, checks status codes, per-endpoint authorization (object-level authZ / IDOR / BOLA), idempotency, pagination, input boundaries, and versioning drift. The goal is to catch silent API breaks — a renamed field, a leaked record, a double charge — at the source, before they reach a user or a downstream integration.

## Why API-layer testing

Most automated quality work is UI-first. When a change breaks the API contract, the UI can hide the failure or surface it late. Testing the API directly:

- catches drift the UI masks,
- proves authorization boundaries faster and more reliably than clicking through screens,
- runs without a browser or device, so it's cheap and fast to repeat.

## What it checks

| Dimension | Question it answers |
|---|---|
| Schema conformance | Does the response match the agreed shape (fields, types, enums)? |
| Status & error contract | Right status codes and a consistent error body? |
| AuthN / AuthZ (incl. IDOR/BOLA) | Can a user reach data or actions they shouldn't? |
| Idempotency & side effects | Does a repeated write double-apply (double charge)? |
| Pagination & filtering | Do limits, cursors, and counts behave? |
| Input boundaries | Are bad/oversize/injection inputs rejected gracefully? |
| Versioning / drift | Did anything break vs the saved baseline? |

## Install

This is a Markdown-defined skill (`SKILL.md` with frontmatter). It works with any agent runtime that loads skills from a directory — point your runtime at this repo, or copy the folder into your skills directory.

**Claude Code / Codex (skills dir):**

```bash
git clone https://github.com/Mohammad-Albaba/api-contract-test-skill.git ~/.claude/skills/api-contract-test
# or for Codex:
git clone https://github.com/Mohammad-Albaba/api-contract-test-skill.git ~/.codex/skills/api-contract-test
```

The skill is self-contained and has **no dependency on any specific agent** — it uses whatever HTTP/MCP request capability the host runtime provides.

## Usage

Invoke it the way your runtime invokes skills, then describe the target in plain language:

- `test the checkout API against its OpenAPI spec on staging`
- `check that role=user gets 403 on DELETE /admin/orders/{id}`
- `verify POST /payments is idempotent with a repeated idempotency-key`

It will confirm scope and auth, run the relevant contract dimensions, and return a PM-readable report with a verdict, a findings table, evidence references, and the single highest-risk break.

## Safety

- Never runs mutating calls against production.
- Reads secrets from environment / local untracked config only — never from the repo or saved evidence; tokens are redacted in all captures.
- Contract & behavior testing only — not load testing, not a full pentest.

## Repo layout

```
SKILL.md                          # the skill definition (frontmatter + workflow)
references/
  contract-dimensions.md          # expanded per-dimension checklist
  report-template.md              # report skeleton
  example-run.md                  # full worked example
contracts/example/baseline.json   # example contract baseline
.github/workflows/ci.yml          # validation CI
CONTRIBUTING.md
```

## License

MIT — see [LICENSE](LICENSE).
