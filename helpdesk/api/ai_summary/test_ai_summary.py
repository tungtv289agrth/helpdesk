"""Tests for the AI summary feature (helpdesk.api.ai_summary)."""

import io
import shutil
import unittest
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.api.ai_summary.ai_summary import (
    MAX_FILE_SIZE_MB,
    AppGuard,
    ai_summarize_files,
)
from helpdesk.api.ai_summary.converters import (
    ConversionError,
    convert_file,
)
from helpdesk.api.ai_summary.llm import LLMError, parse_llm_result
from helpdesk.api.ai_summary.text_compression import (
    PER_FILE_CHAR_LIMIT,
    compress_text,
)
from helpdesk.test_utils import make_file

OCR_AVAILABLE = shutil.which("tesseract") is not None


def make_txt_file(content: str, file_name: str = "test.txt"):
    """Create a File doc holding plain text content."""
    return make_file(file_name, content.encode("utf-8"), "TXT")


def make_csv_bytes() -> bytes:
    import pandas as pd

    df = pd.DataFrame(
        {
            "stt": [1, 2, 3],
            "item": ["May tinh", "Ban ghe", "Man hinh"],
            "gia": [15000000, 2500000, 3000000],
        }
    )
    return df.to_csv(index=False).encode("utf-8")


def make_pdf_bytes(text: str) -> bytes:
    import pymupdf as fitz

    buf = io.BytesIO()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class TestConvertFile(FrappeTestCase):
    def test_txt_conversion(self):
        text = "Hoa don dien tu so 123. Khach hang A thanh toan 5 trieu dong."
        self.assertIn("123", convert_file(text.encode(), "t.txt", "txt"))

    def test_csv_conversion(self):
        text = convert_file(make_csv_bytes(), "ds.csv", "csv")
        self.assertIn("May tinh", text)
        self.assertIn("stt", text)

    def test_xlsx_conversion(self):
        import pandas as pd

        buf = io.BytesIO()
        pd.DataFrame(
            {"item": ["Ban ghe"], "gia": [2500000]}
        ).to_excel(buf, index=False)
        text = convert_file(buf.getvalue(), "ds.xlsx", "xlsx")
        self.assertIn("Ban ghe", text)

    def test_pdf_conversion(self):
        text = convert_file(make_pdf_bytes("Invoice INV-99. Amount 9,500,000 VND."), "i.pdf", "pdf")
        self.assertIn("INV-99", text)

    def test_short_content_rejected(self):
        with self.assertRaises(ConversionError):
            convert_file(b"hello", "x.txt", "txt")

    def test_unsupported_type_rejected(self):
        with self.assertRaises(ConversionError):
            convert_file(b"music", "song.mp3", "mp3")

    @unittest.skipUnless(OCR_AVAILABLE, "tesseract not installed")
    def test_image_ocr(self):
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (1000, 200), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        except OSError:
            font = ImageFont.load_default()
        draw.text((30, 50), "INVOICE NUMBER INV-777 TOTAL 5.000.000", fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        text = convert_file(buf.getvalue(), "scan.png", "png")
        self.assertTrue(any(w in text for w in ["INVOICE", "INV", "777", "5.000.000"]))


class TestTextCompression(FrappeTestCase):
    def test_short_text_unchanged(self):
        text = "Text below the budget stays as is."
        self.assertEqual(compress_text(text, PER_FILE_CHAR_LIMIT), text)

    def test_long_text_is_compressed(self):
        text = "".join(
            f"Day la cau van thu {i} noi ve don hang cua khach hang ABC. " for i in range(200)
        )
        out = compress_text(text, PER_FILE_CHAR_LIMIT)
        self.assertLessEqual(len(out), PER_FILE_CHAR_LIMIT)
        self.assertTrue(out)

    def test_no_punctuation_falls_back_to_truncation(self):
        blob = "no punctuation here " * 5000
        out = compress_text(blob, PER_FILE_CHAR_LIMIT)
        self.assertLessEqual(len(out), PER_FILE_CHAR_LIMIT)


class TestParseLLMResult(FrappeTestCase):
    def test_ok_result(self):
        result = parse_llm_result(
            '{"title": "Hoa don tien dien", "summary": "Tong tien 5 trieu.", "reason": "ok"}'
        )
        self.assertEqual(result["title"], "Hoa don tien dien")
        self.assertEqual(result["reason"], "ok")

    def test_not_enough_information(self):
        result = parse_llm_result(
            '{"title": null, "summary": null, "reason": "not_enough_information"}'
        )
        self.assertIsNone(result["title"])
        self.assertEqual(result["reason"], "not_enough_information")

    def test_irrelevant_content(self):
        result = parse_llm_result(
            '{"title": null, "summary": null, "reason": "irrelevant_content"}'
        )
        self.assertEqual(result["reason"], "irrelevant_content")

    def test_fenced_json_is_accepted(self):
        result = parse_llm_result(
            '```json\n{"title": "Tieu de", "summary": "Mo ta", "reason": "ok"}\n```'
        )
        self.assertEqual(result["title"], "Tieu de")

    def test_garbage_raises(self):
        with self.assertRaises(LLMError):
            parse_llm_result("this is not json at all")


class TestAppGuard(FrappeTestCase):
    def setUp(self):
        self.original = frappe.conf.ai_summary_rate_limit_per_user
        frappe.conf.ai_summary_rate_limit_per_user = 2
        cache = frappe.cache()
        self.key = cache.make_key("ai_summary:summarize", user=True)
        cache.delete(self.key)

    def tearDown(self):
        frappe.conf.ai_summary_rate_limit_per_user = self.original
        frappe.cache().delete(self.key)

    def test_too_many_files(self):
        guard = AppGuard(["a", "b", "c", "d"])
        with self.assertRaises(Exception) as ctx:
            guard.check()
        self.assertEqual(ctx.exception.reason, "too_many_files")

    def test_rate_limit(self):
        guard = AppGuard(["a"])
        self.assertTrue(guard.check_rate_limit())
        self.assertTrue(guard.check_rate_limit())
        self.assertFalse(guard.check_rate_limit())

    def test_unsupported_file_type(self):
        file_doc = make_file("junk.mp3", b"not music", "MP3")
        guard = AppGuard([file_doc.name])
        with self.assertRaises(Exception) as ctx:
            guard.load_files()
        self.assertEqual(ctx.exception.reason, "unsupported_file_type")

    def test_oversized_file(self):
        file_doc = make_file("big.txt", b"x" * (MAX_FILE_SIZE_MB * 1024 * 1024 + 1), "TXT")
        guard = AppGuard([file_doc.name])
        with self.assertRaises(Exception) as ctx:
            guard.load_files()
        self.assertEqual(ctx.exception.reason, "file_too_large")


class TestEndpointPipeline(FrappeTestCase):
    def setUp(self):
        cache = frappe.cache()
        self.key = cache.make_key("ai_summary:summarize", user=True)
        cache.delete(self.key)

    def tearDown(self):
        frappe.cache().delete(self.key)

    def test_ok_flow_with_mocked_llm(self):
        file_doc = make_txt_file(
            "Hoa don tien dien so 123456. Khach hang tra 5,000,000 dong. Can phan hoi nhanh.",
            "hoa-don.txt",
        )
        expected = {
            "title": "Hoa don tien dien 123456",
            "summary": "Khach hang can phan hoi ve hoa don 5 trieu dong.",
            "reason": "ok",
        }
        with mock.patch(
            "helpdesk.api.ai_summary.ai_summary.summarize_text",
            return_value=expected,
        ) as mock_llm:
            response = ai_summarize_files([file_doc.name])

        self.assertTrue(response["success"])
        self.assertEqual(response["title"], expected["title"])
        self.assertEqual(response["summary"], expected["summary"])
        self.assertEqual(response["reason"], "ok")
        mock_llm.assert_called_once()

    def test_llm_not_enough_info(self):
        file_doc = make_txt_file(
            "Khach hang gui mot hoa don so 123. De nghi ho tro nhanh.", "not-enough.txt"
        )
        with mock.patch(
            "helpdesk.api.ai_summary.ai_summary.summarize_text",
            return_value={"title": None, "summary": None, "reason": "not_enough_information"},
        ):
            response = ai_summarize_files([file_doc.name])
        self.assertIsNone(response["title"])
        self.assertIsNone(response["summary"])
        self.assertEqual(response["reason"], "not_enough_information")

    def test_processing_failed_when_llm_raises(self):
        file_doc = make_txt_file("Valid content here. Some more text for a ticket.", "a.txt")
        with mock.patch(
            "helpdesk.api.ai_summary.ai_summary.summarize_text",
            side_effect=LLMError("boom"),
        ):
            response = ai_summarize_files([file_doc.name])
        self.assertFalse(response["success"])
        self.assertEqual(response["reason"], "processing_failed")

    def test_processing_failed_on_unreadable_file(self):
        file_doc = make_file("junk.mp3", b"\x00\x01\x02", "MP3")
        response = ai_summarize_files([file_doc.name])
        self.assertFalse(response["success"])
        self.assertEqual(response["reason"], "unsupported_file_type")

    def test_pdf_then_mock_llm(self):
        file_doc = make_file(
            "invoice.pdf",
            make_pdf_bytes("INVOICE INV-2026-001. Total 12,000,000 VND. Customer XYZ."),
            "PDF",
        )
        expected = {"title": "Invoice", "summary": "Total 12 trieu.", "reason": "ok"}
        with mock.patch(
            "helpdesk.api.ai_summary.ai_summary.summarize_text",
            return_value=expected,
        ):
            response = ai_summarize_files([file_doc.name])
        self.assertEqual(response["reason"], "ok")

    def test_multiple_files_combined(self):
        f1 = make_txt_file("Invoice one content. Amount 100.000 VND.", "a.txt")
        f2 = make_txt_file("Invoice two content. Amount 200.000 VND.", "b.txt")
        with mock.patch(
            "helpdesk.api.ai_summary.ai_summary.summarize_text",
            return_value={"title": "Hai hoa don", "summary": "Tong 300.000 VND.", "reason": "ok"},
        ) as mock_llm:
            response = ai_summarize_files([f1.name, f2.name])
        self.assertTrue(response["success"])
        self.assertEqual(mock_llm.call_count, 1)
