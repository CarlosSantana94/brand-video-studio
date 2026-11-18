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

Copy `assets/watcher.example.json` and edit it. It works the same on macOS and Windows. Use forward slashes in Windows paths, or doubled backslashes.

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

- Install the tools with Homebrew (`brew install python ffmpeg node`), plus `eyes` and Claude Code, then run
  `python3 <skill>/scripts/doctor.py`.
- With OneDrive or Dropbox on the Mac, turn on "Always keep on this device" for the folder, as on Windows.
- To start it at login, save this as `~/Library/LaunchAgents/com.clips.watcher.plist`, with your paths.
  launchd starts programs with an almost empty `PATH`, so list every folder that holds `claude`, `node`,
  `ffmpeg` and `eyes` (`which claude ffmpeg node eyes` prints them):

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
    <key>Label</key><string>com.clips.watcher</string>
    <key>ProgramArguments</key>
    <array>
      <string>/opt/homebrew/bin/python3</string>
      <string>/Users/YOU/.claude/skills/brand-video-studio/scripts/watcher.py</string>
      <string>--config</string>
      <string>/Users/YOU/clips-page/watcher.json</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/YOU/.local/bin</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardErrorPath</key><string>/Users/YOU/clips-page/logs/launchd.err</string>
  </dict>
  </plist>
  ```

  Load it with `launchctl load ~/Library/LaunchAgents/com.clips.watcher.plist` and stop it with
  `launchctl unload` on the same file. If Claude Code was installed with npm under nvm, add that Node's
  `bin` folder to `PATH` too, or set `"claude"` in the config to its full path.
- A Mac that sleeps does not watch. Keep it awake while plugged in (System Settings, Battery or Energy), or run
  the watcher in a terminal with `caffeinate -i python3 .../watcher.py --config watcher.json`.

## TODO: scheduling with Buffer

Not implemented yet, on purpose. The planned flow:

1. Something (a small script or the visual app) watches `review/approved/`.
2. For each approved card, it reads `edits/<id>.mp4` and the matching section of `copy/<id>.md` per channel.
3. It creates a **draft or queued** post through the Buffer API, never "share now", and moves the card to
   `review/scheduled/`.
4. `SPOILER` or `NEEDS-CHECK` cards are never sent unless a human removed the flag.

The hook point is marked `TODO(buffer)` in `watcher.py`.
