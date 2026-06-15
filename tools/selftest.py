#!/usr/bin/env python3
"""Offline self-checks for the executable core. No network. Used by CI.

Exits non-zero on the first failed assertion.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_lib as lib  # noqa: E402
import gen_baseline  # noqa: E402

_n = 0


def check(name, cond):
    global _n
    _n += 1
    if not cond:
        print(f"FAIL: {name}")
        sys.exit(1)
    print(f"ok: {name}")


# --- schema validation ---
S = {"type": "object", "required": ["id", "status"],
     "properties": {"id": {"type": "number"},
                    "status": {"type": "string", "enum": ["a", "b"]}}}
check("schema conforms", lib.validate_schema({"id": 1, "status": "a"}, S) == [])
check("schema catches missing required", any("missing required" in e for e in lib.validate_schema({"id": 1}, S)))
check("schema catches bad enum", any("not in enum" in e for e in lib.validate_schema({"id": 1, "status": "z"}, S)))
check("schema catches bad type", any("expected type" in e for e in lib.validate_schema({"id": "x", "status": "a"}, S)))
check("schema allows int for number", lib.validate_schema({"id": 5, "status": "a"}, S) == [])

# --- secret detection & redaction ---
check("detects secret keys", set(lib.secret_keys_present({"password": "p", "token": "t", "ok": 1})) == {"password", "token"})
check("detects nested secret", "u.apiKey" in lib.secret_keys_present({"u": {"apiKey": "x"}}))
check("redacts password value", '"password":"<redacted>"' in lib.redact_text('{"password":"hunter2"}'))
check("redacts jwt", "<redacted-token>" in lib.redact_text("eyJabcdefg.payload.sig here"))
check("redacts auth header", lib.redact_headers({"Authorization": "Bearer x"})["Authorization"] == "<redacted>")
check("keeps safe header", lib.redact_headers({"Accept": "application/json"})["Accept"] == "application/json")

# --- openapi -> baseline ---
spec = {
    "openapi": "3.0.0", "info": {"version": "1.0"},
    "servers": [{"url": "https://x/v1"}],
    "components": {"schemas": {"P": {"type": "object", "required": ["id"],
                                     "properties": {"id": {"type": "integer"}}}},
                   "securitySchemes": {"b": {"type": "http", "scheme": "bearer"}}},
    "paths": {"/p/{id}": {"get": {"security": [{"b": []}],
                                  "responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/P"}}}}, "401": {}}}}},
}
bl = gen_baseline.build_baseline(spec, "svc", None)
ep = bl["endpoints"][0]
check("baseline base_url from servers", bl["base_url"] == "https://x/v1")
check("baseline resolves $ref schema", ep["schema"]["required"] == ["id"])
check("baseline detects bearer security", ep["auth"] == "bearer")
check("baseline captures error status", 401 in ep.get("error_statuses", []))

print(f"\nAll {_n} self-checks passed.")
