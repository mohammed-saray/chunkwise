import tempfile
import unittest
from pathlib import Path

from chunkwise.core import collect, ignored, pack, render, split_text
from chunkwise.tokens import estimate


def make_code(n_funcs=60):
    return "\n".join(f"def func_{i}(x):\n    '''Docstring for function {i}.'''\n    return x * {i} + {i}\n"
                     for i in range(n_funcs))


class SplitTests(unittest.TestCase):
    def test_small_file_one_piece(self):
        pieces = split_text("a.py", "print(1)\n", 1000)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0].label, "a.py")

    def test_big_file_splits_on_boundaries(self):
        code = make_code()
        pieces = split_text("big.py", code, 300)
        self.assertGreater(len(pieces), 3)
        for pc in pieces:
            self.assertLessEqual(estimate(pc.text), 300)
        for pc in pieces[1:]:
            self.assertTrue(pc.text.startswith("def ") or pc.text.startswith("\n") or pc.text == "",
                            pc.text[:30])
        rebuilt = "\n".join(pc.text for pc in pieces)
        self.assertEqual(rebuilt, code)
        self.assertIn("(part 2/", pieces[1].label)

    def test_overlap(self):
        text = "\n".join(f"line {i} " + "x" * 50 for i in range(200))
        pieces = split_text("t.txt", text, 400, overlap=2)
        self.assertEqual(pieces[1].start, pieces[0].end - 1)

    def test_single_huge_line(self):
        pieces = split_text("one.txt", "x" * 50000, 500)
        self.assertEqual(len(pieces), 1)  # can't split inside a line; still returned


class CollectPackTests(unittest.TestCase):
    def test_collect_ignores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, "proj")
            (root / "src").mkdir(parents=True)
            (root / "node_modules" / "x").mkdir(parents=True)
            (root / "src" / "a.py").write_text("a = 1\n")
            (root / "src" / "b.log").write_text("noise\n")
            (root / "node_modules" / "x" / "i.js").write_text("x\n")
            (root / "img.png").write_bytes(b"\x89PNG\0\0")
            (root / "data.bin").write_bytes(b"\0\1\2")
            (root / ".gitignore").write_text("*.log\n# comment\n")
            files = [p for p, _ in collect([str(root)], [], [])]
            self.assertEqual(files, ["proj/.gitignore", "proj/src/a.py"])
            only = [p for p, _ in collect([str(root)], ["*.py"], [])]
            self.assertEqual(only, ["proj/src/a.py"])

    def test_ignored(self):
        self.assertTrue(ignored("a/node_modules/b.js", ["node_modules"]))
        self.assertTrue(ignored("docs/build/x", ["docs/build"]))
        self.assertFalse(ignored("src/app.py", ["*.log"]))

    def test_pack_and_render_protocol(self):
        files = [("a.py", make_code(40)), ("b.md", "# Title\n\nHello"), ("c.py", "x = 1")]
        chunks = pack(files, 800)
        self.assertGreater(len(chunks), 1)
        parts = render(chunks, "What does func_3 return?", "a codebase")
        n = len(parts)
        self.assertIn(f"I'm going to send you {n} parts of a codebase", parts[0])
        self.assertIn("Files included:\n- a.py", parts[0])
        self.assertIn(f"--- PART 2/{n} ---", parts[1])
        self.assertTrue(parts[-1].rstrip().endswith("What does func_3 return?"))
        self.assertIn(f"last part ({n}/{n})", parts[-1])
        for p in parts:
            self.assertLessEqual(estimate(p), 800 + 60)
        self.assertIn("```python", parts[0])

    def test_single_part_has_no_protocol(self):
        parts = render(pack([("a.py", "x = 1")], 8000), "Explain")
        self.assertEqual(len(parts), 1)
        self.assertNotIn("I'm going to send", parts[0])
        self.assertTrue(parts[0].endswith("Explain"))

    def test_cli_writes_parts(self):
        from chunkwise import cli
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "big.py")
            src.write_text(make_code(80), encoding="utf-8")
            out = Path(tmp, "out")
            self.assertEqual(cli.main([str(src), "-t", "700", "-o", str(out), "-q", "Summarize"]), 0)
            written = sorted(out.glob("part-*.md"))
            self.assertGreater(len(written), 1)
            self.assertEqual(written[0].name, "part-001.md")
            self.assertEqual(cli.main([str(src), "--plan"]), 0)


if __name__ == "__main__":
    unittest.main()
