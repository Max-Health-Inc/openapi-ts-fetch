#!/usr/bin/env python3
"""
Basic smoke tests for the openapi-ts-fetch generator.
Generates a client from the petstore example and validates output structure.

Run: python tests/test_generate.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from generate import generate

EXAMPLES_DIR = Path(__file__).parent.parent / 'examples'
PETSTORE_SPEC = EXAMPLES_DIR / 'petstore.json'


def test_full_generation():
    """Test generating all tags from the petstore spec."""
    with tempfile.TemporaryDirectory() as tmpdir:
        models, apis = generate(str(PETSTORE_SPEC), tmpdir)

        # Should have 3 models: Pet, CreatePetRequest, Owner
        assert len(models) == 3, f"Expected 3 models, got {len(models)}: {models}"
        assert 'Pet' in models
        assert 'CreatePetRequest' in models
        assert 'Owner' in models

        # Should have 2 API classes: PetsApi, OwnersApi
        assert len(apis) == 2, f"Expected 2 APIs, got {len(apis)}: {apis}"
        assert 'PetsApi' in apis
        assert 'OwnersApi' in apis

        # Check file structure
        out = Path(tmpdir)
        assert (out / 'runtime.ts').exists()
        assert (out / 'index.ts').exists()
        assert (out / 'models' / 'index.ts').exists()
        assert (out / 'apis' / 'index.ts').exists()
        assert (out / 'models' / 'Pet.ts').exists()
        assert (out / 'apis' / 'PetsApi.ts').exists()
        assert (out / 'apis' / 'OwnersApi.ts').exists()

        # Check that PetsApi contains expected methods
        pets_api = (out / 'apis' / 'PetsApi.ts').read_text()
        assert 'listPets' in pets_api
        assert 'createPet' in pets_api
        assert 'getPet' in pets_api

        # Check that OwnersApi contains expected methods
        owners_api = (out / 'apis' / 'OwnersApi.ts').read_text()
        assert 'listOwners' in owners_api

        print('  [PASS] test_full_generation')


def test_tag_filtering():
    """Test generating only a subset of tags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        models, apis = generate(str(PETSTORE_SPEC), tmpdir, tag_filter={'pets'})

        # Should have PetsApi only
        assert len(apis) == 1, f"Expected 1 API, got {len(apis)}: {apis}"
        assert 'PetsApi' in apis

        # Should have Pet + CreatePetRequest + Owner (Owner is referenced by Pet)
        assert 'Pet' in models
        assert 'CreatePetRequest' in models
        assert 'Owner' in models  # transitively referenced via Pet.owner

        # OwnersApi should NOT be generated
        out = Path(tmpdir)
        assert not (out / 'apis' / 'OwnersApi.ts').exists()

        print('  [PASS] test_tag_filtering')


def test_tag_filtering_owners_only():
    """Test generating only the owners tag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        models, apis = generate(str(PETSTORE_SPEC), tmpdir, tag_filter={'owners'})

        # Should only have OwnersApi
        assert len(apis) == 1, f"Expected 1 API, got {len(apis)}: {apis}"
        assert 'OwnersApi' in apis

        # Should only have Owner model (Pet/CreatePetRequest not needed)
        assert 'Owner' in models
        assert 'Pet' not in models
        assert 'CreatePetRequest' not in models

        print('  [PASS] test_tag_filtering_owners_only')


def test_model_content():
    """Test that generated model files contain expected TypeScript constructs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generate(str(PETSTORE_SPEC), tmpdir)

        out = Path(tmpdir)
        pet_ts = (out / 'models' / 'Pet.ts').read_text()

        # Interface should exist
        assert 'export interface Pet' in pet_ts
        # FromJSON / ToJSON functions
        assert 'export function PetFromJSON' in pet_ts
        assert 'export function PetToJSON' in pet_ts
        # instanceOf guard
        assert 'export function instanceOfPet' in pet_ts
        # Should import Owner (referenced via $ref)
        assert "import type { Owner }" in pet_ts

        print('  [PASS] test_model_content')


def test_runtime_base_path():
    """Test that runtime.ts BASE_PATH is empty (callers configure via Configuration)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generate(str(PETSTORE_SPEC), tmpdir)

        rt = Path(tmpdir) / 'runtime.ts'
        content = rt.read_text()
        assert 'export const BASE_PATH = ""' in content

        print('  [PASS] test_runtime_base_path')


if __name__ == '__main__':
    print('Running openapi-ts-fetch tests...\n')
    test_full_generation()
    test_tag_filtering()
    test_tag_filtering_owners_only()
    test_model_content()
    test_runtime_base_path()
    print('\nAll tests passed!')
