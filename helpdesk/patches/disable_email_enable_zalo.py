import frappe


def execute():
    # Tắt toàn bộ email workflow theo yêu cầu: thay bằng Zalo 1 chiều
    frappe.db.set_single_value("HD Settings", "skip_email_workflow", 1)
    frappe.db.set_single_value("HD Settings", "send_acknowledgement_email", 0)
    frappe.db.set_single_value("HD Settings", "enable_email_ticket_feedback", 0)
    frappe.db.set_single_value("HD Settings", "enable_reply_email_to_agent", 0)
    frappe.db.set_single_value("HD Settings", "enable_reply_email_via_agent", 0)
    frappe.db.set_single_value("HD Settings", "instantly_send_email", 0)
    # Bật Zalo integration mặc định (token vẫn cần cấu hình thủ công)
    # Không bật auto để tránh lỗi nếu chưa có token, để admin bật trong UI
