#!/usr/bin/env python3
"""Check the tools this skill needs and say how to install what is missing.
usage: doctor.py"""
import os
import re
import shutil
import subprocess
import sys

MIN_NODE = 22
TOOLS = [
    ("ffmpeg", True, "macOS: brew install ffmpeg | Debian/Ubuntu: apt install ffmpeg | Windows: winget install ffmpeg"),
    ("ffprobe", True, "comes with ffmpeg"),
    ("node", True, "https://nodejs.org, version 22 or newer (needed for npx hyperframes)"),
    ("npx", True, "comes with Node"),
    ("eyes", True, "uv tool install git+https://github.com/moritzkremb/claude-eyes && eyes setup --fix"),
    ("whisper-cli", False, "gives eyes local transcripts, and a fallback with WHISPER_MODEL set to a ggml model; Windows: see the README"),
]


def find(tool):
    if shutil.which(tool):
        return True
    return tool == "eyes" and any(os.path.exists(os.path.expanduser(p)) for p in ("~/.local/bin/eyes", "~/.local/bin/eyes.exe"))


def node_major():
    found = re.match(r"v(\d+)", subprocess.run([shutil.which("node"), "--version"], capture_output=True, text=True).stdout)
    return int(found.group(1)) if found else 0


def main():
    missing = False
    for tool, required, hint in TOOLS:
        ok = find(tool)
        print(f"{'ok  ' if ok else 'MISS' if required else 'skip'} {tool}" + ("" if ok else f"  -> {hint}"))
        missing |= required and not ok
    if find("node") and node_major() < MIN_NODE:
        print(f"MISS node {MIN_NODE}+  -> found {node_major()}; hyperframes needs a newer Node")
        missing = True
    elif find("npx"):
        # On Windows npx is npx.cmd, which only runs through its full path.
        done = subprocess.run([shutil.which("npx"), "--yes", "hyperframes", "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        print("ok   hyperframes", done.stdout.strip() if done.returncode == 0 else "(could not run; check your network)")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
