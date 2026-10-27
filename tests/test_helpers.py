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


report = load("pr_report", "pr-review/report.py")

DIFF = """diff --git a/app.py b/app.py
index 1..2 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
 keep
-old <b>
+new
 tail
diff --git a/docs/a.md b/docs/b.md
similarity index 90%
rename from docs/a.md
rename to docs/b.md
--- a/docs/a.md
+++ b/docs/b.md
@@ -10,0 +11,2 @@
+one
+two
\\ No newline at end of file
"""


class ReportTests(unittest.TestCase):
    def render(self, **data):
        return report.render({"title": "t", **data}, ROOT)

    def test_attention_lists_blocking_items_first(self):
        page = self.render(findings=[
            {"label": "Nit", "text": "nit-open", "resolution": "open: optional"},
            {"label": "Important", "text": "imp-fixed", "resolution": "fixed abc123"},
            {"label": "Important", "text": "imp-open", "where": "a.py:3"},
            {"label": "Pre-existing", "text": "pre-open"},
        ], tests=[{"command": "pytest", "status": "fail"}])
        self.assertIn("需要处理 2 项", page)
        verdict = page[page.index("verdict"):page.index("</section>")]
        self.assertLess(verdict.index("imp-open"), verdict.index("pytest"))
        self.assertLess(verdict.index("pytest"), verdict.index("nit-open"))
        self.assertNotIn("imp-fixed", verdict)

    def test_clean_report_says_so(self):
        page = self.render(tests=[{"command": "pytest", "status": "pass"}], reviewers=[{"name": "c", "status": "done"}])
        self.assertIn("可以合并", page)
        self.assertIn("无未解决问题。", page)
        self.assertIn("没有审查意见", page)

    def test_open_nit_does_not_block(self):
        page = self.render(tests=[{"command": "pytest", "status": "pass"}],
                           findings=[{"label": "Nit", "text": "x", "resolution": "open"}])
        self.assertIn("可以合并", page)
        self.assertIn("另有 1 条可选意见", page)

    def test_unverified_items_warn(self):
        page = self.render(tests=[{"command": "pytest -m gpu", "status": "not run", "reason": "no GPU"}],
                           reviewers=[{"status": "running"}])
        self.assertIn("合并前请确认 2 项", page)
        self.assertIn("未命名审查者", page)
        self.assertIn("没有测试记录", self.render())

    def test_unknown_status_and_labels_cannot_hide_problems(self):
        page = self.render(tests=[{"command": "pytest", "status": "error"}],
                           findings=[{"label": "important", "text": "x"}, {"text": "y"}, {"label": "nit", "text": "z", "resolution": "fixed"}])
        self.assertIn("需要处理 3 项", page)
        self.assertIn("Important 2 · Nit 1 · Pre-existing 0", page)
        self.assertIn('class="sev bad">error', page)

    def test_null_lists_and_status_case(self):
        page = self.render(findings=None, tests=[{"command": "a", "status": "Pass"}, {"command": "b"}],
                           reviewers=[{"name": "GLM", "status": "Done"}])
        self.assertIn("通过 1", page)
        self.assertIn("无状态 1", page)
        self.assertNotIn("审查未完成", page)
        self.assertNotIn("None", page)

    def test_text_is_escaped(self):
        page = self.render(title="<b>t</b>", findings=[{"label": "Nit", "text": "<script>alert(1)</script>"}],
                           guide=[{"title": "<i>g</i>", "why": "<u>w</u>", "files": ["<x>.py"]}],
                           structure={"columns": [{"title": "<c>", "nodes": [{"id": "a", "label": "<n>"}]}]})
        for raw in ("<script>alert", "<i>g", "<u>w", "<x>.py", "<c>", "<n>"):
            self.assertNotIn(raw, page)
        self.assertIn("<title>&lt;b&gt;t&lt;/b&gt;</title>", page)

    def test_diff_is_parsed_with_counts_and_line_numbers(self):
        app, doc = report.parse_diff(DIFF)
        self.assertEqual((app["path"], app["add"], app["del"]), ("app.py", 1, 1))
        self.assertIn(("d", 2, "", "old <b>"), app["rows"])
        self.assertIn(("a", "", 2, "new"), app["rows"])
        self.assertIn(("c", 3, 3, "tail"), app["rows"])
        self.assertEqual((doc["path"], doc["add"], doc["del"]), ("docs/b.md", 2, 0))
        self.assertEqual(doc["rows"][-1][0], "h")

    def test_guide_keeps_order_and_collects_other_files(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "diff.patch").write_text(DIFF)
            page = report.render({"title": "t", "diff": "diff.patch",
                                  "guide": [{"title": "Docs first", "why": "why", "files": ["docs/b.md"]}],
                                  "findings": [{"label": "Nit", "where": "app.py:2", "text": "x"}]}, Path(d))
        self.assertIn("01 / 02", page)
        self.assertLess(page.index("Docs first"), page.index("其他改动"))
        self.assertIn('id="f0"', page)
        self.assertIn('<a href="#f0"><code>app.py:2</code></a>', page)
        self.assertIn("2 个文件", page)
        self.assertIn("old &lt;b&gt;", page)

    def test_diagram_draws_nodes_and_known_edges(self):
        svg = report.diagram({"columns": [
            {"title": "入口", "nodes": [{"id": "a", "label": "SKILL.md", "status": "new"}]},
            {"title": "核心", "nodes": [{"id": "b", "label": "report.py", "status": "modified"},
                                        {"id": "c", "label": "x", "status": "weird"}]}],
            "edges": [{"from": "a", "to": "b", "label": "调用"}, {"from": "b", "to": "c"}, {"from": "a", "to": "missing"}]})
        self.assertEqual(svg.count('class="e"'), 2)
        self.assertIn('class="n new"', svg)
        self.assertIn('class="n unchanged"', svg)
        self.assertIn(">调用<", svg)
        self.assertEqual(report.diagram({}), "")

    def test_clip_counts_wide_characters(self):
        self.assertEqual(report.clip("abcdef", 4), "abcd…")
        self.assertEqual(report.clip("中文标签", 4), "中文…")
        self.assertEqual(report.clip("short", 30), "short")

    def test_screens_are_embedded(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.png").write_bytes(b"\x89PNG before")
            Path(d, "b.png").write_bytes(b"\x89PNG after")
            source = Path(d, "report.json")
            source.write_text('{"title": "t", "screens": [{"name": "home", "before": "a.png", "after": "b.png"}]}')
            with contextlib.redirect_stdout(io.StringIO()):
                report.main(["report.py", str(source)])
            page = Path(d, "report.html").read_text()
        self.assertEqual(page.count("data:image/png;base64,"), 2)

    def test_missing_screenshot_stops(self):
        with self.assertRaisesRegex(SystemExit, "screenshot not found"):
            self.render(screens=[{"name": "home", "before": "missing.png", "after": "missing.png"}])
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.png").write_bytes(b"\x89PNG")
            with self.assertRaisesRegex(SystemExit, "no path given"):
                report.render({"title": "t", "screens": [{"name": "home", "before": "a.png"}]}, Path(d))

    def test_numbers_compare_by_value(self):
        self.assertTrue(report.same(1, "1.0"))
        self.assertTrue(report.same("1e3", 1000))
        self.assertTrue(report.same("nan", float("nan")))
        self.assertTrue(report.same("snan", "snan"))
        self.assertFalse(report.same("snan", 1))
        self.assertFalse(report.same(2**53, 2**53 + 1))
        self.assertFalse(report.same(True, 1))
        self.assertFalse(report.same(None, None))

    def test_only_http_pr_links(self):
        self.assertNotIn("javascript:", self.render(pr={"number": 1, "url": "javascript:alert(1)"}))
        self.assertIn('href="https://github.com/a/b/pull/1"', self.render(pr={"number": 1, "url": "https://github.com/a/b/pull/1"}))

    def test_small_diffs_open_and_legend_lists_used_kinds(self):
        with tempfile.TemporaryDirectory() as d:
            big = "diff --git a/big.py b/big.py\n@@ -0,0 +1,61 @@\n" + "+x\n" * 61
            Path(d, "diff.patch").write_text(DIFF + big)
            page = report.render({"title": "t", "diff": "diff.patch", "structure": {"columns": [
                {"title": "c", "nodes": [{"id": "a", "label": "a", "status": "new"}]}]}}, Path(d))
        self.assertIn('id="f0" open', page)
        self.assertIn('id="f2">', page)
        legend = page[page.index('class="legend"'):]
        self.assertIn("新增", legend[:200])
        self.assertNotIn("外部", legend[:200])

    def test_diff_edge_cases(self):
        odd = "\n".join([
            "diff --git a/foo b/x.txt b/foo b/x.txt", "--- a/foo b/x.txt\t", "+++ b/foo b/x.txt\t",
            "@@ -1,2 +1,2 @@", "-one", "+tw\fo", " three",
            'diff --git "a/\\344\\270\\255.txt" "b/\\344\\270\\255.txt"', "new file mode 100644",
            '--- /dev/null', '+++ "b/\\344\\270\\255.txt"', "@@ -0,0 +1 @@", "+hi",
            "diff --git a/img.png b/img.png", "index 1..2 100644", "Binary files a/img.png and b/img.png differ",
            "diff --git a/run.sh b/run.sh", "old mode 100644", "new mode 100755",
            "diff --git a/link b/link", "deleted file mode 100644", "--- a/link", "+++ /dev/null", "@@ -1 +0,0 @@", "-t",
            "diff --git a/link b/link", "new file mode 120000", "--- /dev/null", "+++ b/link", "@@ -0,0 +1 @@", "+t", ""])
        files = report.parse_diff(odd)
        self.assertEqual([f["path"] for f in files], ["foo b/x.txt", "中.txt", "img.png", "run.sh", "link", "link"])
        self.assertIn(("c", 2, 2, "three"), files[0]["rows"])
        self.assertIn(("a", "", 1, "tw\fo"), files[0]["rows"])
        self.assertEqual(files[2]["notes"], ["二进制文件"])
        self.assertEqual(files[3]["notes"], ["原权限 100644", "新权限 100755"])
        with tempfile.TemporaryDirectory() as d:
            Path(d, "diff.patch").write_bytes(odd.encode() + b"diff --git a/l1.txt b/l1.txt\n@@ -0,0 +1 @@\n+caf\xe9\n")
            page = report.render({"title": "t", "diff": "diff.patch", "guide": [
                {"title": "A", "files": ["link", "run.sh"]}, {"title": "B", "files": ["link"]}]}, Path(d))
        self.assertIn("6 个文件", page)
        self.assertIn("caf�", page)
        self.assertIn("新权限 100755", page)
        self.assertEqual(page.count('id="f4"'), 1)
        self.assertEqual(page.count('id="f5"'), 1)

    def test_node_status_is_case_insensitive(self):
        svg = report.diagram({"columns": [{"title": "c", "nodes": [{"id": "a", "label": "a", "status": "New"}]}]})
        self.assertIn('class="n new"', svg)
