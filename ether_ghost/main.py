"""
Main API service module

Provides backend APIs for the web management UI, including:
- Session management
- File transfer operations
- TCP proxy services
- PHP-related features
- System settings management
"""

import asyncio
import functools
import logging
import mimetypes
import re
import secrets
import os
import json
import hmac
import hashlib
import base64
import tempfile
import typing as t
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from contextlib import asynccontextmanager
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from uuid import UUID, uuid4

from fastapi import (
    FastAPI,
    Response,
    Request,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .utils import db

from . import (
    session_manager,
    session_types,
    session_connector,
    core,
)
from .api.connector import router as connector_router
from .api.forward_proxy import router as forward_proxy_router, tcp_forward_proxies
from .api.session import router as session_router
from .api.sessiontype import router as sessiontype_router
from .api.settings import router as settings_router
from .api.utils import router as utils_router
from .api.auth import router as auth_router
from .api.dbms import router as dbms_router


from .utils import const

token = secrets.token_bytes(16).hex()
logger = logging.getLogger("main")

# uuid: (filename, blob_path)

VERSION = "0.2.2"


class FileContentRequest(BaseModel):
    current_dir: str
    filename: str
    text: str
    encoding: str


class PhpCodeRequest(BaseModel):
    code: str


temp_dir = Path(tempfile.gettempdir())
temp_files: t.Dict[UUID, t.Tuple[str, Path]] = {}


# TODO: start all autostart connectors on boot


@asynccontextmanager
async def lifespan(api: FastAPI):
    # logger.warning("Your token is %s", token)
    db.ensure_settings()
    logger.warning("Loading settings from: %s", const.DATA_FOLDER.as_posix())

    await session_connector.autostart_connectors()

    yield

    for _, filepath in temp_files.values():
        if filepath.exists():
            filepath.unlink()
    temp_files.clear()
    for tpl in tcp_forward_proxies.values():
        server = tpl[-1]
        try:
            server.cancel()
        except asyncio.exceptions.CancelledError:
            pass
    tcp_forward_proxies.clear()


DIR = Path(__file__).parent
app = FastAPI(lifespan=lifespan)
app.mount("/public", StaticFiles(directory=DIR / "public"), name="public")
app.mount("/assets", StaticFiles(directory=DIR / "public" / "assets"), name="assets")
app.include_router(auth_router)
app.include_router(connector_router)
app.include_router(forward_proxy_router)
app.include_router(session_router)
app.include_router(sessiontype_router)
app.include_router(settings_router)
app.include_router(utils_router)
app.include_router(dbms_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allowed origins, set to all
    allow_credentials=True,  # allow credentials
    allow_methods=["*"],  # allowed HTTP methods
    allow_headers=["*"],  # allowed headers
)

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
update_check_lock = asyncio.Lock()

def _secret():
    return os.environ.get("ETHER_GHOST_SECRET", token)

def _verify_session(token_value: str) -> bool:
    try:
        if "." not in token_value:
            return False
        data_b64, sig = token_value.split(".", 1)
        raw = base64.urlsafe_b64decode(data_b64.encode())
        s = hmac.new(_secret().encode(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(base64.urlsafe_b64encode(s).decode(), sig):
            return False
        payload = json.loads(raw.decode())
        return int(payload.get("exp", 0)) >= int(asyncio.get_running_loop().time())
    except Exception:
        return False

@app.middleware("http")
async def require_auth(request: Request, call_next) -> Response:
    path = request.url.path
    allowed_equals = {
        "/",
        "/public/index.html",
        "/auth/login",
        "/auth/logout",
        "/auth/status",
        "/utils/version",
        "/utils/background_image",
    }
    allowed_prefixes = [
        "/assets/",
    ]
    if path in allowed_equals or any(path.startswith(p) for p in allowed_prefixes):
        return await call_next(request)
    token_value = request.cookies.get("eg_session", "")
    if not _verify_session(token_value):
        return Response(status_code=401, content="Unauthorized")
    return await call_next(request)


def write_temp_blob(filename: str, blob: bytes):
    filepath = temp_dir / f"{str(uuid4())}.blob"
    filepath.write_bytes(blob)
    file_id = uuid4()
    temp_files[file_id] = (filename, filepath)
    return file_id


def remote_path(filepath: str) -> PurePath:
    """Guess path type (unix/windows) and return corresponding PurePath"""
    if re.match(r"^[a-zA-Z]:[/\\]", filepath):
        return PureWindowsPath(filepath)
    return PurePosixPath(filepath)


@app.middleware("http")
async def set_no_cache(request, call_next) -> Response:
    """Prevent browser caching"""
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def catch_user_error(fn):
    @functools.wraps(fn)
    async def _wraps(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except core.SessionException as exc:
            return {
                "code": getattr(type(exc), "code", -500),
                "msg": f"{type(exc).__doc__}: {str(exc)}",
            }

    return _wraps


async def list_sessions_readable():
    result = session_manager.list_sessions_db_readable() + [
        session_manager.session_to_readable(session)
        for session in session_connector.list_sessions()
    ]
    return result


async def get_session(session_id: UUID):
    session: t.Union[session_types.SessionInfo, None] = (
        session_manager.get_session_info_by_id(session_id)
    )
    if not session:
        raise core.UserError("No such session")
    return session


@app.get("/")
async def hello_world(request: Request):
    """Redirect to homepage or login"""
    token_value = request.cookies.get("eg_session", "")
    if _verify_session(token_value):
        return RedirectResponse("/public/index.html#/")
    return RedirectResponse("/public/index.html#/login")
