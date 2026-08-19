# Feature: HD Ticket Activity — `activity_type` / `extra_value` + fix AssignTo

Thay đổi từ commit `8bd40115f`.

## Ý định / logic

Upstream log hoạt động ticket chỉ bằng chuỗi `action` tiếng Anh (vd
`"set status to Open"`, `"assigned tung"`) được tạo **trên backend bằng string
tĩnh**. Vì string không qua `_()`, không thể dịch. Local sửa theo hướng:

1. **Thêm 2 trường chuẩn hoá** vào `HD Ticket Activity`:
   - `activity_type` (Select): `Field Changed`, `Field Cleared`, `Ticket Split`,
     `Auto Closed`, `Assignment` — để frontend phân loại & dịch đúng.
   - `extra_value` (Text): dữ liệu cấu trúc đi kèm.
2. **Frontend render lại từ 2 trường này** (không hiển thị raw `action`),
   với backward-compat cho record cũ (không có activity_type → dùng `action` cũ).
3. **Fix AssignTo**: trước đây lỗi khi log activity (sau khi API đổi thành công)
   sẽ làm toast "Assignees updated" không hiện / bị coi là fail. Giờ log activity
   nằm ngoài try-catch chính — lỗi log chỉ `console.warn`, không revert kết quả.

## Chi tiết thay đổi

### Backend

- `helpdesk/helpdesk/doctype/hd_ticket_activity/hd_ticket_activity.json`:
  thêm field_order `activity_type`, `extra_value` trước `action`; 2 field mới
  (Select options `\nField Changed\nField Cleared\nTicket Split\nAuto Closed\nAssignment`).
  → **DB schema change: bắt buộc `bench migrate`.**
- `helpdesk/helpdesk/doctype/hd_ticket_activity/hd_ticket_activity.py`:
  `log_ticket_activity(ticket, action, activity_type=None, extra_value=None)`
  — thêm tham số mới (backward compatible, hàm cũ vẫn gọi được).
- `helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py`:
  - `on_update` field change detection: map field → tên tiếng Anh chuẩn hoá
    (`Status`, `Priority`, `Team`, `Ticket Type`, `Contact`, `SLA`) và log với
    `activity_type="Field Changed"`, `extra_value="<Field>||<new_value>"` hoặc
    `"Field Cleared"` + `extra_value=<Field>`.
  - `split` logic: `activity_type="Ticket Split"`, `extra_value="#<id>"`.
  - `close_tickets_after_n_days`: `activity_type="Auto Closed"`, `extra_value="N days"`.
- `helpdesk/helpdesk/doctype/hd_ticket/api.py` `get_history`: thêm `activity_type`,
  `extra_value` vào SELECT query.

### Frontend

- `desk/src/types.ts`: `Activity` interface thêm `activity_type?: string`, `extra_value?: string`.
- `desk/src/components/ticket-agent/TicketActivityPanel.vue`: render theo
  `activity_type` (Field Changed/Cleared, Ticket Split, Auto Closed, Assignment),
  backward-compat với activity cũ. Assignee grouping nay dựa trên `kind !== "view"`
  (trước dựa trên string "assigned"/"unassigned" — fragile).
- `desk/src/components/ticket-agent/AssignTo.vue`: `logActivity` ghi
  `activity_type: "Assignment"`, `extra_value = JSON.stringify({added, removed})`;
  **lỗi log không làm hỏng flow assign** (toast thành công vẫn hiện).

## Quyết định conflict (resolving priority: ưu tiên LOCAL schema)

- **Backend schema + logic log activity: luôn giữ bản local** — upstream không có
  `activity_type`/`extra_value`; nếu upstream cũng sửa các hàm đụng nhau, preserve:
  - `log_ticket_activity` phải giữ signature 4 tham số.
  - `get_history` phải trả `activity_type` + `extra_value`.
  - `field_maps` phải dùng label chuẩn hoá (`"Status"`, `"Priority"`…), không phải
    value raw.
- **Nếu upstream refactor `close_tickets_after_n_days` hoặc logic split**: lấy bản
  upstream làm base, rồi chèn thêm `activity_type`/`extra_value` vào call
  `log_ticket_activity` theo pattern local.
- **Frontend `TicketActivityPanel.vue`**: giữ `formatActivityContent` + grouping
  theo `kind` — đây là logic local quan trọng (upstream hiển thị raw action).
- Nếu upstream thêm trường/column mới vào `hd_ticket_activity.json`, merge các field
  lại (giữ cả 2 trường local + trường upstream). Luôn chạy `bench migrate` sau đó.

## Sau merge

- `bench migrate` (thêm 2 cột vào bảng `HD Ticket Activity`).
- Kiểm tra trang ticket agent: activity panel hiển thị đúng loại hoạt động,
  assign không báo lỗi sau khi đổi người phụ trách.