#!/usr/bin/env python3
"""Execute contract dimension checks against a baseline — fresh live calls only.

Implements the harness principle (SKILL.md): every result comes from a fresh
live call this run; the baseline is comparison input, never a verdict; a check
that cannot be driven live is reported BLOCKED, never faked from cache.

Dimensions covered automatically (others stay manual — reported as untested):
  D1 Schema conformance   — GET endpoints with a schema in the baseline
  D2 Status & error        — success status + JSON-shaped error body
  D3 AuthN                 — bearer endpoints reject calls with no token
  D3 Sensitive-data leak   — response body must not contain secret-looking keys
  D6 Input boundaries      — malformed JSON to a write endpoint must not 500

NOT automated (needs human scope): object-level authZ (IDOR/BOLA), idempotency,
pagination correctness. These are listed under "Not tested" so coverage is honest.

Usage:
  TOKEN=... python3 tools/run_contract.py contracts/<service>/baseline.json \\
      [--token-env TOKEN] [--base-url <override>] [--out-dir contracts/<svc>/runs/<ts>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_lib as lib  # noqa: E402

PASS, DRIFT, BREAK, BLOCKED = "pass", "drift", "break", "BLOCKED"


def _fill(path: str) -> str:
    """Replace {id}-style path params with a probe value so we can drive a call."""
    import re
    return re.sub(r"\{[^}]+\}", "1", path)


def check_endpoint(ep: dict, base: str, token: str | None) -> list[dict]:
    findings: list[dict] = []
    method = ep["method"]
    url = base.rstrip("/") + _fill(ep["path"])
    auth_h = {"Authorization": f"Bearer {token}"} if token else {}

    def record(dim, result, detail, evidence=None):
        findings.append({
            "endpoint": f"{method} {ep['path']}", "dimension": dim,
            "result": result, "detail": detail, "evidence": evidence,
        })

    # Only auto-drive safe, side-effect-free probes live. Writes are probed only
    # for the malformed-input boundary (servers should reject before mutating).
    if method == "GET":
        try:
            r = lib.request("GET", url, headers=auth_h)
        except lib.BlockedError as e:
            record("D2 status", BLOCKED, str(e))
            return findings

        # D2 — success status
        exp = ep.get("success_status", 200)
        record("D2 status", PASS if r.status == exp else DRIFT,
               f"expected {exp}, got {r.status}")

        # D1 — schema conformance
        if "schema" in ep and r.json() is not None:
            errs = lib.validate_schema(r.json(), ep["schema"])
            if errs:
                record("D1 schema", BREAK if any("missing required" in e or "expected type" in e for e in errs) else DRIFT,
                       "; ".join(errs[:4]),
                       _save_evidence(method, ep["path"], auth_h, r))
            else:
                record("D1 schema", PASS, "all required fields present & typed")

        # D3 — sensitive-data leak
        body = r.json()
        if body is not None:
            leaks = lib.secret_keys_present(body)
            if leaks:
                record("D3 sensitive-data", BREAK,
                       f"response exposes secret-looking field(s): {', '.join(leaks[:5])}",
                       _save_evidence(method, ep["path"], auth_h, r))

        # D3 — authN: bearer endpoint must reject no-token
        if ep.get("auth") == "bearer":
            try:
                r2 = lib.request("GET", url)  # no auth header
                ok = r2.status in (401, 403)
                record("D3 authN", PASS if ok else BREAK,
                       f"no-token call returned {r2.status} (expected 401/403)",
                       None if ok else _save_evidence("GET (no token)", ep["path"], {}, r2))
            except lib.BlockedError as e:
                record("D3 authN", BLOCKED, str(e))

    # D6 — input boundary: malformed JSON to a write endpoint must not 500
    if method in ("POST", "PUT", "PATCH"):
        try:
            r = lib.request(method, url, headers={**auth_h, "Content-Type": "application/json"},
                            body="{not valid json")
            if r.status >= 500:
                record("D6 input", BREAK, f"malformed JSON caused {r.status} (server error)",
                       _save_evidence(f"{method} (malformed)", ep["path"], auth_h, r))
            else:
                record("D6 input", PASS, f"malformed JSON rejected with {r.status}")
        except lib.BlockedError as e:
            record("D6 input", BLOCKED, str(e))

    return findings


_EVIDENCE_DIR = {"path": None}


def _save_evidence(label, path, headers, resp) -> str | None:
    d = _EVIDENCE_DIR["path"]
    if not d:
        return None
    safe = (label + path).replace("/", "_").replace(" ", "_").replace("{", "").replace("}", "")
    fname = f"{safe[:80]}.txt"
    with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
        f.write(f"{label} {path}\n")
        f.write(f"Request headers: {json.dumps(lib.redact_headers(headers))}\n")
        f.write(f"→ {resp.status}\n")
        f.write(lib.redact_text(resp.text[:1500]))
        f.write("\n")
    return f"{os.path.basename(d)}/{fname}"


def main(argv=None):
    p = argparse.ArgumentParser(description="Run contract dimension checks (fresh live calls).")
    p.add_argument("baseline")
    p.add_argument("--token-env", default="TOKEN", help="env var holding the bearer token")
    p.add_argument("--base-url", default=None)
    p.add_argument("--out-dir", default=None)
    args = p.parse_args(argv)

    baseline = lib.load_json(args.baseline)
    base = args.base_url or baseline["base_url"]
    if base.startswith("<"):
        print("ERROR: baseline has no real base_url; pass --base-url", file=sys.stderr)
        return 2
    token = lib.env(args.token_env)

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        _EVIDENCE_DIR["path"] = args.out_dir

    all_findings: list[dict] = []
    for ep in baseline["endpoints"]:
        all_findings.extend(check_endpoint(ep, base, token))

    # ---- verdict ----
    results = [f["result"] for f in all_findings]
    if BREAK in results:
        verdict = "breaking change found"
    elif DRIFT in results:
        verdict = "drift found"
    elif results and all(r in (PASS, BLOCKED) for r in results) and BLOCKED in results and PASS not in results:
        verdict = "BLOCKED"
    else:
        verdict = "clean" if results else "BLOCKED (nothing could be driven)"

    report = {
        "service": baseline["service"],
        "base_url": base,
        "verdict": verdict,
        "calls_run_live_this_run": True,
        "counts": {k: results.count(k) for k in (PASS, DRIFT, BREAK, BLOCKED)},
        "findings": all_findings,
        "not_tested": [
            "object-level authZ (IDOR/BOLA) — needs two accounts + owned object ids",
            "idempotency — needs a safe write + idempotency key",
            "pagination correctness — needs known counts/cursors",
        ],
    }
    if args.out_dir:
        with open(os.path.join(args.out_dir, "findings.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    # ---- print PM-readable summary ----
    print(f"\n=== Contract verdict: {verdict} — {baseline['service']} ===")
    print(f"counts: {report['counts']}")
    for f in all_findings:
        mark = {PASS: "🟢", DRIFT: "🟡", BREAK: "🔴", BLOCKED: "⚪"}[f["result"]]
        ev = f"  [{f['evidence']}]" if f["evidence"] else ""
        print(f"  {mark} {f['result']:<7} {f['endpoint']:<28} {f['dimension']:<18} {f['detail']}{ev}")
    print("\nNot auto-tested (run manually):")
    for n in report["not_tested"]:
        print(f"  - {n}")

    # exit non-zero on break so CI can gate
    return 1 if BREAK in results else 0


if __name__ == "__main__":
    raise SystemExit(main())
