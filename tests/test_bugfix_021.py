#!/usr/bin/env python3
"""
Tests for v0.2.1 bugfixes:
  1. Standalone enum schemas included in models/index.ts
  2. model_refs matches non-PascalCase names (Body_*, api__*)
  3. Duplicate operation IDs deduplicated per tag
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from generate import SchemaRegistry, generate, model_refs

SPEC_PATH = Path(__file__).parent.parent / "examples" / "bugfix_021.json"


def _load_spec():
    return json.loads(SPEC_PATH.read_text())


def _gen(tmpdir, **kwargs):
    return generate(str(SPEC_PATH), tmpdir, **kwargs)


# ─── Bug 1: Standalone enum schemas in models/index.ts ──────────────────────


class TestEnumModelsInIndex:
    """Standalone enum schemas (no properties, just enum) must be generated
    and exported from models/index.ts."""

    def test_enum_files_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            models_dir = Path(tmpdir) / "models"
            assert (models_dir / "InteractionSource.ts").exists()
            assert (models_dir / "InteractionKind.ts").exists()

    def test_enum_in_models_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            index = (Path(tmpdir) / "models" / "index.ts").read_text()
            assert "InteractionSource" in index, "InteractionSource missing from models/index.ts"
            assert "InteractionKind" in index, "InteractionKind missing from models/index.ts"

    def test_enum_file_has_type_and_helpers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            content = (Path(tmpdir) / "models" / "InteractionKind.ts").read_text()
            assert "export type InteractionKind" in content
            assert "'chat_message'" in content
            assert "'error'" in content
            assert "InteractionKindFromJSON" in content
            assert "InteractionKindToJSON" in content
            assert "instanceOfInteractionKind" in content

    def test_enum_imported_by_api_that_uses_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            api = (Path(tmpdir) / "apis" / "HistoryApi.ts").read_text()
            assert "InteractionKind" in api, "HistoryApi should import InteractionKind"
            assert "InteractionSource" in api, "HistoryApi should import InteractionSource"

    def test_enum_imported_by_model_that_uses_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            model = (Path(tmpdir) / "models" / "HistoryEntry.ts").read_text()
            assert "InteractionKind" in model
            assert "InteractionSource" in model


# ─── Bug 2: model_refs matches non-PascalCase names ─────────────────────────


class TestNonPascalCaseModelRefs:
    """model_refs must find Body_*, api__* style names in type strings."""

    def test_body_underscore_name_found(self):
        spec = _load_spec()
        reg = SchemaRegistry(spec)
        # When the title has underscores, register_schema PascalCases it
        name = reg.register_schema(
            {"type": "object", "properties": {"audio": {"type": "string"}}, "title": "Body_transcribe_speech_api_stt__post"},
            "Body_transcribe_speech_api_stt__post",
        )
        # The registered name is PascalCased
        assert name == "BodyTranscribeSpeechApiSttPost"
        refs = model_refs(name, reg)
        assert name in refs

    def test_api_double_underscore_name_found(self):
        spec = _load_spec()
        reg = SchemaRegistry(spec)
        name = reg.register_schema(
            {"type": "object", "properties": {"content": {"type": "string"}}, "title": "api__filesystem__WriteFileRequest"},
            "api__filesystem__WriteFileRequest",
        )
        assert name == "ApiFilesystemWriteFileRequest"
        refs = model_refs(name, reg)
        assert name in refs

    def test_body_model_imported_in_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            stt_api = (Path(tmpdir) / "apis" / "SttApi.ts").read_text()
            # PascalCased name must be imported
            assert "BodyTranscribeSpeechApiSttPost" in stt_api
            assert "BodyTranscribeSpeechApiSttPostToJSON" in stt_api

    def test_api_underscore_model_imported_in_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            fs_api = (Path(tmpdir) / "apis" / "FilesystemApi.ts").read_text()
            assert "ApiFilesystemWriteFileRequest" in fs_api
            assert "ApiFilesystemWriteFileRequestToJSON" in fs_api


# ─── Bug 3: Duplicate operation IDs deduplicated ────────────────────────────


class TestDuplicateOperationIdDedup:
    """When multiple HTTP methods share the same operationId (e.g. FastAPI
    api_route with methods=['GET','POST','OPTIONS']), only one should be
    generated to avoid TS duplicate function errors."""

    def test_no_duplicate_methods_in_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            default_api = (Path(tmpdir) / "apis" / "DefaultApi.ts").read_text()
            # Count occurrences of the Raw method
            raw_count = default_api.count("async beaconSinkRaw(")
            assert raw_count == 1, f"Expected 1 beaconSinkRaw method, found {raw_count}"

    def test_no_duplicate_convenience_methods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            default_api = (Path(tmpdir) / "apis" / "DefaultApi.ts").read_text()
            conv_count = default_api.count("async beaconSink(")
            # beaconSink appears once for Raw and once for convenience = 2 total method definitions
            # but beaconSinkRaw should appear only once
            assert conv_count == 1, f"Expected 1 beaconSink convenience method, found {conv_count}"

    def test_default_api_compiles_without_duplicates(self):
        """The generated DefaultApi should be valid TypeScript (no TS2393)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _gen(tmpdir)
            default_api = (Path(tmpdir) / "apis" / "DefaultApi.ts").read_text()
            # A duplicate would have the same method signature appearing twice
            lines = default_api.split("\n")
            method_sigs = [line.strip() for line in lines if line.strip().startswith("async ") and line.strip().endswith("{")]
            assert len(method_sigs) == len(set(method_sigs)), \
                f"Duplicate method signatures found: {[s for s in method_sigs if method_sigs.count(s) > 1]}"
