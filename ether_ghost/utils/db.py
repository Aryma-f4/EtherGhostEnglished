"""Database management for session info and related data"""

import typing as t
from dataclasses import dataclass
from uuid import uuid4, UUID
import sqlalchemy as sa
from sqlalchemy_utils import UUIDType  # type: ignore
from ..session_types import SessionInfo, SessionConnectorInfo, DBMSInfo

from .const import SETTINGS_VERSION, STORE_URL

engine = sa.create_engine(STORE_URL)
OrmSession = sa.orm.sessionmaker(bind=engine)
orm_session = OrmSession()
Base = sa.orm.declarative_base()


class SessionInfoModel(Base):  # type: ignore
    """SQLAlchemy model for storing session info in the database"""

    __tablename__ = "session_info"
    record_id = sa.Column(sa.Integer, primary_key=True)
    session_type = sa.Column(sa.String)  # type: ignore
    session_id = sa.Column(UUIDType(binary=False), default=uuid4)  # type: ignore
    name = sa.Column(sa.String)
    note = sa.Column(sa.String)
    location = sa.Column(sa.String)
    connection = sa.Column(sa.JSON)


class SessionConnectorModel(Base):  # type: ignore
    """SQLAlchemy model for storing session connectors in the database"""

    __tablename__ = "session_connector"
    record_id = sa.Column(sa.Integer, primary_key=True)
    connector_type = sa.Column(sa.String)  # type: ignore
    connector_id = sa.Column(UUIDType(binary=False), default=uuid4)  # type: ignore
    name = sa.Column(sa.String)
    note = sa.Column(sa.String)
    connection = sa.Column(sa.JSON)
    autostart = sa.Column(sa.Boolean)  # run on program startup


class SettingsModel(Base):  # type: ignore
    """SQLAlchemy model for storing settings in the database"""

    __tablename__ = "settings"
    record_id = sa.Column(sa.Integer, primary_key=True)
    version = sa.Column(sa.String)
    settings = sa.Column(sa.JSON)

class DBMSInfoModel(Base):  # type: ignore
    __tablename__ = "dbms_info"
    record_id = sa.Column(sa.Integer, primary_key=True)
    dbms_id = sa.Column(UUIDType(binary=False), default=uuid4)  # type: ignore
    name = sa.Column(sa.String)
    db_type = sa.Column(sa.String)
    host = sa.Column(sa.String)
    port = sa.Column(sa.Integer)
    username = sa.Column(sa.String)
    password_enc = sa.Column(sa.String)
    database = sa.Column(sa.String)
    options = sa.Column(sa.JSON)

@dataclass
class SessionInfoModelTypeHint:
    """Type hints for SessionInfoModel
    Fixes pylint not recognizing SQLAlchemy attribute types"""

    record_id: int
    session_type: str
    session_id: UUID
    name: str
    note: str
    location: str
    connection: t.Dict[t.Any, t.Any]


@dataclass
class SessionConnectorModelTypeHint:
    """Type hints for SessionConnectorModel
    Fixes pylint not recognizing SQLAlchemy attribute types"""

    record_id: int
    connector_type: str
    connector_id: UUID
    name: str
    note: str
    connection: t.Dict[t.Any, t.Any]
    autostart: bool

@dataclass
class DBMSInfoModelTypeHint:
    record_id: int
    dbms_id: UUID
    name: str
    db_type: str
    host: str
    port: int
    username: str
    password_enc: str
    database: str
    options: t.Dict[str, t.Any]


Base.metadata.create_all(engine)


# Conversion helpers


def model_to_info(model: SessionInfoModelTypeHint) -> SessionInfo:
    """Convert SessionInfoModel (SQLAlchemy) to SessionInfo (Pydantic)"""
    connection = {**model.connection}
    result = SessionInfo(
        session_type=model.session_type,
        name=model.name,
        connection=connection,
        session_id=model.session_id,
        note=model.note,
        location=model.location,
    )
    return result


def info_to_model(info: SessionInfo) -> SessionInfoModel:
    """Convert SessionInfo (Pydantic) to SessionInfoModel (SQLAlchemy)"""
    info_dict = info.model_dump()
    return SessionInfoModel(**info_dict)


def model_to_connector(model: SessionConnectorModelTypeHint) -> SessionConnectorInfo:
    """Convert SessionConnectorModel (SQLAlchemy) to SessionConnector (Pydantic)"""
    connection = {**model.connection}
    result = SessionConnectorInfo(
        connector_type=model.connector_type,
        name=model.name,
        connection=connection,
        connector_id=model.connector_id,
        note=model.note,
        autostart=model.autostart,
    )
    return result


def connector_to_model(connector: dict) -> SessionConnectorModel:
    """Convert dict to SessionConnectorModel (SQLAlchemy)"""
    return SessionConnectorModel(**connector)

def _derive_key_from_secret() -> bytes:
    import hashlib, os
    secret = os.environ.get("ETHER_GHOST_SECRET", "change-this-secret")
    return hashlib.sha256(secret.encode()).digest()

def _enc_password(plain: str) -> str:
    from ..utils.cipher import encrypt_aes256_cbc
    key = _derive_key_from_secret()
    import base64
    return base64.b64encode(encrypt_aes256_cbc(key, plain.encode())).decode()

def _dec_password(enc: str) -> str:
    from ..utils.cipher import decrypt_aes256_cbc
    key = _derive_key_from_secret()
    import base64
    return decrypt_aes256_cbc(key, base64.b64decode(enc.encode())).decode()

def dbms_model_to_info(model: DBMSInfoModelTypeHint) -> DBMSInfo:
    return DBMSInfo(
        dbms_id=model.dbms_id,
        name=model.name,
        db_type=model.db_type,
        host=model.host,
        port=model.port,
        username=model.username,
        password=_dec_password(model.password_enc) if model.password_enc else "",
        database=model.database,
        options=model.options or {},
    )

def dbms_info_to_model(info: DBMSInfo) -> DBMSInfoModel:
    data = info.model_dump()
    data["password_enc"] = _enc_password(data.pop("password", ""))
    return DBMSInfoModel(**data)

# Database operations


# TODO: list session by created time
def list_sessions() -> t.List[SessionInfo]:
    """List all sessions in the database"""
    return [model_to_info(model) for model in orm_session.query(SessionInfoModel).all()]


def add_session_info(info: SessionInfo):
    """Add a session"""
    orm_session.add(info_to_model(info))
    orm_session.commit()


def add_session_infos(infos: t.List[SessionInfo]):
    """Add multiple sessions in batch"""
    models = [info_to_model(info) for info in infos]
    orm_session.add_all(models)
    orm_session.commit()


def get_session_info_by_id(
    session_id: t.Union[str, UUID],
) -> t.Union[None, SessionInfo]:
    """Get session by ID and return session info"""
    if isinstance(session_id, str):
        session_id = UUID(session_id)
    model = (
        orm_session.query(SessionInfoModel)
        .filter(SessionInfoModel.session_id == session_id)
        .first()
    )
    if model is None:
        return None
    return model_to_info(model)


def delete_session_info_by_id(
    session_id: t.Union[str, UUID], ignore_unexist=False
) -> bool:
    """Get session by ID and delete it"""
    if isinstance(session_id, str):
        session_id = UUID(session_id)
    model = (
        orm_session.query(SessionInfoModel)
        .filter(SessionInfoModel.session_id == session_id)
        .first()
    )
    if model is None:
        return ignore_unexist  # True if ignore_unexist else False
    orm_session.delete(model)
    orm_session.commit()
    return True


def get_session_by_session_type(session_type: str) -> t.List[SessionInfo]:
    """Get all sessions by session_type"""
    models = (
        orm_session.query(SessionInfoModel)
        .filter(SessionInfoModel.session_type == session_type)
        .all()
    )
    return [model_to_info(model) for model in models]


def delete_session_by_session_type(session_type: str) -> int:
    """Delete sessions by session_type and return the count"""
    models = (
        orm_session.query(SessionInfoModel)
        .filter(SessionInfoModel.session_type == session_type)
        .all()
    )
    count = len(models)
    for model in models:
        orm_session.delete(model)
    if count > 0:
        orm_session.commit()
    return count


def list_session_connectors() -> t.List[SessionConnectorInfo]:
    """List all session connectors in the database"""
    return [
        model_to_connector(model)
        for model in orm_session.query(SessionConnectorModel).all()
    ]


def add_session_connector(connector: SessionConnectorInfo):
    """Add a session connector"""
    orm_session.add(connector_to_model(connector.model_dump()))
    orm_session.commit()


def add_session_connectors(connectors: t.List[SessionConnectorInfo]):
    """Add multiple session connectors in batch"""
    models = [connector_to_model(connector.model_dump()) for connector in connectors]
    orm_session.add_all(models)
    orm_session.commit()

def get_session_connector_all() -> t.List[SessionConnectorInfo]:
    """Get all session connectors"""
    models = orm_session.query(SessionConnectorModel).all()
    return [model_to_connector(model) for model in models]

def get_session_connector_by_connector_id(
    connector_id: t.Union[str, UUID],
) -> t.Union[None, SessionConnectorInfo]:
    """Get session connector by connector_id"""
    if isinstance(connector_id, str):
        connector_id = UUID(connector_id)
    model = (
        orm_session.query(SessionConnectorModel)
        .filter(SessionConnectorModel.connector_id == connector_id)
        .first()
    )
    if model is None:
        return None
    return model_to_connector(model)


def update_session_connector(connector: SessionConnectorInfo) -> bool:
    """Update session connector by connector_id"""
    connector_id = connector.connector_id
    if isinstance(connector_id, str):
        connector_id = UUID(connector_id)
    model = (
        orm_session.query(SessionConnectorModel)
        .filter(SessionConnectorModel.connector_id == connector_id)
        .first()
    )
    if model is None:
        return False
    data = connector.model_dump()
    for key, value in data.items():
        if hasattr(model, key):
            setattr(model, key, value)
    orm_session.commit()
    return True


def delete_session_connector_by_connector_id(
    connector_id: t.Union[str, UUID], ignore_unexist=False
) -> bool:
    """Delete session connector by connector_id"""
    if isinstance(connector_id, str):
        connector_id = UUID(connector_id)
    model = (
        orm_session.query(SessionConnectorModel)
        .filter(SessionConnectorModel.connector_id == connector_id)
        .first()
    )
    if model is None:
        return ignore_unexist
    orm_session.delete(model)
    orm_session.commit()
    return True


def get_settings() -> dict:
    """Get current settings"""
    model = orm_session.query(SettingsModel).first()
    if model is None:
        return {}
    assert model.version == SETTINGS_VERSION, (
        "The version of the settings is not supported!"
        + " Did you load a newer settings?"
    )
    return model.settings


def set_settings(settings: dict):
    model = orm_session.query(SettingsModel).first()
    if model:
        orm_session.delete(model)
    orm_session.add(SettingsModel(version=SETTINGS_VERSION, settings=settings))
    orm_session.commit()


def ensure_settings():
    """Ensure settings exist; write defaults if missing"""
    default_settings = {"theme": "green", "proxy": ""}
    if not get_settings():
        set_settings(default_settings)

# -------- DBMS management --------
def list_dbms() -> t.List[DBMSInfo]:
    models = orm_session.query(DBMSInfoModel).all()
    return [dbms_model_to_info(model) for model in models]

def add_or_update_dbms(info: DBMSInfo) -> DBMSInfo:
    dbms_id = info.dbms_id
    if isinstance(dbms_id, str):
        dbms_id = UUID(dbms_id)
    model = (
        orm_session.query(DBMSInfoModel)
        .filter(DBMSInfoModel.dbms_id == dbms_id)
        .first()
    )
    if model is None:
        orm_session.add(dbms_info_to_model(info))
    else:
        data = info.model_dump()
        for key, value in data.items():
            if key == "password":
                setattr(model, "password_enc", _enc_password(value))
            elif hasattr(model, key):
                setattr(model, key, value)
    orm_session.commit()
    model = (
        orm_session.query(DBMSInfoModel)
        .filter(DBMSInfoModel.dbms_id == info.dbms_id)
        .first()
    )
    return dbms_model_to_info(model)  # type: ignore

def delete_dbms(dbms_id: t.Union[str, UUID]) -> bool:
    if isinstance(dbms_id, str):
        dbms_id = UUID(dbms_id)
    model = (
        orm_session.query(DBMSInfoModel)
        .filter(DBMSInfoModel.dbms_id == dbms_id)
        .first()
    )
    if model is None:
        return False
    orm_session.delete(model)
    orm_session.commit()
    return True
