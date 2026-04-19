# openapi-ts-fetch

Lightweight Python OpenAPI 3.x → TypeScript fetch client generator. **Zero Java, zero npm** — just Python 3.10+ and your OpenAPI spec.

A fast, single-file alternative to the 200MB+ Java `openapi-generator-cli`. Generates fully typed TypeScript fetch clients with the same output structure.

## Features

- **OpenAPI 3.0.3 & 3.1.x** — handles both spec versions natively
- **Schema deduplication** — identical schemas share a single model via content-hash
- **Nested extraction** — inline object properties and array items become named models
- **Tag filtering** — generate only the APIs you need with `--tags`
- **No runtime dependencies** — pure Python stdlib, TypeScript output uses only `fetch`
- **Drop-in compatible** — output matches the `openapi-generator` TypeScript-fetch structure

## Installation

```bash
# Option 1: pip install (coming soon)
pip install openapi-ts-fetch

# Option 2: just copy the two files
curl -O https://raw.githubusercontent.com/Max-Health-Inc/openapi-ts-fetch/main/generate.py
curl -O https://raw.githubusercontent.com/Max-Health-Inc/openapi-ts-fetch/main/runtime-template.ts
```

## Usage

```bash
# Generate full client
python generate.py openapi.json ./src/api-client

# Generate only specific API tags (and their referenced models)
python generate.py openapi.json ./src/api-client --tags users,orders

# From pip install
openapi-ts-fetch openapi.json ./src/api-client --tags users
```

## Output Structure

```
src/api-client/
├── runtime.ts          # Configuration, BaseAPI, middleware, fetch helpers
├── index.ts            # Barrel exports
├── apis/
│   ├── index.ts
│   ├── UsersApi.ts     # One class per OpenAPI tag
│   └── OrdersApi.ts
└── models/
    ├── index.ts
    ├── User.ts          # Interface + FromJSON/ToJSON
    └── CreateUserRequest.ts
```

## Using the Generated Client

```typescript
import { Configuration, UsersApi } from './api-client'

const config = new Configuration({
  basePath: 'https://api.example.com',
  accessToken: async () => getMyToken(),
})

const users = new UsersApi(config)

// Fully typed request and response
const user = await users.getUser({ id: '123' })
console.log(user.name)
```

## Tag Filtering

When you only need a subset of your API in a particular app, use `--tags` to generate a lean client:

```bash
# Full API has 26 tags and 220 models, but your app only uses 'shl'
python generate.py openapi.json ./src/api-client --tags shl

# Output: 1 API class, 3 models (only transitively referenced ones)
```

This is especially useful in monorepos where different apps consume different parts of the same backend API.

## Comparison

| | openapi-ts-fetch | openapi-generator-cli |
|---|---|---|
| Runtime | Python 3.10+ (~1000 LOC) | Java 11+ (~200MB JAR) |
| Install | `pip install` or copy 2 files | Docker / Java / npm wrapper |
| Speed | ~1s for 200+ models | ~10s+ for same spec |
| Tag filtering | Built-in `--tags` | Templates + config |
| Schema dedup | Content-hash based | Limited |
| Output | TypeScript fetch | TypeScript fetch (+ 40 others) |

## Schema Naming Strategy

1. **`title` field** — uses the schema's `title` if present (frameworks like Elysia/TypeBox set these automatically)
2. **Content-hash dedup** — identical schemas with the same title share a single model
3. **Nested objects** — `ParentName` + `PropertyName` (PascalCase)
4. **Array items** — `ParentName` + `PropertyName` + `"Inner"`
5. **Fallback** — `OperationId` + `StatusCode` + `"Response"` / `"Request"`

## License

MIT — [Max Health Inc.](https://github.com/Max-Health-Inc)
