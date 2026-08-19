# Feature: i18n / Vietnamese Translation Wrapper (`__()`/_())

Liên quan các commit: `207771fdf`, `63afb5db2`, `994e3fba9`, `8bd40115f`
(phần frontend). `8bd40115f` còn thêm log hoạt động — xem [feature-activity-type.md](feature-activity-type.md).

## Mục đích

Helpdesk upstream hiển thị toàn bộ UI bằng tiếng Anh. Local gói ~60 file frontend + backend
(doc labels, column defaults, report labels) bằng `__()` / `_()` để có thể dịch sang
tiếng Việt qua bảng dịch của Frappe. Trước khi commit này, hầu hết string hiển thị trực tiếp
không qua wrapper nên không dịch được.

## Phạm vi thay đổi (chính)

- **Backend**
  - `helpdesk/api/doc.py`: `get_list_data`, `get_filterable_fields`, `sort_options`,
    `get_quick_filters` — bọc label động bằng `_()` (vd `_("Name")`, `_(field.label)`).
  - `helpdesk/utils.py`: `contact_default_columns` và các label khác bọc `_()`.
  - Các doctype/report label được bọc `_()`.
- **Frontend** (đại diện, <60 file):
  - `CommunicationArea.vue`: nút "Reply" → `__('Reply Ticket')`, "Comment" → `__('Comment Ticket')`.
  - `TicketField.vue`: Select option labels bọc `__()`.
  - `frappe-ui/Link.vue`: option labels từ `search_link` bọc `__()`.
  - `TicketDetailsTab.vue`: field labels, placeholders, status text bọc `__()`;
    **Select-type core fields chuyển sang dùng `Autocomplete`** với `selectOptions`
    đã dịch (xem [feature-ticket-details.md](feature-ticket-details.md)).
  - `TicketAgentActivities.vue`, `HistoryBox.vue`: empty-state và "Show/Hide changes from" bọc `__()`.
  - `Tickets.vue`: status/priority/ticket_type column values bọc `__()` qua `custom` renderer;
    label trả về từ `createListResource` bọc `__()`.
  - `207771fdf` cũng bỏ route & sidebar menu `CustomerList` không dùng.

## Quyết định conflict (resolving priority: GIỮ LOCAL)

> Câu trả lời của user: "viết docs để làm tham chiếu cho bất cứ lúc nào merge
> mà cần resolve conflict" — ưu tiên mặc định **giữ local `__()`**.

- **Bất kỳ file nào có hover/visible string** — nếu 1 bên là local (có `__()`/`_()`)
  và 1 bên là upstream (string thường), **giữ bản local**.
- Nếu upstream đã bọc string bằng `_()`/`__()` riêng của upstream (frappe-ui dùng `_()`),
  chấp nhận bản upstream miễn là string vẫn đi qua wrapper (không phá translate).
- `TicketDetailsTab.vue`: giữ block `Autocomplete` cho Select field và `selectOptions`
  — đây là thay đổi local quan trọng, upstream dùng `Link` component.
- `Tickets.vue`: giữ custom renderer `status`, `ticket_type`, `priority` (bọc `__()`).
- Nguyên tắc: **không bao giờ để UI hiển thị value thô (status/priority/type) không qua `__()`.**
- Khi upstream thêm feature mới có string mới trong file đang conflict — bọc `__()`
  cho string mới theo cùng pattern, không bỏ string cũ local.

## Lưu ý đặc biệt

- `deploy.sh` (tạo trong `63afb5db2`) — script deploy nội bộ (host `10.28.0.36`,
  rsync + SSH). Là file mới của local, **giữ nguyên** khi merge. Có thể cần cập nhật
  host/user tuỳ môi trường.
- Upstream có `helpdesk/locale/*.po` (vi.po đã tồn tại). Local **không** thêm vi.po —
  chỉ wrapper để Frappe translate engine hoạt động. Đừng merge bảng dịch upstream vào
  làm danh sách string nội bộ (vì upstream dùng tiếng Anh).
- Nếu sau merge có chuỗi mới chưa dịch, chúng hiển thị tiếng Anh — đó là hành vi
  dự kiến (dịch sau), không phải regression.