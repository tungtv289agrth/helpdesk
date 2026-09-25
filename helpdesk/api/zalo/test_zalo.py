"""Unit tests for Zalo integration.

Run: bench --site <site> run-tests --module helpdesk.api.zalo.test_zalo
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from helpdesk.api.zalo import (
    _calc_remaining,
    _create_contact,
    _extract_message,
    _generate_unique_code,
    _get_ticket_contact_email,
    _handle_verification,
    _pending_keys,
    _publish_linked,
    check_zalo_id,
    generate_zalo_code,
    get_zalo_link_status,
    cancel_zalo_link,
)
from helpdesk.api.zalo import _verify as V
from helpdesk.test_utils import make_ticket


class TestExtractMessage(FrappeTestCase):
    def test_valid_payload(self):
        data = {
            "result": {
                "message": {
                    "chat": {"id": "chat_123"},
                    "from": {"display_name": "Test User"},
                    "text": "Hello",
                }
            }
        }
        chat_id, name, text = _extract_message(data)
        self.assertEqual(chat_id, "chat_123")
        self.assertEqual(name, "Test User")
        self.assertEqual(text, "Hello")

    def test_flat_payload(self):
        data = {
            "message": {
                "chat": {"id": "chat_456"},
                "from": {"first_name": "Bot User"},
                "text": "123456",
            }
        }
        chat_id, name, text = _extract_message(data)
        self.assertEqual(chat_id, "chat_456")
        self.assertEqual(name, "Bot User")
        self.assertEqual(text, "123456")

    def test_empty_payload(self):
        self.assertEqual(_extract_message({}), (None, None, None))
        self.assertEqual(_extract_message(None), (None, None, None))
        self.assertEqual(_extract_message("invalid"), (None, None, None))

    def test_missing_chat(self):
        data = {"message": {"from": {"display_name": "X"}, "text": "hi"}}
        chat_id, _, _ = _extract_message(data)
        self.assertIsNone(chat_id)

    def test_caption_fallback(self):
        data = {
            "message": {
                "chat": {"id": "c1"},
                "from": {"display_name": "User"},
                "caption": "caption text",
            }
        }
        _, _, text = _extract_message(data)
        self.assertEqual(text, "caption text")


class TestCalcRemaining(FrappeTestCase):
    def test_future_time(self):
        future = add_to_date(now_datetime(), seconds=60).strftime("%Y-%m-%d %H:%M:%S")
        result = _calc_remaining(future)
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 95)

    def test_past_time(self):
        past = add_to_date(now_datetime(), seconds=-10).strftime("%Y-%m-%d %H:%M:%S")
        result = _calc_remaining(past)
        self.assertEqual(result, 0)

    def test_none_input(self):
        self.assertIsNone(_calc_remaining(None))
        self.assertIsNone(_calc_remaining(""))

    def test超出max_seconds(self):
        future = add_to_date(now_datetime(), seconds=200).strftime("%Y-%m-%d %H:%M:%S")
        result = _calc_remaining(future, max_seconds=95)
        self.assertIsNone(result)


class TestGenerateUniqueCode(FrappeTestCase):
    def test_generates_6_digit_code(self):
        cache = frappe.cache()
        code = _generate_unique_code(cache)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_generates_unique_codes(self):
        cache = frappe.cache()
        codes = {_generate_unique_code(cache) for _ in range(5)}
        self.assertEqual(len(codes), 5)


class TestCheckZaloId(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.cache().delete_value(V._key_lookup("test_zalo_001"))
        super().tearDown()

    def test_missing_chat_id(self):
        result = check_zalo_id(chat_id=None)
        self.assertIn("message", result)

    def test_nonexistent_id_returns_exists_false(self):
        result = check_zalo_id(chat_id="nonexistent_zalo_id_xyz")
        self.assertFalse(result.get("exists"))
        self.assertEqual(result["chat_id"], "nonexistent_zalo_id_xyz")

    def test_existing_id_via_cache(self):
        V.cache_lookup_set("test_zalo_001", {
            "email": "test@example.com",
            "contact": "C-001",
            "ticket": "HD-TICKET-001",
        })
        result = check_zalo_id(chat_id="test_zalo_001")
        self.assertEqual(result["email"], "test@example.com")
        self.assertEqual(result["contact"], "C-001")

    def test_existing_id_via_db(self):
        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "ZaloTest",
            "zalo_user_id": "test_zalo_002",
        })
        contact.append("email_ids", {"email_id": "zalo-test@example.com", "is_primary": True})
        contact.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

        result = check_zalo_id(chat_id="test_zalo_002")
        self.assertEqual(result["email"], "zalo-test@example.com")
        self.assertEqual(result["contact"], contact.name)


class TestGetZaloLinkStatus(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_not_connected(self):
        ticket = make_ticket(subject="Zalo Test Ticket")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)
        result = get_zalo_link_status(ticket.name)
        self.assertEqual(result["state"], "not_connected")

    def test_connected_via_user_contact(self):
        user_email = "zalo-user@test.com"
        user = frappe.get_doc({
            "doctype": "User",
            "email": user_email,
            "first_name": "Zalo",
            "last_name": "User",
        })
        user.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "User", user.name, force=True)

        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "ZaloLinked",
            "user": user.name,
        })
        contact.append("email_ids", {"email_id": user_email, "is_primary": True})
        contact.set("zalo_user_id", "linked_zalo_id")
        contact.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

        ticket = make_ticket(subject="Zalo Status Test")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)

        frappe.set_user(user_email)
        result = get_zalo_link_status(ticket.name)
        self.assertEqual(result["state"], "connected")
        self.assertEqual(result["chat_id"], "linked_zalo_id")

    def test_pending_code(self):
        ticket = make_ticket(subject="Zalo Pending Test")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)

        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "Pending",
        })
        contact.append("email_ids", {"email_id": "pending@test.com", "is_primary": True})
        contact.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

        ticket.contact = contact.name
        ticket.save(ignore_permissions=True)

        cache = frappe.cache()
        code = "111222"
        expires_at = add_to_date(now_datetime(), seconds=80).strftime("%Y-%m-%d %H:%M:%S")
        payload = {"code": code, "email": "pending@test.com", "ticket": ticket.name, "contact": contact.name, "expires_at": expires_at}
        cache.set_value(V._key(code), payload, expires_in_sec=90)
        cache.set_value(V._key_pending_email("pending@test.com"), payload, expires_in_sec=90)
        cache.set_value(V._key_pending_ticket(ticket.name), payload, expires_in_sec=90)
        self.addCleanup(cache.delete_value, V._key(code))
        self.addCleanup(cache.delete_value, V._key_pending_email("pending@test.com"))
        self.addCleanup(cache.delete_value, V._key_pending_ticket(ticket.name))

        result = get_zalo_link_status(ticket.name)
        self.assertEqual(result["state"], "pending")
        self.assertEqual(result["code"], code)


class TestGenerateZaloCode(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.set_single_value("HD Settings", "enable_zalo_integration", 1)
        self.addCleanup(frappe.db.set_single_value, "HD Settings", "enable_zalo_integration", 0)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _make_ticket_with_contact(self):
        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "GenCode",
        })
        contact.append("email_ids", {"email_id": "gencode@test.com", "is_primary": True})
        contact.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

        ticket = make_ticket(subject="GenCode Test", raise_exception=False)
        ticket.contact = contact.name
        ticket.save(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)
        return ticket

    def test_generates_code(self):
        ticket = self._make_ticket_with_contact()
        result = generate_zalo_code(ticket.name)
        self.assertIn("code", result)
        self.assertEqual(len(result["code"]), 6)
        self.assertEqual(result["remaining"], 90)
        self.assertEqual(result["email"], "gencode@test.com")

        cache = frappe.cache()
        self.addCleanup(cache.delete_value, V._key(result["code"]))
        self.addCleanup(cache.delete_value, V._key_pending_email("gencode@test.com"))
        self.addCleanup(cache.delete_value, V._key_pending_ticket(ticket.name))

    def test_idempotent(self):
        ticket = self._make_ticket_with_contact()
        r1 = generate_zalo_code(ticket.name)
        r2 = generate_zalo_code(ticket.name)
        self.assertEqual(r1["code"], r2["code"])

        cache = frappe.cache()
        cache.delete_value(V._key(r1["code"]))
        cache.delete_value(V._key_pending_email("gencode@test.com"))
        cache.delete_value(V._key_pending_ticket(ticket.name))

    def test_no_email_throws(self):
        ticket = make_ticket(subject="No Email Ticket")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)
        with self.assertRaises(frappe.exceptions.ValidationError):
            generate_zalo_code(ticket.name)


class TestHandleVerification(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _setup_pending_code(self, code, email, ticket_name, contact_name):
        cache = frappe.cache()
        expires_at = add_to_date(now_datetime(), seconds=80).strftime("%Y-%m-%d %H:%M:%S")
        payload = {"code": code, "email": email, "ticket": ticket_name, "contact": contact_name, "expires_at": expires_at}
        cache.set_value(V._key(code), payload, expires_in_sec=90)
        return cache

    def test_valid_code_links_contact(self):
        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "VerifyTest",
        })
        contact.append("email_ids", {"email_id": "verify@test.com", "is_primary": True})
        contact.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

        ticket = make_ticket(subject="Verify Test")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)
        ticket.contact = contact.name
        ticket.save(ignore_permissions=True)

        code = "998877"
        cache = self._setup_pending_code(code, "verify@test.com", ticket.name, contact.name)
        self.addCleanup(cache.delete_value, V._key(code))

        result = _handle_verification("chat_from_bot", "Bot Tester", code)
        self.assertEqual(result["message"], "Linked")
        self.assertEqual(result["email"], "verify@test.com")
        self.assertEqual(result["chat_id"], "chat_from_bot")

        saved = frappe.db.get_value("Contact", contact.name, "zalo_user_id")
        self.assertEqual(saved, "chat_from_bot")

    def test_invalid_code_returns_404(self):
        result = _handle_verification("chat1", "User", "000000")
        self.assertEqual(result.get("message"), "Code not found")

    def test_non_digit_text_ignored(self):
        result = _handle_verification("chat1", "User", "not a code")
        self.assertEqual(result, {})

    def test_expired_code(self):
        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "ExpiredTest",
        })
        contact.append("email_ids", {"email_id": "expired@test.com", "is_primary": True})
        contact.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

        ticket = make_ticket(subject="Expired Test")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)

        cache = frappe.cache()
        code = "554433"
        expires_at = add_to_date(now_datetime(), seconds=-10).strftime("%Y-%m-%d %H:%M:%S")
        payload = {"code": code, "email": "expired@test.com", "ticket": ticket.name, "contact": contact.name, "expires_at": expires_at}
        cache.set_value(V._key(code), payload, expires_in_sec=90)

        result = _handle_verification("chat1", "User", code)
        self.assertEqual(result.get("message"), "Code expired")

    def test_creates_contact_when_none_exists(self):
        ticket = make_ticket(subject="New Contact Test")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)
        ticket.raised_by = "newcontact@test.com"
        ticket.save(ignore_permissions=True)

        cache = frappe.cache()
        code = "667788"
        expires_at = add_to_date(now_datetime(), seconds=80).strftime("%Y-%m-%d %H:%M:%S")
        payload = {"code": code, "email": "newcontact@test.com", "ticket": ticket.name, "contact": None, "expires_at": expires_at}
        cache.set_value(V._key(code), payload, expires_in_sec=90)

        result = _handle_verification("new_chat_id", "New Contact User", code)
        self.assertEqual(result["message"], "Linked")

        contact_name = frappe.db.get_value("Contact", {"email_id": "newcontact@test.com"}, "name")
        self.assertIsNotNone(contact_name)
        self.addCleanup(frappe.delete_doc, "Contact", contact_name, force=True)

        zalo_id = frappe.db.get_value("Contact", contact_name, "zalo_user_id")
        self.assertEqual(zalo_id, "new_chat_id")


class TestCreateContact(FrappeTestCase):
    def test_creates_contact_with_email(self):
        result = _create_contact("Test User", "create-test@example.com", "chat_999")
        self.assertIsNotNone(result)
        self.addCleanup(frappe.delete_doc, "Contact", result, force=True)

        zalo_id = frappe.db.get_value("Contact", result, "zalo_user_id")
        email = frappe.db.get_value("Contact", result, "email_id")
        self.assertEqual(zalo_id, "chat_999")
        self.assertEqual(email, "create-test@example.com")

    def test_creates_contact_with_single_name(self):
        result = _create_contact("Singly", "single@example.com", "chat_s1")
        self.assertIsNotNone(result)
        self.addCleanup(frappe.delete_doc, "Contact", result, force=True)

        first = frappe.db.get_value("Contact", result, "first_name")
        self.assertEqual(first, "Singly")


class TestPendingKeys(FrappeTestCase):
    def test_with_ticket_and_email(self):
        keys = _pending_keys("T-001", "a@b.com")
        self.assertEqual(len(keys), 2)

    def test_with_ticket_only(self):
        keys = _pending_keys("T-002", None)
        self.assertEqual(len(keys), 1)

    def test_with_email_only(self):
        keys = _pending_keys("", "c@d.com")
        self.assertEqual(len(keys), 1)

    def test_empty(self):
        keys = _pending_keys("", None)
        self.assertEqual(len(keys), 0)


class TestCancelZaloLink(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_cancels_pending_code(self):
        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "CancelTest",
        })
        contact.append("email_ids", {"email_id": "cancel@test.com", "is_primary": True})
        contact.insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Contact", contact.name, force=True)

        ticket = make_ticket(subject="Cancel Test")
        self.addCleanup(frappe.delete_doc, "HD Ticket", ticket.name, force=True)
        ticket.contact = contact.name
        ticket.save(ignore_permissions=True)

        cache = frappe.cache()
        code = "112233"
        expires_at = add_to_date(now_datetime(), seconds=80).strftime("%Y-%m-%d %H:%M:%S")
        payload = {"code": code, "email": "cancel@test.com", "ticket": ticket.name, "contact": contact.name, "expires_at": expires_at}
        cache.set_value(V._key(code), payload, expires_in_sec=90)
        cache.set_value(V._key_pending_email("cancel@test.com"), payload, expires_in_sec=90)
        cache.set_value(V._key_pending_ticket(ticket.name), payload, expires_in_sec=90)

        result = cancel_zalo_link(ticket.name)
        self.assertTrue(result["ok"])

        self.assertIsNone(cache.get_value(V._key(code)))
        self.assertIsNone(cache.get_value(V._key_pending_email("cancel@test.com")))
        self.assertIsNone(cache.get_value(V._key_pending_ticket(ticket.name)))
