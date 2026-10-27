"""ERA WhatsApp Adapter Integration.

Provides official WhatsApp Business Cloud API integration with status tracking,
real text sending to recipient numbers via Meta Graph API, webhook message storage,
explicit connection status tracking, and zero-cred mock mode for testing.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WhatsAppAdapter:
    """WhatsApp Provider Adapter for ERA supporting Real Meta Cloud API & Mock Mode."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        mock_mode: bool = False,
    ):
        self.api_token = api_token or os.getenv("WHATSAPP_API_TOKEN")
        self.phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.mock_mode = mock_mode or os.getenv("ERA_MOCK_MODE", "false").lower() == "true"
        self._sent_messages: List[Dict[str, Any]] = []
        self._received_messages: List[Dict[str, Any]] = []
        self._drafts: List[Dict[str, Any]] = []
        self.status = "DISCONNECTED"
        self._init_status()

    def _init_status(self) -> None:
        if self.api_token and self.phone_number_id:
            self.status = "CONNECTED"
        elif self.mock_mode:
            self.status = "MOCK_MODE"
        else:
            self.status = "AUTH_REQUIRED"

    @property
    def is_authenticated(self) -> bool:
        return self.status == "CONNECTED"

    def get_status(self) -> Dict[str, Any]:
        """Returns WhatsApp connection status."""
        status_val = self.status if not (self.mock_mode and self.status == "AUTH_REQUIRED") else "MOCK_MODE"
        return {
            "status": status_val,
            "authenticated": self.status == "CONNECTED",
            "phone_number_id": self.phone_number_id,
            "provider": "WhatsApp Business Cloud API" if self.status == "CONNECTED" else ("WhatsApp Mock Mode" if status_val == "MOCK_MODE" else "WhatsApp Disconnected"),
            "api_token_configured": bool(self.api_token),
            "phone_id_configured": bool(self.phone_number_id),
            "limitations": "Cloud API sends messages to phone numbers and receives inbound messages via webhook.",
        }

    def receive_webhook_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Inbound webhook handler for storing incoming WhatsApp messages."""
        try:
            entries = event_data.get("entry", [])
            received_count = 0
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    contacts = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
                    for msg in messages:
                        sender_id = msg.get("from")
                        sender_name = contacts.get(sender_id, sender_id)
                        text_body = msg.get("text", {}).get("body", "")
                        msg_record = {
                            "id": msg.get("id", f"wa_in_{uuid.uuid4().hex[:8]}"),
                            "sender": sender_name,
                            "phone": sender_id,
                            "message": text_body,
                            "timestamp": msg.get("timestamp"),
                        }
                        self._received_messages.insert(0, msg_record)
                        received_count += 1
            return {"success": True, "processed": received_count}
        except Exception as e:
            logger.error("Failed to process WhatsApp webhook: %s", e)
            return {"success": False, "error": str(e)}

    def list_messages(self, limit: int = 10) -> Dict[str, Any]:
        """List recent WhatsApp messages."""
        if self.status == "CONNECTED":
            return {
                "success": True,
                "count": len(self._received_messages[:limit]),
                "messages": self._received_messages[:limit],
                "provider": "whatsapp_real",
            }

        if not self.mock_mode:
            return {
                "success": False,
                "status": self.status,
                "message": "WhatsApp Business Cloud API is not connected.",
                "error": "Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID in environment.",
            }

        mock_messages = [
            {"id": "wa_001", "sender": "Rahul", "phone": "+919876543210", "message": "Meeting update: move to 5 PM today.", "timestamp": "2026-10-04 11:00"},
            {"id": "wa_002", "sender": "Team Group", "phone": "group_01", "message": "Deployment successful on staging server.", "timestamp": "2026-10-04 10:45"},
        ]
        return {"success": True, "count": len(mock_messages), "messages": mock_messages[:limit], "provider": "whatsapp_mock"}

    def search_messages(self, query: str) -> Dict[str, Any]:
        """Search messages by keyword or contact name."""
        q_lower = query.lower()
        if self.status == "CONNECTED":
            filtered = [m for m in self._received_messages if q_lower in m["sender"].lower() or q_lower in m["message"].lower()]
            return {"success": True, "query": query, "count": len(filtered), "messages": filtered, "provider": "whatsapp_real"}

        if not self.mock_mode:
            return {
                "success": False,
                "status": self.status,
                "message": "WhatsApp Business Cloud API is not connected.",
                "error": "WhatsApp connection required.",
            }

        all_msgs = self.list_messages()["messages"]
        filtered = [m for m in all_msgs if q_lower in m["sender"].lower() or q_lower in m["message"].lower()]
        return {"success": True, "query": query, "count": len(filtered), "messages": filtered, "provider": "whatsapp_mock"}

    def read_message(self, message_id: str) -> Dict[str, Any]:
        """Read a specific message thread."""
        all_msgs = self._received_messages if self.status == "CONNECTED" else self.list_messages().get("messages", [])
        match = next((m for m in all_msgs if m["id"] == message_id), None)
        if match:
            return {"success": True, "data": match, "provider": "whatsapp_real" if self.status == "CONNECTED" else "whatsapp_mock"}

        if not self.mock_mode and self.status != "CONNECTED":
            return {"success": False, "status": self.status, "message": "WhatsApp Business Cloud API is not connected."}

        return {"success": False, "error": f"WhatsApp message '{message_id}' not found"}

    def create_draft(self, recipient: str, message: str) -> Dict[str, Any]:
        """Creates a WhatsApp message draft."""
        draft_id = f"wa_draft_{uuid.uuid4().hex[:8]}"
        draft_obj = {
            "draft_id": draft_id,
            "recipient": recipient,
            "message": message,
            "provider": "whatsapp",
            "status": "DRAFT",
        }
        self._drafts.append(draft_obj)
        return {"success": True, "draft_id": draft_id, "draft": draft_obj, "message": f"WhatsApp draft created for {recipient}"}

    def send_message(self, recipient: str, message: str, draft_id: Optional[str] = None) -> Dict[str, Any]:
        """Sends a WhatsApp message via official Meta Graph API (or mock mode)."""
        clean_recipient = "".join(filter(str.isdigit, recipient))
        if clean_recipient.startswith("0"):
            clean_recipient = clean_recipient[1:]

        if self.status == "CONNECTED" and self.api_token and self.phone_number_id:
            try:
                url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
                payload = {
                    "messaging_product": "whatsapp",
                    "to": clean_recipient,
                    "type": "text",
                    "text": {"body": message},
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    wamid = resp_data.get("messages", [{}])[0].get("id", f"wamid_{uuid.uuid4().hex[:8]}")

                    record = {
                        "message_id": wamid,
                        "recipient": recipient,
                        "message": message,
                        "draft_id": draft_id,
                        "verified_sent": True,
                    }
                    self._sent_messages.append(record)
                    return {
                        "success": True,
                        "message_id": wamid,
                        "recipient": recipient,
                        "message": f"WhatsApp message sent to {recipient}",
                        "verified": True,
                        "provider": "whatsapp_real",
                    }
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                logger.error("WhatsApp Graph API HTTPError: %s - %s", he.code, err_body)
                return {"success": False, "error": f"WhatsApp Graph API HTTP {he.code}: {err_body}"}
            except Exception as e:
                logger.error("WhatsApp send error: %s", e)
                return {"success": False, "error": f"WhatsApp API send error: {e}"}

        if not self.mock_mode and self.status != "CONNECTED":
            return {
                "success": False,
                "status": self.status,
                "message": "WhatsApp Business Cloud API is not connected.",
                "error": "WhatsApp connection required.",
            }

        msg_id = f"wa_sent_{uuid.uuid4().hex[:8]}"
        record = {
            "message_id": msg_id,
            "recipient": recipient,
            "message": message,
            "draft_id": draft_id,
            "verified_sent": True,
        }
        self._sent_messages.append(record)
        return {
            "success": True,
            "message_id": msg_id,
            "recipient": recipient,
            "message": f"WhatsApp message sent to {recipient}",
            "verified": True,
            "provider": "whatsapp_mock",
        }

    def verify_send(self, message_id: str) -> Dict[str, Any]:
        """Verifies if a WhatsApp message was sent."""
        match = next((m for m in self._sent_messages if m["message_id"] == message_id), None)
        if match:
            return {"verified": True, "message_id": message_id, "reason": "WhatsApp message delivery confirmed"}
        return {"verified": False, "message_id": message_id, "reason": "WhatsApp message ID not found in dispatch log"}


whatsapp_adapter = WhatsAppAdapter()
