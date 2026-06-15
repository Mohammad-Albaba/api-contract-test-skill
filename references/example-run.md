# Example Run — Orders API contract test

A worked example showing the workflow end to end against the sample baseline in
`contracts/example/baseline.json`. Values are illustrative.

---

## 1. Scope & auth (gate)

- **Environment:** `https://staging.example.com/api` (staging — mutating calls allowed on test records only)
- **Contract source:** `contracts/example/baseline.json`
- **In scope:** `GET /orders/{id}`, `POST /payments`, `GET /products`
- **Accounts:** `user_a` (owner of order `ord_100`), `user_b` (no relation), `admin`
- **Mutation:** `POST /payments` allowed against test order `ord_test`; no real charges
- **Secrets:** bearer tokens read from `$USER_A_TOKEN`, `$USER_B_TOKEN`, `$ADMIN_TOKEN` — redacted in evidence

## 2. Checks run

### `GET /orders/{id}` — Schema + AuthZ (IDOR)

- Schema: `user_a` fetches own `ord_100` → `200`, body matches schema → **pass**
- IDOR: `user_b` fetches `ord_100` (not theirs) → expected `403`, **got `200` with full order body** → **break**

> Plain-language impact: any logged-in user can read another customer's order — name, items, and total — by changing the id in the URL. This is a data-leak and a trust/compliance risk.

Evidence (redacted):

```text
GET /orders/ord_100
Authorization: Bearer <USER_B_TOKEN redacted>
→ 200 OK
{ "id":"ord_100","user_id":"user_a","status":"paid","total":420.00,"currency":"USD","items":[...] }
Expected: 403 Forbidden
```

### `POST /payments` — Idempotency

- First call with `Idempotency-Key: k-1` → `201`, `status: authorized`
- Repeat with same `Idempotency-Key: k-1` → expected the same single payment; **got a second `201` with a new `payment_id`** → **break**

> Plain-language impact: a client retry (flaky network, double tap) can charge the customer twice.

### `GET /products` — Schema + Pagination

- `limit=50` → `200`, 50 items, valid `next` cursor → **pass**
- `limit=99999` → capped at `max_limit: 100`, no over-fetch → **pass**

### `DELETE /admin/orders/{id}` — AuthZ (role boundary) → could not complete

- Goal: confirm `user` role gets `403`, only `admin` may delete.
- The `$ADMIN_TOKEN` returned `401 Invalid/Expired Token` on every call, so the admin-allowed baseline could not be established this run.
- **We do NOT fall back to a prior run's result.** With no fresh admin response, this check is **`BLOCKED`**, not pass/fail.

> Plain-language impact: we cannot yet say whether the admin delete boundary holds — the test could not be driven live. Re-run with a valid admin token to get a verdict.

## 3. Report

**Verdict:** breaking changes found (2); 1 check **BLOCKED**.
**Calls run live this run:** yes for the 3 completed checks; the admin-role check could not be driven (expired token) → BLOCKED.

| Endpoint | Dimension | Result | Business impact | Evidence ref |
|---|---|---|---|---|
| `GET /orders/{id}` | AuthZ (IDOR) | break | Any user reads another's order | runs/ts/idor-orders.txt |
| `POST /payments` | Idempotency | break | Retry can double-charge | runs/ts/payments-retry.txt |
| `GET /products` | Schema/Pagination | pass | — | — |
| `DELETE /admin/orders/{id}` | AuthZ (role) | BLOCKED | Admin boundary unverified — run could not complete | runs/ts/admin-delete-401.txt |

**Top risk:** the IDOR on `GET /orders/{id}` — it exposes other customers' data with no special tooling. Fix: enforce owner/admin object-level authorization server-side; add a regression check that `user_b` → `403` on `user_a`'s order.

**Next step:** file both breaks; add IDOR + idempotency checks to the regression baseline; re-run the BLOCKED admin-role check with a valid admin token — do not close it on the strength of any earlier run.
