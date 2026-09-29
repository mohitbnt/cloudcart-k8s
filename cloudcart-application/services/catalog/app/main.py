import os
from sqlalchemy import create_engine, String, Integer, Float, Boolean, ForeignKey, DateTime, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
DATABASE_URL=os.getenv("DATABASE_URL")
engine=create_engine(DATABASE_URL,pool_pre_ping=True)
class Base(DeclarativeBase): pass
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
app=FastAPI(title="CloudCart Catalog")
class ProductDB(Base):
 __tablename__="products"
 id:Mapped[int]=mapped_column(primary_key=True)
 name:Mapped[str]=mapped_column(String(150))
 description:Mapped[str]=mapped_column(String(500))
 price:Mapped[float]=mapped_column(Float)
 stock:Mapped[int]=mapped_column(Integer)
 category:Mapped[str]=mapped_column(String(80),default="General")
 emoji:Mapped[str]=mapped_column(String(10),default="📦")
class ProductIn(BaseModel): name:str; description:str; price:float; stock:int; category:str="General"; emoji:str="📦"
class ProductOut(ProductIn):
 id:int
 model_config={"from_attributes":True}
@app.on_event("startup")
def startup():
 Base.metadata.create_all(engine)
 with Session(engine) as db:
  if db.scalar(select(ProductDB.id).limit(1)) is None:
   db.add_all([ProductDB(name="Mechanical Keyboard",description="Tactile keys and compact design",price=2499,stock=25,category="Workspace",emoji="⌨️"),ProductDB(name="Wireless Mouse",description="Ergonomic rechargeable mouse",price=999,stock=40,category="Workspace",emoji="🖱️"),ProductDB(name="USB-C Hub",description="Seven-port laptop connectivity",price=1499,stock=15,category="Accessories",emoji="🔌"),ProductDB(name="Noise Cancelling Headphones",description="Immersive sound for focused work",price=3999,stock=12,category="Audio",emoji="🎧")]); db.commit()
@app.get("/health")
def health():
 with engine.connect() as c:c.exec_driver_sql("select 1")
 return {"status":"healthy","service":"catalog","database":"connected"}
@app.get("/products",response_model=list[ProductOut])
def products(category:str|None=None):
 with Session(engine) as db:
  q=select(ProductDB).order_by(ProductDB.id)
  if category:q=q.where(ProductDB.category==category)
  return list(db.scalars(q))
@app.get("/products/{pid}",response_model=ProductOut)
def product(pid:int):
 with Session(engine) as db:
  p=db.get(ProductDB,pid)
  if not p:raise HTTPException(404,"Product not found")
  return p
@app.post("/products",response_model=ProductOut,status_code=201)
def create(x:ProductIn):
 with Session(engine) as db:
  p=ProductDB(**x.model_dump());db.add(p);db.commit();db.refresh(p);return p
