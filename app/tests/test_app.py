"""Run with: python3 -m unittest discover app/tests"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
PORT = 4477
BASE = f"http://127.0.0.1:{PORT}"


def call(path, data=None, method=None, headers=None, raw=None):
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(BASE + path, body, method=method or ("POST" if body is not None else "GET"),
                                 headers={"X-Studio": "1", **(headers or {})})
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())


def status(path, **kwargs):
    try:
        call(path, **kwargs)
        return 200
    except urllib.error.HTTPError as error:
        return error.code


class App(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.video = Path(cls.temp.name) / "clip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1", "-pix_fmt", "yuv420p", str(cls.video)], check=True)
        cls.env = {**os.environ, "BVS_HOME": cls.temp.name, "BVS_CLAUDE": str(APP / "tests" / "fake_claude.py")}
        cls.env.pop("FAKE_CLAUDE", None)
        cls.start("ok")

    @classmethod
    def start(cls, mode):
        cls.server = subprocess.Popen([sys.executable, str(APP / "server.py"), "--port", str(PORT), "--no-open"],
                                      env={**cls.env, "FAKE_CLAUDE": mode}, stdout=subprocess.DEVNULL)
        for _ in range(50):
            try:
                call("/api/brands")
                return
            except OSError:
                time.sleep(0.1)

    @classmethod
    def stop(cls):
        cls.server.terminate()
        cls.server.wait()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.temp.cleanup()

    def brand(self):
        colors = {r: "#123456" for r in ("ink", "ink_dark", "bg", "light", "accent", "highlight")}
        return call("/api/brands", {"name": "Acme Café", "colors": colors, "notes": "Warm"})

    def project(self, name):
        brand = self.brand()
        p = call("/api/projects", {"name": name, "brand": brand["id"], "request": "Make reels"})
        call(f'/api/projects/{p["id"]}/footage/clip.mp4', raw=self.video.read_bytes(), method="PUT")
        return p["id"]

    def wait(self, pid, stages, seconds=20):
        end = time.time() + seconds
        while time.time() < end:
            p = call(f"/api/projects/{pid}")
            if p["stage"] in stages:
                return p
            time.sleep(0.1)
        self.fail(f'stage is still {p["stage"]}')

    def test_brand_problems_catch_missing_fonts_and_colors(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import studio
        d = Path(tempfile.mkdtemp())
        good = {"colors": dict(studio.STARTER), "fonts": {"display": {"file": "Shrikhand-Regular.ttf"}, "body": {"file": "Fredoka.ttf"}}}
        self.assertEqual(studio.brand_problems(d, good), [])
        bad = {"colors": {"ink": "red"}, "fonts": {"display": {"file": "assets/Nope.ttf"}}, "logo": "assets/logo.png"}
        self.assertEqual(studio.brand_problems(d, bad), ["colors", "display font", "body font", "logo"])

    def test_build_prompt_carries_the_users_answers(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import prompts
        project = {"name": "x", "request": "y", "brief": {}, "answers": "Crop the wide clip"}
        self.assertIn("Crop the wide clip", prompts.build(["01-a"], project))
        self.assertNotIn("answered the questions", prompts.build(["01-a"], {"name": "x", "request": "y", "brief": {}}))

    def test_full_flow(self):
        pid = self.project("Full flow")
        call(f"/api/projects/{pid}/propose", {})
        p = self.wait(pid, ["proposal"])
        self.assertEqual(len(p["proposal"]["videos"]), 3)
        call(f"/api/projects/{pid}/build", {"names": ["01-first", "03-third"], "first_only": True})
        p = self.wait(pid, ["first"])
        self.assertEqual([v["name"] for v in p["videos"]], ["01-first"])
        call(f"/api/projects/{pid}/rest", {})
        p = self.wait(pid, ["done"])
        self.assertEqual([v["name"] for v in p["videos"]], ["01-first", "03-third"])
        self.assertIn("A caption", p["copy"])
        self.assertGreater(p["tokens"], 0)
        req = urllib.request.Request(f"{BASE}/files/project/{pid}/renders/01-first.mp4", headers={"Range": "bytes=0-9"})
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 206)
            self.assertEqual(len(res.read()), 10)

    def test_activity_is_recorded(self):
        pid = self.project("Activity")
        call(f"/api/projects/{pid}/propose", {})
        self.wait(pid, ["proposal"])
        text = [a["text"] for a in call(f"/api/projects/{pid}?after=0")["activity"]]
        self.assertIn("Survey the videos", text)

    def test_refuses_unsafe_requests(self):
        pid = self.project("Safety")
        self.assertEqual(status(f"/api/projects/{pid}/propose", data={}, headers={"X-Studio": "0"}), 403)
        self.assertEqual(status("/api/brands", headers={"Host": "evil.example"}), 403)
        self.assertEqual(status("/api/projects/..%2f..%2fetc"), 400)
        self.assertEqual(status(f"/files/project/{pid}/renders/..%2fproject.json"), 404)
        self.assertEqual(status(f"/api/projects/{pid}/footage/notes.txt", raw=b"x", method="PUT"), 400)
        self.assertEqual(status(f"/api/projects/{pid}/build", data={"names": ["nope"]}), 400)

    def test_needs_footage_before_proposal(self):
        brand = self.brand()
        p = call("/api/projects", {"name": "Empty", "brand": brand["id"], "request": "x"})
        self.assertEqual(status(f'/api/projects/{p["id"]}/propose', data={}), 400)

    def test_folder_links_videos_and_keeps_the_brief(self):
        folder = Path(self.temp.name) / "shoot"
        folder.mkdir()
        (folder / "a.mp4").write_bytes(self.video.read_bytes())
        (folder / "notes.txt").write_text("skip")
        self.assertEqual(call("/api/folder", {"path": str(folder)})["count"], 1)
        brand = self.brand()
        brief = {"style": "scrapbook", "motion": "heavy", "energy": 3, "formats": ["1:1", "9:16"],
                 "captions": {"on": True, "type": "box", "upper": True}, "platforms": ["TikTok"]}
        p = call("/api/projects", {"name": "Linked", "brand": brand["id"], "request": "Reels", "folder": str(folder), "brief": brief})
        pid = p["id"]
        self.assertEqual(p["format"], "1:1")
        link = Path(self.temp.name) / "projects" / pid / "footage" / "a.mp4"
        self.assertTrue(link.is_symlink())
        self.assertEqual(call(f"/api/projects/{pid}")["footage"], ["a.mp4"])
        sys.path.insert(0, str(APP))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import prompts
        text = prompts.propose({"request": "x", "brief": brief})
        for part in ("scrapbook", "every 4 seconds", "Energetic", '"mode": "box"', '"case": "upper"', "Extra formats: 9:16", "TikTok"):
            self.assertIn(part, text)
        remembered = [b for b in call("/api/brands") if b["id"] == brand["id"]][0]
        self.assertEqual(remembered["app"]["style"], "scrapbook")

    def test_empty_folder_is_refused(self):
        folder = Path(self.temp.name) / "empty"
        folder.mkdir()
        brand = self.brand()
        self.assertEqual(status("/api/projects", data={"name": "None", "brand": brand["id"], "folder": str(folder)}), 400)

    def test_limit_pauses_and_resumes(self):
        pid = self.project("Limit")
        self.stop(); self.start("limit")
        call(f"/api/projects/{pid}/propose", {})
        p = self.wait(pid, ["limited"])
        self.assertIn("limit", p["note"].lower())
        self.stop(); self.start("ok")
        call(f"/api/projects/{pid}/resume", {})
        self.wait(pid, ["proposal"])

    def test_crash_reports_failure(self):
        pid = self.project("Crash")
        self.stop(); self.start("crash")
        call(f"/api/projects/{pid}/propose", {})
        p = self.wait(pid, ["failed"])
        self.assertIn("exploded", p["note"])
        self.stop(); self.start("ok")

    def test_stop_and_closing_the_app_can_resume(self):
        pid = self.project("Stop")
        self.stop(); self.start("slow")
        call(f"/api/projects/{pid}/propose", {})
        self.wait(pid, ["working"])
        time.sleep(0.4)
        call(f"/api/projects/{pid}/stop", {})
        self.wait(pid, ["stopped"])
        call(f"/api/projects/{pid}/resume", {})
        self.wait(pid, ["working"])
        self.stop(); self.start("ok")
        self.assertEqual(call(f"/api/projects/{pid}")["stage"], "stopped")
