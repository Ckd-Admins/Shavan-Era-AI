"""Natural Language Intent Engine for Era System Controls.

Interprets natural language phrases in English and Hinglish (e.g. 'increase brightness',
'key light chalu kar', 'volume set to 50', 'turn off bluetooth', 'mute audio')
into structured intent actions and numerical parameters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SystemIntent:
    """Represents an extracted system control intent from natural language input."""

    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    matched: bool = True
    raw_query: str = ""


class IntentParser:
    """Parses natural language requests into structured system control actions."""

    @classmethod
    def parse(cls, query: str) -> SystemIntent:
        text = query.strip().lower()
        if not text:
            return SystemIntent(action="unknown", matched=False, raw_query=query)

        # ------------------------------------------------------------------
        # 0. Peripheral Status Intents
        # ------------------------------------------------------------------
        if any(phrase in text for phrase in ["peripheral status", "peripherals status", "bluetooth and wifi", "connection status"]):
            return SystemIntent(action="get_peripheral_status", raw_query=query)

        # ------------------------------------------------------------------
        # 1. Keyboard Backlight Intents
        # ------------------------------------------------------------------
        if any(kw in text for kw in ["keyboard", "key light", "keypad light", "backlight", "laptop light"]) or ("light" in text and any(w in text for w in ["open", "chalu", "on", "off", "band", "kholo", "khol", "jalao", "bujhao"])):
            # ── Read current brightness ──────────────────────────────────
            if any(kw in text for kw in ["kitni", "kitna", "check", "status", "get", "what", "current", "show", "read"]):
                return SystemIntent(action="get_keyboard_backlight", raw_query=query)

            # ── Save to flash ────────────────────────────────────────────
            if any(kw in text for kw in ["save", "persist", "flash"]):
                return SystemIntent(action="save_keyboard_backlight", raw_query=query)

            # ── Set to specific percentage ───────────────────────────────
            m = re.search(r"(\d{1,3})%?", text)
            if m:
                mode = "rainbow" if any(w in text for w in ["rainbow", "wave", "multi", "flow", "color"]) else "rainbow"
                return SystemIntent(action="set_keyboard_backlight", params={"level": int(m.group(1)), "mode": mode}, raw_query=query)

            # ── Turn off ─────────────────────────────────────────────────
            if any(kw in text for kw in ["off", "disable", "turn off", "band", "bund", "bandh", "bujhao", "bujha", "bujhado", "close", "shut"]):
                return SystemIntent(action="set_keyboard_backlight", params={"level": 0, "mode": "off"}, raw_query=query)

            # ── Turn on / full ───────────────────────────────────────────
            if any(kw in text for kw in ["on", "enable", "turn on", "chalu", "chaloo", "vhalu", "valoo", "start", "full", "open", "kholo", "khol", "jalao", "jala", "jalado", "jalayein"]):
                mode = "static" if any(w in text for w in ["static", "single", "white", "plain"]) else "rainbow"
                return SystemIntent(action="set_keyboard_backlight", params={"level": 100, "mode": mode}, raw_query=query)

            # ── Increase brightness ──────────────────────────────────────
            if any(kw in text for kw in ["up", "increase", "raise", "brighter", "badhao", "badha", "zyada", "tez"]):
                return SystemIntent(action="adjust_keyboard_backlight", params={"delta": 25}, raw_query=query)

            # ── Decrease brightness ──────────────────────────────────────
            if any(kw in text for kw in ["down", "decrease", "lower", "dim", "kam", "ghata", "ghataao", "dheema"]):
                return SystemIntent(action="adjust_keyboard_backlight", params={"delta": -25}, raw_query=query)

        # ------------------------------------------------------------------
        # 2. Display Brightness Intents
        # ------------------------------------------------------------------
        if ("brightness" in text or "screen light" in text) and any(kw in text for kw in ["get", "what", "check", "current", "show", "status", "kitni"]):
            return SystemIntent(action="get_display_brightness", raw_query=query)

        m = re.search(r"(?:set|change|put)?\s*(?:display|screen)?\s*(?:brightness|light)\s*(?:to|set|=)?\s*(\d{1,3})%?", text)
        if m:
            val = int(m.group(1))
            return SystemIntent(action="set_display_brightness", params={"level": val}, raw_query=query)

        if any(kw in text for kw in ["increase brightness", "brighter", "turn up brightness", "brightness up", "boost brightness", "brightness badhao", "screen light badhao"]):
            delta_match = re.search(r"by\s*(\d{1,3})%?", text)
            delta = int(delta_match.group(1)) if delta_match else 15
            return SystemIntent(action="adjust_display_brightness", params={"delta": delta}, raw_query=query)

        if any(kw in text for kw in ["decrease brightness", "dim", "lower brightness", "brightness down", "darker", "brightness kam", "screen light kam"]):
            delta_match = re.search(r"by\s*(\d{1,3})%?", text)
            delta = -int(delta_match.group(1)) if delta_match else -15
            return SystemIntent(action="adjust_display_brightness", params={"delta": delta}, raw_query=query)

        # ------------------------------------------------------------------
        # 3. Audio Volume Intents
        # ------------------------------------------------------------------
        if any(kw in text for kw in ["mute volume", "mute audio", "mute sound", "mute"]):
            if "unmute" in text or "off mute" in text or "disable mute" in text:
                return SystemIntent(action="toggle_audio_mute", params={"mute": False}, raw_query=query)
            return SystemIntent(action="toggle_audio_mute", params={"mute": True}, raw_query=query)

        if any(kw in text for kw in ["unmute volume", "unmute audio", "unmute sound", "unmute"]):
            return SystemIntent(action="toggle_audio_mute", params={"mute": False}, raw_query=query)

        if "volume" in text and any(kw in text for kw in ["get", "what", "check", "current", "show", "status", "kitna"]):
            return SystemIntent(action="get_audio_volume", raw_query=query)

        m = re.search(r"(?:set|adjust|change|put)?\s*(?:audio|sound|master)?\s*volume\s*(?:to|set|=|\s)*(\d{1,3})%?", text)
        if m:
            val = int(m.group(1))
            return SystemIntent(action="set_audio_volume", params={"level": val}, raw_query=query)

        if any(kw in text for kw in ["increase volume", "volume up", "turn up volume", "louder", "raise volume", "volume badhao", "sound badhao"]):
            delta_match = re.search(r"by\s*(\d{1,3})%?", text)
            delta = int(delta_match.group(1)) if delta_match else 10
            return SystemIntent(action="adjust_audio_volume", params={"delta": delta}, raw_query=query)

        if any(kw in text for kw in ["decrease volume", "volume down", "turn down volume", "softer", "lower volume", "volume kam", "sound kam"]):
            delta_match = re.search(r"by\s*(\d{1,3})%?", text)
            delta = -int(delta_match.group(1)) if delta_match else -10
            return SystemIntent(action="adjust_audio_volume", params={"delta": -10}, raw_query=query)

        # ------------------------------------------------------------------
        # 4. Peripheral Connection Intents
        # ------------------------------------------------------------------
        if "bluetooth" in text or "bt" in text.split():
            if any(kw in text for kw in ["on", "enable", "connect", "start", "turn on", "chalu", "vhalu"]):
                return SystemIntent(action="set_bluetooth_state", params={"enable": True}, raw_query=query)
            if any(kw in text for kw in ["off", "disable", "disconnect", "stop", "turn off", "band"]):
                return SystemIntent(action="set_bluetooth_state", params={"enable": False}, raw_query=query)
            if any(kw in text for kw in ["status", "check", "state"]):
                return SystemIntent(action="get_peripheral_status", raw_query=query)

        if "wifi" in text or "wi-fi" in text or "wireless" in text:
            if any(kw in text for kw in ["on", "enable", "connect", "start", "turn on", "chalu", "vhalu"]):
                return SystemIntent(action="set_wifi_state", params={"enable": True}, raw_query=query)
            if any(kw in text for kw in ["off", "disable", "disconnect", "stop", "turn off", "band"]):
                return SystemIntent(action="set_wifi_state", params={"enable": False}, raw_query=query)
            if any(kw in text for kw in ["status", "check", "state"]):
                return SystemIntent(action="get_peripheral_status", raw_query=query)

        # ------------------------------------------------------------------
        # 5. WhatsApp Messaging Intents (Hinglish + English)
        # ------------------------------------------------------------------
        if "whatsapp" in text or ("message" in text and any(w in text for w in ["bhejo", "bhej", "send", "karo", "do", "msg"])):
            phone_or_contact = ""
            msg_body = ""

            m_hinglish = re.search(r"([a-z0-9\s]+?)\s+ko\s+(?:whatsapp\s+(?:par|per|pe)\s+)?(?:message|msg)\s+(?:bhejo|bhej|karo|do|bhejdo)\s*(.*)", text)
            if m_hinglish:
                phone_or_contact = m_hinglish.group(1).replace("whatsapp", "").strip()
                msg_body = m_hinglish.group(2).strip()
                msg_body = re.sub(r"^(?:do|to|de|dene)\s+", "", msg_body).strip()

            if not phone_or_contact:
                m_english = re.search(r"(?:send|msg|message)\s+(?:a\s+)?(?:whatsapp\s+)?(?:message\s+)?(?:to\s+)?([a-z0-9\s]+?)\s+(?:saying|with text|text|message)?\s*(.*)", text)
                if m_english:
                    phone_or_contact = m_english.group(1).replace("whatsapp", "").replace("send", "").strip()
                    msg_body = m_english.group(2).strip()
                    msg_body = re.sub(r"^(?:do|to|de|dene)\s+", "", msg_body).strip()

            if phone_or_contact:
                if not msg_body:
                    msg_body = "Hello from ERA!"
                return SystemIntent(action="open_whatsapp", params={"phone": phone_or_contact, "message": msg_body}, raw_query=query)

        # ------------------------------------------------------------------
        # 6. Phone Link Device Intents (Calls, SMS/Messages, File Transfer, Status)
        # ------------------------------------------------------------------
        if any(kw in text for kw in ["call", "dial", "phone lagao", "phonelink", "phone link", "fon lagao", "call karo", "call lagao"]):
            digit_m = re.search(r"(\+?\d[\d\s\-]{6,15}\d|\b\d{10}\b|\b\d{5}\s*\d{5}\b)", text)
            if digit_m:
                clean_num = re.sub(r"[^\d+]", "", digit_m.group(1))
                return SystemIntent(
                    action="make_phone_call",
                    params={"phone": clean_num},
                    raw_query=query,
                )

            cleaned_text = text
            for filler in ["phone link", "phonelink", "windows phone link"]:
                cleaned_text = cleaned_text.replace(filler, "")

            m_ko = re.search(r"([a-z0-9\s]+?)\s+(?:ko|pe|par)\s+(?:call|phone|dial)", cleaned_text)
            if m_ko:
                contact = m_ko.group(1).strip()
                contact = re.sub(r"^(?:is|us|mera|meri|mujhe|please|se)\s+", "", contact).strip()
                if contact and contact not in ["call", "karo", "do", "lagao", "se", "number"]:
                    return SystemIntent(action="make_phone_call", params={"phone": contact}, raw_query=query)

            m_call_after = re.search(r"(?:call|dial|phone lagao|fon lagao)\s+(?:to\s+)?([a-z0-9\s]+)", cleaned_text)
            if m_call_after:
                contact = m_call_after.group(1).strip()
                contact = re.sub(r"\s+(?:karo|do|lagao|bhejo|please)$", "", contact).strip()
                contact = re.sub(r"^(?:to|ko|pe|par|se)\s+", "", contact).strip()
                if contact and contact not in ["karo", "do", "lagao", "please", "call"]:
                    return SystemIntent(action="make_phone_call", params={"phone": contact}, raw_query=query)

        if any(kw in text for kw in ["phone link message", "phone message", "sms read", "messages padho", "sms padho", "read sms", "read message"]):
            return SystemIntent(action="read_phone_messages", raw_query=query)

        if any(kw in text for kw in ["file transfer", "photo transfer", "phone file", "phone photo", "phone link file", "transfer file"]):
            return SystemIntent(action="transfer_phone_files", raw_query=query)

        if "phone link" in text and any(kw in text for kw in ["status", "check", "connected", "connect", "state", "link", "karo", "do"]):
            return SystemIntent(action="get_phone_link_status", raw_query=query)

        return SystemIntent(action="unknown", matched=False, raw_query=query)
