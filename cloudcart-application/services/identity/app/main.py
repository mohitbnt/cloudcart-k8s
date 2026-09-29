import hashlib
import os
import secrets

import redis
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


DATABASE_URL = required_env("DATABASE_URL")
REDIS_URL = required_env("REDIS_URL")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "cloudcart_session")
COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
r = redis.from_url(REDIS_URL, decode_responses=True)


class Base(DeclarativeBase):
    pass


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(30), default="customer")


class Credentials(BaseModel):
    email: str
    password: str


app = FastAPI(title="CloudCart Identity", version="1.0.0")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def user_dict(user: UserDB) -> dict:
    return {"id": str(user.id), "email": user.email, "role": user.role}


def create_session(user: UserDB, response: Response) -> dict:
    token = secrets.token_urlsafe(32)
    key = f"session:{token}"
    r.hset(key, mapping=user_dict(user))
    r.expire(key, SESSION_TTL)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=SESSION_TTL,
        path="/",
    )
    return user_dict(user)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if db.scalar(select(UserDB.id).limit(1)) is None:
            db.add(
                UserDB(
                    email="demo@example.com",
                    password_hash=hash_password("demo123"),
                )
            )
            db.commit()


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    r.ping()
    return {
        "status": "healthy",
        "service": "identity",
        "database": "connected",
        "redis": "connected",
    }


@app.post("/register", status_code=201)
def register(x: Credentials, response: Response):
    email = normalize_email(x.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Please enter a valid email address")
    if len(x.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    with Session(engine) as db:
        existing = db.scalar(select(UserDB).where(UserDB.email == email))
        if existing:
            raise HTTPException(409, "An account with this email already exists")

        user = UserDB(email=email, password_hash=hash_password(x.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return create_session(user, response)


@app.post("/login")
def login(x: Credentials, response: Response):
    email = normalize_email(x.email)
    with Session(engine) as db:
        user = db.scalar(select(UserDB).where(UserDB.email == email))
        if not user or user.password_hash != hash_password(x.password):
            raise HTTPException(401, "Invalid credentials")
        return create_session(user, response)


@app.get("/me")
def me(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    data = r.hgetall(f"session:{token}") if token else {}
    if not data:
        raise HTTPException(401, "Not authenticated")
    r.expire(f"session:{token}", SESSION_TTL)
    return data


@app.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        r.delete(f"session:{token}")
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"logged_out": True}
