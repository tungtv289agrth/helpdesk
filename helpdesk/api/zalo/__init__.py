"""Zalo integration endpoints.

Public (allow_guest):
  - webhook            — receives Bot messages, links chat_id
  - check_zalo_id      — checks if a Zalo ID exists in the system

Agent / authenticated:
  - get_config                 — returns Zalo config for frontend
  - send_message               — sends Zalo message for a ticket
  - set_webhook                — sets Bot webhook
  - get_zalo_link_status       — link status for portal card
  - generate_zalo_code         — generates 6-digit code (90s TTL)
  - resend_zalo_code           — resends code
  - cancel_zalo_link           — cancels pending link
"""

import random
import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime, get_datetime

from helpdesk.utils import is_agent
from helpdesk.utils.zalo import (
    get_zalo_settings,
    is_zalo_enabled,
    send_zalo_message,
)

from . import _verify as V

# ---------------------------------------------------------------------------
# Public endpoints (allow_guest)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def webhook():
    """Webhook endpoint for Zalo Bot.

    Bot sends: POST { message: { chat: {id}, from: {display_name}, text } }
    We return: 200 on success, 404 on code not found/expired.
    """
    if not V.verify_secret():
        return V.frappe.local.response.message

    data = _parse_request_body()

    chat_id, display_name, text = _extract_message(data)
    if chat_id and text is not None:
        return _handle_verification(chat_id, display_name or "Zalo User", text)

    return {}


@frappe.whitelist(allow_guest=True)
def check_zalo_id(chat_id: str | None = None, zalo_user_id: str | None = None):
    """Check if a Zalo ID is linked in the system.

    GET /api/method/helpdesk.api.zalo.check_zalo_id?chat_id=xxx
    Header: X-Bot-Api-Secret-Token: <secret>

    200: {"chat_id": "...", "email": "...", "contact": "...", "ticket": "..."}
    200: {"chat_id": "...", "exists": false}
    400: {"message": "chat_id is required"}
    401: {"message": "Invalid secret token"}
    """
    if not V.verify_secret():
        return V.frappe.local.response.message

    zalo_id = (chat_id or zalo_user_id or "").strip()
    if not zalo_id or not isinstance(zalo_id, str):
        frappe.local.response.http_status_code = 400
        return {"message": "chat_id is required"}

    # Cache first (O(1))
    cached = V.cache_lookup_get(zalo_id)
    if cached:
        return {
            "chat_id": zalo_id,
            "email": cached.get("email"),
            "contact": cached.get("contact"),
            "ticket": cached.get("ticket"),
        }

    # Fallback DB (1 query)
    contact = frappe.db.get_value(
        "Contact",
        {"zalo_user_id": zalo_id},
        ["name", "email_id"],
        as_dict=True,
    )

    if contact:
        ticket = frappe.db.get_value(
            "HD Ticket",
            {"contact": contact.name, "zalo_user_id": zalo_id},
            "name",
        )
        V.cache_lookup_set(zalo_id, {
            "email": contact.email_id,
            "contact": contact.name,
            "ticket": ticket,
        })
        return {
            "chat_id": zalo_id,
            "email": contact.email_id,
            "contact": contact.name,
            "ticket": ticket,
        }

    return {"chat_id": zalo_id, "exists": False}


# ---------------------------------------------------------------------------
# Agent / authenticated endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_config():
    """Return Zalo config for frontend."""
    settings = get_zalo_settings()
    return {
        "enabled": settings["enabled"],
        "oa_id": settings["oa_id"] or "",
        "has_token": bool(settings.get("bot_token") or settings.get("access_token")),
        "has_bot_token": bool(settings.get("bot_token")),
    }


@frappe.whitelist()
def send_message(ticket: str, message: str, recipient_id: str | None = None, chat_id: str | None = None):
    """Send Zalo message for a ticket. Creates Communication with medium=Zalo."""
    if not is_agent():
        frappe.throw(_("Bạn không có quyền gửi Zalo"), frappe.PermissionError)
    if not is_zalo_enabled():
        frappe.throw(_("Tích hợp Zalo chưa được bật trong HD Settings"))
    if not message or not message.strip():
        frappe.throw(_("Nội dung tin nhắn không được trống"))

    chat_id = chat_id or recipient_id
    ticket_doc = frappe.get_doc("HD Ticket", ticket)
    if not chat_id:
        from helpdesk.utils.zalo import resolve_ticket_zalo_user_id

        chat_id = resolve_ticket_zalo_user_id(ticket_doc)
    communication = ticket_doc.create_zalo_communication(message, chat_id)

    if chat_id:
        try:
            result = send_zalo_message(chat_id, message)
            msg_id = None
            if isinstance(result, dict):
                msg_id = (result.get("result") or {}).get("message_id")
                if not msg_id:
                    msg_id = (result.get("data") or {}).get("message_id") or (result.get("data") or {}).get("msg_id")
            if msg_id:
                frappe.db.set_value("Communication", communication.name, "message_id", msg_id)
        except Exception as e:
            frappe.db.set_value("Communication", communication.name, "delivery_status", "Error")
            frappe.log_error(title="Zalo send_message failed", message=f"{ticket}: {e}")
            frappe.throw(str(e))
    else:
        frappe.msgprint(_("Đã lưu lịch sử Zalo nhưng chưa có user_id của khách."))

    return {"communication": communication.name}


@frappe.whitelist()
def set_webhook(url: str, secret_token: str | None = None):
    """Set Bot webhook."""
    from helpdesk.utils.zalo import set_zalo_webhook
    if not secret_token:
        secret_token = frappe.db.get_single_value("HD Settings", "zalo_secret_key")
    return set_zalo_webhook(url, secret_token)


@frappe.whitelist()
def get_zalo_link_status(ticket: str):
    """Link status for portal card."""
    _validate_ticket(ticket)
    frappe.has_permission("HD Ticket", "read", ticket, throw=True)

    contact, email = _get_ticket_contact_email(ticket)

    # Already linked — check logged-in user's Contact (not ticket's)
    user_email = frappe.db.get_value("User", frappe.session.user, "email")
    if user_email:
        user_contact = frappe.db.get_value("Contact", {"email_id": user_email}, "name")
        if not user_contact:
            user_contact = frappe.db.get_value("Contact", {"user": frappe.session.user}, "name")
        if user_contact:
            chat_id = frappe.db.get_value("Contact", user_contact, "zalo_user_id")
            if chat_id:
                return {
                    "state": "connected",
                    "email": email,
                    "zalo_name": frappe.db.get_value("Contact", user_contact, "first_name"),
                    "chat_id": chat_id,
                    "bot_link": V.BOT_LINK,
                }

    cache = frappe.cache()

    # Check pending code (90s, portal-generated)
    for key in _pending_keys(ticket, email):
        data = V.parse_cache_value(cache.get_value(key))
        if data and data.get("code"):
            remaining = _calc_remaining(data.get("expires_at"), max_seconds=95)
            if remaining is not None:
                return {
                    "state": "pending",
                    "email": email,
                    "code": data.get("code"),
                    "expires_at": data.get("expires_at"),
                    "remaining": remaining,
                    "bot_link": V.BOT_LINK,
                    "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={V.BOT_LINK}",
                }

    # Check legacy email OTP (10 min)
    if email:
        data = V.parse_cache_value(cache.get_value(V._key_email(email)))
        if data and data.get("chat_id"):
            remaining = _calc_remaining(data.get("expires_at"), max_seconds=660)
            return {
                "state": "pending",
                "email": email,
                "zalo_name": data.get("display_name"),
                "chat_id": data.get("chat_id"),
                "expires_at": data.get("expires_at"),
                "remaining": remaining or 600,
                "bot_link": V.BOT_LINK,
            }

    return {
        "state": "not_connected",
        "email": email,
        "bot_link": V.BOT_LINK,
        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={V.BOT_LINK}",
    }


@frappe.whitelist()
def generate_zalo_code(ticket: str):
    """Generate 6-digit code (90s TTL). Idempotent — returns existing code if still valid."""
    _validate_ticket(ticket)
    frappe.has_permission("HD Ticket", "read", ticket, throw=True)
    if not is_zalo_enabled():
        frappe.throw(_("Tích hợp Zalo chưa bật trong HD Settings"))

    contact, email = _get_ticket_contact_email(ticket)
    if not email or "@" not in email:
        frappe.throw(_("Ticket chưa có email liên hệ"))

    cache = frappe.cache()

    # Return existing code if still valid
    for key in [V._key_pending_ticket(ticket), V._key_pending_email(email)]:
        existing = V.parse_cache_value(cache.get_value(key))
        if existing and existing.get("code") and existing.get("expires_at"):
            remaining = _calc_remaining(existing["expires_at"])
            if remaining is not None and remaining > 0:
                return {"code": existing["code"], "expires_at": existing["expires_at"], "remaining": remaining, "email": email}
            # Expired — clean up
            cache.delete_value(V._key(existing["code"]))
            cache.delete_value(key)

    # Generate new code
    code = _generate_unique_code(cache)
    expires_at = add_to_date(now_datetime(), seconds=90).strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "email": email,
        "code": code,
        "ticket": ticket,
        "contact": contact,
        "user": frappe.session.user,
        "expires_at": expires_at,
    }
    cache.set_value(V._key(code), payload, expires_in_sec=90)
    cache.set_value(V._key_pending_email(email), payload, expires_in_sec=90)
    cache.set_value(V._key_pending_ticket(ticket), payload, expires_in_sec=90)
    return {"code": code, "expires_at": expires_at, "remaining": 90, "email": email}


@frappe.whitelist()
def resend_zalo_code(ticket: str):
    """Resend code — regenerate via generate_zalo_code."""
    _validate_ticket(ticket)
    frappe.has_permission("HD Ticket", "read", ticket, throw=True)
    return generate_zalo_code(ticket)


@frappe.whitelist()
def cancel_zalo_link(ticket: str):
    """Cancel pending link request (both 90s and legacy 10min flows)."""
    _validate_ticket(ticket)
    frappe.has_permission("HD Ticket", "read", ticket, throw=True)

    contact, email = _get_ticket_contact_email(ticket)
    cache = frappe.cache()

    # Cancel 90s pending
    for key in [V._key_pending_ticket(ticket), V._key_pending_email(email or "")]:
        data = V.parse_cache_value(cache.get_value(key))
        if data and data.get("code"):
            cache.delete_value(V._key(data["code"]))
        cache.delete_value(key)

    # Cancel legacy
    if email:
        data = V.parse_cache_value(cache.get_value(V._key_email(email)))
        if data and data.get("chat_id"):
            cache.delete_value(V._key(data["chat_id"]))
        cache.delete_value(V._key_email(email))

    # Invalidate lookup cache
    if contact:
        user_id = frappe.db.get_value("Contact", contact, "zalo_user_id")
        if user_id:
            V.cache_lookup_delete(user_id)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_request_body() -> dict:
    try:
        data = frappe.request.get_json(silent=True)
        if not data:
            raw = frappe.request.get_data(as_text=True)
            if raw:
                import json as _json
                try:
                    data = _json.loads(raw)
                except Exception:
                    data = frappe.form_dict
            else:
                data = frappe.form_dict
    except Exception:
        data = frappe.form_dict
    return data or {}


def _extract_message(data: dict):
    """Extract (chat_id, display_name, text) from webhook payload."""
    payload = data.get("result") if isinstance(data, dict) and "result" in data else data
    try:
        if not isinstance(payload, dict):
            return None, None, None
        message = payload.get("message") or (payload.get("event_name") and payload.get("message"))
        if not message:
            return None, None, None
        chat = message.get("chat") or {}
        from_user = message.get("from") or {}
        return (
            chat.get("id"),
            from_user.get("display_name") or from_user.get("first_name") or "Zalo User",
            message.get("text") or message.get("caption") or "",
        )
    except Exception as e:
        frappe.log_error(title="Zalo webhook parse error", message=str(e))
        return None, None, None


def _handle_verification(chat_id: str, display_name: str, text: str):
    """Process a 6-digit code from Bot. Returns response dict."""
    text = text.strip()

    if not re.match(r"^\d{6}$", text):
        return {}

    cache = frappe.cache()
    data = V.parse_cache_value(cache.get_value(V._key(text)))

    if not data or data.get("code") != text:
        frappe.local.response.http_status_code = 404
        return {"message": "Code not found"}

    # Check expiry
    expires_at = data.get("expires_at")
    if expires_at and get_datetime(expires_at) < now_datetime():
        cache.delete_value(V._key(text))
        if data.get("email"):
            cache.delete_value(V._key_pending_email(data["email"]))
        if data.get("ticket"):
            cache.delete_value(V._key_pending_ticket(data["ticket"]))
        frappe.local.response.http_status_code = 404
        return {"message": "Code expired"}

    email = data.get("email")
    ticket = data.get("ticket")
    contact_name = data.get("contact") or frappe.db.get_value("Contact", {"email_id": email}, "name")
    if not contact_name:
        contact_name = frappe.db.get_value("Contact", {"zalo_user_id": chat_id}, "name")

    # Upsert Contact
    if contact_name:
        frappe.db.set_value("Contact", contact_name, "zalo_user_id", chat_id)
    else:
        contact_name = _create_contact(display_name, email, chat_id)

    # Clean up pending cache
    cache.delete_value(V._key(text))
    if email:
        cache.delete_value(V._key_pending_email(email))
    if ticket:
        cache.delete_value(V._key_pending_ticket(ticket))

    # Write lookup cache
    V.cache_lookup_set(chat_id, {"email": email, "contact": contact_name, "ticket": ticket})

    # Publish realtime
    _publish_linked(ticket, email, chat_id)

    return {"message": "Linked", "email": email, "chat_id": chat_id}


def _create_contact(display_name: str, email: str, chat_id: str) -> str | None:
    try:
        parts = (display_name or "Zalo User").split(" ", 1)
        contact = frappe.new_doc("Contact")
        contact.first_name = parts[0] or "Zalo"
        if len(parts) > 1:
            contact.last_name = parts[1]
        contact.email_id = email
        contact.set("zalo_user_id", chat_id)
        contact.save(ignore_permissions=True)
        return contact.name
    except Exception as e:
        frappe.log_error(title="Create Contact on Zalo verify", message=str(e))
        return None



def _publish_linked(ticket: str | None, email: str | None, chat_id: str):
    try:
        if email:
            real_user = frappe.db.get_value("User", email, "name")
            if real_user:
                frappe.publish_realtime("helpdesk:zalo-linked", {"ticket": ticket, "email": email, "chat_id": chat_id}, user=real_user, after_commit=True)
        frappe.publish_realtime("helpdesk:zalo-linked", {"ticket": ticket, "email": email, "chat_id": chat_id}, after_commit=True)
    except Exception as e:
        frappe.log_error(title="Zalo _publish_linked error", message=str(e))


def _get_ticket_contact_email(ticket: str) -> tuple[str | None, str | None]:
    try:
        doc = frappe.get_doc("HD Ticket", ticket)
        contact = doc.contact
        email = frappe.db.get_value("Contact", contact, "email_id") if contact else None
        if not email and doc.raised_by and "@" in doc.raised_by:
            email = doc.raised_by
        return contact, email
    except Exception:
        return None, None


def _validate_ticket(ticket):
    if not isinstance(ticket, str) or not ticket or not ticket.strip():
        frappe.throw(_("Invalid ticket"), exc=frappe.ValidationError)


def _pending_keys(ticket: str, email: str | None) -> list[str]:
    keys = []
    if ticket:
        keys.append(V._key_pending_ticket(ticket))
    if email:
        keys.append(V._key_pending_email(email))
    return keys


def _calc_remaining(expires_at: str | None, max_seconds: int = 95) -> int | None:
    if not expires_at:
        return None
    try:
        diff = (get_datetime(expires_at) - now_datetime()).total_seconds()
        remaining = max(0, int(diff))
        return remaining if remaining <= max_seconds else None
    except Exception:
        return None


def _generate_unique_code(cache) -> str:
    for _ in range(12):
        code = f"{random.randint(100000, 999999)}"
        key = V._key(code)
        try:
            if hasattr(cache, "cache") and hasattr(cache.cache, "set"):
                added = cache.cache.set(key, '{"_reserved":1}', nx=True, ex=90)
                if added:
                    cache.delete_value(key)
                    return code
                continue
        except Exception:
            pass
        if not cache.get_value(key):
            return code
    frappe.throw(_("Không tạo được mã, vui lòng thử lại sau"))
