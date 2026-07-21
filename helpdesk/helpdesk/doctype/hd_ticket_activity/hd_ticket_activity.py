# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HDTicketActivity(Document):
    pass


def log_ticket_activity(ticket, action, activity_type=None, extra_value=None):
    return frappe.get_doc(
        {
            "doctype": "HD Ticket Activity",
            "ticket": ticket,
            "action": action,
            "activity_type": activity_type,
            "extra_value": extra_value,
        }
    ).insert(ignore_permissions=True)
