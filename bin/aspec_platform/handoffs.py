"""Typed subagent handoffs (DV-057, pulls P4-013 forward). Allowed-code reason: exact.

A subagent may declare the shape of what it is handed and what it hands back in
`agents/handoffs/<agent>.json` (installed to `.cursor/agents/handoffs/`), as
`{"version", "input": <schema>, "output": <schema>}`. The request API checks each subagent
span's `task` and `summary` against that schema and attaches the result as
`attributes.handoff`, so the inspector can show fields instead of prose. Text that is not
JSON, or does not match, is reported as such and the raw text stays the source of truth.

The validator covers the JSON Schema subset the shipped schemas use: type, required,
properties, additionalProperties (as a schema), items, enum, maxItems. Stdlib only.
"""
from __future__ import annotations

import glob
import json
import os
import re

SCHEMA_DIRS = (os.path.join(".cursor", "agents", "handoffs"), os.path.join("agents", "handoffs"))
FENCE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.S)
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def load_schemas(project) -> dict:
    """Schemas by agent name; the installed copy wins over the package copy."""
    out = {}
    for rel in SCHEMA_DIRS:
        for path in sorted(glob.glob(os.path.join(project or ".", rel, "*.json"))):
            name = os.path.splitext(os.path.basename(path))[0]
            if name in out:
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (OSError, ValueError):
                continue
            if isinstance(doc, dict) and (isinstance(doc.get("input"), dict) or isinstance(doc.get("output"), dict)):
                out[name] = doc
    return out


def extract_json(text):
    """The JSON object a handoff carries: the whole text, else the last fenced block. None if neither."""
    if not isinstance(text, str) or not text.strip():
        return None
    candidates = [text.strip()] + [m.strip() for m in reversed(FENCE.findall(text))]
    for c in candidates:
        if not c.startswith("{"):
            continue
        try:
            value = json.loads(c)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _type_ok(value, t) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    py = TYPES.get(t)
    return py is None or (isinstance(value, py) and not (py is not bool and isinstance(value, bool)))


def validate(value, schema, at="$") -> list:
    """Every mismatch as `<json path>: <reason>`; an empty list means the value matches."""
    if not isinstance(schema, dict):
        return []
    errors = []
    t = schema.get("type")
    if t and not _type_ok(value, t):
        return [f"{at}: expected {t}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{at}: not one of {', '.join(map(str, schema['enum']))}")
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in value:
                errors.append(f"{at}.{key}: required")
        extra = schema.get("additionalProperties")
        for key, v in value.items():
            if key in props:
                errors += validate(v, props[key], f"{at}.{key}")
            elif isinstance(extra, dict):
                errors += validate(v, extra, f"{at}.{key}")
    if isinstance(value, list):
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            errors.append(f"{at}: more than {schema['maxItems']} items")
        for i, item in enumerate(value):
            errors += validate(item, schema.get("items"), f"{at}[{i}]")
    return errors


def _side(text, schema):
    if not isinstance(schema, dict):
        return None
    value = extract_json(text)
    if value is None:
        return {"typed": False, "value": None, "errors": ["not JSON" if text else "empty"]}
    errors = validate(value, schema)
    return {"typed": not errors, "value": value, "errors": errors}


def annotate(spans, schemas) -> list:
    """Copies of `spans` with `attributes.handoff` on each subagent span that has a schema."""
    out = []
    for s in spans:
        schema = schemas.get(s.get("name")) if s.get("kind") == "subagent" else None
        if schema:
            a = dict(s.get("attributes") or {})
            a["handoff"] = {"agent": s["name"], "version": schema.get("version"),
                            "input": _side(a.get("task"), schema.get("input")),
                            "output": _side(a.get("summary"), schema.get("output"))}
            s = dict(s, attributes=a)
        out.append(s)
    return out
