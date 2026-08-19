# Local Customizations & Git Conflict Resolution Reference

Branch `main` đang diverge với `origin/main` (ahead 9, behind 269). Khi pull/rebase
từ `origin/main` sẽ có nhiều conflict. Các file trong thư mục `docs/` này là
**nguồn tham chiếu duy nhất** để resolve conflict — ưu tiên giữ logic local
(customization) trừ khi được ghi chú khác.

## Quy tắc chung khi merge

1. **Luôn đọc docs trước khi resolve.** Mỗi docs mô tả feature, file bị ảnh hưởng,
   và quyết định conflict nên giữ bản nào.
2. **Local customizations dành cho hệ thống nội bộ (Agribank)**: Zalo support,
   Switch app, favicon.ico, __() wrapper, AI upload. Những thứ này **không có trên
   upstream** — khi conflict phải giữ bản local.
3. **File mới của local (không tồn tại ở merge-base)** hầu như không có conflict,
   nhưng phải **giữ nguyên** khi merge (AI upload, docs, deploy.sh).
4. **Thay đổi backend có DB schema** (HD Ticket Activity activity_type/extra_value)
   phải được tái áp dụng sau khi merge bằng `bench migrate`.
5. Không bao giờ `git checkout --ours/theirs` mù — luôn xem docs tương ứng.

## Danh sách commit local (author: tungtranviet)

| Commit | Mô tả | Feature doc |
|--------|-------|-------------|
| `207771fdf` | wrap tất cả UI strings bằng `__()`/_() | [feature-i18n-translation.md](feature-i18n-translation.md) |
| `8bd40115f` | HD Ticket Activity thêm activity_type/extra_value + fix AssignTo | [feature-activity-type.md](feature-activity-type.md), [feature-i18n-translation.md](feature-i18n-translation.md) |
| `63afb5db2` | i18n CommunicationArea/TicketField/Link/TicketDetailsTab + deploy.sh | [feature-i18n-translation.md](feature-i18n-translation.md) |
| `03e3d1c1f` | bỏ customer khỏi coreFields trong TicketDetailsTab | [feature-ticket-details.md](feature-ticket-details.md) |
| `994e3fba9` | wrap status/priority/ticket_type với __() | [feature-i18n-translation.md](feature-i18n-translation.md) |
| `c1ca0cfdd` | nút Reopen Ticket cho customer | [feature-reopen-ticket.md](feature-reopen-ticket.md) |
| `8779ed2e7` | dùng favicon.ico làm logo & favicon | [feature-branding-favicon.md](feature-branding-favicon.md) |
| `2efc266ee` | bỏ Apps/Help/Docs menur, thêm Switch app + Zalo link | [feature-sidebar-zalo.md](feature-sidebar-zalo.md) |
| `c827d5c09` | AI file upload tự điền title/description | [feature-ai-summary.md](feature-ai-summary.md) |

## File bị conflict nhiều khả năng nhất (đã sửa cả 2 bên)

| File | Hướng dẫn |
|------|-----------|
| `desk/src/components/layouts/Sidebar.vue` | [feature-sidebar-zalo.md](feature-sidebar-zalo.md) |
| `desk/src/components/ticket-agent/TicketDetailsTab.vue` | [feature-ticket-details.md](feature-ticket-details.md), [feature-i18n-translation.md](feature-i18n-translation.md) |
| `desk/src/components/ticket-agent/TicketActivityPanel.vue` | [feature-activity-type.md](feature-activity-type.md) |
| `desk/src/pages/ticket/Tickets.vue` | [feature-i18n-translation.md](feature-i18n-translation.md) |
| `helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py` | [feature-activity-type.md](feature-activity-type.md) |
| `helpdesk/helpdesk/doctype/hd_ticket/api.py` | [feature-activity-type.md](feature-activity-type.md) |
| `helpdesk/helpdesk/doctype/hd_ticket_activity/*.json` | [feature-activity-type.md](feature-activity-type.md) |
| `helpdesk/api/doc.py`, `helpdesk/utils.py` | [feature-i18n-translation.md](feature-i18n-translation.md) |
| `desk/src/pages/ticket/TicketNew.vue` | [feature-ai-summary.md](feature-ai-summary.md) |
| `pyproject.toml` | [feature-ai-summary.md](feature-ai-summary.md) |
| `desk/index.html`, `helpdesk/api/config.py`, `helpdesk/hooks.py` | [feature-branding-favicon.md](feature-branding-favicon.md) |

## Workflow đề xuất khi pull

```bash
git fetch origin
git merge origin/main      # hoặc: git rebase origin/main
```

Khi có conflict từng file:
1. Mở docs tương ứng trong bảng trên.
2. Theo "Quyết định conflict" trong docs: giữ local / giữ upstream / merge cả hai.
3. Sau khi resolve xong: chạy `bench migrate` + `bench build` (hoặc `yarn build`
   trong `desk/`) trước khi test.