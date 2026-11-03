# cut.json and spec.json

## cut.json: what plays

```json
{
  "src": "/absolute/path/source.mp4",
  "ranges": [[120.4, 131.2], [140.0, 152.5]],
  "vranges": [[120.4, 126.0], [300.0, 305.2], [140.0, 152.5]],
  "t0": 0,
  "fix": { "Lisboa": "Lisbon", "cost@125.3": "coast", "uh@140.2": "" },
  "add": [[126.1, 126.4, "really"]],
  "drop": ["um", "uh"],
  "names": ["Lisbon", "Airbnb"]
}
```

- **`ranges`:** source seconds, joined in order. They carry the audio, and the picture unless `vranges` is set.
- **`vranges`:** optional. Other shots for the picture. The total duration must equal `ranges`.
- **`fix`:** transcription corrections. A plain key changes every appearance, so use `word@second` when a word appears more than once. An empty value removes it.
- **`add`:** words the transcriber missed, as `[start, end, word]`.
- **`drop`:** filler words hidden from captions. They stay in the audio.
- **`names`:** capitalized words that should not start a new caption group.

## spec.json: how it looks

All times are seconds in the assembled clip. The hook sits over the start of the clip, so speech continues under it.

```json
{
  "style": "pop-bounce",
  "format": "9:16",
  "hook": { "lines": ["The day we", "almost quit"], "pill": "a true story", "icon": "star", "size": 116 },
  "hook_end": 3.5,
  "closing": true,
  "captions": true,
  "voice": true,
  "cam": [
    { "t": 0, "s": 1.1, "x": 120 },
    { "t": 6, "d": 0.5, "s": 1.25, "y": -80 }
  ],
  "layers": [
    { "type": "pill", "t": 4.2, "d": 1.8, "text": "Day one" },
    { "type": "stat", "t": 6, "d": 1.8, "big": "$102", "sub": "per person", "size": 150 },
    { "type": "check", "t": 8, "d": 4, "title": "Worth it?", "items": [[8.3, "The view", "ok"], [9, "The queue", "no"]] },
    { "type": "list", "t": 13, "d": 4, "title": "Order this", "items": [[13.3, "Tacos"], [14, "Soup"]] },
    { "type": "gauge", "t": 18, "d": 3, "title": "Cold-o-meter", "value": 0.8, "label": "down to -8 °C" }
  ],
  "sfx": [[12.4, "impact", 0.4]],
  "music": { "src": "assets/music.mp3", "vol": 0.9, "dur": 28 }
}
```

- **`style`:** overrides `brand.json`.
- **`format`:** `9:16`, `16:9` or `1:1`. Default `9:16`.
- **`hook`:** omit it for no hook. `pill`, `icon` and `size` are optional. Icons: `star`, `bolt`, `heart`, `pin`, `camera`, `money`, `check`, `play`.
- **`closing`:** default `true`. With `false` the video ends on the last clip frame.
- **`captions`:** set `false` for b-roll.
- **`voice`:** set `false` to mute the clip, as when `music` replaces it. Copy the music file into `assets/`.
- **`cam`:** moves of the video frame: `s` scale, `x`, `y`, `d` duration, optional `ease`. `t: 0` sets the opening framing. Add `"sfx": false` to skip its swish.
- **`layers`:** each has start `t`, duration `d` and optional `top` in pixels. Items in `check` and `list` carry their own appear time, timed to the moment they are said. A card enters just before its first row, because an empty card looks broken.
- **`sfx`:** extra effects as `[time, name, volume]`. Effects for layers, hook and closing are added automatically.

Run `make_video.py` again after any change: it regenerates every composition, so edit `spec.json` and not the HTML. For a one-off effect that the spec cannot express, edit the HTML as the last step and say so, because the next build overwrites it.
