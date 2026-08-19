# Feature: Sidebar — bỏ Apps/Help/Docs, thêm "Switch app" + link Zalo

Thay đổi từ commit `2efc266ee`.

## Ý định / logic

Helpdesk upstream hiển thị menu **Apps** (switch giữa các app Frappe Cloud),
**Help/onboarding**, **Docs**, **Login to Frappe Cloud** — không phù hợp hệ thống
nội bộ triển khai như 1 app đơn (single-app). Local:

1. **Bỏ** sidebar link "Help" + HelpModal (onboarding), bỏ `Apps.vue`,
   `AppsIcon.vue`, bỏ "Docs" link, bỏ "Login to Frappe Cloud".
2. **Thay** menu "Apps" bằng mục **"Switch app"** — trỏ về `/app` (desktop Frappe).
3. **Support menu** giờ mở link **Zalo**:
   `https://bot.zaloplatforms.com/bots/2741100038390236707`
   (thay vì `https://t.me/frappedesk`).
4. Mobile (`MobileSidebar.vue`): tương tự — thay `Apps` bằng "Switch app"
   (`/apps`) và bỏ "Docs".

## File bị ảnh hưởng

- `desk/src/components/Apps.vue` — **bị xoá**
- `desk/src/components/icons/AppsIcon.vue` — **bị xoá**
- `desk/src/components/layouts/Sidebar.vue`
- `desk/src/components/layouts/MobileSidebar.vue`
- `desk/src/components/UserMenu.vue`

## Quyết định conflict (resolving priority: GIỮ LOCAL)

> Câu trả lời của user: "Giữ local (Switch app + Zalo)".

- Đây là customization nội bộ — **luôn giữ local** khi conflict với upstream.
- Khi upstream refactor Sidebar (thêm/xoá menu), phải **tái áp dụng** 4 thay đổi
  local lên Sidebar mới của upstream:
  1. Bỏ HelpModal/Help link; bỏ onboarding `useShortcut({key:"h"})`.
  2. Bỏ imports Apps/AppsIcon/HelpIcon/HelpModal/FrappeCloudIcon/confirmLoginToFrappeCloud.
  3. Trong `agentPortalDropdown`:
     - thay `component: markRaw(Apps)` bằng `{ label: __("Switch app"),
       icon: "lucide-arrow-left-right", onClick: switchApp }`;
     - bỏ mục Docs + Login to Frappe Cloud;
     - đổi Support `onClick` sang link Zalo.
  4. Giữ `function switchApp() { window.location.href = "/app"; }`.
- **Lưu ý build**: desktop dùng `/app`, mobile dùng `/apps` — đừng đổi nhầm.
- Nếu upstream đổi tên component/cấu trúc dropdown, áp dụng theo cú pháp mới
  nhưng **giữ nguyên hành vi (chuyển quan `/app`, Zalo link)**.
- `desk/src/router/index.ts`: local xoá route `CustomerList` — giữ bỏ route này khi
  merge để tránh sidebar menu chết.

## Sau merge

- Build frontend và verify: agent portal dropdown có "Switch app", Support mở Zalo,
  không còn menu Apps/Help/Docs/Frappe Cloud.