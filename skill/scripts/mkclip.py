#!/usr/bin/env python3
"""Build assets/clip.mp4 by joining ranges of the source video.
usage: mkclip.py cut.json outdir   -> prints where each range starts in the clip
cut.json has "src" (source video path) and "ranges": [[start, end], ...] in source seconds.
Optional "vranges": other ranges for the picture (same total duration as "ranges"), to cover dark
shots or burned-in text with b-roll while the audio of "ranges" keeps playing."""
import json, subprocess, sys, os
cut = json.load(open(sys.argv[1])); out = sys.argv[2]
V = cut["src"]
os.makedirs(os.path.join(out, "assets"), exist_ok=True)
R = cut["ranges"]; VR = cut.get("vranges", R)
f, t = [], 0.0
for i, (a, b) in enumerate(VR):
    f.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=30[v{i}];")
for i, (a, b) in enumerate(R):
    d = b - a
    f.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={d-0.04:.3f}:d=0.04[a{i}];")
    print(f"range {i}: {a}-{b} -> clip {t:.3f}-{t+d:.3f}")
    t += d
tv = sum(b - a for a, b in VR)
if abs(tv - t) > 0.05:
    sys.exit(f"vranges lasts {tv:.3f}s and ranges {t:.3f}s: they must match")
fc = ("".join(f) + "".join(f"[v{i}]" for i in range(len(VR))) + f"concat=n={len(VR)}:v=1:a=0[v];"
      + "".join(f"[a{i}]" for i in range(len(R))) + f"concat=n={len(R)}:v=0:a=1[a]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", V, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-b:a", "192k", os.path.join(out, "assets", "clip.mp4")], check=True)
print("total", round(t, 3))
