"""
Thin WebSocket consumers for helpdesk realtime events.

Consumers do not contain business logic or ORM access. They only authenticate
the connection context, manage tenant-scoped groups, and forward standardized
JSON events to the frontend.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Set

from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone


class HelpdeskConsumer(AsyncWebsocketConsumer):
    """Tenant-scoped realtime stream for helpdesk operations."""

    async def connect(self) -> None:
        self.joined_groups: Set[str] = set()

        # ====================================================
        # HACK TEMPORÁRIO PARA TESTE SEM LOGIN NO FRONTEND
        # ====================================================
        # user = self.scope.get("user")
        # if not user or not user.is_authenticated:
        #     await self.close(code=4401)
        #     return
        # 
        # organization_id = getattr(user, "organization_id", None)
        # if not organization_id:
        #     await self.close(code=4403)
        #     return
        # self.organization_id = str(organization_id)

        # Forçando o ID da sua Organização para o teste!
        self.organization_id = "684e9201-e7f6-4ea7-9c2f-83d7c26b1593"
        # ====================================================

        self.organization_group_name = self._organization_group_name(self.organization_id)

        await self._join_group(self.organization_group_name)
        await self.accept()
    # async def connect(self) -> None:
    #     self.joined_groups: Set[str] = set()

    #     user = self.scope.get("user")
    #     if not user or not user.is_authenticated:
    #         await self.close(code=4401)
    #         return

    #     organization_id = getattr(user, "organization_id", None)
    #     if not organization_id:
    #         await self.close(code=4403)
    #         return

    #     self.organization_id = str(organization_id)
    #     self.organization_group_name = self._organization_group_name(self.organization_id)

    #     await self._join_group(self.organization_group_name)
    #     await self.accept()

    async def disconnect(self, close_code: int) -> None:
        for group_name in list(getattr(self, "joined_groups", set())):
            await self._leave_group(group_name)

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        """Accept lightweight JSON control messages without mutating domain state."""
        if not text_data:
            return

        try:
            message = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_json(
                self._control_event("error", {"detail": "Invalid JSON"})
            )
            return

        if message.get("type") == "ping":
            await self._send_json(self._control_event("pong", {}))

    async def new_message(self, event: Dict[str, Any]) -> None:
        await self._send_json(event)

    async def ticket_updated(self, event: Dict[str, Any]) -> None:
        await self._send_json(event)

    async def _join_group(self, group_name: str) -> None:
        if group_name in self.joined_groups:
            return

        await self.channel_layer.group_add(group_name, self.channel_name)
        self.joined_groups.add(group_name)

    async def _leave_group(self, group_name: str) -> None:
        if group_name not in self.joined_groups:
            return

        try:
            await self.channel_layer.group_discard(group_name, self.channel_name)
        finally:
            self.joined_groups.discard(group_name)

    async def _send_json(self, payload: Dict[str, Any]) -> None:
        await self.send(text_data=json.dumps(payload, default=str))

    @staticmethod
    def _organization_group_name(organization_id: str) -> str:
        return f"org_{organization_id}_events"

    def _control_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": event_type,
            "event_version": 1,
            "timestamp": timezone.now().isoformat(),
            "organization_id": getattr(self, "organization_id", None),
            "correlation_id": str(uuid.uuid4()),
            "payload": payload,
        }
