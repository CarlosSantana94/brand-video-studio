#!/usr/bin/env python3
"""Stands in for `claude -p` in the watcher tests: reads the prompt from stdin and writes the deliverables."""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
prompt = sys.stdin.read()
grab = lambda label: re.search(rf"^- {label}:\s+(.+)$", prompt, re.M).group(1).strip()
clip = re.search(r"^Clip: (.+)$", prompt, re.M).group(1).strip()
work = re.search(r"^Work only inside (.+?) \(", prompt, re.M).group(1)
shutil.copy(clip, grab("video"))
Path(grab("copy")).write_text("# FAKE HOOK\n## X\ncaption\n## Instagram\ncaption\n#a #b #c\n## TikTok / Shorts\ncaption #a #b #c\n## Credit\nOwn footage\n", encoding="utf-8")
spoiler = os.environ.get("FAKE_SPOILER") == "1"
Path(work, "result.json").write_text(json.dumps({"status": "ready", "hook": "FAKE HOOK", "start": 1, "end": 9, "voiceover": False,
                                                "spoiler": spoiler, "flags": [], "notes": "fake run"}), encoding="utf-8")
print(json.dumps({"type": "result", "result": "done"}))
