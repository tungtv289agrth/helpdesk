# Feature: Branding — dùng favicon.ico làm logo & site favicon

Thay đổi từ commit `8779ed2e7`.

## Ý định / logic

Hiển thị **favicon.ico** (file mới `desk/public/favicon.ico`) làm logo thương
hiệu và favicon của trang, thay vì logo SVG mặc định của upstream. Phù hợp việc
dùng chung 1 asset trên các vị trí:

1. `desk/index.html`: favicon `type="image/x-icon"` → `/assets/helpdesk/desk/favicon.ico`
   (trước: `/assets/helpdesk/desk/manifest/apple-icon-180.png`), title dùng `{{ _("Helpdesk") }}`.
2. `helpdesk/api/config.py`: fallback favicon → `/assets/helpdesk/desk/favicon.ico`
   (trước `/assets/helpdesk/desk/favicon.svg`).
3. `helpdesk/hooks.py` `add_to_apps_screen`: logo → `/assets/helpdesk/desk/favicon.ico`.
4. `desk/src/components/BrandLogo.vue`: khi config không có brand_logo, fallback
   hiện `<img src="/assets/helpdesk/desk/favicon.ico">` (trước: `<HDLogo/>`).

## File bị ảnh hưởng

- `desk/public/favicon.ico` (file binary mới)
- `desk/index.html`
- `helpdesk/api/config.py`
- `helpdesk/hooks.py`
- `desk/src/components/BrandLogo.vue`

## Quyết định conflict (resolving priority: giữ LOCAL branding)

- **Giữ local favicon.ico làm logo/favicon** — đây là nhận diện nội bộ. Nếu
  upstream đổi asset path hoặc thêm logo mới, vẫn giữ `/assets/helpdesk/desk/favicon.ico`
  cho 3 vị trí config + BrandLogo fallback.
- `BrandLogo.vue`: giữ `<img>` fallback; chỉ bỏ nếu upstream cung cấp cơ chế
  brand logo tốt hơn (và khi đó đặt/favicon.ico làm brand_logo của site).
- File binary `favicon.ico` luôn giữ — không có conflict text.
- `desk/index.html`: giữ `{{ _("Helpdesk") }}` title + link favicon local.

## Sau merge

- **Xây lại frontend để copy `favicon.ico` vào static assets** (`bench build` hoặc
  `yarn build` trong `desk/`) — file trong `desk/public` cần rebuild mới xuất hiện
  ở `/assets/helpdesk/desk/`.

  > Lưu ý: nếu chỉ merge code mà không rebuild, browser vẫn dùng favicon cũ
  > (404 cho đường dẫn mới). Build là bắt buộc sau mỗi merge.