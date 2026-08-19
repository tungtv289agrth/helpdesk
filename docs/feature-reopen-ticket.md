# Feature: Reopen Ticket button (customer portal)

Thay đổi từ commit `c1ca0cfdd`.

## Ý định / logic

Trên ticket view của **customer portal** (`desk/src/pages/ticket/TicketCustomer.vue`),
khi ticket có status gốc **Resolved**, customer thấy nút **"Reopen Ticket"**
(icon LucideRotateCcw) để mở lại ticket thành **Open**. Upstream chỉ cho phép
customer **Close** ticket, không có nút mở lại → ticket bị đóng/resolved mà
customer muốn hỏi tiếp thì phải tạo ticket mới.

Chi tiết:

- `onSuccess` của resource lưu `data._original_status = data.status` trước khi
  thay bằng `label_customer` (vì sau bước này `status` là label tiếng Việt).
  Nút hiển thị khi `_original_status === "Resolved"`.
- `handleReopen()` mở `$dialog` xác nhận "Reopen Ticket" → gọi `setValue.submit(
  { fieldname: "status", value: "Open" })` → toast "Ticket reopened successfully."

## Quyết định conflict (resolving priority: giữ LOCAL)

- **File `TicketCustomer.vue`**: giữ nút Reopen + `_original_status` + `handleReopen`.
- Khi upstream refactor ticket customer view:
  - Bảo toàn việc lưu `_original_status` trong `onSuccess` gần nơi set `label_customer`.
  - Chèn lại nút Reopen trong group nút hành động (có icon prefix).
  - Giữ logic `setValue.submit` (cùng endpoint mà nút Close đang dùng).
- Nếu upstream thêm trạng thái mới ngoài `Resolved` mà cần reopen — bổ sung điều
  kiện sau khi merge, nhưng mặc định giữ đúng hành vi cũ (chỉ Resolved).

## Sau merge

- Test trên customer portal: mở ticket Resolved → thấy nút Reopen → bấm → xác nhận
  → status thành Open, ticket agent thấy hoạt động mới.