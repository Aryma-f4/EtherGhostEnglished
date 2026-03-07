import os
import time
import hmac
import hashlib
import base64
import json
from typing import Tuple
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from argon2 import PasswordHasher
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

router = APIRouter()
ph = PasswordHasher()

def get_secret() -> str:
    return os.environ.get("ETHER_GHOST_SECRET", "change-this-secret")

def get_auth() -> Tuple[str, str, str]:
    user = os.environ.get("ETHER_GHOST_AUTH_USERNAME", "")
    pwd = os.environ.get("ETHER_GHOST_AUTH_PASSWORD", "")
    pwd_hash = os.environ.get("ETHER_GHOST_AUTH_PASSWORD_HASH", "")
    if not user and (pwd or pwd_hash):
        user = "admin"
    return user, pwd, pwd_hash

def sign(data: bytes) -> str:
    s = hmac.new(get_secret().encode(), data, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(s).decode()

def encode_session(username: str, ttl_seconds: int = 86400) -> str:
    payload = {
        "u": username,
        "exp": int(time.time()) + ttl_seconds,
        "n": base64.urlsafe_b64encode(os.urandom(16)).decode(),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sig = sign(raw)
    return base64.urlsafe_b64encode(raw).decode() + "." + sig

def decode_session(token: str) -> Tuple[bool, dict]:
    if "." not in token:
        return False, {}
    data_b64, sig = token.split(".", 1)
    try:
        raw = base64.urlsafe_b64decode(data_b64.encode())
        if not hmac.compare_digest(sign(raw), sig):
            return False, {}
        payload = json.loads(raw.decode())
        if payload.get("exp", 0) < int(time.time()):
            return False, {}
        return True, payload
    except Exception:
        return False, {}

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/login")
async def login(req: LoginRequest, response: Response):
    user, pwd, pwd_hash = get_auth()
    if not user or (not pwd and not pwd_hash):
        return {"code": -400, "msg": "Authentication not configured"}
    if not hmac.compare_digest(req.username, user):
        return {"code": -400, "msg": "Invalid credentials"}
    ok = False
    if pwd_hash:
        try:
            ph.verify(pwd_hash, req.password)
            ok = True
        except Exception:
            ok = False
    else:
        ok = hmac.compare_digest(req.password, pwd)
    if not ok:
        return {"code": -400, "msg": "Invalid credentials"}
    token = encode_session(user)
    secure = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        "eg_session",
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=86400,
    )
    return {"code": 0, "data": True}

@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("eg_session", path="/")
    return {"code": 0, "data": True}

@router.get("/auth/status")
async def status(request: Request):
    token = request.cookies.get("eg_session", "")
    ok, _ = decode_session(token)
    return {"code": 0, "data": ok}
