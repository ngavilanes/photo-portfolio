# reel-lab

Learn editing by taking reels apart, re-shooting them with your own footage (Sony a6700)
and rebuilding them in DaVinci Resolve Studio. Each reel goes through the same loop:

1. **Tear down** - `tools/teardown.py` measures cuts, flashes, fades, beats, colour,
   camera motion and the hook. You add the *why* in the report.
2. **Pick 1-2 techniques** - each becomes a lesson in `lessons/`.
3. **Shoot** your version from the lesson's shot list.
4. **Edit** in Resolve.
5. **Compare** side by side (P4: `tools/compare.py`, not built yet), then fix and repeat.

## Status

| Phase | What | State |
|---|---|---|
| P0 | Layout, templates, media rules | done |
| P1 | `teardown.py` + `validate.py` | done - see validation below |
| P2 | `footage_review.py` for your a6700 clips | next, after your first shoot |
| P3 | Resolve exports: EDL markers, FCPXML, Studio Python API | planned |
| P4 | `compare.py` | planned |

## Setup (Mac or Windows)

You need Python 3.10+ and ffmpeg.

```bash
# Mac
brew install ffmpeg python
# Windows (PowerShell)
winget install Gyan.FFmpeg Python.Python.3.12

cd reel-lab
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Tear down a reel

```bash
python tools/teardown.py media/<reel>.mp4 -o references/<reel>
```

The output goes in `references/<reel>/`:

| File | What it is |
|---|---|
| `report.md` | Summary, hook metrics, shot table, transitions and events, colour, and a blank breakdown to fill in |
| `shots.csv` | One row per shot. The `verified_cut_time`, `technique` and `why_it_works` columns are for you |
| `contact_sheet.jpg` | First, middle and last frame of each shot, its palette and its stats |
| `timeline.png` | Shot blocks to scale, with beats, cuts and events |
| `analysis.json` | Everything, for the other tools |

**Screen recordings work.** The script finds the video area inside the app and skips stretches where
the UI covers it (Control Center and similar). A play-button overlay at the very start can still
show up as a cut. Trim it with `--start`, as done for Airports (`--start 0.3 --end 14.4`).
For best results, use the original file rather than a screen recording.

Useful flags: `--start/--end` (seconds), `--crop W:H:X:Y` or `--no-crop`, `--sensitivity`
(default 3.0; lower finds more cuts), `--fps` (default: source rate up to 60).

### What it measures, and what it cannot see

- **Cuts.** Hard cuts and *flash-masked* cuts, where a 1-2 frame flash covers the cut.
- **Flashes with no cut.** Whole-frame flashes or stutters, and *white object flashes*,
  where a single object turns white for a moment.
- **Fades.** Fades to and from black. A fade never crosses a cut.
- **Gradual change.** Dissolves, growing insets, whip pans and fast action are flagged for you to check by eye.
- **Beats.** The tempo, and every cut and event's offset to the nearest beat and half-beat.
  Beat trackers can report half or double the real tempo.
- **Colour.** The palette per shot and per reel, a Lab tint ("teal", "magenta/purple"),
  brightness, contrast, saturation and clipping.
- **Camera motion (heuristic).** Static, pan, tilt, push in, pull out or handheld, from optical flow.
  The speed is in % of frame width per second.
- **Hook (heuristic).** Time to the first cut, cuts in the first 3s, motion and loudness at the
  start, and whether the reel loops.
- **Blind spots.** A 1-2 frame flash right at a cut is sometimes folded into a plain hard cut.
  A layer appearing *inside* a shot (a composite, a growing inset) is reported as a
  hard cut. Masks, text animation, speed ramps and sound effects are not detected.

## Validation

`tools/validate.py` scores detected cuts against a hand-labelled ground truth:

```bash
python tools/validate.py references/airports/analysis.json references/airports/ground_truth.json
python tools/validate.py media/roughcut/teardown/analysis.json tests/fixtures/roughcut/ground_truth.json
```

| Test | Cuts | Tolerance | Recall | Precision | Timing error |
|---|---|---|---|---|---|
| Synthetic rough cut (`tests/fixtures/roughcut/make.sh`, exact cut times) | 6 | ±2 frames | 100% | 100% | 0 frames |
| Airports reel (screen recording, labelled frame by frame at 60 fps) | 6 | ±50 ms | 100% | 100% | max 40 ms (2.4 frames at 60 fps, about 1 frame of the 30 fps reel) |

Caveat: the detector was tuned on the Airports reel, so that score is in-sample. The real test
is the next reel. The ground truth was labelled before the detector existed, and corrected twice
after reviewing at 60 fps. Both corrections went *against* my first labels, and the tool was right
both times. Details are in `references/airports/ground_truth.json`.

## Media rules

- Video, audio and the generated images of other people's reels are **not committed**.
  See `.gitignore`. They stay in `media/` and in each `references/<reel>/` folder on your machine.
- Reels are for study. Don't post a near-copy of someone else's concept or music.
- Your a6700 footage goes in `media/shoots/<date>/`. Send proxies plus the `.XML` sidecars
  from `PRIVATE/M4ROOT/CLIP/`.

## Layout

```
tools/        teardown.py, validate.py (later: footage_review.py, export_resolve.py, compare.py)
templates/    teardown.md (the "why" breakdown), lesson.md
references/   one folder per reel: report, shots.csv, analysis.json, ground truth
lessons/      the roadmap, then one folder per lesson
shoots/       footage reviews per shoot (P2)
tests/        fixtures; the rough cut is regenerated by tests/fixtures/roughcut/make.sh
media/        ignored by git: reels, footage, renders
```
