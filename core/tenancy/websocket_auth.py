"""
JWT authentication middleware for Channels WebSocket connections.

HTTP middleware does not run for WebSocket scopes, so socket authentication must
be resolved at the ASGI layer before consumers are called. This middleware keeps
consumers thin: consumers can trust ``scope["user"]`` and only decide whether to
accept or reject the connection.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)


class JWTAuthMiddleware:
    """Authenticate Channels scopes with a SimpleJWT bearer token."""

    def __init__(self, app):
        self.app = app
        self.jwt_authentication = JWTAuthentication()

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["user"] = AnonymousUser()

        raw_token = self._extract_token(scope)
        if raw_token:
            scope["user"] = await self._get_user_from_token(raw_token)

        return await self.app(scope, receive, send)

    def _extract_token(self, scope) -> Optional[str]:
        """Extract JWT from query params or the Authorization header."""
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)

        for key in ("token", "access_token"):
            values = query_params.get(key)
            if values and values[0]:
                return values[0]

        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization")
        if not authorization:
            return None

        try:
            auth_header = authorization.decode("utf-8")
        except UnicodeDecodeError:
            return None

        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

        return None

    @database_sync_to_async
    def _get_user_from_token(self, raw_token: str):
        """Validate the token and resolve the active user."""
        try:
            validated_token = self.jwt_authentication.get_validated_token(raw_token)
            user = self.jwt_authentication.get_user(validated_token)
        except (InvalidToken, TokenError) as exc:
            logger.debug("WebSocket JWT validation failed: %s", exc)
            return AnonymousUser()
        except Exception:
            logger.exception("Unexpected WebSocket JWT authentication failure")
            return AnonymousUser()

        if not user or not user.is_authenticated or not user.is_active:
            return AnonymousUser()

        return user


def JWTAuthMiddlewareStack(inner):
    """Reusable middleware stack for JWT-authenticated WebSocket routes."""
    return JWTAuthMiddleware(inner)
