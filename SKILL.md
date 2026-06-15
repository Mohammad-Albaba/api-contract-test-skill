---
name: api-contract-test
description: Test an API layer directly as a contract — validate live responses against an OpenAPI/JSON Schema, check status codes, authentication and per-endpoint authorization (object-level authZ / IDOR / BOLA), idempotency, pagination, input boundaries, and versioning drift — independent of any UI. Use when asked to test an API, validate API contracts, check endpoint authorization, find schema drift, test idempotency or pagination, verify status codes, or quality-check a backend service before or alongside UI testing.
license: MIT
---

# API Contract Test

A workflow for testing an HTTP/JSON API layer **as a contract**, independent of any user interface. It verifies what the backend actually returns and enforces — not what a UI happens to render. Use it for web, mobile, and standalone API products.

A silent API break — a renamed field, a leaked record, a double charge — usually hurts trust, money, or integrations long before a human notices it in the UI. This workflow catches those at the source.

Explain findings in plain product language. The reader may be a PM or Quality Lead, not a backend engineer: say *what broke for the user or the business*, not only *which field changed*.

## When To Use

- "test the checkout API against its OpenAPI spec on staging"
- "validate the orders endpoints for schema drift"
- "check that role=user gets 403 on DELETE /admin/orders/{id}"
- "verify POST /payments is idempotent with a repeated idempotency-key"
- "test pagination and input limits on GET /products"
- "quality-check the backend contract before we ship"

Do **not** use it for load/performance testing or as a full penetration test. It is contract & behavior testing of the API surface.

## User Knowledge Assumption

Assume the reader may not be an API specialist.

Do:

- explain each check in one plain sentence before or while running it
- translate technical drift into business impact (who is harmed, what value is at risk)
- ask for required missing information before active testing
- suggest safe defaults when the user is unsure
- keep coverage explicit: which endpoints are tested, which are not, and why
- separate confirmed contract breaks from untested scope

Define any acronym the first time it appears: `schema drift` (the response no longer matches the agreed shape), `IDOR / BOLA` (one user can read or change another user's object), `idempotency` (calling the same write twice has the same effect as once).

## Operating Modes

Use the smallest mode that answers the request.

- `Spec check`: a spec (OpenAPI / Swagger / JSON Schema / Postman collection) exists — validate live responses against it and report drift. Default when a spec is available.
- `Endpoint path`: the user names specific endpoints or a feature (checkout, profile, admin approval) — test those across the contract dimensions below.
- `Discovery`: no spec and no named endpoints — derive the surface from a base URL, captured traffic, or docs; list what was found and state what still needs a spec or scope.
- `Regression retest`: a known contract or prior finding is given — verify only that contract unless new risk is obvious.

## Authorization & Scope Gate

Before any active API call, establish the boundary. Collect or infer:

- target environment / base URL — **must be staging or an authorized test environment; never run mutating calls against production**
- the spec source if any (OpenAPI/Swagger URL, JSON Schema, Postman collection), or "none"
- endpoints or feature under test
- allowed accounts, roles, tenants, and how to authenticate (token, header, login flow)
- whether mutating calls (POST/PUT/PATCH/DELETE) are permitted, and on which records
- forbidden actions: real payments, production writes, email/SMS floods, third-party live calls, destructive deletes

**Secrets handling:** read credentials from environment variables or a local untracked config (e.g. `.env`, a secrets manager) — never hardcode them into the repo, the spec, or saved evidence. Redact tokens and keys from every captured request/response.

If any required item is missing, pause before active checks and ask one focused question with a safe default.

## Control Plane

API requests are made over HTTP — no browser or device is required, which makes this workflow light and fast. **Every verdict must come from a fresh live call made this run** — captured pairs from prior runs are planning input only (they tell you what to expect and how to shape the call), never a substitute for re-driving the request. If a needed call cannot be driven live this run, report `BLOCKED` with the reason rather than falling back to a cached result. Prefer, in order:

1. The bundled executable core (`tools/run_contract.py`, stdlib-only) — generate a baseline with `tools/gen_baseline.py` from an OpenAPI spec, then run the auto-checkable dimensions repeatably. See `tools/README.md`.
2. A configured API/HTTP MCP server or HTTP client tool, if available in the runtime.
3. Direct authenticated HTTP requests via the runtime's request capability, using credentials resolved from env/secrets only.

Prior captured request/response pairs may seed expectations or replay setup, but the result you classify must be a fresh response from this run. Record the auth method used (role/tenant, not the secret) in the run evidence.

## Contract Dimensions

For each in-scope endpoint, evaluate the dimensions that apply and label each result `pass` / `drift` / `break`:

1. **Schema conformance** — response body matches the agreed schema: required fields present, types correct, no unexpected `null`, no removed/renamed fields, enums in range.
2. **Status & error contract** — correct status codes for success, validation error, auth failure, not-found; error bodies follow the agreed error shape.
3. **AuthN / AuthZ** — protected endpoints reject missing/expired tokens; **object-level authZ (IDOR/BOLA)**: a user cannot read or mutate another user's/tenant's object; role boundaries hold (e.g. `user` gets `403`, not `200`, on admin routes). API-tier authZ is often faster and more reliable to prove here than through a UI.
4. **Idempotency & side effects** — repeated writes with the same idempotency key do not double-apply (no double charge, no duplicate order).
5. **Pagination & filtering** — limits/offsets/cursors behave; no over-fetch; counts and `next` links are consistent.
6. **Input boundaries** — required-field omission, wrong types, oversize payloads, and injection-shaped input are rejected gracefully (no `500`, no leak in error text).
7. **Versioning / drift vs baseline** — capture the current response with a fresh live call this run, then diff it against the last saved contract baseline; flag breaking changes (removed field, narrowed type, changed status) vs additive ones. The saved baseline is the comparison reference, never the verdict — never diff two saved files and call it a result.

Scope to the smallest relevant set first; widen only if asked or if risk is obvious. If coverage is bounded (top-N endpoints, no mutation), state plainly what was not tested — silent truncation reads as full coverage when it is not.

## Evidence Rules

Every `drift` or `break` finding requires concrete evidence, not just a rationale:

- the request (method + path + relevant headers, **secrets redacted**) and the response (status + body excerpt)
- the expected-vs-actual diff (schema mismatch, wrong status, leaked object id)
- a one-line business impact in plain language
- the auth context used (role/tenant, not the token)

Keep raw request/response captures under a run folder and reference them from the report.

## Workflow

1. **Confirm scope & auth** via the gate above.
2. **Resolve the contract** — load the spec, or derive expected shape from a baseline / captured traffic; state which source was used.
3. **Run dimension checks** per endpoint, smallest scope first; capture evidence as you go.
4. **Classify** each result `pass` / `drift` / `break`; separate confirmed from untested.
5. **Report** in plain language: summary verdict, a table of endpoint × dimension × result, evidence references, and the single highest-risk break.
6. **Persist** — save the run and update the contract baseline so the next run can detect drift.
7. **File issues** — for each confirmed `break`/`drift` the user approves, file into the configured issue tracker with evidence and priority. If the user asked for report-only / dry-run, return findings and recommended priority without filing. If filing preference was unspecified, ask before creating issues.

## Report Shape

Return a PM-readable brief:

- **Verdict** — clean / drift found / breaking change found
- **Coverage** — endpoints and dimensions tested; what was not
- **Findings table** — endpoint | dimension | result | business impact | evidence ref
- **Top risk** — the single most damaging break and the fix or regression check that closes it
- **Next step** — file now / baseline updated / scope to widen

## Baseline & Memory

Save a contract baseline (the agreed schema + status map per endpoint) alongside the project so future runs compare against it and flag drift. A simple convention:

```
contracts/<service>/baseline.json     # expected shapes + status map
contracts/<service>/runs/<timestamp>/ # captured req/resp + findings
```

Treat a removed/renamed field or a narrowed type as **breaking**; an added optional field as **additive**.

The baseline is comparison input, never proof — a verdict always requires fresh live responses from this run. If a run cannot complete (target unreachable, auth fails, scope blocked), report `BLOCKED` with the reason; do not fall back to the baseline or a prior run as the answer.

## Boundaries

- Never write to production. Never run real payments, floods, or destructive deletes.
- Never store secrets in the repo or in saved evidence; read from env/secrets and redact.
- This is contract & behavior testing, not load/performance testing and not a full pentest.
- Prior run history plans the path; it is never the verdict. Always run fresh live calls, and report `BLOCKED` with the reason if a run cannot complete.

## References

- `references/contract-dimensions.md` — expanded checklist per dimension with example checks.
- `references/report-template.md` — the report skeleton to fill in.
- `references/example-run.md` — a full worked example against the sample baseline.
- `tools/` — the stdlib-only executable core: `gen_baseline.py` (OpenAPI → baseline), `run_contract.py` (run dimensions on fresh live calls), `selftest.py` (offline checks). See `tools/README.md`.
