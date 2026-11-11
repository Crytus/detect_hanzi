"""detect_hanzi.py のテスト。"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import detect_hanzi as dh  # noqa: E402


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.d = dh.Detector()

    def test_simplified_detected(self):
        # 日本の文字コードにない簡体字
        for ch in "们说这钱马乡对时门东车么":
            self.assertTrue(self.d.is_chinese(ch), ch)

    def test_japanese_not_detected(self):
        # 通常の日本語（漢字・かな・記号・英数字・異体字の々）
        for ch in "日本語国学万髙﨑々あア。、ABC1 　":
            self.assertFalse(self.d.is_chinese(ch), ch)

    def test_extra_chars(self):
        # 「个」はJISにあるが追加リストで検出される
        for ch in "个气":
            self.assertTrue(self.d.is_chinese(ch), ch)
            self.assertFalse(dh.Detector(extra_chars="").is_chinese(ch), ch)

    def test_allow_chars(self):
        self.assertFalse(dh.Detector(allow_chars="们").is_chinese("们"))

    def test_level_jis2004(self):
        # JIS X 0213 には「么」があるため jis2004 では検出しない
        d = dh.Detector(level="jis2004")
        self.assertFalse(d.is_chinese("么"))
        self.assertTrue(d.is_chinese("们"))

    def test_scan_positions(self):
        text = "これは日本語です。\n我们这样说。"
        hits = list(self.d.scan_text(text, "t"))
        self.assertEqual([(h.line, h.column, h.char) for h in hits],
                         [(2, 2, "们"), (2, 3, "这"), (2, 4, "样"), (2, 5, "说")])


class TestFileIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dh.main(list(args))
        return code, buf.getvalue()

    def test_read_encodings(self):
        text = "日本語のテキスト"
        for enc in ("utf-8", "utf-8-sig", "cp932", "utf-16"):
            p = self.dir / f"{enc}.txt"
            p.write_bytes(text.encode(enc))
            self.assertEqual(dh.read_text(p), text, enc)

    def test_main_detects(self):
        (self.dir / "a.txt").write_text("今日は良い天气です。\n这个问题", encoding="utf-8")
        code, out = self.run_main(str(self.dir))
        self.assertEqual(code, 1)
        self.assertIn("'气' (U+6C14)", out)
        self.assertIn("a.txt:2:1", out)
        self.assertIn("検出数: 5文字", out)  # 气・这・个・问・题

    def test_main_clean(self):
        (self.dir / "b.txt").write_text("問題ありません。", encoding="cp932")
        code, out = self.run_main(str(self.dir))
        self.assertEqual(code, 0)
        self.assertIn("検出数: 0文字", out)

    def test_extension_filter(self):
        (self.dir / "c.bin").write_text("们", encoding="utf-8")
        code, _ = self.run_main(str(self.dir))
        self.assertEqual(code, 0)
        code, _ = self.run_main(str(self.dir), "--ext", "")
        self.assertEqual(code, 1)

    def test_context(self):
        (self.dir / "d.txt").write_text("この説明は简单です", encoding="utf-8")
        _, out = self.run_main(str(self.dir), "-c")
        self.assertIn("【简】", out)


if __name__ == "__main__":
    unittest.main()
