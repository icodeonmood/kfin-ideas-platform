"""A-API.conventions/2: errors are `{error: {code, message, field?, …}}`, and `message` is ready to show under the
field named by `field`. The words come from the pack's copy (V-FIELDS.checkit), never from the request."""

from __future__ import annotations

from typing import Any


class Refused(Exception):
    def __init__(
        self, status: int, code: str, message: str = "", field: str | None = None, **extra: Any
    ) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.field, self.extra = status, code, message, field, extra

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field is not None:
            err["field"] = self.field
        return {"error": {**err, **self.extra}}


class NotFound(Refused):
    """Someone else's draft or idea looks exactly like a missing one."""

    def __init__(self) -> None:
        super().__init__(404, "not_found", "We can’t find that idea.")
