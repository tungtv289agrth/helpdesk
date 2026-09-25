import re

import frappe
import requests
from frappe import _


def get_zalo_settings():
    """Return Zalo settings as dict. Supports both Bot Token (preferred) and OA legacy."""
    oa_id, access_token, bot_token, enabled = frappe.db.get_value(
        "HD Settings",
        "HD Settings",
        ["zalo_oa_id", "zalo_access_token", "zalo_bot_token", "enable_zalo_integration"],
    )
    # Password fields are encrypted, need get_single_value with decrypt
    if not access_token:
        access_token = frappe.db.get_single_value("HD Settings", "zalo_access_token")
    if not bot_token:
        bot_token = frappe.db.get_single_value("HD Settings", "zalo_bot_token")
    return {
        "oa_id": oa_id,
        "access_token": access_token,
        "bot_token": bot_token,
        "enabled": bool(int(enabled or 0)),
    }


def is_zalo_enabled():
    return bool(int(frappe.db.get_single_value("HD Settings", "enable_zalo_integration") or 0))


def get_bot_token() -> str | None:
    return frappe.db.get_single_value("HD Settings", "zalo_bot_token")


def strip_html_to_text(html: str) -> str:
    """Strip HTML tags for Zalo text message."""
    if not html:
        return ""
    # Remove html tags
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n").strip()


def send_zalo_message(recipient_id: str, message: str, bot_token: str | None = None, access_token: str | None = None):
    """
    Send message via Zalo Bot API (preferred) or fallback to OA.

    Bot API (https://docs.zaloplatforms.com/docs/BOT/apis/sendMessage):
        POST https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendMessage
        Body: { chat_id: "...", text: "..." }
        Response: { ok: true, result: { message_id: "..." } }

    OA fallback:
        POST https://openapi.zalo.me/v3.0/oa/message/cs
        Headers: access_token
        Body: { recipient: {user_id: ...}, message: {text: ...}}
    """
    if not recipient_id:
        frappe.throw(_("Recipient Zalo ID (chat_id) is required"))

    # Resolve tokens: prefer Bot Token
    if not bot_token:
        bot_token = frappe.db.get_single_value("HD Settings", "zalo_bot_token")
    if bot_token:
        # Use Bot API
        text = strip_html_to_text(message)
        if not text:
            text = message
        if len(text) > 2000:
            text = text[:2000]

        url = f"https://bot-api.zaloplatforms.com/bot{bot_token}/sendMessage"
        payload = {"chat_id": recipient_id, "text": text}

        data = {}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json() if resp.content else {}
        except Exception as e:
            frappe.log_error(title="Zalo Bot send failed", message=str(e))
            frappe.throw(_("Gửi Zalo Bot thất bại: {0}").format(str(e)))

        # Bot API returns { ok: true, result: {message_id} } or { ok: false, error: ... }
        if isinstance(data, dict) and not data.get("ok"):
            err_msg = data.get("description") or data.get("error") or str(data)
            frappe.log_error(title="Zalo Bot API error", message=str(data))
            frappe.throw(_("Zalo Bot API lỗi: {0}").format(err_msg))
        return data

    # Fallback to OA if no Bot Token
    if not access_token:
        access_token = frappe.db.get_single_value("HD Settings", "zalo_access_token")
    if not access_token:
        frappe.throw(_("Zalo Bot Token chưa được cấu hình trong HD Settings > Zalo (hoặc OA Access Token legacy)"))

    text = strip_html_to_text(message)
    if not text:
        text = message
    if len(text) > 2000:
        text = text[:2000]

    url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {"access_token": access_token, "Content-Type": "application/json"}
    payload = {"recipient": {"user_id": recipient_id}, "message": {"text": text}}

    data = {}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        data = resp.json() if resp.content else {}
    except Exception as e:
        frappe.log_error(title="Zalo OA send failed", message=str(e))
        frappe.throw(_("Gửi Zalo thất bại: {0}").format(str(e)))

    if isinstance(data, dict) and data.get("error") not in (0, None):
        err_msg = data.get("message") or str(data)
        frappe.log_error(title="Zalo OA API error", message=str(data))
        frappe.throw(_("Zalo API lỗi: {0}").format(err_msg))
    return data


def set_zalo_webhook(webhook_url: str, secret_token: str | None = None):
    """Helper to set Bot webhook via API."""
    bot_token = frappe.db.get_single_value("HD Settings", "zalo_bot_token")
    if not bot_token:
        frappe.throw(_("Chưa cấu hình Zalo Bot Token"))
    if not secret_token:
        secret_token = frappe.db.get_single_value("HD Settings", "zalo_secret_key") or "default-secret"
    url = f"https://bot-api.zaloplatforms.com/bot{bot_token}/setWebhook"
    payload = {"url": webhook_url, "secret_token": secret_token}
    resp = requests.post(url, json=payload, timeout=10)
    return resp.json() if resp.content else {}


def _get_or_create_user_contact() -> str:
    """Get or create Contact linked to the currently logged-in user."""
    # 1. Match by user field
    contact = frappe.db.get_value("Contact", {"user": frappe.session.user})
    if contact:
        return contact

    # 2. Match by email (only if not linked to another user)
    user_email = frappe.db.get_value("User", frappe.session.user, "email")
    if user_email:
        contact = frappe.db.get_value(
            "Contact", {"email_id": user_email, "user": ("in", ("", None))}
        )
        if contact:
            frappe.db.set_value("Contact", contact, "user", frappe.session.user)
            return contact

    # 3. Create new Contact
    user_doc = frappe.get_doc("User", frappe.session.user)
    first_name = user_doc.first_name or frappe.session.user.split("@")[0]
    last_name = user_doc.last_name or ""

    contact_doc = frappe.get_doc(
        {
            "doctype": "Contact",
            "first_name": first_name,
            "last_name": last_name,
            "user": frappe.session.user,
        }
    )
    if user_email:
        contact_doc.append("email_ids", {"email_id": user_email, "is_primary": True})
    contact_doc.insert(ignore_permissions=True)
    return contact_doc.name


def resolve_ticket_zalo_user_id(ticket) -> str | None:
    """
    Resolve Zalo user_id for a ticket.

    Priority:
    1. Contact (of logged-in user).zalo_user_id if exists
    2. Contact (of logged-in user).mobile_no / phone (fallback)
    3. ticket.raised_by if looks like chat_id
    """
    # Check contact of logged-in user
    contact = _get_or_create_user_contact()
    try:
        zalo_id = frappe.db.get_value("Contact", contact, "zalo_user_id")
        if zalo_id:
            return zalo_id
    except Exception:
        pass

    # Fallback to mobile
    mobile = frappe.db.get_value("Contact", contact, "mobile_no") or frappe.db.get_value(
        "Contact", contact, "phone"
    )
    if mobile:
        mobile = re.sub(r"\D", "", mobile)
        return mobile

    if ticket.raised_by and "@" not in ticket.raised_by:
        return re.sub(r"\D", "", ticket.raised_by)
    return None


def get_zalo_user_id_for_ticket(ticket) -> str | None:
    """Legacy alias for resolve_ticket_zalo_user_id."""
    return resolve_ticket_zalo_user_id(ticket)
