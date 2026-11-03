#!/usr/bin/env python3
"""
Map values that are objects (`additionalProperties` with properties) must be
written as models, like object properties and array items are.
"""

import json
import tempfile
from pathlib import Path

from openapi_ts_fetch import generate

COUNTS = {
    "type": "object",
    "required": ["permit", "deny"],
    "properties": {"permit": {"type": "number"}, "deny": {"type": "number"}},
}

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "maps", "version": "1.0.0"},
    "paths": {
        "/analytics": {
            "get": {
                "operationId": "getAnalytics",
                "tags": ["monitoring"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "title": "AnalyticsResponse",
                                    "type": "object",
                                    "required": ["byType", "byMode"],
                                    "properties": {
                                        "byType": {"type": "object", "additionalProperties": COUNTS},
                                        "byMode": {
                                            "type": "object",
                                            "additionalProperties": {**COUNTS, "title": "ModeCounts"},
                                        },
                                        "total": {"type": "object", "additionalProperties": {"type": "number"}},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/servers": {
            "get": {
                "operationId": "getServers",
                "tags": ["monitoring"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "title": "ServerStatus",
                                        "type": "object",
                                        "required": ["up"],
                                        "properties": {"up": {"type": "boolean"}},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
    },
}


def _gen(tmpdir: str) -> Path:
    spec_path = Path(tmpdir) / "spec.json"
    spec_path.write_text(json.dumps(SPEC))
    out = Path(tmpdir) / "out"
    generate(str(spec_path), str(out))
    return out


class TestObjectMapValues:
    def test_every_model_a_file_imports_is_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models = _gen(tmpdir) / "models"
            for ts in models.glob("*.ts"):
                for line in ts.read_text().splitlines():
                    if line.startswith("import") and "from './" in line:
                        target = line.split("from './")[1].split("'")[0]
                        assert (models / f"{target}.ts").exists(), f"{ts.name} imports missing {target}"

    def test_untitled_map_value_is_named_after_its_property(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models = _gen(tmpdir) / "models"
            assert (models / "AnalyticsResponseByTypeValue.ts").exists()
            assert "[key: string]: AnalyticsResponseByTypeValue" in (models / "AnalyticsResponse.ts").read_text()

    def test_titled_map_value_keeps_its_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models = _gen(tmpdir) / "models"
            assert (models / "ModeCounts.ts").exists()
            assert "[key: string]: ModeCounts" in (models / "AnalyticsResponse.ts").read_text()

    def test_primitive_map_values_stay_inline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert "[key: string]: number" in (_gen(tmpdir) / "models" / "AnalyticsResponse.ts").read_text()

    def test_map_values_are_exported_from_the_models_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index = (_gen(tmpdir) / "models" / "index.ts").read_text()
            for name in ("AnalyticsResponseByTypeValue", "ModeCounts", "ServerStatus"):
                assert f"'./{name}'" in index

    def test_a_response_that_is_a_map_of_objects_gets_its_value_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert (_gen(tmpdir) / "models" / "ServerStatus.ts").exists()
