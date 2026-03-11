from uuid import UUID, uuid4
import typing as t
from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    """Basic session info"""

    session_type: str
    name: str
    connection: t.Dict[str, t.Any]
    session_id: UUID = Field(default_factory=uuid4)
    note: str = ""
    location: str = ""

    class Config:
        from_attributes = True


class SessionConnectorInfo(BaseModel):
    """Pydantic model for session connector"""

    connector_type: str
    connector_id: UUID
    name: str
    note: str
    connection: t.Dict[t.Any, t.Any]
    autostart: bool

    class Config:
        from_attributes = True

class DBMSInfo(BaseModel):
    """DBMS configuration entry"""

    dbms_id: UUID = Field(default_factory=uuid4)
    name: str
    db_type: str  # mysql, postgresql, oracle, sqlserver, sqlite
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    database: str = ""
    options: t.Dict[str, t.Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
