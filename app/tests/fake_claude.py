#!/usr/bin/env python3
"""Stands in for `claude -p` in tests: follows the prompt's contract without calling a model."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
prompt = sys.stdin.read()     # the app sends the prompt on stdin, as claude -p reads it
mode = os.environ.get("FAKE_CLAUDE", "ok")
say = lambda e: print(json.dumps(e), flush=True)
say({"type": "system", "subtype": "init"})
say({"type": "assistant", "message": {"content": [{"type": "text", "text": "Looking at the footage."},
     {"type": "tool_use", "name": "Bash", "input": {"description": "Survey the videos", "command": "python3 survey.py"}}]}})
if mode == "limit":
    say({"type": "result", "is_error": True, "result": "You've hit your limit · resets 3pm", "usage": {}})
    sys.exit(1)
if mode == "crash":
    print("something exploded", flush=True)
    sys.exit(2)
if mode == "slow":
    time.sleep(30)
footage = sorted(os.listdir("footage"))
if "Write proposal.json" in prompt:
    os.makedirs("source", exist_ok=True)
    sources = [{"id": f"clip-{i}", "path": f, "duration": 60, "words": 10} for i, f in enumerate(footage)]
    json.dump({"sources": sources}, open("source/sources.json", "w"))
    titles = [("01-first", "The first one"), ("02-second", "The second one"), ("03-third", "The third one")]
    json.dump({"summary": "Three strong moments.", "questions": ["Keep the intro?"], "videos": [
        {"name": n, "title": t, "type": "story", "hook": "Wait for it", "why": "It lands.", "duration": 30,
         "ranges": [[5 + i * 18, 20 + i * 18, "clip-0"]]} for i, (n, t) in enumerate(titles)]}, open("proposal.json", "w"))
elif "approved these videos" in prompt:
    names = prompt.split("proposal.json: ")[1].split(".\n")[0].split(", ")
    plan = json.load(open("plan.json")) if os.path.exists("plan.json") else {"videos": []}
    Path("renders").mkdir(exist_ok=True)
    for n in names:
        Path("videos", n).mkdir(parents=True, exist_ok=True)
        Path("videos", n, "cut.json").write_text(json.dumps({"src": "x.mp4", "ranges": [[0, 1]]}))
        shutil.copy(os.path.join("footage", footage[0]), f"renders/{n}.mp4")
        plan["videos"].append({"name": n, "title": n, "sources": ["clip-0"], "reviewed": True})
    json.dump(plan, open("plan.json", "w"))
    Path("COPY.md").write_text("## Copy\nA caption #tag\n")
say({"type": "result", "is_error": False, "result": "Done.", "total_cost_usd": 0.12, "duration_ms": 1500,
     "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 1000}})
