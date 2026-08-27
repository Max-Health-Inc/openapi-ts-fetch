"""TypeScript api-class emission: one class per tag, one method per operation."""

from __future__ import annotations

from .naming import camel, pascal, safe_id
from .schema_registry import SchemaRegistry

# ─── API class generator ─────────────────────────────────────────────────────────


def _iface_name(oid: str, registry: SchemaRegistry) -> str:
    """Generate a unique request interface name that won't collide with model names."""
    candidate = pascal(oid) + "Request"
    if candidate in registry.models:
        return pascal(oid) + "OperationRequest"
    return candidate


def gen_api(tag: str, operations: list[dict], registry: SchemaRegistry, header: str) -> str:
    """Generate an API class file for a tag."""
    class_name = pascal(tag) + "Api"
    lines: list[str] = [header.rstrip(), "", ""]
    lines.append("import * as runtime from '../runtime';")

    all_refs: set[str] = set()
    for op in operations:
        all_refs |= op.get("_refs", set())

    if all_refs:
        lines.append("import type {")
        for ref in sorted(all_refs):
            lines.append(f"  {ref},")
        lines.append("} from '../models/index';")
        lines.append("import {")
        for ref in sorted(all_refs):
            lines.append(f"    {ref}FromJSON,")
            lines.append(f"    {ref}ToJSON,")
        lines.append("} from '../models/index';")

    lines.append("")

    # Request interfaces — use camelCase param names for TS convention
    for op in operations:
        params = op.get("params", [])
        if params:
            iface = _iface_name(op["id"], registry)
            lines.append(f"export interface {iface} {{")
            for p in params:
                opt = "" if p["required"] else "?"
                cn = camel(p["name"])
                lines.append(f"    {safe_id(cn)}{opt}: {p['ts']};")
            lines.append("}")
            lines.append("")

    # Class
    lines.append("/**")
    lines.append(" * ")
    lines.append(" */")
    lines.append(f"export class {class_name} extends runtime.BaseAPI {{")
    lines.append("")

    for op in operations:
        _gen_operation(lines, op, registry)

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _gen_operation(lines: list[str], op: dict, registry: SchemaRegistry):
    """Generate raw + convenience methods for one operation."""
    oid = op["id"]
    method = op["method"].upper()
    path = op["path"]
    summary = op.get("summary", "")
    desc = op.get("description", "")
    params = op.get("params", [])
    resp_type = op.get("resp_type", "void")
    resp_array = op.get("resp_array", False)
    resp_item = op.get("resp_item")

    has_params = bool(params)
    has_required_params = any(p["required"] for p in params)
    iface = _iface_name(oid, registry) if has_params else None

    # ── Raw method ──
    lines.append("    /**")
    if desc:
        lines.append(f"     * {desc}")
    if summary:
        lines.append(f"     * {summary}")
    lines.append("     */")
    if has_params:
        opt_mark = "" if has_required_params else "?"
        sig = f"requestParameters{opt_mark}: {iface}, "
    else:
        sig = ""
    lines.append(
        f"    async {oid}Raw({sig}initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<{resp_type}>> {{"
    )

    # Guard for optional requestParameters
    if has_params and not has_required_params:
        lines.append("        requestParameters = requestParameters || {};")
        lines.append("")

    for p in params:
        if p["required"]:
            cn = safe_id(camel(p["name"]))
            lines.append(f"        if (requestParameters['{cn}'] == null) {{")
            lines.append("            throw new runtime.RequiredError(")
            lines.append(f"                '{cn}',")
            lines.append(f"                'Required parameter \"{cn}\" was null or undefined when calling {oid}().'")
            lines.append("            );")
            lines.append("        }")
            lines.append("")

    lines.append("        const queryParameters: any = {};")
    for p in params:
        if p["in"] == "query":
            cn = safe_id(camel(p["name"]))
            lines.append(f"        if (requestParameters['{cn}'] != null) {{")
            lines.append(f"            queryParameters['{p['name']}'] = requestParameters['{cn}'];")
            lines.append("        }")
    lines.append("")

    lines.append("        const headerParameters: runtime.HTTPHeaders = {};")
    for p in params:
        if p["in"] == "header":
            cn = safe_id(camel(p["name"]))
            lines.append(f"        if (requestParameters['{cn}'] != null) {{")
            lines.append(f"            headerParameters['{p['name']}'] = String(requestParameters['{cn}']);")
            lines.append("        }")
    lines.append("")

    # Auth
    lines.append("        if (this.configuration && this.configuration.accessToken) {")
    lines.append("            const token = this.configuration.accessToken;")
    lines.append('            const tokenString = await token("BearerAuth", []);')
    lines.append("")
    lines.append("            if (tokenString) {")
    lines.append('                headerParameters["Authorization"] = `Bearer ${tokenString}`;')
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    lines.append(f"        let urlPath = `{path}`;")
    for p in params:
        if p["in"] == "path":
            cn = safe_id(camel(p["name"]))
            lines.append(
                f"        urlPath = urlPath.replace(`{{{p['name']}}}`, encodeURIComponent(String(requestParameters['{cn}'])));"
            )
    lines.append("")

    body_param = next((p for p in params if p["in"] == "body"), None)
    if body_param:
        lines.append("        headerParameters['Content-Type'] = 'application/json';")
        lines.append("")

    lines.append("        const response = await this.request({")
    lines.append("            path: urlPath,")
    lines.append(f"            method: '{method}',")
    lines.append("            headers: headerParameters,")
    lines.append("            query: queryParameters,")
    if body_param:
        bn = safe_id(camel(body_param["name"]))
        bt = body_param["ts"]
        if bt in registry.models:
            lines.append(f"            body: {bt}ToJSON(requestParameters['{bn}']),")
        else:
            lines.append(f"            body: requestParameters['{bn}'],")
    lines.append("        }, initOverrides);")
    lines.append("")

    if resp_type == "void":
        lines.append("        return new runtime.VoidApiResponse(response);")
    elif resp_array and resp_item and resp_item in registry.models:
        lines.append(
            f"        return new runtime.JSONApiResponse(response, (jsonValue) => jsonValue.map({resp_item}FromJSON));"
        )
    elif resp_type in registry.models:
        lines.append(
            f"        return new runtime.JSONApiResponse(response, (jsonValue) => {resp_type}FromJSON(jsonValue));"
        )
    else:
        lines.append(f"        return new runtime.JSONApiResponse<{resp_type}>(response);")

    lines.append("    }")
    lines.append("")

    # ── Convenience method ──
    lines.append("    /**")
    if desc:
        lines.append(f"     * {desc}")
    if summary:
        lines.append(f"     * {summary}")
    lines.append("     */")
    if has_params:
        opt_mark = "" if has_required_params else "?"
        lines.append(
            f"    async {oid}(requestParameters{opt_mark}: {iface}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<{resp_type}> {{"
        )
        lines.append(f"        const response = await this.{oid}Raw(requestParameters, initOverrides);")
    else:
        lines.append(
            f"    async {oid}(initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<{resp_type}> {{"
        )
        lines.append(f"        const response = await this.{oid}Raw(initOverrides);")
    lines.append("        return await response.value();")
    lines.append("    }")
    lines.append("")
