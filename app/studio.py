"""Brands, projects and the queue that runs Claude Code one job at a time."""
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from pathlib import Path

import prompts

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skill"
HOME = Path(os.environ.get("BVS_HOME", "~/BrandVideoStudio")).expanduser()
sys.path.insert(0, str(SKILL / "scripts"))
import batch  # noqa: E402

VIDEO = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")
AUDIO = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".aiff", ".ogg")
IMAGE = (".png", ".jpg", ".jpeg", ".svg", ".webp")
TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Skill", "Bash(python3:*)", "Bash(npx:*)", "Bash(ffmpeg:*)",
         "Bash(ffprobe:*)", "Bash(eyes:*)", "Bash(cd:*)", "Bash(ls:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)"]
LIMIT_WORDS = ("usage limit", "rate limit", "limit reached", "hit your limit", "out of extra usage")
lock = threading.RLock()


def slug(text, taken=()):
    plain = unicodedata.normalize("NFD", text.lower())
    base = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in plain if unicodedata.category(c) != "Mn")).strip("-")[:48] or "untitled"
    found, n = base, 2
    while found in taken:
        found, n = f"{base}-{n}", n + 1
    return found


def safe_id(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value or ""):
        raise ValueError("invalid id")
    return value


def safe_name(name):
    clean = re.sub(r"[^\w .()-]+", "-", os.path.basename(name).strip()).lstrip(".")
    return clean or "file"


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path, data):
    temp = Path(str(path) + ".tmp")
    temp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    temp.replace(path)


# Brands

def brands_dir():
    path = HOME / "brands"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_brands():
    found = []
    for d in sorted(brands_dir().iterdir()):
        data = read_json(d / "brand.json")
        if data:
            found.append({"id": d.name, **data, "notes": read_notes(d), "importing": (d / ".importing").exists()})
    return found


def read_notes(d):
    file = d / "BRAND.md"
    return file.read_text().split("## Voice\n", 1)[-1].strip() if file.exists() else ""


def get_brand(bid):
    d = brands_dir() / safe_id(bid)
    data = read_json(d / "brand.json")
    if not data:
        raise KeyError(bid)
    return {"id": bid, **data, "notes": read_notes(d), "importing": (d / ".importing").exists()}


def save_brand(data, bid=None):
    with lock:
        if not data.get("name", "").strip():
            raise ValueError("A brand needs a name")
        bid = safe_id(bid) if bid else slug(data["name"], {d.name for d in brands_dir().iterdir()})
        d = brands_dir() / bid
        (d / "assets").mkdir(parents=True, exist_ok=True)
        old = read_json(d / "brand.json", {})
        brand = {
            "name": data["name"].strip(), "handle": data.get("handle", "").strip(), "url": data.get("url", "").strip(),
            "cta": data.get("cta", "").strip(), "style": data.get("style", "pop-bounce"), "colors": data["colors"],
            "fonts": old.get("fonts") or {"display": {"family": "Shrikhand", "file": "Shrikhand-Regular.ttf"},
                                          "body": {"family": "Fredoka", "file": "Fredoka.ttf", "weights": "300 700"}},
        }
        for key in ("logo", "app", "source"):
            if old.get(key):
                brand[key] = old[key]
        for key in ("handle", "url", "cta"):
            if not brand[key]:
                del brand[key]
        if (d / ".importing").exists():
            raise ValueError("Claude is still reading this brand kit")
        write_json(d / "brand.json", brand)
        md = d / "BRAND.md"
        head = md.read_text().split("## Voice\n", 1)[0] if md.exists() else f'# {brand["name"]}\n\n'
        md.write_text(f'{head}## Voice\n{data.get("notes", "").strip()}\n')
        return get_brand(bid)


ROLES = ("ink", "ink_dark", "bg", "light", "accent", "highlight")
STARTER = {"ink": "#123C3A", "ink_dark": "#0A2221", "bg": "#F2E6C9", "light": "#FBF7EC", "accent": "#F2A541", "highlight": "#FFD27F"}


def import_brand(folder):
    """Claude reads a brand kit folder (guidelines, logos, fonts) and writes the brand from it."""
    src = Path(folder or "").expanduser()
    if not src.is_dir():
        raise ValueError("Choose a folder")
    if not claude_path():
        raise RuntimeError("Claude Code was not found. Install it, sign in, and start the app again.")
    with lock:
        bid = slug(src.name, {d.name for d in brands_dir().iterdir()})
        d = brands_dir() / bid
        (d / "assets").mkdir(parents=True)
        write_json(d / "brand.json", {"name": src.name, "style": "pop-bounce", "colors": STARTER, "source": str(src)})
        (d / ".importing").touch()
    threading.Thread(target=run_import, args=(bid, src), daemon=True).start()
    return get_brand(bid)


def contrast(a, b):
    def lum(v):
        c = [int(v[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def brand_problems(d, brand):
    problems = []
    if not all(re.fullmatch(r"#[0-9A-Fa-f]{6}", str(brand.get("colors", {}).get(r, ""))) for r in ROLES):
        problems.append("colors")
    for role in ("display", "body"):
        file = brand.get("fonts", {}).get(role, {}).get("file", "")
        if not file or not ((d / file).is_file() or (SKILL / "assets" / "fonts" / Path(file).name).is_file()):
            problems.append(f"{role} font")
    colors = brand.get("colors", {})
    if "colors" not in problems and min(contrast(colors["ink"], colors["bg"]), contrast(colors["ink"], colors["light"])) < 4.5:
        problems.append("contrast of ink against bg or light")
    if brand.get("logo") and not (d / brand["logo"]).is_file():
        problems.append("logo")
    return problems


def run_import(bid, src):
    d = brands_dir() / bid
    skills = d / ".claude" / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "brand-video-studio").symlink_to(SKILL)
    cmd = [claude_path(), "-p", prompts.import_brand(str(src)), "--output-format", "json", "--permission-mode", "acceptEdits",
           "--allowedTools", *TOOLS, "--add-dir", str(src)]
    try:
        done = subprocess.run(cmd, cwd=d, env=clean_env(), capture_output=True, text=True, timeout=1800)
        result = json.loads(done.stdout or "{}")
        failed = done.returncode or result.get("is_error")
        message = str(result.get("result") or done.stdout[-300:])
    except (subprocess.TimeoutExpired, ValueError) as error:
        failed, message, result = True, str(error), {}
    finally:
        shutil.rmtree(d / ".claude", ignore_errors=True)
    with lock:
        brand = read_json(d / "brand.json", {})
        problems = brand_problems(d, brand)
        if "colors" in problems:
            brand["colors"] = STARTER
        if any(p.endswith("font") for p in problems):
            brand.pop("fonts", None)
        if "logo" in problems:
            brand.pop("logo", None)
        brand["source"] = str(src)
        brand["import_cost"] = result.get("total_cost_usd", 0)
        if failed or problems:
            brand["import_note"] = ("Claude Code is not signed in. Run `claude` in a terminal, sign in, and try again."
                                    if "authenticate" in message.lower() else
                                    f"Check this brand: {', '.join(problems) or message[:200]}")
        else:
            brand.pop("import_note", None)
        brand.setdefault("fonts", {"display": {"family": "Shrikhand", "file": "Shrikhand-Regular.ttf"},
                                   "body": {"family": "Fredoka", "file": "Fredoka.ttf", "weights": "300 700"}})
        write_json(d / "brand.json", brand)
        (d / ".importing").unlink(missing_ok=True)


def set_logo(bid, name, stream, length):
    d = brands_dir() / safe_id(bid)
    ext = Path(safe_name(name)).suffix.lower()
    if ext not in IMAGE:
        raise ValueError("Use a PNG, JPG, SVG or WebP logo")
    for old in (d / "assets").glob("logo.*"):
        old.unlink()
    target = d / "assets" / f"logo{ext}"
    copy_stream(stream, target, length)
    brand = read_json(d / "brand.json")
    brand["logo"] = f"assets/logo{ext}"
    write_json(d / "brand.json", brand)
    return get_brand(bid)


def palette(bid):
    brand = get_brand(bid)
    if not brand.get("logo"):
        raise ValueError("Add a logo first")
    path = brands_dir() / bid / brand["logo"]
    if path.suffix == ".svg":
        raise ValueError("Colors can be read from a PNG, JPG or WebP logo")
    out = subprocess.check_output([sys.executable, str(SKILL / "scripts" / "extract_palette.py"), str(path), "--k", "6"])
    return json.loads(out)


def copy_stream(stream, target, length):
    left = length
    temp = Path(str(target) + ".part")
    with open(temp, "wb") as out:
        while left > 0:
            chunk = stream.read(min(1 << 20, left))
            if not chunk:
                temp.unlink(missing_ok=True)
                raise ValueError("The upload stopped before it finished")
            out.write(chunk)
            left -= len(chunk)
    temp.replace(target)


# Projects

def projects_dir():
    path = HOME / "projects"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_dir(pid):
    d = projects_dir() / safe_id(pid)
    if not (d / "project.json").exists():
        raise KeyError(pid)
    return d


def load(pid):
    return read_json(project_dir(pid) / "project.json")


def update(pid, **changes):
    with lock:
        data = load(pid)
        data.update(changes)
        write_json(project_dir(pid) / "project.json", data)
        return data


def create_project(data):
    with lock:
        brand = get_brand(data.get("brand", ""))
        name = data.get("name", "").strip() or "Untitled project"
        pid = slug(name, {d.name for d in projects_dir().iterdir()})
        d = projects_dir() / pid
        (d / "footage").mkdir(parents=True)
        (d / ".claude" / "skills").mkdir(parents=True)
        (d / ".claude" / "skills" / "brand-video-studio").symlink_to(SKILL)
        if brand.get("importing"):
            raise ValueError("Claude is still reading this brand kit")
        shutil.copytree(brands_dir() / brand["id"], d / "brand", ignore=shutil.ignore_patterns(".claude"))
        brief = data.get("brief") or {}
        formats = brief.get("formats") or [data.get("format", "9:16")]
        linked = link_folder(d / "footage", data["folder"]) if data.get("folder") else 0
        if data.get("folder") and not linked:
            shutil.rmtree(d)
            raise ValueError("That folder has no videos")
        remember(brand["id"], brief)
        record = {"id": pid, "name": name, "brand": brand["id"], "brand_name": brand["name"],
                  "request": data.get("request", "").strip(), "format": formats[0], "brief": brief,
                  "count": data.get("count") or None, "stage": "draft", "created": time.time(),
                  "session": None, "note": "", "tokens": 0, "cost": 0.0, "seconds": 0.0}
        write_json(d / "project.json", record)
        return record


def link_folder(target, folder):
    """Use videos where they are: raw footage is too big to copy for every project."""
    count = 0
    for file in folder_files(folder, VIDEO):
        (target / safe_name(file.name)).symlink_to(file)
        count += 1
    return count


def folder_files(folder, kinds):
    path = Path(folder).expanduser()
    if not path.is_dir():
        raise ValueError("That folder was not found")
    return sorted((f for f in path.iterdir() if f.is_file() and f.suffix.lower() in kinds and not f.name.startswith(".")),
                  key=lambda f: f.name.lower())


def describe_folder(folder, kind):
    files = folder_files(folder, AUDIO if kind == "audio" else VIDEO)
    return {"path": str(Path(folder).expanduser()), "files": [{"name": f.name, "mb": round(f.stat().st_size / 1e6, 1)} for f in files[:200]],
            "count": len(files)}


def pick_folder():
    """The browser cannot hand over a folder path, so the computer's own dialog does."""
    if shutil.which("osascript"):
        done = subprocess.run(["osascript", "-e", 'POSIX path of (choose folder)'], capture_output=True, text=True)
    elif shutil.which("zenity"):
        done = subprocess.run(["zenity", "--file-selection", "--directory"], capture_output=True, text=True)
    else:
        return {"path": None, "typed": True}
    return {"path": done.stdout.strip().rstrip("/") or None}


def remember(bid, brief):
    """Each brand starts from its last choices."""
    file = brands_dir() / bid / "brand.json"
    data = read_json(file)
    data["app"] = brief
    write_json(file, data)


def add_footage(pid, name, stream, length):
    clean = safe_name(name)
    if Path(clean).suffix.lower() not in VIDEO:
        raise ValueError("Use an MP4, MOV, M4V, MKV, WebM or AVI file")
    copy_stream(stream, project_dir(pid) / "footage" / clean, length)
    return clean


def list_projects():
    found = [read_json(d / "project.json") for d in projects_dir().iterdir()]
    return sorted((p for p in found if p), key=lambda p: -p["created"])


def videos_state(pid):
    d = project_dir(pid)
    plan = read_json(d / "plan.json", {"videos": []})
    return [{**v, "state": batch.state(str(d), v), "render": (d / "renders" / f'{v["name"]}.mp4').exists()}
            for v in plan.get("videos", [])]


def activity(pid, after=0):
    file = project_dir(pid) / "activity.jsonl"
    if not file.exists():
        return []
    lines = file.read_text().splitlines()[after:]
    return [json.loads(x) for x in lines]


def log(pid, kind, text):
    file = project_dir(pid) / "activity.jsonl"
    last = activity(pid)[-1:]
    if last and last[0]["kind"] == kind and last[0]["text"] == text[:600]:
        return
    with open(file, "a") as out:
        out.write(json.dumps({"t": time.time(), "kind": kind, "text": text[:600]}, ensure_ascii=False) + "\n")


def detail(pid):
    d = project_dir(pid)
    sources = read_json(d / "source" / "sources.json", {"sources": []})["sources"]
    footage = sorted(f.name for f in (d / "footage").iterdir() if f.suffix.lower() in VIDEO)
    copy = d / "COPY.md"
    return {**load(pid), "footage": footage, "sources": [{k: s.get(k) for k in ("id", "duration", "words")} for s in sources],
            "proposal": read_json(d / "proposal.json"), "videos": videos_state(pid),
            "copy": copy.read_text() if copy.exists() else "", "queued": jobs.position(pid), "active": jobs.active == pid}


# Claude Code

def claude_path():
    return os.environ.get("BVS_CLAUDE") or shutil.which("claude")


def tool_line(block):
    data = block.get("input", {})
    if block.get("name") == "Bash":
        return data.get("description") or data.get("command", "")[:120]
    if block.get("name") in ("Read", "Write", "Edit"):
        return f'{block["name"]} {Path(data.get("file_path", "")).name}'
    return block.get("name", "")


def clean_env():
    """Started from inside Claude Code, the app must not hand that session's settings to its own jobs."""
    env = {**os.environ, "PATH": f'{Path("~/.local/bin").expanduser()}:{os.environ.get("PATH", "")}'}
    if "CLAUDECODE" in env:
        for key in list(env):
            if key.startswith(("CLAUDE_CODE_", "CLAUDE_AGENT_")) or key in ("CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT", "ANTHROPIC_BASE_URL"):
                del env[key]
    # A headless run ends when Claude stops, so a render left in the background would be lost: keep everything in the
    # foreground and give long commands (renders, transcripts) room to finish.
    env.update(CLAUDE_CODE_DISABLE_BACKGROUND_TASKS="1", BASH_DEFAULT_TIMEOUT_MS="1800000", BASH_MAX_TIMEOUT_MS="3600000")
    return env


class Jobs:
    """One job at a time: renders are heavy, and a plan's limits are shared."""

    def __init__(self):
        self.waiting = queue.Queue()
        self.order = []
        self.active = None
        self.process = None
        self.stopped = False
        threading.Thread(target=self.work, daemon=True).start()

    def position(self, pid):
        return self.order.index(pid) + 1 if pid in self.order else 0

    def add(self, pid, kind, prompt, after, stage):
        if pid == self.active or pid in self.order:
            raise ValueError("This project already has a job running")
        update(pid, stage=stage, note="", job=kind)
        self.order.append(pid)
        self.waiting.put((pid, kind, prompt, after, stage))

    def stop(self, pid):
        self.stopped = True
        if pid == self.active and self.process:
            os.killpg(self.process.pid, signal.SIGTERM)
        elif pid in self.order:
            self.order.remove(pid)
            update(pid, stage="stopped")

    def work(self):
        while True:
            pid, kind, prompt, after, stage = self.waiting.get()
            if pid not in self.order:
                continue
            self.order.remove(pid)
            self.active, self.stopped = pid, False
            try:
                self.run(pid, prompt, after)
            except Exception as error:   # the worker must outlive one bad job
                log(pid, "error", str(error))
                update(pid, stage="failed", note=str(error))
            self.active, self.process = None, None

    def survey(self, pid):
        """Watching and transcribing every clip is plain work: the app does it, so Claude starts from the results."""
        d = project_dir(pid)
        if (d / "source" / "sources.json").exists():
            return
        log(pid, "note", "Viendo y transcribiendo tus clips" if footage_lang(load(pid)) == "es" else "Watching and transcribing your clips")
        cmd = [sys.executable, str(SKILL / "scripts" / "survey.py"), "footage", "--out", "source", "--lang", footage_lang(load(pid))]
        self.process = subprocess.Popen(cmd, cwd=d, env=clean_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, start_new_session=True)
        tail = []
        for line in self.process.stdout:
            tail = (tail + [line.strip()])[-5:]
        if self.process.wait() and not self.stopped:
            raise RuntimeError("Could not read the clips: " + " ".join(tail)[-300:])

    def run(self, pid, prompt, after):
        project = load(pid)
        binary = claude_path()
        if not binary:
            raise RuntimeError("Claude Code was not found. Install it, sign in, and start the app again.")
        if project.get("job") == "propose":
            self.survey(pid)
            if self.stopped:
                return self.finish(pid, None, 1, [], after)
        session = project.get("session")
        cmd = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
               "--allowedTools", *TOOLS, "--disallowedTools", "Monitor", "ScheduleWakeup", "CronCreate"]
        cmd += ["--resume", session] if session else ["--session-id", (session := str(uuid.uuid4()))]
        brief = project.get("brief", {})
        for folder in (brief.get("sfx_folder"), brief.get("music_folder")):
            if folder:
                cmd += ["--add-dir", folder]
        update(pid, session=session, job_started=time.time())
        env = clean_env()
        self.process = subprocess.Popen(cmd, cwd=project_dir(pid), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, start_new_session=True)
        final, tail = None, []
        for line in self.process.stdout:
            tail = (tail + [line.strip()])[-5:]
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text" and block["text"].strip():
                        log(pid, "say", block["text"].strip())
                    elif block.get("type") == "tool_use":
                        log(pid, "tool", tool_line(block))
            elif event.get("type") == "result":
                final = event
        code = self.process.wait()
        self.finish(pid, final, code, tail, after)

    def finish(self, pid, final, code, tail, after):
        project = load(pid)
        if final:
            usage = final.get("usage", {})
            used = sum(usage.get(k, 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            update(pid, tokens=project.get("tokens", 0) + used, cost=project.get("cost", 0) + final.get("total_cost_usd", 0),
                   seconds=project.get("seconds", 0) + final.get("duration_ms", 0) / 1000)
        message = (final or {}).get("result") or " ".join(tail)
        if self.stopped:
            log(pid, "note", "Stopped")
            update(pid, stage="stopped")
        elif code or not final or final.get("is_error"):
            limited = any(w in str(message).lower() for w in LIMIT_WORDS)
            log(pid, "error", str(message))
            if "authenticate" in str(message).lower():
                message = "Claude Code is not signed in. Run `claude` in a terminal, sign in, and try again."
            update(pid, stage="limited" if limited else "failed", note=str(message)[:400])
        else:
            if final.get("result"):
                log(pid, "say", final["result"])
            update(pid, stage=after(pid))


jobs = Jobs()


def recover():
    """A job cut off by closing the app can be picked up again."""
    for project in list_projects():
        if project["stage"] in ("working", "queued"):
            update(project["id"], stage="stopped", note="The app closed while this was running.")


SPANISH = re.compile(r"\b(el|la|los|las|que|una?|del|con|para|por|y|en)\b", re.I)
ENGLISH = re.compile(r"\b(the|and|with|for|from|this|that|of|to|is)\b", re.I)


def footage_lang(project):
    """The brief's language, else a guess from the request."""
    text = project.get("request", "")
    return project.get("brief", {}).get("lang") or ("es" if len(SPANISH.findall(text)) > len(ENGLISH.findall(text)) else "en")


def after_propose(pid):
    if read_json(project_dir(pid) / "proposal.json"):
        return "proposal"
    raise RuntimeError("Claude finished without a proposal. Ask it to try again.")


def after_build(pid):
    project = load(pid)
    renders = list((project_dir(pid) / "renders").glob("*.mp4"))
    if not any(r.stat().st_mtime > project.get("job_started", 0) for r in renders):
        raise RuntimeError("Claude finished without a new video. Ask it to try again.")
    videos = videos_state(pid)
    approved = load(pid).get("approved", [])
    done = [v["name"] for v in videos if v["state"] in ("reviewed", "rendered")]
    return "done" if approved and all(n in done for n in approved) else "first"


def start_propose(pid, changes=""):
    project = load(pid)
    if not project["request"]:
        raise ValueError("Say what you want first")
    if not any(f.suffix.lower() in VIDEO for f in (project_dir(pid) / "footage").iterdir()):
        raise ValueError("Add at least one video first")
    if changes:
        (project_dir(pid) / "proposal.json").unlink(missing_ok=True)
    jobs.add(pid, "propose", prompts.propose(project, changes), after_propose, "working")


def single_video(pid):
    return load(pid).get("brief", {}).get("single")


def start_build(pid, names, first_only=True, answers=""):
    proposal = read_json(project_dir(pid) / "proposal.json") or {"videos": []}
    known = [v["name"] for v in proposal["videos"]]
    approved = [n for n in known if n in names]
    if not approved:
        raise ValueError("Choose at least one video")
    project = update(pid, approved=approved, answers=answers)
    jobs.add(pid, "build", prompts.build(approved[:1] if first_only else approved, project), after_build, "working")


def make_rest(pid):
    project = load(pid)
    done = {v["name"] for v in videos_state(pid) if v["state"] in ("reviewed", "rendered")}
    rest = [n for n in project.get("approved", []) if n not in done]
    if not rest:
        return update(pid, stage="done")
    jobs.add(pid, "build", prompts.build(rest, project), after_build, "working")


def revise(pid, name, note):
    if not note.strip():
        raise ValueError("Describe the change")
    if name not in {v["name"] for v in videos_state(pid)}:
        raise ValueError("Unknown video")
    update(pid, last_change={"name": name, "note": note})
    jobs.add(pid, "revise", prompts.revise(name, note), after_build, "working")


def resume(pid):
    project = load(pid)
    if project.get("job") == "propose" or not project.get("session"):
        return start_propose(pid)
    change = project.get("last_change") if project.get("job") == "revise" else None
    jobs.add(pid, project.get("job", "build"), prompts.resume(change), after_build, "working")


def health():
    done = subprocess.run([sys.executable, str(SKILL / "scripts" / "doctor.py")], capture_output=True, text=True, timeout=60)
    lines = [x for x in done.stdout.splitlines() if x.startswith("MISS")]
    return {"claude": bool(claude_path()), "missing": lines, "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "home": str(HOME)}
