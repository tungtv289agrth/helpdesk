"""Contact lifecycle hooks for Zalo integration."""


def on_contact_update(doc, method):
    """Invalidate zalo_lookup cache when zalo_user_id changes."""
    old = doc.get_doc_before_save()
    if not old:
        return

    old_val = old.get("zalo_user_id")
    new_val = doc.get("zalo_user_id")

    if old_val != new_val:
        from helpdesk.api.zalo._verify import cache_lookup_delete
        if old_val:
            cache_lookup_delete(old_val)
        if new_val:
            cache_lookup_delete(new_val)
