#!/usr/bin/env python3
"""Find the most active stretch of a clip with no voiceover, such as gameplay, sports or b-roll.
usage: highlight.py video.mp4 [--words words.json] [--min 7] [--max 30] [--top 3] [--json out.json]

Scores every half second by how much the picture changes and how loud the sound is, then proposes
windows between --min and --max seconds around the peaks. With --words it also says whether the clip
has enough speech to caption. Game dialogue counts as speech too, so confirm it is the creator talking.

This only finds candidates. Look at each one with `eyes burst` or `eyes frames` before choosing:
motion is not the same as a good moment, and a menu or a loading screen can score high."""
import argparse
import json
import re
import statistics
import subprocess
import sys

STEP = 0.5


def duration(video):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video]).decode())


def motion(video):
    """Mean absolute difference between consecutive small frames, per frame time."""
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-an", "-vf",
           "fps=10,scale=160:-2,format=gray,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
           "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    pts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", out)]
    val = [float(x) for x in re.findall(r"YAVG=([\d.]+)", out)]
    return list(zip(pts, val))


def loudness(video):
    """RMS level in dB for each 0.1 s of audio; empty if the clip has no sound."""
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-vn", "-af",
           "aresample=48000,asetnsamples=4800,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
           "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    pts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", out)]
    val = [float(x) if x not in ("-inf", "inf", "nan") else -90.0 for x in re.findall(r"RMS_level=(\S+)", out)]
    return list(zip(pts, val))


def bucket(samples, n):
    sums, counts = [0.0] * n, [0] * n
    for t, v in samples:
        k = min(int(t / STEP), n - 1)
        sums[k] += v
        counts[k] += 1
    return [s / c if c else None for s, c in zip(sums, counts)]


def zscores(xs):
    known = [x for x in xs if x is not None]
    if len(known) < 2:
        return [0.0] * len(xs)
    mu, sd = statistics.mean(known), statistics.pstdev(known) or 1.0
    return [((x if x is not None else mu) - mu) / sd for x in xs]


def windows(score, lo, hi, top):
    """Grow a window around each peak while it stays above the clip's median, within lo..hi seconds."""
    n, med = len(score), statistics.median(score)
    lo_n, hi_n = max(1, int(lo / STEP)), max(1, int(hi / STEP))
    taken, found = [False] * n, []
    for peak in sorted(range(n), key=lambda k: -score[k]):
        if taken[peak] or len(found) >= top:
            continue
        a = b = peak
        while b - a + 1 < hi_n:
            left = score[a - 1] if a > 0 and not taken[a - 1] else None
            right = score[b + 1] if b < n - 1 and not taken[b + 1] else None
            if left is None and right is None:
                break
            grow_left = right is None or (left is not None and left >= right)
            best = left if grow_left else right
            if b - a + 1 >= lo_n and best < med:
                break
            a, b = (a - 1, b) if grow_left else (a, b + 1)
        if b - a + 1 < lo_n:
            continue
        for k in range(a, b + 1):
            taken[k] = True
        found.append({"start": round(a * STEP, 2), "end": round((b + 1) * STEP, 2), "peak": round(peak * STEP, 2),
                      "score": round(statistics.mean(score[a:b + 1]), 2)})
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--words", help="words.json from transcribe.py, to tell whether the clip has speech")
    ap.add_argument("--min", type=float, default=7)
    ap.add_argument("--max", type=float, default=30)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--json", help="also write the result here")
    a = ap.parse_args()

    dur = duration(a.video)
    n = max(1, int(dur / STEP + 0.999))
    mot, loud = bucket(motion(a.video), n), bucket(loudness(a.video), n)
    score = [round(m + 0.6 * l, 3) for m, l in zip(zscores(mot), zscores(loud))]
    lo, hi = min(a.min, dur), min(a.max, dur)
    result = {"video": a.video, "duration": round(dur, 2), "windows": windows(score, lo, hi, a.top)}
    if not result["windows"]:
        result["windows"] = [{"start": 0, "end": round(hi, 2), "peak": 0, "score": 0}]

    if a.words:
        words = json.load(open(a.words)).get("words", [])
        rate = len(words) / dur if dur else 0
        result["speech"] = {"words": len(words), "per_second": round(rate, 2),
                            "captionable": len(words) >= 8 and rate >= 0.5}

    result["curve"] = [[round(k * STEP, 1), s] for k, s in enumerate(score)]
    if a.json:
        json.dump(result, open(a.json, "w"), indent=1)
    print(f"{result['duration']}s")
    for w in result["windows"]:
        print(f"  {w['start']:>7.2f}-{w['end']:<7.2f} peak {w['peak']:.1f}s  score {w['score']}")
    if "speech" in result:
        s = result["speech"]
        print(f"  speech: {s['words']} words, {s['per_second']}/s -> {'captions' if s['captionable'] else 'no captions (visual edit)'}")


if __name__ == "__main__":
    sys.exit(main())
