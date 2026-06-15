# Contract Dimensions — Expanded Checklist

Use this as the per-endpoint checklist. Label each check `pass` / `drift` / `break`.

> `drift` = the contract changed in a way that may still work but no longer matches the agreement.
> `break` = the contract is violated in a way that harms a user, the business, or an integration.

## 1. Schema conformance

- All required fields present.
- Field types match (string vs number vs bool vs object/array).
- No unexpected `null` on non-nullable fields.
- No removed or renamed fields vs baseline (**break**).
- New fields are additive and optional (**additive**, not a break).
- Enum values within the agreed set.
- Nested objects and arrays match their declared shape.

## 2. Status & error contract

- `2xx` only on genuine success.
- `400` (or agreed code) on validation failure, with a structured error body.
- `401` on missing/expired auth; `403` on insufficient permission — and the two are not confused.
- `404` on a genuinely missing resource (not on a permission failure that should be `403`).
- Error bodies follow one consistent shape; no stack traces or internal details leaked.

## 3. AuthN / AuthZ (including IDOR / BOLA)

- Protected endpoint rejects a request with no token.
- Protected endpoint rejects an expired/invalid token.
- **Object-level authZ:** user A cannot `GET`/`PUT`/`DELETE` user B's object by changing an id in the path or body.
- **Tenant isolation:** tenant A cannot read tenant B's records.
- **Role boundary:** a low-privilege role gets `403` (not `200`) on a privileged route.
- Authorization is enforced server-side, not just hidden in the UI.

## 4. Idempotency & side effects

- A repeated `POST` with the same idempotency key applies once (no double order, no double charge).
- Retried requests after a timeout don't duplicate side effects.
- `PUT`/`DELETE` are idempotent by definition — confirm a repeat is safe.

## 5. Pagination & filtering

- `limit`/`offset` or cursor honored; over-asking is capped, not unbounded.
- `next`/`prev` links (or cursors) are consistent and terminate.
- Total counts match the data actually returned across pages.
- Filters narrow results correctly and don't leak filtered-out records.

## 6. Input boundaries

- Omitting a required field → graceful `400`, not `500`.
- Wrong type / malformed JSON → graceful rejection.
- Oversize payload → bounded rejection, no crash.
- Injection-shaped input (SQL/script-like) → rejected or safely escaped; no leak in the error text.
- Unicode / RTL / empty-string / boundary numbers handled.

## 7. Versioning / drift vs baseline

- Compare current responses to the saved baseline.
- Removed field, renamed field, narrowed type, or changed success status → **break**.
- Added optional field, new endpoint → **additive**.
- Record the diff in the run evidence.
