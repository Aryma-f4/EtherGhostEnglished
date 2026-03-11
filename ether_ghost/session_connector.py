"""
Session connector management module

Responsibilities:
- Define SessionConnector protocol interface
- Manage connector registration and startup
- Handle session connections and lifecycle
"""

from typing import ClassVar, Protocol
import asyncio
import uuid
import logging


logger = logging.getLogger("core.session_connector")

from .utils import db
from .core import exceptions
from .core.base import SessionInterface, OptionGroup, session_type_info
from .session_types import SessionInfo

connector_sessions: dict[uuid.UUID, SessionInfo] = {}


def get_session(client_id: uuid.UUID):
    return connector_sessions.get(client_id, None)


def get_connector_of_session(client_id: uuid.UUID):
    session = get_session(client_id)
    if not session:
        return None
    connector = [
        connector
        for connector, _ in started_connectors.values()
        if connector.get_session_type() == session.session_type
    ]
    if not connector:
        return None
    return connector.pop()


def list_sessions():
    return list(connector_sessions.values())


def register_session(client_id: uuid.UUID, session_info: SessionInfo):
    connector_sessions[client_id] = session_info


def delete_session(client_id: uuid.UUID):
    connector_sessions.pop(client_id, None)


class SessionConnector(Protocol):
    connector_name: ClassVar[str]  # Internal connector name, globally unique
    connector_name_readable: ClassVar[str]  # Display name for users
    session_class: ClassVar[type[SessionInterface]]
    options: ClassVar[list[OptionGroup]]

    def __init__(self, connector_id: uuid.UUID, config: dict):
        """Provide connector_id and config for the connector instance"""
        raise NotImplementedError()

    async def run(self):
        raise NotImplementedError()

    def get_session_type(self) -> str:
        """Return session_type for the running connector
        Session info created by the connector uses this session_type"""
        raise NotImplementedError()

    # build_session and close_session receive connection config dicts
    # because session objects should not depend on name/note metadata

    def build_session(self, config: dict) -> SessionInterface:
        raise NotImplementedError()

    async def close_session(self, config: dict):
        raise NotImplementedError()


session_connectors: dict[str, type[SessionConnector]] = {}
started_connectors: dict[uuid.UUID, tuple[SessionConnector, asyncio.Task]] = {}


def register_connector(clazz: type[SessionConnector]):
    session_connectors[clazz.connector_name] = clazz
    # register session_type_info when started
    return clazz


async def start_connector(connector_id: uuid.UUID):
    if connector_id in started_connectors:
        raise exceptions.UserError(f"Connector {connector_id} already started")

    connector_info = db.get_session_connector_by_connector_id(connector_id)
    if connector_info is None:
        raise RuntimeError(f"Connector {connector_id} not found")

    clazz = session_connectors[connector_info.connector_type]
    logger.debug(f"Connector info: {connector_info.connection=}")
    connector = clazz(connector_id, connector_info.connection)
    task = asyncio.create_task(connector.run())

    started_connectors[connector_id] = (connector, task)
    session_type_info[connector.get_session_type()] = {
        "constructor": connector.build_session,
        "options": clazz.session_class.conn_options,
        "readable_name": f"{connector_info.name} {clazz.session_class.readable_name}",
    }

    return task


async def stop_connector(connector_id: uuid.UUID):
    if connector_id not in started_connectors:
        raise exceptions.UserError(f"Connector {connector_id} not started")

    connector_info = db.get_session_connector_by_connector_id(connector_id)
    if connector_info is None:
        raise exceptions.ServerError(
            f"Cannot find running connector {connector_id} in database"
        )
    connector, task = started_connectors.pop(connector_id)

    del session_type_info[connector.get_session_type()]
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def autostart_connectors():
    connectors = [
        connector.connector_id
        for connector in db.get_session_connector_all()
        if connector.autostart
    ]
    tasks = await asyncio.gather(
        *[start_connector(connector_id) for connector_id in connectors],
        return_exceptions=True,
    )
    exceptions = [task for task in tasks if isinstance(task, Exception)]
    if exceptions:
        raise ExceptionGroup("Failed to autostart connectors", exceptions)
    return tasks


async def example():
    print(f"{session_connectors=}")
    connector = session_connectors["REVERSE_SHELL"](uuid.uuid4(), {"port": 3001})
    asyncio.create_task(connector.run())
    while True:
        for session_info in list_sessions():
            print(f"{session_info=}")
            session = connector.build_session(session_info.connection)
            result = await session.execute_cmd("ls")
            print(result)
            await connector.close_session(session_info.connection)
            await asyncio.sleep(1)
        await asyncio.sleep(0)
