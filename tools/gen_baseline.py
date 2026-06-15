#!/usr/bin/env python3
"""Generate a contract baseline from an OpenAPI 3.x spec.

The baseline is a COMPARISON REFERENCE (expected shapes + status map), never a
verdict — see the harness principle in SKILL.md. It feeds run_contract.py.

Usage:
  python3 tools/gen_baseline.py <openapi.json|url> --service <name> \\
      [--base-url <url>] [--out contracts/<service>/baseline.json]

Supports JSON specs (stdlib only). For YAML specs, convert to JSON first.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_lib as lib  # noqa: E402


def _resolve_ref(ref: str, root: dict):
    """Resolve a local #/components/... $ref."""
    if not ref.startswith("#/"):
        return {}
    node = root
    for part in ref[2:].split("/"):
        node = node.get(part, {})
    return node


def _schema_from_openapi(schema: dict, root: dict, _depth=0) -> dict:
    """Reduce an OpenAPI schema to the subset our validator understands."""
    if _depth > 6 or not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)
    out: dict = {}
    if "type" in schema:
        out["type"] = schema["type"]
    if "enum" in schema:
        out["enum"] = schema["enum"]
    if schema.get("type") == "object" or "properties" in schema:
        out["type"] = "object"
        if schema.get("required"):
            out["required"] = list(schema["required"])
        props = {}
        for k, v in schema.get("properties", {}).items():
            props[k] = _schema_from_openapi(v, root, _depth + 1)
        if props:
            out["properties"] = props
    if schema.get("type") == "array" and "items" in schema:
        out["type"] = "array"
        out["items"] = _schema_from_openapi(schema["items"], root, _depth + 1)
    return out


def _success_status(responses: dict) -> int:
    for code in responses:
        if str(code).startswith("2"):
            return int(code)
    return 200


def _success_schema(responses: dict, root: dict) -> dict:
    for code, resp in responses.items():
        if not str(code).startswith("2"):
            continue
        content = (resp or {}).get("content", {})
        for ct, media in content.items():
            if "json" in ct and "schema" in media:
                return _schema_from_openapi(media["schema"], root)
    return {}


def build_baseline(spec: dict, service: str, base_url: str | None) -> dict:
    servers = spec.get("servers") or []
    inferred = servers[0]["url"] if servers else None
    endpoints = []
    for path, methods in spec.get("paths", {}).items():
        for method, op in (methods or {}).items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            responses = op.get("responses", {})
            secured = bool(op.get("security") or spec.get("security"))
            ep = {
                "method": method.upper(),
                "path": path,
                "auth": "bearer" if secured else "none",
                "success_status": _success_status(responses),
            }
            schema = _success_schema(responses, spec)
            if schema:
                ep["schema"] = schema
            # surface declared error statuses as part of the status contract
            err = [int(c) for c in responses if str(c)[0] in "45" and str(c).isdigit()]
            if err:
                ep["error_statuses"] = sorted(err)
            endpoints.append(ep)
    return {
        "service": service,
        "base_url": base_url or inferred or "<set base_url>",
        "version": spec.get("info", {}).get("version", "n/a"),
        "generated_from": "openapi",
        "endpoints": endpoints,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate a contract baseline from OpenAPI.")
    p.add_argument("spec", help="path or URL to an OpenAPI 3.x JSON spec")
    p.add_argument("--service", required=True)
    p.add_argument("--base-url", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    if args.spec.startswith(("http://", "https://")):
        spec = lib.request("GET", args.spec).json()
        if spec is None:
            print("ERROR: spec URL did not return JSON (convert YAML to JSON first)", file=sys.stderr)
            return 2
    else:
        spec = lib.load_json(args.spec)

    baseline = build_baseline(spec, args.service, args.base_url)
    out = args.out or f"contracts/{args.service}/baseline.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {out} — {len(baseline['endpoints'])} endpoint(s).")
    print("Review it before running: it is a comparison reference, not a verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
