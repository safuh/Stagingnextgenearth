# API Module

The API module is the HTTP transport boundary. It contains routers, Pydantic request/response schemas, dependencies, and operational endpoints.

## Rules

- Keep business decisions out of routers.
- Delegate use cases to application services.
- Validate external input with Pydantic.
- Return stable, documented response contracts.
- Keep authentication dependencies explicit.
- Version public APIs when compatibility requires it.
- Keep health endpoints independent of product-specific domain modules.

The reference API exposes health endpoints and an optional authentication router. Authentication returns a controlled 503 response until the consuming application supplies an authentication composition factory.

There is no frontend or mobile-client dependency. FastAPI's OpenAPI document is the API contract for any external client.
