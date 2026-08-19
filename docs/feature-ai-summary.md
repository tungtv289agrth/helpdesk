# Feature: AI Summary — "Tải file lên" (auto-fill ticket title & description)

Thay đổi từ commit `c827d5c09`.

## Ý định / logic

Trên trang **New Ticket** có nút nổi **"Tải file lên"** (dưới cùng bên phải) cho
phép chọn file (invoice, screenshot, document…). Hệ thống đọc file, hỏi LLM
(Google Gemini) để sinh **tiêu đề + mô tả** ngắn, rồi **tự điền** vào các field
**Tiêu đề**, **Mô tả** và **Đính kèm** trên form. Là shortcut tùy chọn — flow
thủ công không đổi. **Không bao giờ ghi đè** nội dung người dùng đã tự nhập.

## Kiến trúc (synchronous, bounded → không dùng background job)

Pipeline `helpdesk/api/ai_summary/`:

1. **App Guard** (`ai_summary.py`):
   - Whitelist file type: `pdf, docx, xlsx, csv, txt/md, png, jpg/jpeg`.
   - Giới hạn: ≤ 15 MB/file, ≤ 3 file/call, rate limit per-user qua Redis
     (default 15 calls / 10 phút).
   - Vi phạm dừng ngay trước khi gọi LLM.
   - Response shape `{ success, title, summary, reason }` với `reason` ∈
     `ok | not_enough_information | irrelevant_content | limit_exceeded |
     processing_failed | rate_limited | too_many_files | file_too_large |
     unsupported_file_type`.
2. **Convert to text** (`converters.py`): PDF (PyMuPDF), DOCX (mammoth),
   XLSX/CSV (pandas, first 20 rows), TXT/MD trực tiếp; scan & ảnh qua Tesseract
   OCR (page đầu tiên, có timeout 10s/file). Mỗi conversion có hard timeout.
3. **Compress** (`text_compression.py`): text > 3.000 chars/file hoặc 10.000
   chars/call được rút gọn bằng `sumy` (TextRank) thay vì cắt cụt. Có
   `_SimpleTokenizer` fallback khi nltk punkt không có (hoạt động tốt với
   tiếng Việt).
4. **LLM** (`llm.py`): gửi **chỉ plain text** tới Gemini `generateContent`
   (timeout 10s, retry 429/5xx tối đa 3 lần với backoff); kết quả là title
   (≤80 chars) + description (≤400 chars) hoặc reason lý do không đủ thông tin.

**Cấu hình** — KHÔNG hardcode, đọc từ `sites/<site>/site_config.json`:
`ai_summary_llm_api_key`, `ai_summary_llm_model`, `ai_summary_max_files_per_call`,
`ai_summary_max_file_size_mb`, `ai_summary_rate_limit_per_user`,
`ai_summary_rate_limit_window_minutes`. **Không commit API key.**

## Frontend

- `desk/src/components/AiTicketUpload.vue` (mới): nút nổi + tooltip giới thiệu
  tiếng Việt, trạng thái working (Spinner + text), error banner, chọn file →
  gọi API, emit `@filled`.
- `desk/src/pages/ticket/TicketNew.vue`: nối `@filled="onAiFilled"` — điền title/
  summary/chỉ thêm files; **điều kiện: `!subject.value.trim()` và
  `isContentEmpty(description)`** mới điền → không ghi đè input user. Khi title
  được AI điền, hiện **Badge đỏ** "Nội dung này do AI tạo, vui lòng kiểm soát lại".
  Có helper `plainTextToHtml` (escape + chuyển `\n` sang `<p>`/`<br>`).

## Dependencies

- `pyproject.toml` thêm mục `# AI summary feature (helpdesk.api.ai_summary)` với
  7 deps **để COMMENT**: `pymupdf`, `mammoth`, `pandas>=2.2,<3`, `pytesseract`,
  `pdf2image`, `opencv-python-headless`, `sumy`.

  > Lưu ý user: deps thực chất đã được cài ở 1 custom project riêng; comment chỉ
  > để nhớ. **Khi merge giữ nguyên comment**, không active lại trong pyproject này.
- **OS-level packages** (không cài bằng pip; bắt buộc nếu dùng Scan/OCR):
  `tesseract-ocr`, `tesseract-ocr-vie`, `poppler-utils`.
- `helpdesk/test_utils.py`: helper `make_file(file_name, content, file_type)`
  tạo File doc private standalone trong bộ nhớ, dùng cho test AI pipeline.

## Quyết định conflict (resolving priority: giữ local)

- **Toàn bộ `helpdesk/api/ai_summary/*` là file mới** — giữ nguyên, không có
  conflict thực sự (trừ khi upstream vô tình tạo file trùng tên; nếu vậy rename).
- `desk/src/components/AiTicketUpload.vue` là file mới — giữ nguyên.
- `desk/src/pages/ticket/TicketNew.vue`: khi conflict (vd từ branch develop với
  feature mới), **giữ block `<AiTicketUpload @filled="onAiFilled" />`** + hàm
  `onAiFilled`/`plainTextToHtml` + `autoFilledSubject` ref + Badge. Lấy phần còn
  lại theo bản mới nhất rồi chèn lại các khối local.
- `pyproject.toml`: giữ block comment (không kích hoạt deps). Nếu upstream đổi
  section dependencies, chỉ bảo toàn block `# AI summary feature`.
- `helpdesk/test_utils.py`: giữ hàm `make_file`. Nếu upstream thêm hàm trùng tên,
  đổi tên (vd `make_ai_test_file`) để tránh xung đột.

## Tài liệu chi tiết

Phần setup hoàn chỉnh (deps, OS packages, config JSON mẫu) đã ghi trong
`README.md` — mục "AI Summary — Tải file lên". Khi merge README.md, ghép phần
này (phần local không có ở upstream).