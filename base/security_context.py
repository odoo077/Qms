# base/security_context.py
from __future__ import annotations
from typing import Optional
from contextvars import ContextVar

_current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)

def set_current_user_id(user_id: Optional[int]) -> None:
    _current_user_id.set(user_id)

def get_current_user_id() -> Optional[int]:
    return _current_user_id.get()
