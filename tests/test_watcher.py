"""Run with: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHER = ROOT / "skill" / "scripts" / "watcher.py"
FAKE = Path(__file__).resolve().parent / "fake_claude_clip.py"


class Watcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.inbox, self.out = t / "inbox", t / "out"
        self.inbox.mkdir()
        self.cfg = t / "watcher.json"
        self.cfg.write_text(json.dumps({"watch": str(self.inbox), "out": str(self.out), "brand": str(ROOT / "examples" / "gaming-brand" / "brand.json"),
                                        "lang": "es", "stable_seconds": 0.5, "claude": str(FAKE), "rules": ["Extra rule for the test."]}),
                            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def clip(self, name, meta=None):
        path = self.inbox / name
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x36:d=1", "-pix_fmt", "yuv420p", str(path)], check=True)
        if meta is not None:
            Path(str(path) + ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return path

    def run_once(self, *extra, env=None):
        return subprocess.run([sys.executable, str(WATCHER), "--config", str(self.cfg), "--once", *extra],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env={**os.environ, **(env or {})})

    def test_own_clip_goes_to_review(self):
        self.clip("Game Clip 1.mp4")
        r = self.run_once()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (card,) = (self.out / "review").glob("*.md")
        cid = card.stem
        self.assertTrue((self.out / "edits" / f"{cid}.mp4").exists())
        self.assertTrue((self.out / "copy" / f"{cid}.md").exists())
        meta = json.loads((self.out / "raw" / f"{cid}.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["source"], meta["permission"]), ("own", True))
        self.assertIn("ready", card.read_text(encoding="utf-8"))
        self.assertIn(cid, (self.out / "log.md").read_text(encoding="utf-8"))
        prompt = (self.out / "work" / cid / "prompt.md").read_text(encoding="utf-8")
        self.assertIn("Extra rule for the test.", prompt)
        self.assertIn("Story spoilers", prompt)
        self.assertNotIn("$", prompt.replace("$skill", ""))
        # A second run does not edit it again.
        self.run_once()
        self.assertEqual(len(list((self.out / "review").glob("*.md"))), 1)

    def test_creator_without_permission_is_skipped(self):
        self.clip("theirs.mp4", {"fuente": "creador", "creador": "@someone", "permiso": False})
        self.run_once()
        self.assertEqual(list((self.out / "review").glob("*.md")), [])
        self.assertEqual(list((self.out / "raw").glob("*")), [])
        self.assertIn("NO-PERMISSION", (self.out / "log.md").read_text(encoding="utf-8"))

    def test_creator_with_permission_and_spoiler_flag(self):
        self.clip("theirs.mp4", {"source": "creator", "creator": "@someone", "permission": True})
        self.run_once(env={"FAKE_SPOILER": "1"})
        (card,) = (self.out / "review").glob("*.md")
        self.assertIn("`SPOILER`", card.read_text(encoding="utf-8"))
        self.assertIn("@someone", card.read_text(encoding="utf-8"))

    def test_dry_run_calls_nothing(self):
        self.clip("a.mp4")
        self.run_once("--dry-run")
        self.assertEqual(list((self.out / "edits").glob("*")), [])
        self.assertEqual(len(list((self.out / "work").glob("*/prompt.md"))), 1)


if __name__ == "__main__":
    unittest.main()
