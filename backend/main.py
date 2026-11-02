from __future__ import annotations

import os
import re
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, DateTime, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-this-secret-key-32chars")
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 8
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "academyadmin").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
if not os.getenv("ADMIN_PASSWORD"):
    print(f"[ACADEMY UZ] ADMIN_PASSWORD berilmagan. Vaqtinchalik admin paroli: {ADMIN_PASSWORD}")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "100")) * 1024 * 1024
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'academy.db').as_posix()}")

ALLOWED_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "image/gif": {".gif"},
    "video/mp4": {".mp4"},
    "video/webm": {".webm"},
    "video/quicktime": {".mov"},
    "application/pdf": {".pdf"},
}

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # superadmin|manager|teacher|student
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    data: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgres://")
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgresql://")
engine_args = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True, "pool_recycle": 300}
engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ACADEMY UZ API", version="1.0.0", description="ACADEMY UZ backend and media API")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000,null").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?", allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper() or "U"

ROLE_LABEL = {"superadmin": "Admin", "manager": "Menejer", "teacher": "Ustoz", "student": "O'quvchi"}
CREATABLE = {"superadmin": {"superadmin", "manager", "teacher", "student"}, "manager": {"manager", "teacher", "student"}}

def public(u: User) -> dict:
    return {"id": u.id, "username": u.username, "name": u.name, "email": u.email, "role": u.role,
            "initials": initials(u.name), "subtitle": ROLE_LABEL.get(u.role, u.role), "academy": "ACADEMY UZ"}

with SessionLocal() as _db:  # seed the first administrator from .env (only if no users exist)
    if not _db.scalar(select(User).limit(1)):
        _db.add(User(username=ADMIN_USERNAME, password_hash=hash_password(ADMIN_PASSWORD), name="ACADEMY UZ Admin",
                     email="admin@academy.uz", role="superadmin"))
        _db.commit()

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=TOKEN_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from fastapi import Header

def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Tizimga kiring")
    try:
        payload = jwt.decode(authorization.removeprefix("Bearer ").strip(), SECRET_KEY, algorithms=[ALGORITHM])
        user = db.get(User, int(payload.get("sub")))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Sessiya tugagan, qayta kiring")
    if not user:
        raise HTTPException(status_code=401, detail="Hisob topilmadi")
    return user

def staff(user: User = Depends(current_user)) -> User:
    if user.role not in CREATABLE:
        raise HTTPException(status_code=403, detail="Bu amal uchun ruxsat yo'q")
    return user

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=200)
    role: str
    email: str = Field(default="", max_length=160)

class UserEdit(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str | None = Field(default=None, max_length=160)
    password: str | None = Field(default=None, min_length=6, max_length=200)
    current_password: str | None = None
    role: str | None = None

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ACADEMY UZ API", "time": datetime.now(timezone.utc).isoformat()}

@app.post("/api/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": public(user)}

@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return public(user)

@app.patch("/api/me")
def edit_me(body: UserEdit, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Every user edits own name, email, login and password (login/password change needs the current password)."""
    if (body.username or body.password) and not (body.current_password and verify_password(body.current_password, user.password_hash)):
        raise HTTPException(status_code=403, detail="Joriy parol noto'g'ri")
    if body.username:
        uname = body.username.lower()
        if uname != user.username and db.scalar(select(User).where(User.username == uname)):
            raise HTTPException(status_code=409, detail="Bu login band")
        user.username = uname
    if body.name: user.name = body.name.strip()
    if body.email is not None: user.email = body.email.strip()
    if body.password: user.password_hash = hash_password(body.password)
    db.commit()
    return public(user)

@app.get("/api/users")
def list_users(db: Session = Depends(get_db), _u: User = Depends(staff)):
    return [public(x) | {"created_at": x.created_at.isoformat() if x.created_at else None} for x in db.scalars(select(User).order_by(User.id)).all()]

@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), actor: User = Depends(staff)):
    if body.role not in CREATABLE[actor.role]:
        raise HTTPException(status_code=403, detail="Bu rolni yaratishga ruxsat yo'q")
    uname = body.username.lower()
    if db.scalar(select(User).where(User.username == uname)):
        raise HTTPException(status_code=409, detail="Bu login band")
    u = User(username=uname, password_hash=hash_password(body.password), name=body.name.strip(), email=body.email.strip(), role=body.role)
    db.add(u); db.commit(); db.refresh(u)
    return public(u)

@app.patch("/api/users/{user_id}")
def edit_user(user_id: int, body: UserEdit, db: Session = Depends(get_db), actor: User = Depends(staff)):
    u = db.get(User, user_id)
    if not u: raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if actor.role == "manager" and u.role == "superadmin":
        raise HTTPException(status_code=403, detail="Adminni tahrirlash mumkin emas")
    if body.role and body.role not in CREATABLE[actor.role]:
        raise HTTPException(status_code=403, detail="Bu rolga ruxsat yo'q")
    if body.username and body.username.lower() != u.username:
        if db.scalar(select(User).where(User.username == body.username.lower())):
            raise HTTPException(status_code=409, detail="Bu login band")
        u.username = body.username.lower()
    if body.name: u.name = body.name.strip()
    if body.email is not None: u.email = body.email.strip()
    if body.role: u.role = body.role
    if body.password: u.password_hash = hash_password(body.password)
    db.commit()
    return public(u)

@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(staff)):
    u = db.get(User, user_id)
    if not u: raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if u.id == actor.id: raise HTTPException(status_code=400, detail="O'zingizni o'chira olmaysiz")
    if actor.role == "manager" and u.role == "superadmin": raise HTTPException(status_code=403, detail="Adminni o'chirish mumkin emas")
    db.delete(u); db.commit()

@app.get("/api/media")
def list_media(db: Session = Depends(get_db), _admin: User = Depends(current_user)):
    items = db.scalars(select(MediaAsset).order_by(MediaAsset.created_at.desc())).all()
    return [{"id": x.id, "title": x.title, "description": x.description, "url": f"/uploads/{x.filename}", "original_name": x.original_name, "media_type": x.media_type, "mime_type": x.mime_type, "size_bytes": x.size_bytes, "created_at": x.created_at.isoformat() if x.created_at else None} for x in items]

@app.post("/api/media", status_code=201)
async def upload_media(
    title: str = Form(...),
    description: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(staff),
):
    title = title.strip()
    if not title or len(title) > 180:
        raise HTTPException(status_code=400, detail="Sarlavha 1–180 belgi bo‘lishi kerak")
    mime = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if mime not in ALLOWED_TYPES or suffix not in ALLOWED_TYPES[mime]:
        raise HTTPException(status_code=415, detail="Faqat JPG, PNG, WEBP, GIF, MP4, WEBM, MOV yoki PDF fayllari ruxsat etiladi")
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_DIR / stored_name
    total = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"Fayl hajmi {MAX_UPLOAD_BYTES // (1024*1024)} MB dan oshmasligi kerak")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    kind = "image" if mime.startswith("image/") else "video" if mime.startswith("video/") else "document"
    item = MediaAsset(title=title, description=description.strip()[:2000], filename=stored_name,
                      original_name=Path(file.filename or "file").name[:255], media_type=kind,
                      mime_type=mime, size_bytes=total)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "title": item.title, "description": item.description, "url": f"/uploads/{item.filename}", "media_type": item.media_type, "mime_type": item.mime_type, "size_bytes": item.size_bytes}

@app.delete("/api/media/{media_id}", status_code=204)
def delete_media(media_id: int, db: Session = Depends(get_db), _admin: User = Depends(staff)):
    item = db.get(MediaAsset, media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media topilmadi")
    (UPLOAD_DIR / item.filename).unlink(missing_ok=True)
    db.delete(item)
    db.commit()
    return None


# ---------- generic records: students, teachers, groups, courses, payments, leads, announcements, homework ----------
import json
ALL_KINDS = {"students", "teachers", "groups", "courses", "payments", "leads", "announcements", "homework"}
READ = {"superadmin": ALL_KINDS, "manager": ALL_KINDS,
        "teacher": {"students", "groups", "courses", "homework", "announcements"},
        "student": {"courses", "homework", "announcements", "groups"}}
WRITE = {"superadmin": ALL_KINDS, "manager": ALL_KINDS, "teacher": {"homework", "announcements"}, "student": set()}

class RecordBody(BaseModel):
    data: dict

def rec_out(r: Record) -> dict:
    try: d = json.loads(r.data)
    except ValueError: d = {}
    return {"id": r.id, "kind": r.kind, **d}

def clean(d: dict) -> str:
    out = {k: str(v)[:300] for k, v in d.items() if k in {"name", "email", "group", "score", "status", "details"}}
    if not str(out.get("name", "")).strip(): raise HTTPException(status_code=400, detail="Nomi kiritilishi shart")
    return json.dumps(out, ensure_ascii=False)

def need(user: User, kind: str, write: bool):
    if kind not in ALL_KINDS: raise HTTPException(status_code=404, detail="Bo'lim topilmadi")
    if kind not in (WRITE if write else READ)[user.role]: raise HTTPException(status_code=403, detail="Ruxsat yo'q")

@app.get("/api/records/{kind}")
def rec_list(kind: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    need(user, kind, False)
    return [rec_out(r) for r in db.scalars(select(Record).where(Record.kind == kind).order_by(Record.id.desc())).all()]

@app.post("/api/records/{kind}", status_code=201)
def rec_create(kind: str, body: RecordBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    need(user, kind, True)
    r = Record(kind=kind, data=clean(body.data), created_by=user.id); db.add(r); db.commit(); db.refresh(r)
    return rec_out(r)

@app.patch("/api/records/{kind}/{rid}")
def rec_edit(kind: str, rid: int, body: RecordBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    need(user, kind, True)
    r = db.get(Record, rid)
    if not r or r.kind != kind: raise HTTPException(status_code=404, detail="Topilmadi")
    r.data = clean({**json.loads(r.data), **body.data}); db.commit()
    return rec_out(r)

@app.delete("/api/records/{kind}/{rid}", status_code=204)
def rec_delete(kind: str, rid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    need(user, kind, True)
    r = db.get(Record, rid)
    if r and r.kind == kind: db.delete(r); db.commit()

class Apply(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=30)
    course: str = Field(default="", max_length=100)

@app.post("/api/public/apply", status_code=201)
def apply(body: Apply, db: Session = Depends(get_db)):
    """Public landing-page form -> becomes a lead in the manager's CRM."""
    db.add(Record(kind="leads", data=json.dumps({"name": body.name.strip(), "email": body.phone.strip(), "group": body.course or "Kurs tanlanmagan", "score": "Yangi", "status": "Kutilmoqda"}, ensure_ascii=False)))
    db.commit()
    return {"ok": True}

@app.get("/api/public/courses")
def public_courses(db: Session = Depends(get_db)):
    return [rec_out(r) for r in db.scalars(select(Record).where(Record.kind == "courses").order_by(Record.id)).all()]


# ---------- serve the website itself from the same server (one port, no CORS problems) ----------
from fastapi.responses import FileResponse
SITE_DIR = BASE_DIR.parent
for _route, _file in {"/": "index.html", "/index.html": "index.html", "/app.html": "app.html", "/app.js": "app.js", "/styles.css": "styles.css"}.items():
    app.add_api_route(_route, (lambda f=_file: FileResponse(SITE_DIR / f)), methods=["GET"], include_in_schema=False)
