# Companion skills

Other open-source skills that work well next to this one, picked from
[awesome-claude-video-skills](https://github.com/zhuyansen/awesome-claude-video-skills). That list has more
than 500 repos, each with a security grade. The picks below have the grade "safe" and the MIT license in
that list, and fill a gap this skill does not cover on its own.

They come from each repo's own description and the list's data, and have not been tested with this skill.
Read a skill's `SKILL.md` and scripts before installing it, as you would any code that runs on your machine.

## Already used by this skill

| Skill | Why |
|---|---|
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | The renderer. Its `hyperframes` skill holds the composition rules |
| [moritzkremb/claude-eyes](https://github.com/moritzkremb/claude-eyes) | Watching footage: shots, frames, transcripts, editing DNA |
| [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills) | three.js r186 API for `scenes` (`references/3d-scenes.md`) |

## Worth adding, by job

| Job | Skill | What it adds |
|---|---|---|
| More 9:16 looks | [threeaus/creator-style-kit](https://github.com/threeaus/creator-style-kit) | 18 vertical HyperFrames styles (type, color, motion, sound). Port one into `assets/styles.json` |
| Beat-synced montages | [BusyBee3333/viral-video-edit-skills](https://github.com/BusyBee3333/viral-video-edit-skills) | Song analysis and cuts on the beat, for gameplay or highlight montages set to music |
| Breaking down a viral video | [sharon-laicc/viral-video-decomposer](https://github.com/sharon-laicc/viral-video-decomposer) | Shot-by-shot breakdown of why a short works, to write better hooks. Pairs with `eyes dna` |
| 3D animated shorts | [luispablovillasenor-afk/shorts-animados-claude](https://github.com/luispablovillasenor-afk/shorts-animados-claude) | 2D characters in a three.js world. In Spanish |
| Motion graphics catalog | [iart-ai/motion-skills](https://github.com/iart-ai/motion-skills) | 56 skills: kinetic type, charts, 3D and more, for one-off effects beyond the presets |
| Talking head to reel | [kurbaitaev/ghost-editor](https://github.com/kurbaitaev/ghost-editor) | Another take on `edit-raw-video.md`, useful to compare results |
| Long video to Shorts | [AgriciDaniel/claude-shorts](https://github.com/AgriciDaniel/claude-shorts) | Remotion-based alternative to `reels-from-long-video.md` |
| Recaps with narration | [zenstory-ai/video-recap-skills](https://github.com/zenstory-ai/video-recap-skills) | Writes narration from what is on screen and voices it. Can export CapCut drafts |

## How to use one with this skill

- Keep `brand.json` as the single source of colors, fonts and voice. When another skill makes a piece (a
  3D short, a montage), hand it those values so the result still looks like the brand.
- Bring the result back as footage: add its MP4 to `cut.json` as a source, and let this skill add the hook,
  captions, closing and `COPY.md`.
- Review it the same way: `eyes index` and `review-checklist.md`.
