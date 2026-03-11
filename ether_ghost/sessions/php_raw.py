import typing as t
import logging
import base64

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

logger = logging.getLogger("core.sessions.php_raw")


def base64_encode(s):
    """Encode a string or bytes into base64"""
    if isinstance(s, str):
        s = s.encode("utf-8")
    return base64.b64encode(s).decode()


@register_session
class PHPWebshellRaw(PHPWebshellCommunication, PHPWebshellActions):
    session_type = "PHP_RAW"
    readable_name = "PHP Raw"
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
        self.https_verify = session_conn.get("https_verify", False)
        self.client = get_http_client(verify=self.https_verify)
        self.timeout_refresh_client = session_conn.get("timeout_refresh_client", True)

    async def php_eval_beforebody(self, code: str) -> t.Tuple[int, str]:
        return await self.submit_http(code)

    async def submit_http(self, payload: t.Union[str, bytes]):
        try:
            response = await self.client.request(
                method="POST", url=self.url, content=payload
            )
            return response.status_code, response.text
        except httpx.TimeoutException as exc:
            if self.timeout_refresh_client:
                logger.warning("HTTP request to target timed out; refreshing HTTP client")
                self.client = get_http_client(verify=self.https_verify)
            raise exceptions.NetworkError("HTTP request to target timed out") from exc
        except httpx.HTTPError as exc:
            raise exceptions.NetworkError("Failed to send HTTP request to target: " + str(exc)) from exc
