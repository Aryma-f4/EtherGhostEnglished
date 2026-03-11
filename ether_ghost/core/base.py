"""Define session interfaces and I/O"""

import typing as t
from dataclasses import dataclass
from ..utils.user_agents import random_user_agent
from ..utils.db import get_settings

import httpx

USER_AGENT = random_user_agent()


class OptionAlternative(t.TypedDict):
    name: str
    value: str


class Option(t.TypedDict):
    id: str
    name: str
    type: t.Literal["text", "select", "checkbox"]
    placeholder: t.Union[str, None]
    default_value: t.Any
    alternatives: t.Union[t.List[OptionAlternative], None]


class OptionGroup(t.TypedDict):
    name: str
    options: t.List[Option]


@dataclass
class DirectoryEntry:
    """Information about an entry in a directory"""

    name: str
    permission: str
    filesize: int
    entry_type: t.Literal["dir", "file", "link-dir", "link-file", "unknown"] = "file"


@dataclass
class BasicInfoEntry:
    """A basic info item about a session"""

    key: str
    value: str


# Session objects are created per request and discarded immediately
# They are effectively stateless across requests


class SessionInterface:
    """Session interface"""

    session_type: t.ClassVar[str]
    readable_name: t.ClassVar[str]
    conn_options: t.ClassVar[t.List[OptionGroup]]

    async def execute_cmd(self, cmd: str) -> str:
        """Execute a command on the target"""
        raise NotImplementedError()

    async def test_usablility(self) -> bool:
        """Test session availability"""
        raise NotImplementedError()

    async def list_dir(self, dir_path: str) -> t.List[DirectoryEntry]:
        """List directory contents including . and ..; fill .. if empty"""
        raise NotImplementedError()

    async def mkdir(self, dir_path: str) -> None:
        """Create directory"""
        raise NotImplementedError()

    async def get_file_contents(
        self, filepath: str, max_size: int = 1024 * 200
    ) -> bytes:
        """Get file contents as bytes, not a decoded string"""
        raise NotImplementedError()

    async def put_file_contents(self, filepath: str, content: bytes) -> bool:
        """Save file contents as bytes, not a decoded string"""
        raise NotImplementedError()

    async def delete_file(self, filepath: str) -> bool:
        """Delete file"""
        raise NotImplementedError()

    async def move_file(self, filepath: str, new_filepath: str) -> None:
        """Move file to a new path"""
        raise NotImplementedError()

    async def copy_file(self, filepath: str, new_filepath: str) -> None:
        """Copy file to a new path"""
        raise NotImplementedError()

    async def upload_file(
        self, filepath: str, content: bytes, callback: t.Union[t.Callable, None] = None
    ) -> bool:
        """Upload file as bytes, not a decoded string"""
        raise NotImplementedError()

    async def download_file(
        self, filepath: str, callback: t.Union[t.Callable, None] = None
    ) -> bytes:
        """Download as bytes, not a decoded string"""
        raise NotImplementedError()

    async def send_bytes_over_tcp(
        self,
        host: str,
        port: int,
        content: bytes,
        send_method: t.Union[str, None] = None,
    ) -> t.Union[bytes, None]:
        """Send bytes over TCP to another host with an optional method"""
        raise NotImplementedError()

    async def get_send_tcp_support_methods(self) -> t.List[str]:
        """Return supported TCP send methods"""
        raise NotImplementedError()

    async def get_pwd(self) -> str:
        """Get current directory"""
        raise NotImplementedError()

    async def get_basicinfo(self) -> t.List[BasicInfoEntry]:
        """Get current basic info"""
        raise NotImplementedError()

    async def open_reverse_shell(self, host: str, port: int) -> None:
        """Open a reverse shell"""
        raise NotImplementedError()


class PHPSessionInterface(SessionInterface):
    """PHP Session interface"""

    async def download_phpinfo(self) -> bytes:
        """Get phpinfo file"""
        raise NotImplementedError()

    async def php_eval(self, code: str) -> str:
        """Execute code using eval"""
        raise NotImplementedError()

    async def php_eval_beforebody(self, code: str) -> t.Tuple[int, str]:
        """Execute code without wrapper

        Ensure no echo output before this, but cannot auto-extract output from HTML"""
        # ensure PHP session can open/close correctly
        raise NotImplementedError()

    async def emulated_antsword(self, body: bytes) -> t.Tuple[int, str]:
        """Parse AntSword body and return raw HTTP status code and body"""
        raise NotImplementedError()


class SessionTypeInfo(t.TypedDict):
    constructor: t.Callable[[dict], SessionInterface]
    options: t.List[OptionGroup]
    readable_name: str


session_type_info: t.Dict[str, SessionTypeInfo] = {}


def register_session(cls):
    """Decorate a session class and register a session
    Do not use this to register connector sessions
    register_connector will register the connector via another path
    """
    session_type_info[cls.session_type] = {
        "constructor": cls,
        "options": cls.conn_options,
        "readable_name": cls.readable_name,
    }
    return cls


def get_http_client(**kwargs):
    proxy = None
    if get_settings().get("proxy", None):
        proxy = get_settings().get("proxy", None)
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, proxy=proxy, **kwargs)
