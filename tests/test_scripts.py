"""Cross-platform checks of the editing scripts, without rendering. Run with: python -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skill" / "scripts"
BRAND = ROOT / "examples" / "gaming-brand" / "brand.json"


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


class Scripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        # 4 s of a still frame, then 4 s of motion and loud sound: the active stretch is the second half.
        cls.clip = cls.dir / "clip with spaces é.mp4"
        ffmpeg("-f", "lavfi", "-i", "color=c=0x101020:s=640x360:r=30:d=4",
               "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=4",
               "-f", "lavfi", "-i", "anoisesrc=a=0.005:d=4", "-f", "lavfi", "-i", "sine=f=220:d=4",
               "-filter_complex", "[0:v][2:a][1:v][3:a]concat=n=2:v=1:a=1[v][a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
               str(cls.clip))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_script(self, name, *args):
        done = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout

    def test_highlight_finds_the_action(self):
        words = self.dir / "words.json"
        words.write_text(json.dumps({"words": []}), encoding="utf-8")
        out = self.dir / "hl.json"
        self.run_script("highlight.py", self.clip, "--words", words, "--min", 2, "--max", 4, "--json", out)
        result = json.loads(out.read_text(encoding="utf-8"))
        best = result["windows"][0]
        self.assertGreaterEqual(best["start"], 3.5)
        self.assertFalse(result["speech"]["captionable"])

    def test_gaming_video_with_blur_fit_and_3d_scenes(self):
        video = self.dir / "videos" / "01-test"
        video.mkdir(parents=True)
        (video / "scenes").mkdir()
        (video / "scenes" / "mine.js").write_text("export default async () => (t) => {};\n", encoding="utf-8")
        cut = {"src": str(self.clip), "ranges": [[3.5, 8.0]], "fit": "blur", "size": "1080x1920"}
        spec = {"style": "gaming", "captions": False, "hook": {"lines": ["ÚLTIMO", "SEGUNDO"]},
                "scenes": [{"t": 0, "d": 1.5, "src": "neon-grid"}, {"t": 2, "d": 1, "src": "particles", "mode": "overlay"},
                           {"t": 3, "d": 1, "src": "scenes\\mine.js"}]}
        (video / "cut.json").write_text(json.dumps(cut), encoding="utf-8")
        (video / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        out = self.run_script("make_video.py", video, "--brand", BRAND)
        self.assertIn("3d scenes 3", out)

        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                "-of", "csv=p=0", str(video / "assets" / "clip.mp4")], capture_output=True, text=True)
        self.assertEqual(probe.stdout.strip(), "1080,1920")

        index = (video / "index.html").read_text(encoding="utf-8")
        self.assertIn('"three": "https://cdn.jsdelivr.net/npm/three@0.186.0/build/three.module.js"', index)
        for i in range(3):
            self.assertTrue((video / "compositions" / f"scene3d-{i}.html").exists())
        self.assertTrue((video / "assets" / "scenes" / "neon-grid.js").exists())
        mine = (video / "compositions" / "scene3d-2.html").read_text(encoding="utf-8")
        self.assertIn('import setup from "./scenes/mine.js"', mine)
        self.assertIn("ÚLTIMO", (video / "compositions" / "hook.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
