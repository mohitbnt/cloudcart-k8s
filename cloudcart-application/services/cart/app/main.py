import json
import os

import redis
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


REDIS_URL = required_env("REDIS_URL")
TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "cloudcart_session")

r = redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="CloudCart Cart", version="1.0.0")


class Item(BaseModel):
    product_id: int
    quantity: int


def session_id(request: Request) -> str:
    sid = request.cookies.get(COOKIE_NAME)
    if not sid:
        raise HTTPException(401, "Not authenticated")
    return sid


def read_items(sid: str):
    raw = r.lrange(f"cart:{sid}", 0, -1)
    merged = {}
    for value in raw:
        item = json.loads(value)
        product_id = int(item["product_id"])
        merged[product_id] = merged.get(product_id, 0) + int(item["quantity"])
    return [
        {"product_id": product_id, "quantity": quantity}
        for product_id, quantity in merged.items()
    ]


def write_items(sid: str, items):
    key = f"cart:{sid}"
    pipe = r.pipeline()
    pipe.delete(key)
    if items:
        pipe.rpush(key, *[json.dumps(item) for item in items])
        pipe.expire(key, TTL)
    pipe.execute()


def get_cart(sid: str):
    return {"items": read_items(sid)}


@app.get("/health")
def health():
    r.ping()
    return {"status": "healthy", "service": "cart", "redis": "connected"}


@app.get("/cart")
def browser_get(request: Request):
    return get_cart(session_id(request))


@app.post("/cart/items")
def browser_add(request: Request, x: Item):
    sid = session_id(request)
    if x.quantity <= 0:
        raise HTTPException(400, "Quantity must be positive")

    items = read_items(sid)
    for item in items:
        if item["product_id"] == x.product_id:
            item["quantity"] += x.quantity
            break
    else:
        items.append(x.model_dump())
    write_items(sid, items)
    return get_cart(sid)


@app.patch("/cart/items/{product_id}")
def browser_update(product_id: int, request: Request, x: Item):
    sid = session_id(request)
    if x.quantity < 0:
        raise HTTPException(400, "Quantity cannot be negative")

    items = read_items(sid)
    updated = []
    found = False
    for item in items:
        if item["product_id"] == product_id:
            found = True
            if x.quantity > 0:
                updated.append({"product_id": product_id, "quantity": x.quantity})
        else:
            updated.append(item)

    if not found:
        raise HTTPException(404, "Cart item not found")
    write_items(sid, updated)
    return get_cart(sid)


@app.delete("/cart/items/{product_id}")
def browser_remove(product_id: int, request: Request):
    sid = session_id(request)
    items = [item for item in read_items(sid) if item["product_id"] != product_id]
    write_items(sid, items)
    return get_cart(sid)


@app.delete("/cart")
def browser_clear(request: Request):
    sid = session_id(request)
    r.delete(f"cart:{sid}")
    return get_cart(sid)


# Legacy session-id endpoints retained for backend/service testing.
@app.get("/cart/{sid}")
def get(sid: str):
    return {"session_id": sid, **get_cart(sid)}


@app.post("/cart/{sid}/items")
def add(sid: str, x: Item):
    if x.quantity <= 0:
        raise HTTPException(400, "Quantity must be positive")
    items = read_items(sid)
    for item in items:
        if item["product_id"] == x.product_id:
            item["quantity"] += x.quantity
            break
    else:
        items.append(x.model_dump())
    write_items(sid, items)
    return get(sid)


@app.delete("/cart/{sid}")
def clear(sid: str):
    r.delete(f"cart:{sid}")
    return get(sid)
