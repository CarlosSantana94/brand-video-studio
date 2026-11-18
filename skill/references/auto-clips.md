# Automatic clips from a watched folder

`scripts/watcher.py` watches a folder (a console's capture folder synced by OneDrive, a Dropbox folder, a
phone upload folder) and edits every new clip with Claude Code in headless mode, one at a time. Every
result waits in `review/` for a human. Nothing is published.

## What happens to each clip

1. The watcher waits until the file size has not changed for `stable_seconds` and the file can be opened.
   That covers cloud sync and copies still in progress.
2. It reads the optional metadata sidecar. Another creator's clip without `permission: true` is skipped
   and logged, and never reaches Claude.
3. It copies the clip into `raw/` with `<id>.json` metadata, then runs
   `claude -p --permission-mode acceptEdits --allowedTools ...` in `work/<id>/`, with the prompt from
   `assets/auto-clip-prompt.md` sent on stdin.
4. Claude edits the clip with this skill: `clips-without-voice.md` when nobody talks, the normal caption
   flow when there is a voiceover. It renders to `edits/<id>.mp4`, writes `copy/<id>.md`, and reports in
   `work/<id>/result.json`.
5. The watcher writes `review/<id>.md` with the status and flags (`SPOILER`, `NEEDS-CHECK`, `NO-VIDEO`),
   and a line in `log.md`.

```
<out>/
  raw/       original clip + <id>.json (date, source, creator, permission)
  edits/     final MP4, 1080x1920 H.264 + AAC
  copy/      <id>.md: hook, X, Instagram (3-5 hashtags), TikTok/Shorts, credit line
  review/    one card per clip; move it to review/approved/ or review/rejected/
  work/      Claude's project per clip, prompt.md and claude.log, for debugging
  logs/watcher.log
  log.md
  state.json files already handled, so a restart does not edit them twice
```

## Configuration

Copy `assets/watcher.example.json` and edit it. Use forward slashes in Windows paths, or doubled backslashes.

| Key | Meaning |
|---|---|
| `watch` | Folder to watch, including subfolders |
| `out` | Output folder. Keep it outside the watched folder and outside OneDrive |
| `brand` | Path to `brand.json` |
| `style` | Preset, `gaming` by default |
| `lang` | Language for on-screen text and copy, such as `es` or `en` |
| `format`, `min_len`, `max_len` | `9:16`, 7 and 30 seconds by default |
| `voiceover` | `auto`, `never` or `always`. Use `never` for game captures that never carry your voice |
| `stable_seconds` | How long the size must stay the same before a clip is picked up |
| `timeout_minutes` | Limit per clip |
| `claude` | Command or full path of Claude Code |
| `claude_args` | Extra arguments, such as `["--model", "sonnet"]` |
| `rules`, `rules_file` | Your own content rules, added to the built-in ones |

## Metadata sidecar

Next to a clip, `<clip>.mp4.meta.json` or `<clip>.meta.json`:

```json
{ "source": "creator", "creator": "@name", "permission": true, "voiceover": false, "notes": "race at night" }
```

Spanish keys work too: `fuente` (`propio` / `creador`), `creador`, `permiso`, `voz`, `notas`. A clip
without a sidecar is your own footage. The sidecar can arrive a little after the clip, because it is read
when the clip is processed.

## Built-in content rules

These are always added to the prompt. Add more with `rules`.

- No story spoilers in the hook or on the first frame. Story clips get the `SPOILER` flag, and every caption
  starts with "SPOILER:".
- Other creators' footage only with `permission: true`, credited on screen and in every caption.
- No invented facts. Claims, tips and numbers must be visible or said in the clip, or the line stays generic.
- When something is uncertain, add the `NEEDS-CHECK` flag and explain it instead of guessing.
- Never publish, post or schedule.

For a fan page about someone else's game, film or show, add a rule like the one in the example config: no
official logos, key art or fonts, and nothing that could pass as official.

## Running it

```bash
pip install watchdog                     # optional; without it the watcher polls every poll_seconds
python3 <skill>/scripts/watcher.py --config watcher.json --dry-run --once   # write prompts only
python3 <skill>/scripts/watcher.py --config watcher.json --once             # handle what is there, then exit
python3 <skill>/scripts/watcher.py --config watcher.json                    # keep watching
```

Claude Code must be installed and signed in on the same computer (run `claude` once by hand). The machine
also needs everything `doctor.py` checks: Python 3, ffmpeg, Node and `eyes`.

### Windows

- Install Python 3, ffmpeg (`winget install Gyan.FFmpeg`), Node 22 or newer, `eyes` and Claude Code. Link the
  skill with `powershell -ExecutionPolicy Bypass -File install.ps1` from the repo, then run
  `python <skill>\scripts\doctor.py`.
- In OneDrive, right-click the capture folder and choose **Always keep on this device**. Otherwise clips
  stay as cloud placeholders until something reads them.
- Start it with Windows using Task Scheduler. `pythonw` runs it without a console window:

  ```bat
  schtasks /Create /TN "Clip watcher" /SC ONLOGON /RL LIMITED /TR "\"C:\Path\To\pythonw.exe\" \"C:\Users\YOU\.claude\skills\brand-video-studio\scripts\watcher.py\" --config \"C:\Users\YOU\clips-page\watcher.json\""
  ```

  Remove it with `schtasks /Delete /TN "Clip watcher"`. A shortcut to the same command in
  `shell:startup` works too.

### macOS

Use a LaunchAgent with `RunAtLoad` set to `true`, or run it in a terminal with `caffeinate -i`.

## TODO: scheduling with Buffer

Not implemented yet, on purpose. The planned flow:

1. Something (a small script or the visual app) watches `review/approved/`.
2. For each approved card, it reads `edits/<id>.mp4` and the matching section of `copy/<id>.md` per channel.
3. It creates a **draft or queued** post through the Buffer API, never "share now", and moves the card to
   `review/scheduled/`.
4. `SPOILER` or `NEEDS-CHECK` cards are never sent unless a human removed the flag.

The hook point is marked `TODO(buffer)` in `watcher.py`.
