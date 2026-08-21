import pytest
from fastapi import HTTPException
from ai_quant.core.config import settings
from ai_quant.core.security import mask_secret, verify_control_plane_auth


def test_secret_masking():
    assert mask_secret(None) == "<unset>"
    assert mask_secret("") == "<unset>"
    assert mask_secret("short") == "***"
    assert mask_secret("super-secret-api-token-12345", show_last=4) == "************************2345"
    assert mask_secret("super-secret-api-token-12345", show_last=4).endswith("2345")


def test_control_plane_auth_dev_mode():
    # Dev mode when auth_token is None and auth_required is False
    settings.auth_token = None
    settings.auth_required = False

    res = verify_control_plane_auth(authorization=None, x_api_key=None)
    assert res == "dev-mode-unauthenticated"


def test_control_plane_auth_enforced_success_and_failure():
    settings.auth_token = "valid-institutional-token"
    settings.auth_required = True

    # 1. Successful authentication with Bearer token
    assert verify_control_plane_auth(authorization="Bearer valid-institutional-token") == "valid-institutional-token"

    # 2. Successful authentication with X-API-Key
    assert verify_control_plane_auth(x_api_key="valid-institutional-token") == "valid-institutional-token"

    # 3. Missing authentication -> 401 HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_control_plane_auth(authorization=None, x_api_key=None)
    assert exc_info.value.status_code == 401

    # 4. Invalid authentication -> 401 HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_control_plane_auth(authorization="Bearer wrong-token")
    assert exc_info.value.status_code == 401

    # Clean up settings
    settings.auth_token = None
    settings.auth_required = False
