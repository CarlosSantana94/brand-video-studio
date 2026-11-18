# Clips without a voice

Use this for footage where nobody talks to the viewer: gameplay, sports, drone shots, b-roll, screen captures
with game sound only. Captions timed to words and `autocut.py` both need speech, so they do not apply here.
The edit is chosen by what happens on screen.

## 1. Decide whether there is a voice

```bash
python3 <skill>/scripts/transcribe.py clip.mp4 source/words.json --lang es
python3 <skill>/scripts/highlight.py clip.mp4 --words source/words.json --min 7 --max 30 --json source/highlight.json
```

`highlight.py` reports `speech.captionable`. Treat it as a hint, not the answer: game cutscenes, commentators
and NPCs produce words too. Caption only when the creator is talking to the viewer. If you are not sure,
leave captions off, since wrong captions look worse than none.

When there is a voiceover, follow `edit-raw-video.md` with captions on, as usual.

## 2. Find the moment by looking

`highlight.py` scores every half second by picture change and loudness, and proposes windows around the
peaks. Motion is not the same as a good moment. Menus, loading screens, fast camera spins and explosions
you only hear can all score high, so check each candidate:

```bash
eyes index clip.mp4                          # shots and contact sheets
eyes burst clip.mp4 12.0                     # dense frames around a peak
eyes frames clip.mp4 --range 0:10-0:28 --fps 2
```

Pick the payoff (the hit, the stunt, the near miss, the reveal) and trim around it:

- Start no more than 2 to 3 seconds before the action begins. Short platforms do not wait for a build-up.
- End just after the payoff, or on the reaction. Do not let it trail into walking around.
- Keep it within the target length. 7 to 30 seconds is the default for gameplay.
- Leave the game sound in. It carries the clip. Set `"captions": false` in `spec.json`.

## 3. Frame it for vertical

Wide footage in a 9:16 video loses about two thirds of its width. Choose one:

- **Follow the action** (default): keep the default cover crop and add `cam` moves with `x` to pan toward
  where things happen, for example `{"t": 0, "x": 400}` when the car is on the right. `x` reaches about
  ±1160 px.
- **Show the whole width**: add `"size": "1080x1920", "fit": "blur"` to `cut.json`. The full frame sits in
  the middle over a blurred copy of itself. Use it for wide scenes, races and anything where the sides matter.

## 4. Hook and layers

- The hook is on screen from frame 0 and says what is about to happen, written from what you saw. Use at
  most 3 lines of about 10 characters at the `gaming` size. Shorten it instead of shrinking the type.
- A `pill` can label the moment ("0 to 200 in 4 s") only if the clip shows it. Do not invent stats, places or
  mechanics.
- One punch-in (`cam` with `s: 1.15`) on the payoff is usually enough. Gameplay is already busy.

## 5. Build and review

Follow "Build a video" in `SKILL.md`, skipping the caption re-sync step. In review, also check that:

- The first frame is not a menu, a loading screen or a black frame.
- The payoff is inside the clip and not cut off by the closing, which starts 0.6 s before the end.
- The HUD, minimap or kill feed does not collide with the hook. If it does, move the hook with `hook.size`
  or pan the frame.
