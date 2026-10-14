"""Who is calling: the web server vouches for a signed-in user with a short-lived token.

Better Auth runs in the web app. For each request it makes on a user's behalf, the web server
signs a JWT (HS256, API_TOKEN_SECRET, 2 minutes) whose subject is the user's id. Browsers never
see it. The API only trusts tokens for users that still exist.
"""

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

from recallradar_api.state import DbSession
from recallradar_core.db import AuthUser
from recallradar_core.settings import get_settings

AUDIENCE = "recallradar-api"
ISSUER = "recallradar-web"


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def current_user(
    session: DbSession, authorization: Annotated[str | None, Header()] = None
) -> AuthUser:
    secret = get_settings().api_token_secret
    if secret is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Accounts are disabled.")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Sign in first.")
    try:
        claims = jwt.decode(
            token,
            secret.get_secret_value(),
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as error:
        raise _unauthorized("Your session has expired. Sign in again.") from error
    user = session.get(AuthUser, claims["sub"])
    if user is None:
        raise _unauthorized("Your account no longer exists.")
    return user


CurrentUser = Annotated[AuthUser, Depends(current_user)]
