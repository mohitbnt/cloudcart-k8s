import os

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value.rstrip("/")


ROUTES = {
    "catalog": required_env("CATALOG_URL"),
    "identity": required_env("IDENTITY_URL"),
    "cart": required_env("CART_URL"),
    "order": required_env("ORDER_URL"),
    "inventory": required_env("INVENTORY_URL"),
    "payment": required_env("PAYMENT_URL"),
    "notification": required_env("NOTIFICATION_URL"),
}

PRESERVE_PREFIX = {"cart", "inventory"}

app = FastAPI(title="CloudCart API Gateway", version="1.0.0")


def allowed_origins() -> list[str]:
    value = os.getenv("ALLOWED_ORIGINS", "")
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def route(path: str) -> str:
    clean_path = path.strip("/")
    parts = clean_path.split("/", 1)
    key = parts[0]

    if key not in ROUTES:
        raise HTTPException(404, "API route not found")

    if key in PRESERVE_PREFIX:
        upstream_path = clean_path
    else:
        upstream_path = parts[1] if len(parts) > 1 else ""

    return ROUTES[key] + "/" + upstream_path.lstrip("/")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "gateway"}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy(path: str, request: Request):
    target = route(path)
    body = await request.body()

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    headers["x-correlation-id"] = request.headers.get(
        "x-correlation-id", os.urandom(8).hex()
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            upstream = await client.request(
                request.method,
                target,
                content=body,
                headers=headers,
                params=request.query_params,
            )
    except httpx.RequestError:
        return JSONResponse(
            {"detail": "Upstream service unavailable"},
            status_code=503,
        )

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in {
            "content-length",
            "transfer-encoding",
            "connection",
            "content-encoding",
        }
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
