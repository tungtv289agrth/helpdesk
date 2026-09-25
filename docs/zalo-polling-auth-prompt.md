# Zalo Bot API

## 1. Webhook — Nhận mã từ user và xác thực

Bot nhận tin nhắn từ user → POST về endpoint này.

**Endpoint:** `POST https://<site>/api/method/helpdesk.api.zalo.webhook`

**Header:**
```
X-Bot-Api-Secret-Token: <secret>
```

**Body:**
```json
{
  "message": {
    "chat": { "id": "<chat_id>" },
    "from": { "display_name": "Tên user" },
    "text": "<mã 6 số>"
  }
}
```

**Response:**

| Code | Ý nghĩa |
|------|---------|
| `200` | Mã đúng → liên kết thành công. Body: `{"message":"Linked","email":"...","chat_id":"..."}` |
| `200` | Tin nhắn không phải mã 6 số → bỏ qua. Body: `{}` |
| `404` | Mã sai hoặc hết hạn. Body: `{"message":"Code not found"}` hoặc `{"message":"Code expired"}` |
| `401` | Sai secret. Body: `{"message":"Invalid secret token"}` |

**Ví dụ:**
```bash
curl -X POST https://helpdesk.example.com/api/method/helpdesk.api.zalo.webhook \
  -H "X-Bot-Api-Secret-Token: 123" \
  -H "Content-Type: application/json" \
  -d '{"message":{"chat":{"id":"abc123"},"from":{"display_name":"Tung"},"text":"123456"}}'
```

---

## 2. Check — Kiểm tra Zalo ID đã liên kết chưa

**Endpoint:** `GET https://<site>/api/method/helpdesk.api.zalo.check_zalo_id`

**Header:**
```
X-Bot-Api-Secret-Token: <secret>
```

**Query param:** `chat_id=<zalo_user_id>`

**Response:**

| Code | Ý nghĩa |
|------|---------|
| `200` | Tìm thấy. Body: `{"chat_id":"...","email":"...","contact":"...","ticket":"..."}` |
| `200` | Không tìm thấy. Body: `{"chat_id":"...","exists":false}` |
| `400` | Thiếu chat_id. Body: `{"message":"chat_id is required"}` |
| `401` | Sai secret. Body: `{"message":"Invalid secret token"}` |

**Ví dụ:**
```bash
curl "https://helpdesk.example.com/api/method/helpdesk.api.zalo.check_zalo_id?chat_id=abc123" \
  -H "X-Bot-Api-Secret-Token: 123"
```
