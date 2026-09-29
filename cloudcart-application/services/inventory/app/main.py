import os
from sqlalchemy import create_engine, String, Integer, Float, Boolean, ForeignKey, DateTime, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
DATABASE_URL=os.getenv("DATABASE_URL")
engine=create_engine(DATABASE_URL,pool_pre_ping=True)
class Base(DeclarativeBase): pass
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
app=FastAPI(title="CloudCart Inventory")
class InventoryDB(Base):
 __tablename__="inventory"
 product_id:Mapped[int]=mapped_column(primary_key=True)
 stock:Mapped[int]=mapped_column(Integer)
class Reservation(BaseModel):product_id:int;quantity:int
@app.on_event("startup")
def startup():
 Base.metadata.create_all(engine)
 with Session(engine) as db:
  if db.scalar(select(InventoryDB.product_id).limit(1)) is None:db.add_all([InventoryDB(product_id=i,stock=n) for i,n in {1:25,2:40,3:15,4:12}.items()]);db.commit()
@app.get("/health")
def health():
 with engine.connect() as c:c.exec_driver_sql("select 1")
 return {"status":"healthy","service":"inventory","database":"connected"}
@app.get("/inventory/{pid}")
def get(pid:int):
 with Session(engine) as db:x=db.get(InventoryDB,pid)
 return {"product_id":pid,"stock":x.stock if x else 0}
@app.post("/inventory/reserve")
def reserve(x:Reservation):
 if x.quantity<=0:raise HTTPException(400,"Quantity must be positive")
 with Session(engine) as db:
  row=db.get(InventoryDB,x.product_id)
  if not row or row.stock<x.quantity:raise HTTPException(409,"Insufficient stock")
  row.stock-=x.quantity;db.commit();return {"reserved":True,"product_id":x.product_id,"quantity":x.quantity,"remaining_stock":row.stock}
