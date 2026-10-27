"""Shared server-side operator authentication for restored service entrypoints."""
import hmac
import os

from fastapi import Header, HTTPException


def require_auth(authorization: str | None = Header(None)) -> None:
    expected = os.environ.get("ALPHA_NODE_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="ALPHA_NODE_API_KEY not configured; execution API disabled")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    if not hmac.compare_digest(authorization.removeprefix("Bearer "), expected):
        raise HTTPException(status_code=401, detail="incorrect bearer token")
