# Feature: Ticket Details Tab — bỏ customer khỏi core fields + Autocomplete cho Select

Thay đổi từ commit `03e3d1c1f` (kết hợp phần `TicketDetailsTab.vue` của
`63afb5db2`).

## Ý định / logic

1. **Bỏ trùng customer field** (`03e3d1c1f`): `TicketDetailsTab.vue` có `coreFields`
   chứa field `customer` ở hàng lẻ, nhưng khách hàng đã được hiển thị sẵn qua
   component `TicketContact`. Field này bị xoá để tránh hiển thị trùng trên form.

2. **Select fields dùng Autocomplete** (`63afb5db2`): với field có
   `fieldtype === "Select"`, Tab Details dùng `Autocomplete` (từ frappe-ui) với
   `selectOptions` đã được dịch bởi `__(o)`; các field khác giữ `Link` như cũ.
   → giúp option Select hiển thị tiếng Việt trong form detail.

## File bị ảnh hưởng

- `desk/src/components/ticket-agent/TicketDetailsTab.vue`

## Quyết định conflict (resolving priority: giữ LOCAL)

- **Giữ bỏ field customer trong `coreFields`** — customer đã có `TicketContact`.
- **Giữ block `Autocomplete` cho Select** + `selectOptions` custom trong
  `getFieldInFormat` (field này upstream dùng `Link`). Khi upstream refactor
  `getFieldInFormat` hoặc template detail:
  - chèn lại nhánh `v-else-if="field.visible && field.fieldtype === 'Select'"`
    trong template;
  - giữ `selectOptions` (options split + `__(o)`) trong object field meta.
- Label/placeholder field phải giữ qua `__()` (xem i18n doc) — không quay về
  string thường.

## Sau merge

- Mở ticket agent: form details không hiện trùng customer; Select-type
  (vd ticket type, priority…) hiện option đã dịch và thao tác được.