"""Exceptions raised during session operations"""


class SessionException(Exception):
    """Errors raised when using sessions"""


class UserError(SessionException):
    """User operation error"""

    code = -400


class ServerError(SessionException):
    """Server runtime error"""

    code = -500


class UnknownError(ServerError):
    """Unknown error"""


class TargetError(SessionException):
    """Target error"""

    code = -600


class NetworkError(TargetError):
    """Network error"""

    code = -600


class FileError(TargetError):
    """File error"""

    code = -600


class TargetUnreachable(TargetError):
    """Target unreachable"""

    code = -600


class PayloadOutputError(TargetError):
    """Target output error"""

    code = -600


class TargetRuntimeError(TargetError):
    """Target runtime error"""

    code = -600
