# Executable core

Pure-Python-stdlib helpers that turn the skill's manual checklist into a
repeatable run. No `pip install`. They implement the harness principle:
**every verdict comes from a fresh live call; the baseline is a comparison
reference, never a verdict; a check that can't run live is `BLOCKED`.**

## Files

- `contract_lib.py` — shared: live HTTP, lightweight JSON-Schema check, secret redaction.
- `gen_baseline.py` — build a baseline from an OpenAPI 3.x JSON spec.
- `run_contract.py` — drive the auto-checkable dimensions against a baseline.

## Generate a baseline from OpenAPI

```sh
python3 tools/gen_baseline.py path/to/openapi.json --service myapi
# or from a URL, with an explicit base:
python3 tools/gen_baseline.py https://api.example.com/openapi.json \
    --service myapi --base-url https://staging.example.com
```

Review the generated `contracts/myapi/baseline.json` before running — it is the
comparison reference, not the truth.

## Run the checks (fresh live calls)

```sh
export TOKEN="$MY_STAGING_BEARER"          # secrets from env only
python3 tools/run_contract.py contracts/myapi/baseline.json \
    --token-env TOKEN \
    --out-dir contracts/myapi/runs/$(date +%Y%m%dT%H%M%SZ)
```

Exit code is non-zero if any `break` is found, so CI can gate on it.

## What is automated vs. manual

Automated: schema conformance (D1), success/error status (D2), authN reject
(D3), sensitive-data leak (D3), malformed-input boundary (D6).

**Not** automated — these need human scope and are always printed under
"Not tested": object-level authZ (IDOR/BOLA), idempotency, pagination
correctness. Drive those manually per `references/contract-dimensions.md`.

## Self-check

`python3 tools/selftest.py` runs offline unit checks on the library (schema
validation, secret detection, redaction) — used by CI.
