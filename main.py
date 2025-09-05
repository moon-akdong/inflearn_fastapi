from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Table, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from passlib.context import CryptContext # 패스워드 해싱
from starlette.middleware.sessions import SessionMiddleware
 
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")
templates = Jinja2Templates(directory="templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# 패스워드 해싱 함수
def get_password_hash(password: str):
    return pwd_context.hash(password)
# 패스워드 검증 함수
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)
    #hashed_password = 데이터 베이스에 있는 해싱된 비밀번호 

DATABASE_URL = "mysql+pymysql://root:6884@localhost:3306/my_memo_app"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

class Memo(Base):
    __tablename__ = "memos"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(100), index=True)
    content = Column(String(1000), index=True)
    created_at = Column(DateTime, default=datetime.now)

class MemoCreate(BaseModel): # 메모 생성 검증 모델
    title: str
    content: str

class MemoUpdate(BaseModel): # 메모 수정 모델
    title: Optional[str] = None
    content: Optional[str] = None

# 데이터 베이스 테이블 유저 생성
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True) #index = 검색 속도 증가 : 검색을 많이 할꺼 같을 때
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
# DB 들어가기 전 유저 데이터 검증 모델둘 
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

# 테이블 생성 전 columns 정의한 클래스가 먼저 나와야 한다.
# Base를 상속받는 클래스가 columns 정의한 클래스이다.
# BaseModel을 상속받는 클래스가 검증 모델이다. -> 이건 뒤에 와도 된다.
def get_db():
    db = Session(bind=engine)
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine) # 테이블 생성

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/about")
async def about():
    return {"message": "This is the about page"}

# 메모 생성 - 클라이언트에서 -> 서버로
@app.post("/memos/")
async def create_memo(request: Request, memo: MemoCreate, db: Session = Depends(get_db)):
    # request : session 정보를 가져오기 위해 사용
    username = request.session.get("username") # 로그인 확인 후에는 username을 세션에서 저장했기 때문에
    if username is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    new_memo = Memo(title=memo.title, content=memo.content, user_id=user.id)
    # new_memo = Memo(title=memo.title, content=memo.content)
    db.add(new_memo)
    db.commit()
    db.refresh(new_memo)
    return new_memo

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


@app.post("/signup/")
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully", "user_id": new_user.id}

@app.post("/login/")
async def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user and verify_password(user.password, db_user.hashed_password):
        request.session["user_id"] = db_user.id
        return {"message": "Login successful", "user_id": db_user.id}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/logout/")
async def logout(request: Request):
    request.session.pop("user_id", None)
    return {"message": "Logout successful"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)