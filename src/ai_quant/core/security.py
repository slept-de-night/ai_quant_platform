from __future__ import annotations

import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from .config import settings

logger = logging.getLogger("ai_quant.security")
_warned_once = False


def mask_secret(value: Optional[str], show_last: int = 4) -> str:
    """Masks sensitive strings for safe logging and diagnostics."""
    if not value:
        return "<unset>"
    if len(value) <= 6:
        return "***"
    return f"{'*' * (len(value) - show_last)}{value[-show_last:]}"


def verify_control_plane_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Validates API key for protected control-plane endpoints.
    Allows unauthenticated requests in development mode only when AUTH_TOKEN is unset and AUTH_REQUIRED=False.
    """
    global _warned_once
    configured_token = settings.auth_token

    if not configured_token and not settings.auth_required:
        if not _warned_once:
            logger.warning("[SECURITY] Control plane is running in development mode without AUTH_TOKEN authentication")
            _warned_once = True
        return "dev-mode-unauthenticated"

    auth_str = authorization if isinstance(authorization, str) else None
    key_str = x_api_key if isinstance(x_api_key, str) else None

    provided_token = None
    if auth_str and auth_str.startswith("Bearer "):
        provided_token = auth_str[7:].strip()
    elif key_str:
        provided_token = key_str.strip()

    if not provided_token or provided_token != configured_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: missing or invalid control-plane API authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token
