from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from admin_api.settings import get_settings


basic_security = HTTPBasic(auto_error=False)


def verify_admin(
    credentials: HTTPBasicCredentials | None = Depends(basic_security),
    admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    settings = get_settings()

    if admin_token and secrets.compare_digest(admin_token, settings.admin_token):
        return

    if (
        settings.admin_basic_username
        and settings.admin_basic_password
        and credentials
        and secrets.compare_digest(credentials.username, settings.admin_basic_username)
        and secrets.compare_digest(credentials.password, settings.admin_basic_password)
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Basic"},
    )
