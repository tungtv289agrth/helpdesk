# Feature: Zalo Bot Integration — tắt Email, gửi Zalo Bot 1 chiều

Thay thế toàn bộ luồng gửi mail bằng Zalo Bot (https://docs.zaloplatforms.com/docs/BOT) (1 chiều: agent → khách, qua `bot-api.zaloplatforms.com`).

## Ý định / logic

- **Tắt email toàn bộ**: `HD Settings.skip_email_workflow = 1` (mặc định), các toggle con `send_acknowledgement_email`, `enable_email_ticket_feedback`, `enable_reply_email_to_agent`, `enable_reply_email_via_agent` mặc định `0`. Các method `handle_email_feedback`, `send_acknowledgement_email`, `send_reply_email_to_agent`, `after_insert` đều guard bằng `skip_email_workflow()` để không gọi `frappe.sendmail` nữa (`helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py:119-189,873-932`).
- **Lịch sử giữ nguyên**: mỗi lần agent gửi Zalo tạo 1 `Communication` với `communication_medium="Zalo"`, `sent_or_received="Sent"` để hiển thị trong `TicketActivityPanel.vue`/`EmailArea.vue` giống như email trước đây. `get_communications` (`helpdesk/helpdesk/doctype/hd_ticket/api.py:174`) đã select thêm `communication_medium`.
- **Zalo Bot config**: thêm Tab `Zalo` vào `HD Settings` (`helpdesk/helpdesk/doctype/hd_settings/hd_settings.json:field_order`) với 5 field: `enable_zalo_integration` (Check), `zalo_bot_token` (Password, chính - Bot Token từ Zalo Bot Manager), `zalo_oa_id`/`zalo_access_token` (legacy OA, để trống khi dùng Bot), `zalo_secret_key` (Password, secret_token cho setWebhook, header `X-Bot-Api-Secret-Token`). `helpdesk/utils/zalo.py` ưu tiên `zalo_bot_token`.
- **Outbound API**: `helpdesk/utils/zalo.py:send_zalo_message` ưu tiên Bot API (`POST https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendMessage` body `{"chat_id":...,"text":...}`) theo https://docs.zaloplatforms.com/docs/BOT/apis/sendMessage; fallback OA `https://openapi.zalo.me/v3.0/oa/message/cs` nếu chưa có Bot Token. Text strip HTML, giới hạn 2000 chars, Bot trả về `{ok:true, result:{message_id}}`, OA trả về `{error:0}`.
- **DocType method**: `HDTicket.create_zalo_communication` + `reply_via_zalo` (`helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py`) kiểm tra `is_agent`, `enable_zalo_integration`, resolve `user_id` qua `get_zalo_user_id_for_ticket` (ưu tiên `Contact.zalo_user_id` → `mobile_no/phone` → `raised_by`).
- **API whitelisted**: `helpdesk/api/zalo.py` cung cấp `get_config` (trả `has_bot_token`), `send_message(ticket, message, chat_id?)` (tạo Communication rồi gọi `send_zalo_message(chat_id, message)`), `webhook` (verify `X-Bot-Api-Secret-Token` nếu cấu hình, log `request.get_json()`), `set_webhook(url, secret_token)` wrapper `POST /bot${BOT_TOKEN}/setWebhook`.
- **Frontend**:
  - `desk/src/components/ZaloEditor.vue` (mới, copy từ `EmailEditor.vue` nhưng bỏ `From/To/Cc/Bcc`, label `Gửi Zalo`, cache key `zaloBoxContent`, gọi `reply_via_zalo`).
  - `desk/src/components/CommunicationArea.vue:6-68` nút `Gửi Zalo` (LucideMessageCircle) thay cho `Reply Ticket` (EmailIcon), embed `ZaloEditor`.
  - `desk/src/components/EmailArea.vue:35-105` badge `Zalo` + ẩn `Reply All`/`Cc/Bcc` khi `communication_medium==="Zalo"`, hiện `Tới: <recipients> (qua Zalo)`.
  - `desk/src/components/ticket-agent/TicketActivityPanel.vue:79-138` tab `Emails` → `Zalo`, map `communication_medium` vào props.
  - `desk/src/pages/ticket/MobileTicketAgent.vue:486-532` tương tự cho mobile.
  - `desk/src/components/ticket/TicketAgentActivities.vue:155` empty text `Chưa có tin nhắn Zalo`.
- **Patch**: `helpdesk/patches/disable_email_enable_zalo.py` set các giá trị trên cho site cũ, khai trong `helpdesk/patches.txt:55`.
- **Contact/User ID**: `Contact` có custom field `zalo_user_id` (lấy từ webhook Bot `msg.chat.id`). Khi khách nhắn Bot lần đầu, webhook sẽ lưu `zalo_user_id` vào Contact. Nếu chưa có, `reply_via_zalo` vẫn lưu `Communication` nhưng không gửi được (cần khách nhắn trước).

## File bị ảnh hưởng

- `helpdesk/helpdesk/doctype/hd_settings/hd_settings.json` + provider `helpdesk/utils/zalo.py` + `helpdesk/helpdesk/utils/zalo.py` (copy)
- `helpdesk/api/zalo.py`, `helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py`, `helpdesk/helpdesk/doctype/hd_ticket/api.py`
- `desk/src/components/ZaloEditor.vue` (mới), `desk/src/components/CommunicationArea.vue`, `desk/src/components/EmailArea.vue`, `desk/src/components/ticket-agent/TicketActivityPanel.vue`, `desk/src/pages/ticket/MobileTicketAgent.vue`, `desk/src/components/ticket/TicketAgentActivities.vue`
- `helpdesk/patches/disable_email_enable_zalo.py`, `helpdesk/patches.txt`
- `docs/feature-zalo-integration.md` (tài liệu này), `docs/README.md`

## Quyết định conflict (resolving priority: GIỮ LOCAL)

- `helpdesk/helpdesk/doctype/hd_settings/hd_settings.json`: luôn giữ local các field `skip_email_workflow=1`, các toggle `0`, và Tab `Zalo`. Nếu upstream thêm field mới vào `field_order`, merge bằng cách **giữ cả hai**: append field mới của upstream + giữ các field Zalo ở cuối.
- `helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py`: local thêm `skip` guard vào 3 method email + thêm `create_zalo_communication/reply_via_zalo`. Khi upstream sửa `reply_via_agent`/`create_communication_via_contact`, **giữ nguyên phần Zalo** và re-apply guard `skip_email_workflow`. Không xoá `reply_via_agent` (vẫn tồn tại nhưng bị block bởi skip) để tránh gãy code cũ.
- `helpdesk/helpdesk/doctype/hd_ticket/api.py`: local thêm `communication_medium` vào select. Khi upstream đổi query, giữ thêm cột này.
- `desk/src/components/CommunicationArea.vue`, `EmailArea.vue`, `TicketActivityPanel.vue`, `MobileTicketAgent.vue`: luôn giữ bản local Zalo. Nếu upstream refactor editor/timeline, re-apply: đổi EmailEditor → ZaloEditor, tab label Zalo, badge Zalo.
- `helpdesk/api/zalo.py`, `helpdesk/utils/zalo.py`, `desk/src/components/ZaloEditor.vue`, `helpdesk/patches/disable_email_enable_zalo.py`: file mới của local — **giữ nguyên**, không xoá khi merge.
- Zalo API token là secret: không commit token thật, chỉ lưu trong `HD Settings` (Password field) trên site.

## Cấu hình sau cài (Zalo Bot)

1. `bench --site <site> migrate` (chạy patch `disable_email_enable_zalo`).
2. Tạo Bot: mở Zalo → tìm OA **Zalo Bot Manager** → Tạo bot (tên bắt đầu `Bot ...`) → nhận `Bot Token` qua tin nhắn. Xem https://docs.zaloplatforms.com/docs/BOT/create_bot.
3. Vào `Helpdesk Settings > Zalo` bật `Enable Zalo Integration`, nhập `Zalo Bot Token`. (Để trống OA ID/Access Token legacy).
4. (Tuỳ chọn webhook 2 chiều) `bench --site <site> execute` hoặc gọi `helpdesk.api.zalo.set_webhook` với `url=https://<site>/api/method/helpdesk.api.zalo.webhook` + `secret_token` (trùng `zalo_secret_key`). Zalo sẽ verify header `X-Bot-Api-Secret-Token`. Xem https://docs.zaloplatforms.com/docs/BOT/apis/setWebhook.
5. Đảm bảo `Contact` có `zalo_user_id` (lấy từ webhook `message.chat.id` hoặc `getUpdates`) để `get_zalo_user_id_for_ticket` resolve được. Lần đầu khách chat tới Bot, webhook sẽ thấy `chat_id` — lưu vào `Contact.zalo_user_id` để gửi lại được. Nếu chưa có user_id, `reply_via_zalo` vẫn lưu `Communication` nhưng không gửi được (cần khách nhắn trước).
6. `yarn build` trong `desk/` (`NODE_OPTIONS=--max-old-space-size=4096 yarn build`) đã verify build pass.
7. Test: mở ticket có `Contact` đã có `zalo_user_id` → bấm `Gửi Zalo` → nhập nội dung → Gửi → kiểm tra `Communication` có `medium=Zalo` và khách nhận tin trong chat Bot.

## Hạn chế / TODO 2 chiều

- Hiện chỉ 1 chiều outbound nếu chưa bật webhook; `helpdesk/api/zalo.py:webhook` hiện chỉ verify secret + log. Để làm 2 chiều: parse Bot update `{"message":{"chat":{"id":...},"text":...}}`, lookup `Contact` by `chat_id`, tạo `HD Ticket` nếu chưa có hoặc `Communication(Received, medium=Zalo)` + `ticket.save()` để reopen.
