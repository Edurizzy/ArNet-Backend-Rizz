"""WebSocket URL routing for the helpdesk domain."""

from django.urls import path

from .consumers import HelpdeskConsumer


websocket_urlpatterns = [
    path("ws/v1/helpdesk/", HelpdeskConsumer.as_asgi()),
]
