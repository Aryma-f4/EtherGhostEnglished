import typing as t
import json
import re
import hashlib
import base64


from ..core import exceptions


def user_json_loads(data: str, types: t.Union[type, t.Iterable[type]]):
    if not isinstance(types, type):
        types = tuple(types)
    try:
        parsed = json.loads(data)
        if not isinstance(parsed, types):
            raise exceptions.UserError(
                f"Invalid JSON data: expected {types}, got {type(parsed)}; data={parsed!r}"
            )
        return parsed
    except json.JSONDecodeError as exc:
        raise exceptions.UserError(f"Failed to decode JSON: {data!r}") from exc


def parse_permission(perm: str):
    """Parse rwxrwxrwx permissions into numeric format like 755

    Args:
        perm (str): permission string in rwxrwxrwx format
    """
    # Ugly code ahead
    result = ""
    if not re.match("^[rwx-]{9}$", perm):
        raise ValueError("Wrong permission format: " + perm)
    nums = list(map({"r": 4, "w": 2, "x": 1, "-": 0}.__getitem__, perm))
    for i in range(0, 9, 3):
        result += str(sum(nums[i : i + 3]))
    return result


def java_repr(obj):
    if isinstance(obj, (str, int)):
        if isinstance(obj, str) and len(obj) > 1000:
            parts = ",".join(
                json.dumps(obj[i : i + 1000]) for i in range(0, len(obj), 1000)
            )
            return 'String.join("", ' + parts + ")"
        return json.dumps(obj)
    if isinstance(obj, list) and all(isinstance(x, str) for x in obj):
        return "(new String[]{" + ",".join(java_repr(x) for x in obj) + "})"
    raise NotImplementedError(f"{type(obj)=}")


def md5_encode(s):
    """Encode a string or bytes into MD5"""
    if isinstance(s, str):
        s = s.encode()
    return hashlib.md5(s).hexdigest()


def base64_encode(s: str | bytes):
    """Encode a string or bytes into base64"""
    if isinstance(s, str):
        s = s.encode("utf-8")
    return base64.b64encode(s).decode()
