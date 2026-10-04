"""Offline regressions: no requests to Anki or speech services."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


anki = load("anki", "anki-vocab/anki.py")
figs = load("figs", "paper-figures/check_figs.py")
xcount = load("xcount", "x-post-writing/count.py")


def note(nid, front):
    return {"noteId": nid, "fields": {"Front": {"value": front}, "Back": {"value": "back"}}}


class AnkiTests(unittest.TestCase):
    def test_tts_timeout_is_optional(self):
        with patch.object(anki.shutil, "which", return_value="edge-tts"), \
             patch.object(anki.subprocess, "run", side_effect=subprocess.TimeoutExpired("edge-tts", 60)), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertIsNone(anki.tts("hello", "us"))
        self.assertIn("warning", errors.getvalue())

    def test_media_content_does_not_overwrite_other_recordings(self):
        def fake_call(action, **params):
            self.assertEqual(action, "storeMediaFile")
            return params["filename"]

        with patch.object(anki, "call", side_effect=fake_call), \
             patch.object(anki, "word_audio", return_value=b"word"), \
             patch.object(anki, "tts", side_effect=[b"sentence A", b"sentence B"]):
            first = anki.front_field("test", "sentence A", "us")
            second = anki.front_field("test", "sentence B", "us")
        sounds = lambda text: anki.re.findall(r"\[sound:([^\]]+)\]", text)
        self.assertEqual(sounds(first)[0], sounds(second)[0])
        self.assertNotEqual(sounds(first)[1], sounds(second)[1])

    def test_store_uses_returned_filename(self):
        with patch.object(anki, "call", return_value="renamed.mp3"):
            self.assertEqual(anki.store("requested.mp3", b"audio"), " [sound:renamed.mp3]")

    def test_duplicate_headwords_are_rejected(self):
        with patch.object(anki, "call", side_effect=[[1, 2], [note(1, "Test<br>A"), note(2, "test<br>B")]]):
            with self.assertRaisesRegex(SystemExit, "Multiple notes"):
                anki.notes_by_word("Write")

    def test_other_note_models_are_skipped(self):
        with patch.object(anki, "call", side_effect=[[1], [{"fields": {"Text": {"value": "cloze"}}}]]):
            self.assertEqual(anki.notes_by_word("Write"), {})

    def test_delete_retains_shared_media(self):
        with patch.object(sys, "argv", ["anki.py", "delete", "test"]), \
             patch.object(anki, "notes_by_word", return_value={"test": note(1, "test [sound:shared.mp3]<br>A")}), \
             patch.object(anki, "call") as call, contextlib.redirect_stdout(io.StringIO()):
            anki.main()
        call.assert_called_once_with("deleteNotes", notes=[1])

    def test_refresh_preserves_case_html_and_entities(self):
        front = "<b>Test</b> [sound:old.mp3]<br/>A &amp; <i>B</i>. [sound:old-sentence.mp3]"
        with patch.object(anki, "audio_tags", return_value=(" [sound:new.mp3]", " [sound:new-sentence.mp3]")):
            self.assertEqual(anki.refresh_audio(front, "us"),
                             "<b>Test</b> [sound:new.mp3]<br/>A &amp; <i>B</i>. [sound:new-sentence.mp3]")

    def test_refresh_retains_audio_when_generation_fails(self):
        front = "Test [sound:old.mp3]<br>A [sound:old-sentence.mp3]"
        with patch.object(anki, "audio_tags", return_value=("", "")):
            self.assertEqual(anki.refresh_audio(front, "us"), front)

    def test_audio_no_audio_conflict_fails_before_connecting(self):
        with patch.object(sys, "argv", ["anki.py", "--no-audio", "audio"]), \
             patch.object(anki, "call") as call, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                anki.main()
        self.assertEqual(error.exception.code, 2)
        call.assert_not_called()

    def test_card_text_is_escaped(self):
        self.assertEqual(anki.fields("A&B", "x < y", ["a > b"], None),
                         {"Front": "A&amp;B<br>x &lt; y", "Back": "a &gt; b"})


class FigureTests(unittest.TestCase):
    def run_cli(self, args):
        with patch.object(sys, "argv", ["check_figs.py", *args]), \
             contextlib.redirect_stdout(io.StringIO()) as output, \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            figs.main()
        return error.exception.code, output.getvalue()

    def test_empty_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli([tmp])
        self.assertEqual(code, 1)
        self.assertIn("no PDF files", output)

    def test_bad_pdf_does_not_stop_remaining_checks(self):
        with patch.object(figs, "check", side_effect=[ValueError("broken PDF"), (5.5, 2, [])]) as check:
            code, output = self.run_cli(["bad.pdf", "good.pdf"])
        self.assertEqual(code, 1)
        self.assertEqual(check.call_count, 2)
        self.assertIn("1/2 figures pass", output)

    def test_invalid_width_is_rejected(self):
        for width in ("nan", "inf", "0", "-1"):
            self.assertEqual(self.run_cli(["figure.pdf", "--textwidth", width])[0], 2)

    def test_poppler_failure_is_reported(self):
        result = subprocess.CompletedProcess([], 1, "", "invalid PDF")
        with patch.object(figs.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, "invalid PDF"):
                figs.width_in(Path("bad.pdf"))

    def test_missing_poppler_is_reported(self):
        with patch.object(figs.subprocess, "run", side_effect=FileNotFoundError("pdfinfo")):
            with self.assertRaisesRegex(ValueError, "pdfinfo"):
                figs.width_in(Path("figure.pdf"))

    def test_multipage_pdf_is_rejected(self):
        with patch.object(figs, "poppler", return_value="Pages: 2\nPage size: 396 x 144 pts\n"):
            with self.assertRaisesRegex(ValueError, "single-page"):
                figs.width_in(Path("two-pages.pdf"))

    def test_house_font_and_width(self):
        with patch.object(figs, "width_in", return_value=(5.5, 2)), \
             patch.object(figs, "fonts", return_value=[("SourceSansPro-Regular", True)]):
            self.assertEqual(figs.check(Path("figure.pdf"), 5.5)[2], [])
        with patch.object(figs, "width_in", return_value=(6, 2)), \
             patch.object(figs, "fonts", return_value=[("Helvetica", False)]):
            problems = figs.check(Path("figure.pdf"), 5.5)[2]
        self.assertEqual(len(problems), 4)


if __name__ == "__main__":
    unittest.main()


class XCountTests(unittest.TestCase):
    def test_cjk_emoji_and_url_weights(self):
        # 4 CJK x2, thread emoji 2, ZWJ family 2, " Node.js " 9, URL 23, "." 1
        self.assertEqual(xcount.weight("中文测试🧵👨\u200d👩\u200d👧 Node.js https://example.com/a."), 45)

    def test_bare_domain_counts_as_url(self):
        self.assertEqual(xcount.weight("matduggan.com/what-does-my-dream-os-ui-look-like/"), 23)

    def test_split_on_numbered_lines(self):
        self.assertEqual([p.strip() for p in xcount.split_posts("1/\na\n\n2/\nb\n")], ["a", "b"])
        self.assertEqual(xcount.split_posts("one post"), ["one post"])

    def test_over_limit_exit_code(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("1/\n" + "a" * 281 + "\n2/\nshort\n")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(xcount.main([f.name]), 1)
        self.assertIn("OVER", out.getvalue())


epub = load("epub_build", "epub-making/build.py")
toc = load("epub_toc", "epub-making/check_toc.py")
cover = load("epub_cover", "epub-making/cover.py")
fetch = load("epub_fetch", "epub-making/fetch.py")
wenku8 = load("wenku8", "epub-making/sources/wenku8.py")


class EpubTests(unittest.TestCase):
    TXT = ("★轻小说文库(Www.WenKu8.com)★\r\n\r\n  第一卷 序  \r\n    正文一。\r\n    ***\r\n"
           "  第一卷 插图  \r\n        \r\n  第一卷 后记  \r\n    正文二。\r\n ◆◇◆◇ \r\n").encode("gb18030")

    def test_gb18030_split_drops_ads_and_keeps_scene_breaks(self):
        chapters = epub.split(epub.decode(self.TXT), "第一卷")
        self.assertEqual(chapters, [("序", ["正文一。", "***"]), ("插图", []), ("后记", ["正文二。"])])

    def test_other_prefix_and_utf8(self):
        text = epub.decode("  SSS短篇集 第一篇 特典\n    内容\n".encode())
        self.assertEqual(epub.split(text, "SSS短篇集"), [("第一篇 特典", ["内容"])])

    def test_empty_sections_dropped_or_filled_with_deduped_images(self):
        chapters = epub.split(epub.decode(self.TXT), "第一卷")
        _, kept, dropped = epub.render(chapters)
        self.assertEqual((kept, dropped), (["序", "后记"], ["插图"]))
        with tempfile.TemporaryDirectory() as d:
            for name, data in [("001.jpg", b"a"), ("002.jpg", b"a"), ("003.jpg", b"b"), ("notes.txt", b"x")]:
                Path(d, name).write_bytes(data)
            doc, kept, dropped = epub.render(chapters, d)
        self.assertEqual((kept, dropped), (["序", "插图", "后记"], []))
        self.assertEqual(doc.count("<img "), 2)

    def test_calibre_series_added_and_mimetype_stays_first_uncompressed(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "b.epub")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
                z.writestr("EPUB/content.opf", "<package><metadata></metadata></package>", zipfile.ZIP_DEFLATED)
            epub.add_calibre_series(path, "书&名", "7.5")
            with zipfile.ZipFile(path) as z:
                first = z.infolist()[0]
                opf = z.read("EPUB/content.opf").decode()
        self.assertEqual((first.filename, first.compress_type), ("mimetype", zipfile.ZIP_STORED))
        self.assertIn('name="calibre:series" content="书&amp;名"', opf)
        self.assertIn('content="7.5"', opf)

    def test_toc_compare(self):
        ref = ["序", "第一章", "插图", "后记"]
        self.assertEqual(toc.compare(ref, ["序", "第一章 ", "后记"], ["插图"]), ([], [], True))
        self.assertEqual(toc.compare(ref, ["第一章", "序", "多余"]), (["插图", "后记"], ["多余"], False))

    def test_cover_finds_front_left_of_spine(self):
        import numpy as np
        img = np.full((100, 300), 255, dtype=np.uint8)
        img[:, 40:110] = 60    # 封面
        img[:, 125:260] = 90   # 封底
        self.assertEqual(cover.find_front(img, ratio=0.7, side="left"), (40, 110))

    def test_wenku8_index_parse(self):
        page = ('<table><tr><td class=vcss colspan=4 vid=11>第一卷</td></tr><tr>'
                '<td class=ccss><a href=https://x/1.htm>序</a></td>'
                '<td class=ccss><a href=https://x/2.htm>插图</a></td><td class=ccss>&nbsp;</td></tr></table>')
        self.assertEqual(wenku8.parse(page),
                         [{"name": "第一卷", "vid": "11", "chapters": ["序", "插图"], "illus": "https://x/2.htm"}])

    def test_fetch_rejects_short_delay_and_skips_existing(self):
        with self.assertRaises(SystemExit):
            fetch.main(["--urls", "x", "-d", "y", "--delay", "1"])
        with tempfile.TemporaryDirectory() as d:
            Path(d, "001.jpg").write_bytes(b"old")
            with patch.object(fetch, "get", return_value=b"new") as get, \
                 contextlib.redirect_stdout(io.StringIO()):
                fetch.download_all(["https://a/1.jpg", "https://a/2.jpg?x=1"], d)
            self.assertEqual(get.call_count, 1)
            self.assertEqual(Path(d, "001.jpg").read_bytes(), b"old")
            self.assertEqual(Path(d, "002.jpg").read_bytes(), b"new")

    def test_book_id_is_stable_and_overridable(self):
        from types import SimpleNamespace
        a = SimpleNamespace(id=None, author="作者", title="书名1")
        self.assertEqual(epub.book_id(a), epub.book_id(SimpleNamespace(**vars(a))))
        self.assertTrue(epub.book_id(a).startswith("urn:uuid:"))
        self.assertNotEqual(epub.book_id(a), epub.book_id(SimpleNamespace(id=None, author="作者", title="书名2")))
        self.assertEqual(epub.book_id(SimpleNamespace(id="urn:isbn:1", author="", title="")), "urn:isbn:1")
