"""
Unified Session Management Module

Manages two core objects:
1. SessionInfo - stores session metadata (name, note) and connection config
2. Session - concrete implementation of SessionInterface constructed from SessionInfo

Primary functions:
- CRUD operations for SessionInfo
- Cache and lifecycle management for Session objects
- Conversions between the two object types
"""

import time
import typing as t
from uuid import UUID

from .utils import db
from . import core, session_connector
from .core.base import session_type_info
from .session_types import (
    SessionInfo,
)

SESSION_CACHE_TIMEOUT = 300
session_store: t.Dict[UUID, t.Tuple[int, core.SessionInterface]] = {}
location_readable = {"US": "🇺🇸"}


def session_info_to_session(session_info: SessionInfo) -> core.SessionInterface:
    """将session info转成session对象

    Args:
        session_info (SessionInfo): session info

    Returns:
        session.Session: session对象
    """
    if session_info.session_type not in session_type_info:
        raise core.UserError(f"Session类型{session_info.session_type}不存在")
    constructor = session_type_info[session_info.session_type]["constructor"]
    return constructor(session_info.connection)


def get_session_info_by_id(
    session_id: t.Union[str, UUID],
) -> t.Union[None, SessionInfo]:
    """根据id返回session info

    Args:
        session_id (t.Union[str, UUID]): session id

    Returns:
        t.Union[None, SessionInfo]: session info，找不到时返回None
    """
    if isinstance(session_id, str):
        session_id = UUID(session_id)
    result = db.get_session_info_by_id(session_id)
    if result is not None:
        return result
    return session_connector.get_session(session_id)


def get_session_by_id(session_id: t.Union[str, UUID]) -> core.SessionInterface:
    """根据id返回session对象，优先返回缓存的对象

    Args:
        session_id (t.Union[str, UUID]): session id

    Returns:
        t.Union[None, session.Session]: session对象，找不到时返回None
    """
    if isinstance(session_id, str):
        session_id = UUID(session_id)
    cache_timeout_sessions = [
        uuid
        for uuid, (timestamp, _) in session_store.items()
        if timestamp + SESSION_CACHE_TIMEOUT < time.time()
    ]
    for uuid in cache_timeout_sessions:
        del session_store[uuid]
    if session_id in session_store:
        _, session = session_store[session_id]
        session_store[session_id] = (int(time.time()), session)
        return session

    session_info = get_session_info_by_id(session_id)
    if session_info is None:
        raise core.UserError("No Session associated with this UUID")
    session = session_info_to_session(session_info)
    session_store[session_id] = (int(time.time()), session)
    return session


def clear_session_cache():
    session_store.clear()


def session_to_readable(sess: SessionInfo) -> t.Dict[str, t.Any]:
    """将SessionInfo对象转换为可读的字典"""
    return {
        "type": sess.session_type,
        "readable_type": session_type_info[sess.session_type]["readable_name"],
        "id": sess.session_id,
        "name": sess.name,
        "note": sess.note or "No note",
        "location": location_readable.get(sess.location, "Unknown location"),
    }


def list_sessions_db_readable() -> t.List[t.Dict[str, t.Any]]:
    """列出所有的session info（可读格式）"""
    return [session_to_readable(sess) for sess in db.list_sessions()]


def add_session_info(info: SessionInfo):
    """将session info添加到数据库"""
    db.add_session_info(info)


async def delete_session_info_by_id(session_id: UUID):
    """根据session id删除某个session
    如果是Connector的session则通知connector关闭，否则从数据库中删除"""
    if connector := session_connector.get_connector_of_session(session_id):
        session_info = get_session_info_by_id(session_id)
        assert (
            session_info is not None
        ), "Internal error: we should get session info when finding its connector"
        try:
            await connector.close_session(session_info.connection)
        except Exception:
            session_connector.delete_session(session_id)
    db.delete_session_info_by_id(session_id, ignore_unexist=True)
    session_store.pop(session_id, None)
