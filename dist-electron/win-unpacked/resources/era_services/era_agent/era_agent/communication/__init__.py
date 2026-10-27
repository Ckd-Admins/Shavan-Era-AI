"""ERA Communication Package."""

from .gmail_adapter import GmailAdapter, gmail_adapter
from .router import CommunicationRouter, comm_router
from .whatsapp_adapter import WhatsAppAdapter, whatsapp_adapter

__all__ = ["GmailAdapter", "WhatsAppAdapter", "CommunicationRouter", "gmail_adapter", "whatsapp_adapter", "comm_router"]
