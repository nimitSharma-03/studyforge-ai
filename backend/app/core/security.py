"""Anonymous workspace tokens.

A workspace token is a 256-bit random secret issued by the server. Only its SHA-256 hash
is stored, so a database leak does not reveal usable tokens. Possession of the token is
what authorises access to a workspace; identifiers chosen by the browser are never trusted.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_PREFIX = "sfw_"


def new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def looks_like_token(token: str | None) -> bool:
    return bool(token) and token.startswith(TOKEN_PREFIX) and 30 <= len(token) <= 80
