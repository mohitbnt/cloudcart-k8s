import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Float, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


DATABASE_URL = required_env("DATABASE_URL")
INVENTORY_URL = required_env("INVENTORY_URL").rstrip("/")
PAYMENT_URL = required_env("PAYMENT_URL").rstrip("/")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class OrderDB(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_email: Mapped[str] = mapped_column(String(200))
    total: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(40), default="CONFIRMED")


class Item(BaseModel):
    product_id: int
    quantity: int


class NewOrder(BaseModel):
    customer_email: str
    items: list[Item]
    total: float


app = FastAPI(title="CloudCart Order", version="1.0.0")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    return {"status": "healthy", "service": "order", "database": "connected"}


@app.get("/orders")
def orders():
    with Session(engine) as db:
        return [
            {
                "id": order.id,
                "customer_email": order.customer_email,
                "total": order.total,
                "status": order.status,
            }
            for order in db.scalars(select(OrderDB).order_by(OrderDB.id))
        ]


@app.post("/orders", status_code=201)
async def create(x: NewOrder):
    if not x.items:
        raise HTTPException(400, "Order must contain at least one item")
    if x.total <= 0:
        raise HTTPException(400, "Order total must be positive")

    async with httpx.AsyncClient(timeout=5) as client:
        for item in x.items:
            try:
                response = await client.post(
                    f"{INVENTORY_URL}/inventory/reserve",
                    json=item.model_dump(),
                )
            except httpx.RequestError:
                raise HTTPException(503, "Inventory service unavailable")

            if response.status_code != 200:
                raise HTTPException(409, "Stock unavailable")

        try:
            payment = await client.post(
                f"{PAYMENT_URL}/payments/authorize",
                json={"amount": x.total, "customer_email": x.customer_email},
            )
        except httpx.RequestError:
            raise HTTPException(503, "Payment service unavailable")

        if payment.status_code != 200:
            raise HTTPException(402, "Payment declined")

    with Session(engine) as db:
        order = OrderDB(
            customer_email=x.customer_email.strip().lower(),
            total=x.total,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return {"id": order.id, "status": order.status, "total": order.total}
