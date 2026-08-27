"""Identifier and operation-id naming rules shared by the model and api emitters."""

from __future__ import annotations

import re

# ─── Naming helpers ──────────────────────────────────────────────────────────────


def pascal(name: str) -> str:
    """Convert a kebab/snake/camelCase string to PascalCase."""
    parts = re.split(r"[-_\s]", name)
    result_parts: list[str] = []
    for p in parts:
        sub = re.sub(r"([a-z])([A-Z])", r"\1_\2", p).split("_")
        for s in sub:
            if s:
                result_parts.append(s[0].upper() + s[1:])
    return "".join(result_parts)


def camel(name: str) -> str:
    """Convert to camelCase."""
    p = pascal(name)
    return p[0].lower() + p[1:] if p else ""


def safe_id(name: str) -> str:
    """Make a string safe as a TypeScript identifier."""
    name = re.sub(r"[^a-zA-Z0-9_$]", "_", name)
    if name and name[0:1].isdigit():
        name = "_" + name
    return name


def operation_id(method: str, path: str, op: dict) -> str:
    """Get or generate an operationId, always returning a valid camelCase identifier."""
    if "operationId" in op:
        # Spec-provided operationIds may contain hyphens, wildcards (*), etc.
        # Replace * with 'All' for wildcard routes, strip remaining non-identifier chars,
        # then camelCase for a valid TS method name.
        raw = op["operationId"].replace("*", "All")
        raw = re.sub(r"[^a-zA-Z0-9_-]", "", raw)
        return camel(raw)
    parts = path.strip("/").split("/")
    cleaned = []
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            cleaned.append("By" + pascal(part[1:-1]))
        else:
            cleaned.append(pascal(part))
    return camel(method + "".join(cleaned))
