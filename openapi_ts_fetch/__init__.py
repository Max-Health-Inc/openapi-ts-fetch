"""Pure Python OpenAPI 3.x to TypeScript-fetch client generator.

Replaces the Java openapi-generator-cli for generating a typed fetch-based
API client from an OpenAPI 3.x spec. Handles OpenAPI 3.0.3 and 3.1.x natively.

Output layout:
  - runtime.ts  (shared fetch infra, BASE_PATH updated)
  - models/*.ts (interfaces + FromJSON/ToJSON per schema)
  - apis/*.ts   (API classes extending BaseAPI, one per tag)
  - index.ts    (barrel exports)

Schema naming strategy (mirrors Java openapi-generator):
  1. Use 'title' field if present on the schema (Elysia/TypeBox sets these)
  2. Content-hash dedup: identical schemas with the same title reuse one model
  3. Nested object properties: ParentName + PropertyName (PascalCase)
  4. Array items with object schemas: ParentName + PropertyName + "Inner"
  5. Fallback: OperationId + StatusCode + "Response"/"Request"

Usage:
  openapi-ts-fetch <spec-path> <output-dir> [--tags tag1,tag2,...]
"""

from __future__ import annotations

from .apis import gen_api
from .generator import generate
from .models import gen_model, model_refs
from .naming import camel, operation_id, pascal, safe_id
from .schema_registry import SchemaRegistry, norm_type
from .version import __version__

__all__ = [
    "SchemaRegistry",
    "__version__",
    "camel",
    "gen_api",
    "gen_model",
    "generate",
    "model_refs",
    "norm_type",
    "operation_id",
    "pascal",
    "safe_id",
]
