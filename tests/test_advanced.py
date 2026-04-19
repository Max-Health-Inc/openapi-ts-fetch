#!/usr/bin/env python3
"""
Advanced tests for the openapi-ts-fetch generator.

Exercises: allOf, oneOf, anyOf, nullable, additionalProperties, inline objects,
enums, header params, void responses, auto-generated operationIds, required vs
optional serialization, and error handling.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from generate import SchemaRegistry, generate, norm_type, operation_id

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
ADVANCED_SPEC = EXAMPLES_DIR / "advanced.json"


def _load_spec():
    return json.loads(ADVANCED_SPEC.read_text())


def _gen_advanced(tmpdir, **kwargs):
    return generate(str(ADVANCED_SPEC), tmpdir, **kwargs)


# ─── allOf composition ────────────────────────────────────────────────────────


class TestAllOf:
    """Employee uses allOf to extend PersonBase."""

    def test_allof_produces_intersection_type(self):
        spec = _load_spec()
        reg = SchemaRegistry(spec)
        ts = reg.ts_type(spec["components"]["schemas"]["Employee"], "Employee")
        assert "&" in ts, f"allOf should produce intersection type, got: {ts}"
        assert "PersonBase" in ts

    def test_allof_model_files_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, _ = _gen_advanced(tmpdir)
            assert "PersonBase" in models
            out = Path(tmpdir)
            assert (out / "models" / "PersonBase.ts").exists()


# ─── oneOf / anyOf unions ────────────────────────────────────────────────────


class TestUnions:
    """Department.head is oneOf, Department.budget is anyOf."""

    def test_oneof_produces_union(self):
        spec = _load_spec()
        reg = SchemaRegistry(spec)
        dept = spec["components"]["schemas"]["Department"]
        head_schema = dept["properties"]["head"]
        ts = reg.ts_type(head_schema, "DepartmentHead")
        assert "PersonBase" in ts
        assert "null" in ts, f"oneOf with null variant should be nullable, got: {ts}"

    def test_anyof_produces_union(self):
        spec = _load_spec()
        reg = SchemaRegistry(spec)
        dept = spec["components"]["schemas"]["Department"]
        budget_schema = dept["properties"]["budget"]
        ts = reg.ts_type(budget_schema, "DepartmentBudget")
        assert "number" in ts
        assert "string" in ts

    def test_department_model_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, _ = _gen_advanced(tmpdir)
            assert "Department" in models
            dept_ts = (Path(tmpdir) / "models" / "Department.ts").read_text()
            assert "export interface Department" in dept_ts


# ─── Nullable (OpenAPI 3.1 type arrays) ─────────────────────────────────────


class TestNullable:
    def test_31_type_array_nullable(self):
        """type: ["string", "null"] should normalize to (string, nullable=True)."""
        t, nullable = norm_type({"type": ["string", "null"]})
        assert t == "string"
        assert nullable is True

    def test_31_type_array_non_nullable(self):
        t, nullable = norm_type({"type": "string"})
        assert t == "string"
        assert nullable is False

    def test_nullable_property_in_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            # PersonBase.email is type: ["string", "null"]
            base_ts = (Path(tmpdir) / "models" / "PersonBase.ts").read_text()
            assert "string | null" in base_ts

    def test_nullable_in_create_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            req_ts = (Path(tmpdir) / "models" / "CreateEmployeeRequest.ts").read_text()
            # nickname is type: ["string", "null"]
            assert "string | null" in req_ts


# ─── additionalProperties (map types) ───────────────────────────────────────


class TestAdditionalProperties:
    def test_string_map(self):
        spec = _load_spec()
        reg = SchemaRegistry(spec)
        # Employee inline allOf[1].properties.metadata
        allof_obj = spec["components"]["schemas"]["Employee"]["allOf"][1]
        meta_schema = allof_obj["properties"]["metadata"]
        ts = reg.ts_type(meta_schema, "Metadata")
        assert "{ [key: string]:" in ts
        assert "string" in ts

    def test_nested_object_map(self):
        spec = _load_spec()
        reg = SchemaRegistry(spec)
        dept = spec["components"]["schemas"]["Department"]
        settings_schema = dept["properties"]["settings"]
        ts = reg.ts_type(settings_schema, "Settings")
        assert "{ [key: string]:" in ts


# ─── Inline schema extraction ────────────────────────────────────────────────


class TestInlineExtraction:
    """ReportSummary.departments has inline array items with object properties."""

    def test_inline_array_item_extracted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, _ = _gen_advanced(tmpdir)
            # The inline object in departments array items should be extracted
            # Name should be something like ReportSummaryDepartmentsInner
            inline_names = [m for m in models if "Inner" in m or "Departments" in m]
            assert len(inline_names) >= 1, f"Expected inline model extraction, got models: {models}"

    def test_inline_model_has_properties(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, _ = _gen_advanced(tmpdir)
            # Find the inline model file
            models_dir = Path(tmpdir) / "models"
            inline_files = [f for f in models_dir.iterdir() if "Inner" in f.name or "Departments" in f.name]
            assert inline_files, f"No inline model file found in {[f.name for f in models_dir.iterdir()]}"
            content = inline_files[0].read_text()
            assert "name" in content
            assert "count" in content


# ─── Enum generation ─────────────────────────────────────────────────────────


class TestEnums:
    def test_enum_constant_object(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            base_ts = (Path(tmpdir) / "models" / "PersonBase.ts").read_text()
            # Should have enum constant: PersonBaseRoleEnum
            assert "PersonBaseRoleEnum" in base_ts
            assert "'admin'" in base_ts
            assert "'manager'" in base_ts
            assert "'staff'" in base_ts

    def test_enum_type_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            base_ts = (Path(tmpdir) / "models" / "PersonBase.ts").read_text()
            assert "export type PersonBaseRoleEnum" in base_ts


# ─── Required vs optional ───────────────────────────────────────────────────


class TestRequiredOptional:
    def test_required_property_not_optional(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            addr_ts = (Path(tmpdir) / "models" / "Address.ts").read_text()
            # street and city are required — no ? mark
            assert "street:" in addr_ts or "street :" in addr_ts
            # state is optional — should have ?
            assert "state?" in addr_ts or "state ?" in addr_ts

    def test_instanceof_checks_required(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            addr_ts = (Path(tmpdir) / "models" / "Address.ts").read_text()
            assert "instanceOfAddress" in addr_ts
            assert "'street'" in addr_ts
            assert "'city'" in addr_ts

    def test_from_json_required_no_null_guard(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            req_ts = (Path(tmpdir) / "models" / "CreateEmployeeRequest.ts").read_text()
            # 'name' is required — FromJSON should use direct access
            assert "json['name']" in req_ts


# ─── API codegen: header params, void responses, operationId ────────────────


class TestApiCodegen:
    def test_header_param_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            api_ts = (Path(tmpdir) / "apis" / "EmployeesApi.ts").read_text()
            # X-Tenant-Id header param
            assert "X-Tenant-Id" in api_ts
            assert "headerParameters" in api_ts

    def test_void_response_for_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            api_ts = (Path(tmpdir) / "apis" / "EmployeesApi.ts").read_text()
            # deleteEmployee returns void (204)
            assert "deleteEmployee" in api_ts
            assert "VoidApiResponse" in api_ts

    def test_required_param_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            api_ts = (Path(tmpdir) / "apis" / "EmployeesApi.ts").read_text()
            # X-Tenant-Id is required — should have RequiredError throw
            assert "RequiredError" in api_ts

    def test_path_param_substitution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            api_ts = (Path(tmpdir) / "apis" / "EmployeesApi.ts").read_text()
            assert "employeeId" in api_ts
            assert "encodeURIComponent" in api_ts

    def test_auto_generated_operation_id(self):
        """departments GET has no operationId — should auto-generate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            api_ts = (Path(tmpdir) / "apis" / "DepartmentsApi.ts").read_text()
            # Should have auto-generated method like getDepartments
            assert "getDepartments" in api_ts

    def test_request_body_serialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            api_ts = (Path(tmpdir) / "apis" / "EmployeesApi.ts").read_text()
            assert "Content-Type" in api_ts
            assert "ToJSON" in api_ts

    def test_bearer_auth_wiring(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            api_ts = (Path(tmpdir) / "apis" / "EmployeesApi.ts").read_text()
            assert "accessToken" in api_ts
            assert "Bearer" in api_ts


# ─── Operation ID edge cases ────────────────────────────────────────────────


class TestOperationId:
    def test_explicit_id_preserved(self):
        assert operation_id("get", "/pets", {"operationId": "listPets"}) == "listPets"

    def test_auto_id_from_path(self):
        oid = operation_id("get", "/departments", {})
        assert oid == "getDepartments"

    def test_path_param_becomes_by(self):
        oid = operation_id("get", "/employees/{employeeId}", {})
        assert "ByEmployeeId" in oid

    def test_wildcard_replaced(self):
        oid = operation_id("get", "/proxy", {"operationId": "proxy-*"})
        assert "All" in oid
        assert "*" not in oid

    def test_special_chars_stripped(self):
        oid = operation_id("get", "/x", {"operationId": "get.items[0]"})
        # should produce a valid identifier
        assert oid.isidentifier(), f"'{oid}' is not a valid identifier"


# ─── Error handling ──────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_missing_openapi_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.json"
            bad.write_text('{"info": {"title": "nope"}}')
            try:
                generate(str(bad), tmpdir)
                assert False, "Should have raised SystemExit"
            except SystemExit as e:
                assert e.code == 1

    def test_wrong_openapi_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.json"
            bad.write_text('{"openapi": "2.0.0", "paths": {}}')
            try:
                generate(str(bad), tmpdir)
                assert False, "Should have raised SystemExit"
            except SystemExit as e:
                assert e.code == 1

    def test_no_paths_or_webhooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.json"
            bad.write_text('{"openapi": "3.1.0"}')
            try:
                generate(str(bad), tmpdir)
                assert False, "Should have raised SystemExit"
            except SystemExit as e:
                assert e.code == 1

    def test_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                generate(str(Path(tmpdir) / "nonexistent.json"), tmpdir)
                assert False, "Should have raised an error"
            except (FileNotFoundError, SystemExit):
                pass


# ─── Tag filtering with advanced spec ────────────────────────────────────────


class TestAdvancedTagFiltering:
    def test_filter_employees_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, apis = _gen_advanced(tmpdir, tag_filter={"employees"})
            assert "EmployeesApi" in apis
            assert "DepartmentsApi" not in apis
            assert "ReportsApi" not in apis

    def test_filter_preserves_transitive_deps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, apis = _gen_advanced(tmpdir, tag_filter={"employees"})
            # Employee refs PersonBase via allOf, Address via property
            assert "PersonBase" in models or "Address" in models
            # Department should NOT be in models (not referenced by employees)
            assert "Department" not in models

    def test_nonexistent_tag_yields_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, apis = _gen_advanced(tmpdir, tag_filter={"nonexistent"})
            assert len(apis) == 0


# ─── Barrel exports ──────────────────────────────────────────────────────────


class TestBarrelExports:
    def test_models_index_exports_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models, _ = _gen_advanced(tmpdir)
            idx = (Path(tmpdir) / "models" / "index.ts").read_text()
            for m in models:
                assert m in idx, f"Model {m} missing from models/index.ts"

    def test_apis_index_exports_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, apis = _gen_advanced(tmpdir)
            idx = (Path(tmpdir) / "apis" / "index.ts").read_text()
            for a in apis:
                assert a in idx, f"API {a} missing from apis/index.ts"

    def test_toplevel_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen_advanced(tmpdir)
            idx = (Path(tmpdir) / "index.ts").read_text()
            assert "runtime" in idx
            assert "apis" in idx
            assert "models" in idx
