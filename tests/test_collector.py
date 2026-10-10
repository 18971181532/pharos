"""Tests for the file collector."""
import os
import unittest
from pharos.collector import detect_language, collect, iter_files, SKIP_DIRS
from tests.helpers import create_temp_project, cleanup_temp_project


class TestDetectLanguage(unittest.TestCase):
    def test_python(self):
        self.assertEqual(detect_language("main.py"), "python")

    def test_typescript(self):
        self.assertEqual(detect_language("app.tsx"), "typescript")

    def test_markdown(self):
        self.assertEqual(detect_language("README.md"), "markdown")

    def test_dockerfile(self):
        self.assertEqual(detect_language("Dockerfile"), "docker")

    def test_unknown_binary(self):
        self.assertIsNone(detect_language("image.png"))
        self.assertIsNone(detect_language("archive.zip"))


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.root = create_temp_project({
            "main.py": "import os\n",
            "lib/util.js": "function f() {}\n",
            "docs/readme.md": "# Hello\n",
            "image.png": "binary",
            "__pycache__/mod.cpython.pyc": "cache",
            "node_modules/pkg/index.js": "var x = 1;\n",
            ".git/config": "[core]\n",
        })

    def tearDown(self):
        cleanup_temp_project(self.root)

    def test_collects_text_files(self):
        docs = list(collect(self.root))
        paths = [d.path for d in docs]
        self.assertIn("main.py", paths)
        self.assertIn("lib/util.js", paths)
        self.assertIn("docs/readme.md", paths)

    def test_skips_binary(self):
        docs = list(collect(self.root))
        paths = [d.path for d in docs]
        self.assertNotIn("image.png", paths)

    def test_skips_dependency_dirs(self):
        docs = list(collect(self.root))
        paths = [d.path for d in docs]
        self.assertNotIn("node_modules/pkg/index.js", paths)
        self.assertNotIn("__pycache__/mod.cpython.pyc", paths)
        self.assertFalse(any(".git" in p.split("/") for p in paths))

    def test_language_detected(self):
        docs = list(collect(self.root))
        by_path = {d.path: d for d in docs}
        self.assertEqual(by_path["main.py"].language, "python")
        self.assertEqual(by_path["lib/util.js"].language, "javascript")

    def test_content_read(self):
        docs = list(collect(self.root))
        main = next(d for d in docs if d.path == "main.py")
        self.assertIn("import os", main.content)

    def test_size_and_mtime(self):
        docs = list(collect(self.root))
        main = next(d for d in docs if d.path == "main.py")
        self.assertGreater(main.size, 0)
        self.assertGreater(main.mtime, 0)

    def test_exclude_patterns(self):
        docs = list(collect(self.root, exclude_patterns=["docs/"]))
        paths = [d.path for d in docs]
        self.assertNotIn("docs/readme.md", paths)

    def test_single_file(self):
        single = os.path.join(self.root, "main.py")
        docs = list(collect(single))
        self.assertEqual(len(docs), 1)


if __name__ == "__main__":
    unittest.main()
