#!/usr/bin/env python3
"""
teardown.py - break a reference reel into shots, transitions, beats, colour,
camera motion and hook metrics.

    python tools/teardown.py media/airports.mp4 -o references/airports

Screen recordings are handled: the script finds the video area inside the app
UI and skips stretches where the UI takes over (Control Center, app switcher).
Everything it reports is a measurement or a heuristic - the report says which.

Options:
  --start / --end S     only analyse this window (seconds, source time)
  --crop W:H:X:Y        force the video area (source pixels); --no-crop to disable
  --fps N               analysis frame rate (default: source rate, max 60)
  --sensitivity X       cut threshold as a multiple of local activity (default 3.0;
                        lower = more cuts)
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
ANALYSIS_WIDTH = 320   # frames kept for thumbnails
METRIC_WIDTH = 160     # frames used for scores / flow


def sh(cmd: list[str]) -> bytes:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout


# --------------------------------------------------------------------------- probe
def probe(path: Path) -> dict:
    j = json.loads(sh([FFPROBE, "-v", "error", "-print_format", "json",
                       "-show_streams", "-show_format", str(path)]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if "rotate" in (v.get("tags") or {}):
        rot = int(v["tags"]["rotate"])
    if abs(rot) % 180 == 90:
        w, h = h, w

    def rate(s: str) -> float:
        n, d = s.split("/")
        return float(n) / float(d) if float(d) else 0.0

    fps = rate(v.get("avg_frame_rate", "0/1"))
    if not 0 < fps <= 240:
        fps = rate(v.get("r_frame_rate", "30/1"))
    dur = float(j["format"].get("duration") or v.get("duration") or 0)
    return dict(width=w, height=h, fps=round(fps, 3), duration=dur,
                codec=v.get("codec_name"),
                has_audio=any(s["codec_type"] == "audio" for s in j["streams"]))


def read_frames(path: Path, *, fps: float, width: int, src_size: tuple[int, int],
                crop=None, start: float = 0.0, end: float | None = None):
    cw, ch = (crop[0], crop[1]) if crop else src_size
    height = max(2, int(round(width * ch / cw / 2)) * 2)
    vf = []
    if crop:
        vf.append("crop=%d:%d:%d:%d" % tuple(crop))
    vf += [f"fps={fps}", f"scale={width}:{height}:flags=area"]
    cmd = [FFMPEG, "-v", "error", "-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-t", f"{end - start:.3f}"]
    cmd += ["-i", str(path), "-an", "-vf", ",".join(vf),
            "-pix_fmt", "bgr24", "-f", "rawvideo", "-"]
    raw = sh(cmd)
    fsz = width * height * 3
    n = len(raw) // fsz
    frames = np.frombuffer(raw[: n * fsz], np.uint8).reshape(n, height, width, 3)
    return frames, start + np.arange(n) / fps


def longest_run(mask: np.ndarray):
    best, cur, best_rng = 0, 0, None
    for i, m in enumerate(list(mask) + [False]):
        if m:
            cur += 1
        else:
            if cur > best:
                best, best_rng = cur, (i - cur, i)
            cur = 0
    return best_rng


# ------------------------------------------------------------ content area / window
def detect_content(path: Path, info: dict, use_crop: bool = True):
    """Find the video area inside a screen recording and the time window where
    the app UI is not covering it."""
    fps, width = 5, 160
    frames, times = read_frames(path, fps=fps, width=width,
                                src_size=(info["width"], info["height"]))
    g = frames.mean(axis=3).astype(np.float32)
    n, H, W = g.shape
    med = np.median(g, axis=0)
    dev = np.abs(g - med)

    crop, box = None, (0, H, 0, W)
    if use_crop:
        # a pixel is "content" if it departs from its own median look most of the time
        active = (dev > 18).mean(axis=0) > 0.35
        rows = longest_run(active.mean(axis=1) > 0.25)
        cols = longest_run(active.mean(axis=0) > 0.25)
        if rows and cols:
            y0, y1 = rows
            x0, x1 = cols
            if (y1 - y0) / H > 0.9:
                y0, y1 = 0, H
            if (x1 - x0) / W > 0.9:
                x0, x1 = 0, W
            box = (y0, y1, x0, x1)
            sx, sy = info["width"] / W, info["height"] / H
            X, Y = int(x0 * sx) // 2 * 2, int(y0 * sy) // 2 * 2
            CW, CH = int((x1 - x0) * sx) // 2 * 2, int((y1 - y0) * sy) // 2 * 2
            if not (X == 0 and Y == 0 and CW >= info["width"] - 2 and CH >= info["height"] - 2):
                crop = (CW, CH, X, Y)

    # UI takeover: the area outside the video departs from its usual look
    outside = np.ones((H, W), bool)
    y0, y1, x0, x1 = box
    outside[y0:y1, x0:x1] = False
    flagged = np.zeros(n, bool)
    if outside.sum() > 0.05 * H * W:
        flagged = dev[:, outside].mean(axis=1) > 15
        # close single-sample gaps so a blip doesn't split the window
        for i in range(1, n - 1):
            if flagged[i - 1] and flagged[i + 1]:
                flagged[i] = True
    rng = longest_run(~flagged)
    i0, i1 = rng if rng else (0, n)
    start = float(times[i0])
    end = min(info["duration"], float(times[i1 - 1]) + 1 / fps)
    excluded = []
    run = None
    for i, f in enumerate(list(flagged) + [False]):
        if f and run is None:
            run = i
        elif not f and run is not None:
            excluded.append((round(float(times[run]), 2), round(float(times[i - 1]) + 1 / fps, 2)))
            run = None
    other_windows = []
    if rng:
        # content outside the chosen window (e.g. the reel looping again)
        if i0 > 0:
            other_windows.append((0.0, round(start, 2)))
        if i1 < n:
            other_windows.append((round(end, 2), round(info["duration"], 2)))
    return crop, (start, end), excluded, other_windows


# ------------------------------------------------------------------------- scores
def frame_metrics(frames: np.ndarray):
    n = len(frames)
    h = int(round(METRIC_WIDTH * frames.shape[1] / frames.shape[2]))
    small = np.stack([cv2.resize(f, (METRIC_WIDTH, h), interpolation=cv2.INTER_AREA)
                      for f in frames])
    hsv = np.stack([cv2.cvtColor(s, cv2.COLOR_BGR2HSV) for s in small]).astype(np.float32)
    gray = np.stack([cv2.cvtColor(s, cv2.COLOR_BGR2GRAY) for s in small])
    luma = gray.reshape(n, -1).mean(axis=1)
    score = np.zeros(n)
    if n > 1:
        d = np.abs(np.diff(hsv, axis=0))
        d[..., 0] = np.minimum(d[..., 0], 180 - d[..., 0])  # hue wraps
        score[1:] = d.mean(axis=(1, 2, 3))
    return small, hsv, gray, luma, score


def hsv_dist(a: np.ndarray, b: np.ndarray) -> float:
    d = np.abs(a - b)
    d[..., 0] = np.minimum(d[..., 0], 180 - d[..., 0])
    return float(d.mean())


def detect_cuts(score, hsv, fps, sensitivity=3.0, min_score=8.0):
    """Adaptive threshold: a frame is a cut candidate when its change score is
    well above the local activity around it. Then pair up enter/exit spikes to
    find flash frames, and decide whether the flash hides a cut."""
    n = len(score)
    w = max(4, int(round(fps * 0.3)))
    cands = []
    for t in range(1, n):
        win = [score[i] for i in range(max(1, t - w), min(n, t + w + 1))
               if abs(i - t) > 1 and score[i] > 0.2]          # skip duplicate frames
        base = float(np.median(win)) if win else 0.0
        if score[t] < min_score or score[t] / (base + 1.0) < sensitivity:
            continue
        # a cut is a spike: it must clearly beat at least one side of its
        # immediate neighbourhood (rejects zoom/blur ramps that climb steadily)
        def side(idx):
            v = [score[i] for i in idx if 0 < i < n and score[i] > 0.2]
            return float(np.mean(v)) if v else 0.0
        if score[t] < 1.8 * min(side(range(t - 3, t - 1)), side(range(t + 2, t + 4))):
            continue
        cands.append(t)
    # non-max suppression (keep the strongest within 2 frames)
    kept = []
    for t in cands:
        if kept and t - kept[-1] <= 2:
            if score[t] > score[kept[-1]]:
                kept[-1] = t
        else:
            kept.append(t)

    cuts, events = [], []
    max_flash = max(2, int(round(0.2 * fps)))
    i = 0
    while i < len(kept):
        t = kept[i]
        nxt = kept[i + 1] if i + 1 < len(kept) else None
        if nxt is not None and nxt - t <= max_flash:
            pre, post = hsv[t - 1], hsv[nxt]
            d_pp = hsv_dist(pre, post)
            flash_len = (nxt - t) / fps
            if d_pp < 0.5 * min(score[t], score[nxt]):
                events.append(dict(type="flash / stutter frame", frame=t, duration=round(flash_len, 3),
                                   note="frame(s) jump then return to the same shot - a flash accent or a stutter, no cut"))
            else:
                cuts.append(dict(frame=t, kind="flash-masked cut", flash=round(flash_len, 3)))
            i += 2
            continue
        cuts.append(dict(frame=t, kind="hard cut"))
        i += 1

    # Local flashes: a small part of the frame (a silhouette, a light leak) jumps
    # in brightness for a few frames. Too small to move the global score.
    V = hsv[..., 2]
    jump = np.zeros((n,) + V.shape[1:], bool)
    jump[1:] = np.abs(np.diff(V, axis=0)) > 60
    frac = jump.mean(axis=(1, 2))
    busy = {c["frame"] + k for c in cuts for k in range(-3, 4)} | \
           {e["frame"] + k for e in events for k in range(-3, 4)}
    t = 1
    while t < n - 1:
        win = [frac[i] for i in range(max(1, t - w), min(n, t + w + 1)) if abs(i - t) > 1]
        base = float(np.median(win)) if win else 0.0
        if t in busy or frac[t] < 0.01 or frac[t] < 6 * base + 0.002:
            t += 1
            continue
        mask = jump[t]
        exit_ = None
        for t2 in range(t + 1, min(n, t + max_flash + 1)):
            if (jump[t2] & mask).sum() > 0.4 * mask.sum():
                exit_ = t2
                break
        if exit_ is None:
            t += 1
            continue
        # a real flash brightens nearly every changed pixel toward white; stutter,
        # blur and motion change pixels in both directions
        up = (V[t][mask] > V[t - 1][mask]).mean()
        whiteish = V[t][mask].mean() > 185 and hsv[t][..., 1][mask].mean() < 70
        if up < 0.85 or not whiteish:
            t += 1
            continue
        d_region = float(np.abs(V[exit_][mask] - V[t - 1][mask]).mean())
        dur = round((exit_ - t) / fps, 3)
        if d_region > 25:
            cuts.append(dict(frame=t, kind="flash-masked cut", flash=dur, local=True))
        else:
            events.append(dict(type="white object flash", frame=t, duration=dur,
                               note=f"one object/area ({frac[t] * 100:.1f}% of frame) flashes white - no cut"))
        t = exit_ + 1
    cuts.sort(key=lambda c: c["frame"])
    return cuts, events


def smooth(x, k):
    if k <= 1 or len(x) < k:
        return np.asarray(x, float)
    return np.convolve(x, np.ones(k) / k, mode="same")


def detect_fades(luma, fps, cut_frames=(), black=14.0):
    """Fades to / from near-black. A fade never crosses a cut."""
    n = len(luma)
    bounds = [0] + sorted(cut_frames) + [n]
    fades = []
    for a, b in zip(bounds, bounds[1:]):
        for f in _fades_in_shot(luma[a:b], fps, black):
            fades.append(dict(type=f["type"], start_frame=f["start_frame"] + a,
                              end_frame=f["end_frame"] + a))
    return fades


def _fades_in_shot(luma, fps, black):
    s = smooth(luma, max(3, int(fps * 0.15)))
    n = len(s)
    fades = []
    is_black = s < black
    # include an ending that is still descending toward black
    tail_dark = n > 0 and s[-1] < black * 1.8
    i = 0
    while i < n:
        if is_black[i] or (i == n - 1 and tail_dark):
            j = i
            while j > 0 and s[j - 1] >= s[j] - 0.3:
                j -= 1
            if (i - j) / fps >= 0.25 and s[j] >= 2.5 * max(s[i], 1):
                fades.append(dict(type="fade out", start_frame=j, end_frame=i))
            k = i
            while k < n and is_black[k]:
                k += 1
            m = k
            while m < n - 1 and s[m + 1] >= s[m] - 0.3 and s[m + 1] < 200:
                m += 1
            if k < n and (m - k) / fps >= 0.25 and s[m] >= 2.5 * max(s[k], 1):
                fades.append(dict(type="fade in", start_frame=k, end_frame=m))
            i = max(k, i + 1)
        else:
            i += 1
    return fades


def detect_gradual(score, cuts, fps):
    """Stretches of sustained heavy change without a hard cut: dissolves, growing
    insets, whip pans, fast subject motion. Flagged for a human to look at."""
    k = max(3, int(round(fps * 0.2)))
    s = smooth(score, k)
    thr = max(5.0, 2.5 * float(np.median(score[score > 0.2])) if (score > 0.2).any() else 5.0)
    cut_frames = {c["frame"] for c in cuts}
    out, run = [], None
    for i, v in enumerate(list(s) + [0]):
        if v > thr and run is None:
            run = i
        elif v <= thr and run is not None:
            if (i - run) / fps >= 0.2 and not any(run - k <= c <= i + k for c in cut_frames):
                out.append(dict(type="gradual change / fast motion", start_frame=run, end_frame=i))
            run = None
    return out


# ----------------------------------------------------------------- per-shot stats
def palette(frames_bgr: np.ndarray, k: int = 5):
    px = frames_bgr.reshape(-1, 3).astype(np.float32)
    if len(px) > 20000:
        px = px[np.random.default_rng(0).choice(len(px), 20000, replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, labels, centers = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k)
    order = np.argsort(-counts)
    return [dict(hex="#%02x%02x%02x" % tuple(int(c) for c in centers[i][::-1]),
                 share=round(float(counts[i] / counts.sum()), 3)) for i in order]


def tone_words(a: float, b: float, sat: float) -> str:
    words = []
    if a < -3 and b < -2:
        words.append("teal")
    elif a < -3:
        words.append("green tint")
    elif a > 4 and b < 0:
        words.append("magenta/purple")
    elif a > 4:
        words.append("red tint")
    if b > 8:
        words.append("warm/orange")
    elif b < -5 and "teal" not in words:
        words.append("cool/blue")
    if sat < 0.18:
        words.append("desaturated")
    elif sat > 0.45:
        words.append("saturated")
    return ", ".join(words) or "neutral"


def camera_motion(gray: np.ndarray, fps: float):
    """Global motion from dense optical flow. Speeds are % of frame width per second."""
    n, H, W = gray.shape
    if n < 3:
        return dict(move="too short to tell", speed=0.0, energy=0.0)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    rx, ry = xs - W / 2, ys - H / 2
    rn = np.sqrt(rx ** 2 + ry ** 2) + 1e-3
    dxs, dys, divs, mags = [], [], [], []
    for i in range(1, n):
        if np.abs(gray[i].astype(np.int16) - gray[i - 1]).mean() < 0.5:
            continue  # duplicate frame
        f = cv2.calcOpticalFlowFarneback(gray[i - 1], gray[i], None, 0.5, 3, 15, 3, 5, 1.2, 0)
        fx, fy = f[..., 0], f[..., 1]
        dxs.append(float(np.median(fx)))
        dys.append(float(np.median(fy)))
        divs.append(float(np.mean((fx * rx + fy * ry) / rn)))
        mags.append(float(np.mean(np.hypot(fx, fy))))
    if not mags:
        return dict(move="static", speed=0.0, energy=0.0)
    k = 100.0 * fps / W
    dx, dy = np.median(dxs) * k, np.median(dys) * k
    div = np.median(divs) * k
    energy = float(np.median(mags) * k)
    trans = float(np.hypot(dx, dy))
    jitter = float(np.hypot(np.std(dxs), np.std(dys)) * k)
    if energy < 1.5:
        move = "static"
    elif abs(div) > 0.6 * trans and abs(div) > 1.0:
        move = "push in" if div > 0 else "pull out"
    elif trans > 1.5:
        if abs(dx) >= abs(dy):
            move = "pan right" if dx < 0 else "pan left"
        else:
            move = "tilt down" if dy < 0 else "tilt up"
    else:
        move = "subject motion (camera ~static)"
    if jitter > 6 and move != "static":
        move += ", handheld"
    return dict(move=move, speed=round(max(trans, abs(div)), 1), energy=round(energy, 1),
                jitter=round(jitter, 1))


def shot_stats(small, hsv, gray, fps):
    n = len(small)
    idx = np.linspace(min(1, n - 1), max(n - 2, 0), num=min(8, n)).round().astype(int)
    samp = small[idx]
    lab = np.stack([cv2.cvtColor(s, cv2.COLOR_BGR2LAB) for s in samp]).astype(np.float32)
    g = gray[idx].astype(np.float32)
    a = float(lab[..., 1].mean() - 128)
    b = float(lab[..., 2].mean() - 128)
    sat = float(hsv[idx][..., 1].mean() / 255)
    return dict(
        palette=palette(samp),
        luma=round(float(g.mean()), 1),
        contrast=round(float(np.percentile(g, 98) - np.percentile(g, 2)), 1),
        clip_shadows_pct=round(float((g < 6).mean() * 100), 1),
        clip_highlights_pct=round(float((g > 249).mean() * 100), 1),
        saturation=round(sat, 2), lab_a=round(a, 1), lab_b=round(b, 1),
        tone=tone_words(a, b, sat),
        **camera_motion(gray, fps),
    )


# -------------------------------------------------------------------------- audio
def analyse_audio(path: Path, start: float, end: float):
    try:
        import librosa
    except ImportError:
        return dict(error="librosa not installed")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        sh([FFMPEG, "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
            "-i", str(path), "-vn", "-ac", "1", "-ar", "22050", str(wav)])
        y, sr = librosa.load(str(wav), sr=22050)
    if len(y) == 0 or float(np.sqrt(np.mean(y ** 2))) < 1e-3:
        return dict(error="no usable audio (silent or muted)")
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=env, sr=sr, units="time")
    rms = librosa.feature.rms(y=y)[0]
    rt = librosa.times_like(rms, sr=sr)
    first = rms[rt < 0.5]
    return dict(
        tempo=round(float(np.atleast_1d(tempo)[0]), 1),
        beats=[round(float(t) + start, 3) for t in beats],
        onsets=[round(float(t) + start, 3) for t in onsets],
        opening_loudness_ratio=round(float(first.mean() / (np.median(rms) + 1e-9)), 2) if len(first) else None,
    )


def nearest(t: float, grid: list[float]):
    if not grid:
        return None
    g = np.asarray(grid)
    i = int(np.argmin(np.abs(g - t)))
    return float(t - g[i])


# ------------------------------------------------------------------------- output
def font(size, bold=False):
    from PIL import ImageFont
    for p in (f"/usr/share/fonts/opentype/inter/Inter-{'SemiBold' if bold else 'Regular'}.otf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def to_pil(bgr):
    from PIL import Image
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def contact_sheet(shots, frames, out: Path):
    from PIL import Image, ImageDraw
    tw = 240
    th = int(round(tw * frames.shape[1] / frames.shape[2]))
    pad, text_w, pal_w = 12, 400, 120
    W = pad + 3 * (tw + pad) + pal_w + pad + text_w
    H = pad + len(shots) * (th + pad)
    img = Image.new("RGB", (W, H), (17, 17, 17))
    d = ImageDraw.Draw(img)
    f1, f2 = font(18, True), font(14)
    for r, s in enumerate(shots):
        y = pad + r * (th + pad)
        a, b = s["_a"], s["_b"]
        for c, fi in enumerate([a, (a + b - 1) // 2, b - 1]):
            img.paste(to_pil(frames[fi]).resize((tw, th)), (pad + c * (tw + pad), y))
        x = pad + 3 * (tw + pad)
        yy = y
        for p in s["palette"]:
            if yy >= y + th - 1:
                break
            h = max(2, int(round(p["share"] * th)))
            d.rectangle([x, yy, x + pal_w - 1, min(y + th, yy + h) - 1], fill=p["hex"])
            yy += h
        tx = x + pal_w + pad
        d.text((tx, y), f"Shot {s['shot']}  {s['start']:.2f}-{s['end']:.2f}s", fill=(235, 235, 235), font=f1)
        lines = [f"{s['duration']:.2f}s  ({s['frames']} fr)", f"in: {s['cut_in']}",
                 f"camera: {s['move']}", f"tone: {s['tone']}",
                 f"luma {s['luma']}  contrast {s['contrast']}  sat {s['saturation']}"]
        for i, ln in enumerate(lines):
            d.text((tx, y + 26 + i * 19), ln, fill=(170, 170, 170), font=f2)
    img.save(out, quality=88)


def timeline(shots, frames, fps, window, audio, events, out: Path):
    from PIL import Image, ImageDraw
    W, margin = 1600, 40
    t0, t1 = window
    span = max(t1 - t0, 1e-3)
    X = lambda t: int(margin + (t - t0) / span * (W - 2 * margin))
    strip_y, strip_h = 70, 110
    H = 340
    img = Image.new("RGB", (W, H), (17, 17, 17))
    d = ImageDraw.Draw(img)
    fl, fs = font(15, True), font(13)
    ink, muted, accent = (235, 235, 235), (120, 120, 120), (255, 176, 32)
    d.text((margin, 14), "Pacing timeline - each block is a shot, width = duration", fill=ink, font=fl)
    beats = (audio or {}).get("beats") or []
    for bt in beats:
        if t0 <= bt <= t1:
            d.line([X(bt), strip_y - 18, X(bt), strip_y - 6], fill=muted, width=1)
    if beats:
        d.text((margin, strip_y - 36), f"beats ({audio['tempo']} bpm)", fill=muted, font=fs)
    for s in shots:
        x0, x1 = X(s["start"]), X(s["end"])
        bw = max(1, x1 - x0 - 2)
        fr = to_pil(frames[(s["_a"] + s["_b"] - 1) // 2])
        sc = max(strip_h / fr.height, bw / fr.width)          # cover the block
        fr = fr.resize((max(bw, int(round(fr.width * sc))), max(strip_h, int(round(fr.height * sc)))))
        cx, cy = (fr.width - bw) // 2, (fr.height - strip_h) // 2
        img.paste(fr.crop((cx, cy, cx + bw, cy + strip_h)), (x0 + 1, strip_y))
        if bw > 22:
            d.rectangle([x0 + 1, strip_y, x0 + 24, strip_y + 18], fill=(17, 17, 17))
            d.text((x0 + 5, strip_y + 2), str(s["shot"]), fill=ink, font=fs)
    for s in shots[1:]:
        d.line([X(s["start"]), strip_y - 4, X(s["start"]), strip_y + strip_h + 4], fill=accent, width=2)
    ay = strip_y + strip_h + 10
    d.line([margin, ay, W - margin, ay], fill=muted, width=1)
    step = 1 if span <= 20 else 5 if span <= 90 else 15
    t = np.ceil(t0)
    while t <= t1:
        d.line([X(t), ay, X(t), ay + 5], fill=muted)
        d.text((X(t) - 8, ay + 8), f"{t:g}s", fill=muted, font=fs)
        t += step
    ey = ay + 34
    groups = []   # point events of the same type that sit close together share one label
    for e in [e for e in events if "time" in e]:
        x = X(e["time"])
        if groups and groups[-1]["type"] == e["type"] and x - groups[-1]["x1"] < 140:
            groups[-1]["x1"], groups[-1]["n"] = x, groups[-1]["n"] + 1
        else:
            groups.append(dict(type=e["type"], x0=x, x1=x, n=1))
        d.polygon([(x, ey), (x + 5, ey + 5), (x, ey + 10), (x - 5, ey + 5)], fill=ink)
    for g in groups:
        label = g["type"] + (f" x{g['n']}" if g["n"] > 1 else "")
        d.text((g["x0"] - 5, ey + 13), label, fill=ink, font=fs)
    for e in [e for e in events if "start" in e]:
        d.rectangle([X(e["start"]), ey + 34, max(X(e["end"]), X(e["start"]) + 2), ey + 40], fill=muted)
        d.text((X(e["start"]), ey + 43), e["type"].split(" /")[0], fill=muted, font=fs)
    d.text((margin, H - 24), "orange line = detected cut   grey ticks = beats   white diamonds = flash events   grey bars = fades / gradual change (check by eye)",
           fill=muted, font=fs)
    img.save(out)


def fmt_off(x):
    return "-" if x is None else f"{x * 1000:+.0f} ms"


def write_report(out: Path, a: dict, template: Path | None):
    L = []
    src, s = a["source"], a["summary"]
    L += [f"# Teardown: {src['file']}", "",
          "_Generated by `tools/teardown.py`. Numbers are measurements; anything marked "
          "**heuristic** is an estimate - verify by eye before you rely on it._", "",
          "![timeline](timeline.png)", "",
          "## Source", "",
          f"- {src['width']}x{src['height']} @ {src['fps']} fps, {src['duration']:.2f}s, codec {src['codec']}",
          f"- Video area analysed: {'full frame' if not a['crop'] else 'crop W:H:X:Y = ' + ':'.join(map(str, a['crop']))}",
          f"- Content window: {a['window'][0]:.2f}s - {a['window'][1]:.2f}s"]
    if a["excluded_ui"]:
        L.append("- Skipped (app UI covering the video): " + ", ".join(f"{x:.2f}-{y:.2f}s" for x, y in a["excluded_ui"]))
    if a["other_windows"]:
        L.append("- Not analysed (outside the main window, e.g. the reel looping): "
                 + ", ".join(f"{x:.2f}-{y:.2f}s" for x, y in a["other_windows"]))
    L += ["", "## Summary", "",
          f"- **{s['shots']} shots** in {s['length']:.2f}s - average {s['avg_shot']:.2f}s, "
          f"median {s['median_shot']:.2f}s, shortest {s['min_shot']:.2f}s, longest {s['max_shot']:.2f}s",
          f"- Cuts per second: {s['cuts_per_sec']:.2f}"]
    au = a["audio"]
    if au and "error" not in au:
        L.append(f"- Tempo: **{au['tempo']} bpm** (beat length {60 / au['tempo']:.3f}s). "
                 "Beat trackers sometimes report half or double the real tempo.")
        L.append(f"- Cuts within ±{s['beat_tolerance_ms']} ms of a beat: **{s['cuts_on_beat']}/{s['cuts']}**; "
                 f"of a beat or half-beat: {s['cuts_on_half_beat']}/{s['cuts']}")
    elif au:
        L.append(f"- Audio: {au['error']}")
    h = a["hook"]
    L += ["", "## Hook (first seconds) - heuristic", "",
          f"- First cut at **{h['first_cut']:.2f}s**" if h["first_cut"] is not None else "- No cut at all",
          f"- Cuts in the first 3s: {h['cuts_first_3s']} (average shot there {h['avg_shot_first_3s']:.2f}s vs {s['avg_shot']:.2f}s overall)",
          f"- Motion in the first second: {h['motion_first_sec']} %w/s (reel median {h['motion_median']} %w/s)",
          f"- Opening frame vs reel average: brightness {h['open_luma']} vs {h['avg_luma']}, contrast {h['open_contrast']} vs {h['avg_contrast']}"]
    if h.get("opening_loudness") is not None:
        L.append(f"- Audio in the first 0.5s is {h['opening_loudness']}x the median loudness "
                 f"({'starts strong' if h['opening_loudness'] >= 0.8 else 'starts quiet / builds'})")
    L += [f"- Loop: {h['loop']}",
          "- Not measured (fill in): on-screen text in the first second, what question the opening makes you ask", ""]

    L += ["## Shots", "", "![contact sheet](contact_sheet.jpg)", "",
          "| # | in | out | dur | cut in | to beat | camera (heuristic) | tone | luma / contrast / sat |",
          "|---|----|-----|-----|--------|---------|--------------------|------|-----------------------|"]
    for sh_ in a["shots"]:
        L.append(f"| {sh_['shot']} | {sh_['start']:.2f} | {sh_['end']:.2f} | {sh_['duration']:.2f} | {sh_['cut_in']} | "
                 f"{fmt_off(sh_['cut_offset_beat'])} | {sh_['move']} | {sh_['tone']} | "
                 f"{sh_['luma']} / {sh_['contrast']} / {sh_['saturation']} |")
    L += ["", "## Transitions and events", ""]
    if a["events"]:
        for e in a["events"]:
            when = f"{e['time']:.2f}s" if "time" in e else f"{e['start']:.2f}-{e['end']:.2f}s"
            beat = ""
            if e.get("beat_offset") is not None:
                beat = f" (beat {fmt_off(e['beat_offset'])}, half-beat {fmt_off(e['half_beat_offset'])})"
            L.append(f"- **{e['type']}** at {when}{beat}" + (f" - {e['note']}" if e.get("note") else ""))
    else:
        L.append("- None detected beyond hard cuts.")
    L += ["", "Known blind spots: a layer appearing inside a shot (a composite, a growing inset) is reported "
          "as a hard cut; masks, text animation, speed ramps and sound design are not detected. "
          "Check the contact sheet and note them below.", "",
          "## Colour", "", f"- Overall tone: **{a['colour']['tone']}** "
          f"(Lab a* {a['colour']['lab_a']}, b* {a['colour']['lab_b']}; negative a* = green, negative b* = blue)",
          "- Reel palette: " + " ".join(f"`{p['hex']}` {p['share'] * 100:.0f}%" for p in a["colour"]["palette"]), ""]
    if template and template.exists():
        L += ["---", "", template.read_text()]
    (out / "report.md").write_text("\n".join(L) + "\n")


# --------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    ap.add_argument("--crop", help="W:H:X:Y in source pixels")
    ap.add_argument("--no-crop", action="store_true")
    ap.add_argument("--fps", type=float, default=None,
                    help="analysis frame rate (default: source rate, max 60)")
    ap.add_argument("--sensitivity", type=float, default=3.0)
    args = ap.parse_args(argv)

    info = probe(args.input)
    # analyse at the source rate: resampling shifts cut times by up to half a frame slot
    fps = args.fps or min(info["fps"] or 30.0, 60.0)
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] probing content area ...", file=sys.stderr)
    crop, window, excluded, other = detect_content(args.input, info, use_crop=not args.no_crop and not args.crop)
    if args.crop:
        crop = tuple(int(v) for v in args.crop.split(":"))
    if args.start is not None or args.end is not None:
        window = (args.start if args.start is not None else 0.0,
                  args.end if args.end is not None else info["duration"])
        excluded, other = [], []

    print(f"[2/5] decoding {window[0]:.2f}-{window[1]:.2f}s at {fps} fps ...", file=sys.stderr)
    frames, times = read_frames(args.input, fps=fps, width=ANALYSIS_WIDTH, crop=crop,
                                start=window[0], end=window[1],
                                src_size=(info["width"], info["height"]))
    small, hsv, gray, luma, score = frame_metrics(frames)
    n = len(frames)
    T = lambda i: round(float(window[0] + i / fps), 3)

    print("[3/5] detecting cuts, flashes, fades ...", file=sys.stderr)
    cuts, flash_events = detect_cuts(score, hsv, fps, args.sensitivity)
    fades = detect_fades(luma, fps, [c["frame"] for c in cuts])
    gradual = detect_gradual(score, cuts, fps)

    print("[4/5] analysing audio ...", file=sys.stderr)
    audio = analyse_audio(args.input, *window) if info["has_audio"] else dict(error="no audio track")
    beats = audio.get("beats", []) if audio else []
    half = sorted(beats + [(a + b) / 2 for a, b in zip(beats, beats[1:])])
    tol = max(0.07, 2 / fps)

    print("[5/5] per-shot stats and images ...", file=sys.stderr)
    bounds = [0] + [c["frame"] for c in cuts] + [n]
    kinds = ["start"] + [c["kind"] for c in cuts]
    shots = []
    for i in range(len(bounds) - 1):
        a_, b_ = bounds[i], bounds[i + 1]
        if b_ <= a_:
            continue
        st = shot_stats(small[a_:b_], hsv[a_:b_], gray[a_:b_], fps)
        start, end = T(a_), T(b_)
        off_b = nearest(start, beats) if i > 0 else None
        shots.append(dict(shot=len(shots) + 1, start=start, end=end,
                          duration=round(end - start, 3), frames=b_ - a_,
                          cut_in=kinds[i], cut_offset_beat=off_b,
                          cut_offset_half_beat=nearest(start, half) if i > 0 else None,
                          _a=a_, _b=b_, **st))

    events = [dict(type=e["type"], time=T(e["frame"]), duration=e["duration"], note=e["note"]) for e in flash_events]
    events += [dict(type="flash-masked cut", time=T(c["frame"]), duration=c["flash"],
                    note="a flash frame covers the cut - often hides a jump cut") for c in cuts if c["kind"] == "flash-masked cut"]
    events += [dict(type=f["type"], start=T(f["start_frame"]), end=T(f["end_frame"]),
                    note="") for f in fades]
    events += [dict(type=g["type"], start=T(g["start_frame"]), end=T(g["end_frame"]),
                    note="dissolve, inset/scale move, whip pan or fast action - check by eye") for g in gradual]
    events.sort(key=lambda e: e.get("time", e.get("start")))
    for e in events:
        if "time" in e and beats:
            e["beat_offset"] = nearest(e["time"], beats)
            e["half_beat_offset"] = nearest(e["time"], half)

    durs = np.array([s["duration"] for s in shots]) if shots else np.array([0.0])
    cut_times = [s["start"] for s in shots[1:]]
    length = window[1] - window[0]
    on_b = sum(1 for s in shots[1:] if s["cut_offset_beat"] is not None and abs(s["cut_offset_beat"]) <= tol)
    on_h = sum(1 for s in shots[1:] if s["cut_offset_half_beat"] is not None and abs(s["cut_offset_half_beat"]) <= tol)

    # hook
    first3 = [s for s in shots if s["start"] < window[0] + 3]
    k1 = max(2, int(fps))
    hook_motion = camera_motion(gray[:k1], fps)["energy"] if n > 2 else 0
    first_hist = cv2.calcHist([hsv[0]], [0, 1], None, [30, 32], [0, 180, 0, 256])
    last_hist = cv2.calcHist([hsv[-1]], [0, 1], None, [30, 32], [0, 180, 0, 256])
    sim = float(cv2.compareHist(first_hist, last_hist, cv2.HISTCMP_CORREL))
    if luma[-1] < 18:
        loop = "ends on (near) black - a visible restart, not a seamless loop"
    elif sim > 0.8:
        loop = f"last frame resembles the first (similarity {sim:.2f}) - likely built to loop"
    else:
        loop = f"hard restart (first/last frame similarity {sim:.2f})"
    allc = gray.astype(np.float32)
    hook = dict(
        first_cut=cut_times[0] - window[0] if cut_times else None,
        cuts_first_3s=sum(1 for t in cut_times if t < window[0] + 3),
        avg_shot_first_3s=float(np.mean([min(s["end"], window[0] + 3) - s["start"] for s in first3])) if first3 else 0.0,
        motion_first_sec=hook_motion,
        motion_median=float(np.median([s["energy"] for s in shots])) if shots else 0,
        open_luma=round(float(luma[0]), 1), avg_luma=round(float(luma.mean()), 1),
        open_contrast=round(float(np.percentile(allc[0], 98) - np.percentile(allc[0], 2)), 1),
        avg_contrast=round(float(np.mean([s["contrast"] for s in shots])), 1) if shots else 0,
        opening_loudness=(audio or {}).get("opening_loudness_ratio"),
        loop=loop,
    )
    samp = small[np.linspace(0, n - 1, min(24, n)).round().astype(int)]
    lab = np.stack([cv2.cvtColor(s, cv2.COLOR_BGR2LAB) for s in samp]).astype(np.float32)
    ca, cb = float(lab[..., 1].mean() - 128), float(lab[..., 2].mean() - 128)
    colour = dict(palette=palette(samp, 6), lab_a=round(ca, 1), lab_b=round(cb, 1),
                  tone=tone_words(ca, cb, float(hsv[..., 1].mean() / 255)))

    analysis = dict(
        source=dict(file=args.input.name, **info), crop=crop, window=[round(window[0], 3), round(window[1], 3)],
        excluded_ui=excluded, other_windows=other, analysis_fps=fps,
        summary=dict(shots=len(shots), cuts=len(cut_times), length=length,
                     avg_shot=float(durs.mean()), median_shot=float(np.median(durs)),
                     min_shot=float(durs.min()), max_shot=float(durs.max()),
                     cuts_per_sec=len(cut_times) / length if length else 0,
                     cuts_on_beat=on_b, cuts_on_half_beat=on_h, beat_tolerance_ms=int(tol * 1000)),
        cuts=[dict(time=t, kind=s["cut_in"]) for t, s in zip(cut_times, shots[1:])],
        events=events, audio=audio, hook=hook, colour=colour,
        shots=[{k: v for k, v in s.items() if not k.startswith("_")} for s in shots],
        score=[round(float(x), 2) for x in score],
    )
    (args.out / "analysis.json").write_text(json.dumps(analysis, indent=1))
    with open(args.out / "shots.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["shot", "start", "end", "duration", "cut_in", "cut_offset_beat_ms", "camera_move",
                    "move_speed_pct_w_per_s", "tone", "luma", "contrast", "saturation", "palette",
                    "verified_cut_time", "technique", "why_it_works"])
        for s in shots:
            w.writerow([s["shot"], s["start"], s["end"], s["duration"], s["cut_in"],
                        "" if s["cut_offset_beat"] is None else round(s["cut_offset_beat"] * 1000),
                        s["move"], s["speed"], s["tone"], s["luma"], s["contrast"], s["saturation"],
                        " ".join(p["hex"] for p in s["palette"]), "", "", ""])
    contact_sheet(shots, frames, args.out / "contact_sheet.jpg")
    timeline(shots, frames, fps, window, audio, events, args.out / "timeline.png")
    tpl = Path(__file__).resolve().parent.parent / "templates" / "teardown.md"
    write_report(args.out, analysis, tpl)
    print(f"done: {len(shots)} shots, {len(events)} events -> {args.out}/report.md", file=sys.stderr)
    return analysis


if __name__ == "__main__":
    main()
