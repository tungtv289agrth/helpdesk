"""Zalo secret verification and cache helpers."""

import json

import frappe
from frappe.utils.password import get_decrypted_password

BOT_LINK = "https://bot.zaloplatforms.com/bots/2741100038390236707"


# ---------------------------------------------------------------------------
# Secret verification
# ---------------------------------------------------------------------------

def verify_secret() -> bool:
    """Verify webhook secret token. Returns True if valid.

    On failure, sets ``frappe.local.response.http_status_code`` and
    ``frappe.local.response.message`` so the caller can ``return`` immediately.
    """
    secret = get_decrypted_password("HD Settings", "HD Settings", "zalo_secret_key")
    if not secret:
        frappe.local.response.http_status_code = 401
        frappe.local.response.message = {"message": "Secret not configured"}
        return False

    token = (
        frappe.request.headers.get("X-Bot-Api-Secret-Token")
        or frappe.form_dict.get("secret_token")
        or frappe.form_dict.get("X-Bot-Api-Secret-Token")
    )

    if not token:
        try:
            raw = frappe.request.get_data(as_text=True)
            if raw:
                body = json.loads(raw)
                if isinstance(body, dict):
                    token = body.get("secret_token") or body.get("X-Bot-Api-Secret-Token")
        except Exception:
            pass

    if not token or token != secret:
        frappe.local.response.http_status_code = 401
        frappe.local.response.message = {"message": "Invalid secret token"}
        return False

    return True


# ---------------------------------------------------------------------------
# Cache helpers — centralized keys + read/write
# ---------------------------------------------------------------------------

def _key(code: str) -> str:
    return f"zalo_code:{code}"

def _key_email(email: str) -> str:
    return f"zalo_verify_email:{email.lower().strip()}"

def _key_chat(chat_id: str) -> str:
    return f"zalo_verify:{chat_id}"

def _key_pending_ticket(ticket: str) -> str:
    return f"zalo_pending_ticket:{ticket}"

def _key_pending_email(email: str) -> str:
    return f"zalo_pending_email:{email.lower().strip()}"

def _key_lookup(zalo_id: str) -> str:
    return f"zalo_lookup:{zalo_id}"


def cache_lookup_get(zalo_id: str) -> dict | None:
    """Get cached link result for a zalo_id. Returns None if miss."""
    val = frappe.cache().get_value(_key_lookup(zalo_id))
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except Exception:
            return None
    return val


def cache_lookup_set(zalo_id: str, data: dict, ttl: int = 86400):
    """Cache link result for a zalo_id. Default TTL 24h."""
    frappe.cache().set_value(_key_lookup(zalo_id), data, expires_in_sec=ttl)


def cache_lookup_delete(zalo_id: str):
    """Delete cached link result for a zalo_id."""
    frappe.cache().delete_value(_key_lookup(zalo_id))


def parse_cache_value(val):
    """Parse a cache value that might be JSON string or dict. Returns dict or None."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return None
    return val if isinstance(val, dict) else None
