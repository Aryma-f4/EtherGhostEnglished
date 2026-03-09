import socket
from uuid import UUID
import typing as t
from fastapi import APIRouter
from pydantic import BaseModel

from ..utils import db
from ..session_types import DBMSInfo

router = APIRouter()

class DBMSRequest(BaseModel):
    dbms_id: t.Union[str, UUID, None] = None
    name: str
    db_type: str
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    database: str = ""
    options: t.Dict[str, t.Any] = {}

@router.get("/dbms")
async def list_dbms():
    items = db.list_dbms()
    safe_items = []
    for x in items:
        d = x.model_dump()
        d["password"] = ""
        safe_items.append(d)
    return {"code": 0, "data": safe_items}

@router.post("/dbms")
async def add_or_update_dbms(info: DBMSRequest):
    payload = info.model_dump()
    if payload.get("dbms_id") is None:
        payload.pop("dbms_id", None)
    db_info = DBMSInfo(**payload)
    saved = db.add_or_update_dbms(db_info)
    return {"code": 0, "data": saved}

@router.delete("/dbms/{dbms_id}")
async def delete_dbms(dbms_id: UUID):
    ok = db.delete_dbms(dbms_id)
    return {"code": 0, "data": ok}

@router.get("/dbms/{dbms_id}/test")
async def test_dbms(dbms_id: UUID, timeout: int = 5):
    infos = [x for x in db.list_dbms() if x.dbms_id == dbms_id]
    if not infos:
        return {"code": -400, "msg": "No such DBMS"}
    info = infos[0]
    db_type = info.db_type.lower()
    if db_type == "sqlite":
        import os
        try:
            import sqlalchemy as sa
            engine = sa.create_engine(f"sqlite:///{info.database}")
            with engine.connect() as conn:
                result = conn.execute(sa.text("SELECT 1")).scalar()
            return {"code": 0, "data": bool(result)}
        except Exception:
            return {"code": 0, "data": os.path.exists(info.database)}
    def tcp_test():
        try:
            with socket.create_connection((info.host, int(info.port)), timeout=timeout):
                return True
        except Exception:
            return False
    try:
        import sqlalchemy as sa
        from sqlalchemy.engine import URL
        if db_type == "mysql":
            url = URL.create(
                "mysql+pymysql",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=info.database or None,
            )
        elif db_type == "postgresql":
            url = URL.create(
                "postgresql+psycopg",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=info.database or None,
            )
        elif db_type == "oracle":
            dsn = info.database or ""
            url = URL.create(
                "oracle+oracledb",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=dsn or None,
            )
        elif db_type == "sqlserver":
            url = URL.create(
                "mssql+pyodbc",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=info.database or None,
                query={"driver": info.options.get("driver", "ODBC Driver 17 for SQL Server")},
            )
        else:
            return {"code": -400, "msg": f"Unsupported db_type: {info.db_type}"}
        engine = sa.create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(sa.text("SELECT 1")).scalar()
        return {"code": 0, "data": bool(result)}
    except Exception:
        return {"code": 0, "data": tcp_test()}
def _get_info(dbms_id: UUID) -> t.Union[DBMSInfo, None]:
    infos = [x for x in db.list_dbms() if x.dbms_id == dbms_id]
    return infos[0] if infos else None

def _get_engine(info: DBMSInfo):
    import sqlalchemy as sa
    from sqlalchemy.engine import URL
    tname = info.db_type.lower()
    if tname == "sqlite":
        return sa.create_engine(f"sqlite:///{info.database}")
    if tname == "mysql":
        return sa.create_engine(
            URL.create(
                "mysql+pymysql",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=info.database or None,
            )
        )
    if tname == "postgresql":
        return sa.create_engine(
            URL.create(
                "postgresql+psycopg",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=info.database or None,
            )
        )
    if tname == "oracle":
        return sa.create_engine(
            URL.create(
                "oracle+oracledb",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=info.database or None,
            )
        )
    if tname == "sqlserver":
        return sa.create_engine(
            URL.create(
                "mssql+pyodbc",
                username=info.username or None,
                password=info.password or None,
                host=info.host,
                port=int(info.port),
                database=info.database or None,
                query={"driver": info.options.get("driver", "ODBC Driver 17 for SQL Server")},
            )
        )
    raise RuntimeError("Unsupported db_type")

class SQLRequest(BaseModel):
    sql: str
    params: t.Dict[str, t.Any] = {}
    max_rows: int = 200
    schema: t.Union[str, None] = None

class DeleteRequest(BaseModel):
    schema: t.Union[str, None] = None
    table: str
    keys: t.List[t.Dict[str, t.Any]] = []
    where: t.Dict[str, t.Any] = {}

class UpdateRequest(BaseModel):
    schema: t.Union[str, None] = None
    table: str
    key: t.Dict[str, t.Any]
    values: t.Dict[str, t.Any]
@router.get("/dbms/{dbms_id}/schemas")
async def list_schemas(dbms_id: UUID):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        insp = sa.inspect(engine)
        schemas = insp.get_schema_names()
        return {"code": 0, "data": schemas}
    except Exception as e:
        return {"code": -500, "msg": str(e)}

@router.get("/dbms/{dbms_id}/tables")
async def list_tables(dbms_id: UUID, schema: t.Union[str, None] = None):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        insp = sa.inspect(engine)
        tables = insp.get_table_names(schema=schema)
        return {"code": 0, "data": tables}
    except Exception as e:
        return {"code": -500, "msg": str(e)}

@router.get("/dbms/{dbms_id}/columns")
async def list_columns(dbms_id: UUID, schema: t.Union[str, None] = None, table: str = ""):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        insp = sa.inspect(engine)
        cols = insp.get_columns(table, schema=schema)
        return {"code": 0, "data": cols}
    except Exception as e:
        return {"code": -500, "msg": str(e)}

@router.get("/dbms/{dbms_id}/primary_key")
async def primary_key(dbms_id: UUID, schema: t.Union[str, None] = None, table: str = ""):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        insp = sa.inspect(engine)
        pk = insp.get_pk_constraint(table, schema=schema)
        cols = pk.get("constrained_columns") or []
        return {"code": 0, "data": cols}
    except Exception as e:
        return {"code": -500, "msg": str(e)}

@router.post("/dbms/{dbms_id}/query")
async def run_query(dbms_id: UUID, req: SQLRequest):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        with engine.begin() as conn:
            # set current schema/database if provided
            if req.schema:
                tname = info.db_type.lower()
                if tname == "mysql":
                    conn.exec_driver_sql(f"USE `{req.schema}`")
                elif tname == "postgresql":
                    conn.exec_driver_sql(f"SET search_path TO {req.schema}")
                elif tname == "sqlserver":
                    conn.exec_driver_sql(f"USE [{req.schema}]")
                elif tname == "oracle":
                    conn.exec_driver_sql(f"ALTER SESSION SET CURRENT_SCHEMA = {req.schema}")
            result = conn.execute(sa.text(req.sql), req.params)
            if getattr(result, "returns_rows", False):
                rows = result.fetchmany(req.max_rows)
                cols = list(result.keys())
                rows_json = [dict(getattr(r, "_mapping", {})) for r in rows]
                return {"code": 0, "data": {"columns": cols, "rows": rows_json, "rowcount": len(rows_json)}}
            return {"code": 0, "data": {"rowcount": result.rowcount}}
    except Exception as e:
        return {"code": -500, "msg": str(e)}

@router.post("/dbms/{dbms_id}/delete")
async def delete_rows(dbms_id: UUID, req: DeleteRequest):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        metadata = sa.MetaData()
        table = sa.Table(req.table, metadata, autoload_with=engine, schema=req.schema)
        deleted = 0
        with engine.begin() as conn:
            if req.keys:
                for key in req.keys:
                    conds = [table.c[col] == key[col] for col in key.keys() if col in table.c]
                    if not conds:
                        continue
                    stmt = sa.delete(table).where(sa.and_(*conds))
                    result = conn.execute(stmt)
                    deleted += result.rowcount or 0
            elif req.where:
                conds = [table.c[col] == req.where[col] for col in req.where.keys() if col in table.c]
                if conds:
                    stmt = sa.delete(table).where(sa.and_(*conds))
                    result = conn.execute(stmt)
                    deleted += result.rowcount or 0
        return {"code": 0, "data": {"deleted": deleted}}
    except Exception as e:
        return {"code": -500, "msg": str(e)}

@router.post("/dbms/{dbms_id}/update")
async def update_row(dbms_id: UUID, req: UpdateRequest):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        metadata = sa.MetaData()
        table = sa.Table(req.table, metadata, autoload_with=engine, schema=req.schema)
        conds = [table.c[col] == req.key[col] for col in req.key.keys() if col in table.c]
        if not conds:
            return {"code": -400, "msg": "Invalid key"}
        values = {k: v for k, v in req.values.items() if k in table.c}
        if not values:
            return {"code": -400, "msg": "No values to update"}
        with engine.begin() as conn:
            stmt = sa.update(table).where(sa.and_(*conds)).values(**values)
            result = conn.execute(stmt)
        return {"code": 0, "data": {"updated": result.rowcount or 0}}
    except Exception as e:
        return {"code": -500, "msg": str(e)}

@router.get("/dbms/{dbms_id}/grants")
async def get_grants(dbms_id: UUID):
    info = _get_info(dbms_id)
    if info is None:
        return {"code": -400, "msg": "No such DBMS"}
    try:
        import sqlalchemy as sa
        engine = _get_engine(info)
        tname = info.db_type.lower()
        with engine.begin() as conn:
            if tname == "mysql":
                user = conn.execute(sa.text("SELECT CURRENT_USER()")).scalar()
                rows = conn.execute(sa.text("SHOW GRANTS FOR CURRENT_USER()")).fetchall()
                grants = [r[0] for r in rows]
            elif tname == "postgresql":
                user = conn.execute(sa.text("SELECT current_user")).scalar()
                rows = conn.execute(sa.text("""
                    SELECT table_schema, table_name, privilege_type
                    FROM information_schema.table_privileges
                    WHERE grantee = current_user
                    ORDER BY table_schema, table_name
                """)).fetchall()
                grants = [f"{r[0]}.{r[1]}: {r[2]}" for r in rows]
            elif tname == "sqlserver":
                user = conn.execute(sa.text("SELECT USER_NAME()")).scalar()
                rows = conn.execute(sa.text("SELECT permission_name, state_desc FROM fn_my_permissions(NULL, 'DATABASE')")).fetchall()
                grants = [f"{r[0]} ({r[1]})" for r in rows]
            elif tname == "oracle":
                user = conn.execute(sa.text("SELECT USER FROM dual")).scalar()
                rows = conn.execute(sa.text("SELECT privilege FROM USER_SYS_PRIVS")).fetchall()
                grants = [r[0] for r in rows]
            elif tname == "sqlite":
                user = "sqlite"
                grants = ["SQLite does not support GRANT/REVOKE per connection"]
            else:
                user = ""
                grants = []
        return {"code": 0, "data": {"user": user, "grants": grants}}
    except Exception as e:
        return {"code": -500, "msg": str(e)}
