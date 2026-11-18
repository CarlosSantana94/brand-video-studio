#!/usr/bin/env python3
"""Watch a folder for new clips and edit each one with Claude Code in headless mode, one at a time.
usage: watcher.py --config watcher.json [--once] [--dry-run]

Every finished edit lands in <out>/review/ for a human to approve. Nothing is ever published.

  <out>/raw/      the original clip and <id>.json metadata (date, source, creator, permission)
  <out>/edits/    final MP4s
  <out>/copy/     COPY.md per clip: hook, captions for X, Instagram and TikTok/Shorts, credit
  <out>/review/   one card per clip waiting for approval, with its flags (SPOILER, NEEDS-CHECK, ...)
  <out>/work/     Claude's project folder per clip
  <out>/log.md    one line per clip;   <out>/logs/watcher.log   the detailed log

A clip is picked up once its size has not changed for "stable_seconds", which covers OneDrive, Dropbox and
network copies still in progress. Metadata comes from an optional sidecar next to the clip, named
<clip>.meta.json (or <clip-without-extension>.json):
  {"source": "own" | "creator", "creator": "@name", "permission": true, "voiceover": false, "notes": "..."}
Spanish keys work too: fuente/propio/creador, creador, permiso. Without a sidecar the clip is your own.
A clip from another creator without "permission": true is skipped and never sent to Claude.

Uses the watchdog package when it is installed and falls back to polling otherwise. See
references/auto-clips.md for the configuration, and for starting it when the computer starts."""
import argparse
import datetime as dt
import json
import logging
import os
import queue
import re
import shutil
import string
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
FORMATS = {"9:16": "1080x1920", "16:9": "1920x1080", "1:1": "1080x1080"}
DEFAULTS = {
    "style": "gaming", "lang": "en", "format": "9:16", "min_len": 7, "max_len": 30, "voiceover": "auto",
    "extensions": [".mp4", ".mov", ".mkv", ".webm"], "stable_seconds": 20, "poll_seconds": 5,
    "timeout_minutes": 45, "claude": "claude", "claude_args": [], "rules": [],
}
BASE_RULES = [
    "Story spoilers: never put plot, ending, character-fate or mission-outcome information in the hook or on "
    "the first frame (it is the cover). If the clip shows story content (a cutscene, a mission ending, a "
    "reveal), set \"spoiler\": true and the flag \"SPOILER\" in result.json, and start every caption in "
    "the copy with \"SPOILER:\".",
    "Footage from another creator (metadata source \"creator\"): process it only if metadata permission is "
    "true. Credit the creator's handle on screen for the whole clip (a pill layer) and in every caption and "
    "the Credit line. If permission is not true, write status \"skipped\" and make nothing.",
    "Do not invent facts. A tip, number, location, mechanic or claim goes in the hook or captions only if it "
    "is visible or said in the clip. If you cannot verify it, keep the line generic.",
    "If anything is uncertain (who is speaking, whether it is a spoiler, licensed music in the audio), add "
    "the flag \"NEEDS-CHECK\" and explain it in notes instead of guessing.",
]
ALLOWED_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep",
                 "Bash(python3:*)", "Bash(python:*)", "Bash(py:*)", "Bash(eyes:*)", "Bash(ffmpeg:*)", "Bash(ffprobe:*)",
                 "Bash(npx:*)", "Bash(cd:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)", "Bash(ls:*)", "Bash(cat:*)"]
SKIP_NAMES = re.compile(r"(^~|^\.|\.tmp$|\.part$|\.partial$|\.crdownload$|\.download$)", re.I)

log = logging.getLogger("watcher")


# ---------------------------------------------------------------- config and metadata
def load_config(path):
    cfg = dict(DEFAULTS, **json.load(open(path, encoding="utf-8")))
    for key in ("watch", "out", "brand"):
        if not cfg.get(key):
            sys.exit(f"{path}: \"{key}\" is required")
        cfg[key] = str(Path(os.path.expanduser(cfg[key])).resolve())
    cfg["extensions"] = [e.lower() for e in cfg["extensions"]]
    return cfg


def sidecar(clip):
    for cand in (clip.with_name(clip.name + ".meta.json"), clip.with_suffix(".meta.json"), clip.with_suffix(".json")):
        if cand.exists():
            try:
                return json.load(open(cand, encoding="utf-8"))
            except ValueError as e:
                log.warning("bad metadata %s: %s", cand, e)
                return {"_error": str(e)}
    return {}


def metadata(clip):
    raw = sidecar(clip)
    pick = lambda *keys, default=None: next((raw[k] for k in keys if k in raw), default)
    source = str(pick("source", "fuente", default="own")).lower()
    source = "creator" if source in ("creator", "creador", "other", "otro", "tercero") else "own"
    stat = clip.stat()
    return {
        "date": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "original": str(clip), "bytes": stat.st_size,
        "source": source,
        "creator": pick("creator", "creador"),
        "permission": pick("permission", "permiso", default=source == "own") is True,
        "voiceover": pick("voiceover", "voz"),
        "notes": pick("notes", "notas", default=""),
    }


def clip_id(clip, meta):
    stamp = meta["date"].replace("-", "").replace(":", "").replace("T", "-")
    slug = re.sub(r"[^a-z0-9]+", "-", clip.stem.lower()).strip("-")[:40] or "clip"
    return f"{stamp}-{slug}"


# ---------------------------------------------------------------- state
class State:
    """Remembers which files were handled, so a restart or a re-sync does not edit them twice."""

    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()
        self.data = json.load(open(path, encoding="utf-8")) if path.exists() else {}

    def key(self, clip):
        st = clip.stat()
        return f"{clip.name}|{st.st_size}"

    def seen(self, clip):
        return self.key(clip) in self.data

    def mark(self, clip, value):
        with self.lock:
            self.data[self.key(clip)] = value
            tmp = self.path.with_suffix(".tmp")
            json.dump(self.data, open(tmp, "w", encoding="utf-8"), indent=1)
            os.replace(tmp, self.path)


# ---------------------------------------------------------------- the job
class Watcher:
    def __init__(self, cfg, dry_run=False):
        self.cfg, self.dry_run = cfg, dry_run
        self.out = Path(cfg["out"])
        for sub in ("raw", "edits", "copy", "review", "work", "logs"):
            (self.out / sub).mkdir(parents=True, exist_ok=True)
        self.state = State(self.out / "state.json")
        self.jobs = queue.Queue()
        self.pending = set()
        self.plock = threading.Lock()

    # ---- discovery
    def candidate(self, path):
        p = Path(path)
        if p.suffix.lower() not in self.cfg["extensions"] or SKIP_NAMES.search(p.name):
            return False
        try:
            return p.is_file() and not self.out_contains(p)
        except OSError:
            return False

    def out_contains(self, p):
        try:
            p.resolve().relative_to(self.out)
            return True
        except ValueError:
            return False

    def offer(self, path):
        p = Path(path)
        if not self.candidate(p):
            return
        with self.plock:
            if str(p) in self.pending:
                return
            self.pending.add(str(p))
        threading.Thread(target=self.wait_stable, args=(p,), daemon=True).start()

    def scan(self):
        for root, _, files in os.walk(self.cfg["watch"]):
            for f in sorted(files):
                self.offer(os.path.join(root, f))

    def wait_stable(self, p):
        """Queue the file once its size stops changing and it can be opened (Windows locks files being written)."""
        need, last, since = self.cfg["stable_seconds"], -1, time.time()
        while True:
            try:
                size = p.stat().st_size
                if size != last:
                    last, since = size, time.time()
                elif size > 0 and time.time() - since >= need:
                    with open(p, "rb") as fh:
                        fh.read(1)
                    break
            except FileNotFoundError:
                with self.plock:
                    self.pending.discard(str(p))
                return
            except OSError:
                since = time.time()     # locked or still downloading
            time.sleep(min(2, need / 4) or 0.2)
        if self.state.seen(p):
            with self.plock:
                self.pending.discard(str(p))
            return
        log.info("queued %s (%d MB)", p.name, last // 2**20)
        self.jobs.put(p)

    # ---- processing
    def worker(self):
        while True:
            p = self.jobs.get()
            if p is None:
                return
            try:
                self.process(p)
            except Exception:
                log.exception("failed on %s", p)
                self.state.mark(p, {"status": "error"})
            finally:
                with self.plock:
                    self.pending.discard(str(p))
                self.jobs.task_done()

    def process(self, clip):
        meta = metadata(clip)
        cid = clip_id(clip, meta)
        if meta["source"] == "creator" and not meta["permission"]:
            log.warning("skipped %s: footage from %s without permission=true", clip.name, meta["creator"] or "another creator")
            self.log_md(cid, "skipped", ["NO-PERMISSION"], "Other creator's footage without permission")
            self.state.mark(clip, {"id": cid, "status": "skipped"})
            return

        raw = self.out / "raw" / f"{cid}{clip.suffix.lower()}"
        if not raw.exists():
            shutil.copy2(clip, raw)
        meta["raw"] = str(raw)
        json.dump(meta, open(raw.with_suffix(".json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

        work = self.out / "work" / cid
        work.mkdir(parents=True, exist_ok=True)
        edit, copy = self.out / "edits" / f"{cid}.mp4", self.out / "copy" / f"{cid}.md"
        prompt = self.prompt(raw, cid, meta, work, edit, copy)
        (work / "prompt.md").write_text(prompt, encoding="utf-8")
        if self.dry_run:
            log.info("dry run: prompt for %s written to %s", cid, work / "prompt.md")
            return

        result_path = work / "result.json"
        if result_path.exists():
            result_path.unlink()
        log.info("editing %s with Claude", cid)
        started = time.time()
        code = self.run_claude(prompt, work)
        result = {"status": "failed", "flags": ["NO-RESULT"], "notes": f"claude exited with {code} and wrote no result.json"}
        if result_path.exists():
            try:
                result = json.load(open(result_path, encoding="utf-8"))
            except ValueError as e:
                result["notes"] = f"result.json is not valid JSON: {e}"
        if result.get("status") == "ready" and not edit.exists():
            result = dict(result, status="failed", flags=result.get("flags", []) + ["NO-VIDEO"])
        flags = list(dict.fromkeys((["SPOILER"] if result.get("spoiler") else []) + list(result.get("flags", []))))
        mins = round((time.time() - started) / 60, 1)
        log.info("%s: %s in %s min %s", cid, result.get("status"), mins, " ".join(flags))
        self.review_card(cid, meta, result, flags, edit, copy, work)
        self.log_md(cid, result.get("status", "failed"), flags, result.get("hook") or result.get("notes", ""))
        self.state.mark(clip, {"id": cid, "status": result.get("status")})
        # TODO(buffer): once a card is approved (moved to review/approved/), queue edits/<id>.mp4 with the
        # captions from copy/<id>.md in Buffer. Never schedule anything that has not been approved by a human.

    def prompt(self, raw, cid, meta, work, edit, copy):
        rules = BASE_RULES + list(self.cfg["rules"])
        if self.cfg.get("rules_file"):
            rules.append(Path(self.cfg["rules_file"]).read_text(encoding="utf-8"))
        voice = self.cfg["voiceover"] if meta["voiceover"] is None else ("always" if meta["voiceover"] else "never")
        tpl = string.Template((SKILL / "assets" / "auto-clip-prompt.md").read_text(encoding="utf-8"))
        return tpl.safe_substitute(
            skill=SKILL, clip=raw, id=cid, meta=json.dumps(meta, ensure_ascii=False), brand=self.cfg["brand"],
            style=self.cfg["style"], min_len=self.cfg["min_len"], max_len=self.cfg["max_len"],
            format=self.cfg["format"], size=FORMATS[self.cfg["format"]], voiceover=voice, lang=self.cfg["lang"],
            work=work, edit=edit, copy=copy, rules="\n".join(f"- {r}" for r in rules))

    def run_claude(self, prompt, work):
        exe = shutil.which(self.cfg["claude"]) or self.cfg["claude"]
        cmd = [exe, "-p", "--output-format", "json", "--permission-mode", "acceptEdits",
               "--add-dir", str(SKILL), str(self.out), "--allowedTools", *ALLOWED_TOOLS, *self.cfg["claude_args"]]
        if exe.lower().endswith(".py"):
            cmd = [sys.executable] + cmd
        out_log = work / "claude.log"
        try:
            with open(out_log, "w", encoding="utf-8") as fh:
                # The prompt goes through stdin: Windows .cmd shims cut long command lines.
                proc = subprocess.run(cmd, input=prompt, text=True, encoding="utf-8", stdout=fh, stderr=subprocess.STDOUT,
                                      cwd=work, timeout=self.cfg["timeout_minutes"] * 60)
            return proc.returncode
        except subprocess.TimeoutExpired:
            log.error("claude timed out after %s min", self.cfg["timeout_minutes"])
            return "timeout"
        except FileNotFoundError:
            log.error("claude not found: set \"claude\" in the config to its full path")
            return "not-found"

    # ---- outputs
    def review_card(self, cid, meta, result, flags, edit, copy, work):
        rel = lambda p: os.path.relpath(p, self.out / "review")
        lines = [f"# {cid}", "",
                 f"- status: **{result.get('status')}**   flags: {' '.join(f'`{f}`' for f in flags) or 'none'}",
                 f"- hook: {result.get('hook', '')}",
                 f"- clip: {result.get('start', '?')}–{result.get('end', '?')} s of the original, voiceover: {result.get('voiceover')}",
                 f"- source: {meta['source']}{' ' + meta['creator'] if meta.get('creator') else ''}, recorded {meta['date']}",
                 f"- video: [{edit.name}]({rel(edit)})" if edit.exists() else "- video: none",
                 f"- copy: [{copy.name}]({rel(copy)})" if copy.exists() else "- copy: none",
                 f"- work: {work}", "", result.get("notes", ""), "",
                 "Approve: move this card to review/approved/. Reject: move it to review/rejected/.", ""]
        (self.out / "review" / f"{cid}.md").write_text("\n".join(lines), encoding="utf-8")

    def log_md(self, cid, status, flags, note):
        path = self.out / "log.md"
        if not path.exists():
            path.write_text("# Clip log\n\n| time | clip | status | flags | hook / note |\n|---|---|---|---|---|\n", encoding="utf-8")
        note = str(note).replace("|", "/").replace("\n", " ")[:120]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"| {dt.datetime.now():%Y-%m-%d %H:%M} | {cid} | {status} | {' '.join(flags)} | {note} |\n")


# ---------------------------------------------------------------- main
def observe(w):
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        log.info("watchdog not installed: polling every %ss", w.cfg["poll_seconds"])
        while True:
            w.scan()
            time.sleep(w.cfg["poll_seconds"])

    class Handler(FileSystemEventHandler):
        def on_created(self, e):
            if not e.is_directory:
                w.offer(e.src_path)

        def on_moved(self, e):
            if not e.is_directory:
                w.offer(e.dest_path)

        on_modified = on_created

    obs = Observer()
    obs.schedule(Handler(), w.cfg["watch"], recursive=True)
    obs.start()
    log.info("watching %s", w.cfg["watch"])
    try:
        while True:
            time.sleep(300)
            w.scan()        # catches anything an event missed, such as files synced while asleep
    finally:
        obs.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--once", action="store_true", help="handle what is in the folder now, then exit")
    ap.add_argument("--dry-run", action="store_true", help="write prompts and metadata but do not call Claude")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if not Path(cfg["watch"]).is_dir():
        sys.exit(f"watch folder not found: {cfg['watch']}")
    w = Watcher(cfg, a.dry_run)
    handlers = [logging.FileHandler(w.out / "logs" / "watcher.log", encoding="utf-8")]
    if sys.stdout:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)

    threading.Thread(target=w.worker, daemon=True).start()
    w.scan()
    if a.once:
        time.sleep(0.5)
        while True:     # wait for the stability checks, then for the queue
            with w.plock:
                if not w.pending:
                    break
            time.sleep(0.5)
        w.jobs.join()
        return
    observe(w)


if __name__ == "__main__":
    main()
