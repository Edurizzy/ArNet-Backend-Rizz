"""
Helpdesk API URL Configuration for ArNet Platform.

This module defines URL routes for helpdesk API endpoints optimized for:
1. Agent dashboard and productivity workflows
2. Real-time conversation management
3. Operational helpdesk business processes
4. Future WebSocket and event-driven integration

Ticket Endpoints (Agent Operations):
- GET    /tickets/                           - Agent dashboard (filtered ticket list)
- POST   /tickets/                           - Create new ticket
- GET    /tickets/{id}/                      - Ticket details with context
- PUT    /tickets/{id}/                      - Update ticket properties
- PATCH  /tickets/{id}/                      - Partial ticket update
- POST   /tickets/{id}/assign/               - Assign ticket to agent  
- POST   /tickets/{id}/update-status/        - Change ticket status
- POST   /tickets/bulk-assign/               - Bulk ticket assignment
- GET    /tickets/statistics/               - Dashboard metrics

Message Endpoints (Conversation Management):
- GET    /messages/?ticket_id={id}          - Load conversation messages
- POST   /messages/                         - Add message to ticket
- GET    /messages/{id}/                    - Get specific message details

URL Design Principles:
- RESTful conventions for standard operations
- Custom actions for helpdesk-specific workflows
- Real-time communication patterns
- Agent productivity optimization
- Future WebSocket endpoint compatibility
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TicketViewSet, MessageViewSet


# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

# Main router for helpdesk API endpoints
router = DefaultRouter()

# Register ViewSets with appropriate URL patterns
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'messages', MessageViewSet, basename='message')

# The router automatically creates these URL patterns:
#
# Ticket URLs:
# ^tickets/$                                [name='ticket-list']           (GET, POST)
# ^tickets/(?P<pk>[^/.]+)/$                [name='ticket-detail']         (GET, PUT, PATCH, DELETE)
# ^tickets/(?P<pk>[^/.]+)/assign/$         [name='ticket-assign']         (POST)
# ^tickets/(?P<pk>[^/.]+)/update-status/$  [name='ticket-update-status']  (POST)
# ^tickets/bulk-assign/$                   [name='ticket-bulk-assign']    (POST)
# ^tickets/statistics/$                    [name='ticket-statistics']     (GET)
#
# Message URLs:
# ^messages/$                              [name='message-list']          (GET, POST)
# ^messages/(?P<pk>[^/.]+)/$              [name='message-detail']        (GET, PUT, PATCH, DELETE)


# =============================================================================
# URL PATTERNS
# =============================================================================

# Main URL patterns for the helpdesk API
urlpatterns = [
    # Include all router-generated URLs
    path('', include(router.urls)),
]

# Final URL structure when integrated with core URLs:
#
# Base: /api/v1/helpdesk/
#
# ===============================================
# TICKET MANAGEMENT (Agent Dashboard)
# ===============================================
#
# Agent Dashboard - List and Filter Tickets:
# GET /api/v1/helpdesk/tickets/
# Query Parameters:
#   ?status=open                    - Filter by status
#   ?priority=urgent                - Filter by priority  
#   ?channel=whatsapp              - Filter by channel
#   ?assigned_to={uuid}            - Filter by agent
#   ?search=customer               - Search customers/titles
#   ?sla_overdue=true              - Show overdue tickets
#   ?unassigned=true               - Show unassigned tickets
#   ?page=2&page_size=20           - Pagination
#
# Create New Ticket:
# POST /api/v1/helpdesk/tickets/
# Body: {
#   "customer_id": "uuid",
#   "title": "Customer issue description", 
#   "channel": "whatsapp",
#   "priority": "high"
# }
#
# Get Ticket Details:
# GET /api/v1/helpdesk/tickets/{uuid}/
#
# Update Ticket Properties:
# PUT /api/v1/helpdesk/tickets/{uuid}/
# PATCH /api/v1/helpdesk/tickets/{uuid}/
# Body: {
#   "title": "Updated title",
#   "priority": "urgent",
#   "metadata": {"key": "value"}
# }
#
# ===============================================
# TICKET OPERATIONS (Agent Actions)
# ===============================================
#
# Assign Ticket to Agent:
# POST /api/v1/helpdesk/tickets/{uuid}/assign/
# Body: {"agent_id": "agent-uuid"}
#
# Update Ticket Status:
# POST /api/v1/helpdesk/tickets/{uuid}/update-status/
# Body: {
#   "status": "resolved",
#   "reason": "Issue resolved via email"
# }
#
# Bulk Assign Tickets:
# POST /api/v1/helpdesk/tickets/bulk-assign/
# Body: {
#   "ticket_ids": ["uuid1", "uuid2", "uuid3"],
#   "agent_id": "agent-uuid"
# }
#
# Dashboard Statistics:
# GET /api/v1/helpdesk/tickets/statistics/
# Returns: {
#   "total_tickets": 150,
#   "open_tickets": 25,
#   "overdue_tickets": 3,
#   "by_priority": {...},
#   "by_channel": {...}
# }
#
# ===============================================
# MESSAGE MANAGEMENT (Conversation)
# ===============================================
#
# Load Conversation Messages:
# GET /api/v1/helpdesk/messages/?ticket_id={uuid}
# Query Parameters:
#   ?ticket_id={uuid}              - Required: Ticket to load messages for
#   ?limit=50                      - Number of messages to load
#   ?offset=100                    - Skip messages (pagination)
#   ?before_id={uuid}              - Load messages before this message (scroll up)
#   ?after_id={uuid}               - Load messages after this message (real-time)
#
# Add Message to Ticket:
# POST /api/v1/helpdesk/messages/
# Body: {
#   "ticket_id": "uuid",
#   "sender_type": "agent",
#   "direction": "outbound", 
#   "content": "Message text",
#   "is_internal": false,
#   "external_message_id": "whatsapp-msg-123"
# }
#
# Get Specific Message:
# GET /api/v1/helpdesk/messages/{uuid}/
#
# ===============================================
# USAGE EXAMPLES FOR COMMON WORKFLOWS
# ===============================================
#
# Agent Dashboard Load:
# 1. GET /api/v1/helpdesk/tickets/?assigned_to={agent_id}&status=open
# 2. GET /api/v1/helpdesk/tickets/statistics/
#
# Open Ticket Conversation:
# 1. GET /api/v1/helpdesk/tickets/{ticket_id}/
# 2. GET /api/v1/helpdesk/messages/?ticket_id={ticket_id}&limit=50
#
# Agent Responds to Customer:
# 1. POST /api/v1/helpdesk/messages/ (with agent response)
# 2. POST /api/v1/helpdesk/tickets/{ticket_id}/update-status/ (if resolving)
#
# Customer Sends New Message (Webhook):
# 1. POST /api/v1/helpdesk/messages/ (with external_message_id for dedup)
#    → Service automatically evaluates ticket state changes
#
# Real-time Message Updates:
# 1. WebSocket connection (future implementation)
# 2. Polling: GET /api/v1/helpdesk/messages/?ticket_id={id}&after_id={last_msg}
#
# ===============================================
# FUTURE ENDPOINTS (Event-Driven Extensions)
# ===============================================
#
# When event-driven architecture is implemented, these endpoints
# will be enhanced with WebSocket support and real-time notifications:
#
# WebSocket Endpoints (Future):
# - /ws/helpdesk/tickets/          - Ticket updates stream
# - /ws/helpdesk/messages/{id}/    - Real-time conversation
# - /ws/helpdesk/agent/{id}/       - Agent-specific updates
#
# Analytics Endpoints (Future):
# - /api/v1/helpdesk/analytics/response-times/
# - /api/v1/helpdesk/analytics/customer-satisfaction/
# - /api/v1/helpdesk/analytics/agent-performance/
#
# AI Integration Endpoints (Future):
# - /api/v1/helpdesk/ai/suggest-response/
# - /api/v1/helpdesk/ai/auto-categorize/
# - /api/v1/helpdesk/ai/sentiment-analysis/


# =============================================================================
# API DOCUMENTATION METADATA
# =============================================================================

app_name = 'helpdesk'

# The URL patterns follow RESTful conventions with helpdesk-specific
# operational endpoints for agent productivity and real-time communication.
# 
# This structure is optimized for:
# 1. Agent dashboard performance
# 2. Real-time conversation loading  
# 3. High-frequency message creation
# 4. Future WebSocket integration
# 5. Event-driven architecture expansion