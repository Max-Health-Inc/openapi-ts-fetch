"""TypeScript model emission: interfaces, enums, and the FromJSON/ToJSON converters."""

from __future__ import annotations

import json
import re

from .naming import camel, pascal, safe_id
from .schema_registry import SchemaRegistry, norm_type

# ─── Dependency tracking ─────────────────────────────────────────────────────────


def model_refs(ts_type: str, registry: SchemaRegistry, exclude: str = "") -> set[str]:
    """Find model names referenced in a TS type string."""
    refs: set[str] = set()
    # Match PascalCase names AND non-standard names (Body_*, api__* etc.)
    for word in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", ts_type):
        if word in registry.models and word != exclude and word != "Array":
            refs.add(word)
    return refs


# ─── Model file generator ────────────────────────────────────────────────────────


def gen_enum_model(name: str, schema: dict, header: str) -> str:
    """Generate a standalone enum model .ts file (string union type)."""
    values = schema.get("enum", [])
    lines: list[str] = [header.rstrip(), ""]

    # Type alias as string union
    if values:
        union = "\n  | ".join(f"'{v}'" for v in values)
        lines.append(f"export type {name} = ")
        lines.append(f"  | {union};")
    else:
        lines.append(f"export type {name} = string;")
    lines.append("")

    # instanceOf guard
    vals_arr = ", ".join(f"'{v}'" for v in values)
    lines.append(f"export function instanceOf{name}(value: any): value is {name} {{")
    lines.append(f"    return [{vals_arr}].includes(value);")
    lines.append("}")
    lines.append("")

    # FromJSON / ToJSON (identity for enums)
    lines.append(f"export function {name}FromJSON(json: any): {name} {{")
    lines.append(f"    return {name}FromJSONTyped(json, false);")
    lines.append("}")
    lines.append("")
    lines.append(f"export function {name}FromJSONTyped(json: any, ignoreDiscriminator: boolean): {name} {{")
    lines.append(f"    return json as {name};")
    lines.append("}")
    lines.append("")
    lines.append(f"export function {name}ToJSON(value?: {name} | null): any {{")
    lines.append("    return value as any;")
    lines.append("}")
    lines.append("")
    lines.append(
        f"export function {name}ToJSONTyped(value?: {name} | null, ignoreDiscriminator: boolean = false): any {{"
    )
    lines.append("    return value as any;")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def gen_model(name: str, schema: dict, registry: SchemaRegistry, header: str) -> str:
    """Generate a complete model .ts file."""
    lines: list[str] = [header.rstrip(), ""]

    props = schema.get("properties", {})
    required_names = list(dict.fromkeys(schema.get("required", [])))
    required = set(required_names)

    # Resolve property types
    prop_types: dict[str, str] = {}
    for pname, pschema in props.items():
        child_ctx = name + pascal(pname)
        prop_types[pname] = registry.ts_type(pschema, child_ctx)

    # Collect model imports
    imports: set[str] = set()
    for ts in prop_types.values():
        imports |= model_refs(ts, registry, name)

    # Write imports
    lines.append("import { mapValues } from '../runtime';")
    for imp in sorted(imports):
        lines.append(f"import type {{ {imp} }} from './{imp}';")
        lines.append("import {")
        lines.append(f"    {imp}FromJSON,")
        lines.append(f"    {imp}FromJSONTyped,")
        lines.append(f"    {imp}ToJSON,")
        lines.append(f"    {imp}ToJSONTyped,")
        lines.append(f"}} from './{imp}';")
    lines.append("")

    # Pre-compute enum type names for properties that have enum values
    enum_type_map: dict[str, str] = {}
    for pname, pschema in props.items():
        if "enum" in pschema:
            enum_type_map[pname] = f"{name}{pascal(pname)}Enum"

    # Build camelCase property name mapping: original -> camel
    camel_names: dict[str, str] = {}
    for pname in props:
        camel_names[pname] = camel(pname)

    # Interface — use camelCase property names (matches Java generator convention)
    lines.append("/**")
    if schema.get("description"):
        lines.append(f" * {schema['description']}")
    lines.append(" * @export")
    lines.append(f" * @interface {name}")
    lines.append(" */")
    lines.append(f"export interface {name} {{")
    for pname, pschema in props.items():
        desc = pschema.get("description", "")
        opt = "?" if pname not in required else ""
        # Use enum type if enum values are declared, otherwise use resolved TS type
        ts = enum_type_map.get(pname, prop_types[pname])
        cn = camel_names[pname]
        lines.append("    /**")
        if desc:
            lines.append(f"     * {desc}")
        lines.append(f"     * @type {{{ts}}}")
        lines.append(f"     * @memberof {name}")
        lines.append("     */")
        lines.append(f"    {safe_id(cn)}{opt}: {ts};")
    lines.append("}")
    lines.append("")

    # Enum constants for enum properties
    for pname, pschema in props.items():
        if "enum" in pschema:
            enum_name = f"{name}{pascal(pname)}Enum"
            lines.append("/**")
            lines.append(" * @export")
            lines.append(" */")
            lines.append(f"export const {enum_name} = {{")
            for val in pschema["enum"]:
                key = safe_id(pascal(str(val)))
                lines.append(f"    {key}: '{val}'," if isinstance(val, str) else f"    {key}: {json.dumps(val)},")
            lines.append("} as const;")
            lines.append(f"export type {enum_name} = typeof {enum_name}[keyof typeof {enum_name}];")
            lines.append("")

    # instanceOf — check camelCase property names
    lines.append("/**")
    lines.append(f" * Check if a given object implements the {name} interface.")
    lines.append(" */")
    lines.append(f"export function instanceOf{name}(value: object): value is {name} {{")
    for p in required_names:
        cn = camel_names.get(p, p)
        lines.append(f"    if (!('{cn}' in value) || value['{cn}'] === undefined) return false;")
    lines.append("    return true;")
    lines.append("}")
    lines.append("")

    # FromJSON — read json['original_name'], assign to camelCase key
    lines.append(f"export function {name}FromJSON(json: any): {name} {{")
    lines.append(f"    return {name}FromJSONTyped(json, false);")
    lines.append("}")
    lines.append("")
    lines.append(f"export function {name}FromJSONTyped(json: any, ignoreDiscriminator: boolean): {name} {{")
    lines.append("    if (json == null) {")
    lines.append("        return json;")
    lines.append("    }")
    lines.append("    return {")
    lines.append("        ")
    for pname, pschema in props.items():
        cn = safe_id(camel_names[pname])
        is_required = pname in required
        lines.append(f"        '{cn}': {_from_json(pname, pschema, prop_types[pname], registry, name, is_required)},")
    lines.append("    };")
    lines.append("}")
    lines.append("")

    # ToJSON — read value['camelCaseName'], output to 'original_name' key
    lines.append(f"export function {name}ToJSON(json: any): {name} {{")
    lines.append(f"    return {name}ToJSONTyped(json, false);")
    lines.append("}")
    lines.append("")
    lines.append(
        f"export function {name}ToJSONTyped(value?: {name} | null, ignoreDiscriminator: boolean = false): any {{"
    )
    lines.append("    if (value == null) {")
    lines.append("        return value;")
    lines.append("    }")
    lines.append("")
    lines.append("    return {")
    lines.append("        ")
    for pname, pschema in props.items():
        cn = safe_id(camel_names[pname])
        lines.append(f"        '{pname}': {_to_json(pname, pschema, prop_types[pname], registry, name, cn)},")
    lines.append("    };")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def _resolve_model_type(schema: dict, ts_type: str, registry: SchemaRegistry) -> str | None:
    """Find the model name for a schema, if it resolves to one."""
    if "$ref" in schema:
        name, _ = registry.resolve_ref(schema["$ref"])
        return name
    clean = ts_type.replace(" | null", "").strip()
    if clean in registry.models:
        return clean
    return None


def _from_json(
    pname: str, schema: dict, ts_type: str, registry: SchemaRegistry, parent: str, is_required: bool = False
) -> str:
    """Generate FromJSON expression for a property.

    For required properties, don't wrap in null-check (avoids 'undefined is not assignable' errors).
    For optional properties, return undefined if the JSON value is null/missing.
    """
    model = _resolve_model_type(schema, ts_type, registry)
    if model:
        if is_required:
            return f"{model}FromJSON(json['{pname}'])"
        return f"json['{pname}'] == null ? undefined : {model}FromJSON(json['{pname}'])"

    stype, _ = norm_type(schema)
    if stype == "array":
        items = schema.get("items", {})
        item_model = _resolve_model_type(items, "", registry)
        if not item_model:
            # Check by canonical form
            itype, _ = norm_type(items) if isinstance(items, dict) else (None, False)
            if isinstance(items, dict) and itype == "object" and items.get("properties"):
                canon = registry._canonical(items)
                item_model = registry._canon_map.get(canon)
        if item_model:
            if is_required:
                return f"((json['{pname}'] as Array<any>).map({item_model}FromJSON))"
            return f"json['{pname}'] == null ? undefined : ((json['{pname}'] as Array<any>).map({item_model}FromJSON))"

    if is_required:
        return f"json['{pname}']"
    return f"json['{pname}'] == null ? undefined : json['{pname}']"


def _to_json(
    pname: str, schema: dict, ts_type: str, registry: SchemaRegistry, parent: str, camel_name: str = ""
) -> str:
    """Generate ToJSON expression for a property.

    Reads from value['camelCaseName'] and outputs to 'original_name'.
    """
    cn = camel_name or safe_id(pname)
    model = _resolve_model_type(schema, ts_type, registry)
    if model:
        return f"{model}ToJSON(value['{cn}'])"

    stype, _ = norm_type(schema)
    if stype == "array":
        items = schema.get("items", {})
        item_model = _resolve_model_type(items, "", registry)
        if not item_model:
            itype, _ = norm_type(items) if isinstance(items, dict) else (None, False)
            if isinstance(items, dict) and itype == "object" and items.get("properties"):
                canon = registry._canonical(items)
                item_model = registry._canon_map.get(canon)
        if item_model:
            return f"value['{cn}'] == null ? undefined : ((value['{cn}'] as Array<any>).map({item_model}ToJSON))"

    return f"value['{cn}']"
