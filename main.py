from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Table, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from passlib.context import CryptContext # 패스워드 해싱
 
app = FastAPI()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = "mysql+pymysql://root:6884@localhost:3306/my_memo_app"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

class Memo(Base):
    __tablename__ = "memos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True)
    content = Column(String(1000), index=True)
    created_at = Column(DateTime, default=datetime.now)

class MemoCreate(BaseModel): # 메모 생성 검증 모델
    title: str
    content: str

class MemoUpdate(BaseModel): # 메모 수정 모델
    title: Optional[str] = None
    content: Optional[str] = None

def get_db():
    db = Session(bind=engine)
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine) # 테이블 생성

# 메모 생성 - 클라이언트에서 -> 서버로
@app.post("/memos/")
async def create_memo(memo: MemoCreate, db: Session = Depends(get_db)):
    new_memo = Memo(title=memo.title, content=memo.content)
    db.add(new_memo)
    db.commit()
    db.refresh(new_memo)
    return ({"id": new_memo.id, "title": new_memo.title, "content": new_memo.content})

# 메모 조회 - 서버에서 -> 클라이언트
@app.get("/memos")
async def list_memos(db: Session = Depends(get_db)):
    memos = db.query(Memo).all()
    return [{"id": memo.id, "title": memo.title, "content": memo.content} for memo in memos]

# 메모 수정 
@app.put("/memos/{memo_id}")
async def update_memo(memo_id: int, memo: MemoUpdate, db: Session = Depends(get_db)):
    db_memo = db.query(Memo).filter(Memo.id == memo_id).first()
    if db_memo is None:
        raise HTTPException(status_code=404, detail="Memo not found")
    if memo.title is not None:
        db_memo.title = memo.title
    if memo.content is not None:
        db_memo.content = memo.content
    db.commit()
    db.refresh(db_memo)
    return ({"id": db_memo.id, "title": db_memo.title, "content": db_memo.content})

# 메모 삭제
@app.delete("/memos/{memo_id}")
async def delete_memo(memo_id: int, db: Session = Depends(get_db)):
    db_memo = db.query(Memo).filter(Memo.id == memo_id).first()
    if db_memo is None:
        raise HTTPException(status_code=404, detail="Memo not found")
    db.delete(db_memo)
    db.commit()
    return ({"message": "Memo deleted successfully"})

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/about")
async def about():
    return {"message": "This is the about page"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)