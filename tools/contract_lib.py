"""Shared helpers for the api-contract-test executable core.

Pure Python stdlib — no pip install, runs anywhere (incl. CI).
Covers: live HTTP, lightweight JSON-Schema checking, secret redaction.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------- #
# Secret redaction
# --------------------------------------------------------------------------- #

# Header names whose values must never be written to evidence.
_SECRET_HEADERS = {"authorization", "idempotency-key", "x-api-key", "cookie", "set-cookie"}
# JSON keys whose values must be redacted even when they ARE the finding.
_SECRET_KEYS = re.compile(r"(pass(word)?|token|secret|api[-_]?key|authorization)", re.I)
# JWT-ish blobs that may appear inline.
_JWT = re.compile(r"eyJ[A-Za-z0-9_\-]{6}[A-Za-z0-9_\-.]+")


def redact_headers(headers: dict) -> dict:
    out = {}
    for k, v in headers.items():
        out[k] = "<redacted>" if k.lower() in _SECRET_HEADERS else v
    return out


def redact_text(text: str) -> str:
    """Redact obvious secret values from a free-text/body excerpt."""
    text = _JWT.sub("<redacted-token>", text)
    # redact "password":"value" style pairs (keep the key, drop the value)
    text = re.sub(
        r'("(?:[^"]*(?:pass(?:word)?|token|secret|api[-_]?key)[^"]*)"\s*:\s*)"[^"]*"',
        r'\1"<redacted>"',
        text,
        flags=re.I,
    )
    return text


def secret_keys_present(obj, _path="") -> list[str]:
    """Return dotted paths of any secret-looking keys found in a parsed body."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{_path}.{k}" if _path else k
            if _SECRET_KEYS.search(str(k)):
                found.append(p)
            found.extend(secret_keys_present(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(secret_keys_present(v, f"{_path}[{i}]"))
    return found


# --------------------------------------------------------------------------- #
# HTTP — every verdict comes from a fresh live call (harness principle)
# --------------------------------------------------------------------------- #


class Response:
    def __init__(self, status: int, headers: dict, body_bytes: bytes):
        self.status = status
        self.headers = headers
        self.body_bytes = body_bytes
        self.text = body_bytes.decode("utf-8", "replace")

    def json(self):
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            return None

    @property
    def is_json(self) -> bool:
        ct = self.headers.get("content-type", "")
        return "json" in ct.lower() or self.json() is not None


def request(method: str, url: str, headers: dict | None = None,
            body: dict | str | None = None, timeout: int = 20) -> Response:
    """Drive one fresh live HTTP request. Raises BlockedError on transport failure."""
    headers = dict(headers or {})
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
        else:
            data = body.encode()
    # Default UA: many APIs sit behind a WAF/CDN that 403s the bare urllib agent.
    headers.setdefault("User-Agent", "api-contract-test/1.0")
    headers.setdefault("Accept", "application/json")
    req = urllib.request.Request(url, data=data, method=method.upper())
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
    except urllib.error.HTTPError as e:
        # HTTP errors (4xx/5xx) ARE valid contract results, not transport failures.
        return Response(e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise BlockedError(f"transport failure calling {method} {url}: {e}") from e


class BlockedError(Exception):
    """Raised when a run cannot complete — caller must report BLOCKED, never fall back."""


# --------------------------------------------------------------------------- #
# Lightweight JSON-Schema conformance (subset: type, required, enum, properties)
# --------------------------------------------------------------------------- #

_TYPES = {
    "object": dict, "array": list, "string": str,
    "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
}


def validate_schema(value, schema: dict, _path="$") -> list[str]:
    """Return a list of human-readable conformance errors ([] == conforms)."""
    errs: list[str] = []
    t = schema.get("type")
    if t:
        py = _TYPES.get(t)
        # JSON has no int/float split; allow ints where number expected.
        if py and not isinstance(value, py):
            if not (t == "number" and isinstance(value, bool) is False and isinstance(value, (int, float))):
                errs.append(f"{_path}: expected type {t}, got {type(value).__name__}")
                return errs  # type wrong → deeper checks meaningless
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{_path}: value {value!r} not in enum {schema['enum']}")
    if t == "object" and isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errs.append(f"{_path}: missing required field '{req}'")
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                errs.extend(validate_schema(value[k], sub, f"{_path}.{k}"))
    if t == "array" and isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errs.extend(validate_schema(item, schema["items"], f"{_path}[{i}]"))
    return errs


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #


def env(name: str, required: bool = False) -> str | None:
    v = os.environ.get(name)
    if required and not v:
        raise BlockedError(f"required env var {name} is not set (secrets must come from env)")
    return v


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
