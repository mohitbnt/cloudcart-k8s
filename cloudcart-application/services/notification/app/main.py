import os

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


DATABASE_URL = required_env("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class NoticeDB(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(500))


class Notice(BaseModel):
    recipient: str
    message: str


app = FastAPI(title="CloudCart Notification", version="1.0.0")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    return {"status": "healthy", "service": "notification", "database": "connected"}


@app.post("/notifications", status_code=201)
def create_notification(data: Notice):
    with Session(engine) as database:
        notification = NoticeDB(
            recipient=data.recipient,
            message=data.message,
        )
        database.add(notification)
        database.commit()
        database.refresh(notification)
        return {
            "id": notification.id,
            "queued": True,
            "recipient": notification.recipient,
            "message": notification.message,
        }


@app.get("/notifications")
def list_notifications():
    with Session(engine) as database:
        notifications = database.scalars(
            select(NoticeDB).order_by(NoticeDB.id)
        ).all()
        return [
            {
                "id": item.id,
                "recipient": item.recipient,
                "message": item.message,
            }
            for item in notifications
        ]
