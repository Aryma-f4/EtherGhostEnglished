"""Utils API routes"""

import asyncio
import importlib.metadata
import os
import json
import logging
import re
import time
import typing as t
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from uuid import UUID
from packaging.version import Version

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..utils import const
from ..core import ServerError

from .base import temp_files

logger = logging.getLogger("main")
router = APIRouter()
update_check_lock = asyncio.Lock()

def safe_current_version() -> str:
    try:
        return importlib.metadata.version("ether_ghost")
    except Exception:
        return os.environ.get("ETHER_GHOST_VERSION", "0.0.0-dev")

def remote_path(filepath: str) -> PurePath:
    """Guess path type (unix/windows) and return corresponding PurePath"""
    if re.match(r"^[a-zA-Z]:[/\\]", filepath):
        return PureWindowsPath(filepath)
    return PurePosixPath(filepath)

async def update_info_last():
    """Get last update check result"""
    update_check_info = None
    try:
        if const.UPDATE_CHECK_FILEPATH.exists():
            update_check_info = json.loads(const.UPDATE_CHECK_FILEPATH.read_text())
    except Exception:
        update_check_info = None
        try:
            const.UPDATE_CHECK_FILEPATH.unlink()
        except Exception as exc:
            raise ServerError("Cannot read last check result and cannot delete the file") from exc
    if update_check_info is None:
        return None
    current_version = safe_current_version()
    if current_version != update_check_info["current_version"]:
        return None
    if current_version != update_check_info["new_version"]:
        logger.warning(f"New version available: {current_version} -> {update_check_info['new_version']}")
    return update_check_info

async def update_info_fetch():
    """Fetch latest version info from PyPI"""
    url = "https://pypi.org/pypi/ether-ghost/json"
    try:
        async with httpx.AsyncClient() as client:
            data = (await client.get(url)).json()
            versions = list(data["releases"].keys())
            new_version = max(versions, key=Version)
    except Exception as exc:
        raise ServerError("Cannot fetch latest version from PyPI") from exc

    current_version = safe_current_version()
    update_check_info = {
        "has_new_version": Version(new_version) > Version(current_version),
        "last_check_time": int(time.time()),
        "current_version": current_version,
        "new_version": new_version,
    }
    if current_version != update_check_info["new_version"]:
        logger.warning(f"New version available: {current_version} -> {update_check_info['new_version']}")
    try:
        const.UPDATE_CHECK_FILEPATH.write_text(json.dumps(update_check_info))
    except Exception as exc:
        raise ServerError("Cannot write file") from exc
    return update_check_info

# Utils routes
@router.get("/utils/version")
async def version():
    """Get current version"""
    current_version = safe_current_version()
    return {"code": 0, "data": current_version}

@router.get("/utils/lazy_check_update")
async def lazy_check_update():
    """Lazy update check"""
    async with update_check_lock:
        update_check_info = await update_info_last()
    if (
        update_check_info is not None
        and time.time() - update_check_info["last_check_time"]
        < const.UPDATE_CHECK_INTERVAL
    ):
        return {
            "code": 0,
            "data": {
                "lazy": True,
                "has_new_version": update_check_info.get("has_new_version", False),
                "current_version": update_check_info["current_version"],
                "new_version": update_check_info["new_version"],
            },
        }
    async with update_check_lock:
        update_check_info = await update_info_fetch()
    return {
        "code": 0,
        "data": {
            "lazy": False,
            "has_new_version": update_check_info.get("has_new_version", False),
            "current_version": update_check_info["current_version"],
            "new_version": update_check_info["new_version"],
        },
    }

@router.get("/utils/check_update")
async def check_update():
    """Force update check"""
    async with update_check_lock:
        update_check_info = await update_info_fetch()
    return {
        "code": 0,
        "data": {
            "has_new_version": update_check_info.get("has_new_version", False),
            "current_version": update_check_info["current_version"],
            "new_version": update_check_info["new_version"],
        },
    }

@router.get("/utils/background_image")
async def background_image():
    """Get background image"""
    for ext in ["png", "jpg", "webp"]:
        filepath = const.DATA_FOLDER / f"bg.{ext}"
        if filepath.exists():
            return FileResponse(path=filepath)
    raise HTTPException(status_code=404, detail="Image not found")

@router.get("/utils/fetch_downloaded_file/{file_id}")
async def fetch_downloaded_file(file_id: UUID):
    """Get downloaded file"""
    if file_id not in temp_files:
        raise HTTPException(status_code=404, detail="File not found")
    (filename, filepath) = temp_files[file_id]
    return FileResponse(path=filepath, filename=filename)

@router.get("/utils/join_path")
async def join_path(folder: str, entry: str):
    """Join path"""
    result = None
    if entry == "..":
        result = remote_path(folder).parent
    elif entry == ".":
        result = remote_path(folder)
    else:
        result = remote_path(folder) / entry
    return {"code": 0, "data": result}

@router.get("/utils/test_proxy")
async def test_proxy(proxy: str, site: str, timeout: int = 10):
    """Test proxy"""
    sites = {
        "google": "http://www.gstatic.com/generate_204",
        "cloudflare": "http://cp.cloudflare.com/",
        "microsoft": "http://www.msftconnecttest.com/connecttest.txt",
        "apple": "http://www.apple.com/library/test/success.html",
        "huawei": "http://connectivitycheck.platform.hicloud.com/generate_204",
        "xiaomi": "http://connect.rom.miui.com/generate_204",
    }
    if site not in sites:
        return {"code": -400, "msg": f"Specified server {site} not recognized"}
    try:
        async with httpx.AsyncClient(proxy=proxy) as client:
            resp = await client.get(sites[site], timeout=timeout)
            return {"code": 0, "data": resp.status_code < 300}
    except Exception:
        return {"code": -500, "msg": f"Proxy {repr(proxy)} cannot connect to {site} server"}
