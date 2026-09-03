from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app import auth_service, inventory_service


def token_for(username: str, roles: list[str], audience: str = "inventory-service") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": username, "roles": roles, "iss": auth_service.ISSUER,
                       "aud": audience, "iat": now, "exp": now + timedelta(minutes=5)},
                      auth_service.PRIVATE_KEY, algorithm="RS256")


def test_valid_admin_token():
    claims = inventory_service.decode_token("Bearer " + token_for("admin", ["admin"]))
    assert claims["sub"] == "admin"


def test_wrong_audience_is_unauthorized():
    with pytest.raises(HTTPException) as error:
        inventory_service.decode_token("Bearer " + token_for("admin", ["admin"], "other"))
    assert error.value.status_code == 401


def test_missing_token_is_unauthorized():
    with pytest.raises(HTTPException) as error:
        inventory_service.decode_token(None)
    assert error.value.status_code == 401


def test_viewer_role_is_forbidden():
    dependency = inventory_service.require_role("admin")
    with pytest.raises(HTTPException) as error:
        dependency({"sub": "viewer", "roles": ["viewer"]})
    assert error.value.status_code == 403
