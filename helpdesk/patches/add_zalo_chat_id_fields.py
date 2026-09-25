from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(get_custom_fields())


def get_custom_fields():
    return {
        "Contact": [
            {
                "fieldname": "zalo_user_id",
                "label": "Zalo User ID",
                "fieldtype": "Data",
                "insert_after": "email_id",
                "description": "Zalo User ID (lấy từ webhook message.chat.id). Tự động lưu khi khách nhắn Bot.",
                "unique": 0,
                "translatable": 0,
            },
        ]
    }
