"""Inline-schema extraction into named models, with dedup and 3.1 type normalization."""

from __future__ import annotations

import json
from typing import Any

from .naming import pascal

# ─── OpenAPI 3.1 type normalization ──────────────────────────────────────────────


def norm_type(schema: dict) -> tuple[str | None, bool]:
    """Normalize OpenAPI 3.1 type arrays like ["array", "null"]. Returns (type_str, nullable)."""
    raw = schema.get("type")
    if isinstance(raw, list):
        non_null = [t for t in raw if t != "null"]
        nullable = len(non_null) < len(raw)
        return (non_null[0] if non_null else "null"), nullable
    return raw, schema.get("nullable", False) or raw == "null"


# ─── Schema registry with dedup & nested extraction ─────────────────────────────


class SchemaRegistry:
    """
    Extracts inline schemas into named models with deduplication.

    Same-titled schemas with identical structure share a single model name.
    Nested object properties and array items are recursively extracted.
    """

    def __init__(self, spec: dict):
        self.spec = spec
        self.models: dict[str, dict] = {}  # name -> schema
        self._canon_map: dict[str, str] = {}  # canonical_hash -> name (dedup)
        self._used_names: set[str] = set()
        self._extracting: set[int] = set()  # cycle guard (schema id)

        # Pre-populate from components/schemas
        for name, schema in (spec.get("components", {}).get("schemas", {}) or {}).items():
            self._register_direct(name, schema)

    def _canonical(self, schema: dict) -> str:
        """Compute a canonical form of a schema for deduplication (ignores metadata).

        If the schema has an explicit 'title', it is preserved in the canonical
        form so that semantically distinct schemas with identical structure but
        different titles are never collapsed together.
        """
        # Metadata keys that are purely cosmetic (safe to strip for dedup)
        _cosmetic = ("description", "example", "examples", "default", "x-examples", "externalDocs")

        def _strip(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _strip(v) for k, v in sorted(obj.items()) if k not in _cosmetic}
            if isinstance(obj, list):
                return [_strip(x) for x in obj]
            return obj

        return json.dumps(_strip(schema), sort_keys=True, separators=(",", ":"))

    def _unique_name(self, base: str) -> str:
        if base not in self._used_names:
            self._used_names.add(base)
            return base
        n = 1
        while f"{base}{n}" in self._used_names:
            n += 1
        name = f"{base}{n}"
        self._used_names.add(name)
        return name

    def resolve_ref(self, ref: str) -> tuple[str, dict]:
        parts = ref.lstrip("#/").split("/")
        obj = self.spec
        for part in parts:
            obj = obj[part]
        return parts[-1], obj

    def _register_direct(self, name: str, schema: dict) -> str:
        """Register with the given name, no title override. Used for components.

        Unlike inline schemas, named component schemas are ALWAYS registered
        under their declared name — even if another component has an identical
        structure.  Dedup is only recorded when no prior mapping exists so that
        later *inline* schemas can still be collapsed into a component.
        """
        canon = self._canonical(schema)
        name = self._unique_name(name)
        self.models[name] = schema
        # Only seed the dedup map if no entry yet — never skip a named component
        if canon not in self._canon_map:
            self._canon_map[canon] = name
        self._extract_nested(name, schema)
        return name

    def register_schema(self, schema: dict, context_name: str) -> str:
        """
        Register an inline object schema and return its assigned name.
        Uses 'title' if available, otherwise uses context_name.
        Content-hash dedup ensures identical schemas share a name.
        """
        if not schema or not isinstance(schema, dict):
            return context_name

        # Compute canonical form for dedup
        canon = self._canonical(schema)
        if canon in self._canon_map:
            return self._canon_map[canon]

        # Determine name: title takes priority
        title = schema.get("title")
        if title and isinstance(title, str):
            name = pascal(title)
        else:
            name = context_name

        name = self._unique_name(name)
        self.models[name] = schema
        self._canon_map[canon] = name

        # Recursively extract nested schemas
        self._extract_nested(name, schema)
        return name

    def _extract_nested(self, parent_name: str, schema: dict):
        """Recursively extract nested object/array schemas from properties."""
        sid = id(schema)
        if sid in self._extracting:
            return  # cycle guard
        self._extracting.add(sid)

        try:
            props = schema.get("properties", {})
            if not isinstance(props, dict):
                return

            for pname, pschema in props.items():
                if not isinstance(pschema, dict):
                    continue

                child_name = parent_name + pascal(pname)

                ptype, _ = norm_type(pschema)

                # Object property with properties → extract as separate model
                if ptype == "object" and pschema.get("properties"):
                    self.register_schema(pschema, child_name)

                # Array property with object items → extract with "Inner" suffix
                elif ptype == "array":
                    items = pschema.get("items", {})
                    item_type, _ = norm_type(items) if isinstance(items, dict) else (None, False)
                    if isinstance(items, dict) and item_type == "object" and items.get("properties"):
                        self.register_schema(items, child_name + "Inner")

                # anyOf/oneOf with embedded objects
                for keyword in ("anyOf", "oneOf"):
                    if keyword in pschema and isinstance(pschema[keyword], list):
                        for variant in pschema[keyword]:
                            if (
                                isinstance(variant, dict)
                                and variant.get("type") == "object"
                                and variant.get("properties")
                            ):
                                self.register_schema(variant, child_name)
        finally:
            self._extracting.discard(sid)

    def ts_type(self, schema: dict | None, context_name: str = "") -> str:
        """
        Convert an OpenAPI schema to a TypeScript type string.
        Extracts inline object schemas as named models.
        """
        if schema is None:
            return "any"

        # $ref
        if "$ref" in schema:
            name, _ = self.resolve_ref(schema["$ref"])
            return name

        # allOf
        if "allOf" in schema:
            types = [self.ts_type(s, context_name) for s in schema["allOf"]]
            return " & ".join(types) if types else "any"

        # oneOf / anyOf (handle nullable unions)
        for keyword in ("oneOf", "anyOf"):
            if keyword in schema:
                variants = schema[keyword]
                non_null = [v for v in variants if v.get("type") != "null"]
                has_null = len(non_null) < len(variants) or schema.get("nullable")
                types = [self.ts_type(v, context_name) for v in non_null]
                ts = " | ".join(types) if types else "any"
                if has_null:
                    ts += " | null"
                return ts

        schema_type, nullable = norm_type(schema)

        # Enum values
        if "enum" in schema:
            ts = "string"
            return f"{ts} | null" if nullable else ts

        # Object with properties → register as named model
        if schema_type == "object" and schema.get("properties"):
            name = self.register_schema(schema, context_name)
            return f"{name} | null" if nullable else name

        # Array
        if schema_type == "array":
            items = schema.get("items", {})
            item_ctx = context_name + "Inner" if context_name else "Item"
            item_type = self.ts_type(items, item_ctx)
            ts = f"Array<{item_type}>"
            return f"{ts} | null" if nullable else ts

        # Object without properties (generic/map)
        if schema_type == "object":
            if "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
                val = self.ts_type(schema["additionalProperties"], context_name + "Value")
                ts = f"{{ [key: string]: {val} }}"
            else:
                ts = "object"
            return f"{ts} | null" if nullable else ts

        # Primitives
        type_map = {
            "string": "string",
            "integer": "number",
            "number": "number",
            "boolean": "boolean",
            "null": "null",
        }
        if schema_type in type_map:
            ts = type_map[schema_type]
            return f"{ts} | null" if nullable else ts

        return "any"

    def response_schema(
        self, responses: dict, status_codes: tuple = ("200", "201", "202", "204")
    ) -> tuple[str | None, dict | None]:
        """Returns (status_code, schema) for the first matching JSON response."""
        for code in status_codes:
            resp = responses.get(code, {})
            content = resp.get("content", {})
            for mt in ("application/json", "*/*"):
                if mt in content:
                    return code, content[mt].get("schema")
        return None, None

    def request_schema(self, body: dict | None) -> dict | None:
        if not body:
            return None
        content = body.get("content", {})
        for mt in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded"):
            if mt in content:
                return content[mt].get("schema")
        return None
