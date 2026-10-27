"""ERA Unified Communication Router.

Provides a single interchangeable interface for Gmail and WhatsApp communication.
Registers communication tools into ERA Tool Registry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    from era_agent.communication.gmail_adapter import gmail_adapter
    from era_agent.communication.whatsapp_adapter import whatsapp_adapter
    from era_agent.mission_engine.models import RiskLevel
    from era_agent.tools.tool_registry import tool_registry
except ImportError:
    from communication.gmail_adapter import gmail_adapter
    from communication.whatsapp_adapter import whatsapp_adapter
    from mission_engine.models import RiskLevel
    from tools.tool_registry import tool_registry

logger = logging.getLogger(__name__)


class CommunicationRouter:
    """Unified router for Gmail & WhatsApp providers."""

    def __init__(self) -> None:
        self.gmail = gmail_adapter
        self.whatsapp = whatsapp_adapter

    def read(self, provider: str, query: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        p = provider.lower()
        if p == "gmail":
            return self.gmail.search_emails(query) if query else self.gmail.list_emails(limit)
        elif p in ["whatsapp", "wa"]:
            return self.whatsapp.search_messages(query) if query else self.whatsapp.list_messages(limit)
        else:
            return {"success": False, "error": f"Unsupported communication provider: '{provider}'"}

    def draft(self, provider: str, recipient: str, message: str, subject: Optional[str] = None) -> Dict[str, Any]:
        p = provider.lower()
        if p == "gmail":
            return self.gmail.create_draft(recipient, subject or "ERA Message", message)
        elif p in ["whatsapp", "wa"]:
            return self.whatsapp.create_draft(recipient, message)
        else:
            return {"success": False, "error": f"Unsupported communication provider: '{provider}'"}

    def send(
        self,
        provider: str,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
        draft_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        p = provider.lower()
        if p == "gmail":
            return self.gmail.send_email(recipient, subject or "ERA Notification", message, draft_id)
        elif p in ["whatsapp", "wa"]:
            return self.whatsapp.send_message(recipient, message, draft_id)
        else:
            return {"success": False, "error": f"Unsupported communication provider: '{provider}'"}

    def get_status(self) -> Dict[str, Any]:
        return {
            "gmail": {
                "authenticated": self.gmail.is_authenticated,
                "provider": "Gmail Official API" if self.gmail.is_authenticated else "Gmail Secure Mock Layer",
            },
            "whatsapp": {
                "authenticated": self.whatsapp.is_authenticated,
                "provider": "WhatsApp Cloud API" if self.whatsapp.is_authenticated else "WhatsApp Secure Mock Layer",
            },
        }


comm_router = CommunicationRouter()


# Register Communication Tools into Unified Tool Registry
@tool_registry.register(
    "gmail_list",
    "List recent emails from Gmail inbox.",
    {"max_results": {"type": "integer", "default": 10}},
    permission_level=RiskLevel.READ_ONLY,
)
def gmail_list(max_results: int = 10) -> Dict[str, Any]:
    return comm_router.read("gmail", limit=max_results)


@tool_registry.register(
    "gmail_search",
    "Search emails in Gmail using query string.",
    {"query": {"type": "string", "required": True}},
    permission_level=RiskLevel.READ_ONLY,
)
def gmail_search(query: str) -> Dict[str, Any]:
    return comm_router.read("gmail", query=query)


@tool_registry.register(
    "gmail_read",
    "Read full contents of a Gmail message by message ID.",
    {"message_id": {"type": "string", "required": True}},
    permission_level=RiskLevel.READ_ONLY,
)
def gmail_read(message_id: str) -> Dict[str, Any]:
    return comm_router.gmail.read_email(message_id)


@tool_registry.register(
    "gmail_draft",
    "Create a draft email in Gmail without sending.",
    {"recipient": {"type": "string", "required": True}, "subject": {"type": "string", "required": True}, "body": {"type": "string", "required": True}},
    permission_level=RiskLevel.LOW_RISK,
)
def gmail_draft(recipient: str, subject: str, body: str) -> Dict[str, Any]:
    return comm_router.draft("gmail", recipient=recipient, message=body, subject=subject)


@tool_registry.register(
    "gmail_reply",
    "Create a draft reply to a specific Gmail message.",
    {"message_id": {"type": "string", "required": True}, "body": {"type": "string", "required": True}},
    permission_level=RiskLevel.LOW_RISK,
)
def gmail_reply(message_id: str, body: str) -> Dict[str, Any]:
    return comm_router.gmail.create_reply(message_id, body)


@tool_registry.register(
    "gmail_send",
    "Send an email via Gmail. Requires user confirmation.",
    {"recipient": {"type": "string", "required": True}, "subject": {"type": "string", "required": True}, "body": {"type": "string", "required": True}, "draft_id": {"type": "string"}},
    permission_level=RiskLevel.EXTERNAL_SIDE_EFFECT,
    confirmation_required=True,
    verification_handler=lambda res, args: comm_router.gmail.verify_send(res.get("message_id", "")),
)
def gmail_send(recipient: str, subject: str, body: str, draft_id: Optional[str] = None) -> Dict[str, Any]:
    return comm_router.send("gmail", recipient=recipient, message=body, subject=subject, draft_id=draft_id)


@tool_registry.register(
    "whatsapp_list",
    "List recent WhatsApp messages.",
    {"limit": {"type": "integer", "default": 10}},
    permission_level=RiskLevel.READ_ONLY,
)
def whatsapp_list(limit: int = 10) -> Dict[str, Any]:
    return comm_router.read("whatsapp", limit=limit)


@tool_registry.register(
    "whatsapp_search",
    "Search WhatsApp messages by keyword or contact name.",
    {"query": {"type": "string", "required": True}},
    permission_level=RiskLevel.READ_ONLY,
)
def whatsapp_search(query: str) -> Dict[str, Any]:
    return comm_router.read("whatsapp", query=query)


@tool_registry.register(
    "whatsapp_read",
    "Read specific WhatsApp message by message ID.",
    {"message_id": {"type": "string", "required": True}},
    permission_level=RiskLevel.READ_ONLY,
)
def whatsapp_read(message_id: str) -> Dict[str, Any]:
    return comm_router.whatsapp.read_message(message_id)


@tool_registry.register(
    "whatsapp_draft",
    "Create a WhatsApp draft message.",
    {"recipient": {"type": "string", "required": True}, "message": {"type": "string", "required": True}},
    permission_level=RiskLevel.LOW_RISK,
)
def whatsapp_draft(recipient: str, message: str) -> Dict[str, Any]:
    return comm_router.draft("whatsapp", recipient=recipient, message=message)


@tool_registry.register(
    "whatsapp_send",
    "Send a WhatsApp message to recipient. Requires user confirmation.",
    {"recipient": {"type": "string", "required": True}, "message": {"type": "string", "required": True}, "draft_id": {"type": "string"}},
    permission_level=RiskLevel.EXTERNAL_SIDE_EFFECT,
    confirmation_required=True,
    verification_handler=lambda res, args: comm_router.whatsapp.verify_send(res.get("message_id", "")),
)
def whatsapp_send(recipient: str, message: str, draft_id: Optional[str] = None) -> Dict[str, Any]:
    return comm_router.send("whatsapp", recipient=recipient, message=message, draft_id=draft_id)
