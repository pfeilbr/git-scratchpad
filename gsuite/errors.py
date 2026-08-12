class CLIError(Exception):
    """User-facing error: printed as `error: <msg>`, exit code 1."""


class AuthError(CLIError):
    """Authentication problem (missing/expired credentials, bad scopes)."""


class APIError(CLIError):
    """Google API returned an error response."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
