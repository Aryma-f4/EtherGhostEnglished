import tempfile
import subprocess
from ..core import exceptions


def nodejs_eval(code, argv):
    with tempfile.NamedTemporaryFile("w", suffix=".js") as f:
        f.write(code)
        f.flush()
        with subprocess.Popen(["node", f.name] + argv, stdout=subprocess.PIPE) as proc:
            proc.wait()
            if proc.returncode != 0:
                raise exceptions.ServerError(
                    f"NodeJS execution failed, return code {proc.returncode}"
                )
            stdout, _ = proc.communicate()
            return stdout
