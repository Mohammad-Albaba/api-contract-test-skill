# API Contract Test — Report

**Service / area:** <service>
**Environment:** <staging / test base URL>
**Contract source:** <OpenAPI url | JSON Schema | baseline | derived from traffic>
**Run timestamp:** <timestamp>
**Calls run live this run:** <yes / no — if no, the verdict is BLOCKED, not a result>
**Auth context(s) used:** <role/tenant — never the token>

## Verdict

> clean / drift found / breaking change found / BLOCKED

Use **BLOCKED** when a run could not complete (target unreachable, auth failed, scope denied) — never substitute a cached or prior-run result for a fresh one. One plain-language sentence on what this means for the product.

## Coverage

- Endpoints tested: <list>
- Dimensions tested: <schema / status / authZ / idempotency / pagination / input / versioning>
- **Not tested (and why):** <explicit list — mutation skipped, endpoints out of scope, etc.>

## Findings

| Endpoint | Dimension | Result | Business impact | Evidence ref |
|---|---|---|---|---|
| `GET /orders/{id}` | AuthZ (IDOR) | break | User can read another user's order | runs/<ts>/idor-orders.txt |
| `POST /payments` | Idempotency | drift | Retry may create a duplicate charge | runs/<ts>/payments-retry.txt |
| `GET /products` | Schema | pass | — | — |

## Top risk

The single most damaging finding, who it harms, and the fix or regression check that closes it.

## Next step

- [ ] File approved findings into the tracker
- [ ] Baseline updated
- [ ] Scope to widen: <...>
