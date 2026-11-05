"""Typed stand-ins for what cdedb2 adds to ``Environment.globals``."""

from __future__ import annotations

import datetime
from typing import Any

CDEDB_OFFLINE_DEPLOYMENT: bool
CDEDB_DEV: bool
CDEDB_TEST: bool
EXTENDED_PARAMETER_TIMEOUT: Any
I18N_LANGUAGES: list[str]
I18N_ADVERTISED_LANGUAGES: list[str]
AdminViews: Any
IGNORE_WARNINGS_NAME: str
ANTI_CSRF_TOKEN_NAME: str
ANTI_CSRF_TOKEN_PAYLOAD: str
nbsp: str
enums: Any


def raise_(message: str) -> Any:
    raise NotImplementedError


def drow_last_index(prefix: str = "") -> str:
    raise NotImplementedError


def encode_anti_csrf(*args: Any, **kwargs: Any) -> str:
    raise NotImplementedError


def staticurl(path: str) -> str:
    raise NotImplementedError


def docurl(topic: str, anchor: str = "") -> str:
    raise NotImplementedError


def encode_parameter(*args: Any, **kwargs: Any) -> str:
    raise NotImplementedError


MANAGEMENT_ADDRESS: str
GIT_COMMIT: str
EntitySorter: Any


def now() -> datetime.datetime:
    raise NotImplementedError
