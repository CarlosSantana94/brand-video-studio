You are editing one new clip for a short-form page, with no one watching. Use the brand-video-studio
skill at $skill (read $skill/SKILL.md, $skill/references/auto-clips.md and $skill/references/clips-without-voice.md first) and finish on your own:
do not ask questions, because nobody will answer. Write every on-screen text and caption in $lang.

Clip: $clip
Clip id: $id
Metadata: $meta
Brand: $brand
Style preset: $style
Length: $min_len to $max_len seconds, $format, $size, MP4 H.264 + AAC.
Voiceover setting: $voiceover

Run the skill's Python scripts with `$python` (for example `$python $skill/scripts/highlight.py ...`).
Work only inside $work (your project folder) and write the deliverables to exactly:
- video: $edit
- copy:  $copy

## Steps

1. Index the clip with `eyes index "$clip"` and look at its contact sheets. Transcribe it with
   `transcribe.py` into $work/source/words.json.
2. Decide whether there is a voiceover to caption. Voiceover setting "never" means no; "always" means yes;
   "auto" means yes only if `highlight.py --words` says captionable AND the speech is the creator talking
   to the viewer, not game, film or broadcast dialogue.
3. No voiceover: do NOT use autocut.py and do NOT use word-timed captions. Run `highlight.py`, then check
   the candidate windows with `eyes burst` / `eyes frames` and pick the moment that is actually the
   payoff (the hit, the stunt, the reveal). Trim so the clip starts close to the action, ends just after
   the payoff, and lasts $min_len-$max_len s. Set `"captions": false` in spec.json.
   With voiceover: follow the normal raw-edit flow (references/edit-raw-video.md) with captions on.
4. Framing for $format: follow the action with `cam` x moves when the action stays in one part of the
   frame; use `"fit": "blur"` with `"size"` in cut.json when the whole width matters.
5. Hook: in the first second, at most 3 short lines, written from what you SAW in the clip.
6. Build, check, snapshot, render and loudness-normalize as SKILL.md says, then write the final file to
   $edit. Watch it once with `eyes index` and fix anything the review checklist flags.
7. Write $copy in this exact format:

   # <hook>
   ## X
   <caption, under 260 characters>
   ## Instagram
   <caption>
   <3 to 5 hashtags>
   ## TikTok / Shorts
   <caption with 3 to 5 hashtags>
   ## Credit
   <credit line, or "Own footage">

8. Finally write $work/result.json:
   {"status": "ready" | "skipped" | "failed", "hook": "...", "start": <s>, "end": <s>,
    "voiceover": true|false, "spoiler": true|false, "flags": ["..."], "notes": "one or two sentences"}
   Use "skipped" when a rule below forbids processing it, and say why in notes.

## Content rules (they override everything above)

$rules

Never publish, post, upload or schedule anything. Everything you make waits for human review.
