import os
from sqlalchemy import create_engine, String, Integer, Float, Boolean, ForeignKey, DateTime, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
DATABASE_URL=os.getenv("DATABASE_URL")
engine=create_engine(DATABASE_URL,pool_pre_ping=True)
class Base(DeclarativeBase): pass
from fastapi import FastAPI
from pydantic import BaseModel
app=FastAPI(title="CloudCart Payment")
class PaymentDB(Base):
 __tablename__="payments"
 id:Mapped[int]=mapped_column(primary_key=True)
 customer_email:Mapped[str]=mapped_column(String(200))
 amount:Mapped[float]=mapped_column(Float)
 status:Mapped[str]=mapped_column(String(30))
class Payment(BaseModel):amount:float;customer_email:str
@app.on_event("startup")
def startup():Base.metadata.create_all(engine)
@app.get("/health")
def health():
 with engine.connect() as c:c.exec_driver_sql("select 1")
 return {"status":"healthy","service":"payment","database":"connected"}
@app.post("/payments/authorize")
def authorize(x:Payment):
 with Session(engine) as db:p=PaymentDB(customer_email=x.customer_email,amount=x.amount,status="AUTHORIZED");db.add(p);db.commit();db.refresh(p);return {"id":p.id,"status":p.status,"amount":p.amount}
